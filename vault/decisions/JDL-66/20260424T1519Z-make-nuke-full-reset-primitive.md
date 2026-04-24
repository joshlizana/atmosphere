---
id: 01KQ0176VMYSFDFFT51R8RYHG3
type: decision
name: 20260424T1519Z-make-nuke-full-reset-primitive
created_at: 2026-04-24T15:19Z
created_by: log/01KQ0176VMYSFDFFT51R8RYHG3
component: make
---

## Purpose
Records the architectural decision that `make nuke` is the canonical full-reset primitive — it removes all platform-generated content so the next `make up` restarts from a genuinely clean slate.

## 2026-04-24T15:19Z — initial
- agent: log/01KQ0176VMYSFDFFT51R8RYHG3
- refs: [[.claude/context/operations]], [[decisions/JDL-66/20260424T1518Z-docker-named-volumes-for-state]]

Outcome. `make nuke` runs `docker compose down -v --remove-orphans && rm -rf ./data && rm -f .env`. It removes everything the platform generates on the operator's host: every named volume declared in `compose.yml` (current and future `atmosphere_*`), any stray orphan containers from old compose shapes, any legacy `./data/` bind-mount directory (safety net for operators upgrading from the pre-named-volumes era), and the auto-generated `.env` file. After `make nuke`, `make up` regenerates `.env` with fresh random secrets and brings the platform up from zero state. The two form a paired "delete and rerun" primitive. ^p001

Alternatives considered. (1) Volume-only nuke (`docker compose down -v` alone) — rejected: leaves `.env` in place, which couples the next `make up` to the old random secrets. Operator's mental model of "clean slate" doesn't match reality if `.env` persists. (2) Preserve `.env` across nuke, require operator to `rm .env` manually if they want regeneration — rejected: splits the reset primitive into two commands, one of which operators will forget. The point of `nuke` is one-command reset. (3) Omit the `rm -rf ./data` step since M1+ doesn't create bind-mount directories — rejected: backward-compatibility safety net. Operators upgrading from the pre-named-volumes era may have legacy `./data/` subdirs; `nuke` cleans them without requiring a separate migration step. The cost is a no-op `rm -rf` on clean hosts; the benefit is an upgrade-safe reset for every operator regardless of their history. (4) Destroy docker images too (`docker compose down -v --rmi all`) — rejected: image teardown forces a 1-2 GB re-pull on the next `make up`, which is expensive and rarely what the operator wants. The `nuke` primitive is about *state*, not *image cache*. Operators who want to redownload images can run `docker compose pull` explicitly. ^p002

Reasoning. The platform's operator surface is three commands: `make up` (bring up), `make down` (stop, preserve state), `make nuke` (full reset). Each has a crisp and non-overlapping semantics. `nuke` is the "I want to pretend this platform was never installed" primitive — it exists because `make up` now auto-generates `.env`, which means there are operator-generated artifacts on the host that a partial cleanup would leave stranded. Pairing nuke with the auto-populate decision gives operators a clean loop: `make nuke && make up` is a full reset. ^p003

Implications for `Makefile`. Lands with three targets: `up`, `down`, `nuke`. `nuke`'s recipe is exactly `docker compose down -v --remove-orphans && rm -rf ./data && rm -f .env`. The recipe uses `&&` so a failure in any step halts. If the first `docker compose down -v` fails (e.g., on a host where no compose project is running), the target can no-op cleanly — `docker compose down -v --remove-orphans || true` may be appropriate if idempotence is needed on hosts with no running compose. ^p004

Implications for `.gitignore` and repo layout. `.gitignore` already excludes `.env` and `data/` — no additional changes needed. ^p005

Operator-facing contract. The note about `nuke`: "this destroys all bronze older than the Jetstream replay window." This couples to the no-backups decision — the platform explicitly accepts that `nuke` is irreversible past the replay window. ^p006

Validation. Smoke Probe for JDL-66 validates the full cycle: `make up` → assertions → `make nuke` → `make up` → assertions → pass. Re-runnability is a first-class property. ^p007

Forward posture. Future milestones extend the `Makefile` with non-destructive targets (`test`, `lint`, `logs`, `up-<tier>`) but the destructive surface remains exactly `nuke`. No additional destructive primitives will be introduced. ^p008
