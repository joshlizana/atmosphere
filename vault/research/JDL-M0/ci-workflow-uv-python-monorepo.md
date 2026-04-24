---
id: ci-workflow-uv-python-monorepo
type: research
name: CI workflow pattern for uv-managed Python monorepo (M0)
created_at: 2026-04-24
created_by: scout
component: ci
---

## Purpose

Establish the conventional 2026 pattern for a GitHub Actions CI workflow on the Atmosphere repo: Python-heavy monorepo, uv as package manager, gates for pytest + ruff + black + prettier + dbt parse. M0 acceptance criterion.

## Entry — initial — 2026-04-24 — scout

**agent:** scout
**refs:** [[.claude/context/roadmap.md]] (M0), [[.claude/context/operations.md]]

### Findings ^p001

uv has first-class Cargo-style workspace support as of 2026 and is the de-facto standard for new Python projects. A workspace declares member packages in the root `pyproject.toml` under `[tool.uv.workspace]` and shares a single `uv.lock`. Dev dependencies belong at the workspace root under `[dependency-groups]` so one `uv sync` hydrates the whole tree. ^p002

The idiomatic CI install is `uv sync --locked --all-extras --all-packages --dev`: `--locked` fails if `uv.lock` is stale (reproducibility gate), `--all-packages` installs every workspace member (without it, sync only touches the root package), `--all-extras` picks up optional extras, `--dev` pulls the default dev group. `--all-packages` is not yet the default (astral-sh/uv#9755 tracks making it so), so omitting it is a common footgun in workspace CI. ^p003

`astral-sh/setup-uv@v7` is the current canonical pin. `enable-cache: true` writes the uv cache to GitHub Actions cache automatically, keyed off `uv.lock` by default. No need to hand-roll `actions/cache` blocks. Pin the uv version explicitly (`version: "0.11.7"` or similar) rather than floating — avoids surprise breakage when a new uv minor ships. ^p004

Python 3.12 is forced by PyFlink. PyFlink officially supports 3.9–3.12 only; 3.13 is not yet supported as of 2026 (Flink Python docs, nightlies.apache.org). dbt-core gained 3.13 support in 1.10+, transformers/PyIceberg/prefect all run on 3.13, but PyFlink is the floor. Pick 3.12 and revisit when Flink publishes a 3.13 wheel. ^p005

`dbt parse` returns exit code 0 on success, 1 on handled error (model syntax, bad refs, missing deps), 2 on unhandled error — per dbt's exit-code contract (docs.getdbt.com/reference/exit-codes). It is exit-code-stable enough to gate PRs without grep wrappers. The known `--fail-fast` / `--no-fail-fast` bug (dbt-core#11897) does not affect the baseline exit code; it only affects whether parse stops on first error or collects all. CI can treat `dbt parse` as a normal shell step. ^p006

For prettier without Node.js in the repo, two viable paths: (1) `actionsx/prettier@v3` runs the prettier CLI directly from the action without requiring `package.json` — cleanest for a Python-only repo; (2) a tiny `package.json` with prettier pinned as a devDep plus `npm ci && npx prettier --check .` — heavier but gives deterministic version pinning alongside a `.prettierrc`. Path (1) is lighter for M0; path (2) becomes worth it once prettier plugins enter the picture. In a Python repo prettier typically formats `*.yml`/`*.yaml`, `*.md`, `*.json` — exclude `*.py` (ruff/black own that) and `app/dbt/target/` (generated). ^p007

### Recommended workflow skeleton ^p008

```yaml
# .github/workflows/ci.yml
name: ci
on:
  pull_request:
  push:
    branches: [main]
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
jobs:
  python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v7
        with:
          version: "0.11.7"
          enable-cache: true
          python-version: "3.12"
      - run: uv sync --locked --all-extras --all-packages --dev
      - run: uv run ruff check .
      - run: uv run black --check .
      - run: uv run pytest
      - run: uv run --directory app/dbt dbt parse --profiles-dir ./profiles
  prettier:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actionsx/prettier@v3
        with:
          args: --check "**/*.{yml,yaml,md,json}"
```

### Recommended root `pyproject.toml` stub ^p009

```toml
[project]
name = "atmosphere"
version = "0.0.0"
requires-python = "==3.12.*"

[tool.uv.workspace]
members = ["app/services/*", "app/flink-jobs/*", "app/prefect"]

[dependency-groups]
dev = [
  "pytest>=8",
  "ruff>=0.6",
  "black>=24",
  "dbt-core>=1.9",
  "dbt-duckdb>=1.9",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.black]
line-length = 100
target-version = ["py312"]
```

### Gotchas ^p010

- `--all-packages` is easy to forget and silently installs only the root package — tests in member packages then ImportError. Put it in the workflow from day one. ^p011
- `dbt parse` requires a `profiles.yml`. For CI against an empty project, ship a minimal DuckDB in-memory profile under `app/dbt/profiles/profiles.yml` that resolves without credentials; otherwise parse fails on profile lookup even when no models exist. ^p012
- Pin `astral-sh/setup-uv` to a major tag (`@v7`) but pin `version:` to an exact uv release — the action tag and the uv CLI version are independent. ^p013
- Prettier 3.x treats some YAML edge cases aggressively (prettier#17016 — YAML parsed as Markdown in rare cases). If CI starts failing on a valid YAML file, pin prettier to a known-good minor and investigate before updating. ^p014
- Keep `app/dbt/target/`, `app/dbt/dbt_packages/`, and `.venv/` in `.prettierignore` — generated JSON in `target/` will otherwise dominate CI time and produce noisy diffs. ^p015

### Sources ^p016

- uv workspaces: https://docs.astral.sh/uv/concepts/projects/workspaces/
- uv GitHub Actions integration: https://docs.astral.sh/uv/guides/integration/github/
- setup-uv repo: https://github.com/astral-sh/setup-uv
- uv#9755 (default --all-packages): https://github.com/astral-sh/uv/issues/9755
- uv#6935 (workspace sync): https://github.com/astral-sh/uv/issues/6935
- dbt exit codes: https://docs.getdbt.com/reference/exit-codes
- dbt-core Python 3.13 tracker: https://github.com/dbt-labs/dbt-core/issues/11106
- PyFlink installation: https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/python/installation/
- actionsx/prettier: https://github.com/actionsx/prettier
- prettier#17016 (YAML edge case): https://github.com/prettier/prettier/issues/17016
