---
id: 01KPZMFGDV30HZHTMFTJ00WVCK
type: file
name: setup-uv-workspace-ci-2026.md
created_at: 2026-04-24T11:37Z
created_by: log/01KPZMFGDV30HZHTMFTJ00WVCK
component: vault
---

## Purpose
Tracks the lifecycle of `vault/research/JDL-M0/setup-uv-workspace-ci-2026.md` — a legacy Scout research note carrying the canonical `astral-sh/setup-uv` + `uv sync` pattern for JDL-65 M0 CI work. The note lived under the pre-Linear `JDL-M0/` namespace that predates the current issue-numbered research layout; it was superseded by a re-researched, JDL-65-pathed version at `vault/research/JDL-65/setup-uv-workspace-ci-2026.md` and deleted from the working tree as part of the JDL-65 close-out.

## 2026-04-24T11:37Z — initial
- agent: log/01KPZMFGDV30HZHTMFTJ00WVCK
- refs: [[research/JDL-65/setup-uv-workspace-ci-2026]]

At the start of the JDL-65 session, the working tree carried two unstaged research notes under `vault/research/JDL-M0/` left over from an earlier unnumbered phase of the repo — `ci-workflow-uv-python-monorepo.md` and `setup-uv-workspace-ci-2026.md`. The user deleted them from the working tree and directed Scout to re-research both topics under the correct `vault/research/JDL-65/` namespace, which Scout completed and committed to `vault/research/JDL-65/setup-uv-workspace-ci-2026.md` at commit `debce3d`. The legacy JDL-M0 note is the superseded version and is not to be consulted for JDL-65 CI decisions. ^p001

At the close of JDL-65 the unstaged deletion was committed as `dacf851` on branch `JDL-65-m0-repo-ci-host-prep` with message `chore(JDL-65): remove stale JDL-M0 research notes`. The commit bundles both JDL-M0 research-note deletions into a single changeset (207 deletions across the two files: 117 lines for `ci-workflow-uv-python-monorepo.md` and 90 lines for this file). The commit body records the supersession rationale — "Both notes were superseded by re-researched JDL-65-pathed versions. The JDL-M0 prefix predates the Linear issue numbering and is no longer used." — and the `JDL-M0/` directory itself is now gone from the tree because both of its contents were removed in the same commit. ^p002

The deleted note's frontmatter (`id: setup-uv-workspace-ci-2026`, `type: research`, `created_by: scout`, `component: ci`) and its Purpose section — pinning down the 2026-canonical `astral-sh/setup-uv` usage pattern, the `uv sync` flag combination for workspace CI, current major tag and release cadence, SHA-pinning vs version pinning, cache defaults, and which flags are defaults vs must-specify — are recorded here only as provenance for the supersession. The canonical current content lives at [[research/JDL-65/setup-uv-workspace-ci-2026]] and that is the note to read. This file is the final entry in the lifecycle of the JDL-M0-pathed version; no further entries follow. ^p003
