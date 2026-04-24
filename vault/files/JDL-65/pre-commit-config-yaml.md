---
id: 01KPZC7RJNPFM1BB5A3JZ969XJ
type: file
name: .pre-commit-config.yaml
created_at: 2026-04-24T09:05Z
created_by: log/01KPZC7RJNPFM1BB5A3JZ969XJ
component: repo
---

## Purpose
Tracks the lifecycle of `.pre-commit-config.yaml` at the repo root — the local pre-commit hook manifest that mirrors the Python lint/format gates from `.github/workflows/ci.yml` so contributors catch ruff failures before pushing. Two repos are pinned: `astral-sh/ruff-pre-commit` (ruff lint + ruff-format) and `pre-commit/pre-commit-hooks` (trailing-whitespace, end-of-file-fixer, check-yaml, check-toml, check-merge-conflict).

## 2026-04-24T09:05Z — initial
- agent: log/01KPZC7RJNPFM1BB5A3JZ969XJ
- refs: [[decisions/JDL-65/20260424T0853Z-ruff-only-drops-black]], [[files/JDL-65/pyproject-toml]], [[files/JDL-65/gitignore]], [[files/JDL-65/prettierignore]]

Forge created `.pre-commit-config.yaml` at the repo root as part of JDL-65 M0 scaffolding and committed it as a single-file commit on branch `JDL-65-m0-repo-ci-host-prep`. The file opens with a top-of-file comment block per the repo YAML convention, explaining that the config mirrors the Python lint/format gates from `.github/workflows/ci.yml`, that contributors install the hooks locally via `uv run pre-commit install` after a workspace sync (`uv sync --all-packages --all-extras --all-groups`), and that the CI workflow remains the authoritative gate list. Two repos are declared under the top-level `repos:` key. ^p001

The first repo entry is `astral-sh/ruff-pre-commit` pinned to `v0.8.6`, a recent stable tag that exposes both the `ruff` and `ruff-format` hook ids and is compatible with the `ruff>=0.6` dev-dependency floor declared in the root `pyproject.toml`. The `ruff` hook carries `args: [--fix]` so local runs auto-apply safe fixes on commit, and both ruff hooks are scoped with `types_or: [python, pyi]` so they only touch Python sources and stub files. There is no black hook and no separate formatter — this matches the Alternative B choice captured in [[decisions/JDL-65/20260424T0853Z-ruff-only-drops-black]] to consolidate Python lint and format on ruff alone, with `ruff format` replacing `black` as a drop-in black-compatible formatter. ^p002

The second repo entry is `pre-commit/pre-commit-hooks` pinned to `v5.0.0`, with the five sanity hooks specified by the M0 Design: `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-toml`, and `check-merge-conflict`. No Prettier hook is configured — Prettier's `prettier --check` runs only in CI (per the `.prettierignore` scoping captured in [[files/JDL-65/prettierignore]]) and is deliberately not mirrored in pre-commit to keep local install friction low and avoid a Node toolchain dependency on every contributor's workstation. No `dbt parse` hook is configured either; CI owns that gate. ^p003

Forge noted two context items with the invocation. First, at commit time `.github/workflows/ci.yml` referenced in the file's top-of-file comment did not yet exist on disk — the `.github/workflows/` directory was empty and the comment pointed at the path as a forward reference matching the Design-stated intent. The CI workflow was a separate M0 Forge invocation and now exists. Second, before the commit the working tree carried unstaged `vault/` and `CLAUDE.md` entries; Forge explicitly `git add`ed only `.pre-commit-config.yaml` and confirmed `git diff --cached --name-only` showed only that single path before committing, preserving the one-invocation-one-file contract. ^p004
