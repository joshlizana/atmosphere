---
id: 01KPZQVNBTEEAPAD64K743AGR1
type: decision
name: 20260424T1236Z-seaweedfs-s3-credentials-via-env-vars
created_at: 2026-04-24T12:36Z
created_by: log/01KPZQVNBTEEAPAD64K743AGR1
component: seaweedfs
---

## Purpose
Records the M1 decision to supply SeaweedFS's single S3 admin identity via `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` environment variables, rather than via an `-s3.config` JSON file (committed literal, committed placeholder + `envsubst` shim, or an in-file `${VAR}` interpolation path).

## 2026-04-24T12:36Z — initial
- agent: log/01KPZQVNBTEEAPAD64K743AGR1
- refs: [[research/JDL-66/seaweedfs-s3-config-env-interpolation]], [[research/JDL-66/seaweedfs-single-container-compose-2026]], [[.claude/context/components/lakekeeper]], [[.claude/context/components/iceberg]]

Outcome. M1 ships SeaweedFS with its single admin identity sourced from the environment: the container reads `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` at process start, and `weed`'s `loadEnvironmentVariableCredentials` unconditionally synthesizes an admin identity from them after any `-s3.config` JSON has been read. The `-s3.config` flag is not passed, no JSON file is committed, no entrypoint shim is needed, no init sidecar is needed. ^p001

Alternatives considered. (1) Committed literal-credentials JSON at `config/seaweedfs/s3.json` — rejected: puts secrets in the git tree. (2) Committed placeholder JSON (e.g. `s3.json.tmpl`) plus a compose `entrypoint:` override running `envsubst` into `/tmp/s3.json` at container start — rejected: adds moving parts (a template file, a shim, a non-default entrypoint) for zero gain over the env-var path at M1's single-identity scope. Also, SeaweedFS 3.95 regressed the most common variant of this pattern (inline-shell-echo s3.json), seaweedfs/seaweedfs#7028 — still open as of research date. (3) Expecting SeaweedFS's `-s3.config` JSON loader to natively env-interpolate `${VAR}` tokens in the file contents — rejected on evidence: upstream source (`weed/s3api/auth_credentials.go`) shows the loader does a pure `os.ReadFile` → protobuf/JSON unmarshal with no substitution pass. The `WEED_` prefix mechanism covers CLI flags and TOML configs but not the S3 identities JSON. ^p002

Reasoning. The env-var path was always there — it just wasn't documented as the canonical mechanism in the first-pass SeaweedFS compose Scout. The follow-up Scout (reading the upstream identity-loader source directly) confirmed it unconditionally synthesizes an admin identity from `AWS_*` env vars after any file-based config is loaded. Combining env vars with the single-trust-domain posture already ratified in `.claude/context/components/lakekeeper.md` §Storage access and `.claude/context/components/iceberg.md` — every client container holds the same S3 access key/secret from `.env` — this is the simplest path that satisfies M1's requirement without producing a credentials file to manage. ^p003

Implications for `compose.yml`. The SeaweedFS service definition omits `-s3.config` from its `command:`, and does not mount anything under `/etc/seaweedfs/`. The service's `environment:` reads `AWS_ACCESS_KEY_ID=${SEAWEEDFS_S3_ACCESS_KEY}` and `AWS_SECRET_ACCESS_KEY=${SEAWEEDFS_S3_SECRET_KEY}` from the existing `.env.example` keys (no new env vars needed). ^p004

Implications for repo layout. `.gitignore` needs no `config/seaweedfs/s3.json` entry (the file doesn't exist in this deployment shape). The original file #2 and file #6 in the M1 plan are dropped; the file count for M1 drops from 8 to 6. ^p005

Future escape hatch. If per-service scoped identities ever become necessary (e.g., a read-only `clickhouse-reader` identity), the fallback path is well-understood — committed `config/seaweedfs/s3.json.tmpl` + compose `entrypoint:` override with `envsubst` — but is deferred until a scoped-identity requirement actually surfaces. Reserving this as a known-good escape hatch, not a present-day need. ^p006

Verification signal. On container startup, the log line `Added admin identity from AWS environment variables: name=admin-<prefix>, accessKey=...` confirms the credential path is working. The M1 smoke Probe can grep for this line as a green-light signal that SeaweedFS's S3 admin identity materialized correctly. ^p007

Design doc alignment. The pre-existing design docs (`.claude/context/components/lakekeeper.md` §Storage access, `.claude/context/components/iceberg.md`) already describe credentials-via-env-vars as the platform norm. This decision re-aligns M1 implementation with that pre-existing design — the `-s3.config` JSON approach proposed in the first SeaweedFS compose Scout was a detour, not a fit. No design-doc edits needed. ^p008
