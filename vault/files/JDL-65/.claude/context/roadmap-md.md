---
id: 01KPZB8Y3PVKWA4X7E0K2M9Q1D
type: file
name: .claude/context/roadmap.md
created_at: 2026-04-24T08:58Z
created_by: log/01KPZB8Y3PVKWA4X7E0K2M9Q1D
component: repo
---

## Purpose
Tracks changes to `.claude/context/roadmap.md`, the repo-level roadmap that sequences milestones M0 through M14 and defines their acceptance criteria, build tasks, validation steps, and operationalization steps.

## 2026-04-24T08:58Z — initial
- agent: log/01KPZB8Y3PVKWA4X7E0K2M9Q1D
- refs: [[research/JDL-65/compose-gpu-syntax-cuda-base-image-2026]], [[research/JDL-65/uv-workspace-layout]], [[decisions/JDL-65/20260424T0852Z-uv-workspace-declared-at-m0]]

At the start of JDL-65 (M0 — Repo, CI, and host prep), `.claude/context/roadmap.md` was edited in four places within the M0 section to reflect two architectural decisions settled with the user before any file-writing began. The two decisions — standardizing on `ruff format` in place of `black`, and pinning the NVIDIA CUDA base image used for GPU passthrough verification to `nvidia/cuda:12.9.0-base-ubuntu22.04` — were captured separately as `decision` events; this entry records only the resulting file edit. ^p001

The acceptance line of M0 (line 23) was edited twice on the same line: `black --check` was replaced with `ruff format --check`, and the CUDA image tag `nvidia/cuda:12.2-base` was replaced with `nvidia/cuda:12.9.0-base-ubuntu22.04`. The build-band CI-workflow bullet (line 29) had `ruff, black --check` replaced with `ruff check, ruff format --check` so the CI gate names match the decided tooling. The build-band NVIDIA Container Toolkit bullet (line 31) had the old CUDA tag replaced with the new one. The operationalize-band pre-commit bullet (line 35) had `running ruff and black locally` replaced with `running ruff (lint + format) locally`. ^p002

A grep across `.claude/context/` confirmed that no other files in the repo reference the old `black` invocation or the old `nvidia/cuda:12.2-base` tag, so these four edits fully propagate the two decisions across the design-documentation surface. ^p003
