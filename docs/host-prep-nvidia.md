# Host prep — NVIDIA Container Toolkit on CachyOS

Operator-facing install and verification guide for the NVIDIA Container
Toolkit on the Atmosphere CachyOS deploy host. The end-state is a successful
`docker run --gpus all ... nvidia-smi` from the host, which is the M0 (JDL-65)
acceptance gate and the prerequisite for Oracle's GPU reservation in M7.

For full source citations, background, and deeper troubleshooting detail, see
[`vault/research/JDL-65/nvidia-container-toolkit-cachyos.md`](../vault/research/JDL-65/nvidia-container-toolkit-cachyos.md).

## Prerequisites

This guide assumes the host is already in the following state:

- CachyOS Linux with a working NVIDIA kernel driver. `nvidia-smi` run as a
  normal user on the host returns a populated table with a driver version and
  the GPU model. If it does not, install a driver package first
  (`nvidia-open-dkms` is the CachyOS default for Turing+ GPUs; `nvidia-dkms` is
  the proprietary alternative) — driver install is out of scope here.
- Docker is installed and running as a rootful systemd service
  (`systemctl is-active docker` returns `active`). Atmosphere does not use
  rootless Docker; the remediations below assume rootful only.
- `pacman` is configured with the default CachyOS mirrorlist, so
  `cachyos-extra-v4` takes precedence over `extra`. The toolkit package is
  pulled from the official repo — **not** from the AUR and **not** from an
  NVIDIA-hosted repository.

## Install

Four commands, in order:

```bash
# 1. Install the toolkit from the official CachyOS repo (cachyos-extra-v4).
sudo pacman -S --needed nvidia-container-toolkit

# 2. Write the `nvidia` runtime entry into /etc/docker/daemon.json.
sudo nvidia-ctk runtime configure --runtime=docker

# 3. Restart Docker so it picks up the new runtime definition.
sudo systemctl restart docker

# 4. Smoke test — this is the M0 acceptance command.
docker run --rm --gpus all nvidia/cuda:12.9.0-base-ubuntu22.04 nvidia-smi
```

Step 2 merges only the `runtimes.nvidia` block into `/etc/docker/daemon.json`.
The resulting file looks like:

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

Do **not** add `"default-runtime": "nvidia"` to this file. Doing so would route
every Atmosphere container — Postgres, Redpanda, Grafana, all of them —
through the NVIDIA hook, which is wasted work on containers that never touch
the GPU and a real source of startup overhead and surprising failure modes.
The correct pattern is per-service GPU reservation; see
[Compose-level GPU syntax](#compose-level-gpu-syntax-forward-looking) below.

## Verify

The M0 acceptance command:

```bash
docker run --rm --gpus all nvidia/cuda:12.9.0-base-ubuntu22.04 nvidia-smi
```

Expected output is a populated `nvidia-smi` table showing the same driver
version that host-side `nvidia-smi` returns, along with the GPU model and
current memory / utilisation figures. Shape (truncated):

```
+-----------------------------------------------------------------------------+
| NVIDIA-SMI <version>       Driver Version: <version>    CUDA Version: <ver> |
|-------------------------------+----------------------+----------------------+
| GPU  Name        Persistence-M| Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp  Perf  Pwr:Usage/Cap|         Memory-Usage | GPU-Util  Compute M. |
|===============================+======================+======================|
|   0  NVIDIA ...               | ...                  | ...                  |
+-------------------------------+----------------------+----------------------+
```

If the driver version printed inside the container matches what host-side
`nvidia-smi` shows, the toolkit path is working end-to-end. If the command
errors instead, jump to [Troubleshooting](#troubleshooting).

## CachyOS-specific notes

**Kernel / DKMS alignment.** CachyOS's `linux-cachyos` kernel is patched and
moves faster than Arch mainline. The NVIDIA out-of-tree modules (`nvidia-dkms`
or `nvidia-open-dkms`) occasionally lag a fresh kernel bump by minutes to
hours. If Docker GPU access breaks immediately after a kernel upgrade, the
first diagnostic is:

```bash
dkms status | grep nvidia
```

A healthy system shows the NVIDIA module built against the running kernel
version. If it is missing or shows a stale kernel, `sudo pacman -Syu` pulls
the matched DKMS build; this usually resolves it within one update cycle.
Users who want strict kernel/module lockstep can run the bundled
`linux-cachyos-nvidia-open` (or `linux-cachyos-lts-nvidia-open`) packages
instead of the split `linux-cachyos` + `nvidia-open-dkms` setup.

**`nvidia-open` vs proprietary.** The toolkit is driver-agnostic. It consumes
`libnvidia-ml` from the userspace stack, not the kernel module directly, so
both `nvidia-open-dkms` and the proprietary `nvidia-dkms` work identically
with `--gpus all`. CachyOS forum reports of
`could not select device driver "" with capabilities: [[gpu]]` errors
specifically on `nvidia-open` setups reduce in every case to either the
toolkit not being installed or Docker not being restarted after
`nvidia-ctk runtime configure` — not a driver-flavour incompatibility.

**`nvidia-uvm` module.** The toolkit depends on `nvidia-uvm` (unified memory)
being loaded alongside the base `nvidia` module. The DKMS packages install a
modprobe dependency chain so `modprobe nvidia` drags `nvidia-uvm` in
automatically. A successful host-side `nvidia-smi` is sufficient evidence
that the module stack is primed — if `nvidia-uvm` were missing, host-side
`nvidia-smi` would fail, not just the container path. No explicit
`modules-load.d` entry is needed.

**cgroup v2.** CachyOS ships systemd cgroup v2 unified hierarchy by default
and Docker uses the `systemd` cgroup driver by default. The historical
"Failed to initialize NVML: Unknown Error" failure that required
`systemd.unified_cgroup_hierarchy=false` or `no-cgroups = true` is resolved
in every currently-supported toolkit version, including 1.19.0. No special
cgroup configuration is needed. The `no-cgroups = true` workaround is only
relevant to rootless Docker, which Atmosphere does not use.

## Troubleshooting

| Symptom                                                                | Likely cause                                                                          | Fix                                                                                                                                       |
| ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `could not select device driver "" with capabilities: [[gpu]]`         | Toolkit not installed, or Docker not restarted after `nvidia-ctk runtime configure`   | Re-run the four install commands above in order; verify `/etc/docker/daemon.json` has the `runtimes.nvidia` block.                        |
| `Failed to initialize NVML: Unknown Error` on a freshly-booted host    | `nvidia-uvm` not yet loaded because nothing has exercised CUDA on the host since boot | Run `nvidia-smi` once on the host to trigger module load, then retry the container.                                                       |
| Same NVML error right after a kernel upgrade                           | `nvidia-*-dkms` module did not rebuild against the new kernel                         | `dkms status \| grep nvidia`; if the module is missing or stale, `sudo pacman -Syu` to pull a matching DKMS build and reboot if required. |
| `docker: Error response from daemon: unknown runtime specified nvidia` | `/etc/docker/daemon.json` is missing the `runtimes.nvidia` block                      | Re-run `sudo nvidia-ctk runtime configure --runtime=docker`, inspect the file, `sudo systemctl restart docker`.                           |
| Driver version inside the container does not match the host            | Stale container image cached locally, or host driver updated without a Docker restart | `docker pull nvidia/cuda:12.9.0-base-ubuntu22.04` to refresh, then `sudo systemctl restart docker` and retry.                             |

## Compose-level GPU syntax (forward-looking)

Atmosphere's M0 scope stops at the host-level smoke test above. Oracle — the
sole GPU consumer — does not land in `compose.yml` until M7. This section
documents the syntax that Oracle will use so the operator knows what to
expect, and is **informational**: there is no compose file to edit at M0.

Oracle reserves the GPU through `deploy.resources.reservations.devices` with
`driver: nvidia`, `count: 1`, `capabilities: [gpu]`. The shape is:

```yaml
services:
  oracle:
    image: atmosphere/oracle:latest
    deploy:
      resources:
        limits:
          cpus: "2"
          memory: 2560M
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    environment:
      ORACLE_DEVICE: cuda
```

Two things to avoid, both of which surface in older examples and ask-an-LLM
output:

- **Do not** add a top-level `runtime: nvidia` key to the service. The field
  is silently ignored on recent Docker Compose v2 (since v2.29.7) and is not
  a safety-net alongside `deploy.resources.reservations.devices` — it is a
  source of confusion for the next reader. The `reservations.devices` block
  is the only GPU declaration Oracle needs.
- **Do not** set `"default-runtime": "nvidia"` in `/etc/docker/daemon.json`,
  as already noted in the [Install](#install) section. The per-service
  `reservations.devices` pattern is correct; a global default-runtime flip
  affects every other container on the host.

`count: 1` means "any one GPU" and is correct for the single-GPU Atmosphere
host. `capabilities: [gpu]` is required — omitting it fails validation with
a misleading "device driver not set" error.
