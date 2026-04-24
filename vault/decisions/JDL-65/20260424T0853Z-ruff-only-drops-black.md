---
id: 01KPZB3BS27DZTD274ED1EXJ9D
type: decision
name: 20260424T0853Z-ruff-only-drops-black
created_at: 2026-04-24T08:53Z
created_by: log/01KPZB3BS27DZTD274ED1EXJ9D
component: repo
---

## Purpose
Records the decision to drop black entirely and consolidate Python linting and formatting on ruff alone — `ruff check` for lint and `ruff format --check` for format — across the CI gates, pre-commit hooks, and the root `pyproject.toml` dev-dependency set.

## 2026-04-24T08:53Z — initial
- agent: log/01KPZB3BS27DZTD274ED1EXJ9D
- refs: [[decisions/JDL-65/20260424T0852Z-uv-workspace-declared-at-m0]]

At the start of JDL-65 (M0 — Repo, CI, and host prep), we chose between two ways to shape the Python formatting toolchain in the initial repo scaffolding. Alternative A was to keep both black and ruff as the original roadmap text specified: black handles formatting, ruff handles linting, each with its own CI step, pre-commit hook, and dev dependency. Alternative B was to use ruff alone — `ruff format` is a drop-in black-compatible implementation running in the same Rust-backed binary that powers `ruff check`, so one tool can own both gates. We chose Alternative B. ^p001

The primary reasoning is that the ruff formatter is a drop-in black-compatible implementation, so keeping black alongside ruff adds a second toolchain, a second CI step, a second pre-commit hook, and a second dev dependency for no behavioral benefit. One tool, one config surface, one install is strictly cheaper than two while producing the same formatted output. ^p002

Implication for M0 file-writing: the root `pyproject.toml` dev group drops `black`, the `[tool.black]` table is omitted, and a `[tool.ruff.format]` section configures any non-default format options. The `.github/workflows/ci.yml` has `uv run ruff format --check .` where `uv run black --check .` would have gone. The `.pre-commit-config.yaml` uses ruff's official pre-commit hooks for both lint and format, with no separate black hook. `.claude/context/roadmap.md` has been edited in four places to remove black references, tracked as a separate `file-modified` event. ^p003
