---
id: dbt-parse-empty-project-scaffolding
type: research
name: Minimum scaffolding for dbt parse against an empty dbt project (M0 / JDL-65)
created_at: 2026-04-24
created_by: scout
component: dbt
---

## Purpose

Establish the 2026-canonical minimum scaffolding to make `dbt parse` exit 0 in CI against an empty Atmosphere dbt project at `app/dbt/`. The adapter is `dbt-duckdb`, CI has no external databases, and the gate must be deterministic enough to merge-block on. This note covers the required `dbt_project.yml` fields, the CI-safe `profiles.yml`, how dbt resolves the profiles location, exit-code semantics, and known 2026 bugs that could affect the gate.

## Entry — initial — 2026-04-24 — scout

**agent:** scout
**refs:** [[.claude/context/roadmap.md]] (M0), [[.claude/context/components/dbt-duckdb.md]], [[.claude/context/components/prefect.md]] (CI gate mention)

### What `dbt parse` actually does ^p001

`dbt parse` reads every file in the project, evaluates Jinja, resolves `ref()` / `source()` / `config()` calls, and writes `target/manifest.json` plus `target/perf_info.json`. It does **not** execute SQL, does **not** connect to the warehouse, and does **not** require network access to the data platform. This is the defining distinction from `dbt compile`, which runs introspective queries and therefore needs a live warehouse connection. For an empty `models/` directory the command still succeeds — it emits a manifest with zero model nodes and reports zero models found. This is the exact property M0 relies on. ^p002

### Profile is still required, even though parse never connects ^p003

A working `profiles.yml` resolvable to the project's configured `profile:` name is mandatory for `dbt parse` despite no connection being opened. dbt loads the profile because project configuration can condition on `{{ target }}` and on the adapter type (e.g., `{{ target.type == 'duckdb' }}`) during parse. A missing or unresolvable profile fails parse with a "Could not find profile" runtime error and exit code 1. The profile does not need to point at a reachable database; for dbt-duckdb it only needs a valid shape. ^p004

### Minimum `dbt_project.yml` ^p005

The strictly required fields as of dbt-core 1.10.x (2026 baseline) are `name` and `config-version`. `profile` is conditionally required — it defaults to the project `name` if omitted, but relying on that implicit default is a footgun because it couples two unrelated names. Everything else has sensible built-in defaults (`model-paths: ["models"]`, `seed-paths: ["seeds"]`, `macro-paths: ["macros"]`, `test-paths: ["tests"]`, `target-path: "target"`). `config-version: 2` is the current schema version; there is no `3` in 2026 and `1` has been removed since dbt-core 1.5. ^p006

Minimal viable file for `app/dbt/dbt_project.yml`:

```yaml
name: 'atmosphere'
version: '0.0.0'
config-version: 2
profile: 'atmosphere'
```

That is sufficient for `dbt parse` to exit 0 with no models, seeds, macros, or tests present. Adding `model-paths: ["models"]` etc. is explicit but redundant at M0. ^p007

### Minimum `profiles.yml` for dbt-duckdb ^p008

The absolute minimum for dbt-duckdb is `type: duckdb` with no `path` — this runs entirely in-memory. The `database` attribute auto-sets to `memory`. Nothing persists, nothing writes to disk, no credentials are consumed. Ideal for CI. From the dbt-duckdb README and dbt docs: "The simplest configuration requires only `type: duckdb` in your profile. This runs an in-memory database — all data is lost after the run completes." ^p009

Minimal CI-safe `profiles.yml`:

```yaml
atmosphere:
  target: ci
  outputs:
    ci:
      type: duckdb
```

Explicit `path: ':memory:'` is equivalent to omitting `path:` entirely and is slightly more self-documenting if we want CI intent to be obvious in review. Both forms behave identically. ^p010

### Profile location resolution (2026 order) ^p011

dbt-core 1.10.x resolves `profiles.yml` in this precedence, first match wins:

1. `--profiles-dir <path>` CLI flag — explicit, highest precedence.
2. `DBT_PROFILES_DIR` environment variable.
3. Current working directory (where `dbt` is invoked) — present since the dbt 1.3 regression documented in dbt-core#6066 that quietly changed this from being last to being third. This has *not* been reverted; it is the 2026 behavior.
4. `~/.dbt/profiles.yml` — the historical default, now the last fallback.

Two practical consequences for CI: (a) a stray `profiles.yml` in the project directory will shadow anything in `~/.dbt/`, which can silently flip test behavior vs. developer laptops where `~/.dbt/profiles.yml` often exists from prior projects; (b) relative paths in `DBT_PROFILES_DIR` have had bugs historically — use absolute paths in CI. The robust pattern is `--profiles-dir ./profiles` (or equivalent) with the file co-located in the dbt project, which is what the M0 CI-workflow research recommends. ^p012

### Exit-code semantics ^p013

Per dbt's formal exit-code contract (`docs.getdbt.com/reference/exit-codes`):

- **0** — invocation completed without error.
- **1** — completed with at least one *handled* error (model syntax error, missing ref, bad permissions, schema-file violation, invalid project config). For parse specifically this covers every parse-time failure we care about: unparseable Jinja, malformed YAML, undefined `ref()`, duplicate resource names, invalid schema.yml shape.
- **2** — completed with an *unhandled* error (Ctrl-C, network interruption, Python traceback inside dbt). Rare in CI; usually indicates a dbt-core bug or an infra problem, not a project problem.

For the M0 gate this maps cleanly: treat any non-zero as a failure and let GitHub Actions' default behavior (fail the step) fail the job. No grep wrappers needed, no parsing stdout. ^p014

### Known 2026 bugs that could affect the gate ^p015

**dbt-core#11897** (filed 2025-08-06 against dbt-core 1.10.6 with dbt-duckdb): `dbt parse --no-fail-fast` does not change behavior — parse always stops at the first error. The flag was documented to allow collecting every parse error in one invocation but has never worked as advertised. The issue has been closed as `wontfix` / "not planned" by dbt Labs. **Impact on M0:** none for the exit-code contract — exit code is still 1 on any parse failure, which is what the CI gate checks. The only visible consequence is ergonomic: if multiple parse errors land in one PR, the author sees them one at a time across successive CI runs rather than all at once. Not worth working around at M0. ^p016

**dbt-core#10571** (partial parsing + secret env vars): partial parsing silently disables itself when profile connection info references a `{{ env_var('...') }}` that starts with `DBT_ENV_SECRET_`. Not relevant at M0 (no env vars in the minimal profile) but worth noting for when real credentials land later — the CI workflow should pass `--no-partial-parse` to force a full parse on every run anyway (see p018). ^p017

**CI hygiene — always pass `--no-partial-parse`.** Partial parsing is an optimization for incremental local edits; it compares file mtimes against a cached `target/partial_parse.msgpack`. In CI every run starts with an empty `target/` so partial parsing adds no value and introduces a category of weird-cache-state bugs (dbt-core#11363, dbt-core#8872, dbt-core#11164 are all partial-parse-specific failures that do not occur on full parse). The dbt docs explicitly recommend `--no-partial-parse` in CI. ^p018

### Recommended M0 files ^p019

Three files, total ~15 lines:

```
app/dbt/
├── dbt_project.yml
├── profiles/
│   └── profiles.yml
└── models/           # empty directory, committed via .gitkeep
    └── .gitkeep
```

`app/dbt/dbt_project.yml`:

```yaml
name: 'atmosphere'
version: '0.0.0'
config-version: 2
profile: 'atmosphere'
```

`app/dbt/profiles/profiles.yml`:

```yaml
atmosphere:
  target: ci
  outputs:
    ci:
      type: duckdb
```

CI invocation (matches the form in the ci-workflow research note):

```
uv run --directory app/dbt dbt parse --profiles-dir ./profiles --no-partial-parse
```

This exits 0 on success, 1 on any parse error, and never touches a network or a persistent database. `models/.gitkeep` keeps the directory in git so dbt's default `model-paths: ["models"]` does not warn about a missing path. ^p020

### Version pinning note ^p021

dbt-core 1.10.x is the 2026-current stable track; dbt-core 1.11 is in staged release as of April 2026 (the March 2026 compatible release was skipped to stabilize 1.11.6). dbt-duckdb 1.9.6+ targets dbt-core >= 1.8 and DuckDB 1.1.x. Pin explicitly in `pyproject.toml` rather than floating — dbt minor-version updates have historically broken the parse path (cf. dbt-core#11363 partial-parse regression in 1.8). Suggested pins for M0: `dbt-core==1.10.*`, `dbt-duckdb==1.9.*`. Revisit when 1.11 reaches compatible-track GA. ^p022
