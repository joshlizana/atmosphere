---
id: seaweedfs-s3-config-env-interpolation
type: research
name: SeaweedFS -s3.config env-var interpolation behavior (4.21, April 2026)
created_at: 2026-04-24
created_by: scout
component: seaweedfs
---

## Purpose

Pin down how SeaweedFS's `-s3.config` JSON loader treats file contents at load time, decide between the three candidate patterns for shipping static S3 credentials in M1 (literal-creds file vs. placeholder + entrypoint shim vs. native env-var interpolation), and surface the upstream-supported env-var fallback so the compose wiring uses the cleanest shape available today. Follow-up from the existing plan in [[research/JDL-66/seaweedfs-single-container-compose-2026.md]] (commit `6d3d042`) which specified `-s3.config=/etc/seaweedfs/s3.json` with credentials "sourced from `.env`" but did not pin the sourcing mechanism.

## Entry — initial — 2026-04-24 — scout

**agent:** scout
**refs:** [[.claude/context/components/iceberg.md]] (SeaweedFS section), [[.claude/context/operations.md]] (Secrets and configuration), [[research/JDL-66/seaweedfs-single-container-compose-2026.md]], upstream `weed/s3api/auth_credentials.go` on `master`, SeaweedFS wiki pages S3-Credentials and Load-Command-Line-Options-from-a-file, `docker/seaweedfs-compose.yml` and `docker/compose/s3.json` in upstream, seaweedfs/seaweedfs discussions #4728 and issues #7028

### The authoritative answer: no interpolation on file contents ^p001

SeaweedFS's `-s3.config` JSON loader does not perform any form of `${VAR}` / `$VAR` / template substitution on the file contents. The loader is `loadS3ApiConfigurationFromFile` in `weed/s3api/auth_credentials.go` on master, and its implementation is minimal: `os.ReadFile(fileName)` reads the raw bytes, an optional KMS initialization pass runs against the content, and the bytes go straight into `LoadS3ApiConfigurationFromBytes` which invokes `filer.ParseS3ConfigurationFromBytes` to unmarshal them as JSON (or the internal protobuf equivalent). There is no interpolation step, no shell expansion, no Go-template rendering — whatever you put in the file is what the parser sees. Candidate pattern #3 (native env-var interpolation inside the JSON) is structurally unavailable. ^p002

### The WEED_ prefix mechanism does not apply here ^p003

SeaweedFS does have a documented `WEED_` environment-variable override mechanism, but it is scoped to two surfaces only: (a) command-line flags — e.g., `WEED_MASTER_PORT` overriding `-master.port` — and (b) TOML configuration files loaded via `-options` / `master.toml` / `filer.toml` / `notification.toml` / `replication.toml`, where TOML keys map to `WEED_<UPPER_KEY>_<UPPER_SUBKEY>` environment variables. The `-s3.config` JSON file for S3 identities is a different config surface — it is parsed through the `iam_pb.S3ApiConfiguration` protobuf/JSON schema, not through the generic Viper-backed config loader that honors the `WEED_` prefix — so `WEED_IDENTITIES_*`-style overrides are not a real thing. The wiki's S3-Credentials page confirms this implicitly by not mentioning the `WEED_` prefix in the context of S3 identity configuration, and by listing environment variables as a separate (lower-priority) authentication source rather than as an overlay on the JSON file. ^p004

### What SeaweedFS does support natively: `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` ^p005

SeaweedFS reads `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` directly from the environment via `loadEnvironmentVariableCredentials` in the same `auth_credentials.go`. When both are set, it synthesizes an admin identity named `admin-<first-8-chars-of-access-key>` with `ACTION_ADMIN`, appends it to the in-memory identities list, and marks it `IsStatic: true` (immutable across reloads). The wiki's S3-Credentials page documents this pattern (`export AWS_ACCESS_KEY_ID=... ; export AWS_SECRET_ACCESS_KEY=...`) as the canonical fallback when no `-s3.config` file is provided. The critical detail the source code makes explicit, which the wiki does not clearly spell out: `loadEnvironmentVariableCredentials` is called unconditionally after `loadS3ApiConfigurationFromFile` runs, so if both are populated, you get the JSON identities *plus* an additional admin identity synthesized from the env vars — it is not a strict either/or. ^p006

### Pattern decision for M1: native env-var fallback, no static JSON file ^p007

The cleanest M1 shape is **candidate pattern #3' (variant)**: do not ship `-s3.config` at all, and rely on SeaweedFS's native `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` env-var loading. Concretely in compose: ^p008

```yaml
services:
  seaweedfs:
    image: chrislusf/seaweedfs:4.21
    command: >-
      server -s3 -filer
      -dir=/data
      -master.volumeSizeLimitMB=1024
    environment:
      AWS_ACCESS_KEY_ID: ${SEAWEEDFS_S3_ACCESS_KEY}
      AWS_SECRET_ACCESS_KEY: ${SEAWEEDFS_S3_SECRET_KEY}
    volumes:
      - ./data/seaweedfs:/data
```

`SEAWEEDFS_S3_ACCESS_KEY` and `SEAWEEDFS_S3_SECRET_KEY` come from `.env` at the compose project root (already the pattern documented in [[.claude/context/operations.md]] §Secrets and configuration). No JSON file, no entrypoint shim, no one-shot init sidecar, no committed placeholder template, no read-only-image concerns. The synthesized `admin-*` identity has `ACTION_ADMIN` which for M1 is exactly the posture `[[.claude/context/components/lakekeeper.md]]` already ratifies: "the compose network is the security perimeter" with every client holding the same S3 key pair. ^p009

### Why this beats the placeholder + envsubst shim (candidate #2) ^p010

Candidate #2 (commit `s3.json.tmpl` with `${...}` tokens, render at container start via an entrypoint shim or init sidecar) was the leading alternative and is the pattern that upstream users have historically inlined via `/bin/sh -c "echo '...' > /s3.json && weed s3 -config=/s3.json"` in compose. That shape has an open regression: seaweedfs/seaweedfs#7028 (filed 2025-07-22, still open as of this research) reports that inline-shell `s3.json` generation produces `SignatureDoesNotMatch` errors starting in SeaweedFS 3.95, with no maintainer resolution in the thread. Our 4.21 target is well past that cutoff, so reproducing the inline-echo pattern specifically is off the table; a proper entrypoint shim with `envsubst` over a committed template would probably work, but it buys nothing over the native env-var path while adding a file (`s3.json.tmpl`), a shim script, and a new failure mode (`envsubst` not in the image, placeholder token collision with legitimate `$` content). ^p011

### Why this beats a literal-creds committed file (candidate #1) ^p012

Candidate #1 (commit `config/seaweedfs/s3.json` with real keys) is ruled out by the existing rule in [[.claude/context/operations.md]]: "Every credential loads from environment variables defined in a single `.env` file ... never committed." Even if the repo were private, diverging from that pattern for one service creates a second credential-audit surface for no operational benefit. ^p013

### Caveat: the synthesized admin identity name is derived from the key ^p014

The env-var-synthesized identity's name is `admin-<first-8-chars-of-AWS_ACCESS_KEY_ID>`, not a fixed string. Any tooling that pins by identity name — dashboards, future per-identity ACL narrowing, audit log filters — needs to compute it from the access key rather than hard-coding a value. For M1 this is academic (we only have one identity with `ACTION_ADMIN`), but worth flagging before anyone reaches for an identity name from a log and is surprised it changes if the access key rotates. The access-key/secret pair itself is what every client authenticates with, so log correlation on access-key prefix stays stable. ^p015

### If we ever need non-admin identities: the shim is then required ^p016

The env-var path synthesizes exactly one admin identity. Any future posture that needs per-service identities with scoped actions (e.g., a `clickhouse-readonly` identity that only has `Read`/`List`) cannot be expressed via env vars alone — at that point `-s3.config` with a full `identities[]` array becomes necessary, and because the loader does no interpolation (§p002), the only way to keep real credentials out of the repo is to revisit pattern #2: a committed template (`config/seaweedfs/s3.json.tmpl`) + an entrypoint shim that runs `envsubst` into a writable location and starts `weed server ... -s3.config=<rendered>`. This is a post-M1 concern explicitly — the design doc ([[.claude/context/components/lakekeeper.md]], [[.claude/context/components/iceberg.md]]) commits to a single-trust-domain posture with one SeaweedFS S3 key pair shared across all clients, so M1 does not need this. Keep the option in mind but do not build it yet. ^p017

### Shim shape if the post-M1 case ever lands ^p018

When the time comes, the cleanest shim shape on SeaweedFS's upstream `chrislusf/seaweedfs:4.x` image is an `entrypoint:` override in compose rather than a separate init sidecar. The image ships with `gettext` (for `envsubst`) in recent releases and a writable `/etc/seaweedfs/` is not required — render into `/tmp/s3.json` which is always writable: ^p019

```yaml
services:
  seaweedfs:
    image: chrislusf/seaweedfs:4.21
    entrypoint: ["/bin/sh", "-c"]
    command:
      - |
        envsubst < /config/s3.json.tmpl > /tmp/s3.json &&
        exec weed server -s3 -filer -dir=/data
             -s3.config=/tmp/s3.json
    environment:
      SEAWEEDFS_ADMIN_ACCESS_KEY: ${SEAWEEDFS_ADMIN_ACCESS_KEY}
      SEAWEEDFS_ADMIN_SECRET_KEY: ${SEAWEEDFS_ADMIN_SECRET_KEY}
      SEAWEEDFS_READONLY_ACCESS_KEY: ${SEAWEEDFS_READONLY_ACCESS_KEY}
      SEAWEEDFS_READONLY_SECRET_KEY: ${SEAWEEDFS_READONLY_SECRET_KEY}
    volumes:
      - ./data/seaweedfs:/data
      - ./config/seaweedfs:/config:ro
```

Single container, no init-sidecar lifecycle to orchestrate, no shared volume between services, standard `exec` handoff so signal handling works. If `gettext` turns out to be missing on a future base-image rebase, the fallback is a 5-line `sh` substitution with `sed` against the same template — still smaller surface than a separate init service. ^p020

### Verify at the host before committing compose ^p021

Once compose is wired, the smoke test is: `docker compose up -d seaweedfs`, then `docker logs seaweedfs 2>&1 | grep 'Added admin identity from AWS environment variables'` — that exact log line is emitted by `loadEnvironmentVariableCredentials` on successful identity synthesis (Go source: `glog.Infof("Added admin identity from AWS environment variables: name=%s, accessKey=%s", ...)`). Absence of that line after startup is the unambiguous signal that env-var injection did not take. Secondary verification is an `aws --endpoint-url=http://localhost:8333 s3 mb s3://test-bucket` using those credentials — that exercise is already the M1 acceptance criterion in [[.claude/context/roadmap.md]]. ^p022

### Sources ^p023

- `weed/s3api/auth_credentials.go` on master (loadS3ApiConfigurationFromFile, LoadS3ApiConfigurationFromBytes, loadEnvironmentVariableCredentials): https://github.com/seaweedfs/seaweedfs/blob/master/weed/s3api/auth_credentials.go
- SeaweedFS wiki — S3 Credentials: https://github.com/seaweedfs/seaweedfs/wiki/S3-Credentials
- SeaweedFS wiki — Load Command-Line Options from a file (WEED_ prefix mechanism): https://github.com/seaweedfs/seaweedfs/wiki/Load-Command-Line-Options-from-a-file
- Upstream canonical compose example: https://github.com/seaweedfs/seaweedfs/blob/master/docker/seaweedfs-compose.yml
- Upstream canonical s3.json example (literal keys, dev/test only): https://github.com/seaweedfs/seaweedfs/blob/master/docker/compose/s3.json
- Discussion #4728 — static S3 config vs shell-overwrite: https://github.com/seaweedfs/seaweedfs/discussions/4728
- Issue #7028 — 3.95 broke inline-echo s3.json generation: https://github.com/seaweedfs/seaweedfs/issues/7028
- DeepWiki — SeaweedFS Configuration chapter: https://deepwiki.com/seaweedfs/seaweedfs/5.1-configuration
