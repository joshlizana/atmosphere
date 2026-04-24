---
id: 01KPZBK0JT8ASWNFG38Q13F6TF
type: file
name: profiles.yml
created_at: 2026-04-24T09:02Z
created_by: log/01KPZBK0JT8ASWNFG38Q13F6TF
component: dbt
---

## Purpose
Tracks the lifecycle of `app/dbt/profiles/profiles.yml` — the CI-safe dbt profile consumed by the M0 `dbt parse` gate. Declares the `atmosphere` profile with a single `ci` target of `type: duckdb` and no `path:`, yielding an in-memory DuckDB that needs no credentials, opens no network connections, and writes nothing to disk. Real data-plane connection configuration (Lakekeeper REST catalog + SeaweedFS S3) will be introduced in M8 when actual models land; this file is the minimum shape required to make `dbt parse --profiles-dir ./profiles` exit 0 against an empty project.

## 2026-04-24T09:02Z — initial
- agent: log/01KPZBK0JT8ASWNFG38Q13F6TF
- refs: [[research/JDL-65/dbt-parse-empty-project-scaffolding]]

Forge created `app/dbt/profiles/profiles.yml` at the repo as part of JDL-65 M0 scaffolding and committed it as `b311b25` on branch `JDL-65-m0-repo-ci-host-prep` with message `build(JDL-65): add CI-safe in-memory DuckDB dbt profile for \`dbt parse\``. The file is nine lines — a four-line top-of-file comment explaining the CI-parse purpose and signalling that real connection config arrives in M8, followed by the five-line profile block declaring the `atmosphere` profile with `target: ci` and a single `outputs.ci` mapping of `type: duckdb`. The shape matches the authoritative research note p009–p010 and the recommended M0 file in p019 exactly. ^p001

The profile carries no `path:` key. Omitting `path:` is equivalent to `path: ':memory:'` for dbt-duckdb and auto-sets `database` to `memory`; the explicit-memory form was skipped in favour of the shorter omission because both behave identically and the top-of-file comment already makes CI intent obvious on review. No credentials, no env-var references, no schema, no threads setting — the minimal viable shape for `dbt parse` to load the profile and satisfy its mandatory resolution step without ever opening a connection. ^p002

Forge surfaced and resolved a scaffolding gotcha during the write: the `app/` directory did not exist at the repo root at invocation time, so every parent of the target path (`app/`, `app/dbt/`, `app/dbt/profiles/`) had to be created before the `Write` tool would succeed. Forge ran `mkdir -p /home/josh/atmosphere/app/dbt/profiles` first, then wrote the file, and captured the pattern as a forge memory entry (`gotcha_app_directory_m0.md` plus a one-line index entry) so other early-M0 invocations writing anywhere under `app/...` will pre-create parents rather than hitting the same failure mode. ^p003

Only `app/dbt/profiles/profiles.yml` was staged in `b311b25`; the working tree's unrelated uncommitted changes — two deleted research notes under `vault/research/JDL-M0/`, untracked `CLAUDE.md` at the repo root, untracked empty skeleton directories under `app/prefect/`, `app/services/`, and `app/dbt/models/`, and untracked vault notes under `vault/files/JDL-65/` and `vault/research/JDL-65/` — were deliberately left alone, preserving the one-invocation-one-file contract. ^p004
