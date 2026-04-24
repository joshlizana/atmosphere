---
id: 01KPZBHGNPZGV4HRW01CBKX01H
type: file
name: pyproject.toml
created_at: 2026-04-24T09:01Z
created_by: log/01KPZBHGNPZGV4HRW01CBKX01H
component: repo
---

## Purpose
Tracks changes to the root `pyproject.toml`, the virtual-package workspace root for the Atmosphere monorepo — carrying the Python version floor, the uv workspace declaration and explicit member list, the shared dev dependency group, and tool configuration for ruff (lint + format) and pytest.

## 2026-04-24T09:01Z — initial
- agent: log/01KPZBHGNPZGV4HRW01CBKX01H
- refs: [[decisions/JDL-65/20260424T0852Z-uv-workspace-declared-at-m0]], [[decisions/JDL-65/20260424T0853Z-ruff-only-drops-black]], [[research/JDL-65/uv-workspace-layout]], [[research/JDL-65/setup-uv-workspace-ci-2026]]

At the start of JDL-65 (M0 — Repo, CI, and host prep), Forge created `pyproject.toml` at the repo root as the virtual uv workspace root for the Atmosphere monorepo. The file is 33 lines and landed in commit `8d416bf` with message `build(JDL-65): add root pyproject.toml for uv workspace`. This entry records the file creation; the two architectural decisions it implements (uv workspace declared at M0 with `members = []`, and ruff-only Python lint+format) are captured separately as `decision` events and referenced above. ^p001

The root is virtual: `[tool.uv] package = false` declares the root as never-built and never-installed, which is why no `[build-system]` table exists. The `[project]` table still carries `name = "atmosphere-workspace"`, `version = "0.0.0"`, and `requires-python = "==3.12.*"` to satisfy uv's expectation of a project table at the workspace root. The Python floor is set to `==3.12.*` because PyFlink's supported-version matrix tops out at 3.12 and the workspace-wide version is the intersection of every member's requirement. ^p002

The `[tool.uv.workspace]` block has `members = []` — an explicit empty list rather than a glob like `app/services/*`. This implements the workspace-at-M0 decision directly: future milestones (M4 for Spout, M5 and M6 for the Flink jobs and shared `atmosphere-common` library, M7 for Sleuth and Oracle) will append the appropriate member paths one at a time as those services land. An explicit list sidesteps the uv#17196 hard-error where any directory matching a glob without its own `pyproject.toml` breaks every `uv sync`, which would otherwise fire immediately because M0 creates empty skeleton directories under `app/services/` and `app/flink-jobs/`. ^p003

The `[dependency-groups]` table uses PEP 735 with a single `dev` group covering the full M0 tooling surface: `pytest>=8`, `ruff>=0.6`, `pre-commit>=3.8`, `dbt-core>=1.10,<1.11`, and `dbt-duckdb>=1.9,<1.10`. Dev tools use `>=` lower bounds to track upstream velocity; the two dbt packages are pinned to minor-version ranges to match the Design's stability posture. Black is absent by design — the ruff-only decision dropped it. ^p004

Ruff configuration follows the decision: `[tool.ruff]` sets `line-length = 100` and `target-version = "py312"`; `[tool.ruff.lint]` selects rule families `E, F, W, I, UP, B, SIM`; and `[tool.ruff.format]` is present as an empty table to signal that ruff owns formatting (it activates ruff's format defaults, which are black-compatible). Pytest configuration is minimal but load-bearing: `testpaths = ["app/tests"]` scopes collection, and `addopts = "--import-mode=importlib"` is the mode required for a workspace monorepo — without it, basename collisions on files like `test_helpers.py` across workspace members would break collection. ^p005
