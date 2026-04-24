---
id: 01KQ0PY80XNQFMTTW9CYD455B1
type: incident
name: 20260424T2139Z-alpine-ipv6-first-localhost-breaks-busybox-wget-healthcheck
created_at: 2026-04-24T21:39Z
created_by: log/helm-m1-log-026
component: helm
---

## Purpose
Retroactively records the incident that Alpine-based containers resolve `localhost` to `::1` before `127.0.0.1`, causing BusyBox wget healthchecks against IPv4-only services to always report `unhealthy` even when the endpoint is reachable. The failure surfaced on the SeaweedFS service during the M1 smoke Probe re-run and is a class-of-bug lesson that will recur on every future Alpine-image service in the stack unless the healthcheck pattern is pinned to a literal IPv4 address or dual-probes both loopback families.

## 2026-04-24T21:39Z — initial
- agent: log/helm-m1-log-026
- refs: [[research/JDL-66/seaweedfs-single-container-compose-2026]], [[research/JDL-66/seaweedfs-healthcheck-busybox-wget-2026]], [[files/JDL-66/compose-yml]], [[.probe-logs/2026-04-24T17:22:57Z-JDL-66-rerun-m1-shared-infrastructure-smoke-test-against-fixed-init-sh]]

What happened. The initial M1 `compose.yml` (commit `bb4fc7c`) used `wget --spider -q http://localhost:9333/cluster/status` as the SeaweedFS healthcheck, per the first SeaweedFS Scout's recommendation at [[research/JDL-66/seaweedfs-single-container-compose-2026]] (commit `6d3d042`). The M1 smoke Probe's first re-run (task `a3f2804c93ee37e65`) found that the container consistently reported `Up (unhealthy)` even though the endpoint was functionally reachable — `curl http://localhost:9333/cluster/status` from the host returned the expected `{"IsLeader": true, ...}` JSON body, and `test_12_seaweedfs_master_healthy` passed against that same endpoint over the compose network. The endpoint worked; the healthcheck command was misclassifying. ^p001

Root cause. The `chrislusf/seaweedfs:4.21` image is Alpine 3.23.4-based. Alpine's `/etc/hosts` ships `::1 localhost localhost` (IPv6 first) by default. SeaweedFS binds IPv4 loopback only — `127.0.0.1:9333` and `172.17.0.2:9333`, never `::1`. BusyBox wget 1.37 follows the first resolved record, which is the IPv6 one, tries to connect to `[::1]:9333`, gets connection-refused, exits 1. The resolution path is broken at the container / Alpine libc layer, not at SeaweedFS. ^p002

Scout v3 for SeaweedFS at [[research/JDL-66/seaweedfs-healthcheck-busybox-wget-2026]] (commit `9db0e56`) diagnosed this correctly and recommended three orthogonal defenses bundled: literal `127.0.0.1` instead of `localhost` (bypasses the IPv6-first resolution), `/cluster/healthz` instead of `/cluster/status` (dedicated Kubernetes-style liveness endpoint, doesn't require the master to be mid-election), and `-O /dev/null` instead of `--spider` (avoids a separate BusyBox bug where `--spider` returns exit 0 on "can't connect"). Forge applied the triple fix at commit `d895987` (recorded in the 17:22Z addendum on [[files/JDL-66/compose-yml]]). Verified working on the current Probe run — SeaweedFS now reports healthy. ^p003

Lesson. Every Alpine-based service in the platform — present and future — will exhibit the same IPv6-first `localhost` resolution behavior on any healthcheck that uses DNS rather than a literal IP. M1 onwards, every healthcheck against a service running in an Alpine container must either use a literal IPv4 address (`127.0.0.1`), not `localhost`, or dual-probe both `[::1]` and `127.0.0.1` if the service might bind either. This is directly relevant to every future Alpine service in the stack — Loki (Alpine variant), Grafana (Alpine variant available), Prometheus (Alpine variant available), Redpanda's console sidecar (when added), any Elementary service. The same failure mode will recur on each unless the healthcheck follows one of the two patterns above. ^p004

Scope of harm. None reached `main`. Probe surfaced the issue on its first run; the platform never operated with false-positive healthy reporting for long; the `seaweedfs-init` sidecar (which gates on `depends_on.condition: service_healthy`) correctly waited for a real healthy signal, so no downstream bucket-creation happened against a half-up SeaweedFS. ^p005

Why retroactive. This incident occurred during the first Probe re-run ([[.probe-logs/2026-04-24T17:22:57Z-JDL-66-rerun-m1-shared-infrastructure-smoke-test-against-fixed-init-sh]]) alongside two other bugs (Redpanda `--admin-addr`, `.env.example` CHANGEME). At the time, Helm treated the Probe report as routine Probe→fix debugging and went straight to Scouts + Forges without filing incident Logs for any of the three. User subsequently clarified the threshold: class-of-bug lessons warrant incident Logs; routine config tweaks don't. This Alpine IPv6-first case is the clearest class-of-bug of the three (directly recurs on every future Alpine service), so it gets logged retroactively. The Redpanda `--admin-addr` case is subsumed by the newer `--set`-passthrough incident being logged in parallel (see [[incidents/JDL-66/20260424T1723Z-rpk-set-flag-not-stripped-by-redpanda-v26]]). The `.env.example` CHANGEME case was a narrow local fix with no transferable lesson — no incident filed. ^p006
