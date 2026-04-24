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

## 2026-04-24T09:15Z — addendum
- agent: log/01KPZCRVY284P05ZW3FPXNFH4Q
- refs: [[files/JDL-65/prettierignore]]

Forge modified `.prettierignore` as part of JDL-65 M0 Prettier-gate remediation and committed the change as `a6b65cf` on branch `JDL-65-m0-repo-ci-host-prep` with message `chore(JDL-65): broaden .prettierignore to exclude vault/ entirely`. The single-line entry `vault/.obsidian/` was replaced with a whole-tree `vault/` exclusion, and the surrounding comment was expanded from the one-line `# Obsidian local workspace state` header to a four-line block documenting why Prettier cannot round-trip Obsidian-authored Markdown: table cell padding, @-reference line spacing, `^pNNN` block-id anchors, and `![[wikilink]]` embeds. All other entries and their ordering were preserved. ^p001

This change narrows one of the two boundaries the original initial entry recorded as deliberate. The initial note's fourth paragraph stated that `vault/` was intentionally not excluded wholesale because "vault Markdown should be formatted"; that reasoning was wrong in practice — vault Markdown is authored through Obsidian, whose output conventions diverge from Prettier's canonical format enough that running `prettier --check` across the tree would either fail CI on every Obsidian-touched note or silently reformat block-id anchors and wikilinks on save. The whole-tree exclusion resolves the tension by putting the entire vault out of Prettier's scope; the comment block at the line records the rationale so a future edit does not re-narrow the scope without understanding why. ^p002

The complementary exclusion pattern for `app/dbt/` (the initial note's other "deliberately not wholesale" carve-out) is unchanged — only the generated `target/`, `dbt_packages/`, and `logs/` subdirectories are excluded, and top-level dbt YAML files remain in Prettier's scope. `.gitignore` was untouched per the invocation constraint; vault content stays tracked in git regardless of Prettier's formatting scope. Forge verified `git diff --cached --name-only` was clean before committing and used a scoped `-- .prettierignore` pathspec on `git commit` to avoid any parallel-agent staging leak, producing a one-file one-commit change. ^p003
