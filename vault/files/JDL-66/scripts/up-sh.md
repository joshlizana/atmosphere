---
id: 01KPZQXVTDEAYXC7X4R6ERZVDJ
type: file
name: up.sh
created_at: 2026-04-24T12:37Z
created_by: log/01KPZQXVTDEAYXC7X4R6ERZVDJ
component: repo
---

## Purpose
Tracks the lifecycle of `/home/josh/atmosphere/scripts/up.sh` — the tiered, health-gated operator bring-up script for the Atmosphere platform. Brings the stack up from a clean state in dependency order, polling each tier's docker healthchecks to gate progression before the next tier is started. Designed as the canonical one-command entry point that future milestones extend by appending tier blocks rather than by restructuring.

## 2026-04-24T12:37Z — initial
- agent: log/01KPZQXVTDEAYXC7X4R6ERZVDJ
- refs: [[research/JDL-66/seaweedfs-single-container-compose-2026]], [[research/JDL-66/redpanda-compose-single-broker-2026]], [[research/JDL-66/postgres-compose-multi-db-init-2026]], [[.claude/context/operations]]

Forge created `scripts/up.sh` at commit `ab40f56` on branch `JDL-66-m1-shared-infrastructure-online` with message `feat(JDL-66): add tiered health-gated bring-up script`. The file is committed executable (mode `100755`) and tracked in git so `git clone && ./scripts/up.sh` works on a fresh checkout without a separate `chmod +x` step. ^p001

The preflight block verifies Docker Compose v2 is available on PATH, creates `./data/seaweedfs` and `./data/redpanda` if absent, and `chown`s them to their container UIDs (`1000:1000` for SeaweedFS and `101:101` for Redpanda) via `sudo`. The chown is load-bearing because a fresh bind-mount directory is owned by root on creation and the SeaweedFS (UID 1000) and Redpanda (UID 101) processes fail to write to their data dirs without it — the failure mode is a confusing permission-denied at container start rather than an obvious missing-directory error. Postgres is explicitly excluded from the chown step because it uses a docker-managed named volume (`atmosphere_postgres`) whose permissions are handled by docker itself, keeping Postgres's strict `0700`/`0750` data-dir check cleanly satisfied without operator intervention. ^p002

A `wait_for_healthy <timeout-seconds> <svc>...` shell helper polls `docker inspect --format='{{.State.Health.Status}}' ${PROJECT}-<svc>-1` on a 2-second cadence until every named service reports `healthy` or the timeout fires. On timeout it dumps `docker compose logs --tail=50` for each still-pending service before exiting non-zero, so the operator gets actionable diagnostic output instead of a bare timeout message. Services without a healthcheck are treated as a config bug and fail loudly rather than being silently allowed to pass — this keeps healthcheck coverage a tier-gating invariant rather than a best-effort signal. ^p003

Tier 1 (M1) runs `docker compose up -d postgres seaweedfs redpanda`, waits for all three to report `healthy`, then runs `docker compose up --exit-code-from seaweedfs-init seaweedfs-init` in the foreground as a one-shot so the bucket-creator's exit status surfaces to the script and any bucket-provisioning failure aborts the bring-up rather than being silently swallowed in a `-d` background run. The main function contains explicit comments marking where future tiers land — M2 Lakekeeper, M3 observability fabric, M4+ data-plane services — so each milestone extends the script by appending to a reserved slot rather than by restructuring the control flow. ^p004

The `COMPOSE_PROJECT_NAME` prefix is honored via env with a default of `atmosphere`, so the script works under custom project names without code changes; this matches the `COMPOSE_PROJECT_NAME=atmosphere` pin documented in `.env.example` (see `[[env-example]]`) and keeps the container-name construction (`${PROJECT}-<svc>-1`) stable across operator checkout-directory variations. ^p005
