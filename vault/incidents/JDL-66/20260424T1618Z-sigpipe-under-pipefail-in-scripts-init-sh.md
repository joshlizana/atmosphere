---
id: 01KQ04JJX8R1M16PECFVAYP1ED
type: incident
name: 20260424T1618Z-sigpipe-under-pipefail-in-scripts-init-sh
created_at: 2026-04-24T16:18Z
created_by: log/01KQ04JJX8R1M16PECFVAYP1ED
component: helm
---

## Purpose
Records the M1 smoke-Probe incident where `scripts/init.sh` exited 141 on every fresh clone because its `tr -dc ... </dev/urandom | head -c 32` random-secret pipeline raised SIGPIPE under `set -o pipefail`, leaving `.env` half-initialized and blocking `make up`; captures the deterministic reproduction, the bounded-read remediation landing in a parallel Forge invocation, and the operational implication that any future `pipefail`-declaring shell Forge must be paired with a shellcheck-equivalent review step.

## 2026-04-24T16:18Z — initial
- agent: log/01KQ04JJX8R1M16PECFVAYP1ED
- refs: [[files/JDL-66/scripts/init-sh]], [[files/JDL-66/app/tests/test_m1_infrastructure_smoke-py]], [[decisions/JDL-66/20260424T1545Z-split-bring-up-into-init-sh-and-up-sh]], [[.claude/context/operations]]

What happened. The M1 smoke Probe's first outer-loop run (task `a468e17a6a5359be5`, report commit `6fbad22`) failed immediately in Phase 2 at `test_04_make_up_completes_and_returns_zero`. Direct cause: `make up` exited 141 with signature `make: *** [Makefile:10: up] Error 141`. Downstream: 19 of 25 tests failed; 17 of the failures were downstream consequences of the platform never coming up; the remaining 6 "passes" were Phase-1 clean-state checks or pass-for-wrong-reason cases. ^p001

Root cause. `scripts/init.sh` uses the classic `tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32` pipeline to generate each random secret value. Under `set -euo pipefail` (declared at the top of the script), this pipeline fails every time: `head -c 32` reads 32 bytes and closes its stdin, `tr` is still reading from `/dev/urandom` (an infinite source) and attempting to write downstream, the first write after `head` closes fails with EPIPE, `tr` receives SIGPIPE, exits 141. `pipefail` propagates 141 up to the pipeline's exit code, `set -e` terminates the script. The `sed` substitution never runs. `.env` is left half-initialized with every `CHANGEME` slot unsubstituted, and `scripts/up.sh` is never invoked. ^p002

Reproduction (3/3 deterministic): `bash -c 'set -euo pipefail; rand=$(tr -dc "A-Za-z0-9" </dev/urandom | head -c 32); echo OK'` exits 141 before printing `OK`. The minimal repro elides all surrounding script context — only `set -o pipefail` plus the idiomatic `tr | head -c` pipeline is required to trigger the failure, which confirms the SIGPIPE-under-pipefail interaction as the sole proximate cause rather than any interaction with `sed`, `/dev/urandom` availability, or the `.env` materialization loop structure. ^p003

Remediation. Replace the two-stage `tr | head -c` pipeline with a bounded-read + bash parameter-expansion pattern: `chunk=$(LC_ALL=C tr -dc 'A-Za-z0-9' < <(head -c 256 /dev/urandom))` followed by `rand="${chunk:0:32}"`. `head -c 256 /dev/urandom` reads exactly 256 bytes and exits cleanly; `tr` filters a bounded input stream and exits normally; bash slices the first 32 characters via `${chunk:0:32}`. No pipeline to a premature-closer, so no SIGPIPE. Entropy margin is generous — 256 bytes × ~66% alphanumeric keep rate ≈ 170 characters expected, of which we take 32. A parallel Forge invocation is landing this fix now (see the next `files/JDL-66/scripts/init-sh` file-modified entry once it commits). After the fix, the smoke Probe re-runs against the corrected script. ^p004

Why this slipped past authoring. The `tr | head -c` pattern is a well-known shell idiom that works correctly WITHOUT `pipefail`. Most authoring references omit the pipefail-interaction caveat. The Forge invocation that wrote [[files/JDL-66/scripts/init-sh]] inherited the idiomatic form without spotting the interaction with `set -o pipefail` declared earlier in the same script. This is a category of bug that static analysis catches reliably — `shellcheck` flags `tr | head -c` under `pipefail` as SC2094 / SC2320 family — so a CI-integrated `shellcheck` pass on `scripts/**/*.sh` would have caught it before Probe did. ^p005

Operational implication. Any future shell-script Forge invocation that declares `set -o pipefail` must be paired with a `shellcheck`-equivalent review step, either by the authoring agent or by a CI check. This incident is the signal to add that step; the specific fix is tactical. The M0 CI surface described in [[.claude/context/operations]] already runs `ruff` and `prettier` gates — adding `shellcheck` against `scripts/**/*.sh` extends the same green-light model to shell-script authoring and would have failed the original `init.sh` commit at CI rather than at Probe. ^p006

Scope of harm. None reached main. The bug was caught on the first Probe run against the M1 branch (`JDL-66-m1-shared-infrastructure-online`); no push, no PR, no merge. The Probe's own test file (`app/tests/test_m1_infrastructure_smoke.py`) is retained as the regression harness — its `test_04_make_up_completes_and_returns_zero` test is the exact assertion that failed 141, so re-running it against the remediated script is the authoritative proof the fix holds. ^p007
