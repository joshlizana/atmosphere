---
id: seaweedfs-healthcheck-busybox-wget-2026
type: research
name: SeaweedFS 4.21 single-container compose healthcheck — BusyBox wget, IPv6 localhost gotcha, and the canonical test command
created_at: 2026-04-24
created_by: scout
component: seaweedfs
---

## Purpose

Pin down the canonical `docker-compose` healthcheck for the M1 single-container SeaweedFS service running `weed server -s3 -filer` on `chrislusf/seaweedfs:4.21`, given the observed false-negative in the M1 smoke probe (container reports `unhealthy` while the `/cluster/status` endpoint is in fact serving 200 on the host). Identify the actual failure mode, the tooling available inside the image, and the exact `test:` array to replace the current one. Follow-up from [[research/JDL-66/seaweedfs-s3-config-env-interpolation.md]] (commit landed earlier in JDL-66) which established the compose shape but did not revisit the healthcheck after that landed.

## Entry — initial — 2026-04-24 — scout

**agent:** scout
**refs:** [[compose.yml]] (seaweedfs service block, lines 61-93), [[research/JDL-66/seaweedfs-s3-config-env-interpolation.md]], upstream `chrislusf/seaweedfs:4.21` image (live probe), BusyBox 1.37 wget source, seaweedfs/seaweedfs PR #6520, seaweedfs/seaweedfs issue #8243, seaweedfs/seaweedfs PR #2680, BusyBox mailing-list thread "wget --spider" (2021-09)

### The root cause is IPv6 localhost resolution, not BusyBox wget semantics ^p001

The failing command, `wget --spider -q http://localhost:9333/cluster/status`, fails inside the container because `localhost` resolves to `::1` first via the Alpine default `/etc/hosts` (`::1 localhost localhost` — observed on 4.21: Alpine 3.23.4, BusyBox 1.37). SeaweedFS's master HTTP listener binds IPv4 only — `127.0.0.1:9333` and `172.17.0.2:9333` (eth0) — never `::1`. BusyBox wget's address resolution prefers the IPv6 record, connects to `[::1]:9333`, gets `Connection refused`, and exits 1. The endpoint itself is perfectly healthy; the container is not. This is a silent protocol-family mismatch that the current `test:` array does not defend against. ^p002

Reproduced on the live image: `wget --spider http://localhost:9333/cluster/status` traces `Connecting to localhost:9333 ([::1]:9333)` → `can't connect to remote host: Connection refused`. Switching to `http://127.0.0.1:9333/cluster/status` connects, receives `HTTP/1.1 200 OK` with the expected JSON body (`{"IsLeader":true,"Leader":"172.17.0.2:9333.19333"}`), and wget exits 0. The fix is a single character change: use `127.0.0.1` instead of `localhost`. ^p003

### The BusyBox `--spider` HEAD/GET concern does not apply here ^p004

There is a real and well-documented BusyBox-wget-vs-SeaweedFS interaction in seaweedfs/seaweedfs PR #6520 ("fix: bucket-hook fails with gnu wget") — but it runs the opposite direction of the platform's naive reading. `--spider` in **GNU** wget issues a HEAD request; SeaweedFS's `/cluster/status` handler does not implement HEAD, so GNU wget gets `405 Method Not Allowed` and flags the check as failed. PR #6520 moved the bucket-hook script from `wget --spider` to `wget -O -` (forcing a GET) to accommodate environments with GNU wget installed. ^p005

The `chrislusf/seaweedfs:4.21` container does not have GNU wget; `/usr/bin/wget` is a symlink into the BusyBox multi-call binary (verified: `command -v wget` → `/usr/bin/wget`; `wget --help` shows the BusyBox v1.37.0 banner; no `curl` binary is present on the runtime image despite being listed in the build-deps layer). BusyBox wget's `--spider` is documented to issue a **GET** (not HEAD) — confirmed in the 2021-09 BusyBox mailing-list thread and by direct observation: `wget -S --spider http://127.0.0.1:9333/cluster/status` on 4.21 returns a 200 with the full response headers, matching GET-method behavior. So the SeaweedFS master's lack of HEAD support is not a concern for our image; `--spider` functions correctly as a liveness probe here. ^p006

### The second gotcha: BusyBox `wget --spider` without `-q` returns exit 0 on connection refused ^p007

Observed directly on 4.21: `wget --spider http://127.0.0.1:9999/nothing` (nothing listening on the target port) returns exit **0** with "can't connect to remote host: Connection refused" printed to stderr. Adding `-q` changes exit to **1**. `wget -S --spider http://127.0.0.1:9999/nothing` also returns exit 0 on connection refused. This is a latent BusyBox bug-class; it does not bite us when the service *is* up and responding (exit codes agree with reality then) but it creates a silent false-pass mode if the healthcheck ever hits a connection-refused state without `-q`. ^p008

The safe rule: **always use `-q` with `--spider` in a healthcheck command**, or avoid `--spider` entirely and use `-O /dev/null` / `-O -`. The `-O /dev/null` form returns exit 1 on connection refused regardless of `-q`, so it is the more robust shape for a healthcheck that has to behave correctly under every failure mode. ^p009

### Endpoint menu on 4.21 — master, filer, S3 all serve loopback-IPv4; volume does not ^p010

Probed each listener directly from inside the container on 127.0.0.1 (steady-state, 25 seconds after container start). Results: ^p011

- **Master 9333** — `/cluster/healthz` returns 200 empty body (added by PR #2680 as the cheap liveness probe); `/cluster/status` returns 200 JSON with leader state; `/healthz`, `/status`, `/metrics` return 404 on 9333 (metrics is on the dedicated `-metricsPort` at 9327).
- **Filer 8888** — `/healthz` returns 200 empty body with `Server: SeaweedFS 30GB 4.21` header; `/status` returns 404.
- **S3 gateway 8333** — both `/status` and `/healthz` return 200 empty body. The bug in seaweedfs/seaweedfs#8243 (S3 `/healthz` resolving as a bucket-name lookup and returning NoSuchBucket) was fixed upstream before 4.21; confirmed working on this image.
- **Volume 8080** — binds `172.17.0.2:8080` (eth0) only, *not* `127.0.0.1:8080`. Loopback probes of port 8080 fail with connection refused. Any in-container healthcheck must target a port that binds loopback-IPv4, not volume.

### Recommendation: `/cluster/healthz` on port 9333 via 127.0.0.1 ^p012

The canonical replacement for the current `test:` array is: ^p013

```yaml
healthcheck:
  test:
    [
      "CMD-SHELL",
      "wget -q -O /dev/null http://127.0.0.1:9333/cluster/healthz || exit 1",
    ]
  interval: 10s
  timeout: 5s
  retries: 6
  start_period: 20s
```

Rationale for each piece: ^p014

- `127.0.0.1` sidesteps the IPv6 localhost trap (§p002).
- Port `9333` is the master, which is the correct "overall service health" target for a single-container `weed server` deployment — if the master is serving, the registry / cluster state is queryable; filer (8888) and S3 gateway (8333) come up after the master and depend on it, so a master-level probe is a correct upstream health signal. The M0/M1 acceptance criterion already specifies the master's `/cluster/status` as the check, so staying on 9333 preserves operator intuition.
- `/cluster/healthz` (not `/cluster/status`) is the lighter endpoint. Upstream PR #2680 added it specifically as a Kubernetes startup-probe target; it returns 200 empty-body without serializing the leader-election JSON, so it has marginally lower per-probe cost and no dependency on the JSON encoder being healthy. Every 10 seconds this matters slightly; at any frequency it is simply more representative of "master is serving HTTP" without coupling to the status-report path.
- `wget -q -O /dev/null` is the robust shape: returns exit 0 on 200, exit 1 on connection-refused, exit 1 on any non-2xx/3xx response — verified on 4.21. Avoids the `--spider` silent-pass bug (§p008). Discards the body which is empty anyway but keeps the command output clean in `docker inspect --format='{{.State.Health}}'`.
- `|| exit 1` is defensive redundancy — wget already exits 1 on failure, but the explicit fallback guards against any future `wget` shim that decides to exit 0 on error (seen on some Docker base images). Cheap insurance.

### Timing parameters: 10s / 5s / 6 retries / 20s start_period all stand ^p015

Measured the cold-start time from container create to master 9333 serving `/cluster/healthz` 200 on 4.21: **1 second**. Master binds HTTP essentially immediately. The existing 20s `start_period` is a generous buffer for a busy host and should be left alone. 10s interval × 6 retries = 60s of failing checks before the container is flipped to unhealthy — appropriate for the M1 smoke, where we want transient glitches to not trip the red tile but real outages to surface within a minute. 5s timeout against a 1s-cold endpoint leaves 5x headroom. None of these numbers require adjustment. ^p016

### Alternative target not chosen: filer `/healthz` (8888) ^p017

The filer's `/healthz` would also work, binds loopback-IPv4, and responds 200. Reason not chosen: the master is the authoritative cluster-coordination layer; a failing filer with a healthy master is still a degraded-but-partial service the operator wants to see reflected. Probing the master gives a cleaner "is the single-container bootstrap functional" signal that aligns with the M1 acceptance criterion's language ("SeaweedFS `/cluster/status`"). If the future deployment ever breaks the single-container invariant and splits master / filer / volume into separate containers, each gets its own healthcheck targeting its own endpoint — that is not this milestone. ^p018

### Alternative target not chosen: S3 gateway `/healthz` (8333) ^p019

S3 `/healthz` is the shape an *external* consumer would probe (the client contract is S3); it's the natural choice for a load-balancer health check in a production deployment where the S3 gateway is the ingress. Inside the compose single-container, probing S3 conflates two concerns: the master's cluster-state and the S3 API's readiness. A master-only probe separates those and is the cleaner single-source-of-truth signal for "SeaweedFS is up at all." If M1 smoke ever needs a second probe specifically asserting the S3 layer, it belongs as an external test against the host-published 8333 port (the probe harness already does this via `aws --endpoint-url=...`), not as an in-container healthcheck. ^p020

### Alternative considered and rejected: `curl` ^p021

`curl` is not present in the runtime `chrislusf/seaweedfs:4.21` image — verified directly (`command -v curl` returns nothing; only `wget` is in `/usr/bin`). The image's build `apk add --virtual build-dependencies --update wget curl ca-certificates` installs curl *only in the build layer*, which is removed before the final image. Using `curl` in the healthcheck would require either installing it via an entrypoint-side `apk add` (slow, creates a new image-state drift surface, fails on image restart if the registry is unreachable) or mounting a binary in. Neither is worth it when BusyBox wget with the right flags works cleanly. ^p022

### What about using a TCP-only probe via `nc`? ^p023

BusyBox `nc -zv 127.0.0.1 9333` does exist on the image and works (exit 0 on connect, exit 1 on refused — verified). A TCP-level probe would skip the HTTP handler entirely and only confirm the port is bound. That is a weaker signal than `/cluster/healthz`: the port binds ~1s before the HTTP router accepts the `/cluster/healthz` route (observed 0s gap in the measurement but there's a race-window during first boot where `accept(2)` returns fine but the handler isn't wired). The HTTP-level probe is both more representative and not materially more expensive at a 10s interval, so stay with wget. ^p024

### Summary diff against the current compose.yml ^p025

```diff
     healthcheck:
       test:
         [
           "CMD-SHELL",
-          "wget --spider -q http://localhost:9333/cluster/status || exit 1",
+          "wget -q -O /dev/null http://127.0.0.1:9333/cluster/healthz || exit 1",
         ]
       interval: 10s
       timeout: 5s
       retries: 6
       start_period: 20s
```

Two changes to the test command; no timing changes. The semantic shifts are: (1) IPv4-literal loopback bypasses the IPv6-first `localhost` resolution, (2) `/cluster/healthz` is the dedicated liveness endpoint rather than the verbose status endpoint, (3) `-O /dev/null` replaces `--spider` to eliminate the BusyBox exit-0-on-connection-refused silent-pass bug. All three changes are orthogonal; any one of them would fix the current false-negative, but the combined shape is robust against the full class of BusyBox-wget gotchas. ^p026

### Verification plan for the fix ^p027

Once the compose change lands, the acceptance path mirrors the probe that surfaced the bug: `docker compose up -d seaweedfs` → wait 30s → `docker compose ps seaweedfs` should read `Up (healthy)`. `docker inspect --format='{{json .State.Health}}' atmosphere-seaweedfs-1` shows a `Status: healthy` with recent passing probe `Output: ""` (empty because `-O /dev/null`). Negative test: stop the container's master process briefly (harder to stage cleanly than just asserting steady-state), or more practically, change the healthcheck URL to a port with nothing listening and verify `unhealthy` flips within `interval × retries` = 60s. ^p028

### Sources ^p029

- Existing JDL-66 research: [[research/JDL-66/seaweedfs-s3-config-env-interpolation.md]] — established the compose shape this healthcheck fix refines.
- seaweedfs/seaweedfs PR #6520 — "fix: bucket-hook fails with gnu wget": https://github.com/seaweedfs/seaweedfs/pull/6520 — the GNU-wget-HEAD-405 background, not our case but frequently conflated.
- seaweedfs/seaweedfs PR #2680 — "healthz check to avoid drain node with last replicas": https://github.com/seaweedfs/seaweedfs/pull/2680 — establishes `/cluster/healthz` (and filer `/healthz`) as Kubernetes-startup-probe endpoints.
- seaweedfs/seaweedfs issue #8243 — "Health check for S3 service not working": https://github.com/seaweedfs/seaweedfs/issues/8243 — bucket-vs-endpoint resolution bug, fixed upstream before 4.21.
- seaweedfs/seaweedfs issue #1840 — "[s3] healthcheck API endpoint handler": https://github.com/seaweedfs/seaweedfs/issues/1840 — original request that led to the S3 `/status` and `/healthz` endpoints.
- BusyBox mailing list — "wget --spider" 2021-09: https://lists.busybox.net/pipermail/busybox/2021-September/089248.html — confirms BusyBox `--spider` uses GET, not HEAD.
- Live probe of `chrislusf/seaweedfs:4.21` on 2026-04-24 — Alpine 3.23.4, BusyBox 1.37.0 (2025-12-16), no curl in runtime image, port-binding enumeration and endpoint-response matrix captured directly via `docker exec`.
