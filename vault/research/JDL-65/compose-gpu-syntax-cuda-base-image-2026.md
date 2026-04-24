---
id: compose-gpu-syntax-cuda-base-image-2026
type: research
name: Docker Compose v2 GPU reservation syntax and CUDA base-image tag (2026)
created_at: 2026-04-24
created_by: scout
component: compose
---

## Purpose

Pin down the 2026-canonical Docker Compose v2 GPU reservation syntax for Oracle's single-GPU passthrough, and fix the exact CUDA base-image tag the M0 (JDL-65) smoke test should use for `docker run --rm --gpus all <tag> nvidia-smi`. Resolves which of the three historical shapes — top-level `runtime: nvidia`, `deploy.resources.reservations.devices` with `driver: nvidia`, and the newer `driver: cdi` + `nvidia.com/gpu=...` — applies on Docker Compose v2 + NVIDIA Container Toolkit v1.18+/v1.19 on CachyOS (Arch-based).

## Entry — initial — 2026-04-24 — scout

**agent:** scout
**refs:** [[.claude/context/roadmap.md]] (M0), [[.claude/context/components/oracle.md]], [[.claude/context/operations.md]] (GPU section), NVIDIA Container Toolkit v1.18.0 / v1.19.0 release notes, Docker Compose Deploy Specification, Arch Linux `nvidia-container-toolkit` 1.19.0-1 (2026-03-14)

### Three historical shapes, only two still work ^p001

Compose has accumulated three ways to request an NVIDIA GPU and they correspond to three different eras of the toolkit. Top-level `runtime: nvidia` was the original `nvidia-docker2` / `nvidia-container-runtime` pattern; it depended on registering `"runtimes": {"nvidia": ...}` in `/etc/docker/daemon.json` and then naming that runtime on the service. `deploy.resources.reservations.devices` with `driver: nvidia` is the Compose-native pattern that landed when Docker 19.03 added first-class `--gpus` support, and is what Docker's own "Enable GPU support" page still shows as the primary example. `deploy.resources.reservations.devices` with `driver: cdi` + `device_ids: ['nvidia.com/gpu=all']` is the CDI-era pattern introduced as the toolkit moved to auto-generated CDI specs. As of April 2026, only the second and third shapes are first-class; the top-level `runtime: nvidia` path has been reported broken on recent Compose v2 (docker/compose#12203, with the `runtime` field silently ignored starting at v2.29.7) and NVIDIA's old `nvidia-docker` / `nvidia-container-runtime` repos are archived. Don't use it. ^p002

### The CDI pivot in NVIDIA Container Toolkit v1.18.0 ^p003

Toolkit v1.18.0 was a structural shift: the NVIDIA Container Runtime's default mode flipped from `legacy` to a just-in-time-generated CDI spec, and the package now installs a systemd unit (`nvidia-cdi-refresh.service`) that keeps `/etc/cdi/nvidia.yaml` in sync with the devices on the host. Legacy mode is still supported for cases that require it but is explicitly deprecated. Practical consequence for us: on a current NVIDIA Container Toolkit install, `/etc/cdi/nvidia.yaml` already exists and Docker's own CDI integration can reference `nvidia.com/gpu=all` directly without `nvidia-ctk runtime configure --runtime=docker` being the pivotal step it once was. v1.19.0 (March 2026, and the version currently in Arch `extra` as `nvidia-container-toolkit 1.19.0-1`) is a smaller feature release on top of v1.18 — IGX 2.0 Thor support, Tegra CUDA forward-compat — and carries the same CDI-by-default posture. ^p004

### What the design doc already picks — and why that's still right ^p005

[[.claude/context/operations.md]] specifies Oracle's reservation as `deploy.resources.reservations.devices` with `driver: nvidia`, `count: 1`, `capabilities: [gpu]`, plus the NVIDIA Container Toolkit on the host. That is shape #2 above. In April 2026 this is still the path Docker's own `docs.docker.com/compose/how-tos/gpu-support/` leads with and the one most examples across the ecosystem render. Behind the scenes on a v1.18+ toolkit, the `nvidia` runtime driver is itself now dispatching through CDI mode, so shape #2 and shape #3 converge on the same device-injection path — the difference is declarative surface, not runtime behavior. Keep shape #2 for v1: it matches the design doc verbatim, stays readable for anyone landing here from older examples, and does not require us to reference CDI device IDs (`nvidia.com/gpu=all`) that a future non-NVIDIA-GPU contributor might find opaque. The cost of holding the line is zero — no behavior difference versus CDI on this toolkit version. ^p006

### Canonical Oracle compose snippet ^p007

```yaml
services:
  oracle:
    image: atmosphere/oracle:latest
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2560M   # 2.5 GB hard cap from operations.md
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    environment:
      ORACLE_DEVICE: cuda
```

`count: 1` and `device_ids` are mutually exclusive — pick `count` for "any one GPU" (correct here; the host has one GPU and Oracle is the only GPU consumer), pick `device_ids: ['0']` only when pinning by host index. `capabilities: [gpu]` is required — omitting it fails validation. ^p008

### Smoke-test image tag — use 12.9.0-base-ubuntu22.04 ^p009

The `nvidia/cuda` repo on Docker Hub carries CUDA 13.2.1 as the newest version as of early 2026 (`13.2.1-base-ubuntu22.04` and `13.2.1-base-ubuntu24.04` both exist). The 12.x line continues in parallel, with `12.9.0-base-ubuntu22.04` as a recent, well-known tag on it; Docker's own current compose GPU docs use `12.9.0-base-ubuntu22.04` in the canonical smoke-test example. The tag in our own [[.claude/context/roadmap.md]] M0 acceptance — `nvidia/cuda:12.2-base` — is stale: (a) CUDA 12.2 is well behind current, and (b) the unqualified `12.2-base` form without a distro suffix no longer exists on the registry; the modern naming convention is strictly `<VERSION>-<FLAVOR>-<DISTRO>` (e.g., `12.9.0-base-ubuntu22.04`). The `latest` meta-tag has been deprecated on both NGC and Docker Hub for CUDA images, so every reference must be fully qualified. ^p010

For the M0 smoke test, pick `nvidia/cuda:12.9.0-base-ubuntu22.04`. Rationale: 12.9 matches the CUDA 12.x toolchain the HuggingFace `transformers` + PyTorch wheels Oracle will eventually consume have been built against (PyTorch still primarily ships CUDA 12.x wheels in 2026); Ubuntu 22.04 is a conservative pick for a base image (24.04 is supported but less battle-tested across the ecosystem); and staying on 12.x avoids coupling the smoke test to CUDA 13 before Oracle's actual dependency matrix has been pinned. Both `12.9.0-base-ubuntu22.04` and `13.2.1-base-ubuntu22.04` would pass the smoke test; the choice is about not over-committing. ^p011

### Updated M0 acceptance command ^p012

```bash
docker run --rm --gpus all nvidia/cuda:12.9.0-base-ubuntu22.04 nvidia-smi
```

`--gpus all` remains the correct CLI flag on Docker ≥ 19.03 and works orthogonally to the compose-file surface. On a v1.18+ toolkit this is automatically satisfied through CDI under the hood. The smoke test only validates host-level passthrough; it does not exercise any compose configuration. Run it before `docker compose config` on the compose stack so a passthrough problem surfaces as a driver/toolkit issue rather than as a compose YAML issue. ^p013

### CachyOS / Arch specifics ^p014

CachyOS inherits Arch's package graph, so `pacman -S nvidia-container-toolkit` pulls the Arch `extra` package at 1.19.0-1 (last signed 2026-03-13). After install, the canonical one-shot is `sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker` — this writes the `nvidia` runtime entry into `/etc/docker/daemon.json` so that shape #2 (`driver: nvidia`) resolves on Docker's side. On v1.18+ this also enables the `nvidia-cdi-refresh.service` systemd unit that keeps `/etc/cdi/nvidia.yaml` current, which is what lets Docker's native CDI integration answer `--gpus all` / `driver: nvidia` / `driver: cdi` requests uniformly. No Arch-specific deviation from the mainline flow. ^p015

### Gotchas ^p016

- `runtime: nvidia` at the top level of a service is silently ignored on recent Compose v2 (docker/compose#12203). If you see it in old examples or ask-an-LLM output, delete it — do not add it alongside the `deploy.resources.reservations.devices` block "for safety." It's not safety; it's a near-certain source of confusion when a future reader tries to reproduce the setup. ^p017
- `deploy.resources.reservations.devices` historically required Swarm mode — it does not anymore on Compose v2, but some docs still say so. Ignore that caveat; Compose v2 honors the `reservations.devices` block in plain `docker compose up` without Swarm. ^p018
- The `capabilities: [gpu]` field is required, not optional. Omitting it fails validation with "device driver not set" rather than silently ignoring — which is fine, just worth knowing when skimming an error. ^p019
- `count: all` and `count: 1` are both valid; `count: all` pins every host GPU (overkill and wrong here — Oracle is the only GPU consumer but we want the reservation shape to stay stable if a second GPU-using service ever arrives). Stick with `count: 1`. ^p020
- The `nvidia/cuda` Docker Hub `latest` tag is deprecated (explicit callout on the image page). Always fully qualify: `<VERSION>-<FLAVOR>-<DISTRO>`. ^p021
- If the stack ever needs to run on a GPU-less CI host, the compose `deploy.resources.reservations.devices` block is not an error on a non-GPU host — Docker silently skips the reservation — but the container will come up without a GPU, and Oracle needs to fall back to `ORACLE_DEVICE=cpu` explicitly (already documented in [[.claude/context/components/oracle.md]]). Do not rely on the reservation block alone to force a failure. ^p022

### Sources ^p023

- Docker Compose GPU support: https://docs.docker.com/compose/how-tos/gpu-support/
- Docker Compose Deploy Specification: https://docs.docker.com/reference/compose-file/deploy/
- Docker CDI support: https://docs.docker.com/build/building/cdi/
- NVIDIA Container Toolkit install guide: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html
- NVIDIA Container Toolkit release notes: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/release-notes.html
- NVIDIA Container Toolkit CDI support: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/cdi-support.html
- NVIDIA sample workload (smoke test): https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/sample-workload.html
- docker/compose#12203 (runtime: nvidia silently ignored): https://github.com/docker/compose/issues/12203
- nvidia/cuda Docker Hub: https://hub.docker.com/r/nvidia/cuda
- Arch Linux nvidia-container-toolkit 1.19.0-1: https://archlinux.org/packages/extra/x86_64/nvidia-container-toolkit/
- NVIDIA container-images CUDA supported-tags: https://gitlab.com/nvidia/container-images/cuda/blob/master/doc/supported-tags.md
