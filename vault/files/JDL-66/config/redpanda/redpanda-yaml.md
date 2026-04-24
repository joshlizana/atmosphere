---
id: 01KQ0QG8N9CHXXG7P71SNR2PX9
type: file
name: redpanda-yaml
created_at: 2026-04-24T21:49Z
created_by: log/01KQ0QG8N9CHXXG7P71SNR2PX9
component: redpanda
---

## Purpose
Tracks the lifecycle of `/home/josh/atmosphere/config/redpanda/redpanda.yaml` — Redpanda's node-scoped config file mounted into `/etc/redpanda/redpanda.yaml` read-only on the broker container. The file is the canonical injection path for node-level properties (listener bindings, SMP/memory knobs, etc.) that either have no working `rpk redpanda start` flag or whose flag variants are rejected by the broker version in use. Node-level property additions that cannot ride a compose `command:` flag land here; cluster-scoped seeds stay in the sister `.bootstrap.yaml`.

## 2026-04-24T21:49Z — initial
- agent: log/01KQ0QG8N9CHXXG7P71SNR2PX9
- refs: [[files/JDL-66/config/redpanda/bootstrap-yaml]], [[files/JDL-66/compose-yml]], [[incidents/JDL-66/20260424T1723Z-rpk-set-flag-not-stripped-by-redpanda-v26]], [[research/JDL-66/redpanda-admin-api-listener-v26]], [[research/JDL-66/redpanda-compose-single-broker-2026]]

Forge created `config/redpanda/redpanda.yaml` at commit `2caa6a2` on branch `JDL-66-m1-shared-infrastructure-online`. The file is a 10-line YAML document — a 5-line header comment block followed by a 4-line body declaring a single node-level property: a `redpanda.admin` listener list with one entry binding `0.0.0.0:9644`. ^p001

The file exists to solve one specific problem surfaced in `[[incidents/JDL-66/20260424T1723Z-rpk-set-flag-not-stripped-by-redpanda-v26]]`: the v26.1.6 broker binary has no admin-listener flag exposed via `rpk redpanda start` that actually works — `--admin-addr` is unknown to the parser, and the `--set=redpanda.admin[N].*` variant produces a passthrough rejection. The canonical mechanism the broker does honor is reading `/etc/redpanda/redpanda.yaml` at startup. This file supplies exactly that, with the minimum content needed to produce the desired listener binding. ^p002

Scope discipline: the file intentionally carries nothing else. Other Redpanda node-level properties (`data_directory`, `seed_servers`, `kafka_api`, `advertised_kafka_api`, `rpc_server`, etc.) are set by the compose `command:` flags that pass through to the broker correctly — duplicating them here would create config drift between the two surfaces. Cluster-level properties (`storage_min_free_bytes` and future additions) are seeded once at first boot via the sister `[[files/JDL-66/config/redpanda/bootstrap-yaml]]` and this file does not touch them. Every future node-level property addition either goes here (if the broker accepts it via the file) or via a `rpk redpanda start` flag (if the flag exists and works). ^p003

Validation run at commit time: `python3 -c 'import yaml; yaml.safe_load(open("config/redpanda/redpanda.yaml"))'` returned the expected structure `{'redpanda': {'admin': [{'address': '0.0.0.0', 'port': 9644}]}}`. Trailing whitespace check was clean, unix line endings, trailing newline at EOF. ^p004

A parallel Forge invocation (m1-forge-018) modified `compose.yml` in the same work batch to add the mount (`./config/redpanda/redpanda.yaml:/etc/redpanda/redpanda.yaml:ro`) alongside the existing `.bootstrap.yaml` mount, and to remove the two broken `--set=redpanda.admin[0].*` command-line flags that `[[incidents/JDL-66/20260424T1723Z-rpk-set-flag-not-stripped-by-redpanda-v26]]` identified as the failure vector. The `compose.yml` edit is tracked separately in `[[files/JDL-66/compose-yml]]`. ^p005
