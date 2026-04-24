---
id: 01KQ02T1NE67TDCFBQDE6QWK14
type: file
name: init.sh
created_at: 2026-04-24T19:19Z
created_by: log/01KQ02T1NE67TDCFBQDE6QWK14
component: repo
---

## Purpose
Tracks the lifecycle of `/home/josh/atmosphere/scripts/init.sh` — the platform's first-boot pre-flight and ephemeral-artifact-generation script. Runs as the first half of the `make up` chain: validates dependencies in a non-mutating pre-flight, then materializes `.env` from `.env.example` with independent random secrets, then hands control to `scripts/up.sh` for service bring-up.

## 2026-04-24T19:19Z — initial
- agent: log/01KQ02T1NE67TDCFBQDE6QWK14
- refs: [[files/JDL-66/env-example]], [[files/JDL-66/scripts/up-sh]], [[files/JDL-66/Makefile]], [[decisions/JDL-66/20260424T1519Z-up-sh-auto-generates-env-on-first-boot]], [[.claude/context/operations]]

Forge created `scripts/init.sh` at commit `ba0350c` on branch `JDL-66-m1-shared-infrastructure-online`, executable (mode `100755`) and tracked in git so a fresh `git clone && make up` works without a separate `chmod +x` step. The script enforces a load-bearing invariant: all pre-flight dependency checks run BEFORE any state mutation, so a clean abort on a missing dependency leaves the repo exactly as it was — no half-initialized `.env`, no partial copy of `.env.example`, no residue to clean up before the next attempt. ^p001

Section A — pre-flight dependency checks — is idempotent and non-mutating. `check_docker_compose_v2()` verifies `docker` is on `PATH`, then that `docker compose version` responds, then that the reported version is v2.x or greater; the major-version accept pattern is a glob on `docker compose version --short` that accepts `2.x`, `3.x+`, and `10+.x` so the check survives future Compose major-version bumps without code changes. `check_repo_root()` verifies the sentinel trio `compose.yml` + `.env.example` + `Makefile` is all present in the current working directory, and names the specific missing file(s) in any failure message so an operator who ran the script from the wrong directory sees exactly which sentinel(s) were absent rather than a generic "not in repo root" error. Both helpers `fail` loud with a specific remediation hint, and the script exits non-zero before touching `.env` if any check misses. ^p002

Section B — ephemeral artifact generation — mutates state and runs only if Section A passed. `generate_env()` checks for `.env`. If present: one-line skip log (`→ .env present; skipping generation`) and exit 0 — operator customization always wins, and regeneration requires an explicit `rm .env` per the forward-posture clause of [[decisions/JDL-66/20260424T1519Z-up-sh-auto-generates-env-on-first-boot]]. If absent: copy `.env.example` → `.env`, then loop-until-no-`CHANGEME`, replacing each `=CHANGEME` slot with an independent URL-safe 32-char random string. Each iteration generates a fresh random via `tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32` and substitutes only the first remaining occurrence per pass via `sed -i "0,/=CHANGEME$/ s//=${rand}/"`, so every slot receives its own independent random value — uniform substitution (one random reused across every slot) is the failure mode explicitly avoided. No secret ever reaches stdout or stderr; one log line acknowledges generation on completion. ^p003

The tooling surface is POSIX-shell-only: `bash`, `tr`, `sed`, `grep`, `head`, `printf`, `command`, `cp`, `[`, `case`, and `/dev/urandom`. No `openssl`, no `python`, no `awk`-only features, no other cross-distro hazards — the script runs on any host the rest of the Atmosphere bring-up already runs on, matching the POSIX-coreutils constraint established in [[decisions/JDL-66/20260424T1519Z-up-sh-auto-generates-env-on-first-boot]] ^p004 and keeping the dependency assumption set to just "Docker Compose v2 on PATH" that Section A itself validates. ^p004

The script is the first half of the `make up` chain: the `Makefile` `up` target recorded in [[files/JDL-66/Makefile]] ^p002 is `./scripts/init.sh && ./scripts/up.sh`, so on fresh-clone first boot `init.sh` generates `.env` and passes control to `up.sh` for the tiered, health-gated service bring-up; on re-runs against an initialized repo `init.sh` validates dependencies and no-ops the env-gen silently. The companion `make nuke` target in [[files/JDL-66/Makefile]] ^p004 removes `.env` along with the data tree, so the next `make up` triggers a fresh `init.sh` regeneration cycle with new independent randoms. This splits the responsibility that originally lived wholly inside `scripts/up.sh` per [[files/JDL-66/scripts/up-sh]] ^p007 into two scripts — env-gen moves to `init.sh` here, and `up.sh` narrows to service bring-up only in a parallel Forge invocation — keeping the `.env` auto-generation contract identical while letting the pre-flight / mutation boundary become a script boundary instead of an in-script section boundary. ^p005
