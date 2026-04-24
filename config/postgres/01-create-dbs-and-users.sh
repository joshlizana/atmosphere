#!/usr/bin/env bash
# Atmosphere Postgres first-boot init — provisions the four logical databases
# (`lakekeeper`, `prefect`, `openmetadata`, `grafana`) and their per-service
# owners on an empty `/var/lib/postgresql/data` cluster.
#
# Why this is `.sh` and not `.sql`:
#   The official `postgres` image's entrypoint iterates
#   `/docker-entrypoint-initdb.d/` on first boot and dispatches per file
#   extension. `.sql` files are fed to `psql` WITHOUT `-v name=value`
#   bindings — so `${POSTGRES_LAKEKEEPER_PASSWORD}` in a bare `.sql` file
#   lands in Postgres as the literal 7-char string "${POSTG...}", not the
#   interpolated password. Auth then fails silently at the downstream
#   service (Lakekeeper, Prefect, ...) rather than at init time.
#   `.sh` files, by contrast, are SOURCED (when non-executable) by the
#   entrypoint, so every environment variable injected by compose is in
#   scope and heredoc-interpolates into the SQL we pipe to `psql`.
#
# Do NOT `chmod +x` this file — the entrypoint `exec`'s executable `.sh`
# scripts in a subprocess that does not inherit the entrypoint's shell
# helpers, and the expected "sourced" semantics go away. Non-executable
# is the correct mode.
#
# This script is only invoked when the data directory is empty (the
# entrypoint checks for `PG_VERSION`). To re-run on an existing cluster,
# wipe the `atmosphere_postgres` named volume and bring the container
# back up.

set -euo pipefail
IFS=$'\n\t'

create_db_and_user() {
  local db="$1"
  local user="$2"
  local password="$3"

  echo "postgres-init: creating role '${user}' and database '${db}'"

  psql -v ON_ERROR_STOP=1 \
    --username "${POSTGRES_USER}" \
    --dbname postgres <<-EOSQL
		CREATE USER "${user}" WITH PASSWORD '${password}';
		CREATE DATABASE "${db}" OWNER "${user}";
		GRANT ALL PRIVILEGES ON DATABASE "${db}" TO "${user}";
	EOSQL
}

create_db_and_user "lakekeeper"   "${POSTGRES_LAKEKEEPER_USER}"   "${POSTGRES_LAKEKEEPER_PASSWORD}"
create_db_and_user "prefect"      "${POSTGRES_PREFECT_USER}"      "${POSTGRES_PREFECT_PASSWORD}"
create_db_and_user "openmetadata" "${POSTGRES_OPENMETADATA_USER}" "${POSTGRES_OPENMETADATA_PASSWORD}"
create_db_and_user "grafana"      "${POSTGRES_GRAFANA_USER}"      "${POSTGRES_GRAFANA_PASSWORD}"

echo "postgres-init: provisioning complete; current database list:"
psql -v ON_ERROR_STOP=1 \
  --username "${POSTGRES_USER}" \
  --dbname postgres \
  --command '\l' \
  && echo "postgres-init: all four atmosphere logical databases and owners created successfully."
