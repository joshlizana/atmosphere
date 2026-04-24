---
id: 01KQ04HZ3X3J5KZH07X2S3858D
type: file
name: test_m1_infrastructure_smoke.py
created_at: 2026-04-24T16:18Z
created_by: log/01KQ04HZ3X3J5KZH07X2S3858D
component: repo
---

## Purpose
Tracks the lifecycle of `/home/josh/atmosphere/app/tests/test_m1_infrastructure_smoke.py` — the M1 shared-infrastructure smoke-test suite. The file is a pytest harness that asserts the full M1 platform lifecycle end-to-end: clean-state baselines, `make up` bring-up, Postgres / SeaweedFS / Redpanda behavior, restart persistence, and a full `make nuke` → `make up` reset cycle. It is the ongoing regression harness Probe re-invokes whenever `compose.yml`, `scripts/init.sh`, `scripts/up.sh`, `Makefile`, or the M1 config files change.

## 2026-04-24T16:18Z — initial
- agent: log/01KQ04HZ3X3J5KZH07X2S3858D
- refs: [[.probe-logs/2026-04-24T15:58:57Z-JDL-66-outer-loop-smoke-probe-validating-the-m1-shared-infrastructure-tier]], [[files/JDL-66/scripts/init-sh]], [[files/JDL-66/compose-yml]], [[.claude/context/operations]]

Probe created `app/tests/test_m1_infrastructure_smoke.py` at commit `6fbad22` on branch `JDL-66-m1-shared-infrastructure-online` as part of its outer-loop smoke-run validation of the M1 shared-infrastructure tier (Probe task id `a468e17a6a5359be5`). The file is a pytest test suite with 25 test functions organized into seven phases that together exercise the full M1 platform lifecycle from baseline clean state through bring-up, per-service behavior, restart persistence, and a full-reset cycle. ^p001

Phase 1 (`test_01`..`test_03`) establishes baseline clean-state assertions after `make nuke`: no `.env` present, no `atmosphere_*` docker-managed volumes present, and no M1 services running. These three tests define the known-empty starting point every subsequent phase builds on, so any leakage across test runs surfaces immediately rather than masking a real defect under stale state. ^p002

Phase 2 (`test_04`..`test_08`) covers first `make up` bring-up: `.env` is generated with independent random secrets (one distinct random per `=CHANGEME` slot, per the generation contract recorded in [[files/JDL-66/scripts/init-sh]] ^p003), all four M1 services report healthy, the `seaweedfs-init` bucket-provisioning one-shot exits 0, and the three `atmosphere_postgres` / `atmosphere_seaweedfs` / `atmosphere_redpanda` docker-managed volumes are present on disk with the literal names pinned by the `name:` overrides documented in [[files/JDL-66/compose-yml]] ^p006 ^p010. ^p003

Phase 3 (`test_09`..`test_11`) exercises Postgres behavior: the four logical databases (`lakekeeper`, `prefect`, `openmetadata`, `grafana`) exist, each per-service user connects successfully with its `.env`-sourced password, and each user is the `OWNER` of its own database — confirming the init-SQL ownership invariant established in the Postgres init script rather than merely accepting GRANT-based access. ^p004

Phase 4 (`test_12`..`test_14`) covers SeaweedFS: the master `/cluster/status` endpoint returns healthy, the three platform buckets `atmosphere` / `flink` / `loki` are all present via the S3 API, and the admin identity is synthesized from the `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` env vars per the decision recorded in [[files/JDL-66/compose-yml]] ^p003 (no `-s3.config` flag; env-var synthesis only). ^p005

Phase 5 (`test_15`..`test_18`) covers Redpanda: the admin API at `:9644/v1/status/ready` returns ready, the cluster property `storage_min_free_bytes` is `2147483648` (the 2 GB backstop from [[files/JDL-66/config/redpanda/bootstrap-yaml]]), a topic create-and-delete cycle round-trips cleanly through the Kafka admin API, and the default schema-registry (8081) and pandaproxy (8082) ports are unbound on the host — confirming the deliberate omission of those flags per [[files/JDL-66/compose-yml]] ^p005. ^p006

Phase 6 (`test_19`..`test_22`) covers state durability across `docker compose restart`: a marker row is seeded into each stateful service (Postgres row, SeaweedFS S3 object, Redpanda topic + record), every service survives a restart cycle, and every marker is still retrievable afterward. This phase is the direct acceptance-criterion proof for the M1 statement "each container survives a `docker compose restart`" from [[.claude/context/operations]] and the roadmap's M1 acceptance language. ^p007

Phase 7 (`test_23`..`test_25`) exercises the full-reset cycle: `make nuke` leaves the platform in the empty state Phase 1 asserts, the following `make up` brings the platform back up green, and the regenerated `.env` carries fresh random secrets that are distinct from the prior cycle's (per-slot independence is preserved across reset boundaries, not just within a single generation pass). ^p008

Probe's first run against the initial M1 implementation landed 6 of 25 tests passing and 19 failing; the six that passed were all Phase-1 clean-state assertions or cases passing for the wrong reason, and all 19 failures traced back to a single SIGPIPE-under-`pipefail` defect in `scripts/init.sh` — recorded separately in the sibling incident log `20260424T160XZ-init-sh-sigpipe-under-pipefail`. The suite itself is correct as written — it caught a real defect on its very first run against real M1 infrastructure — and the retention intent is for it to become the ongoing regression harness for M1, re-invoked by Probe whenever `compose.yml`, `scripts/init.sh`, `scripts/up.sh`, `Makefile`, or the M1 config files under `config/postgres/` and `config/redpanda/` change. ^p009

## 2026-04-24T22:30Z — addendum
- agent: log/helm-m1-log-030
- refs: [[incidents/JDL-66/20260424T2139Z-alpine-ipv6-first-localhost-breaks-busybox-wget-healthcheck]]

Forge modified `app/tests/test_m1_infrastructure_smoke.py` at commit `c9abe00` on branch `JDL-66-m1-shared-infrastructure-online`. The change extends `test_20_restart_all_three_and_rewait_healthy` with a second readiness gate that closes a post-restart window between SeaweedFS's docker healthcheck and the master's gRPC-dial readiness — fixing a CI-only flake on `test_21_markers_survive_restart` that did not surface during local Probe runs because Probe reruns failing tests up to 3 times and absorbed the transient window. ^p010

Root cause. The SeaweedFS docker healthcheck probes the master's HTTP `/cluster/healthz` endpoint on port 9333, which begins responding 200 shortly after container restart. The master's gRPC server — the surface `weed shell` actually dials when its commands need to talk to the master — comes up later in the same boot, so there is a window where `wait_for_healthy(EXPECTED_HEALTHY, timeout=240)` returns green while a subsequent `weed shell s3.bucket.list` still fails with `failed to dial : failed to exit idle mode: failed to start resolver: passthrough: received empty target in Build()`. GitHub Actions runs the suite once, so the first restart of CI hit the window and `test_21_markers_survive_restart` failed; local Probe runs passed 25/25 three times because the harness retries failed tests. The window is a structural property of the restart boundary — every downstream test that uses `weed shell` after `test_20` would be exposed to it — so the fix is centralized in `test_20` rather than localized per dependent test. ^p011

The new gate is additive — the existing `wait_for_healthy(EXPECTED_HEALTHY, timeout=240)` call is unchanged. Immediately after that call returns green, the test enters a retry loop bounded by a 30-second outer deadline, calling `docker compose exec -T seaweedfs weed shell -master=localhost:9333` with stdin `s3.bucket.list\n` on each attempt. The retry loop inlines `subprocess.run` with a 15-second per-invocation timeout (matching the inline-`subprocess.run` convention already used at lines 231-238 of the same file) rather than reusing the existing `weed_shell()` helper, because that helper hardcodes a 30-second timeout equal to the outer deadline — a single attempt would consume the entire budget. Failed attempts back off 2 seconds before retrying. On outer-deadline expiry the gate raises `AssertionError` carrying the last `stderr` verbatim so the dial-error signature surfaces cleanly during diagnosis. ^p012

Scope of change. Only `test_20_restart_all_three_and_rewait_healthy` was modified. `test_21_markers_survive_restart`, `test_22`, and every other test function in the file are preserved verbatim. `import time` was already present at line 34, so no new imports were added. Once `test_20` returns, every downstream test in the suite can rely on `weed shell` being dial-able against the restarted master. ^p013

Validation. The fix targets the deterministic CI-only failure recorded in `[[incidents/JDL-66/20260424T2139Z-alpine-ipv6-first-localhost-breaks-busybox-wget-healthcheck]]`; expected outcome on the next GitHub Actions run is 25/25 with no spurious `test_21` failure. ^p014
