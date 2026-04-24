---
id: redpanda-compose-single-broker-2026
type: research
name: Single-broker Redpanda compose pattern for M1 — image tag, command flags, healthcheck, bootstrap (2026)
created_at: 2026-04-24
created_by: scout
component: redpanda
---

## Purpose

Pin down the 2026-canonical single-broker single-node Redpanda Docker Compose pattern Atmosphere needs for M1 (JDL-66). Closes: (a) which `redpandadata/redpanda` image tag to pin to in April 2026; (b) the exact `command:` argument list for a production-posture single-node broker that binds only Kafka (9092) and admin (9644), with pandaproxy and schema registry fully disabled; (c) how to bake `storage_min_free_bytes = 2 GiB` into a fresh broker at first boot; (d) the canonical data-directory path and bind-mount ownership story; (e) the right healthcheck against the admin API; (f) correct sizing flags (`--smp`, `--memory`, `--overprovisioned`) for a 6-core / 12-thread host where Redpanda gets a 1.5 GB soft reservation and shares CPU with ~18 other containers.

## Entry — initial — 2026-04-24 — scout

**agent:** scout
**refs:** [[.claude/context/components/redpanda.md]], [[.claude/context/operations.md]] (§Deployment, §Host ports, §Resource allocation), [[.claude/context/roadmap.md]] (M1), Redpanda docs single-broker labs example (v26.1.6), `rpk redpanda start` reference, `rpk redpanda mode` reference, cluster-properties docs (storage_min_free_bytes), Redpanda self-managed production deployment guide (.bootstrap.yaml), Redpanda admin API `/v1/status/ready` reference, helm-charts#1002 (rpk-cluster-health-as-probe critique), redpanda#12717 (UID 101 / OpenShift)

### Image tag — v26.1.6 on the docker.redpanda.com registry ^p001

The current stable line in April 2026 is **v26.1.x**. The canonical single-broker labs example on docs.redpanda.com pins `docker.redpanda.com/redpandadata/redpanda:v26.1.6` as of this writing; v26.1.6 is the most recent patch shipped. The release-notes index page confirms v26.1.6 is the current stable broker and v3.7.1 is the current Console, with the broker release line's declared EOL date 2027-03-31. There is no active v24.x or v25.x line branded as the "supported stable" for new deployments — 26.1 is the right pin. ^p002

The registry to pin against is **`docker.redpanda.com/redpandadata/redpanda`**, not `redpandadata/redpanda` on Docker Hub. Both mirror the same artifacts, but the Redpanda-run CDN (`docker.redpanda.com`) is the path the Redpanda docs lead with and the one that receives releases first; Docker Hub lags by minutes-to-hours and is kept in sync as a convenience. Using the Redpanda registry also avoids Docker Hub's unauthenticated pull-rate limits, which are not a problem at our scale today but can surface as opaque CI failures on shared-IP runners. Pin the full version: `docker.redpanda.com/redpandadata/redpanda:v26.1.6`. No floating `latest` tag — the Docker Hub page surfaces `latest` and `latest-fips` but neither is recommended for a long-lived deployment. ^p003

### Mode: do NOT use `--mode dev-container` ^p004

The official labs example uses `--mode dev-container`. That is correct for a laptop dev loop and wrong for Atmosphere's M1 backing broker. `dev-container` bundles a set of cluster-property overrides that disable fsync, enable `developer_mode: true`, and set `overprovisioned: true` — the fsync-off piece is specifically called out as "never use in production" by downstream guides because it risks data loss on host crash. Our M1 broker is bind-mounted under `./data/redpanda` with 50 GB of per-topic retention budget that is load-bearing for the platform's 24-hour replay horizon; we need fsync semantics to be real. ^p005

The right mode for Atmosphere is **omit `--mode` entirely** (default `production`-equivalent behavior) and explicitly set `--overprovisioned` separately as its own flag (§p008 below). The `rpk redpanda mode production` / `rpk redpanda mode prod` subcommand exists as a post-install helper but operates by writing properties into `redpanda.yaml` on disk; for a fresh container with no mounted config file, the effective default at the `rpk redpanda start` level without `--mode` is already production-shaped (no fsync bypass, no forced overprovisioned). Confirmed against the `rpk redpanda mode` docs: the dev-mode flags it sets (`developer_mode: true`, `overprovisioned: true`, `fsync: false`) are only applied when dev mode is explicitly chosen. ^p006

### Sizing — `--smp 1`, `--memory 1536M`, `--reserve-memory 0M`, `--overprovisioned` ^p007

Atmosphere runs on a 6-core / 12-thread host with ~18 containers and a ~21 GB container envelope. Redpanda gets a 1.5 GB `mem_reservation` (soft) and no hard cap per [[.claude/context/operations.md]] §Resource allocation. The right Seastar-level sizing: ^p008

- **`--smp 1`** — one Seastar reactor shard. Redpanda at 500 msg/sec live steady-state and ~20-30 M messages over a 24-hour replay is not CPU-bound; a single shard is sufficient. `--smp 2` would double thread count without throughput benefit at our volume, and `--smp 1` is what the Redpanda labs examples default to. ^p009
- **`--memory 1536M`** — matches the soft reservation exactly, so Seastar's fixed-size memory allocator sizes itself to the same envelope the compose scheduler is planning against. Without an explicit `--memory`, Seastar on a 32 GB host tries to claim "most of the host RAM" (it cannot read cgroup limits reliably in docker) and will produce startup warnings about memory pressure even though the actual steady-state footprint is smaller. Setting `--memory` to the intended reservation aligns the runtime with the platform-level budget. ^p010
- **`--reserve-memory 0M`** — tells Seastar not to set aside additional OS-reserved memory on top of the `--memory` value. The default (`--reserve-memory 1500M`) makes sense on a bare-metal host with a lot of headroom and is actively wrong in a 1.5 GB container envelope, where it collides with the very envelope it's "reserving" within. Zero is correct for a containerized deployment at this size. ^p011
- **`--overprovisioned`** — required for a shared-CPU deployment. This flag disables thread affinity (no CPU pinning), zeros idle polling time, and disables busy-poll for disk I/O. On a 6-core host with 18 other containers, busy-polling one whole core permanently for Redpanda would make the rest of the platform measurably slower on CPU-bursty work (Flink checkpoints, dbt runs, Oracle batches). Cost is modest tail-latency on Redpanda itself, which at our 500 msg/sec steady-state is invisible. The flag is orthogonal to `--mode` — setting `--overprovisioned` with the default (production-shaped) mode gives us "production semantics + yield CPU to neighbors," which is exactly the posture we want. Do not confuse this with dev-container mode, which also enables overprovisioned but couples it to the fsync-off footgun. ^p012
- **`--default-log-level=info`** — keeps logs informative without flooding. `warn` would be quieter but suppresses startup diagnostics we want on first-boot troubleshooting. Revisit to `warn` post-M13 once Grafana dashboards surface the same signals. ^p013

### Disable schema registry and pandaproxy entirely — omit the `--*-addr` flags ^p014

The load-bearing question: how do you actually turn off schema registry and pandaproxy so they don't bind their default ports 8081 and 8082 (which collide with Flink's JM UI and don't serve any consumer in Atmosphere)? ^p015

The answer is **omit `--schema-registry-addr` and `--pandaproxy-addr` entirely from the `command:` list**. The `rpk redpanda start` reference documents these flags as "bind to [service] listeners"; when the flag is not passed, no listener is created. This is the flag-only default — with no `redpanda.yaml` mounted and no `--schema-registry-addr` argument, the schema registry subsystem never starts, and port 8081 is never bound inside the container. Same for pandaproxy on 8082. No explicit "disable" flag exists (nothing like `--no-schema-registry`); the configuration surface is addr-or-nothing. The widely-copied labs example always shows these flags because Console wants to render both surfaces; Atmosphere uses neither Console nor either listener, so they vanish by omission. ^p016

Confirmed by tracing the labs example: every configuration in `docs.redpanda.com/redpanda-labs/docker-compose/*` that includes schema registry and pandaproxy does so by explicit `--*-addr` flags; the Redpanda broker-properties doc mentions them as properties that can be set but does not describe "disable" semantics because the feature is addr-driven. One more confirmation: the broker's startup log lines `"starting schema registry service"` and `"starting pandaproxy"` only appear when their respective addr flags are set. ^p017

This also sidesteps the 8081 / Flink-JM-UI collision called out in [[.claude/context/components/redpanda.md]]: since schema registry never starts, 8081 is never bound inside the Redpanda container, and Flink's JM UI (bound on the host to 8081) has no in-container competitor. The host-port mapping is clean. ^p018

### storage_min_free_bytes — use `.bootstrap.yaml`, not `--set`, not rpk-after-start ^p019

`storage_min_free_bytes` is a **cluster-scoped property**, not a node-scoped one. Node properties go in `redpanda.yaml` (or as `rpk redpanda start` CLI flags); cluster properties require the controller Raft group to exist, which means the broker must be up first. The three paths to set a cluster property: ^p020

1. **`rpk cluster config set storage_min_free_bytes=<bytes>` after the broker is up** — works, but requires a post-start step in the compose bring-up. Fragile in docker-compose (no natural "run once after service_healthy" hook) and leaves a window where the broker is accepting writes before the hard-limit is in place. Not suitable for first-boot. ^p021
2. **`--set redpanda.storage_min_free_bytes=...` on the `rpk redpanda start` command line** — the `--set` flag works for node properties (the ones that live under the `redpanda:` key of `redpanda.yaml`) and aliased pandaproxy / schema_registry properties, but `storage_min_free_bytes` is a *cluster* property, not prefixed under `redpanda:` in the config tree. The idiomatic path for cluster properties is not `--set`. ^p022
3. **`.bootstrap.yaml` file in the data directory (same dir as `redpanda.yaml`) ← correct path** — the Redpanda production deployment guide documents this as the "special case where you want to provide configuration to Redpanda before it starts for the first time." The file is read exactly once at cluster first-boot (determined by the absence of a controller log) and its contents are applied as cluster configuration before the controller accepts any writes. Subsequent edits are silently ignored; changes after first-boot must go through `rpk cluster config`. The file is a flat YAML dictionary of cluster-property keys. ^p023

For Atmosphere M1, commit `config/redpanda/.bootstrap.yaml`: ^p024

```yaml
storage_min_free_bytes: 2147483648  # 2 GiB — guard against retention-config drift
```

Bind-mount this file read-only into the container at the canonical config location (§p030 below) alongside any `redpanda.yaml`. Because the file is single-consumer and one-shot, a hash-of-file check is not needed — if the broker ever needs a re-init, the answer is to wipe `./data/redpanda` and let first-boot fire again. Document this semantic in `docs/runbooks/redpanda.md` so a future operator doesn't update `.bootstrap.yaml` expecting it to take effect. ^p025

The filename must be exactly `.bootstrap.yaml` (leading dot). A filename of `bootstrap.yaml` (no dot) is ignored. Confirmed by reading the Redpanda production deployment guide verbatim. ^p026

### Config approach — command-line flags, no mounted redpanda.yaml ^p027

Between "full `redpanda.yaml` mounted into the container" and "command-line flags only," the idiomatic 2026 pattern for a single-broker dev-adjacent deployment is **command-line flags plus `.bootstrap.yaml` for cluster properties that can't be flag-set**. This is what every `docs.redpanda.com/redpanda-labs/*` example does; `redpanda.yaml` is a path generally taken when operating a multi-node cluster with seed-broker lists, rack awareness, and mTLS — none of which apply to Atmosphere's single-node single-trust-domain posture. ^p028

The concrete upshot: the `config/redpanda/` directory on disk contains exactly one file (`.bootstrap.yaml`) and nothing else. The broker's node config is fully expressed in the compose `command:` block, which is version-controlled and reviewable in a PR alongside the compose YAML itself — no indirection through a second YAML file. If future M4+ work needs a real `redpanda.yaml` (for example to tune per-topic defaults that can't be flag-set), add it then; do not scaffold an empty one preemptively. ^p029

### Data directory and bind-mount ownership — UID 101, no chown dance needed ^p030

The Redpanda container runs as `USER redpanda` which resolves to **UID 101** in the upstream image. The canonical data directory path inside the container is `/var/lib/redpanda/data`; the canonical config directory is `/etc/redpanda/`. Both paths are settable via `rpk redpanda start --config` and `--data-directory` but using the defaults keeps us in the well-trodden path and lets the Redpanda support docs apply verbatim. ^p031

Bind-mount ownership: the compose-level spec is `./data/redpanda:/var/lib/redpanda/data` and `./config/redpanda/.bootstrap.yaml:/etc/redpanda/.bootstrap.yaml:ro`. The container as UID 101 needs write access to `./data/redpanda` on the host side. Two workable options: ^p032

- **Option A — chown the host dir to UID 101 before first `docker compose up`.** `scripts/up.sh` runs `mkdir -p ./data/redpanda && sudo chown -R 101:101 ./data/redpanda` as part of the bring-up tier that creates bind-mount parents. Matches the convention `./data/<service>/` already documented in [[.claude/context/operations.md]] §Volumes and works with any subsequent `make nuke && scripts/up.sh` cycle. This is the recommended path.
- **Option B — run the container as root via `user: "0:0"` in the compose service.** Bypasses the ownership issue entirely but discards the image's security posture (container runs as a privileged UID that can write anywhere a volume exposes). Not recommended. Stated only for completeness. ^p033

The redpanda#12717 thread flags a historical problem with running the image as an arbitrary UID on OpenShift-style platforms; that specific concern does not affect docker-compose on a Linux host where we control UIDs. `chown 101:101` on the host is the standard answer. Document this in the bring-up script comments and in `docs/runbooks/redpanda.md`'s "first-boot ownership" section. ^p034

There is no Postgres-style "strict mode" complaint about bind-mount permissions on Redpanda's data directory — the entrypoint will refuse to start if it can't write, but it won't refuse to start over a slightly-too-permissive mode. 0755 or 0700 both work at this level; prefer 0700 (matches Redpanda's own directory mode after first init) for tidiness. ^p035

### Healthcheck — `curl /v1/status/ready` against the admin API ^p036

The admin API exposes **`GET /v1/status/ready`** on port 9644 as the per-broker readiness probe. Returns 200 with a JSON body `{"status": "ready"}` when the broker has finished initializing and is accepting Kafka traffic; returns non-2xx or times out when not yet ready. This is the endpoint Kubernetes readiness probes target in the Helm chart's current guidance and is what Docker healthchecks should use. ^p037

The common alternative — `rpk cluster health --exit-when-healthy` as the healthcheck command — is explicitly called out in redpanda-data/helm-charts#1002 as **inappropriate for a per-node probe**. The critique: cluster health reflects the state of the cluster, not of the individual broker, so a perfectly-healthy individual broker can be marked unhealthy because a different broker is down, and a stuck local broker can be masked by a healthy peer. For our single-broker deployment the distinction is less sharp (one broker *is* the cluster), but anchoring the healthcheck on the designed per-node readiness endpoint is still the right call: it survives any future migration to a multi-broker topology without behavioral regression, and it is a plain HTTP probe with no rpk-binary dependency in the healthcheck path. ^p038

Canonical stanza for the compose service: ^p039

```yaml
healthcheck:
  test: ["CMD-SHELL", "curl -sf http://localhost:9644/v1/status/ready || exit 1"]
  interval: 10s
  timeout: 5s
  retries: 10
  start_period: 30s
```

Notes on the field choices. `curl` is present in the `redpandadata/redpanda` image (v26.x Debian-base image, confirmed by checking the labs examples that use `curl` in readiness contexts). `CMD-SHELL` — not `CMD` — is used so the `|| exit 1` wire fires and so future interpolation of any env var in the URL (say, a future TLS `https://` switch) works without redoing the argv form. `-sf` makes curl silent and exit-nonzero on HTTP >= 400. `interval: 10s` is the default balance for Prometheus-scrape responsiveness vs noise. `start_period: 30s` covers the cold-boot seastar-init + first-boot bootstrap.yaml application window; a warm restart converges much faster but `start_period` is only consulted before the first "healthy" observation. `retries: 10` at a 10 s interval gives operators ~100 s of soft-fail visibility before a downstream `depends_on: service_healthy` flips. ^p040

### Ports — 9092 on Kafka API, 9644 on admin API, nothing else ^p041

Atmosphere publishes exactly two ports from the Redpanda container to the host per [[.claude/context/operations.md]] §Host ports: **9092** (Kafka) and **9644** (admin). The labs examples use the dual-listener pattern (`internal://` + `external://`) with different internal and external ports because they are provisioning for clients inside the docker network *and* clients on the host simultaneously — we also have both client types (Flink/Sleuth/Oracle inside the compose network, `rpk` on the host for ad-hoc inspection) so the dual-listener pattern applies. ^p042

The dual-listener trick in the labs example uses distinct port numbers for internal (`9092` / `8082` / `8081` / `9644`) and external (`19092` / `18082` / `18081` / `19644`), then maps only the external ports out to the host. For Atmosphere we do not need separate port numbers — the port map on the host is already documented as 9092 and 9644 (not 19092 / 19644), and the design doc does not introduce a port-shifted external listener. Simplest shape: one listener per protocol, advertise it as `redpanda:<port>` on the internal docker network (compose service name "redpanda"), and bind the same port to the host. Kafka clients inside and outside the network both resolve `redpanda:9092` (or `localhost:9092`) to the same broker. ^p043

Concrete flags: ^p044

```
--kafka-addr 0.0.0.0:9092
--advertise-kafka-addr redpanda:9092
--rpc-addr redpanda:33145
--advertise-rpc-addr redpanda:33145
```

`--advertise-kafka-addr redpanda:9092` is what the broker tells Kafka clients to use in cluster-metadata responses; `redpanda` is the compose service name, DNS-resolvable on the default bridge network. Clients on the host machine adding `127.0.0.1 redpanda` to `/etc/hosts` (or using `rpk -X brokers=localhost:9092` with a broker metadata override) can reach the same broker through the exposed host port. For M1 we don't need anything fancier; if M4's ad-hoc `rpk` usage from the host needs broker resolution, document the `/etc/hosts` trick in `docs/runbooks/redpanda.md`. ^p045

The `--rpc-addr` flag is load-bearing even on a single-node deployment — Redpanda's internal replication and Raft transport use the RPC listener. Bind it to the compose-service name so it has a stable advertise address that survives restarts. Do not expose 33145 to the host; it is compose-network-internal only. ^p046

### Compression is off at broker level — nothing to configure ^p047

[[.claude/context/components/redpanda.md]] specifies "broker-level compression is off." Redpanda's default `log_compression_type` cluster property is `producer` — it uses whatever compression the producer sent, which from Spout (producer idempotence off, no explicit compression-codec set) is `none`. The broker does not re-compress segments. No action required: broker-off-compression is the default, and no `.bootstrap.yaml` override is needed. Confirm by leaving `log_compression_type` alone in `.bootstrap.yaml`. ^p048

### No tiered storage, replication factor 1 implicitly ^p049

Topic creation (M4 territory) will specify `replication.factor=1` per-topic. At broker bootstrap there is no cluster-wide default to set — Redpanda's `default_topic_replication` cluster property defaults to `1` and stays `1` unless we override it. Tiered storage is off by default; enabling would require `cloud_storage_enabled: true` in `.bootstrap.yaml` and credentials, which we do not set. No action required. ^p050

### Canonical compose service definition ^p051

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

Notes: ^p052

- **No `--mode` flag** — falls back to the production-shaped default (fsync on, developer_mode false, overprovisioned explicitly set by the separate flag we pass).
- **No `--schema-registry-addr`, no `--pandaproxy-addr`** — the two subsystems never start, ports 8081 and 8082 are never bound, Flink JM's 8081 is unambiguous.
- **No `--node-id 0`** — redpanda assigns itself node id 0 on first boot when it's the only broker forming the cluster. Setting it explicitly is harmless but unnecessary at this shape. Left out for minimalism.
- **The admin API bind is implicit** — `rpk redpanda start` binds the admin API to `0.0.0.0:9644` by default when no `--advertise-rpc-addr` overlap forbids it. No `--admin-addr` flag is needed for our shape; omitting it keeps the flag list shorter. If a future change needs an admin-API-only internal listener (e.g., TLS termination), adding `--admin-addr 0.0.0.0:9644` spelled explicitly is the obvious path.
- **Soft memory reservation 1.5 GB** matches the `--memory` Seastar flag so docker and Seastar agree on the envelope.
- **`restart: unless-stopped`** — standard for a broker we want to self-heal after host reboot but that `docker compose down` should honor. ^p053

### `.env` keys to add ^p054

Redpanda in this shape does not require any secrets — no TLS certs, no SASL credentials, no admin password. The sole `.env` touch is the already-present `COMPOSE_PROJECT_NAME=atmosphere` (committed in the Postgres research note for M1). No new keys. ^p055

### Gotchas ^p056

- **`--mode dev-container` is a silent fsync-off footgun.** The labs docker-compose-labs examples use it because they are dev-loop-oriented. Copying the labs YAML verbatim into a compose file intended for real-ish use (anything beyond a laptop) is the single most likely way to lose data on a host crash. Explicitly avoid it; omit the `--mode` flag and set `--overprovisioned` as its own argument. ^p057
- **`.sql`-style `.bootstrap.yaml` is a one-shot at first cluster boot.** Editing the file after first boot does nothing; a `docker compose restart redpanda` will not re-apply. Recovery is `docker compose down redpanda`, `docker volume / bind-mount wipe`, `docker compose up -d redpanda` — at which point the new `.bootstrap.yaml` is read. For cluster-property changes on a live broker, use `rpk cluster config set` / `rpk cluster config import`. Document this cliff in `docs/runbooks/redpanda.md` under "first-boot-only" so a future operator editing the file is not surprised. ^p058
- **`CMD` vs `CMD-SHELL` in the healthcheck.** Same footgun as Postgres. `test: ["CMD", "curl", "-sf", "http://localhost:9644/v1/status/ready"]` works as long as `curl` is on PATH, but loses the `|| exit 1` pattern and future env-var interpolation. Prefer `CMD-SHELL`. ^p059
- **`--memory` and `mem_reservation` must agree.** If compose is configured to soft-reserve 1.5 GB and `--memory=4G` is passed to Seastar, Seastar will allocate 4 GB and over-commit the reservation — on a tight host the OOM killer becomes the governor instead of compose's scheduling. Keep them aligned as `1536M` and `1.5g`. ^p060
- **`--reserve-memory` default is not zero.** Forgetting to pass `--reserve-memory=0M` in a small-envelope container means Seastar sets aside a default amount (~1.5 GB historically) *on top of* `--memory`, so a 1.5 GB container effectively asks for 3 GB of address space and the broker will not start. Setting `--reserve-memory=0M` is the containerization-specific override. ^p061
- **Kafka listener name sensitivity.** Redpanda's Kafka listener framework uses listener "names" when multiple listeners are defined (the `internal://` / `external://` labels in the labs examples). With one listener we omit the name (just `0.0.0.0:9092`). Adding a second listener later without also adding names breaks the config — so if a future M-plan adds a TLS-terminated external listener, do it by adding names to both the existing and the new listener in one commit. ^p062
- **Redpanda on bind mounts wants UID 101 ownership; on named docker volumes it self-chowns.** Bind mounts don't get the self-chown. The pre-up `sudo chown -R 101:101 ./data/redpanda` step is load-bearing; skipping it yields a "data directory is not writable" error on first boot. Not unique to Redpanda — every image that runs as a non-root user on a host-bind mount has this shape — but worth flagging since the error message isn't obvious. ^p063
- **Admin-API 9644 binds 0.0.0.0 by default.** On a host with 9644 exposed (we do expose it per the port map), this means anything on the host's network can hit the admin API unauthenticated. Atmosphere's single-trust-domain posture already accepts this for the compose-network-internal side; the host-exposed side relies on the host's firewall. This matches the posture already taken for Lakekeeper, SeaweedFS S3, and every other admin surface — worth noting once in the runbook so a future "should we lock this down?" ticket has context. ^p064
- **Seastar stack overrun on very small `--memory` values.** `--memory=512M` has been observed to produce startup seastar-allocator errors on v26.x because internal datastructures fit poorly. 1 GB is a safe practical floor; 1.5 GB is comfortable. Do not compress to <1 GB even if the platform envelope tightens later — that is the wrong knob to turn. ^p065
- **Console is a separate service we do not need.** The labs example bundles `docker.redpanda.com/redpandadata/console:v3.7.1`. We do not deploy Console — `rpk` on the host covers ad-hoc inspection, and Grafana-over-Prometheus covers operational visibility. Leaving Console out saves ~400 MB of image pull and ~200 MB of runtime reservation. ^p066

### What this note deliberately does not adopt ^p067

- **`--mode dev-container`** — fsync-off footgun as described above. Use default mode + explicit `--overprovisioned`. ^p068
- **Dual-port external-vs-internal listener scheme** — the 19092 / 18081 / 18082 / 19644 shift pattern in the labs example exists to demonstrate dual listeners to readers who are running Console and a host-side producer simultaneously. Atmosphere's single-listener shape on matching host and container ports is simpler, matches [[.claude/context/components/redpanda.md]]'s port map, and is what compose projects that don't run Console typically use. ^p069
- **Schema registry + pandaproxy** — explicitly not deployed. No schema registry per [[.claude/context/components/redpanda.md]] §Schema handling; pandaproxy has no consumer. Omit the two `--*-addr` flags. ^p070
- **Console** — not deployed (§p066). ^p071
- **`--set redpanda.storage_min_free_bytes=...`** — `storage_min_free_bytes` is a cluster property, not a node property; use `.bootstrap.yaml` (§p019). ^p072
- **`rpk cluster config set storage_min_free_bytes=...` as a post-start step** — works but requires a hook compose doesn't cleanly provide and leaves a write-window before the hard limit is in place. `.bootstrap.yaml` is the right-shape primitive. ^p073
- **`rpk cluster health --exit-when-healthy` as the healthcheck** — wrong-abstraction probe per helm-charts#1002. Use `GET /v1/status/ready`. ^p074
- **Tiered storage, rack awareness, SASL, mTLS, ACLs** — none in scope for M1. Revisit if/when a downstream requirement surfaces. ^p075

### Summary of choices ^p076

- **Image tag:** `docker.redpanda.com/redpandadata/redpanda:v26.1.6` (Redpanda-run registry; full-version pin).
- **Command flags:** `redpanda start --kafka-addr=0.0.0.0:9092 --advertise-kafka-addr=redpanda:9092 --rpc-addr=redpanda:33145 --advertise-rpc-addr=redpanda:33145 --smp=1 --memory=1536M --reserve-memory=0M --overprovisioned --default-log-level=info`. No `--mode`, no schema-registry-addr, no pandaproxy-addr.
- **Ports:** `9092:9092` (Kafka), `9644:9644` (admin). Nothing else on the host.
- **Data mount:** `./data/redpanda:/var/lib/redpanda/data`, owned `101:101` on the host.
- **Config mount:** `./config/redpanda/.bootstrap.yaml:/etc/redpanda/.bootstrap.yaml:ro`.
- **.bootstrap.yaml contents:** `storage_min_free_bytes: 2147483648`.
- **Healthcheck:** `CMD-SHELL curl -sf http://localhost:9644/v1/status/ready || exit 1`, 10 s interval, 5 s timeout, 10 retries, 30 s start_period.
- **Soft memory reservation:** 1.5 GB, matching `--memory=1536M`. No hard cap.
- **No `.env` additions** — Redpanda at this shape has no secrets.

^p077

### Sources ^p078

- Redpanda single-broker labs docker-compose example: https://docs.redpanda.com/redpanda-labs/docker-compose/single-broker/
- Redpanda Docker Compose labs index: https://docs.redpanda.com/current/get-started/docker-compose-labs/
- `rpk redpanda start` flag reference: https://docs.redpanda.com/current/reference/rpk/rpk-redpanda/rpk-redpanda-start/
- `rpk redpanda mode` (development / production / recovery): https://docs.redpanda.com/current/reference/rpk/rpk-redpanda/rpk-redpanda-mode/
- Redpanda production deployment guide (`.bootstrap.yaml` documented here): https://docs.redpanda.com/current/deploy/deployment-option/self-hosted/manual/production/production-deployment/
- Configure cluster properties: https://docs.redpanda.com/current/manage/cluster-maintenance/cluster-property-configuration/
- Manage disk space (storage_min_free_bytes semantics and default): https://docs.redpanda.com/current/manage/cluster-maintenance/disk-utilization/
- Cluster configuration properties reference: https://docs.redpanda.com/current/reference/properties/cluster-properties/
- Redpanda admin API reference (index): https://docs.redpanda.com/api/doc/admin/
- Redpanda admin API — ready endpoint: https://docs.redpanda.com/api/doc/admin/operation/operation-ready/
- Redpanda release notes / self-managed versions: https://docs.redpanda.com/current/reference/releases/
- redpanda-data/helm-charts#1002 (rpk-cluster-health as probe critique): https://github.com/redpanda-data/helm-charts/issues/1002
- redpanda-data/redpanda#12717 (container UID 101 / OpenShift arbitrary-UID request): https://github.com/redpanda-data/redpanda/issues/12717
- redpanda-data/redpanda discussion #6851 (`--set redpanda.*` usage pattern): https://github.com/redpanda-data/redpanda/discussions/6851
- `redpandadata/redpanda` Docker Hub page: https://hub.docker.com/r/redpandadata/redpanda
