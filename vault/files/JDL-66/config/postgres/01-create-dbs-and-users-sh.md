---
id: 01KPZQTP9KZNRD8S554XV0A247
type: file
name: 01-create-dbs-and-users.sh
created_at: 2026-04-24T14:30Z
created_by: log/01KPZQTP9KZNRD8S554XV0A247
component: postgres
---

## Purpose
Tracks the lifecycle of `config/postgres/01-create-dbs-and-users.sh` — the first-boot initialization script the docker-library/postgres entrypoint runs to provision the four per-service logical databases (`lakekeeper`, `prefect`, `openmetadata`, `grafana`) and their matching owner roles on a fresh Postgres data directory. Executed only when `PG_VERSION` is absent from the data directory; idempotent-by-absence on every subsequent boot.

## 2026-04-24T14:30Z — initial
- agent: log/01KPZQTP9KZNRD8S554XV0A247
- refs: [[research/JDL-66/postgres-compose-multi-db-init-2026]], [[.env-example]]

Forge created `config/postgres/01-create-dbs-and-users.sh` as part of JDL-66 M1 shared-infrastructure scaffolding and committed it as `5834af3` on branch `JDL-66-m1-shared-infrastructure-online`. The file is a non-executable bash script landed in the container's `/docker-entrypoint-initdb.d/` directory via the compose config-mount, sourced by the official Postgres entrypoint only on first boot when `PG_VERSION` is absent from the data directory — every subsequent container start skips the script entirely, so the provisioning is inherently idempotent against the data volume's lifecycle rather than against its own logic. ^p001

The script provisions four per-service users — `lakekeeper`, `prefect`, `openmetadata`, `grafana` — each reading its password from an environment variable named in `.env.example` (`POSTGRES_LAKEKEEPER_PASSWORD`, `POSTGRES_PREFECT_PASSWORD`, `POSTGRES_OPENMETADATA_PASSWORD`, `POSTGRES_GRAFANA_PASSWORD`). For each user it then creates a matching database with that user as `OWNER` and grants `ALL PRIVILEGES` on the database to its owner. The four databases are consumed downstream by Lakekeeper (M2), Prefect (M10), OpenMetadata (M12), and Grafana (M3); front-loading all four at M1 avoids per-milestone init-SQL accretion and keeps the Postgres provisioning surface a single-file, single-pass concern. ^p002

The file is mode `644` and must stay that way — a prominent header comment warns against a future "helpfully chmod +x the scripts" regression. The docker-library/postgres entrypoint treats executable and non-executable `.sh` files differently: executable scripts are run as subprocesses via `exec`, which does not carry the compose environment into their env block, so the `${POSTGRES_*_PASSWORD}` interpolations would silently expand to empty strings and every downstream service's auth would fail at a later milestone with no clear root-cause trail. Non-executable `.sh` files are sourced into the entrypoint's own shell, which has the full compose env visible. The mode-644 invariant is the single operational detail that makes this script correct. ^p003
