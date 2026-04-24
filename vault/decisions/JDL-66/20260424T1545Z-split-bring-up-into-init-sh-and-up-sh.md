---
id: 01KQ02PMQNWBPCZZMBP55W8TK8
type: decision
name: 20260424T1545Z-split-bring-up-into-init-sh-and-up-sh
created_at: 2026-04-24T15:45Z
created_by: log/01KQ02PMQNWBPCZZMBP55W8TK8
component: repo
---

## Purpose
Records the architectural decision to split the operator bring-up into two scripts — `scripts/init.sh` for pre-flight dependency checks plus ephemeral artifact generation, and `scripts/up.sh` for tier-by-tier service bring-up — chained by the `Makefile` `up` target so the `&&` operator enforces checks-before-mutation. Supersedes the portion of [[decisions/JDL-66/20260424T1519Z-up-sh-auto-generates-env-on-first-boot]] that co-located `.env` generation inside `up.sh`; the generation mechanism itself is unchanged, only its host file moves.

## 2026-04-24T15:45Z — initial
- agent: log/01KQ02PMQNWBPCZZMBP55W8TK8
- refs: [[decisions/JDL-66/20260424T1519Z-up-sh-auto-generates-env-on-first-boot]], [[decisions/JDL-66/20260424T1519Z-make-nuke-full-reset-primitive]], [[.claude/context/operations]]

Outcome. The operator bring-up is structured as two scripts plus a Makefile target. `scripts/init.sh` carries (A) pre-flight dependency checks — `docker compose` v2 present on PATH, cwd equal to repo root — and (B) ephemeral artifact generation — `.env` populated from `.env.example` with independent URL-safe 32-char random secrets per `CHANGEME` slot on first boot, idempotent skip when `.env` already exists. `scripts/up.sh` carries tier-by-tier service bring-up with health-gating and nothing else. The `Makefile` `up` target becomes `./scripts/init.sh && ./scripts/up.sh`, and the `&&` ensures pre-flight failures abort before any service interaction. ^p001

Alternatives considered. (1) Everything in `scripts/up.sh` (the prior state that landed in commit `1656700`). Rejected: conflates pre-flight validation with state mutation. A missing `docker compose` binary would nevertheless generate a `.env` file, leaving the operator with a confusingly half-initialized repo. No clean separation between "verify you can run the platform" and "actually run the platform." (2) Pre-flight at the Makefile level with `.env` generation inside `up.sh`. Rejected: splits state-mutating code across two files (Makefile-embedded shell plus `up.sh`). Harder to audit, harder to test, and the Makefile's recipe-level shell has different quoting rules than a standalone script. (3) Three scripts — `check.sh` for pre-flight, `init.sh` for ephemeral-gen, `up.sh` for bring-up. Rejected: over-decomposed. Pre-flight and ephemeral-gen always run together as first-boot; chaining them inside one `init.sh` with the strict ordering (all checks pass, then gen runs) is exactly the invariant we want, and no further splitting adds value. (4) `scripts/init.sh` for pre-flight plus gen, `scripts/up.sh` for bring-up, Makefile chains them — the selected path. Clear responsibilities per file, one-command operator entry via `make up`, enforcement of "checks-before-mutation" encoded in the `&&` chain. ^p002

Reasoning. The load-bearing invariant is that pre-flight dependency checks run BEFORE any state mutation, so a clean abort on a missing dependency leaves the repo exactly as it was — no `.env` to clean up, no half-initialized artifacts to confuse future runs. Co-locating the two in `init.sh` lets the script enforce the ordering internally (Section A runs, then Section B runs only if A passed) rather than relying on operator discipline or Makefile recipe conventions. The Makefile `up` target's `./scripts/init.sh && ./scripts/up.sh` then extends the same checks-before-mutation invariant to the service-bring-up boundary: if init fails, services are never touched. ^p003

Implications for `scripts/up.sh`. The file loses its `.env` auto-populate block (the loop-until-no-`CHANGEME` pattern added in commit `1656700`) and its `preflight()` Docker-Compose-v2 check. The file shrinks to: header comment, helpers (`log` / `warn` / `fail` / `wait_for_healthy`), `tier1_m1_infra` block, future-tier markers, `main()`. ^p004

Implications for `scripts/init.sh`. This is a new file carrying the moved pre-flight plus ephemeral-gen logic, plus its own header and `main()`. Executable, POSIX-coreutils only, idempotent. Section A runs dependency checks and exits non-zero on failure; Section B runs only if A passed and performs the `.env` materialization (copy from `.env.example`, replace each `=CHANGEME` with an independent URL-safe 32-char random string), skipping entirely when `.env` already exists. ^p005

Implications for `Makefile`. The `up` target changes from `./scripts/up.sh` to `./scripts/init.sh && ./scripts/up.sh`. The `down` and `nuke` targets are unchanged — `down` remains non-destructive (preserves `.env`), `nuke` remains the full-reset primitive (removes `.env`) per [[decisions/JDL-66/20260424T1519Z-make-nuke-full-reset-primitive]]. ^p006

Supersession scope. This decision supersedes the portion of [[decisions/JDL-66/20260424T1519Z-up-sh-auto-generates-env-on-first-boot]] that located `.env` generation inside `up.sh`. The generation mechanism itself — independent random 32-char URL-safe secrets per `CHANGEME` slot; idempotent skip when `.env` exists; no secret values echoed — is unchanged. Only the host file moved from `up.sh` to `init.sh`. ^p007

Forward posture. Future dependency checks (NVIDIA Container Toolkit validation for M7+, disk-space checks, additional tooling presence checks) extend `init.sh`'s Section A without touching `up.sh`. New ephemeral artifacts (if any ever surface) extend Section B. Operator-facing docs (README, CONTRIBUTING) continue to point at `make up` as the single entry command; the two-script internal structure is an implementation detail operators do not need to know. ^p008

Explicit non-change. `make down` still preserves `.env` because `down` is non-destructive. `make nuke` still removes `.env` because `nuke` is the full-reset primitive. The init.sh / up.sh split does not change those semantics — `nuke` remains the paired destructive primitive to `up`, and running `nuke && up` regenerates a fresh `.env` with fresh random secrets via `init.sh`. ^p009
