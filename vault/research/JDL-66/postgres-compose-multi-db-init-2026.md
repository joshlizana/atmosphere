---
id: postgres-compose-multi-db-init-2026
type: research
name: Single-container Postgres compose pattern for M1 — multi-db init, named volume, healthcheck (2026)
created_at: 2026-04-24
created_by: scout
component: postgres
---

## Purpose

Pin down the 2026-canonical single-container Postgres compose pattern Atmosphere needs for M1 (JDL-66): four logical databases (`lakekeeper`, `prefect`, `openmetadata`, `grafana`) with per-service users, provisioned via `/docker-entrypoint-initdb.d/` on first boot; docker-managed named volume `atmosphere_postgres` for `/var/lib/postgresql/data`; `pg_isready` healthcheck with sensible interval/timeout/retries/start_period; all credentials sourced from the compose `.env` file. Cover: which major version to pin (17 vs 18), exact tag convention, init-SQL ordering rules, `.sql` vs `.sh` env-interpolation semantics (the load-bearing footgun), the top-level `volumes:` declaration shape required to yield the literal name `atmosphere_postgres`, and the Alpine-vs-Debian choice for this deployment.

## Entry — initial — 2026-04-24 — scout

**agent:** scout
**refs:** [[.claude/context/operations.md]] (§Deployment, §Volumes and storage), [[.claude/context/roadmap.md]] (M1), [[.claude/context/components/lakekeeper.md]] (§Backing database), docker-library/postgres master `docker-entrypoint.sh`, Postgres official Docker Hub README, Compose Specification §Volumes top-level element, PostgreSQL release calendar 2026-02-26

### Major version — pin Postgres 17, not 18 ^p001

Postgres 18 was released 2025-09-25 and is on 18.3 as of 2026-02-26; 17 is on 17.9. Both are stable and community-supported (17's EOL is 2029-11-08). For Atmosphere the right pin is **17**, not 18, because 18 changed the default data directory path the entrypoint expects — under 17 and earlier, `/var/lib/postgresql/data` is the correct mount point; under 18 the default `PGDATA` moved to `/var/lib/postgresql/{VERSION}/docker` and the official image's README explicitly warns that mounting at `/var/lib/postgresql/data` on 18 "will not persist database data when the container is re-created." That is a silent-data-loss footgun on a multi-service backing DB we never want to step on, so M1 pins 17 and revisits the upgrade to 18 as its own scoped change with a planned PGDATA migration rather than as a casual version bump. The four backing services (Lakekeeper, Prefect, OpenMetadata, Grafana) are all tested against 17 in their current stable releases — none requires 18-specific features. ^p002

### Exact tag — `postgres:17-bookworm` (Debian), not Alpine ^p003

The image publishes both Alpine-libc and Debian-glibc flavors on every supported major. For M1 the recommendation is `postgres:17-bookworm` (current stable Debian base for 17) rather than `postgres:17-alpine`, on two grounds. First, Alpine builds Postgres from source against musl libc because the Postgres community build farm's coverage is glibc-first; that is workable but introduces a distinct test surface for any Postgres extension that ships only as a glibc binary. None of the four backing services need an extension today, but Lakekeeper's backing DB and Prefect's backing DB are both long-lived state — trading a one-time ~160 MB image savings against future-proof extension compatibility is a bad bet at a scale where the whole SeaweedFS volume will eclipse the image-size delta within the first day of operation. Second, Postgres 15+ on Alpine does support ICU locales (the pre-15 "Alpine Postgres can't collate" gotcha is resolved), but glibc on Debian remains the path with the fewest locale-related surprises for any future analytical query that hits this Postgres directly. The size argument that usually favors Alpine does not survive contact with the rest of the Atmosphere envelope. Tag is `postgres:17-bookworm`; optionally pinned to a specific patch (`postgres:17.9-bookworm`) in a manner that Dependabot / Renovate can bump. `postgres:17` alone (without the distro suffix) currently resolves to the Debian variant but relying on that implicit default is fragile — be explicit. ^p004

### Init script dispatch — the canonical entrypoint behavior ^p005

The entrypoint's `docker_process_init_files` function iterates `/docker-entrypoint-initdb.d/` in **sorted name order defined by the current locale (defaults to `en_US.utf8`)** and dispatches per file extension: ^p006

- `*.sh` — if executable, `exec`'d directly; if non-executable, **sourced** into the entrypoint's own shell (so env vars and helper functions from the entrypoint are available). Either way, the script sees the container's environment variables — `$POSTGRES_USER`, `$POSTGRES_DB`, plus anything the compose file injected. This is the shape that gets full shell-style env interpolation "for free."
- `*.sql` — passed to `psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --no-password --no-psqlrc -f "$f"`. Note what is **not** there: no `-v <name>=<value>` variable bindings from the environment. A raw `.sql` file mounted into init cannot reference `${LAKEKEEPER_PASSWORD}` or `:lakekeeper_password` and expect substitution. psql's own `\set` / `:var` interpolation works only against variables that either (a) psql was invoked with via `-v`, or (b) the SQL file itself declared with `\set`. Neither applies to env vars without a wrapper.
- `*.sql.gz` / `*.sql.xz` / `*.sql.zst` — decompressed into the same `psql` invocation as `.sql`. Same interpolation constraint.

Init scripts run **only when the data directory is empty** — the entrypoint checks for a `PG_VERSION` file and sets `DATABASE_ALREADY_EXISTS` if found. A second `docker compose up` on the same volume does not re-run init, which is the correct behavior for us (we want create-users-and-dbs to be a one-time-at-first-boot thing) but does mean that any change to the init script after the first boot is silently ignored until the volume is recreated. `make nuke`-style wipes or explicit `docker volume rm atmosphere_postgres` are the recovery path. ^p007

### The load-bearing env-interpolation footgun ^p008

Passwords for Lakekeeper, Prefect, OpenMetadata, and Grafana all live in `.env` (per `.claude/context/operations.md` §Secrets and configuration) and must reach `CREATE ROLE … PASSWORD '…'` at first boot. Because `.sql` files do not get env interpolation, the canonical workaround is to write the init script as a **non-executable `.sh`** in `/docker-entrypoint-initdb.d/`; the entrypoint sources it, so `$LAKEKEEPER_PASSWORD` et al. are visible, and the script emits the SQL via a heredoc piped to `psql`. The mrts/docker-postgresql-multiple-databases repo is the widely-copied prior art for this shape; we adapt it rather than copy it because their version creates users with **no password** (fine for dev; not fine for a single-trust-domain deployment where the only meaningful barrier is the bridge-network boundary and we still want per-user GRANT attribution). ^p009

Our canonical init script — commit as `config/postgres/init/01-create-dbs-and-users.sh` and bind-mount into the container at `/docker-entrypoint-initdb.d/01-create-dbs-and-users.sh`: ^p010

```bash
#!/bin/bash
set -euo pipefail

# Env vars expected from compose (.env):
#   LAKEKEEPER_DB_PASSWORD
#   PREFECT_DB_PASSWORD
#   OPENMETADATA_DB_PASSWORD
#   GRAFANA_DB_PASSWORD

create_db_and_user() {
  local db=$1
  local user=$1
  local pw=$2
  echo "Creating role ${user} and database ${db}"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
    CREATE ROLE "${user}" WITH LOGIN PASSWORD '${pw}';
    CREATE DATABASE "${db}" OWNER "${user}";
    GRANT ALL PRIVILEGES ON DATABASE "${db}" TO "${user}";
EOSQL
}

create_db_and_user lakekeeper   "${LAKEKEEPER_DB_PASSWORD}"
create_db_and_user prefect      "${PREFECT_DB_PASSWORD}"
create_db_and_user openmetadata "${OPENMETADATA_DB_PASSWORD}"
create_db_and_user grafana      "${GRAFANA_DB_PASSWORD}"
```

The `01-` prefix is required, not cosmetic: sorted-name dispatch means a future contributor dropping a `02-seed-audit-tables.sh` into the same dir will run after this one, and a `00-debug-env.sh` will run before. Document the numbering scheme in `config/postgres/init/README.md` so the ordering is explicit to readers. ^p011

The script connects explicitly to the `postgres` maintenance DB (`--dbname postgres`) rather than relying on the entrypoint's default, because the entrypoint's `docker_process_sql` helper defaults to `$POSTGRES_DB` if set — and if we ever set `POSTGRES_DB=atmosphere` in `.env` for a stray cross-check, the init would try to create roles against a DB that is itself being created in the same init phase, which is a confusing failure mode worth preempting. `postgres` is always present. ^p012

Role names and DB names are quoted (`"${user}"`) so future additions like `dbt_sandbox` don't silently break if a name ever contains a mixed-case identifier or a reserved word. Passwords are single-quoted (SQL literal). This shape is injection-safe against the env values we control but is not hardened against attacker-controlled names — that is not our threat model and should not become one at a cost we can't justify; the compose `.env` file is a single-trust-domain configuration artifact. ^p013

### Healthcheck — the canonical pg_isready stanza ^p014

Docker Compose accepts standard `interval` / `timeout` / `retries` / `start_period` fields; the recommended Postgres stanza is `pg_isready` with an interval shorter than the downstream `depends_on: condition: service_healthy` wait expectations. For M1: ^p015

```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d postgres"]
  interval: 10s
  timeout: 5s
  retries: 10
  start_period: 30s
```

Notes on the field choices. `CMD-SHELL` (not `CMD`) is required to get env-var interpolation — we parameterize `$POSTGRES_USER` so that renaming the superuser via `.env` does not silently break the healthcheck. `-d postgres` explicitly probes the maintenance DB rather than letting `pg_isready` default to the invoking user's DB name, which is just defensive about any future `POSTGRES_DB` env change. `interval: 10s` balances responsiveness against noise in the Prometheus scrape. `start_period: 30s` is generous — on a cold volume the entrypoint has to run initdb plus our four-user/four-DB init script, which is seconds-not-minutes even on a slow disk; 30 s gives the init script's failures a full window to become visible before they flip the container to unhealthy. `retries: 10` at a 10 s interval allows for a ~100 s soft-fail window, which matches `docker compose up -d` expectations for operator visibility. ^p016

### Named volume — how to land on the literal name `atmosphere_postgres` ^p017

Compose v2 prefixes top-level volumes with the project name by default, so a naive `volumes: { postgres: }` block in a project whose directory is `atmosphere` produces a docker volume named `atmosphere_postgres` **automatically** — no `external:` declaration needed. This matches our desired name exactly, so the canonical pattern is: ^p018

```yaml
services:
  postgres:
    image: postgres:17-bookworm
    environment:
      POSTGRES_USER: ${POSTGRES_SUPERUSER_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_SUPERUSER_PASSWORD}
      LAKEKEEPER_DB_PASSWORD: ${LAKEKEEPER_DB_PASSWORD}
      PREFECT_DB_PASSWORD: ${PREFECT_DB_PASSWORD}
      OPENMETADATA_DB_PASSWORD: ${OPENMETADATA_DB_PASSWORD}
      GRAFANA_DB_PASSWORD: ${GRAFANA_DB_PASSWORD}
    volumes:
      - postgres:/var/lib/postgresql/data
      - ./config/postgres/init:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_SUPERUSER_USER:-postgres} -d postgres"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 30s
    deploy:
      resources:
        reservations:
          memory: 768M
    restart: unless-stopped

volumes:
  postgres:
```

The auto-prefixing behavior is project-name-driven: `docker compose -p atmosphere up` (or running from an `atmosphere/` directory with the default `COMPOSE_PROJECT_NAME` inference) yields `atmosphere_postgres`. If the project name ever diverges from `atmosphere` — e.g., a contributor clones into `bluesky-platform/` — the volume name silently changes too. Two defensive options: (a) commit `COMPOSE_PROJECT_NAME=atmosphere` into `.env` (cleanest — pins project name for every `docker compose` invocation in the repo); (b) use the `name:` property on the top-level volume to force the literal name regardless of project: ^p019

```yaml
volumes:
  postgres:
    name: atmosphere_postgres
```

Option (a) is preferred because it pins **every** project-prefixed artifact — volumes, networks, default container names — to `atmosphere_*` in one place, and `.claude/context/operations.md` §Volumes already names `docker volume ls --filter name=atmosphere_` as the backup-enumeration command, implying the project name is the stable prefix. Add `COMPOSE_PROJECT_NAME=atmosphere` to `.env.example` as an explicit declaration. Then the compose file stays on the short `volumes: { postgres: }` form and relies on the guaranteed project prefix. ^p020

Do **not** set `external: true` on this volume. External volumes have a lifecycle "managed outside the application" — `docker compose down -v` will not remove them, which defeats the `make nuke` workflow described in `.claude/context/operations.md` (`docker compose down -v && rm -rf ./data/*`). We want `-v` to wipe Postgres along with the bind-mount paths in a single gesture. ^p021

### `.env` keys to add ^p022

Atmosphere's `.env.example` currently documents "Postgres user passwords" (per `.claude/context/roadmap.md` M0 acceptance list) without nailing the key names. The set this note commits to: ^p023

```
# Postgres — superuser (created by the image's initdb)
POSTGRES_SUPERUSER_USER=postgres
POSTGRES_SUPERUSER_PASSWORD=changeme

# Postgres — per-service logical DB passwords (created by init script)
LAKEKEEPER_DB_PASSWORD=changeme
PREFECT_DB_PASSWORD=changeme
OPENMETADATA_DB_PASSWORD=changeme
GRAFANA_DB_PASSWORD=changeme

# Compose project name — pins the atmosphere_ prefix on every Compose artifact
COMPOSE_PROJECT_NAME=atmosphere
```

The superuser username defaults to `postgres` (matches the image's own default), so it is effectively a no-op override for most deployments; exposing it as a variable still makes the healthcheck stanza correct without a hardcoded "postgres" literal. Passwords for the four logical DBs are individually named (not folded into a `POSTGRES_PASSWORDS=…` structured variable) so that rotation can touch one line at a time and so each downstream service's compose entry can reference its own variable explicitly. ^p024

### What this note deliberately does not adopt ^p025

- **`POSTGRES_MULTIPLE_DATABASES`** — the env variable that the mrts/docker-postgresql-multiple-databases repo and the dev.to-ecosystem copies popularized. It is **not part of the official Postgres image**; it only exists in third-party forks and in community init scripts that parse it. Using it adds a magic-variable illusion (readers expect it to be supported by the base image, and it isn't) without giving us anything the direct bash loop in §Init script doesn't already give us more legibly. The four DBs are a fixed list that only changes when a new backing service appears — comma-splitting a variable is solving a problem we don't have. ^p026
- **`POSTGRES_HOST_AUTH_METHOD=trust`** — a common shortcut for eliminating passwords inside a trusted compose network. Atmosphere's single-trust-domain posture (per `.claude/context/components/lakekeeper.md` §Auth) is already "the bridge network is the perimeter," so the auth-method setting is not load-bearing for security. Keep the default (`scram-sha-256` on 17), set real per-user passwords via the init script, and preserve user-level attribution in Postgres audit logs. The attribution is the payoff for the tiny cost of managing passwords. ^p027
- **`POSTGRES_INITDB_ARGS`** — used by some deployments to force an ICU locale / specific collation at cluster-init time. Default libc `en_US.utf8` collation is fine for the four backing services (none does mixed-locale sorting). Revisit only if a future feature exercises collations. ^p028
- **Docker secrets / `_FILE` variants** — `POSTGRES_PASSWORD_FILE` and friends support Swarm-style secret mounts. Atmosphere uses plain `.env` at M1 per `.claude/context/operations.md` §Secrets. Upgrading to docker secrets is a separate, later change that can mechanically translate this shape without touching the init-script logic. Flagged, not adopted. ^p029

### Gotchas ^p030

- **Init scripts are ignored if `/var/lib/postgresql/data` is non-empty on first start.** The entrypoint checks for `PG_VERSION` and short-circuits. Anyone bringing up Atmosphere against a previously-used `atmosphere_postgres` volume will see Postgres start without running the init script — the four backing DBs and their users won't exist, and Lakekeeper (M2) will fail to authenticate. Recovery is `docker volume rm atmosphere_postgres` then `docker compose up -d postgres`. Document this in `docs/runbooks/postgres.md` as the first troubleshooting step. ^p031
- **`.sql` files get no env interpolation.** A contributor who reads the Docker docs' "drop `.sql` files in" line and follows it literally will find that `CREATE ROLE foo PASSWORD '${FOO_PW}'` becomes a literal `${FOO_PW}` string in Postgres. The error is silent at SQL level (the string is a valid password literal) and surfaces only when the downstream service tries to auth. Fix is to convert to the `.sh` shape. Our script already does this; the gotcha is for future authors who add a `.sql` file without thinking. ^p032
- **`CMD` vs `CMD-SHELL` in the healthcheck.** `test: ["CMD", "pg_isready", "-U", "$POSTGRES_USER"]` does not interpolate `$POSTGRES_USER` — Docker exec's argv form takes the literal string. Only `CMD-SHELL` (or the bare-string form) routes through `/bin/sh -c` and gets env interpolation. Our stanza uses `CMD-SHELL`. ^p033
- **`pg_isready` exit code 2 means "rejected" not "no connection."** The healthcheck test considers any non-zero exit unhealthy, which is correct for our use — we want rejected connections (e.g., still initializing) to count as not-yet-ready. No adjustment needed. ^p034
- **Sourced `.sh` scripts run with `set -e` inherited from the entrypoint.** A subshell exit in the init script aborts init. Our script uses `set -euo pipefail` explicitly so behavior is the same regardless of whether the entrypoint sources or execs it. ^p035
- **`postgres:17-bookworm` is ~438 MB compressed; `postgres:17-alpine` is ~278 MB.** If disk pressure on the host ever becomes a constraint, the tradeoff is reversible as a per-image swap — the init script, healthcheck, and env variables are identical across flavors. Revisit at that point rather than pre-emptively. ^p036

### Summary of choices ^p037

- **Image tag:** `postgres:17-bookworm` (Debian-glibc, stable 17.9 line).
- **Data mount path:** `/var/lib/postgresql/data` (17-canonical; do not reuse this path on 18).
- **Named volume:** `postgres` at the top level, relying on `COMPOSE_PROJECT_NAME=atmosphere` in `.env` to prefix into `atmosphere_postgres`. Not `external`.
- **Init script shape:** non-executable `.sh` in `/docker-entrypoint-initdb.d/01-create-dbs-and-users.sh`, sourced by the entrypoint, loops over a hardcoded list of four `{db, user, password}` tuples, emits SQL via heredoc to `psql --dbname postgres`.
- **Healthcheck:** `CMD-SHELL pg_isready -U ${POSTGRES_SUPERUSER_USER} -d postgres`, 10 s interval, 5 s timeout, 10 retries, 30 s start_period.
- **Soft memory reservation:** 768 MB per `.claude/context/operations.md`, no hard cap.
- **Env keys:** `POSTGRES_SUPERUSER_USER`, `POSTGRES_SUPERUSER_PASSWORD`, `LAKEKEEPER_DB_PASSWORD`, `PREFECT_DB_PASSWORD`, `OPENMETADATA_DB_PASSWORD`, `GRAFANA_DB_PASSWORD`, `COMPOSE_PROJECT_NAME`.

^p038

### Sources ^p039

- Postgres Docker Hub README (canonical image doc): https://hub.docker.com/_/postgres
- docker-library/docs postgres README (markdown source): https://github.com/docker-library/docs/blob/master/postgres/README.md
- docker-library/postgres entrypoint source: https://github.com/docker-library/postgres/blob/master/docker-entrypoint.sh
- docker-library/postgres issue #151 (multi-db canonical thread): https://github.com/docker-library/postgres/issues/151
- mrts/docker-postgresql-multiple-databases (prior-art init script): https://github.com/mrts/docker-postgresql-multiple-databases
- Compose Specification — Volumes top-level element: https://compose-spec.github.io/compose-spec/07-volumes.html
- Docker Compose — Define and manage volumes: https://docs.docker.com/reference/compose-file/volumes/
- Docker Compose — Control startup order (healthchecks): https://docs.docker.com/compose/how-tos/startup-order/
- PostgreSQL release calendar (17 EOL 2029-11-08): https://www.postgresql.org/support/versioning/
- docker-library/postgres issue #1004 (ICU on Alpine): https://github.com/docker-library/postgres/issues/1004
