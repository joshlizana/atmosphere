---
id: 01KQ0160WCZQ0SH5J7WK7H5H62
type: decision
name: 20260424T1519Z-up-sh-auto-generates-env-on-first-boot
created_at: 2026-04-24T15:19Z
created_by: log/01KQ0160WCZQ0SH5J7WK7H5H62
component: repo
---

## Purpose
Records the M1 decision that `scripts/up.sh` auto-materializes `.env` on first boot by copying `.env.example` and replacing every `=CHANGEME` placeholder with an independent URL-safe 32-character random string using POSIX-portable coreutils. Operator-edited `.env` files are always honored — generation runs only when `.env` is absent.

## 2026-04-24T15:19Z — initial
- agent: log/01KQ0160WCZQ0SH5J7WK7H5H62
- refs: [[files/JDL-66/scripts/up-sh]], [[files/JDL-66/env-example]], [[.claude/context/operations]]

Outcome. `scripts/up.sh` gains a `.env` preflight section that runs immediately after `set -euo pipefail` and before any docker call. When `.env` is absent, the script copies `.env.example` to `.env` and replaces every `=CHANGEME` value with an independent URL-safe 32-char random string generated via `tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32` (or POSIX-equivalent coreutils pipeline). When `.env` exists, the preflight is a no-op — operator customization always wins, and regeneration requires an explicit `rm .env` before re-running the script. ^p001

Alternatives considered. (1) Operator manually populates `.env` from `.env.example` before first bring-up (the original M0 plan). Rejected: every new operator hits a documentation-and-onboarding dependency on first clone, and the typical first-time experience collapses into "paste keys from `.env.example` into `.env` and guess passwords" — guessed passwords get reused across services, which is strictly worse than independent randoms. (2) A dedicated Probe agent materializes a throwaway `.env` for smoke tests only. Rejected by implication: auto-populate makes Probe a normal bring-up run with no special credential handling, keeping the test path and operator path identical. (3) Commit `.env` with fake-but-deterministic passwords. Rejected: `.env` is gitignored by existing repo rule, and deterministic passwords couple the test and production credential surface in a way that leaks security conventions. ^p002

Reasoning. "Fresh clone to running platform in one command" is a first-class operator experience for this platform, and `scripts/up.sh` already owns the tiered, health-gated bring-up primitive (see `[[files/JDL-66/scripts/up-sh]]` ^p002 and ^p003). Materializing `.env` on first boot is the logical extension of that primitive — same entry point, same failure-diagnostic posture, no new tool for the operator to learn. Random secrets at first boot are trivially superseded by operator edit for the small number of keys that need specific values (`GHPAGES_PAT`, `GHPAGES_COMMIT_AUTHOR_EMAIL`), which only matter in later-milestone scope anyway; operator edits are always honored because `.env` existence blocks regeneration. ^p003

Implementation constraints. The generation routine is POSIX-shell-only — no `openssl`, no `python`, nothing beyond coreutils — so it works on any host the rest of `scripts/up.sh` already runs on. Every `CHANGEME` value in `.env.example` is replaced with an *independent* random string, not the same string substituted uniformly; uniform substitution is the failure mode to avoid, and independence is the invariant. Secret hygiene: the routine does not echo any generated value to stdout or stderr. One acknowledging line (`→ Generated .env from .env.example ...`) is the only output; the secrets live in `.env` for the operator to read directly if needed. ^p004

Scope note on `GHPAGES_*` keys. `GHPAGES_PAT` and `GHPAGES_COMMIT_AUTHOR_EMAIL` receive random values like every other `CHANGEME` — they are not functional at M1 (GitHub Pages publishing goes live at M11), so random placeholders cause no harm in the intervening milestones. An inline comment in `up.sh` next to the generation block calls out that the operator must replace these with real values before M11 ships. ^p005

Implications for repo layout. `.env.example` stays the single source of truth for the set of keys and their `CHANGEME` placeholders — no companion template file, no `.env.tmpl`, no secrets committed. `scripts/up.sh` owns the transformation. Operator workflow documentation in `CONTRIBUTING.md` and/or the root README will be updated in a later milestone to read "Run `./scripts/up.sh` — it auto-generates `.env` on first run" instead of the older "copy `.env.example` to `.env` and fill in values"; the doc edit is deferred to avoid coupling this decision to a documentation-refactor commit. ^p006

Idempotence. Re-running `scripts/up.sh` on a healthy platform remains a no-op from the `.env` preflight's perspective: `.env` exists, so generation skips entirely, no output, no side effects. This preserves the script's existing invariant that repeated invocations during normal operation are harmless. ^p007
