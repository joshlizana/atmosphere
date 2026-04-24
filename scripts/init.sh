#!/usr/bin/env bash
# ==============================================================================
# Atmosphere — first-boot pre-flight + ephemeral artifact generation
# ==============================================================================
#
# Gates `scripts/up.sh`. Runs BEFORE any service is touched, in two sections:
#
#   A. Pre-flight dependency checks (idempotent, non-mutating):
#        1. `docker compose` v2 is on PATH.
#        2. cwd is the Atmosphere repo root (sentinel trio:
#           compose.yml + .env.example + Makefile).
#      Future milestones will add more checks here (NVIDIA Container
#      Toolkit for M7+, etc.).
#
#   B. Ephemeral artifact generation (mutates state; only runs if A passed):
#        1. On a fresh clone: copy .env.example to .env and fill every
#           =CHANGEME slot with an independent URL-safe 32-char random
#           string. Operator replaces GHPAGES_PAT /
#           GHPAGES_COMMIT_AUTHOR_EMAIL with real values before M11.
#        2. If .env already exists: no-op — operator customization wins.
#
# Ordering is load-bearing: a failed pre-flight exits non-zero BEFORE
# .env is generated, so a clean abort never leaves a half-initialized
# repo with a populated .env it cannot use.
#
# Idempotent. `make up` chains this script then `scripts/up.sh`; running
# this script directly against an initialized repo is a silent pass.
# ==============================================================================

set -euo pipefail

# ------------------------------------------------------------------------------
# Output helpers
# ------------------------------------------------------------------------------

log()  { printf '[init.sh] %s\n' "$*"; }
fail() { printf '[init.sh] ERROR: %s\n' "$*" >&2; }

# ------------------------------------------------------------------------------
# Section A — Pre-flight dependency checks (non-mutating)
# ------------------------------------------------------------------------------

# Verify Docker Compose v2 is available. Compose v1 (`docker-compose`) is not
# supported; the stack relies on v2-only syntax (`depends_on.condition`,
# `include:` semantics, the `docker compose` subcommand form).
check_docker_compose_v2() {
  if ! command -v docker >/dev/null 2>&1; then
    fail "\`docker\` not found on PATH. Install Docker Engine + Compose v2."
    fail "Fix: https://docs.docker.com/engine/install/"
    exit 1
  fi

  if ! docker compose version >/dev/null 2>&1; then
    fail "\`docker compose\` (v2) not available. Compose v1 (docker-compose) is not supported."
    fail "Fix: install the Docker Compose v2 plugin — https://docs.docker.com/compose/install/"
    exit 1
  fi

  # Confirm the reported version is >= 2.x. `docker compose version --short`
  # returns e.g. `2.29.7`.
  local version
  version=$(docker compose version --short 2>/dev/null || printf '')
  case "$version" in
    2.*|[3-9].*|[1-9][0-9]*.*)
      : # v2+; ok
      ;;
    *)
      fail "\`docker compose\` reports version '${version}'; need v2.x or newer."
      fail "Fix: upgrade the Docker Compose v2 plugin — https://docs.docker.com/compose/install/"
      exit 1
      ;;
  esac
}

# Verify cwd is the Atmosphere repo root. All three sentinel files must be
# present; any single miss means the operator is running from somewhere else.
check_repo_root() {
  local missing=()
  [ -f compose.yml  ] || missing+=(compose.yml)
  [ -f .env.example ] || missing+=(.env.example)
  [ -f Makefile     ] || missing+=(Makefile)

  if [ "${#missing[@]}" -gt 0 ]; then
    fail "Not running from the Atmosphere repo root. Missing: ${missing[*]}"
    fail "Fix: cd into the repo root (the directory containing compose.yml) and re-run."
    exit 1
  fi
}

# ------------------------------------------------------------------------------
# Section B — Ephemeral artifact generation (mutates state)
# ------------------------------------------------------------------------------

# Materialize .env on first boot. An existing .env is never touched — operator
# customization always wins; to regenerate, delete .env first (or `make nuke`).
#
# Every =CHANGEME slot is filled with an INDEPENDENT URL-safe 32-char random
# string: the loop regenerates `rand` on each iteration and `sed` substitutes
# only the first remaining =CHANGEME occurrence (`0,/pattern/`), so no two
# slots ever share the same value.
generate_env() {
  if [ -f .env ]; then
    log "→ .env present; skipping generation"
    return 0
  fi

  cp .env.example .env
  while grep -q '=CHANGEME$' .env; do
    local rand
    rand=$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32)
    sed -i "0,/=CHANGEME$/ s//=${rand}/" .env
  done
  log "→ Generated .env from .env.example with random secrets (replace GHPAGES_PAT / GHPAGES_COMMIT_AUTHOR_EMAIL before M11)"
}

# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------

main() {
  # Section A — pre-flight (bail before any state mutation).
  check_docker_compose_v2
  check_repo_root

  # Section B — ephemeral artifacts (only reached if all pre-flights passed).
  generate_env
}

main "$@"
