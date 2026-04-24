---
id: redpanda-admin-api-listener-v26
type: research
name: Redpanda v26.1.x admin API listener — canonical rpk redpanda start config (2026)
created_at: 2026-04-24
created_by: scout
component: redpanda
---

## Purpose

Nail down the canonical mechanism in Redpanda v26.1.x for binding the admin API listener to `0.0.0.0:9644` when the broker is launched via `rpk redpanda start` inside a single-broker Docker container. Resolves the M1 smoke blocker surfaced by the prior Scout note (`vault/research/JDL-66/redpanda-compose-single-broker-2026.md`, §p052 third bullet), which asserted "admin API bind is implicit — binds to 0.0.0.0:9644 by default" and recommended that `--admin-addr=0.0.0.0:9644` be added only as a future explicit-config option. Live-tested against `docker.redpanda.com/redpandadata/redpanda:v26.1.6` (JDL-66 branch), the binary rejects `--admin-addr=0.0.0.0:9644` with `Argument parse error: unrecognised option '--admin-addr=0.0.0.0:9644'` and then crash-loops. The correct fix must (a) be accepted by the v26.1.6 binary, (b) bind admin on `0.0.0.0:9644` so the host port-map `9644:9644` is reachable, and (c) keep the in-container healthcheck `curl http://localhost:9644/v1/status/ready` green.

## Entry — correction — 2026-04-24 — scout

**agent:** scout
**refs:** [[research/JDL-66/redpanda-compose-single-broker-2026]], [[.claude/context/components/redpanda]], [[.claude/context/operations]] (§Host ports, §Deployment), [[.claude/context/roadmap.md]] (M1), `rpk redpanda start` flag reference (current), Broker Configuration Properties reference, Specify Admin API Addresses for rpk, `rpk redpanda config set` reference, `rpk redpanda start` source code at `v26.1.6` tag (`src/go/rpk/pkg/cli/redpanda/start.go`), Redpanda discussion #6851 (`--set redpanda.<property>` pattern), Redpanda single-broker labs example
**corrects:** [[research/JDL-66/redpanda-compose-single-broker-2026]] §p040 and §p052 third bullet — the admin listener does NOT default to `0.0.0.0:9644`; the documented default in `redpanda.yaml`'s broker-properties reference is `{address: "127.0.0.1", port: 9644}`, which renders the host port mapping `9644:9644` unreachable from outside the container without explicit config. The suggestion in §p052 that `--admin-addr 0.0.0.0:9644` is "the obvious path if a future change needs an admin-API-only internal listener" is also wrong: `--admin-addr` has never been registered as a flag on `rpk redpanda start` in any current release line, and v26.1.6 explicitly rejects it.

### The flag shape caller proposed — `--admin-addr` — does not exist on `rpk redpanda start` ^p001

The v26.1.6 live error (`Argument parse error: unrecognised option '--admin-addr=0.0.0.0:9644'`) matches what the source code and the current docs table both show: the `rpk redpanda start` subcommand registers flags for Kafka (`--kafka-addr`), Pandaproxy (`--pandaproxy-addr`), Schema Registry (`--schema-registry-addr`), and RPC (`--rpc-addr`) listeners — but not for admin. The admin listener is the only broker listener without a first-class `--<listener>-addr` convenience flag. The current docs page for `rpk redpanda start` (`docs.redpanda.com/current/reference/rpk/rpk-redpanda/rpk-redpanda-start/`) lists every flag in a single table, and there is no `--admin-addr` entry. Cross-checked against the GitHub source at tag `v26.1.6` (`src/go/rpk/pkg/cli/redpanda/start.go`, flag registration block beginning around line 345) — only the four listener flags above are registered; no admin flag is ever added. ^p002

The prior Scout note's "admin-addr as an obvious future path" suggestion was a reasonable inference by pattern-match from the other four listeners but is not actually wired up. Do not reintroduce it. ^p003

### The admin listener default is `127.0.0.1:9644`, NOT `0.0.0.0:9644` ^p004

The authoritative source is `docs.redpanda.com/current/reference/properties/broker-properties/`, which lists the `admin` property with default value `{address: "127.0.0.1", port: 9644}`. Two other docs pages (`get-started/admin-addresses/` and informal blog posts) summarize the default as "0.0.0.0" — this is a documentation inconsistency, not a version difference. The authoritative broker-properties reference and the dev-deployment guide's example `redpanda.yaml` both leave `admin` as a `- address: <listener-address>, port: 9644` placeholder that the operator must fill in; the broker-properties table is the one that specifies the baked-in default when no configuration applies. ^p005

On `rpk redpanda start` with no `redpanda.yaml` mounted, no `--set redpanda.admin[...]`, and no admin-addr flag (because none exists), the effective listener is the broker-properties default: `127.0.0.1:9644`. Loopback-only. The in-container healthcheck `curl -sf http://localhost:9644/v1/status/ready` is unaffected — `localhost` inside the container resolves to `127.0.0.1`, so the probe works. The host port-map `9644:9644` is the thing that breaks: Docker's userland-proxy cannot forward to a listener that is only bound on the container's loopback interface, so `curl -sf http://<host>:9644/v1/status/ready` from outside the container returns connection-refused. This is consistent with the crash-loop behavior reported: if the v26.1.6 binary rejects the bogus `--admin-addr` flag at argv parse time, it exits non-zero immediately, and `docker compose` reschedules the container — the listener default is never reached because the process never starts. Fixing the argv error alone without also binding admin on `0.0.0.0` would silently swap one failure mode (crash-loop) for another (healthy container that the host can't reach). ^p006

### Canonical fix — `--set redpanda.admin[0].address=0.0.0.0 --set redpanda.admin[0].port=9644` ^p007

`rpk redpanda start` supports an undocumented-but-functional `--set <key>=<value>` flag that writes directly into the in-memory `redpanda.yaml` config tree before the broker subprocess launches. It is NOT in the docs-page flag table (only `-X` / `--config-opt` is listed there, which targets `rpk.yaml` not `redpanda.yaml`), but it is implemented in the source at `src/go/rpk/pkg/cli/redpanda/start.go` via a `parseConfigKvs` function (lines 108-122 on the `v26.1.6` tag) that extracts `--set` pairs from `os.Args` before cobra flag parsing runs, and a `setConfig` function (around line 945 on the same tag) that applies each pair through `config.Set(y, key, value)`. This is the same `config.Set` path that the documented `rpk redpanda config set` command uses, which means the bracket-index notation documented for `rpk redpanda config set redpanda.kafka_api[0].port=9092` works identically for `--set` on `rpk redpanda start`. ^p008

Concrete addition to the existing `command:` list in `compose.yml`: ^p009

```yaml
- --set=redpanda.admin[0].address=0.0.0.0
- --set=redpanda.admin[0].port=9644
```

Two separate `--set` entries — one per property path. Do NOT try to collapse them into a single `--set redpanda.admin[0]='{address: 0.0.0.0, port: 9644}'` line; while `rpk redpanda config set` supports that YAML-object shape, the `--set` parser on `rpk redpanda start` splits on the first `=` sign only and treats the remainder as a scalar, so the YAML-literal shape would be interpreted as a flat string assignment to `redpanda.admin[0]` and fail type-check at config-apply time. Two separate key/value pairs is the shape that matches how the source code parses. ^p010

The `[0]` index creates the admin listener as the first (and only) entry in the `admin` array. Since the array is empty at this point (nothing else has written to it), `[0]` is the correct index. Future work that wants a second admin listener — say, a TLS-terminated external listener on a different port — would add `--set=redpanda.admin[1].address=...` alongside the existing index-0 entry. ^p011

### Do not use `.bootstrap.yaml` for this ^p012

The admin listener is a **node-scoped** property (lives under `redpanda:` in `redpanda.yaml`), not a cluster-scoped property. `.bootstrap.yaml` is a first-boot-only override for cluster-scoped properties (what `rpk cluster config set` targets — `storage_min_free_bytes`, `log_retention_ms`, and similar) and does NOT accept node-scoped keys like `redpanda.admin[0].address`. Mixing them in `.bootstrap.yaml` either silently ignores them or errors on first-boot parse depending on the Redpanda version. The existing `config/redpanda/.bootstrap.yaml` (single line: `storage_min_free_bytes: 2147483648`) is correctly scoped; do not add `admin:` entries to it. ^p013

### Do not mount a `redpanda.yaml` either ^p014

The alternative to `--set` is to generate a full `redpanda.yaml` on disk and bind-mount it at `/etc/redpanda/redpanda.yaml`. This is what the Redpanda production-deployment guide walks through and what every multi-node cluster does. For Atmosphere's single-broker shape it is wrong on three counts: (a) the existing compose `command:` block already encodes every node property that matters (Kafka addr, RPC addr, SMP, memory, overprovisioned, log level); the only missing piece is two admin entries, which is exactly what `--set` exists for; (b) mounting a `redpanda.yaml` fragments node config across two sources (the compose `command:` block + the yaml file), which makes "what does this broker actually bind?" a two-place lookup; (c) historical compose + redpanda bind-mount interactions have produced confusing "device or resource busy" errors when the container's entrypoint writes to `redpanda.yaml` on first init (documented in redpanda#6851). Sticking with `--set` on the command-line keeps node config in one reviewable place (the compose YAML), which is the same reasoning §p027 of the prior Scout note already applied to the rest of the node configuration. ^p015

### Updated compose service definition ^p016

The minimal diff against the prior Scout note's §p051 canonical compose block is two new lines in the `command:` list. The full updated block for reference: ^p017

```yaml
services:
  redpanda:
    image: docker.redpanda.com/redpandadata/redpanda:v26.1.6
    container_name: redpanda
    command:
      - redpanda
      - start
      - --kafka-addr=0.0.0.0:9092
      - --advertise-kafka-addr=redpanda:9092
      - --rpc-addr=redpanda:33145
      - --advertise-rpc-addr=redpanda:33145
      - --set=redpanda.admin[0].address=0.0.0.0
      - --set=redpanda.admin[0].port=9644
      - --smp=1
      - --memory=1536M
      - --reserve-memory=0M
      - --overprovisioned
      - --default-log-level=info
    volumes:
      - ./data/redpanda:/var/lib/redpanda/data
      - ./config/redpanda/.bootstrap.yaml:/etc/redpanda/.bootstrap.yaml:ro
    ports:
      - "9092:9092"
      - "9644:9644"
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:9644/v1/status/ready || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 30s
    deploy:
      resources:
        reservations:
          memory: 1536M
    restart: unless-stopped
```

Every other element of the prior Scout note's compose block (§p051) remains correct: image tag, `--kafka-addr=0.0.0.0:9092`, advertise-kafka, RPC listener, Seastar sizing flags, no `--mode`, no schema-registry-addr, no pandaproxy-addr, healthcheck, port map, mem reservation. The two `--set` entries are the sole addition. ^p018

### Why not also add `--set=redpanda.admin[0].name=...` ^p019

The admin array item's `name` field is optional when there is a single listener (the dev-deployment example omits it). It becomes load-bearing only when multiple admin listeners exist and TLS config needs to reference them by name. At one listener there is no ambiguity. Keeping the `--set` list to exactly two lines (address + port) matches the minimum surface that fixes the blocker. If a future TLS-terminated admin listener is added, name both listeners at once in the same commit (§p062 of the prior Scout note flagged the same "name all or name none" gotcha for Kafka listeners). ^p020

### Healthcheck implication — unchanged ^p021

The in-container healthcheck `curl -sf http://localhost:9644/v1/status/ready || exit 1` works regardless of whether admin binds on `127.0.0.1` or `0.0.0.0` — `localhost` resolves to `127.0.0.1` inside the container, and both bind addresses accept traffic destined to `127.0.0.1` on port 9644. The healthcheck success criterion was never the thing that was actually broken; it was the external host port-map reachability and the caller's ability to run `rpk cluster config get ...` from outside the container. Both are fixed by binding on `0.0.0.0`. ^p022

### Advertise-addr implications — none needed ^p023

The admin API does not have an "advertise" counterpart the way Kafka and RPC do. Kafka and RPC need advertise addresses because clients and peer brokers must know how to reach the broker from wherever they are, which can differ from where the broker binds (the `internal://redpanda:9092` / `external://localhost:19092` dual-listener trick in the labs example). Admin is a local-administrative-traffic API only — clients (`rpk`, Prometheus scraping the status endpoint, a future Grafana panel) target it by the address they already know (`redpanda:9644` inside the compose network, `localhost:9644` from the host), and the broker does not publish admin endpoints in any discovery protocol. So no `--set=redpanda.advertised_admin_api[0]...` work is needed, and no such property exists in the broker-properties reference. ^p024

### Security implication — acknowledged, same posture as prior note ^p025

Binding admin on `0.0.0.0` makes the admin API reachable from (a) any container on the compose network, and (b) any host on the host's network (via the `9644:9644` port map). The prior Scout note's §p064 already flagged this: "Admin-API 9644 binds 0.0.0.0 by default. On a host with 9644 exposed (we do expose it per the port map), this means anything on the host's network can hit the admin API unauthenticated. Atmosphere's single-trust-domain posture already accepts this for the compose-network-internal side; the host-exposed side relies on the host's firewall. This matches the posture already taken for Lakekeeper, SeaweedFS S3, and every other admin surface." That paragraph read as a doc-correctness-only statement when written; after this correction, it is also the actual operational posture we are adopting. No change in scope — the posture matches the design doc's single-trust-domain framing — but worth re-noting that the "binds on 0.0.0.0 by default" clause is now true by explicit config, not by broker default. Update `docs/runbooks/redpanda.md` in M13 to reflect this when it's written. ^p026

### Gotchas ^p027

- **`--set` is not in the `rpk redpanda start` docs-table flag list.** The current docs page (`docs.redpanda.com/current/reference/rpk/rpk-redpanda/rpk-redpanda-start/`) only lists `-X` / `--config-opt`, which targets `rpk.yaml` — an entirely separate config file used by `rpk` itself, not by the broker. `-X redpanda.admin[0].address=0.0.0.0` would be silently written to `rpk.yaml`'s cloud section, not to `redpanda.yaml`'s broker section, and would not change the broker's admin listener binding. Only the (undocumented but functional) `--set` flag does the right thing. If a future release of Redpanda deprecates or removes `--set`, the fallback is to generate and bind-mount a small `redpanda.yaml` — at which point revisit §p014. The GitHub discussion at redpanda#6851 confirms `--set` as the community-idiomatic path on the compose image. ^p028
- **`--set=key=value` with the equals sign vs `--set key value` as two tokens.** Both work; cobra/pflag tolerates either, and the special `parseConfigKvs` function strips `--set` before cobra sees it regardless. The equals-sign form is the shape every other flag in our `command:` list uses, so keep it for consistency. ^p029
- **Bracket notation on empty arrays creates elements at the index.** `--set=redpanda.admin[0].address=0.0.0.0` on a fresh broker with no existing admin config creates an admin entry at index 0 with just `address` set, then the follow-up `--set=redpanda.admin[0].port=9644` fills in `port`. Running only the first `--set` line would yield `admin: [{address: 0.0.0.0}]` with port defaulting to whatever the broker-properties default is for `port` alone (still 9644 — confirmed from the broker-properties default `{address: "127.0.0.1", port: 9644}` being a unified object default, so port fills in from the same source). Pass both lines anyway for explicitness; relying on the default-port fallback is a foot-gun a future operator adding a second listener would trip on. ^p030
- **Seastar argv error vs rpk flag error.** The `Argument parse error: unrecognised option '--admin-addr=0.0.0.0:9644'` message comes from the Seastar command-line parser, not from rpk. That is because `rpk redpanda start` (when run with an unrecognized flag) falls through and forwards the full argv to the `redpanda` binary, which then fails its own Seastar-level parse. So the error message is literally telling us "the redpanda broker binary does not accept `--admin-addr`" — which is consistent with the Seastar reactor owning every listener flag (`--kafka-addr`, `--rpc-addr`) but NOT owning admin (admin lives entirely in the redpanda application layer, configured via `redpanda.yaml` only). This confirms that no "just different flag name" exists — the broker binary genuinely has no admin-listener argv flag, because the design intent is that admin is yaml-configured. `--set` on the rpk wrapper is the only command-line path that reaches admin config. ^p031
- **The default is `127.0.0.1:9644`, not `0.0.0.0:9644`, and cross-doc summaries disagree.** `docs.redpanda.com/current/get-started/admin-addresses/` and several blog posts summarize the default as "0.0.0.0"; the authoritative `docs.redpanda.com/current/reference/properties/broker-properties/` table specifies `{address: "127.0.0.1", port: 9644}`. The disagreement is probably historical drift in the summary pages; the properties reference is the canonical source and is what the binary actually honors. The observable behavior (Docker port-forward failing through to the container's loopback-only listener) matches the properties reference's default, not the summary pages'. ^p032
- **The labs single-broker example appears to work without `--set redpanda.admin[...]`, but uses `--mode dev-container`.** `dev-container` mode is NOT listed in the broker-properties reference as changing the admin default, but empirically the labs example at `docs.redpanda.com/redpanda-labs/docker-compose/single-broker/` exposes admin as `19644:9644` and works without any explicit admin-addr config. Two possible explanations: (a) dev-container mode silently flips the admin default to `0.0.0.0`, which would be consistent with its other "developer-friendly but unsafe" defaults (fsync off, developer_mode true), or (b) the labs example has been drifting for a while and Console connects successfully only because Console and Redpanda share the compose bridge and reach each other by service-name DNS on some path that doesn't go through the admin API. Did not drill into which explanation is right; either way, Atmosphere deliberately does NOT use `--mode dev-container` (prior Scout §p004-p006) so we cannot rely on whatever implicit admin behavior it enables. Explicit `--set` is the path for us. ^p033

### What this note deliberately does not recommend ^p034

- **`--admin-addr=0.0.0.0:9644`** — does not exist as a flag on `rpk redpanda start` or on the redpanda broker binary itself. Caller-proposed syntax; does not parse. ^p035
- **`--mode dev-container`** — same footgun as the prior note (§p004-p006). Might incidentally fix the admin listener, but at the cost of fsync-off and developer_mode semantics. ^p036
- **Mounting a full `redpanda.yaml`** — fragments node config across two sources and invites the bind-mount-busy class of issue (§p015). ^p037
- **Adding `admin:` entries to `.bootstrap.yaml`** — wrong file; that's cluster-scoped, admin is node-scoped (§p013). ^p038
- **`-X redpanda.admin[0].address=0.0.0.0`** — targets `rpk.yaml` (rpk's own config), not `redpanda.yaml` (broker config). Would silently succeed at the flag-parse level and fail to affect broker listener binding. See §p028. ^p039
- **`rpk cluster config set` after broker start** — does not apply to node-scoped properties like `admin`. `rpk cluster config` only addresses cluster-scoped properties. Attempting `rpk cluster config set admin ...` returns an unknown-property error. ^p040

### Summary of choices ^p041

- **Flag:** two `--set` pairs on the `rpk redpanda start` command line: `--set=redpanda.admin[0].address=0.0.0.0` and `--set=redpanda.admin[0].port=9644`.
- **No `redpanda.yaml` mount needed.** Node config stays fully expressed in the compose `command:` block.
- **No `.bootstrap.yaml` change needed.** Admin is node-scoped; `.bootstrap.yaml` is cluster-scoped.
- **Healthcheck stanza unchanged** from prior Scout note §p039.
- **Port map `9644:9644` unchanged** — will now actually be reachable from the host once the listener binds `0.0.0.0`.
- **`--admin-addr` is not a real flag and should not appear in the compose file.** Was a caller-side hypothesis; v26.1.6 rejects it.
- **Broker-properties default for `admin` is `{address: "127.0.0.1", port: 9644}`** — loopback-only unless explicitly overridden. This is the load-bearing correction against the prior Scout note's assertion that admin defaults to `0.0.0.0`.

^p042

### Sources ^p043

- `rpk redpanda start` flag reference (current): https://docs.redpanda.com/current/reference/rpk/rpk-redpanda/rpk-redpanda-start/
- Broker Configuration Properties reference (authoritative defaults table): https://docs.redpanda.com/current/reference/properties/broker-properties/
- Specify Admin API Addresses for rpk: https://docs.redpanda.com/current/get-started/admin-addresses/
- `rpk redpanda config set` (documents bracket-index notation): https://docs.redpanda.com/current/reference/rpk/rpk-redpanda/rpk-redpanda-config-set/
- Redpanda production deployment guide (example `redpanda.yaml`): https://docs.redpanda.com/current/deploy/deployment-option/self-hosted/manual/production/production-deployment/
- Redpanda dev deployment guide (example `redpanda.yaml`): https://docs.redpanda.com/current/deploy/redpanda/manual/production/dev-deployment/
- Redpanda single-broker labs example: https://docs.redpanda.com/redpanda-labs/docker-compose/single-broker/
- `rpk redpanda start` source at `v26.1.6` tag: https://github.com/redpanda-data/redpanda/blob/v26.1.6/src/go/rpk/pkg/cli/redpanda/start.go
- Redpanda discussion #6851 (`--set redpanda.<property>` pattern in compose): https://github.com/redpanda-data/redpanda/discussions/6851
- Redpanda admin API `/v1/status/ready` endpoint: https://docs.redpanda.com/api/doc/admin/operation/operation-ready/
- Prior Scout note being corrected: [[research/JDL-66/redpanda-compose-single-broker-2026]]
