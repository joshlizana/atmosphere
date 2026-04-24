"""M0 smoke test proving the pytest CI gate is wired up.

This file exists so that CI has something to run and so a deliberately-broken
commit can turn CI red as part of the M0 validate step. Real per-service tests
arrive starting M4; until then this is the only test in the project.
"""

import sys


def test_smoke_pytest_runs() -> None:
    assert True is True


def test_smoke_python_version() -> None:
    assert sys.version_info[:2] == (3, 12)
