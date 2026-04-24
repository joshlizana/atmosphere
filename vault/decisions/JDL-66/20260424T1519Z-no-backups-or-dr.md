---
id: 01KQ016NEQCG9Z5KXYDZ1TG3V3
type: decision
name: 20260424T1519Z-no-backups-or-dr
created_at: 2026-04-24T15:19Z
created_by: log/01KQ016NEQCG9Z5KXYDZ1TG3V3
component: platform
---

## Purpose
Records the architectural decision that the Atmosphere platform ships no backup or disaster-recovery mechanism — recovery is always a fresh Jetstream 24-hour replay plus `dbt build`, and any data older than Jetstream's replay window is permanently unrecoverable by design.

## 2026-04-24T15:19Z — initial
- agent: log/01KQ016NEQCG9Z5KXYDZ1TG3V3
- refs: [[.claude/context/architecture]], [[.claude/context/operations]], [[.claude/context/components/iceberg]], [[.claude/context/components/spout]]

Outcome. The platform explicitly ships no backup or disaster-recovery functionality. There is no `docs/backups.md`, no `docs/disaster-recovery.md`, no backup scripts, no scheduled DR drills, no Prefect flow for volume snapshotting, no host-level backup guidance. Recovery from any failure — single-volume loss, total host loss, operator `make nuke` — is exactly what the architecture already encodes: Spout reconnects to Jetstream with a 24-hour cursor, Flink re-ingests bronze, `dbt build` rebuilds silver and gold from bronze. Any data older than Jetstream's 24-hour replay window is permanently unrecoverable by design, and surfaces as a visible gap in the analytics layer. ^p001

Alternatives considered. (1) Host-level tar/rsync backups of named volumes on an operator-chosen cadence, documented in `docs/backups.md` (what the original M1 operationalize band called for). Rejected: this is solo-operator personal-project scope; the full recovery path already exists (Jetstream replay → bronze → dbt → gold) and backups add an operational burden without improving the durability guarantee past the 24-hour window. (2) Filesystem-snapshot-based hot backups (btrfs/zfs/LVM) with `docs/backups.md` recommending one. Rejected for the same reason, plus the added host-filesystem dependency constrains operator hardware choice. The existing CachyOS CoW-default filesystem makes this tempting but the benefit is still bounded by the 24-hour re-ingest floor. (3) No backups, recovery through re-ingest only. The selected path. Matches the existing design claim that "Jetstream is the source of truth; everything else is a projection" (`.claude/context/architecture.md`). The operator's only pre-destructive-action discipline is "back up whatever matters outside the platform" — but the platform itself vows nothing. ^p002

Reasoning. The existing design already treats Jetstream as source of truth and Iceberg bronze as rebuildable. Layering operator-managed backups on top creates an inconsistent promise: the platform says "recovery is re-ingest" while backup docs would say "and also back up your SeaweedFS volume daily." The inconsistency is worse than the absence. Removing backups re-aligns the operator's mental model with the architectural reality — Iceberg bronze on a single-host deployment with no replication is explicitly in the "fine to lose" category. That's the tradeoff single-host scope makes. ^p003

Implications for docs. `docs/backups.md` does NOT exist. Will not be authored. Drops from the M1 operationalize band's file list. ^p004

Implications for roadmap §M14. The Build band's `docs/disaster-recovery.md` and `docs/backups.md` bullets drop entirely. The Validate band's "DR drill: destroy SeaweedFS, rebuild, confirm silver/gold rows match" reshapes into "Fresh-operator drill: clean CachyOS host, run `scripts/up.sh`, verify platform comes up from zero state in <1 hour and first Jetstream replay cycle produces bronze rows as expected." The rebuild IS the DR path; no separate drill. The Operationalize band's "Schedule quarterly DR drills in Prefect (run against a shadow volume; don't actually destroy production SeaweedFS)" drops entirely. No quarterly DR drills exist because no DR procedure exists. ^p005

Implications for roadmap Post-MVP backlog. "Backup strategy beyond bind-mount snapshotting (offsite replication, point-in-time recovery)" drops entirely. The non-goal is explicit, not deferred. ^p006

Implications for design docs. `.claude/context/components/iceberg.md` §SeaweedFS topology — "real durability comes from host-level backups of the SeaweedFS data directory" becomes "host loss is an accepted tradeoff; recovery from any failure is fresh Jetstream replay." `.claude/context/components/iceberg.md` §Durability model — "Iceberg data durability is provided by host-level backups" becomes "Iceberg data past the Jetstream 24-hour replay window is explicitly unguaranteed. Recovery is always fresh re-ingest; no backup mechanism exists." `.claude/context/operations.md` §Operational model already aligns — recovery = Jetstream replay; bronze rebuildable; silver/gold rebuildable — no edits needed beyond dropping any backup enumeration that lingers in §Volumes and storage. ^p007

Implications for `make nuke`. Semantics couple cleanly: `nuke` destroys everything the platform can regenerate (`docker compose down -v --remove-orphans && rm -rf ./data && rm -f .env`), and the next `make up` regenerates from zero. The operator's only warning before `make nuke` is "this destroys all bronze older than the Jetstream replay window." ^p008
