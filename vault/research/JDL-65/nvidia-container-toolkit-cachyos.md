---
id: nvidia-container-toolkit-cachyos
type: research
name: NVIDIA Container Toolkit install on CachyOS (M0)
created_at: 2026-04-24
created_by: scout
component: host-prep
---

## Purpose

Establish the canonical 2026 install sequence for NVIDIA Container Toolkit on CachyOS so that `docker run --rm --gpus all <cuda-base-image> nvidia-smi` succeeds and returns the driver version — M0 (JDL-65) acceptance gate. Captures package sourcing, `nvidia-ctk runtime configure` behavior, runtime-mode choice (legacy vs CDI), daemon.json shape, and CachyOS-specific gotchas (kernel module alignment, cgroup v2, nvidia-open vs proprietary).

## Entry — initial — 2026-04-24 — scout

**agent:** scout
**refs:** [[.claude/context/roadmap.md]] (M0), [[.claude/context/operations.md]] (Deployment — GPU)

### Package sourcing ^p001

`nvidia-container-toolkit` is in Arch's official `extra` repo at version `1.19.0-1` (last updated 2026-03-14) with dependencies `glibc`, `libnvidia-container=1.19.0`, and `go` (build-time). CachyOS mirrors this in its `cachyos-extra-v4` repo at `1.19.0-1.1` — same upstream source tree under `archlinux/packaging/packages/nvidia-container-toolkit`, built against CachyOS's `x86_64_v4` microarchitecture baseline. Both are `pacman -S`-installable; no AUR needed, no NVIDIA-hosted repo needed. CachyOS's repo takes precedence over Arch's in the default pacman mirrorlist, so `pacman -S nvidia-container-toolkit` picks up the CachyOS-rebuilt variant automatically. ^p002

The package pulls in `libnvidia-container` as its only non-glibc runtime dep — the old `libnvidia-container-tools` dep from pre-1.17 releases is now folded into the main package. No separate `nvidia-container-runtime` package to chase; the runtime binary ships inside `nvidia-container-toolkit`. ^p003

### Host driver prerequisite ^p004

The toolkit does not install or manage the kernel driver — that is a separate stack the host must already have working. On CachyOS in 2026 the canonical driver options, tracked through `chwd` (CachyOS Hardware Detection tool) and surfaced by CachyOS's community NVIDIA installer script, are: ^p005

- **`nvidia-open-dkms`** — the open-source kernel module (NVIDIA's out-of-tree GPL-licensed modules, Turing+ GPUs only). Recommended by CachyOS for newer GPUs and is what `chwd` picks by default on supported hardware.
- **`nvidia-dkms`** — the proprietary kernel module, rolling release (currently on the 590xx branch).
- **`nvidia-580xx-dkms` / `nvidia-590xx-dkms`** — pinned branch packages that exist alongside the rolling packages after CachyOS's March 2026 "NVIDIA Driver Restructuring" announcement, which split the rolling `nvidia-dkms` package into explicit branch variants and replaced the "NVIDIA Closed" metapackage with `nvidia-580xx-utils` as the stable foundation.
- **`nvidia-utils`** (or `nvidia-580xx-utils` / `nvidia-590xx-utils` branch variants) — userspace libraries (`libnvidia-ml.so`, `nvidia-smi`, the CUDA runtime shims). **This is the critical package for Docker GPU access** because `nvidia-container-toolkit` bind-mounts these libraries from the host into the container at runtime.

For Atmosphere's scope — a GPU already working for host-side use is assumed — the prerequisite check is just `nvidia-smi` on the host returning a driver version. If that works, the userspace libraries are already present and the container toolkit has what it needs to mount them. ^p006

### nvidia-open vs proprietary for Docker ^p007

Both work with `nvidia-container-toolkit`; the toolkit is driver-agnostic by design — it consumes `libnvidia-ml` via the userspace stack, not the kernel module directly. There have been CachyOS forum reports of the `could not select device driver "" with capabilities: [[gpu]]` error specifically on nvidia-open setups, but those reduce in every case to toolkit not being installed or Docker not being restarted after `nvidia-ctk runtime configure` — not a driver-flavor incompatibility. Once the toolkit is installed and Docker is restarted, `--gpus all` works identically on nvidia-open-dkms and nvidia-dkms. No reason to prefer one over the other for the Docker path specifically. ^p008

### Kernel module alignment gotcha ^p009

CachyOS's `linux-cachyos` kernel is patched and moves faster than the Arch mainline; NVIDIA's out-of-tree modules occasionally lag. The documented failure mode is a DKMS build break after a kernel upgrade — the new kernel installs, the old module is invalidated, DKMS tries to rebuild, and the module version fails against a kernel API change. CachyOS backports NVIDIA patches into the `nvidia-dkms` / `nvidia-open-dkms` packages as soon as upstream publishes them, but the window between `linux-cachyos` bumping and the matching `nvidia-*-dkms` bump landing can be hours-to-days. The operational consequence for M0 is: if the host has just upgraded the kernel and Docker GPU access breaks, the first diagnostic step is `dkms status | grep nvidia` to confirm the module actually built against the running kernel, followed by `pacman -Syu` to pull any newer `nvidia-*-dkms` package. This is a host-ops concern, not an Atmosphere-code concern — flagged for the runbook. ^p010

Related: the `linux-cachyos-nvidia-open` and `linux-cachyos-lts-nvidia-open` packages exist as bundled kernel+module combos for users who want the versioning guaranteed in lockstep. They are an alternative to the standalone `linux-cachyos` + `nvidia-open-dkms` split and sidestep the alignment-window issue entirely; the tradeoff is less flexibility in kernel choice. Not required for M0, mentioned for completeness. ^p011

### Install sequence ^p012

Assuming a working host driver (`nvidia-smi` returns a version), the M0 install is four commands: ^p013

```bash
# 1. Install the toolkit from the official repo.
sudo pacman -S --needed nvidia-container-toolkit

# 2. Write NVIDIA runtime config into /etc/docker/daemon.json.
sudo nvidia-ctk runtime configure --runtime=docker

# 3. Restart Docker so it picks up the new runtime definition.
sudo systemctl restart docker

# 4. Verify — this is the M0 acceptance command.
docker run --rm --gpus all nvidia/cuda:12.2-base nvidia-smi
```

Step 4 should print the same driver version as host-side `nvidia-smi`. If it prints a container runtime error, see §Troubleshooting. ^p014

### What `nvidia-ctk runtime configure --runtime=docker` writes ^p015

The command reads `/etc/docker/daemon.json` if it exists (creates it if not), merges the `runtimes.nvidia` block in, and writes it back. It emits three log lines: ^p016

```
INFO[0000] Loading config from /etc/docker/daemon.json
INFO[0000] Wrote updated config to /etc/docker/daemon.json
INFO[0000] It is recommended that docker daemon be restarted.
```

The resulting `/etc/docker/daemon.json` contains: ^p017

```json
{
  "runtimes": {
    "nvidia": {
      "args": [],
      "path": "nvidia-container-runtime"
    }
  }
}
```

That block alone is what `--gpus all` needs — Docker's `--gpus` flag implicitly selects the `nvidia` runtime when it is present in the runtimes map. **No `default-runtime: nvidia` is written by default, and none is needed for Atmosphere.** Setting `default-runtime: nvidia` globally would route every container — Postgres, Redpanda, Grafana, Prometheus, all eighteen containers — through the NVIDIA hook, which is wasted work for containers that never touch the GPU and a small but real source of startup overhead and failure modes. The correct pattern is per-service: `--gpus all` on `docker run`, or `deploy.resources.reservations.devices` with `driver: nvidia` in `compose.yml` (scoped to Oracle only, per `.claude/context/components/oracle.md`). Out of scope for this topic. ^p018

### Legacy vs CDI mode ^p019

Runtime mode is a separate axis from the Docker-integration plumbing. The `nvidia-container-runtime` binary supports two modes, selected via `/etc/nvidia-container-toolkit/config.toml` under `nvidia-container-runtime.mode`: ^p020

- **Legacy mode** — the runtime inspects environment variables (`NVIDIA_VISIBLE_DEVICES`, `NVIDIA_DRIVER_CAPABILITIES`) on the container and dynamically bind-mounts driver libraries and device files. This is what `--gpus all` has used since the toolkit's inception.
- **CDI mode** — the runtime reads a static CDI (Container Device Interface) YAML spec describing the GPU devices and mounts exactly what the spec declares. The spec lives at `/var/run/cdi/nvidia.yaml` and is generated by the `nvidia-cdi-refresh` systemd service, added in toolkit v1.18.0 and present in the 1.19.0 package. The service auto-regenerates the spec on driver install/upgrade and boot, so on a stable host it is maintenance-free.

The default runtime mode in 1.19.0 is no longer strict legacy — recent releases use a `jit-cdi` (just-in-time CDI) hybrid that generates the spec on the fly per-container while still accepting legacy env-var contracts. For Atmosphere the practical answer is: **stick with the default, do not manually switch to CDI**. `--gpus all` continues to work, `deploy.resources.reservations.devices` continues to work, the acceptance test continues to work. Forcing CDI (`sudo nvidia-ctk config --in-place --set nvidia-container-runtime.mode=cdi` plus Docker's `--device=nvidia.com/gpu=all` syntax) is a Podman-first workflow and adds steps without buying anything at M0. Revisit only if the toolkit deprecates the hybrid default in a future release, which is not signaled in the 1.19.0 release notes. ^p021

### cgroup v2 behavior ^p022

CachyOS ships systemd cgroup v2 unified hierarchy by default (same as current Arch). The historical "Failed to initialize NVML: Unknown Error" failure mode from 2020-2022 — where early nvidia-container-toolkit versions could not talk to cgroup v2 and required either `systemd.unified_cgroup_hierarchy=false` on the kernel cmdline or `no-cgroups = true` in the toolkit config — is **resolved in every currently-supported toolkit version**. Docker engine's cgroup driver is `systemd` by default on Arch/CachyOS, which matches what the toolkit expects. No special cgroup configuration is needed for rootful Docker GPU access on 1.19.0. ^p023

The only cgroup workaround still relevant in 2026 is for **rootless Docker**, which Atmosphere does not use — the NVIDIA runtime cannot configure cgroups as a non-root user, and rootless setups require `no-cgroups = true` plus manual device passthrough. Since every Atmosphere compose service runs under the default rootful Docker daemon, this branch does not apply. Flagged in case a contributor tries to run the stack under rootless Docker and hits it. ^p024

A 1.19.0-specific regression exists for MIG (Multi-Instance GPU) setups — `nvidia-cap1`/`nvidia-cap2` cgroup access fails for non-privileged MIG containers (NVIDIA/nvidia-container-toolkit#1740). MIG is not in scope for Atmosphere; the Oracle container reserves one whole GPU rather than a MIG slice. ^p025

### `nvidia-uvm` module loading ^p026

The container toolkit depends on `nvidia-uvm` (unified memory) and `nvidia-modeset` being loaded on the host in addition to the base `nvidia` module. The DKMS packages install a `/usr/lib/modprobe.d/nvidia-utils.conf` (or equivalent) that declares the dependency chain, so `modprobe nvidia` drags `nvidia-uvm` in automatically. `nvidia-smi` executing successfully on the host is sufficient evidence that all three are loaded — if a module were missing, `nvidia-smi` itself would fail, not just the container path. No explicit `modules-load.d` entry is required in the Atmosphere compose or host config. ^p027

If the host has just been rebooted and `nvidia-smi` works but `docker run --gpus` fails with `Failed to initialize NVML: Unknown Error`, the specific suspect is `nvidia-uvm` not being loaded yet because nothing has exercised CUDA on the host. Running `nvidia-smi` once on the host triggers the load; this is why some docs recommend an `nvidia-modprobe` or `modprobe nvidia-uvm` step in host-provisioning scripts. Not load-bearing on CachyOS where `nvidia-smi` is almost always already primed by a desktop session, but worth knowing for truly-headless servers. ^p028

### Troubleshooting matrix ^p029

| Symptom | Likely cause | Fix |
|---|---|---|
| `could not select device driver "" with capabilities: [[gpu]]` | `nvidia-container-toolkit` not installed, or Docker not restarted after `nvidia-ctk runtime configure` | `pacman -S nvidia-container-toolkit && sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker` |
| `Failed to initialize NVML: Unknown Error` on fresh boot | `nvidia-uvm` not yet loaded | Run `nvidia-smi` once on the host to trigger load |
| Same error after a kernel upgrade | `nvidia-*-dkms` module didn't rebuild against new kernel | `dkms status \| grep nvidia`; if missing/failed, `sudo pacman -Syu` to pull matching DKMS package |
| `docker: Error response from daemon: unknown runtime specified nvidia` | `/etc/docker/daemon.json` missing the runtimes block | Re-run `sudo nvidia-ctk runtime configure --runtime=docker`; verify the file contents; restart Docker |
| Works rootful, fails rootless | cgroup v2 + rootless Docker is unsupported by default | Set `no-cgroups = true` in `/etc/nvidia-container-toolkit/config.toml`; or use rootful Docker (matches Atmosphere) |

^p030

### Summary for the contributor-facing doc ^p031

The CONTRIBUTING / README step for M0 should be a short block: prerequisite is working `nvidia-smi` on the host; run `sudo pacman -S --needed nvidia-container-toolkit`, `sudo nvidia-ctk runtime configure --runtime=docker`, `sudo systemctl restart docker`; verify with `docker run --rm --gpus all nvidia/cuda:12.2-base nvidia-smi`. Do not set `default-runtime: nvidia`. Do not manually switch to CDI mode. If the verify fails, `dkms status` is the first diagnostic. ^p032

### Sources ^p033

- [Arch Linux package — nvidia-container-toolkit 1.19.0-1](https://archlinux.org/packages/extra/x86_64/nvidia-container-toolkit/)
- [CachyOS package — nvidia-container-toolkit 1.19.0-1.1 (cachyos-extra-v4)](https://packages.cachyos.org/package/cachyos-extra-v4/x86_64_v4/nvidia-container-toolkit)
- [NVIDIA Container Toolkit — Installing the NVIDIA Container Toolkit (official)](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
- [NVIDIA Container Toolkit — Support for Container Device Interface (CDI)](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/cdi-support.html)
- [NVIDIA Container Toolkit — Changelog (GitHub)](https://github.com/NVIDIA/nvidia-container-toolkit/blob/main/CHANGELOG.md)
- [CachyOS Forum — NVIDIA Driver Restructuring (580xx/590xx)](https://discuss.cachyos.org/t/announcement-maintenance-notice-nvidia-driver-restructuring-580xx-590xx/20010)
- [CachyOS Forum — Docker with NVIDIA open driver](https://discuss.cachyos.org/t/how-to-run-docker-image-with-nvidia-gpu-on-cachyos-with-nvidia-open-driver/5281)
- [Arch Forums — Docker with GPU: Failed to initialize NVML (cgroup v2 history)](https://bbs.archlinux.org/viewtopic.php?id=266915)
- [sleeplessbeastie — How to use NVIDIA Container Toolkit with Docker (2025)](https://sleeplessbeastie.eu/2025/11/27/how-to-use-nvidia-container-toolkit-with-docker/)
- [dev.to (pakos) — Access Nvidia GPU inside docker container in Arch](https://dev.to/pakos/access-nvidia-gpu-inside-docker-container-in-arch-linux-4k6b)

^p034
