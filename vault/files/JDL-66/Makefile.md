---
id: 01KQ01980DW2HYZ12F70E288XT
type: file
name: Makefile
created_at: 2026-04-24T19:00Z
created_by: log/01KQ01980DW2HYZ12F70E288XT
component: repo
---

## Purpose
Tracks the lifecycle of `/home/josh/atmosphere/Makefile` — the top-level operator-convenience entry point encoding Atmosphere's full bring-up → teardown → full-reset lifecycle as three PHONY targets (`up`, `down`, `nuke`). The file constitutes the platform's entire operator surface at M1.

## 2026-04-24T19:00Z — initial
- agent: log/01KQ01980DW2HYZ12F70E288XT
- refs: [[decisions/JDL-66/20260424T1519Z-make-nuke-full-reset-primitive]], [[decisions/JDL-66/20260424T1518Z-docker-named-volumes-for-state]], [[decisions/JDL-66/20260424T1519Z-up-sh-auto-generates-env-on-first-boot]], [[files/JDL-66/scripts/up-sh]], [[files/JDL-66/compose-yml]], [[.claude/context/operations]]

Forge created `Makefile` at the repo root on branch `JDL-66-m1-shared-infrastructure-online`. Three PHONY targets encode the full platform lifecycle — `up`, `down`, `nuke` — constituting Atmosphere's entire operator surface at M1 (bring-up, teardown that preserves state, and full-reset). The file is not executable — Makefiles are read by `make`, not executed as scripts. ^p001

The `up` target delegates to `./scripts/up.sh` — the tiered, health-gated bring-up script recorded in [[files/JDL-66/scripts/up-sh]] that handles `.env` auto-generation on first boot and sequences the platform's service tiers behind docker healthchecks. At M1 the script takes no arguments; future milestones that add per-tier args (e.g., `up-<tier>` drill-downs) would have the Makefile forward them through. Keeping the `up` target a thin delegator rather than inlining the tiered bring-up logic means the tier ordering and health-gating live in exactly one place (`scripts/up.sh`) and both `make up` and a direct `./scripts/up.sh` invocation produce identical behavior. ^p002

The `down` target runs `docker compose down` — stops services and removes their containers while preserving every `atmosphere_*` named volume, the repo-local `./data/` tree, and the auto-generated `.env`. Reversible via `make up`; the paired teardown-to-bring-up cycle is the normal operator loop for restarting the stack without losing state. Explicitly distinct from `nuke` in that state survives. ^p003

The `nuke` target runs `docker compose down -v --remove-orphans || true` followed by `rm -rf ./data` and `rm -f .env`. The `|| true` guard on the docker-compose step — added beyond the decision note's base recipe — makes the target idempotent on hosts where no compose project is running, so `make nuke` on a fresh clone or after a prior `make nuke` doesn't fail. Per [[decisions/JDL-66/20260424T1519Z-make-nuke-full-reset-primitive]], the three-step recipe destroys every `atmosphere_*` named volume declared in `compose.yml`, sweeps any legacy `./data/` bind-mount directory as a safety net for operators upgrading from the pre-named-volumes era, and removes the auto-generated `.env` so the next `make up` regenerates it with fresh random secrets per [[decisions/JDL-66/20260424T1519Z-up-sh-auto-generates-env-on-first-boot]]. The `make nuke && make up` loop forms the full-reset primitive. ^p004

Two small structural affordances support forward extension without requiring edits to this invocation's scope. First, recipe indentation uses tabs throughout — GNU Make silently fails to execute space-indented recipes, so the tab convention is load-bearing and is documented in a header comment (`Recipe lines are tab-indented (GNU Make requires tabs).`). Second, each target carries a `##` doc-comment on the line immediately above its recipe — a convention that enables a future `make help` auto-discovery target (parses `##` comments via `grep ': ##'`) to be added without this invocation needing to pre-build it. `make -n up down nuke` dry-runs cleanly, emitting the expected commands in order. ^p005

The destructive surface is pinned at exactly `nuke` — per the forward-posture clause of [[decisions/JDL-66/20260424T1519Z-make-nuke-full-reset-primitive]], future milestones extend the `Makefile` with non-destructive targets (`test`, `lint`, `logs`, `up-<tier>`) but no additional destructive primitives are planned. The three-target surface here is the complete destructive vocabulary for the platform's lifecycle. ^p006
