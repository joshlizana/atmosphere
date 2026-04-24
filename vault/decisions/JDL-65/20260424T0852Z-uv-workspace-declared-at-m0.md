---
id: 01KPZB0TBGXBXKNKMPZ5H8G2RT
type: decision
name: 20260424T0852Z-uv-workspace-declared-at-m0
created_at: 2026-04-24T08:52Z
created_by: log/01KPZB0TBGXBXKNKMPZ5H8G2RT
component: repo
---

## Purpose
Records the decision to declare `[tool.uv.workspace]` at M0 with an explicit empty `members = []` list, rather than deferring the workspace block until the first real Python member (Spout) lands at M4.

## 2026-04-24T08:52Z — initial
- agent: log/01KPZB0TBGXBXKNKMPZ5H8G2RT
- refs: [[research/JDL-65/uv-workspace-layout]]

At the start of JDL-65 (M0 — Repo, CI, and host prep), we chose between two ways to handle the uv workspace declaration in the initial root `pyproject.toml`. Alternative A was to ship a plain-package root `pyproject.toml` at M0 with no `[tool.uv.workspace]` block and add the workspace declaration later when the first real Python member (Spout, in M4) arrived. Alternative B was to declare the workspace block at M0 with `members = []` and append one explicit member path per subsequent milestone as Python members arrive. We chose Alternative B. ^p001

The primary reasoning is cost: establishing the workspace pattern once at M0 is cheaper than retrofitting a workspace declaration into a future change set that is ostensibly about something else. A later milestone focused on Spout should not have to also relitigate the root `pyproject.toml` shape; keeping the workspace declaration stable from the first commit keeps later PRs focused on their own scope. ^p002

The member list is deliberately explicit (`members = []`, extended path-by-path) rather than a glob like `app/services/*`. This avoids the uv#17196 footgun where any directory matching a workspace glob without its own `pyproject.toml` hard-errors every `uv sync`. Because M0 creates empty skeleton directories for `app/services/`, `app/flink-jobs/`, and similar, a glob-based member list would break `uv sync` until those skeletons carry their own package manifests. An explicit list sidesteps this entirely. ^p003

Implication for M0 file-writing: the root `pyproject.toml` will contain `[tool.uv.workspace]` with `members = []`. Each later milestone that introduces a Python member (M4 for Spout, M5 and M6 for the Flink jobs and shared common library, M7 for Sleuth and Oracle) will append the appropriate member path(s) as part of its own PR. ^p004
