---
id: seaweedfs-single-container-compose-2026
type: research
name: SeaweedFS single-container compose pattern — master + volume + filer + S3 gateway (M1 / JDL-66)
created_at: 2026-04-24
created_by: scout
component: seaweedfs
---

## Purpose

Pin down the 2026-canonical shape of Atmosphere's M1 SeaweedFS compose service: which `chrislusf/seaweedfs` tag to pin, whether to use `weed mini` or `weed server -s3 -filer`, the exact CLI argument set for all four roles in one process with replication off and all state under `/data`, the idiomatic static-credentials path (env vars vs `-s3.config` JSON), the healthcheck shape against `/cluster/status`, and the idiomatic idempotent mechanism for creating the three required buckets (`atmosphere`, `flink`, `loki`) on fresh bring-up. Ground everything in the official SeaweedFS wiki and the upstream repo rather than blog posts.

## Entry — initial — 2026-04-24 — scout

**agent:** scout
**refs:** [[.claude/context/components/iceberg.md]] (§SeaweedFS topology), [[.claude/context/operations.md]] (§Volumes and storage, §Secrets and configuration), [[.claude/context/roadmap.md]] (M1), SeaweedFS wiki `Getting-Started`, `Quick-Start-with-weed-mini`, `S3-Credentials`, `Master-Server-API`, `Replication`; `seaweedfs/seaweedfs/blob/master/weed/command/server.go`; `chrislusf/seaweedfs` Docker Hub tags page; `seaweedfs/seaweedfs` GitHub releases; discussions #2461, #4739, #7599; issues #6542, #8243.

### Image tag — pin to `chrislusf/seaweedfs:4.21` ^p001

The `chrislusf/seaweedfs` repo tags by semver at each release (current-stable track), and upstream has been cutting a release roughly every week on the 4.x line. As of 2026-04-24 the most recent four tags are `4.21` (2026-04-19), `4.20` (2026-04-13), `4.19` (2026-04-08), and `4.18` (2026-04-02). Pointers `latest`, `latest_large_disk`, and `dev` also exist and re-point on every release — `latest` currently tracks `4.21` and `dev` tracks the upstream master branch several times a day. Pin to `4.21` rather than `latest` for the same reason every other Atmosphere service pins by exact version: a docker-daemon pull at an arbitrary future moment should not silently upgrade a cluster-metadata-bearing container to whatever the upstream master branch contains. The `_large_disk`, `_full`, `_rocksdb`, and `_foundationdb` suffix variants are for specialized volume-format / filer-backend builds we do not need — stick with the plain `4.21`. ^p002

### `weed server -s3 -filer`, not `weed mini` ^p003

Both modes exist for the "all four roles in one process" use case but they carry different support guarantees. `weed mini` is explicitly documented on the wiki page [Quick-Start-with-weed-mini](https://github.com/seaweedfs/seaweedfs/wiki/Quick-Start-with-weed-mini) as "designed for learning, development, and testing only. It may not guarantee backward compatibility between versions." `weed server` with the `-filer` and `-s3` sub-service flags is the production-supported shape and has been stable across the 3.x and 4.x release lines. Atmosphere is a single-host deployment and consciously trades HA for operational simplicity (RF=000, single container for all four roles), but it is not a "learning" deployment — the data passing through is append-only Iceberg bronze that is recoverable from Jetstream replay within 24 hours, which means a format-compatibility break on a `weed mini` upgrade would be recoverable but disruptive. `weed server -s3 -filer` is the correct pick; the "components run in one OS process" property is identical across both modes at runtime, so we lose nothing in simplicity by choosing the stable flag surface. ^p004

### Canonical compose service ^p005

```yaml
services:
  seaweedfs:
    image: chrislusf/seaweedfs:4.21
    container_name: seaweedfs
    command:
      - server
      - -dir=/data
      - -master.port=9333
      - -master.defaultReplication=000
      - -volume.port=8080
      - -volume.max=0
      - -filer=true
      - -filer.port=8888
      - -s3=true
      - -s3.port=8333
      - -s3.config=/etc/seaweedfs/s3.json
      - -metricsPort=9327
    environment:
      WEED_CLUSTER_DEFAULT_REPLICATION: "000"
    ports:
      - "9333:9333"   # master HTTP
      - "8080:8080"   # volume HTTP
      - "8888:8888"   # filer HTTP
      - "8333:8333"   # S3 gateway
      - "9327:9327"   # Prometheus /metrics
    volumes:
      - ./data/seaweedfs:/data
      - ./config/seaweedfs/s3.json:/etc/seaweedfs/s3.json:ro
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:9333/cluster/status"]
      interval: 10s
      timeout: 5s
      retries: 6
      start_period: 20s
    mem_reservation: 1g
    restart: unless-stopped
```

Every flag on that command list is resolved from `weed/command/server.go` in the upstream repo — the defaults for master/volume/filer/S3 ports on `weed server` are exactly 9333/8080/8888/8333 (matching what [[.claude/context/operations.md]] §Host ports specifies), so most of the `*.port` flags are redundant; they are listed explicitly for self-documenting review. `-dir=/data` is the single flag that roots master metadata, volume data files (the `.dat`/`.idx` files), and the filer's default leveldb-backed metadata store all under one directory, which is exactly what lets the single `./data/seaweedfs:/data` bind mount capture every piece of state. ^p006

### Replication off: two knobs, both needed ^p007

SeaweedFS replication policies are three-digit strings `DRC` where D = data centers, R = racks across DCs, C = servers within a rack. `000` means "no replication, just store one copy" (wiki page [Replication](https://github.com/seaweedfs/seaweedfs/wiki/Replication)). The default-replication setting is owned by the master and lives at `-master.defaultReplication=000` on the `weed server` flag surface. The master also honors an environment-variable override, `WEED_CLUSTER_DEFAULT_REPLICATION=000`, which some deployment shapes (Helm chart, a few community docker-compose examples) use instead of the CLI flag. Setting both is idempotent and belt-and-suspenders — the CLI flag is the declarative source of truth and the env var defends against a future `weed server` release that demotes the flag default. For the client-write side there is nothing to set: with `defaultReplication=000` at the master, new volumes are created with policy `000` and all subsequent writes (including those that traverse the filer and S3 gateway) inherit it without per-client configuration. No `-volume.defaultReplication` flag exists — replication is master-governed, not volume-governed. ^p008

### S3 static credentials: use `-s3.config`, not env vars ^p009

SeaweedFS supports two paths for static S3 credentials: a JSON config file passed via `-s3.config=/path/to/s3.json`, and the AWS SDK standard `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` env var fallback. The priority order documented on [S3-Credentials](https://github.com/seaweedfs/seaweedfs/wiki/S3-Credentials) is: config file → filer-stored config → Admin UI → environment variables. Environment variables are the lowest-priority lane and are treated as an emergency fallback; the idiomatic path is `-s3.config`. Atmosphere should follow that — one JSON file under `./config/seaweedfs/s3.json`, bind-mounted read-only, consumed by the gateway at start. This also keeps the credentials surface aligned with [[.claude/context/operations.md]] §Secrets and configuration: the actual key/secret *values* still come from the repo root `.env` file (via a small init-time template step or a pre-built rendered copy), but the S3 gateway sees a JSON file, which is the interface SeaweedFS treats as authoritative. ^p010

### `s3.json` shape for Atmosphere ^p011

```json
{
  "identities": [
    {
      "name": "atmosphere",
      "credentials": [
        {
          "accessKey": "${SEAWEEDFS_S3_ACCESS_KEY}",
          "secretKey": "${SEAWEEDFS_S3_SECRET_KEY}"
        }
      ],
      "actions": ["Admin", "Read", "Write", "List", "Tagging"]
    }
  ]
}
```

One identity is sufficient because [[.claude/context/components/lakekeeper.md]] and the other component docs place the whole compose stack inside one trust domain — every Iceberg client (Flink, dbt-duckdb, ClickHouse, Prefect, Elementary, OpenMetadata) uses the same access key / secret pair. The `actions` array uses SeaweedFS's permission vocabulary: global `Admin` grants bucket-create and bucket-delete (which the init job needs — see p014), and `Read`/`Write`/`List`/`Tagging` cover everything the Iceberg clients do at runtime. Resources can be scoped per bucket (`"Read:atmosphere/*"`) but there is no reason to do so at M1. Reload semantics: changes to the JSON file require a SIGHUP to the gateway process or a container restart; there is no auto-reload on file mtime for the config-file path (filer-stored config does auto-reload, but we are not using that path). ^p012

### Watch out: the one-time allow-all lock-in ^p013

Discussion #4739 and the S3-Credentials wiki call out an important footgun: if the gateway is ever started *without* any credentials, it runs in "allow all" mode and stays there; adding an identity later "will automatically and permanently transition" the server to requiring authentication — but only after a restart, and only if the config file / filer config is picked up cleanly. This is unlikely to bite Atmosphere because `-s3.config` is set on the first boot, but the operational consequence is: never run an "empty first boot" to smoke-test the service and then add credentials after the fact. Always start with `s3.json` present. ^p014

### Bucket creation: one-shot init container using `weed shell` ^p015

There are three options documented in upstream discussions for pre-creating buckets, with distinct tradeoffs:

1. **Lazy creation via S3 `CreateBucket`** — the S3 API handler does support `CreateBucket` (issue #5509 confirms this), so `aws --endpoint-url=http://seaweedfs:8333 s3 mb s3://atmosphere` works and is inherently idempotent (a second call returns `BucketAlreadyOwnedByYou` / HTTP 409 which the AWS CLI treats as a no-op with `--no-cli-pager` and exit 254 otherwise; wrap with `|| true` or a `head-bucket` pre-check). This is the *most portable* path — it works against any S3-compatible endpoint and does not depend on SeaweedFS internals. But it requires the S3 gateway and filer to both be healthy before it can run.
2. **`weed shell` with `s3.bucket.create -name <bucket>`** — runs against the master's admin port and creates the bucket directly under the filer's `/buckets` prefix (discussion #2461). Idempotent by design (second call is a no-op); requires the master to be up but does not strictly require the S3 gateway to be ready. Runs inside the existing seaweedfs image, so no extra container image needed.
3. **`create-bucket-hook`** — a newer SeaweedFS feature (discussion #7599, PR #7728 landed December 2025) that creates buckets declaratively at master startup via a hook config. Still under refinement in early 2026 (the #7599 thread notes buckets created via the hook behave slightly differently from lazy-created buckets until #7728's fix); not worth taking this as the canonical path at M1 when the older `weed shell` approach is rock-solid.

Pick option 2 for the init path. It has the tightest coupling to SeaweedFS's supported surface, it is idempotent without extra wrapping, it runs inside the same image we already pinned (no extra image to track), and it does not require waiting for the full S3 gateway boot — only the master. Option 1 is fine as a fallback for debugging / manual operator work. ^p016

### Init container shape ^p017

```yaml
  seaweedfs-init:
    image: chrislusf/seaweedfs:4.21
    depends_on:
      seaweedfs:
        condition: service_healthy
    entrypoint: ["/bin/sh", "-c"]
    command:
      - |
        for bucket in atmosphere flink loki; do
          echo "s3.bucket.create -name ${bucket}"
        done | weed shell -master=seaweedfs:9333
    restart: "no"
```

`s3.bucket.create` is idempotent by SeaweedFS design — a second create against an existing bucket returns success — so re-running the init container on every `docker compose up -d` is harmless. `depends_on` with `service_healthy` ensures the init only fires after the `/cluster/status` healthcheck goes green, which means the master is serving Raft state and the filer has registered. `restart: "no"` keeps the init from loop-restarting after a successful exit; a failed exit surfaces as a one-shot failure for the operator to investigate rather than silently retrying. `weed shell` connects to the master's admin surface on the bridge network by compose service name, not on a host-published port, so no extra port exposure is needed. ^p018

### Healthcheck against `/cluster/status` ^p019

The master HTTP API exposes `/cluster/status` (wiki page [Master-Server-API](https://github.com/seaweedfs/seaweedfs/wiki/Master-Server-API)) and returns a small JSON document `{"IsLeader": true, "Leader": "<host>:<port>", "Peers": [...]}`. For a single-master deployment, `IsLeader: true` and an empty `Peers` list is the healthy steady state. Health-check-wise we do not need to parse the JSON — we just need confirmation that the master HTTP listener is up, which is what `wget --spider -q` checks (HEAD request, exit 0 on 2xx/3xx response, exit >0 on network or 4xx/5xx). The SeaweedFS image is Alpine-based and includes `curl` but *not* `wget` explicitly — however, Alpine's BusyBox shell provides `wget` as a builtin applet (with `--spider` support), so `wget --spider` works without adding packages. Using `wget --spider` keeps the healthcheck identical to what the upstream compose examples use and makes the test shorter than the equivalent `curl -fsS -o /dev/null` form. ^p020

The `start_period: 20s` allows for the initial boot sequence (master election is effectively instant on a single node, but the filer does a small amount of schema bootstrap on first boot when `/data` is empty, and the S3 gateway does a short "wait to connect to filer" loop — discussion #2461 measured this at ~5 seconds on a warm filer and up to ~25s on cold start with a fully-initializing filer). 20s start-period leaves room for the cold case without slowing the warm path. `interval: 10s / timeout: 5s / retries: 6` gives the service a full minute of health-probe budget before being declared unhealthy, which is generous but matches the [[.claude/context/operations.md]] §Startup ordering tiered-bring-up expectation that downstream services can tolerate a short SeaweedFS stall. ^p021

### S3 gateway startup-order caveat inside one process ^p022

Inside `weed server -s3 -filer`, the four sub-services are started sequentially by the single Go binary: master first (so it can hand out the initial Raft state), then volume (registers with master), then filer (registers with master, stores its metadata on the volume layer), then S3 (connects to the filer). `depends_on` within the container is moot — they all start in the same process — but there is a visible "wait to connect to filer" delay in the S3 gateway's startup log until the filer finishes binding. The consequence for Atmosphere is that an S3 client (including the init container using `aws s3 mb`) can get "connection refused" on port 8333 for several seconds even after the `/cluster/status` healthcheck on 9333 goes green. Using `weed shell -master=seaweedfs:9333` for the init path — as proposed in p017 — sidesteps this entirely because `weed shell` talks to the master, not the S3 gateway. If someone reaches for the portable `aws s3 mb` path in a future hot-reload context, add a small retry loop or a secondary TCP healthcheck on 8333. ^p023

### `./data/seaweedfs` ownership and permissions ^p024

The SeaweedFS Alpine image runs the server binary as a `seaweed` user created in the Dockerfile at UID 1000 / GID 1000. A fresh bind mount `./data/seaweedfs` created by `docker compose up` with default host settings will be owned by root (UID 0) unless the host creates it first with matching ownership — which causes the first `weed server` boot to fail with a permission-denied error trying to create `/data/master` or `/data/filerldb2`. Two clean resolutions, in order of preference:

1. **Pre-create the directory on the host with matching UID/GID.** Put this in `scripts/up.sh` as part of M1's bring-up: `mkdir -p data/seaweedfs && sudo chown -R 1000:1000 data/seaweedfs` (or for rootless Docker, `chown $(id -u):$(id -g) data/seaweedfs`, which works because rootless mapping lines up host UID to the container's UID 0/1000 via `/etc/subuid`). This matches the pattern [[.claude/context/operations.md]] already uses for Postgres (where the named-volume path sidesteps the permission problem entirely on a docker-managed path).
2. **Run the container as root.** Add `user: "0:0"` to the compose service. Simpler one-liner, but the image's internal `USER seaweed` line exists for good reason — root in a long-lived storage container is mildly unidiomatic — and changing user ownership on every bring-up is cheaper than the operational cost of eventual file-ownership confusion.

Pick option 1 and document it in `docs/backups.md` alongside the bind-mount enumeration — matches the solo-operator posture of M1 and keeps the `./data/seaweedfs` tree's on-host permissions legible. ^p025

### Metrics ^p026

`-metricsPort=9327` exposes a Prometheus endpoint covering master, volume, filer, and S3 gateway subsystems — this is the *single* Prometheus endpoint [[.claude/context/components/iceberg.md]] §Metrics references for SeaweedFS. Key metric families: `SeaweedFS_master_*` (Raft state, volume count), `SeaweedFS_volume_*` (disk usage per volume, file count), `SeaweedFS_filer_*` (request latency, metadata op count), `SeaweedFS_s3_*` (per-bucket request rate, request duration percentiles). The design-doc sentence "SeaweedFS runs as a single container exposing one Prometheus endpoint covering master, volume, and filer subsystems" is exactly this — `-metricsPort=9327` on a single `weed server` process covers all of them. Prometheus scrapes by compose service name on the bridge network (`seaweedfs:9327`); the host port binding `9327:9327` in p005 is optional and useful only for host-side `curl` during setup, not for Prometheus scraping. ^p027

### Summary of decisions for M1 implementation ^p028

- Image: `chrislusf/seaweedfs:4.21` pinned by exact tag.
- Command: `weed server -dir=/data -filer -s3 -s3.config=/etc/seaweedfs/s3.json -master.defaultReplication=000 -metricsPort=9327` (other port flags redundant with defaults; list them for review clarity).
- Env override: `WEED_CLUSTER_DEFAULT_REPLICATION=000` as defense-in-depth.
- Credentials: single identity in `./config/seaweedfs/s3.json` with full `Admin/Read/Write/List/Tagging` actions, access/secret from `.env`.
- State: one bind mount `./data/seaweedfs:/data`, pre-chowned to 1000:1000 on the host by `scripts/up.sh`.
- Healthcheck: `wget --spider -q http://localhost:9333/cluster/status`, 10s/5s/6-retry/20s-start-period.
- Bucket init: `seaweedfs-init` one-shot container running `weed shell -master=seaweedfs:9333` with `s3.bucket.create -name <bucket>` per bucket (`atmosphere`, `flink`, `loki`), idempotent by SeaweedFS design, gated on `service_healthy`.
- Ports on host: 9333 (master HTTP), 8080 (volume HTTP), 8888 (filer HTTP), 8333 (S3), 9327 (Prometheus `/metrics`) — matches [[.claude/context/operations.md]] §Host ports exactly.

### Sources ^p029

- SeaweedFS Getting Started wiki: https://github.com/seaweedfs/seaweedfs/wiki/Getting-Started
- SeaweedFS Quick Start with weed mini wiki: https://github.com/seaweedfs/seaweedfs/wiki/Quick-Start-with-weed-mini
- SeaweedFS S3 Credentials wiki: https://github.com/seaweedfs/seaweedfs/wiki/S3-Credentials
- SeaweedFS Replication wiki: https://github.com/seaweedfs/seaweedfs/wiki/Replication
- SeaweedFS Master Server API wiki: https://github.com/seaweedfs/seaweedfs/wiki/Master-Server-API
- `weed/command/server.go` flag surface: https://github.com/seaweedfs/seaweedfs/blob/master/weed/command/server.go
- Upstream docker compose example: https://github.com/seaweedfs/seaweedfs/blob/master/docker/seaweedfs-compose.yml
- Discussion #2461 (bucket creation at startup): https://github.com/seaweedfs/seaweedfs/discussions/2461
- Discussion #4739 (static s3 config behavior): https://github.com/seaweedfs/seaweedfs/discussions/4739
- Discussion #7599 (create-bucket-hook): https://github.com/seaweedfs/seaweedfs/discussions/7599
- Issue #8243 (S3 healthcheck endpoint routing): https://github.com/seaweedfs/seaweedfs/issues/8243
- Issue #5509 (S3 CreateBucket support): https://github.com/seaweedfs/seaweedfs/issues/5509
- Docker Hub tags: https://hub.docker.com/r/chrislusf/seaweedfs/tags
- GitHub releases: https://github.com/seaweedfs/seaweedfs/releases
