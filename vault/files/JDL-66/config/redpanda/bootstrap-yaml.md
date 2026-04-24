---
id: 01KPZQV883J6YXPD3HMYYGC9W2
type: file
name: bootstrap-yaml
created_at: 2026-04-24T12:36Z
created_by: log/01KPZQV883J6YXPD3HMYYGC9W2
component: redpanda
---

## Purpose
Tracks the lifecycle of `/home/josh/atmosphere/config/redpanda/.bootstrap.yaml` — Redpanda's first-boot cluster-property seed file. Cluster-scoped properties (as distinct from node-scoped ones) have exactly one legal injection path at cluster-first-boot: this YAML file in the broker's config directory. The file is read once before writes are accepted and later edits are silently ignored on an already-initialized cluster; subsequent cluster-property additions go here in their own PRs with the understanding that on a live cluster they only take effect via `rpk cluster config set` or a deliberate reinitialization.

## 2026-04-24T12:36Z — initial
- agent: log/01KPZQV883J6YXPD3HMYYGC9W2
- refs: [[research/JDL-66/redpanda-compose-single-broker-2026]], [[.claude/context/components/redpanda]]

Forge created `config/redpanda/.bootstrap.yaml` at commit `c7ebb30` on branch `JDL-66-m1-shared-infrastructure-online` with message `chore(JDL-66): seed Redpanda cluster-property bootstrap (storage_min_free_bytes)`. The file is a flat YAML document holding a single cluster-scoped property, `storage_min_free_bytes: 2147483648` (2 GiB exactly, 2 * 1024^3 bytes). ^p001

The leading dot in the filename is load-bearing — Redpanda's broker specifically looks for `.bootstrap.yaml` in its config directory and will not pick up a non-dotted variant. The file is read exactly once at cluster first-boot, before any writes are accepted; edits after first-boot are silently ignored by the broker. This constrains the operational model: every cluster-property seed for M1 must land in this file before the Redpanda container comes up for the first time, or it will require post-boot reconciliation via `rpk cluster config set` instead. ^p002

Cluster properties cannot be set via `--set redpanda.storage_min_free_bytes=...` on the `rpk` / `redpanda` command line because that syntax targets node-scoped properties exclusively; the bootstrap file is the only correct injection path for cluster-wide seeds at first boot. Node-level knobs (`--smp`, `--memory`, listener bindings, and similar) stay in the compose service's `command:` block and do not belong in this file — keeping the two scopes on two different surfaces prevents category-confusion drift as more knobs land in later milestones. ^p003

Subsequent cluster-property additions extend this file with additional keys; each addition lands in a future PR's own bootstrap-yaml edit, with the understanding that on an already-initialized cluster the new key takes effect only after a `redpanda.yaml` reload or a cluster-property override via `rpk cluster config set`. The `storage_min_free_bytes = 2 GiB` value itself is the aggressive-retention floor on the data volume that acts as a second-line defense against per-topic retention drift or a burst beyond the modeled 50 GB Redpanda volume envelope, per the platform-wide storage-floor rationale in `.claude/context/components/redpanda.md`. ^p004
