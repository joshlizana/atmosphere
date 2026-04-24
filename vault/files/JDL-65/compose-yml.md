---
id: 01KPZBGDWQ30QVZEM70YDQ7GSA
type: file
name: compose-yml
created_at: 2026-04-24T09:00Z
created_by: log/01KPZBGDWQ30QVZEM70YDQ7GSA
component: repo
---

## Purpose
Tracks the lifecycle of `/home/josh/atmosphere/compose.yml` — the Docker Compose v2 entry point for the atmosphere platform. Services land progressively from M1 onward; this file is the single root-level compose manifest that `docker compose config`, `docker compose up`, and every bring-up script resolve against.

## 2026-04-24T09:00Z — initial
- agent: log/01KPZBGDWQ30QVZEM70YDQ7GSA
- refs: [[decisions/JDL-65/20260424T0852Z-uv-workspace-declared-at-m0]]

Forge created `compose.yml` at the repo root as part of JDL-65 M0 scaffolding. The file is a six-line Compose v2 stub consisting of a top-of-file comment, `name: atmosphere`, and an empty inline-map `services: {}`. It carries no `version:` key (deprecated in Compose v2), no `networks:`, no `volumes:`, and no `secrets:` — none of those are needed until the first service lands in M1. ^p001

The stub satisfies the M0 acceptance gate that a fresh clone must run `docker compose config` without error. The `{}` inline-empty-map form was chosen over a bare `services:` key because a bare key with nothing under it parses as `null` and reads like an incomplete edit, while `{}` is unambiguously "intentionally empty" and survives linters cleanly. ^p002

Committed as `8028803` on branch `JDL-65-m0-repo-ci-host-prep`. Only `compose.yml` was staged; the working tree's unrelated uncommitted changes (deleted research notes, untracked `.env.example`, `CLAUDE.md`, `.claude/`, `vault/.obsidian/`, new `vault/research/JDL-65/` contents) were deliberately left alone. ^p003
