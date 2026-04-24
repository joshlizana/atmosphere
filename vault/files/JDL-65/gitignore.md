---
id: 01KPZBG82WX3QBSX7V6KD7E27K
type: file
name: gitignore
created_at: 2026-04-24T09:00Z
created_by: log/01KPZBG82WX3QBSX7V6KD7E27K
component: repo
---

## Purpose
Tracks the lifecycle of the repository root `.gitignore` — the single source of truth for what the atmosphere repo refuses to track. Covers Python toolchain outputs (bytecode, venv, uv cache, linter caches), build artifacts, dbt-duckdb generated artifacts, Quarto render outputs, compose runtime bind-mount state under `./data/`, environment files, Obsidian workspace metadata under `vault/.obsidian/`, the top-level `.claude/` agent state tree, OS and editor cruft, and Flink local checkpoint/savepoint directories. Notable carve-outs: `uv.lock` and `.env.example` are both deliberately committed and the file documents this inline.

## 2026-04-24T09:00Z — initial
- agent: log/01KPZBG82WX3QBSX7V6KD7E27K
- refs: [[decisions/JDL-65/20260424T0852Z-uv-workspace-declared-at-m0]], [[decisions/JDL-65/20260424T0853Z-ruff-only-drops-black]]

Forge created `.gitignore` at the repo root as part of JDL-65 M0 scaffolding and committed it as `ad27793` on branch `JDL-65-m0-repo-ci-host-prep` with message `chore(JDL-65): add root .gitignore for M0 scaffolding`. The file is grouped into labeled sections by concern: Python bytecode and native extensions, virtualenvs, uv cache, Python tool caches, build/dist artifacts, dbt-duckdb artifacts under `app/dbt/`, Quarto render outputs, compose runtime bind-mount state (`data/`), env files, Obsidian local state (`vault/.obsidian/`), Claude agent local state (`.claude/`), OS cruft, editor swap/config, and Flink local checkpoint/savepoint directories. ^p001

Two deliberate non-ignores carry inline comments in the file so the carve-outs are not lost to future edits. `uv.lock` is explicitly kept out of the uv section because the lockfile is the canonical pinned dependency set the whole workspace reproduces from; ignoring it would break the "one commit describes one reproducible dependency graph" property. `.env.example` is explicitly kept out of the env section because it is the documented template of every required environment key for the compose stack (Lakekeeper service passwords, Postgres credentials, Grafana admin, Prefect API key, OpenMetadata admin, SeaweedFS S3 key pair) and needs to be tracked to serve as the contributor-facing documentation of the `.env` contract. ^p002

`vault/.obsidian/` is scoped narrowly to the Obsidian workspace metadata subdirectory; the containing `vault/` tree itself is tracked because it holds the project's research, decision, file, incident, and result notes. `.claude/` is ignored at the repo root even though the project does keep some tracked content under `.claude/context/` — those tracked paths are carved out by the repo's conventions and tooling rather than by `.gitignore` exceptions in this file, and this same pattern is the reason vault file-mirror notes for `.claude/...` source files require `git add -f` to stage. ^p003

Forge noted pre-existing working-tree churn not touched by this invocation: two deleted files under `vault/research/JDL-M0/`, an untracked `CLAUDE.md` at the repo root, and a new vault research note. Only `.gitignore` was staged and committed in `ad27793`, preserving the one-invocation-one-file contract. ^p004

## 2026-04-24T09:25Z — addendum
- agent: log/01KPZBG82WX3QBSX7V6KD7E27K
- refs: [[research/JDL-65/prettier-ci-python-repo]], [[files/JDL-65/prettierignore]]

Forge modified `.gitignore` as part of JDL-65 M0 Prettier-gate remediation, adding a single line (`CLAUDE.md`) directly under `.claude/` inside the existing `# Claude agent local state` section. No reordering, no new section, no re-include. The change committed as `e485e27` on `JDL-65-m0-repo-ci-host-prep` with message `chore(JDL-65): ignore root CLAUDE.md` — scoped to the one file via `git commit -- <path>` as a belt-and-suspenders measure against parallel-agent staging pollution. One file changed, one insertion. ^p001

The intent is documented in the commit body: `CLAUDE.md` stays in the working tree as a Claude-Code context import but is excluded from git and, because Prettier's CLI honors `.gitignore` by default, is therefore also excluded from the `prettier --check .` CI gate that had been failing on it. This is functionally equivalent to adding an entry to `.prettierignore`, but placing it in `.gitignore` instead removes the file from git tracking entirely — which matches the pre-existing treatment of the sibling `.claude/` tree (agent-local state, not repo-tracked). Keeping both agent-local surfaces in one gitignore section keeps the carve-out visible in one place. ^p002

Forge noted pre-existing working-tree churn left untouched: two untracked vault research files under `vault/research/` outside the invocation scope. The one-invocation-one-file contract was preserved — only `.gitignore` went into `e485e27` even though subsequent commits on the branch (`60a0202`, `a6b65cf`, `2729d58`) have since advanced the tip with unrelated Prettier-gate remediation work. ^p003
