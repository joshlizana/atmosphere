---
id: 01KPZQVDNG8K278GNENXZR88RJ
type: file
name: env-example
created_at: 2026-04-24T17:55Z
created_by: log/01KPZQVDNG8K278GNENXZR88RJ
component: repo
---

## Purpose
Tracks the lifecycle of `/home/josh/atmosphere/.env.example` — the checked-in template enumerating every environment key the atmosphere compose stack expects in a local `.env`. Carries the contributor-facing contract for Lakekeeper service passwords, Postgres credentials, Grafana admin, Prefect API key, OpenMetadata admin, SeaweedFS S3 key pair, and the Docker Compose project-name pin.

## 2026-04-24T17:55Z — initial
- agent: log/01KPZQVDNG8K278GNENXZR88RJ
- refs: [[research/JDL-66/postgres-compose-multi-db-init-2026]]

Forge modified `.env.example` at commit `37b4d2e` on branch `JDL-66-m1-shared-infrastructure-online`, inserting a new `# Compose project` section immediately before the existing `# Postgres` section. The new section carries a multi-line `#` comment describing why the pin exists — mirroring `name: atmosphere` in `compose.yml` so `atmosphere_postgres` and every other `atmosphere_*` artifact resolves predictably regardless of the operator's checkout directory name — followed by the unquoted key `COMPOSE_PROJECT_NAME=atmosphere`. No existing key, value, comment, or line ordering was touched. ^p001

The pin enables reliable `docker volume ls --filter name=atmosphere_` enumeration for the backup workflow, keeps the compose project's naming stable under `docker` CLI commands that don't themselves read `compose.yml`, and protects the Postgres named-volume path `atmosphere_postgres` declared at the compose top-level `volumes:` block (landing in `compose.yml` later this PR). Without the pin, Docker derives the project name from the working-directory basename, which would produce `<dirname>_postgres` and break both the backup enumeration and any assumption that the named volume is stable across operator checkouts. ^p002

The file was originally created in M0 under JDL-65 and was further tweaked by a linter (intentional) after Forge's commit, so the working-tree state downstream of `37b4d2e` carries formatter-applied whitespace adjustments outside the scope of this invocation. Only Forge's `37b4d2e` addition is recorded here; the subsequent linter pass is a separate modification event. ^p003
