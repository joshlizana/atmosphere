#!/usr/bin/env bash
# ==============================================================================
# Atmosphere — tiered, health-gated bring-up script
# ==============================================================================
#
# One-command operator bring-up for the Atmosphere platform. Starts each tier
# of services, waits for every service in that tier to report `healthy` via its
# docker healthcheck, then moves on to the next tier. Re-running the script on
# an already-up platform is a no-op (docker compose up -d is idempotent; the
# health wait short-circuits when everything is already healthy).
#
# Tiers (populated as milestones land):
#   Tier 1 — M1 infrastructure: postgres, seaweedfs, redpanda
#   Tier 1 follow-up           : seaweedfs-init (one-shot; runs to completion)
#   Tier 2 — M2 catalog        : lakekeeper                          (future)
#   Tier 3 — M3 observability  : prometheus, loki, alloy, grafana    (future)
#   Tier 4 — M4+ data plane    : spout, flink, sleuth, oracle, ...   (future)
#
# Extending this script for a new milestone: add a new "Tier N: <milestone>"
# block at the bottom of the script. Each block is two lines of real work:
#   docker compose up -d <services...>
#   wait_for_healthy 120 <services...>
# Plus any one-shot sidecars run via `docker compose up <svc>` (no -d) so they
# stream logs and block until exit.
#
# On first boot, if `.env` is absent the script materializes one from
# `.env.example` and fills every `CHANGEME` slot with an independent URL-safe
# 32-char random string. An existing `.env` is never touched — operator
# customization always wins. To regenerate, delete `.env` first.
#
# Assumptions:
#   - Docker Compose v2 is on PATH (the `docker compose` subcommand form).
#     Compose v1 (`docker-compose`) is not supported.
#   - The operator runs this script from the repository root.
#   - COMPOSE_PROJECT_NAME defaults to `atmosphere` (pinned in .env); the script
#     honors an override if one is set in the environment.
#
# Exit codes:
#   0  — every tier came up healthy
#   1  — pre-flight failed (missing docker compose v2, or .env generation error)
#   2  — a tier failed to become healthy within its timeout (logs dumped)
#   other — propagated from `docker compose` itself
# ==============================================================================

set -euo pipefail

# ------------------------------------------------------------------------------
# Env preflight: materialize .env on first boot if absent.
# - If .env exists, do nothing (operator customization wins).
# - If .env is absent, copy .env.example and replace every CHANGEME
#   with an independent URL-safe 32-char random string. Note that
#   GHPAGES_PAT and GHPAGES_COMMIT_AUTHOR_EMAIL also get random values;
#   operator replaces those with real values before M11 when GitHub
#   Pages publishing goes live.
# - Never overwrite an existing .env. To regenerate, delete .env first.
# ------------------------------------------------------------------------------
if [ ! -f .env ]; then
  cp .env.example .env
  while grep -q '=CHANGEME$' .env; do
    rand=$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32)
    sed -i "0,/=CHANGEME$/ s//=${rand}/" .env
  done
  printf '[up.sh] Generated .env from .env.example with random secrets. Edit .env to customize (e.g., GHPAGES_PAT for M11).\n'
fi

# ------------------------------------------------------------------------------
# Config
# ------------------------------------------------------------------------------

# Project name used to compute container names (`<project>-<service>-1`).
# Pinned to `atmosphere` in .env; respect any explicit override in the env.
PROJECT="${COMPOSE_PROJECT_NAME:-atmosphere}"

# Default per-tier health wait. Tiers can override by passing a different
# timeout to wait_for_healthy.
DEFAULT_TIMEOUT=120

# ------------------------------------------------------------------------------
# Output helpers
# ------------------------------------------------------------------------------

log()  { printf '[up.sh] %s\n' "$*"; }
warn() { printf '[up.sh] WARN: %s\n' "$*" >&2; }
fail() { printf '[up.sh] ERROR: %s\n' "$*" >&2; }

# ------------------------------------------------------------------------------
# wait_for_healthy <timeout-seconds> <svc>...
#
# Polls `docker inspect --format='{{.State.Health.Status}}' <container>` for
# every listed service until all report `healthy`, or until the timeout fires.
# Container names are computed as `${PROJECT}-<svc>-1` per Compose v2 defaults.
#
# On timeout, dumps the last 50 log lines of each unhealthy service via
# `docker compose logs` and exits 2 so the operator sees what broke.
# ------------------------------------------------------------------------------
wait_for_healthy() {
  local timeout="$1"
  shift
  local services=("$@")

  log "Waiting up to ${timeout}s for healthy: ${services[*]}"

  local deadline=$(( $(date +%s) + timeout ))
  local pending=("${services[@]}")

  while (( ${#pending[@]} > 0 )); do
    local still_pending=()
    local svc
    for svc in "${pending[@]}"; do
      local container="${PROJECT}-${svc}-1"
      # `docker inspect` returns "healthy" | "unhealthy" | "starting" | "" (no
      # healthcheck defined) | errors out (container doesn't exist yet). An
      # empty status means the service has no healthcheck — treat that as a
      # config bug and fail loudly rather than silently passing.
      local status
      status=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}NO_HEALTHCHECK{{end}}' \
               "$container" 2>/dev/null || echo "NOT_FOUND")
      case "$status" in
        healthy)
          log "  ${svc}: healthy"
          ;;
        NO_HEALTHCHECK)
          fail "Service '${svc}' (container '${container}') has no healthcheck defined."
          fail "Every service in a tier must define a healthcheck so up.sh can gate on it."
          return 2
          ;;
        NOT_FOUND)
          # Container may not have been created yet — keep polling briefly.
          still_pending+=("$svc")
          ;;
        *)
          still_pending+=("$svc")
          ;;
      esac
    done

    pending=("${still_pending[@]}")

    if (( ${#pending[@]} == 0 )); then
      break
    fi

    if (( $(date +%s) >= deadline )); then
      fail "Timed out after ${timeout}s waiting for: ${pending[*]}"
      for svc in "${pending[@]}"; do
        fail "--- last 50 log lines from ${svc} ---"
        docker compose logs --tail=50 --no-color "$svc" >&2 || true
      done
      return 2
    fi

    sleep 2
  done

  log "All healthy: ${services[*]}"
}

# ------------------------------------------------------------------------------
# Pre-flight
# ------------------------------------------------------------------------------

preflight() {
  log "Pre-flight: checking docker compose availability"
  if ! docker compose version >/dev/null 2>&1; then
    fail "\`docker compose\` (v2) not available. Install Docker Compose v2."
    exit 1
  fi

  log "Pre-flight: complete (project=${PROJECT})"
}

# ------------------------------------------------------------------------------
# Tier 1 — M1 infrastructure
# ------------------------------------------------------------------------------

tier1_m1_infra() {
  log "Tier 1 (M1 infrastructure): starting postgres, seaweedfs, redpanda"
  docker compose up -d postgres seaweedfs redpanda
  wait_for_healthy "$DEFAULT_TIMEOUT" postgres seaweedfs redpanda

  # seaweedfs-init is a one-shot sidecar: it creates the Iceberg/Flink/Loki
  # buckets via `weed shell` and exits 0. Run it in the foreground (no -d) so
  # its exit status propagates and its output is visible to the operator.
  # Re-running on an already-initialized SeaweedFS is a no-op because
  # `s3.bucket.create` is idempotent by design.
  log "Tier 1 follow-up: running seaweedfs-init (one-shot bucket creator)"
  docker compose up --exit-code-from seaweedfs-init seaweedfs-init
}

# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------

main() {
  preflight
  tier1_m1_infra
  # Tier 2 (M2 — Lakekeeper) lands here.
  # Tier 3 (M3 — observability: prometheus, loki, alloy, grafana) lands here.
  # Tier 4+ (M4+ — data plane: spout, flink, sleuth, oracle, ...) lands here.

  log "All services up"
}

main "$@"
