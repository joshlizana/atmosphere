---
id: 01KPZB4NNVMV0ATRGJJ4R7Y57N
type: decision
name: 20260424T0853Z-cuda-base-image-tag-bump
created_at: 2026-04-24T08:53Z
created_by: log/01KPZB4NNVMV0ATRGJJ4R7Y57N
component: host
---

## Purpose
Records the decision to bump the CUDA base-image tag used for the host GPU smoke test from `nvidia/cuda:12.2-base` to `nvidia/cuda:12.9.0-base-ubuntu22.04`, selecting a mid-line 12.x release with an explicit distro suffix over either staying on the stale 12.2 tag or jumping ahead to CUDA 13.2.

## 2026-04-24T08:53Z — initial
- agent: log/01KPZB4NNVMV0ATRGJJ4R7Y57N
- refs: [[research/JDL-65/compose-gpu-syntax-cuda-base-image-2026]]

At the start of JDL-65 (M0 — Repo, CI, and host prep), Scout verified that the CUDA base-image tag specified in the roadmap (`nvidia/cuda:12.2-base`) was stale on two axes: CUDA 12.2 is well behind current (12.9.x is recent on the 12.x line, 13.2.1 is newest as of early 2026), and the unqualified `12.2-base` form without a distro suffix is no longer how the `nvidia/cuda` registry is laid out — modern convention is strictly `<VERSION>-<FLAVOR>-<DISTRO>`. The `latest` meta-tag has been deprecated on both NGC and Docker Hub, so every reference must be fully qualified. ^p001

Alternative A was to stay on CUDA 12.2 for consistency with the original roadmap text. Alternative B was to jump to CUDA 13.2 (newest stable as of early 2026). Alternative C was to adopt `nvidia/cuda:12.9.0-base-ubuntu22.04`. We chose Alternative C. ^p002

The primary reasoning is dependency-matrix risk: PyTorch and HuggingFace wheels that Oracle will consume in M7 are still primarily built against CUDA 12.x in 2026, so committing the smoke test to CUDA 13 before Oracle's dependency matrix is pinned would create unnecessary risk. Ubuntu 22.04 is a conservative base-image floor versus 24.04, keeping the smoke-test environment aligned with the most widely tested CUDA-on-Linux surface. ^p003

Implication for M0 file-writing: the smoke-test command in `docs/host-prep-nvidia.md` (to be authored during M0) and both occurrences in `.claude/context/roadmap.md` use the updated tag. `.claude/context/roadmap.md` has already been edited (tracked as a separate `file-modified` event). ^p004
