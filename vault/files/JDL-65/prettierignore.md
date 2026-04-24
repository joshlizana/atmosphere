---
id: 01KPZBGETK39CWWH60F2Y578B8
type: file
name: .prettierignore
created_at: 2026-04-24T09:00Z
created_by: log/01KPZBGETK39CWWH60F2Y578B8
component: repo
---

## Purpose
Tracks changes to `.prettierignore`, the repo-root Prettier exclusion list that scopes the CI `prettier --check` gate to YAML, Markdown, and JSON and keeps Prettier out of Python sources, tool caches, generated artifacts, compose runtime data, and local agent state.

## 2026-04-24T09:00Z — initial
- agent: log/01KPZBGETK39CWWH60F2Y578B8
- refs: [[research/JDL-65/prettier-ci-python-repo]], [[decisions/JDL-65/20260424T0853Z-ruff-only-drops-black]]

At the start of JDL-65 (M0 — Repo, CI, and host prep), `.prettierignore` was created at the repo root to define the exclusion surface for the `prettier --check .` CI gate. Prettier's CLI already honors `.gitignore` and has built-in defaults for `.git` and `node_modules`; this file exists as explicit belt-and-braces so the formatting scope is legible at a glance and survives independently of `.gitignore` churn. The file uses gitignore syntax throughout. ^p001

Scope of exclusions, in the order they appear in the file: Python sources (`*.py`, `*.pyi`) — explicit boundary marker declaring ruff's ownership per the M0 tooling decision; Python tool caches and virtualenvs (`__pycache__/`, `.venv/`, `.ruff_cache/`, `.mypy_cache/`, `.pytest_cache/`, `.uv-cache/`); build and distribution output (`build/`, `dist/`, `*.egg-info/`); the uv lockfile (`uv.lock`) as a machine-generated TOML that is committed but must not be reformatted; generated dbt directories (`app/dbt/target/`, `app/dbt/dbt_packages/`, `app/dbt/logs/`); generated Quarto directories (`_site/`, `.quarto/`); compose runtime data (`data/` — the `./data/<service>/` bind-mount tree described in the deployment notes); the Obsidian local workspace (`vault/.obsidian/`); Claude agent local state (`.claude/`); and OS cruft (`.DS_Store`). Section ordering and comment style mirror `.gitignore` so the two files read as siblings when skimmed. ^p002

Two deviations from the research note's example are worth recording. First, `uv.lock` is listed once under its "uv lockfile" section rather than duplicated at a trailing "lockfiles" block as the research example suggested; the single entry with a clear comment carries the intent without the redundancy. Second, the research example's `**/.venv/`, `**/__pycache__/`, and `*.pyc` lines were omitted because Prettier's gitignore-syntax matching walks the tree and the un-prefixed `.venv/` / `__pycache__/` entries already match at any depth, and `*.pyc` is redundant once `*.py` and the caches are excluded. Also deliberately absent are Flink/Java artifacts (`*.jar`, `*.class`, `app/flink-jobs/**/target/`) from the research example — Flink jobs are a post-M0 concern (M5+) and the invocation's design field did not list them. ^p003

Two boundaries the file intentionally does not cross: `vault/` is not excluded wholesale because vault Markdown should be formatted; only `vault/.obsidian/` is excluded. Likewise `app/dbt/` is not excluded wholesale because top-level dbt YAML files (`dbt_project.yml`, `profiles.yml`, model property YAMLs) should be formatted; only the generated `target/`, `dbt_packages/`, and `logs/` subdirectories are excluded. ^p004
