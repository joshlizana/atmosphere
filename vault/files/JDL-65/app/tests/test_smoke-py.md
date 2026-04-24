---
id: 01KPZBJM3Z2MBD58NETRWDBY32
type: file
name: test_smoke.py
created_at: 2026-04-24T09:01Z
created_by: log/01KPZBJM3Z2MBD58NETRWDBY32
component: repo
---

## Purpose
Tracks the lifecycle of `app/tests/test_smoke.py` — the trivial pytest module that gives the M0 `uv run pytest` CI gate something to run and pins CI to Python 3.12 strictly so runner drift surfaces here instead of downstream. Real per-service tests start arriving in M4; until then this file is the sole test target for the workspace.

## 2026-04-24T09:01Z — initial
- agent: log/01KPZBJM3Z2MBD58NETRWDBY32
- refs: [[decisions/JDL-65/20260424T0852Z-uv-workspace-declared-at-m0]], [[research/JDL-65/uv-workspace-layout]], [[research/JDL-65/setup-uv-workspace-ci-2026]], [[files/JDL-65/pyproject-toml]]

Forge created `app/tests/test_smoke.py` as part of JDL-65 M0 scaffolding and committed it as `cf33926` on branch `JDL-65-m0-repo-ci-host-prep` with message `test(JDL-65): add M0 smoke test proving pytest CI gate is wired up`. The file is 16 lines: one module docstring explaining the M0 CI-gate role, a single `import sys`, and two zero-argument test functions with `-> None` return annotations. ^p001

The two tests carry distinct jobs. `test_smoke_pytest_runs` asserts `True is True` — a tautology whose only purpose is to make pytest collect and execute at least one test so the `uv run pytest` gate reports a green run rather than the "no tests collected" exit code 5. `test_smoke_python_version` asserts `sys.version_info[:2] == (3, 12)` with strict equality, not `>=`. The strict pin is deliberate and matches the workspace-root `requires-python = "==3.12.*"` in `pyproject.toml`: PyFlink's supported-version matrix tops out at 3.12, and catching CI-runner drift to 3.13 here at M0 is cheaper than debugging a PyFlink import failure in M5. ^p002

Collection works without a `conftest.py` or `__init__.py` because `pyproject.toml` already sets `[tool.pytest.ini_options] addopts = "--import-mode=importlib"` and `testpaths = ["app/tests"]`; importlib import mode is what enables `app/tests/` to be picked up as a plain directory rather than a package. The target directory did not exist before this commit — creating the file implicitly created `app/tests/`, which is the expected behavior under importlib mode. No workspace-member imports are used; the only import is stdlib `sys`. ^p003
