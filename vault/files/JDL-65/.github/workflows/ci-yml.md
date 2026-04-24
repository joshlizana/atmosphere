---
id: 01KPZC8SHBT7A4K8NSYFAN5YB7
type: file
name: ci-yml
created_at: 2026-04-24T09:13Z
created_by: log/01KPZC8SHBT7A4K8NSYFAN5YB7
component: repo
---

## Purpose
Tracks the lifecycle of `/home/josh/atmosphere/.github/workflows/ci.yml` — the M0 green-light GitHub Actions workflow that enforces the repo's lint / format / test / parse gates on every pull request and every push to `main`. Runs two parallel jobs on `ubuntu-latest`: a `python` job driving uv-managed `ruff check`, `ruff format --check`, `pytest`, and `dbt parse`; and a `prettier` job driving pinned `npx prettier --check`. This file is the single source of truth for the CI contract referenced by the M0 acceptance criterion.

## 2026-04-24T09:13Z — initial
- agent: log/01KPZC8SHBT7A4K8NSYFAN5YB7
- refs: [[research/JDL-65/setup-uv-workspace-ci-2026]], [[research/JDL-65/prettier-ci-python-repo]], [[research/JDL-65/dbt-parse-empty-project-scaffolding]], [[decisions/JDL-65/20260424T0853Z-ruff-only-drops-black]], [[files/JDL-65/pyproject-toml]], [[files/JDL-65/app/dbt/dbt_project-yml]], [[files/JDL-65/app/tests/test_smoke-py]]

Forge created `.github/workflows/ci.yml` as part of JDL-65 M0 scaffolding and committed it as `3b5ae7c` on branch `JDL-65-m0-repo-ci-host-prep` with message `ci(JDL-65): add M0 green-light GitHub Actions workflow`. The file is 78 lines and is the only workflow file in the repo — a single consolidated workflow rather than separate per-gate files, matching the M0 acceptance criterion that a single `ci.yml` runs every green-light gate. ^p001

The workflow triggers on both `pull_request:` (every PR regardless of target branch) and `push: branches: [main]` so the gate runs on merge commits as well as on the PR preview, catching any drift introduced by a merge conflict resolution. Concurrency is grouped on `ci-${{ github.ref }}` with `cancel-in-progress: true`, so consecutive pushes to the same branch cancel the in-flight run and only the latest commit's gate completes — avoiding wasted runner minutes on superseded commits. ^p002

Two jobs run in parallel, both on `runs-on: ubuntu-latest`. The `python` job: `actions/checkout@34e1148` → `astral-sh/setup-uv@08807647` with `version: "0.11.7"` and `python-version: "3.12"` → `uv sync --locked --all-packages --all-extras --all-groups` → `uv run ruff check` → `uv run ruff format --check` → `uv run pytest` → `uv run dbt parse --profiles-dir ./profiles --no-partial-parse`. The `prettier` job: `actions/checkout@34e1148` → `actions/setup-node@48b55a01` with npm cache keyed on `ci.yml` → `npx --yes prettier@3.8.3 --check .`. The two jobs share the checkout step but otherwise run fully isolated. ^p003

Every third-party action is pinned by commit SHA with a trailing `# <version>` comment for Dependabot's GitHub Actions updater to bump against: `actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4.3.1`, `astral-sh/setup-uv@08807647 # v8.1.0`, `actions/setup-node@48b55a01 # v6.4.0`. The uv CLI is pinned via the action's `version: "0.11.7"` input, and Python is pinned via `python-version: "3.12"` — these two pins together reproduce the workspace-root `requires-python = "==3.12.*"` constraint from `pyproject.toml` and the uv lockfile's pinned uv version in CI, so runner drift surfaces here rather than downstream. ^p004

Deliberate non-inclusions: no `package.json` is committed (prettier is invoked via `npx --yes prettier@3.8.3` rather than as a workspace dependency — the Python repo has no JS dependency graph to manage), no `black` step (the ruff-only decision dropped it and `ruff format --check` owns formatting), no `dbt deps` step (no packages consumed in the M0 empty dbt project), and no separate workflow file (one `ci.yml` fulfills the M0 gate contract and also keeps Dependabot-surfaced bump PRs scoped to one file). ^p005

Gotchas surfaced during Forge's create invocation: the pathspec ordering of `git commit -- <path> -m "msg"` fails because git expects flags before `--`; Forge pivoted to `git commit -m "msg"` after confirming the staged index contained only `ci.yml` via `git diff --cached --name-only`. This ordering gotcha is already captured in Forge's memory under `gotcha_git_commit_pathspec_order.md`. ^p006
