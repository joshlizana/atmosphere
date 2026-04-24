---
id: setup-uv-workspace-ci-2026
type: research
name: Canonical astral-sh/setup-uv + uv sync pattern for workspace CI (2026)
created_at: 2026-04-24
created_by: scout
component: ci
---

## Purpose

Pin down the 2026-canonical `astral-sh/setup-uv` usage pattern and the exact `uv sync` flag combination for a uv workspace repo running its CI gates (pytest, ruff, black, dbt parse) on GitHub Actions. Covers: current major tag and release cadence, SHA-pinning vs version pinning, cache defaults, and which `uv sync` flags are defaults vs must-specify for a workspace. Closes out the M0 (JDL-65) question of what the workflow `.github/workflows/ci.yml` should contain for the uv side.

## Entry — initial — 2026-04-24 — scout

**agent:** scout
**refs:** [[.claude/context/roadmap.md]] (M0), [[.claude/context/operations.md]], astral-sh/setup-uv v8.1.0 (2026-04-16), astral-sh/uv#9755 (closed not-planned), astral-sh/uv#6935 (closed), astral-sh/uv#15656 (open, 2026-03 activity), astral-sh/uv#17351 (open)

### setup-uv: v8 is the current major, mutable tags are gone ^p001

The current major line is `astral-sh/setup-uv@v8`. v8.0.0 shipped 2026-03-29 as the "immutable releases and secure tags" release and was followed by v8.1.0 on 2026-04-16 (adds a `no-project` input; not relevant to our use case). v7.6.0 (2026-03-16) was the last v7 release and added Astral's mirror as the default uv download source. ^p002

The v8.0.0 breaking change that matters for our workflow file: **minor and major tags are no longer published**. `@v8`, `@v8.0`, `@v8.1` do not resolve. Only full semver tags (`@v8.1.0`) are valid. The explicit rationale Astral gave was supply-chain hardening — a floating major tag lets a compromised maintainer ship a silent update into every consumer's next run. The practical pattern is to pin by commit SHA with a version comment, which is what Astral's own docs and marketplace listing now show. ^p003

Canonical pin for today: `astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b # v8.1.0`. Dependabot's GitHub Actions ecosystem updates SHA-pinned action references and bumps the trailing comment in lockstep, so pinning to SHA does not create a stale-action maintenance burden if Dependabot is wired up. ^p004

### Pin the uv CLI version too, not just the action ^p005

The action and the uv CLI it installs are separate pins. The `version:` input controls which uv release gets downloaded and added to PATH; if omitted, setup-uv reads `required-version` from `uv.toml` / `pyproject.toml` and falls back to "latest" if neither declares one. Astral's own GitHub Actions guide calls out pinning an explicit uv version as best practice so a fresh uv release cannot change lockfile resolution semantics or CLI flag behavior mid-PR. The uv minor cadence is roughly weekly — the release-notes tail in v8.1.0 alone references checksums for uv 0.11.3 through 0.11.7. A floating uv is a real footgun on a long-lived repo. ^p006

### Cache behavior: `enable-cache: auto` is the default and does the right thing ^p007

`enable-cache` defaults to `"auto"`, which resolves to **enabled on GitHub-hosted runners, disabled on self-hosted**. This is the desired behavior for Atmosphere's CI — we're on GitHub-hosted `ubuntu-latest`. No need to set `enable-cache: true` explicitly; the default already covers it. ^p008

The default `cache-dependency-glob` tracks every file that can influence resolution: `**/*requirements*.txt`, `**/*requirements*.in`, `**/*constraints*.txt`, `**/*constraints*.in`, `**/pyproject.toml`, `**/uv.lock`, `**/*.py.lock`. Crucially this globs recursively, so for a workspace with `pyproject.toml` in every member the cache invalidates whenever any member's manifest changes — exactly right. No manual cache-key construction needed. ^p009

The cache stores the uv download cache (`~/.cache/uv` by default). On a cache hit, `uv sync --locked` still has to wire the venv and install, but wheel downloads are skipped; on Atmosphere's dependency surface (transformers, PyIceberg, dbt-duckdb, pyflink) the wall-clock saving is material. ^p010

### uv sync in a workspace: `--all-packages` is NOT the default ^p011

The question "does `uv sync` at the workspace root install all members" has a definitive answer and a relevant policy-level history. Per the official workspaces doc: "`uv run` and `uv sync` operate on the workspace root by default." Only the **root** member's environment is synced unless you either `cd` into a member, pass `--package <name>`, or pass `--all-packages`. ^p012

This was proposed as the new default in astral-sh/uv#9755 ("Make `--all-packages` the default?") on 2024-12-10. Charlie Marsh closed it as not-planned the same day with the following reasoning, which settles the question for the foreseeable future: "I think we're somewhat unlikely to change this… Cargo, for example, behaves the same way: the workspace root is a member, just like any other, and by default `cargo run` uses the current directory which can be overridden with `-p`." No tracking issue has reopened the question since; a related 2025-06 comment requesting a `[tool.uv] sync-all-packages = true` config escape hatch went unanswered. ^p013

The practical upshot: **every uv-workspace CI invocation must specify `--all-packages` explicitly**, or it silently installs only the root and any `pytest` command that imports from a non-root member will fail with an `ImportError` that is not obviously a CI-config issue. This is the dominant footgun in uv-workspace CI. The M0 pattern established in the prior research note (workflow skeleton) already got this right. ^p014

### `--locked` is the stale-lockfile gate ^p015

`--locked` raises an error if `uv.lock` would be updated by the sync rather than silently re-resolving and patching the lockfile. For CI this is the reproducibility assertion — a PR that touched `pyproject.toml` without running `uv lock` fails visibly. The alternative flag `--frozen` uses the lockfile without even checking it's up-to-date, which is wrong for CI because a stale lockfile would still pass. Use `--locked`, never `--frozen`, in CI. ^p016

### `--all-extras` and `--dev` in a workspace ^p017

Semantics confirmed against the current CLI reference and the sync concepts page:

- Extras (PEP 621 `[project.optional-dependencies]`) are **not** synced by default. `--all-extras` includes them all. We likely don't have extras at M0 but including the flag is cheap insurance against a future `[project.optional-dependencies]` block being added to a member and silently dropping out of CI. ^p018
- Dev dependency groups (PEP 735 `[dependency-groups]`) **are** synced by default; `--no-dev` opts out. So strictly speaking `--dev` is redundant on a default sync. However, explicit `--dev` documents the intent in the workflow file and is defensive against any future uv policy shift. The combined cost is zero bytes. ^p019
- `--all-groups` would include non-default dependency groups. The design for Atmosphere keeps a single `dev` group at the workspace root (see prior research note's stub `pyproject.toml`), so `--all-groups` is unnecessary right now. It's worth noting in case we later split dev groups (e.g., a `docs` group for Quarto) and want CI to exercise all of them. ^p020

### Canonical flag combination for CI ^p021

```
uv sync --locked --all-packages --all-extras --dev
```

Or equivalently omitting the redundant `--dev`:

```
uv sync --locked --all-packages --all-extras
```

Both are correct; the former documents intent more loudly. I prefer the explicit form for M0 — a future reader of the workflow file should not have to remember that dev is synced by default. ^p022

### Related open gotchas (not blocking M0, worth knowing) ^p023

- **uv#15656** ("Install dev dependencies of transitive workspace packages when targeting a single package", opened 2026-03-12, still open): when you `uv sync --package foo`, dev dependencies of workspace packages `foo` depends on are **not** installed, even with `--all-extras --all-groups`. Only `--all-packages` installs them. This does not affect our M0 CI (we use `--all-packages`) but matters if we ever add per-service build jobs that target a single workspace member. ^p024
- **uv#17351** ("uv.lock for workspaces", open): a workspace produces one root `uv.lock` — individual members do not get their own lockfile. If a downstream consumer ever wants to vendor, say, `app/services/common` independently, they'd have to reconstruct a lockfile from the monorepo. Not a problem inside the monorepo; only relevant if we split a library out. ^p025
- **Documentation drift.** docs.astral.sh/uv/guides/integration/github/ (WebFetch response) currently shows `@v7` examples while the released action is v8.1.0 and the marketplace listing shows v8 SHAs. Do not trust that integration-guide page as authoritative for the major tag in 2026; trust the `setup-uv` repo's README and release notes. The docs page has not been updated to reflect the v8 release yet. ^p026

### Final recommendation for the M0 workflow ^p027

```yaml
- uses: astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b # v8.1.0
  with:
    version: "0.11.7"          # pin CLI too; bump via Dependabot / manual PRs
    python-version: "3.12"     # PyFlink floor; Flink still lacks 3.13 wheels
    # enable-cache defaults to "auto" — no need to set
- run: uv sync --locked --all-packages --all-extras --dev
```

Every downstream gate runs via `uv run` (`uv run pytest`, `uv run ruff check .`, `uv run black --check .`, `uv run --directory app/dbt dbt parse`) so it picks up the workspace venv wired by the sync step. ^p028
