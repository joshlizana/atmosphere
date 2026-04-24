# Contributing to Atmosphere

Atmosphere is a single-host streaming lakehouse built on Docker Compose. This
document covers what you need on your machine, how to set up the workspace,
the gates your changes must pass before opening a pull request, and the
local-build deploy model the platform uses.

## Prerequisites

- **Python 3.12.** The workspace is pinned to 3.12 in `pyproject.toml`.
- **[uv](https://docs.astral.sh/uv/).** All Python work — dependency install,
  linting, tests, dbt — runs through `uv`. Install it with the official
  standalone installer:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **Docker with Compose v2.** The platform is defined in the top-level
  `compose.yml` and every service builds locally on the host. `docker compose`
  (the v2 subcommand) must be on your PATH; the legacy `docker-compose`
  binary is not used.
- **NVIDIA Container Toolkit.** Oracle (sentiment inference) needs GPU
  passthrough. Host setup is operator-specific; see `docs/` for host prep
  notes.
- **Node / npx.** Prettier runs via `npx` rather than as a workspace
  dependency, so any recent Node with `npx` available is sufficient.

## Setup

```bash
git clone git@github.com:<owner>/atmosphere.git
cd atmosphere
uv sync --locked --all-packages --all-extras --all-groups
uv run pre-commit install
```

`uv sync` materializes the lockfile into a project-local `.venv/`. Every
command below is prefixed with `uv run` so it executes inside that
environment — you do not need to activate the venv manually.

`uv run pre-commit install` wires the repo's pre-commit hooks into your local
git checkout so the fast gates (ruff, prettier) run on every commit.

## Local gates

These are the same commands CI runs. Run them locally before pushing — a red
CI build on gates that pass cleanly on your machine usually means your
working tree drifted from what you pushed.

```bash
# Python lint + format
uv run ruff check .
uv run ruff format --check .

# Python tests
uv run pytest

# dbt parse (schema + ref graph validation, no warehouse access)
uv run --directory app/dbt dbt parse --profiles-dir ./profiles --no-partial-parse

# Prettier (YAML / Markdown / JSON)
npx --yes prettier --check .

# Compose-shape gate
docker compose config
```

Ruff is the sole Python linter and formatter — there is no black in this
repo. Prettier owns YAML, Markdown, and JSON; it is configured never to touch
Python. `docker compose config` parses `compose.yml` and resolves
interpolations, catching syntax and reference errors without starting any
containers.

## Branching and commits

**Branches** follow `JDL-XXX-<short-kebab>`, where `JDL-XXX` is the Linear
issue ID and the kebab suffix is a short human-readable hint at the scope.

```
JDL-65-m0-repo-ci-host-prep
JDL-120-sleuth-backoff-tuning
```

**Commit subjects** use `type(JDL-XXX): subject`:

```
build(JDL-65): add uv.lock for workspace dev dependencies
test(JDL-65): add M0 smoke test proving pytest CI gate is wired up
chore(JDL-65): add config/.gitkeep placeholder
```

`type` follows the usual conventional-commit palette (`build`, `chore`,
`docs`, `feat`, `fix`, `refactor`, `test`). Keep the subject under 72
characters and imperative-present-tense ("add", not "added"). The Linear ID
in parentheses anchors every commit to a ticket so `git log` is a readable
audit trail of what shipped for which issue.

## Local-build deploy model

Atmosphere does not publish container images. There is no CI image pipeline
and no container registry. Every service that is built from a Dockerfile —
the Prefect worker, Spout, Sleuth, Oracle, and any other locally-built
service — is built on the deploy host with `docker compose build`, directly
from the git checkout.

The canonical roll-forward loop is:

```bash
git pull
docker compose build <service>
docker compose up -d <service>
```

The canonical rollback loop is identical with a pinned SHA:

```bash
git checkout <sha>
docker compose build <service>
docker compose up -d <service>
```

Because the source of truth is whatever commit is checked out when you run
`docker compose build`, keep the host on a clean, known ref before building.
During active development the worker and service images are expected to be
rebuilt frequently; Dockerfiles are structured so system deps live in early
layers and application code copies last, keeping iterative rebuilds fast.

## Environment configuration

Every secret and environment-specific value the compose stack consumes is
declared in `.env.example` at the repo root. `.env.example` is the template
and is checked in; `.env` is the real, populated file and is gitignored.

```bash
cp .env.example .env
# edit .env and replace every CHANGEME with a real value
```

Do not commit `.env` or any file containing real credentials. If you add a
new environment variable anywhere in the stack, add it to `.env.example`
with a `CHANGEME` placeholder (or a sensible non-secret default) in the same
pull request.

## Issues and pull requests

Work is tracked in Linear under the `JDL` project. File bugs and feature
requests there; the branch and commit conventions above keep git history
tied back to the ticket.

Pull requests should be small, scoped to a single Linear issue, and ready
for review when opened:

- All local gates above pass.
- The branch is rebased on (or up to date with) `main`.
- The PR description links the Linear issue and briefly states what
  changed and why.

## Further reading

Operator-facing topics — host preparation, backups, disaster recovery,
per-service runbooks — live under `docs/` and land as the platform grows
through its milestones.
