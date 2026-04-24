---
id: 01KPZC9P4VJSCGRWV2S3GNEB6Z
type: file
name: CONTRIBUTING.md
created_at: 2026-04-24T09:14Z
created_by: log/01KPZC9P4VJSCGRWV2S3GNEB6Z
component: repo
---

## Purpose
Tracks the lifecycle of `CONTRIBUTING.md` at the repo root — the contributor onboarding guide for the Atmosphere monorepo. Covers prerequisites, workspace setup, local lint/test/format gates that mirror CI, branch and commit conventions, and the local-build deploy model that bounds how code reaches the running host (no registry, `git pull && docker compose build && up -d`).

## 2026-04-24T09:14Z — initial
- agent: log/01KPZC9P4VJSCGRWV2S3GNEB6Z
- refs: [[decisions/JDL-65/20260424T0853Z-ruff-only-drops-black]], [[files/JDL-65/pyproject-toml]], [[files/JDL-65/pre-commit-config-yaml]], [[files/JDL-65/compose-yml]]

Forge created `CONTRIBUTING.md` at the repo root as part of JDL-65 M0 scaffolding and committed it as `9ed7612` on branch `JDL-65-m0-repo-ci-host-prep` with message `docs(JDL-65): add CONTRIBUTING.md describing local-build deploy model`. The commit was scoped to the single file via `git add CONTRIBUTING.md` followed by `git commit -m <msg> -- CONTRIBUTING.md`, leaving the working tree's pre-existing unstaged `vault/` deletions and untracked `CLAUDE.md` alone — preserving the one-invocation-one-file contract. ^p001

The file is organized top-down from environment prerequisites to day-to-day contributor workflow. The prerequisites section names Python 3.12 (matching the `requires-python = "==3.12.*"` floor in [[files/JDL-65/pyproject-toml]]), uv as the workspace manager, Docker with Compose v2, the NVIDIA Container Toolkit for GPU-touching services (Oracle in M7), and Node (via `npx`) for the Prettier gate. The setup section reduces to two commands: `uv sync` to materialize the workspace virtualenv and `uv run pre-commit install` to wire the local hooks declared in [[files/JDL-65/pre-commit-config-yaml]] into the checkout. ^p002

The local gates section enumerates the same commands CI runs, without asserting the CI workflow file's path — `ruff check`, `ruff format --check`, `pytest`, `dbt parse --profiles-dir ./profiles --no-partial-parse`, `prettier --check`, and `docker compose config`. Ruff is presented as the sole Python linter and formatter, matching the Alternative B choice captured in [[decisions/JDL-65/20260424T0853Z-ruff-only-drops-black]] — no black. `docker compose config` exercises the root [[files/JDL-65/compose-yml]] manifest, which is the M0 acceptance gate for a parseable compose surface even while `services: {}` is empty. ^p003

Conventions land in two short sections. Branches follow `JDL-XXX-<kebab>` (e.g., `JDL-65-m0-repo-ci-host-prep`). Commit subjects follow `type(JDL-XXX): subject` where `type` is one of the conventional-commits set (`feat`, `fix`, `docs`, `build`, `ci`, `chore`, `refactor`, `test`). The local-build deploy model is described as the canonical path for code reaching the host: no container registry, no CI image pipeline — `git pull && docker compose build <svc> && docker compose up -d <svc>` rolls forward, and `git checkout <sha> && docker compose build <svc> && docker compose up -d <svc>` rolls back. This is the contributor-facing restatement of the Prefect-section commitment that the worker image is built locally on the deploy host. ^p004

Forge surfaced one design-vs-constraints conflict at authoring time: the invocation Design asked for a one-line pointer to `docs/host-prep-nvidia.md`, but Constraints forbade referencing directories that don't exist yet. `docs/` exists on disk with only a `.gitkeep`; `docs/host-prep-nvidia.md` does not. Forge followed the Constraint and used a softer phrasing — "see `docs/` for host prep notes" — which points at the existing directory without asserting the specific file exists. The Related-files section of the invocation also named `.github/workflows/ci.yml` and `.pre-commit-config.yaml`; only the latter existed at commit time (the former directory was empty), so the document describes the gates as "the same commands CI runs" without naming a workflow file and describes `uv run pre-commit install` as wiring hooks into the local checkout without asserting a config file path. ^p005
