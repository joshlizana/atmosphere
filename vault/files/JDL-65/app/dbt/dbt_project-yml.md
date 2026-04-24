---
id: 01KPZBJBJ1JHZGN3TJC2GXE24R
type: file
name: dbt_project-yml
created_at: 2026-04-24T09:01Z
created_by: log/01KPZBJBJ1JHZGN3TJC2GXE24R
component: dbt-duckdb
---

## Purpose
Tracks the lifecycle of `/home/josh/atmosphere/app/dbt/dbt_project.yml` — the minimum dbt project manifest that lets `dbt parse` run green in CI against an empty models tree during M0. Serves as the declaration of project name, profile binding, dbt-core version pin, and the canonical path layout the project assumes. Model/seed/snapshot/test configuration blocks are intentionally absent until the silver and gold layers land in M8.

## 2026-04-24T09:01Z — initial
- agent: log/01KPZBJBJ1JHZGN3TJC2GXE24R
- refs: [[research/JDL-65/dbt-parse-empty-project-scaffolding]]

Forge created `app/dbt/dbt_project.yml` as part of JDL-65 M0 scaffolding and committed it as `39b93ed` on branch `JDL-65-m0-repo-ci-host-prep` with message `build(JDL-65): add minimum dbt_project.yml for M0 parse gate`. The file is 43 lines and carries a top-of-file comment block naming itself, pointing at `.claude/context/conventions.md` for the platform model-naming conventions (`stg_<source>`, `fct_<event>`, `dim_<entity>`, `mart_<subject>` all under `bluesky.dbt.*`), and noting that `dbt-duckdb` is pinned in the repo's `pyproject.toml`. ^p001

Declared keys: `name: 'atmosphere'`, `version: '1.0.0'`, `config-version: 2`, `profile: 'atmosphere'`, and `require-dbt-version: '>=1.10.0,<1.11.0'` — the version pin matches the `dbt-core>=1.10,<1.11` constraint already in `pyproject.toml` so a dbt-core upgrade that slips the floor or the ceiling is rejected by both the Python resolver and dbt itself. The explicit path keys (`model-paths`, `seed-paths`, `test-paths`, `analysis-paths`, `macro-paths`, `snapshot-paths`, `target-path`, `clean-targets`) are stated with their defaults so the path contract reads at a glance rather than being implicit. ^p002

Intentionally absent: the `models:`, `seeds:`, `snapshots:`, `tests:`, `sources:`, `macros:`, and `analyses:` config blocks. None of them have a concrete consumer at M0 (the models tree is empty and the first models don't land until M8) and every one of them would be dead configuration until then. The file is the minimum surface that lets `dbt parse` succeed as the CI gate requires, nothing more. ^p003

Gotchas surfaced during the create invocation: Forge's pre-existing memory warned that `Write` against `/home/josh/atmosphere/app/...` at M0 required a prior `mkdir -p` because the `app/` tree does not yet exist — that memory was empirically stale. `Write` created the `app/dbt/` parent directory inline on this invocation, and Forge corrected the memory file `gotcha_app_directory_m0.md` in place rather than leaving the stale guidance to cause future invocations to run unnecessary `mkdir` prep. ^p004

Known follow-up out of scope for this invocation: `app/dbt/profiles/profiles.yml` (referenced by this file via `profile: 'atmosphere'`) does not yet exist. A CI `dbt parse` run cannot succeed until that profile file lands alongside this one; that's a separate forthcoming create invocation. ^p005
