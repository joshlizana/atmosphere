---
id: 01KPZC8HKD9PR2PHY5DDR3HFYC
type: file
name: README.md
created_at: 2026-04-24T09:13Z
created_by: log/01KPZC8HKD9PR2PHY5DDR3HFYC
component: repo
---

## Purpose
Tracks the lifecycle of the repository root `README.md` — the one-page repo front that orients a fresh contributor to Atmosphere. It carries the platform one-paragraph pitch, the source-of-truth posture, an Architecture section that delegates full diagrams to `.claude/context/architecture.md`, the current-milestone statement, and a Getting started section pointing at `CONTRIBUTING.md`, `docs/host-prep-nvidia.md`, and `.claude/context/`. It does not carry badges, Mermaid diagrams, usage examples, or a License section.

## 2026-04-24T09:13Z — initial
- agent: log/01KPZC8HKD9PR2PHY5DDR3HFYC
- refs: [[files/JDL-65/compose-yml]], [[files/JDL-65/gitignore]], [[files/JDL-65/pyproject-toml]], [[files/JDL-65/prettierignore]]

Forge modified `/home/josh/atmosphere/README.md` as part of JDL-65 M0 scaffolding, replacing the 13-byte placeholder that shipped with the repo's `first commit` (`e358491`) with a 52-line one-page repo front. The rewrite was committed as `51cad9e` on branch `JDL-65-m0-repo-ci-host-prep` with message `docs(JDL-65): rewrite root README as one-page repo front`, scoped to `README.md` only via the `git commit -m "<msg>" -- README.md` pathspec form so Forge's commit did not sweep in parallel-agent work (the pre-staged `.pre-commit-config.yaml` and the in-flight `.github/workflows/ci.yml`). ^p001

Structure of the rewritten file: an H1 `# Atmosphere` title; an opening paragraph describing the platform end-to-end (Jetstream → Redpanda → Flink bronze on Iceberg/SeaweedFS → Sleuth profile enrichment + Oracle sentiment → dbt-duckdb silver/gold → ClickHouse serving → Quarto reports and Grafana dashboards); a second paragraph stating the single-source-of-truth posture (Jetstream canonical, Iceberg durable projection, ClickHouse pure query engine with S3 filesystem cache as sole acceleration, 24-hour Jetstream cursor replay as the only recovery mechanism); an `## Architecture` section that narrates the data and governance planes in one paragraph and defers full diagrams to `.claude/context/architecture.md`; a `## Current state` section declaring M0 scope and pointing at the fifteen-milestone roadmap in `.claude/context/roadmap.md`; and a `## Getting started` section with four bullets pointing at `CONTRIBUTING.md`, `docs/host-prep-nvidia.md`, the `.claude/context/` design docs (starting with `project-overview.md`, then `architecture.md`, then per-component files), and the Linear project `Atmosphere`. ^p002

Intentional absences, recorded so future edits preserve them: no badges (the repo is private and there is no public CI status surface to advertise); no Mermaid diagrams (the authoritative diagrams live in `.claude/context/architecture.md` and duplicating them in the README creates a drift hazard); no usage example (the platform is infrastructure, not a library — usage is `docker compose up`, covered under `CONTRIBUTING.md` and the roadmap's milestone acceptance criteria); and no `## License` section (the project is private and no license has been chosen yet). The file stays under the 100-line constraint documented in the invocation contract. ^p003

Two of the four bullets in the Getting started section reference files — `CONTRIBUTING.md` and `docs/host-prep-nvidia.md` — that do not yet exist on disk as of this invocation. Both are explicit M0 deliverables per `.claude/context/roadmap.md` and are being built by parallel Forge agents in the same milestone; forward references to sibling M0 artifacts are appropriate because they will exist by the time M0 closes and the ones-and-zeros acceptance gate is exercised. The link targets are written as relative repo-root paths (`[`CONTRIBUTING.md`](CONTRIBUTING.md)` and `[`docs/host-prep-nvidia.md`](docs/host-prep-nvidia.md)`) so GitHub's file browser resolves them cleanly once the files land. ^p004

Forge reported one operational gotcha worth recording for future README edits and for any agent that scope-commits inside a working tree with parallel-agent activity: the `git commit` pathspec argument order matters — `git commit -m "<msg>" -- <path>` works, but `git commit -- <path> -m "<msg>"` treats the message as a pathspec and errors. Forge added a local memory note (`gotcha_git_commit_pathspec_order.md`) so its future invocations get the order right on the first try. Post-commit `git status` confirmed the parallel agent's `.pre-commit-config.yaml` and `.github/workflows/ci.yml` remained staged/untouched outside this commit, preserving the one-invocation-one-commit contract. ^p005
