---
id: 01KPZNZ9XN0WTVYXSE5YPFMJEC
type: decision
name: 20260424T1203Z-compose-gpu-syntax
created_at: 2026-04-24T12:03Z
created_by: log/01KPZNZ9XN0WTVYXSE5YPFMJEC
component: compose
---

## Purpose
Records the decision to adopt Compose v2's `deploy.resources.reservations.devices` block with `driver: nvidia`, `count: 1`, and `capabilities: [gpu]` as the canonical GPU reservation syntax for the Atmosphere platform, rather than the legacy top-level `runtime: nvidia` key or the Docker Python SDK's `device_requests` shape.

## 2026-04-24T12:03Z — initial
- agent: log/01KPZNZ9XN0WTVYXSE5YPFMJEC
- refs: [[research/JDL-65/compose-gpu-syntax-cuda-base-image-2026]], [[decisions/JDL-65/20260424T0853Z-cuda-base-image-tag-bump]], [[files/JDL-65/docs/host-prep-nvidia-md]]

During JDL-65 (M0) close-out, Scout research established the 2026-canonical Compose v2 GPU reservation syntax. Three historical shapes exist; only two still work. The top-level `runtime: nvidia` key is broken on recent Compose v2 — silently ignored since v2.29.7 per docker/compose#12203 — and the underlying `nvidia-docker2` / `nvidia-container-runtime` upstream repos are archived, so it is not a viable choice. The `driver: nvidia` + `capabilities: [gpu]` block under `deploy.resources.reservations.devices` is Docker's primary documented shape and works. The `driver: cdi` + `device_ids: ['nvidia.com/gpu=all']` CDI-native path also works. ^p001

We chose the `driver: nvidia` + `capabilities: [gpu]` shape. Reasoning: it matches the platform's design-doc posture already expressed in `operations.md` and `components/oracle.md`, it stays legible to readers landing in the repo from older Docker examples, and it has zero behavioral cost versus CDI on a current NVIDIA Container Toolkit — v1.18+ dispatches both shapes through the same CDI code path under the hood. ^p002

`device_requests` was considered and rejected as a compose-file key because it is not one — it is a Docker Python SDK parameter, not part of the compose-file spec. Any reference suggesting `device_requests` belongs in `compose.yml` is incorrect regardless of which driver keyword accompanies it. ^p003

Scope of applicability: the M7 Oracle service (sentiment inference on GPU) and any future GPU-consuming service. The smoke test `docker run --rm --gpus all nvidia/cuda:12.9.0-base-ubuntu22.04 nvidia-smi` is orthogonal to this decision — that command uses the Docker CLI `--gpus` flag, not a compose-file surface, and tests only host-level GPU passthrough. ^p004

This decision retrofits the design docs: `.claude/context/components/oracle.md` line 7 was edited in the same session (local-only since `.claude/` is gitignored) to replace the incorrect `runtime: nvidia with device_requests` phrasing with the canonical `deploy.resources.reservations.devices` block. That edit is tracked as a separate `file-modified` event against `.claude/context/components/oracle.md`. ^p005
