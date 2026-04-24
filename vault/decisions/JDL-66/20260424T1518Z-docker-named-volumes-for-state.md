---
id: 01KQ0151EZHT7C2TF8TBB4XAY2
type: decision
name: 20260424T1518Z-docker-named-volumes-for-state
created_at: 2026-04-24T15:18Z
created_by: log/01KQ0151EZHT7C2TF8TBB4XAY2
component: compose
---

## Purpose
Records the architectural decision to persist all Atmosphere stateful services to docker-managed named volumes rather than host bind mounts, replacing the original M1 mixed-mode plan (bind mounts for "bind-tolerant" services, named volume for Postgres only).

## 2026-04-24T15:18Z — initial
- agent: log/01KQ0151EZHT7C2TF8TBB4XAY2
- refs: [[.claude/context/architecture]], [[.claude/context/operations]], [[.claude/context/components/iceberg]]

Outcome. Every stateful Atmosphere service — present and future — persists to a docker-managed named volume declared at the compose top-level `volumes:` block. At M1 this means three volumes: `atmosphere_postgres`, `atmosphere_seaweedfs`, `atmosphere_redpanda`. Future stateful services (Prometheus TSDB, Loki index, ClickHouse filesystem cache) adopt the same pattern as they land in their respective milestones. Configuration files (read-only, immutable inputs from `config/**`) continue to use bind mounts; that's a distinct sub-pattern from state persistence and does not change. ^p001

Alternatives considered. (1) Mixed mode (the initial M1 plan) — bind mounts for "bind-tolerant" services (SeaweedFS at `./data/seaweedfs`, Redpanda at `./data/redpanda`, future Loki at `./data/loki`, Prometheus at `./data/prometheus`, ClickHouse cache at `./data/clickhouse/cache`) with Postgres as the lone exception using a named volume for its strict 0700 data-dir mode check. Rejected: two operational modes is one too many to reason about at solo-operator scale. The asymmetry requires every bring-up to know which services need host-side UID chowns (SeaweedFS UID 1000, Redpanda UID 101, others TBD) and which don't. External-storage offload via host symlinks adds a third sub-mode. The asymmetry had no upside — bind-mount paths were never directly manipulated by the operator in normal operation. (2) All bind mounts, including Postgres — rejected: Postgres's strict 0700 data-dir mode check fails on many host filesystems when Docker attempts to set the mode, forcing operator workarounds that vary by filesystem. (3) All docker-managed named volumes — the selected path. One operational mode across every stateful service. No host-side UID chowns (docker handles them). No symlink escape hatch needed — docker volume drivers cover external-storage offload per-volume when operationally necessary. `docker volume ls --filter name=atmosphere_` enumerates everything in one command. ^p002

Reasoning. Uniformity wins over per-service tuning at this scale. The `atmosphere_*` name prefix becomes the single operational target for inspection (backups are a non-goal per a coupled decision landing the same day). Docker's volume driver abstraction means platform code doesn't need to know where state physically lives; future operators can substitute external-storage drivers per-volume without touching compose config. The cost — loss of direct host-filesystem access to state — is accepted; the operator rarely needs that access in practice and can always spin up a short-lived debug container bind-mounting the volume when they do. ^p003

Implications for `compose.yml`. The SeaweedFS service mounts `atmosphere_seaweedfs:/data` instead of `./data/seaweedfs:/data`. The Redpanda service mounts `atmosphere_redpanda:/var/lib/redpanda/data` instead of `./data/redpanda:/var/lib/redpanda/data`. The top-level `volumes:` block declares both new entries with `name:` overrides mirroring the existing `atmosphere_postgres` pattern (pins the literal on-disk volume name regardless of `COMPOSE_PROJECT_NAME`). ^p004

Implications for scripts and repo layout. `scripts/up.sh` drops the preflight `mkdir` + `sudo chown` steps — Docker handles volume initialization and ownership automatically. `.gitignore`'s `data/` entry becomes cosmetic at M1 but stays as a safety net. ^p005

Design-doc edits required. `.claude/context/operations.md` §Volumes and storage needs a full rewrite. `.claude/context/components/iceberg.md` §SeaweedFS topology plus §Storage layout need updates (no more `./data/seaweedfs` references). `.claude/context/roadmap.md` §M1 build, §M3 build (Prometheus/Loki), and §M9 acceptance (ClickHouse cache) need path substitutions. ^p006

Forward posture. Future milestones follow the same pattern without re-litigating: every new stateful service gets an `atmosphere_<service>` docker-managed named volume with a `name:` override. The pattern is now the platform default. ^p007
