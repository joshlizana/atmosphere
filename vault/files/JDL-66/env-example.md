---
id: 01KPZQVDNG8K278GNENXZR88RJ
type: file
name: env-example
created_at: 2026-04-24T17:55Z
created_by: log/01KPZQVDNG8K278GNENXZR88RJ
component: repo
---

## Purpose
Tracks the lifecycle of `/home/josh/atmosphere/.env.example` — the checked-in template enumerating every environment key the atmosphere compose stack expects in a local `.env`. Carries the contributor-facing contract for Lakekeeper service passwords, Postgres credentials, Grafana admin, Prefect API key, OpenMetadata admin, SeaweedFS S3 key pair, and the Docker Compose project-name pin.

## 2026-04-24T17:55Z — initial
- agent: log/01KPZQVDNG8K278GNENXZR88RJ
- refs: [[research/JDL-66/postgres-compose-multi-db-init-2026]]

Forge modified `.env.example` at commit `37b4d2e` on branch `JDL-66-m1-shared-infrastructure-online`, inserting a new `# Compose project` section immediately before the existing `# Postgres` section. The new section carries a multi-line `#` comment describing why the pin exists — mirroring `name: atmosphere` in `compose.yml` so `atmosphere_postgres` and every other `atmosphere_*` artifact resolves predictably regardless of the operator's checkout directory name — followed by the unquoted key `COMPOSE_PROJECT_NAME=atmosphere`. No existing key, value, comment, or line ordering was touched. ^p001

The pin enables reliable `docker volume ls --filter name=atmosphere_` enumeration for the backup workflow, keeps the compose project's naming stable under `docker` CLI commands that don't themselves read `compose.yml`, and protects the Postgres named-volume path `atmosphere_postgres` declared at the compose top-level `volumes:` block (landing in `compose.yml` later this PR). Without the pin, Docker derives the project name from the working-directory basename, which would produce `<dirname>_postgres` and break both the backup enumeration and any assumption that the named volume is stable across operator checkouts. ^p002

The file was originally created in M0 under JDL-65 and was further tweaked by a linter (intentional) after Forge's commit, so the working-tree state downstream of `37b4d2e` carries formatter-applied whitespace adjustments outside the scope of this invocation. Only Forge's `37b4d2e` addition is recorded here; the subsequent linter pass is a separate modification event. ^p003

## 2026-04-24T17:40Z — addendum
- agent: log/01KQ05X7M1P9K2D3V4B5C6A7L8
- refs: [[incidents/JDL-66/20260424T1618Z-sigpipe-under-pipefail-in-scripts-init-sh]], [[decisions/JDL-66/20260424T1519Z-up-sh-auto-generates-env-on-first-boot]], [[files/JDL-66/scripts/init-sh]], [[files/JDL-66/app/tests/test_m1_infrastructure_smoke-py]]

Forge modified `.env.example` at commit `5d46f21` on branch `JDL-66-m1-shared-infrastructure-online`. Surgical edit to one sentence of the ten-line preamble comment block at the top of the file. The sentence previously read "Operators copy it to a sibling `.env` (which is gitignored) and replace every `CHANGEME` placeholder with a real value for their environment." It now reads "Operators copy it to a sibling `.env` (which is gitignored) and replace every placeholder with a real value for their environment." — the backticked word `` `CHANGEME` `` dropped, with a minor word-wrap shift to keep lines under ~80 chars. Two lines changed in the diff. ^p004

Rationale: the M1 smoke Probe re-run (task `a3f2804c93ee37e65`) failed `test_05_env_generated_with_unique_secrets` because the generated `.env` — produced by `scripts/init.sh` via `cp .env.example .env` + per-slot CHANGEME substitution per [[files/JDL-66/scripts/init-sh]] ^p003 — inherited the preamble comment verbatim. The test's broad substring scan `"CHANGEME" not in text` hit the backticked word in prose even though every actual `KEY=CHANGEME` placeholder was correctly substituted with a random 32-char secret. Of the three remedies considered (rephrase preamble, strip preamble in init.sh, narrow the test), the user chose the preamble rephrase as cleanest — any operator reading a `KEY=CHANGEME` line understands by context what the placeholder is, without needing the prose to name it explicitly. ^p005

Verification per Forge's response: `grep '^#.*CHANGEME' .env.example` returns no hits, so the literal word no longer appears in any comment line; `grep -c '=CHANGEME$' .env.example` reports 16 placeholders intact, so every `KEY=CHANGEME` line below the preamble stayed verbatim and remains the substitution anchor for `init.sh`'s sed loop keyed on `=CHANGEME$`. ^p006

Everything else in `.env.example` is preserved verbatim: the `# Compose project` section recorded in the initial entry ^p001 with `COMPOSE_PROJECT_NAME=atmosphere`, every section header (`# Postgres`, `# SeaweedFS S3`, `# Redpanda`, etc.), every other comment, every `KEY=VALUE` pair including both the static defaults and the sixteen `KEY=CHANGEME` placeholders. No key added, no key removed. ^p007
