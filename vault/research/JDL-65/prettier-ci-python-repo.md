---
id: prettier-ci-python-repo
type: research
name: Prettier --check as a CI gate in a Python-only repo (JDL-65)
created_at: 2026-04-24
created_by: scout
component: ci
---

## Purpose

Settle the 2026-canonical way to run `prettier --check` as a GitHub Actions gate on Atmosphere — a Python-only repo with no Node.js, no `package.json`, and no appetite to introduce either purely for formatting YAML / Markdown / JSON. Target files: `*.yml`, `*.yaml`, `*.md`, `*.json`. Python is ruff + black territory and must stay untouched.

## Entry — initial — 2026-04-24 — scout

**agent:** scout
**refs:** [[.claude/context/roadmap.md]] (M0), [[research/JDL-M0/ci-workflow-uv-python-monorepo.md]]

### Landscape of options ^p001

Three real options exist in 2026. Each is production-viable; the trade-off is about maintenance surface and version control. ^p002

**Option A — `actionsx/prettier@v3`.** The action most commonly cited for "prettier without Node.js." It ships a pre-built native binary so there's no `package.json`, no `npm install`, no `setup-node` step. Usage is one YAML step: `uses: actionsx/prettier@v3` with `args: --check .`. The problem in 2026 is maintenance: the repo's last release was `v3` on 2023-07-27 pinning Prettier 3.0.0, and the last commit to the default branch was 2024-02-07. Open issue #117 ("update v3 series to 3.0.3") has sat since October 2023, and #118 ("Globs are somewhat broken") since November 2023. Prettier itself has shipped through 3.8.3 (released 2026-04-15) with many bug fixes and the new experimental high-performance CLI in 3.6+. Pinning to `actionsx/prettier@v3` means accepting whatever behavior Prettier 3.0.0 has, forever, until someone else forks or the maintainer returns. ^p003

**Option B — `creyD/prettier_action@v4.6`.** Actively maintained (most recent release 2025-06-09, recent pushes in 2025-11), and it can pin `prettier_version` explicitly or fetch latest. It installs Node inside the action and runs prettier; no repo-side `package.json` required for `--check` usage. It is built around an "auto-format and commit" flow (hence the name `prettify code`), and `--check` usage is supported but slightly against the action's grain — you get auto-commit machinery you will never use. Works, but adds an action dependency whose primary value proposition is orthogonal to what we need. ^p004

**Option C — `actions/setup-node@v6` + `npx prettier@<version> --check .`.** GitHub-first-party Node provisioning, then run the Prettier CLI via `npx` with an explicit pinned version. No `package.json`, no third-party action, no auto-commit machinery. The Prettier version is a literal string in `ci.yml` — bumping it is a one-line PR with a visible diff, and Dependabot's `github-actions` ecosystem can monitor `actions/setup-node` while the prettier pin stays under human control. Workflow cost: one extra `setup-node` step (~2-3s cold, cached via `actions/setup-node`'s npm cache backed by a workflow-file `cache-dependency-path`). That's the only price. ^p005

**Option D (rejected) — commit a top-level `package.json` with prettier as a devDep.** This is the Prettier docs' recommended path and the one the autofix.ci flow assumes. It works, but it seeds a Node.js dependency surface in a Python-only repo — `package-lock.json`, a `npm ci` step in CI, a Dependabot ecosystem for npm, and an ongoing maintenance expectation that doesn't pay for itself at the formatting-only scope Atmosphere needs. If prettier plugins enter the picture later (e.g., `prettier-plugin-sql` for dbt model formatting, or a Tailwind plugin) the calculus flips and this becomes the right answer. At M0 it does not. ^p006

### Recommendation ^p007

**Option C: `actions/setup-node@v6` + `npx prettier@<pinned> --check .`.** Best combination of control and minimal surface. Prettier version is explicitly pinned in `ci.yml` (Dependabot-visible as a string), Node provisioning is the GitHub-first-party path, and there is no third-party action to audit or unpin when it goes stale. The `actionsx/prettier@v3` route was the right answer in 2022 but the repo is effectively dormant in 2026; adopting it now means locking to Prettier 3.0.0 and inheriting someone else's abandonware risk for a formatting gate. Option C is a few extra seconds of CI time per run to keep that control in-house. ^p008

### Canonical workflow step ^p009

```yaml
prettier:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v6
      with:
        node-version: "20"
        cache: npm
        cache-dependency-path: .github/workflows/ci.yml
    - run: npx --yes prettier@3.8.3 --check .
```

Notes on the specifics: `node-version: "20"` is Node's current LTS through April 2026 and is what Prettier 3.x is tested against (Prettier dropped Node 14/16 support in 3.0). `cache: npm` with `cache-dependency-path: .github/workflows/ci.yml` uses Simon Willison's no-`package.json` pattern — the workflow file's hash is the cache key, so the npm cache (which `npx` respects) is reused across runs and invalidates any time CI config changes. `npx --yes` suppresses the interactive install prompt on a cache miss. `prettier@3.8.3` is a literal pin; bumps are one-line PRs. `--check .` is the canonical invocation per the Prettier docs: the `.` means "recurse the current directory, pick supported files by extension," which is exactly the right behavior when paired with a `.prettierignore`. ^p010

### Glob: `.` vs explicit `**/*.{yml,yaml,md,json}` ^p011

Prettier docs explicitly recommend `prettier . --check` over explicit globs. The dot-path walks the tree, uses the built-in supported-extensions list (which covers every file type we format: `.yml`, `.yaml`, `.md`, `.json`, and many more), and honors `.prettierignore`. Explicit globs like `"**/*.{yml,yaml,md,json}"` are shell-dependent (need quoting to dodge shell expansion on runners), skip edge-case filenames Prettier knows about (e.g., `package.json` as a literal filename without the extension, or `.prettierrc` with no extension at all), and provide no real safety benefit when `.prettierignore` is the single source of truth for exclusions. Use `.`. ^p012

One future consideration: Prettier 3.6 shipped an experimental new CLI (`--experimental-cli` flag or `PRETTIER_EXPERIMENTAL_CLI=1` env) that is dramatically faster (~20× in reported benchmarks) and is slated to become the default in Prettier 4.0. It's still flagged experimental in 3.8.3. Skip for M0 — the Atmosphere workflow-file set is small enough that legacy-CLI latency is a non-issue; revisit when Prettier 4.0 lands or if CI runtime becomes a concern. ^p013

### `.prettierignore` for a Python / dbt / uv repo ^p014

Prettier's CLI already excludes `.git`, `.svn`, `.hg`, `.jj`, `.sl`, and `node_modules` by default, and additionally honors `.gitignore`. That means anything listed in the repo's `.gitignore` is already excluded — in practice this covers most of the transient artifacts. `.prettierignore` is still worth writing explicitly so the formatting scope is legible at a glance and survives independently of `.gitignore` churn. Gitignore syntax. ^p015

Canonical `.prettierignore` for Atmosphere:

```gitignore
# Python
.venv/
**/.venv/
__pycache__/
**/__pycache__/
*.pyc
.ruff_cache/
.mypy_cache/
.pytest_cache/

# uv
.uv-cache/
uv.lock

# dbt
app/dbt/target/
app/dbt/dbt_packages/
app/dbt/logs/

# Flink / Java build artifacts
app/flink-jobs/**/target/
app/flink-jobs/**/build/
*.jar
*.class

# Data and local state (matches deployment.md ./data/ layout)
data/

# Quarto and notebook artifacts
**/_site/
**/.quarto/
**/.ipynb_checkpoints/

# Generated docs or coverage
coverage/
htmlcov/
.coverage
site/

# Prettier shouldn't touch Python — ruff and black own these
*.py
*.pyi

# Lockfiles Prettier would otherwise reformat in ways the tooling doesn't expect
uv.lock
```

Notes: `uv.lock` is listed twice on purpose — once under the uv block for human readability and once at the bottom to make the "Prettier must not touch lockfiles" intent obvious when someone skims. `*.py` and `*.pyi` are explicit belt-and-braces; Prettier has no Python formatter so it wouldn't touch them anyway, but making the boundary explicit documents the ruff/black ownership. The ClickHouse filesystem cache at `./data/clickhouse/cache` and SeaweedFS data under `./data/seaweedfs` are both caught by the single `data/` entry. ^p016

### Canonical `.prettierrc` (optional but recommended) ^p017

A minimal `.prettierrc` avoids surprise behavior diffs if prettier defaults ever change and documents the one non-default choice we'd typically want for YAML (double quotes):

```json
{
  "printWidth": 100,
  "proseWrap": "preserve"
}
```

`printWidth: 100` matches the ruff / black line length already set in the M0 workflow note. `proseWrap: "preserve"` keeps Markdown line breaks as authored — important for design docs and runbooks where paragraph structure is deliberate. ^p018

### Trade-off summary ^p019

| Option | Repo-side deps | Maintenance surface | Version control | Recommendation |
|---|---|---|---|---|
| A `actionsx/prettier@v3` | None | Third-party, dormant since 2024 | Frozen at Prettier 3.0.0 | Avoid |
| B `creyD/prettier_action@v4.6` | None | Third-party, actively maintained | `prettier_version` input | Viable fallback |
| C `setup-node` + `npx prettier@X` | None | GitHub-first-party + literal pin | Literal version in CI file | **Pick this** |
| D `package.json` + `npm ci` | `package.json`, `package-lock.json` | npm ecosystem | Dependabot-managed | Revisit when plugins needed |

Picking C costs ~2-3 seconds of CI per run (setup-node + npx cold path; cache-warm it's faster) and a three-line diff when bumping Prettier versions. Picking A saves those seconds at the cost of abandoning version control to an unmaintained action. Picking D saves the setup-node step at the cost of owning a `package.json` lifecycle. ^p020

### Integration with the M0 ci.yml skeleton ^p021

Folding this into the workflow skeleton from `research/JDL-M0/ci-workflow-uv-python-monorepo.md` replaces the `actionsx/prettier@v3` job with:

```yaml
  prettier:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v6
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: .github/workflows/ci.yml
      - run: npx --yes prettier@3.8.3 --check .
```

The prettier job stays independent of the python job (separate `runs-on`, separate cache, can run in parallel). No cross-job artifact sharing. ^p022

### Sources ^p023

- [actionsx/prettier repo](https://github.com/actionsx/prettier) — dormant; last release v3 on 2023-07-27, last commit 2024-02-07.
- [creyD/prettier_action marketplace page](https://github.com/marketplace/actions/prettier-action) — v4.6 released 2025-06-09.
- [Prettier CI docs](https://prettier.io/docs/ci) — canonical "pin a version" guidance.
- [Prettier CLI docs](https://prettier.io/docs/cli) — `prettier . --check` is the canonical invocation.
- [Prettier ignore docs](https://prettier.io/docs/ignore) — gitignore syntax, defaults.
- [Prettier 3.6 release notes](https://prettier.io/blog/2025/06/23/3.6.0) — experimental fast CLI, slated for 4.0.
- [Simon Willison TIL: npm cache with npx and no package.json](https://til.simonwillison.net/github-actions/npm-cache-with-npx-no-package) — the `cache-dependency-path` pattern used in option C.
- [Simon Willison TIL: Prettier in GitHub Actions](https://til.simonwillison.net/github-actions/prettier-github-actions) — corroborating pattern for the npx route.
- [actions/setup-node](https://github.com/actions/setup-node) — v6.4.0 released 2026-04-20. ^p024
