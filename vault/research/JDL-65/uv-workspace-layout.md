---
id: uv-workspace-layout
type: research
name: uv workspace layout for a multi-service Python monorepo (JDL-65 / M0)
created_at: 2026-04-24
created_by: scout
component: repo
---

## Purpose

Establish the 2026-canonical uv workspace layout for Atmosphere's M0 repo skeleton: root `pyproject.toml` with `[tool.uv.workspace]` members glob, per-member `pyproject.toml` minimum shape, dev-dependency placement, `[dependency-groups]` (PEP 735) vs `[project.optional-dependencies]` (PEP 621) trade-offs, inter-member dependency resolution, and glob-discovery gotchas across `app/services/*` and `app/flink-jobs/*`.

## Entry — initial — 2026-04-24 — scout

**agent:** scout
**refs:** [[.claude/context/roadmap.md]] (M0 §Build), [[.claude/context/operations.md]], [[vault/research/JDL-M0/ci-workflow-uv-python-monorepo]] (deleted in prior commit but referenced for CI continuity)

### Workspace shape and package/virtual distinction ^p001

uv workspaces are Cargo-style: a single root `pyproject.toml` declares members via `[tool.uv.workspace]`, a single `uv.lock` covers the whole tree, and one `.venv` is shared across every member. Members can be applications or libraries; every included directory must contain its own `pyproject.toml`. The workspace root is itself a member and must have a `[project]` table with a `name` — even if it is a pure orchestrator with no code of its own. ^p002

The root can be either a **package** (default, `[tool.uv] package = true`, built and installed editable alongside members — requires a build backend) or a **virtual** project (`[tool.uv] package = false`, not built/installed, only its dependencies land in the venv). Atmosphere's root has no code to publish and exists only to organize `app/services/*`, `app/flink-jobs/*`, `app/prefect`, and shared tooling — so `package = false` is the correct posture. The virtual root still needs a unique `[project] name` that does not collide with any member (astral-sh/uv#10xxx-era footgun: naming both the root and the core service `atmosphere` produces `Two workspace members are both named 'atmosphere'`). Use `atmosphere-workspace` for the root, reserve the plain `atmosphere` or `atmosphere-common` for the shared library member. ^p003

Workspace members themselves pick `package = true|false` independently. Libraries that other members import (`app/services/common`) must be `package = true` so they install editable and are importable by sibling members. Applications that only produce an entrypoint and never get imported by anything else (`app/services/spout`, `app/services/sleuth`, `app/services/oracle`, PyFlink jobs) can be `package = false` — their dependencies still resolve into the shared venv and their modules are still runnable via `uv run --package spout python -m spout`. Setting app members to `package = false` means they don't need a `[build-system]` table, which eliminates the build-backend choice for every service that will never be published. ^p004

### Root `pyproject.toml` — the canonical shape ^p005

```toml
[project]
name = "atmosphere-workspace"
version = "0.0.0"
requires-python = "==3.12.*"
description = "Atmosphere streaming lakehouse — workspace root"

[tool.uv]
package = false

[tool.uv.workspace]
members = [
  "app/services/*",
  "app/flink-jobs/*",
  "app/prefect",
]

[dependency-groups]
dev = [
  "pytest>=8",
  "pytest-asyncio>=0.24",
  "ruff>=0.6",
  "black>=24",
]
dbt = [
  "dbt-core>=1.9",
  "dbt-duckdb>=1.9",
]

[tool.uv.sources]
# Shared lib is picked up automatically by the workspace glob; no explicit
# source entry needed at the root unless the root itself depends on it.

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.black]
line-length = 100
target-version = ["py312"]

[tool.pytest.ini_options]
testpaths = ["app"]
addopts = "--import-mode=importlib"
```

`requires-python` is enforced workspace-wide — uv takes the intersection of every member's `requires-python` and rejects configurations that produce an empty set. Pinning `==3.12.*` at the root and letting members inherit by not re-declaring (or declaring the same constraint) keeps the floor uniform. PyFlink is the binding constraint; drop to `>=3.12` when PyFlink ships a 3.13 wheel. ^p006

`addopts = "--import-mode=importlib"` on the root pytest config is not optional for workspace monorepos — pytest's default `prepend` mode caches modules by basename, so two members each having a `tests/test_helpers.py` collide with `imported module 'test_helpers' has this __file__ attribute... which is not the same as the test file we want to collect`. `importlib` mode isolates module namespaces per-package and is the documented fix. ^p007

### Per-member `pyproject.toml` — minimum shapes ^p008

**Shared library (`app/services/common/pyproject.toml`) — `package = true`, importable by everyone else:** ^p009

```toml
[project]
name = "atmosphere-common"
version = "0.0.0"
requires-python = "==3.12.*"
dependencies = [
  "pydantic>=2.8",
]

[build-system]
requires = ["uv_build>=0.5,<0.6"]
build-backend = "uv_build"

[tool.uv]
package = true
```

`uv_build` is uv's native build backend (since uv 0.5, default for `uv init` since mid-2025); it is zero-config, fast, and tightly integrated with `uv build`/`uv publish`. Hatchling still works and is the right choice if you need VCS-driven versions, custom build hooks, or extension modules — none of which apply to a pure-Python shared lib. ^p010

**Application member (`app/services/spout/pyproject.toml`) — `package = false`, depends on shared lib:** ^p011

```toml
[project]
name = "spout"
version = "0.0.0"
requires-python = "==3.12.*"
dependencies = [
  "atmosphere-common",
  "aiohttp>=3.10",
  "aiokafka>=0.11",
  "prometheus-client>=0.21",
  "websockets>=13",
]

[tool.uv]
package = false

[tool.uv.sources]
atmosphere-common = { workspace = true }
```

Inter-member dependencies always require **two** entries: the package name in `[project] dependencies` AND the `{ workspace = true }` entry in `[tool.uv.sources]`. Declaring only one half produces `'atmosphere-common' is included as a workspace member, but is missing an entry in 'tool.uv.sources'`. `uv add --package spout atmosphere-common` writes both automatically and is the recommended add path rather than hand-editing. Workspace sources are always editable — `import atmosphere_common` from inside `spout/` resolves to the live source tree, not a cached wheel. ^p012

`package = false` on application members means no `[build-system]` is required; the member exists purely as a container for dependencies and a runnable module tree. Entrypoints for these services are `docker compose` commands (`python -m spout`), not installed console scripts, so the lack of a build backend is a feature. ^p013

### Dev dependencies — root-only, via `[dependency-groups]` ^p014

PEP 735 `[dependency-groups]` is the 2026 replacement for the historical `[tool.uv.dev-dependencies]` and is also the correct choice over `[project.optional-dependencies]` (PEP 621) for local-only tooling. The distinction is explicit and load-bearing:

- `[project.optional-dependencies]` becomes *extras* on the published wheel — `pip install atmosphere-common[plot]`. These are user-facing feature flags for a published library. Atmosphere publishes nothing, so there is no use case for optional-dependencies in this repo. ^p015
- `[dependency-groups]` are local-only, never leak into published metadata, and are designed exactly for dev tooling (pytest, ruff, black, dbt). The default group name `dev` is auto-synced by `uv sync` / `uv run` unless `--no-default-groups` is passed. Additional groups (`test`, `dbt`, `lint`) are explicit via `--group <name>`. Groups can include other groups via `{include-group = "lint"}`. ^p016

Dev dependencies live at the **workspace root only**, not in per-member pyprojects. Rationale: the workspace has one shared `.venv`, so a pytest installed for one member is installed for all; duplicating the declaration in each member creates three version-drift opportunities per tool. `uv sync --all-packages --all-groups` (or the tighter `--group dev --group dbt`) from the root hydrates the whole tree in one pass. The dbt CLI is installed via a dedicated `dbt` group at the root — not as a member project — because dbt is tooling that operates on `app/dbt/`, not a Python package we author. ^p017

### CI invocation — the sync command ^p018

The idiomatic CI install is:

```bash
uv sync --locked --all-packages --all-extras --all-groups
```

Flag-by-flag:

- `--locked` — fail if `uv.lock` is stale relative to any member's dependencies. Reproducibility gate.
- `--all-packages` — install every workspace member's dependencies, not just the root's. **Not the default** (tracked at astral-sh/uv#9755); forgetting this is the #1 workspace CI bug — tests in member packages raise `ModuleNotFoundError` because only the root was installed.
- `--all-extras` — pick up any `[project.optional-dependencies]` declared on members (currently none in Atmosphere, but cheap insurance).
- `--all-groups` — include every dependency group, not just `dev`. Equivalent to `--group dev --group dbt --group …` but survives adding new groups without a CI edit. ^p019

Omit `--all-packages` in CI only if you want to test "root-only" install as a separate gate. Running `uv sync` from inside a member directory silently uses that member's view of the workspace, which is rarely what CI wants — always run from the repo root. ^p020

### Glob-discovery and exclude gotchas ^p021

Six gotchas specific to `members = ["app/services/*", "app/flink-jobs/*"]`:

1. **Glob paths must not be prefixed with `./`** — `members = ["app/services/*"]` works, `members = ["./app/services/*"]` does not. Silent-in-some-versions, error-in-others; either way it is not the supported form. ^p022

2. **Every matched directory must contain a `pyproject.toml` or uv errors hard** (astral-sh/uv#17196, still open as of 2026). A stale `app/services/foo/` left over from a branch switch — or a directory a developer created but hasn't yet populated — blocks every `uv sync` with `Workspace member '.../app/services/foo' is missing a 'pyproject.toml' (matches: 'app/services/*')`. No warn-only flag yet. Workaround: either delete the empty dir, or add it to `exclude = [...]` until it has a pyproject. This is load-bearing for M0 because the roadmap lands Spout (M4), Sleuth + Oracle (M7), etc. in staggered milestones — so the glob match `app/services/*` will match directories that don't yet have a pyproject if we scaffold them early. Recommendation: **do not create member directories until the milestone that populates them**, or add stub `pyproject.toml` files the moment a directory appears. ^p023

3. **Exclude patterns apply after members evaluate.** Early-0.4.x had a bug where `exclude = ["projects/b"]` didn't override `members = ["projects/*"]` (astral-sh/uv#7071), fixed in #7175. At current uv versions this works correctly — but note that exclude paths should be written relative to the workspace root and match the same form as the member globs. ^p024

4. **Nested pyproject.toml files in non-member directories can surprise uv.** If `app/dbt/` has a `pyproject.toml` (for dbt's Python-side tooling) but is *not* listed in `members`, uv still treats it differently depending on CWD — running `uv run` from inside `app/dbt/` can pick up that local pyproject as a standalone project even though the rest of the repo treats it as foreign (astral-sh/uv#11302, #17308). Keep non-member pyprojects out of glob-reachable paths, or list them explicitly under `members` so they participate in the workspace. For Atmosphere: the dbt project lives at `app/dbt/` and is a dbt project, not a Python package — it has `dbt_project.yml`, not `pyproject.toml`. No conflict. ^p025

5. **Workspace root `name` must be distinct from every member `name`.** If the root uses `atmosphere` and any member also uses `atmosphere`, uv fails with `Two workspace members are both named 'atmosphere'`. Using `atmosphere-workspace` for the root sidesteps this once and never needs revisiting. ^p026

6. **A single `uv.lock` covers the whole workspace — there is no per-member lockfile.** A change to `app/services/oracle/pyproject.toml` updates the single root `uv.lock`; CI's `--locked` gate catches stale commits. Developers adding deps should always use `uv add --package <member> <dep>` rather than hand-editing a member's pyproject, because the CLI form performs the lock update and the `[tool.uv.sources]` reconciliation in one shot. ^p027

### Inter-member resolution mechanics ^p028

When a member declares `atmosphere-common` in its dependencies and `atmosphere-common = { workspace = true }` in `[tool.uv.sources]`, uv resolves the name against the workspace roster first — no PyPI lookup, no wheel build, no versioning conflict with a same-named public package. Installation is editable (the shared lib's source directory is added to the venv via a `.pth` link), so edits in `app/services/common/src/atmosphere_common/` are immediately visible to `import atmosphere_common` in every other member without a rebuild. ^p029

Version numbers on workspace members are not meaningful for intra-workspace resolution — uv always uses the local source regardless of the version declared. Members' versions only matter if you publish them. For a never-published monorepo, keeping every member at `version = "0.0.0"` is fine and avoids the update-in-fifteen-places-for-a-release dance. ^p030

If the same package appears as a PyPI dependency of one member and a workspace member of another (e.g. a hypothetical `pydantic` workspace member colliding with the PyPI `pydantic`), uv warns and uses the workspace source — but this is a real footgun worth avoiding by not giving workspace members names that shadow common PyPI packages. The `atmosphere-common` / `atmosphere-workspace` naming above avoids this. ^p031

### Recommended repo layout ^p032

```
atmosphere/
├── pyproject.toml                 # workspace root, package=false
├── uv.lock                        # single shared lockfile
├── .python-version                # 3.12
├── app/
│   ├── services/
│   │   ├── common/
│   │   │   ├── pyproject.toml     # package=true (importable lib)
│   │   │   └── src/atmosphere_common/__init__.py
│   │   ├── spout/
│   │   │   ├── pyproject.toml     # package=false
│   │   │   └── src/spout/__init__.py
│   │   ├── sleuth/
│   │   │   └── pyproject.toml     # (added at M7)
│   │   └── oracle/
│   │       └── pyproject.toml     # (added at M7)
│   ├── flink-jobs/
│   │   └── bronze-writer-post/
│   │       └── pyproject.toml     # (added at M5)
│   ├── prefect/
│   │   └── pyproject.toml         # (added at M10)
│   ├── dbt/
│   │   └── dbt_project.yml        # NOT a uv member
│   ├── quarto/                    # NOT a uv member; .qmd files
│   └── tests/
│       └── (workspace-level tests — root pytest rootdir)
```

The `src/<package_name>/` layout inside each member is recommended (not required): it keeps tests from accidentally importing the package from its source directory via CWD, forces editable-install correctness, and aligns with the `--import-mode=importlib` pytest configuration. ^p033

Per-member test files can live under `app/services/<svc>/tests/` and the root pytest config sweeps them in via `testpaths = ["app"]`. Unit tests that span multiple members live at `app/tests/`. ^p034

### Open questions for follow-up ^p035

- Whether to also declare `tool.uv.dev-dependencies` for tooling that lives in its own CI stage (e.g. mypy, if introduced post-M0) vs. everything in `[dependency-groups]` with groups as the split axis. Current recommendation: one source of truth (`[dependency-groups]`), groups as the split axis. ^p036
- Whether PyFlink (which has its own on-prem Java/Python mismatch history) resolves cleanly under `uv sync` against a workspace or whether `app/flink-jobs/*` members need a constraint override for `apache-flink`. To be answered at M5. ^p037

### Sources ^p038

- uv workspaces reference: https://docs.astral.sh/uv/concepts/projects/workspaces/
- uv dependencies reference: https://docs.astral.sh/uv/concepts/projects/dependencies/
- uv settings reference: https://docs.astral.sh/uv/reference/settings/
- uv build backend: https://docs.astral.sh/uv/concepts/build-backend/
- pydevtools handbook — uv monorepo: https://pydevtools.com/handbook/how-to/how-to-set-up-a-python-monorepo-with-uv-workspaces/
- DEV.to — 3 things I wish I knew: https://dev.to/aws/3-things-i-wish-i-knew-before-setting-up-a-uv-workspace-30j6
- kfchou — uv Monorepo Workspaces: https://kfchou.github.io/uv-monorepo/
- tomasrepcik — Python workspaces: https://tomasrepcik.dev/blog/2025/2025-10-26-python-workspaces/
- uv#9755 (default --all-packages): https://github.com/astral-sh/uv/issues/9755
- uv#6935 (workspace sync semantics): https://github.com/astral-sh/uv/issues/6935
- uv#17196 (empty-dir glob match error): https://github.com/astral-sh/uv/issues/17196
- uv#7071 / #7175 (exclude bug + fix): https://github.com/astral-sh/uv/issues/7071
- uv#9415 (nested pyproject doc gap): https://github.com/astral-sh/uv/issues/9415
- uv#11302 / #17308 (nested pyproject CWD behavior): https://github.com/astral-sh/uv/issues/11302
- PEP 735 dependency groups: https://peps.python.org/pep-0735/
- Gauge.sh — validating uv workspace deps: https://www.gauge.sh/blog/how-to-validate-uv-workspace-dependencies
