"""M1 shared-infrastructure outer-loop smoke test (JDL-66).

Exercises the full operator `make nuke` → `make up` cycle against the host,
asserts every acceptance criterion from the M1 roadmap entry, and confirms
service state survives a `docker compose restart`.

This is an OUTER-LOOP test: it brings up real docker containers, binds real
host ports, and persists real docker-managed volumes. It is not safe to run
in parallel with another copy of the atmosphere platform on the same host.

Test specification — see JDL-66 Probe invocation. Phases run sequentially in
the order declared here; later phases depend on state established by
earlier phases.

Phases:
    1. Baseline clean state (make nuke, assert clean).
    2. First bring-up (make up, assert healthy, .env populated).
    3. Postgres behavior (four DBs, per-service users, ownership).
    4. SeaweedFS behavior (master healthy, three buckets present).
    5. Redpanda behavior (ready, bootstrap seed, topic lifecycle,
       schema-registry / HTTP-proxy disabled).
    6. State across `docker compose restart`.
    7. Full-reset cycle (make nuke → make up regenerates .env secrets).
    8. Cleanup (leave platform in `make down`).
"""

from __future__ import annotations

import json
import re
import shutil
import socket
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = REPO_ROOT / ".env"

# Container name conventions — `${COMPOSE_PROJECT_NAME}-<service>-1` with the
# project pinned to `atmosphere` via .env / compose.yml `name:`.
CONTAINER_POSTGRES = "atmosphere-postgres-1"
CONTAINER_SEAWEEDFS = "atmosphere-seaweedfs-1"
CONTAINER_REDPANDA = "atmosphere-redpanda-1"
CONTAINER_SEAWEEDFS_INIT = "atmosphere-seaweedfs-init-1"

EXPECTED_HEALTHY = (CONTAINER_POSTGRES, CONTAINER_SEAWEEDFS, CONTAINER_REDPANDA)
EXPECTED_VOLUMES = ("atmosphere_postgres", "atmosphere_seaweedfs", "atmosphere_redpanda")
EXPECTED_DBS = ("grafana", "lakekeeper", "openmetadata", "prefect")
# (db_name, env-var user, env-var password) — matches the init script.
SERVICE_DBS = (
    ("lakekeeper", "POSTGRES_LAKEKEEPER_USER", "POSTGRES_LAKEKEEPER_PASSWORD"),
    ("prefect", "POSTGRES_PREFECT_USER", "POSTGRES_PREFECT_PASSWORD"),
    ("openmetadata", "POSTGRES_OPENMETADATA_USER", "POSTGRES_OPENMETADATA_PASSWORD"),
    ("grafana", "POSTGRES_GRAFANA_USER", "POSTGRES_GRAFANA_PASSWORD"),
)
EXPECTED_BUCKETS = ("atmosphere", "flink", "loki")

# Shared module-scope state. Previous probes produce values (captured
# Phase-2 superuser password, env map) that later probes read.
state: dict[str, object] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 120,
    env: dict[str, str] | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess:
    """Run a subprocess and capture stdout/stderr.

    Never raises on non-zero exit unless `check=True`. Tests inspect returncode
    themselves so they can attach logs to assertion failures.
    """
    return subprocess.run(
        cmd,
        cwd=cwd or REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        check=check,
    )


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse a dotenv-style file into a dict. Strips inline comments via the
    `KEY=VALUE` rule (first `=` splits; no quoting semantics needed — the
    generator produces plain `KEY=alnum32` lines)."""
    out: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip()
    return out


def docker_inspect_health(container: str) -> str:
    """Return the `.State.Health.Status` of a container, or empty string if
    the container doesn't exist / has no healthcheck."""
    cp = run(
        [
            "docker",
            "inspect",
            "--format",
            "{{if .State.Health}}{{.State.Health.Status}}{{else}}NO_HEALTHCHECK{{end}}",
            container,
        ],
        timeout=15,
    )
    if cp.returncode != 0:
        return "NOT_FOUND"
    return cp.stdout.strip()


def docker_inspect_state(container: str) -> tuple[str, int]:
    """Return (status, exit_code) for a container — used for one-shot sidecars
    where exit-code-0 is the success signal."""
    cp = run(
        [
            "docker",
            "inspect",
            "--format",
            "{{.State.Status}} {{.State.ExitCode}}",
            container,
        ],
        timeout=15,
    )
    if cp.returncode != 0:
        return ("NOT_FOUND", -1)
    parts = cp.stdout.strip().split()
    return (parts[0], int(parts[1])) if len(parts) == 2 else ("UNKNOWN", -1)


def wait_for_healthy(containers: tuple[str, ...], timeout: int = 180) -> dict[str, str]:
    """Poll every listed container until healthy, or timeout.

    Returns the final status map so the caller can attach it to assertion
    failures. Does not raise — the caller asserts on the result.
    """
    deadline = time.time() + timeout
    final: dict[str, str] = {}
    while time.time() < deadline:
        final = {c: docker_inspect_health(c) for c in containers}
        if all(s == "healthy" for s in final.values()):
            return final
        time.sleep(3)
    return final


def dump_logs(service: str, tail: int = 200) -> str:
    """Capture `docker compose logs --tail=N <service>` for failure context."""
    cp = run(
        ["docker", "compose", "logs", f"--tail={tail}", "--no-color", service],
        timeout=30,
    )
    return cp.stdout + cp.stderr


def compose_ps() -> str:
    cp = run(["docker", "compose", "ps", "--all"], timeout=30)
    return cp.stdout + cp.stderr


def current_env() -> dict[str, str]:
    """Load the current .env — each test re-reads so Phase 7 sees the new
    generation rather than Phase 2's cached copy."""
    assert ENV_PATH.exists(), ".env missing when expected"
    return parse_env_file(ENV_PATH)


def psql_exec(
    container: str,
    user: str,
    db: str,
    sql: str,
    *,
    password: str | None = None,
    extra_args: tuple[str, ...] = (),
) -> subprocess.CompletedProcess:
    """Run `psql` inside a compose container. When `password` is provided, it
    is passed through via `PGPASSWORD` in the container environment so
    non-superuser auth works against `host all all scram-sha-256`."""
    env_args: list[str] = []
    if password is not None:
        env_args = ["-e", f"PGPASSWORD={password}"]
    cmd = [
        "docker",
        "compose",
        "exec",
        "-T",
        *env_args,
        container,
        "psql",
        "-U",
        user,
        "-d",
        db,
        "-Atc",
        sql,
        *extra_args,
    ]
    return run(cmd, timeout=30)


def weed_shell(script: str) -> subprocess.CompletedProcess:
    """Pipe a script into `weed shell` in the seaweedfs container."""
    cmd = [
        "docker",
        "compose",
        "exec",
        "-T",
        "seaweedfs",
        "weed",
        "shell",
        "-master=localhost:9333",
    ]
    return subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        input=script,
        capture_output=True,
        text=True,
        timeout=30,
    )


def rpk(*args: str) -> subprocess.CompletedProcess:
    """Run `rpk` inside the redpanda container."""
    cmd = ["docker", "compose", "exec", "-T", "redpanda", "rpk", *args]
    return run(cmd, timeout=30)


def port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    """Return True iff a TCP connect to host:port succeeds. Used for the
    port-NOT-bound assertions — a refused connect is the positive signal."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Pre-flight — skip the whole module if docker isn't available so CI (which
# has no docker) gives a clean skip instead of a red fail.
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.skipif(
    shutil.which("docker") is None,
    reason="docker not available on this host; outer-loop smoke requires docker+compose",
)


# ---------------------------------------------------------------------------
# Phase 1 — Baseline clean state
# ---------------------------------------------------------------------------


def test_01_make_nuke_succeeds_from_cold():
    """`make nuke` must be safe on a never-brought-up host (the target uses
    `|| true` on the down step precisely so this is a no-op on cold state)."""
    cp = run(["make", "nuke"], timeout=120)
    assert cp.returncode == 0, (
        f"`make nuke` failed on cold state (returncode={cp.returncode}).\n"
        f"stdout:\n{cp.stdout}\nstderr:\n{cp.stderr}"
    )


def test_02_no_atmosphere_volumes_remain():
    """After nuke, no `atmosphere_*` docker volumes must remain."""
    cp = run(
        ["docker", "volume", "ls", "--filter", "name=atmosphere_", "--format", "{{.Name}}"],
        timeout=15,
    )
    assert cp.returncode == 0, f"docker volume ls failed:\n{cp.stderr}"
    lingering = [ln for ln in cp.stdout.splitlines() if ln.strip()]
    assert lingering == [], f"unexpected lingering volumes after nuke: {lingering}"


def test_03_env_file_absent():
    """`.env` must not exist after nuke."""
    assert not ENV_PATH.exists(), f".env still present at {ENV_PATH} after nuke"


# ---------------------------------------------------------------------------
# Phase 2 — First bring-up
# ---------------------------------------------------------------------------


def test_04_make_up_succeeds():
    """`make up` chains init.sh then up.sh; timeout budget covers first-run
    image pulls (~5 minutes; we give 10 to be safe)."""
    cp = run(["make", "up"], timeout=600)
    if cp.returncode != 0:
        ps = compose_ps()
        logs = {
            s: dump_logs(s, tail=100)
            for s in ("postgres", "seaweedfs", "seaweedfs-init", "redpanda")
        }
        pytest.fail(
            f"`make up` failed (returncode={cp.returncode}).\n"
            f"stdout:\n{cp.stdout}\nstderr:\n{cp.stderr}\n"
            f"compose ps:\n{ps}\n"
            + "\n".join(f"--- {s} logs ---\n{body}" for s, body in logs.items())
        )


def test_05_env_generated_with_unique_secrets():
    """.env exists, has no `CHANGEME` leftovers, and the two postgres
    passwords sampled are independent random values."""
    assert ENV_PATH.exists(), ".env not generated by init.sh"
    text = ENV_PATH.read_text()
    assert "CHANGEME" not in text, f".env still contains CHANGEME slots:\n{text}"
    env = parse_env_file(ENV_PATH)
    superuser_pw = env.get("POSTGRES_SUPERUSER_PASSWORD", "")
    lakekeeper_pw = env.get("POSTGRES_LAKEKEEPER_PASSWORD", "")
    assert superuser_pw and lakekeeper_pw, (
        "missing postgres passwords in generated .env; "
        f"superuser={superuser_pw!r} lakekeeper={lakekeeper_pw!r}"
    )
    assert superuser_pw != lakekeeper_pw, (
        "postgres superuser + lakekeeper passwords are identical — "
        "init.sh must generate independent random values per slot"
    )
    # Save for Phase 7 regeneration comparison.
    state["phase2_superuser_password"] = superuser_pw
    state["phase2_env"] = env


def test_06_long_lived_services_healthy():
    """All three long-lived containers must report `healthy`."""
    final = wait_for_healthy(EXPECTED_HEALTHY, timeout=240)
    unhealthy = {c: s for c, s in final.items() if s != "healthy"}
    if unhealthy:
        # Map container → service for log dump.
        svc_map = {
            CONTAINER_POSTGRES: "postgres",
            CONTAINER_SEAWEEDFS: "seaweedfs",
            CONTAINER_REDPANDA: "redpanda",
        }
        logs = {svc_map[c]: dump_logs(svc_map[c]) for c in unhealthy}
        pytest.fail(
            f"unhealthy services: {unhealthy}\n"
            + "\n".join(f"--- {s} logs ---\n{body}" for s, body in logs.items())
        )


def test_07_seaweedfs_init_exited_zero():
    """One-shot sidecar must have exited cleanly with code 0."""
    status, exit_code = docker_inspect_state(CONTAINER_SEAWEEDFS_INIT)
    if status != "exited" or exit_code != 0:
        logs = dump_logs("seaweedfs-init", tail=200)
        pytest.fail(
            f"seaweedfs-init not in expected state: status={status!r} exit_code={exit_code}\n"
            f"logs:\n{logs}"
        )


def test_08_expected_volumes_exist():
    """Three docker-managed `atmosphere_*` volumes must exist."""
    cp = run(
        ["docker", "volume", "ls", "--filter", "name=atmosphere_", "--format", "{{.Name}}"],
        timeout=15,
    )
    assert cp.returncode == 0, f"docker volume ls failed:\n{cp.stderr}"
    present = sorted(ln.strip() for ln in cp.stdout.splitlines() if ln.strip())
    assert present == sorted(EXPECTED_VOLUMES), (
        f"volume set mismatch; expected={sorted(EXPECTED_VOLUMES)} got={present}"
    )


# ---------------------------------------------------------------------------
# Phase 3 — Postgres behavior
# ---------------------------------------------------------------------------


def test_09_four_logical_dbs_exist():
    """Superuser-authed `SELECT datname FROM pg_database` must list all four."""
    env = current_env()
    superuser = env["POSTGRES_SUPERUSER"]
    sql = (
        "SELECT datname FROM pg_database "
        "WHERE datname IN ('lakekeeper','prefect','openmetadata','grafana') "
        "ORDER BY datname"
    )
    cp = psql_exec("postgres", superuser, "postgres", sql)
    assert cp.returncode == 0, (
        f"psql query failed (returncode={cp.returncode}):\n"
        f"stdout:\n{cp.stdout}\nstderr:\n{cp.stderr}"
    )
    found = tuple(ln.strip() for ln in cp.stdout.splitlines() if ln.strip())
    assert found == EXPECTED_DBS, f"db set mismatch: expected={EXPECTED_DBS} got={found}"


def test_10_each_service_user_connects_to_its_db():
    """Each per-service user must auth to its matching-name DB and current_user /
    current_database report the expected pair."""
    env = current_env()
    failures: list[str] = []
    for db, user_key, pw_key in SERVICE_DBS:
        user = env[user_key]
        password = env[pw_key]
        sql = "SELECT current_user || '|' || current_database()"
        cp = psql_exec("postgres", user, db, sql, password=password)
        if cp.returncode != 0:
            failures.append(f"{db}: psql returned {cp.returncode}; stderr={cp.stderr.strip()}")
            continue
        got = cp.stdout.strip()
        expected = f"{user}|{db}"
        if got != expected:
            failures.append(f"{db}: expected={expected!r} got={got!r}")
    assert not failures, "per-service user auth failures:\n" + "\n".join(failures)


def test_11_each_service_user_owns_its_db():
    """`pg_get_userbyid(datdba)` must resolve to the per-service user for each
    of the four service DBs."""
    env = current_env()
    superuser = env["POSTGRES_SUPERUSER"]
    failures: list[str] = []
    for db, user_key, _pw_key in SERVICE_DBS:
        expected_user = env[user_key]
        sql = f"SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = '{db}'"
        cp = psql_exec("postgres", superuser, "postgres", sql)
        if cp.returncode != 0:
            failures.append(f"{db}: psql returned {cp.returncode}; stderr={cp.stderr.strip()}")
            continue
        got = cp.stdout.strip()
        if got != expected_user:
            failures.append(f"{db}: owner expected={expected_user!r} got={got!r}")
    assert not failures, "ownership mismatches:\n" + "\n".join(failures)


# ---------------------------------------------------------------------------
# Phase 4 — SeaweedFS behavior
# ---------------------------------------------------------------------------


def test_12_seaweedfs_master_healthy():
    """Master `/cluster/status` must return HTTP 200 and JSON body with
    `IsLeader: true`."""
    cp = run(["curl", "-fsS", "http://localhost:9333/cluster/status"], timeout=15)
    assert cp.returncode == 0, f"curl against :9333/cluster/status failed: {cp.stderr.strip()}"
    try:
        body = json.loads(cp.stdout)
    except json.JSONDecodeError as e:
        pytest.fail(f"cluster/status did not return JSON: {e}; body={cp.stdout!r}")
    assert body.get("IsLeader") is True, f"cluster/status JSON missing IsLeader=true; body={body!r}"


def test_13_three_buckets_present():
    """`weed shell` `s3.bucket.list` must include atmosphere / flink / loki."""
    cp = weed_shell("s3.bucket.list\n")
    if cp.returncode != 0:
        logs = dump_logs("seaweedfs-init", tail=100)
        pytest.fail(
            f"weed shell failed (returncode={cp.returncode})\n"
            f"stdout:\n{cp.stdout}\nstderr:\n{cp.stderr}\n"
            f"seaweedfs-init logs:\n{logs}"
        )
    output = cp.stdout + cp.stderr
    missing = [b for b in EXPECTED_BUCKETS if not re.search(rf"\b{b}\b", output)]
    if missing:
        pytest.fail(f"buckets missing from s3.bucket.list: {missing}\nweed shell output:\n{output}")


# ---------------------------------------------------------------------------
# Phase 5 — Redpanda behavior
# ---------------------------------------------------------------------------


def test_15_redpanda_admin_ready():
    """Admin API readiness endpoint must return HTTP 200."""
    cp = run(["curl", "-fsS", "http://localhost:9644/v1/status/ready"], timeout=15)
    assert cp.returncode == 0, f"curl against :9644/v1/status/ready failed: {cp.stderr.strip()}"


def test_16_storage_min_free_bytes_seeded():
    """Bootstrap YAML must have seeded `storage_min_free_bytes=2147483648`."""
    cp = rpk("cluster", "config", "get", "storage_min_free_bytes")
    assert cp.returncode == 0, (
        f"rpk failed (returncode={cp.returncode}):\nstdout:\n{cp.stdout}\nstderr:\n{cp.stderr}"
    )
    value = cp.stdout.strip()
    assert value == "2147483648", (
        f"storage_min_free_bytes not seeded by bootstrap YAML; expected=2147483648 got={value!r}"
    )


def test_17_topic_create_list_delete_cycle():
    """Create → list → delete → relist cycle on a dedicated test topic."""
    topic = "smoke-probe-test"
    # Ensure clean slate — a dangling topic from a prior failed run would
    # make `rpk topic create` fail. Delete is best-effort; ignore result.
    rpk("topic", "delete", topic)

    create = rpk("topic", "create", topic)
    assert create.returncode == 0, (
        f"rpk topic create failed:\nstdout:\n{create.stdout}\nstderr:\n{create.stderr}"
    )

    listing = rpk("topic", "list")
    assert listing.returncode == 0, f"rpk topic list failed:\nstderr:\n{listing.stderr}"
    assert topic in listing.stdout, (
        f"topic {topic!r} absent from rpk topic list output:\n{listing.stdout}"
    )

    delete = rpk("topic", "delete", topic)
    assert delete.returncode == 0, (
        f"rpk topic delete failed:\nstdout:\n{delete.stdout}\nstderr:\n{delete.stderr}"
    )

    listing_after = rpk("topic", "list")
    assert listing_after.returncode == 0
    assert topic not in listing_after.stdout, (
        f"topic {topic!r} still present after delete:\n{listing_after.stdout}"
    )


def test_18_schema_registry_and_http_proxy_disabled():
    """Ports 8081 (schema-registry) and 8082 (HTTP proxy) must NOT be bound
    on the host — flag omission on the Redpanda command line is the only
    thing that disables these subsystems."""
    assert not port_open("localhost", 8081), (
        "port 8081 is bound — schema-registry must be disabled by flag omission"
    )
    assert not port_open("localhost", 8082), (
        "port 8082 is bound — HTTP proxy must be disabled by flag omission"
    )


# ---------------------------------------------------------------------------
# Phase 6 — State across `docker compose restart`
# ---------------------------------------------------------------------------


def test_19_create_persistence_markers():
    """Create a marker in each service to survive the upcoming restart."""
    env = current_env()
    # Postgres: create a table in the lakekeeper DB as the lakekeeper user.
    lk_user = env["POSTGRES_LAKEKEEPER_USER"]
    lk_pw = env["POSTGRES_LAKEKEEPER_PASSWORD"]
    sql = (
        "CREATE TABLE smoke_probe_marker (ts TIMESTAMPTZ DEFAULT now()); "
        "INSERT INTO smoke_probe_marker DEFAULT VALUES;"
    )
    cp = psql_exec("postgres", lk_user, "lakekeeper", sql, password=lk_pw)
    assert cp.returncode == 0, (
        f"postgres marker creation failed:\nstdout:\n{cp.stdout}\nstderr:\n{cp.stderr}"
    )

    # SeaweedFS: create a marker bucket via `weed shell`.
    sw = weed_shell("s3.bucket.create -name smoke-probe-marker\n")
    assert sw.returncode == 0, (
        f"seaweedfs marker bucket creation failed:\nstdout:\n{sw.stdout}\nstderr:\n{sw.stderr}"
    )

    # Redpanda: create a marker topic.
    rp = rpk("topic", "create", "smoke-probe-marker")
    assert rp.returncode == 0, (
        f"redpanda marker topic creation failed:\nstdout:\n{rp.stdout}\nstderr:\n{rp.stderr}"
    )


def test_20_restart_all_three_and_rewait_healthy():
    """`docker compose restart postgres seaweedfs redpanda` then wait for
    every one to come back healthy."""
    cp = run(
        ["docker", "compose", "restart", "postgres", "seaweedfs", "redpanda"],
        timeout=180,
    )
    assert cp.returncode == 0, (
        f"docker compose restart failed:\nstdout:\n{cp.stdout}\nstderr:\n{cp.stderr}"
    )
    final = wait_for_healthy(EXPECTED_HEALTHY, timeout=240)
    unhealthy = {c: s for c, s in final.items() if s != "healthy"}
    assert not unhealthy, f"services unhealthy after restart: {unhealthy}"


def test_21_markers_survive_restart():
    """Each marker from test_19 must still exist after the restart."""
    env = current_env()
    lk_user = env["POSTGRES_LAKEKEEPER_USER"]
    lk_pw = env["POSTGRES_LAKEKEEPER_PASSWORD"]

    cp = psql_exec(
        "postgres",
        lk_user,
        "lakekeeper",
        "SELECT count(*) FROM smoke_probe_marker",
        password=lk_pw,
    )
    assert cp.returncode == 0, (
        f"postgres marker count query failed:\nstdout:\n{cp.stdout}\nstderr:\n{cp.stderr}"
    )
    assert cp.stdout.strip() == "1", (
        f"postgres marker did not survive restart: count={cp.stdout.strip()!r}"
    )

    sw = weed_shell("s3.bucket.list\n")
    assert sw.returncode == 0, f"weed shell failed post-restart: {sw.stderr}"
    assert "smoke-probe-marker" in (sw.stdout + sw.stderr), (
        "seaweedfs marker bucket did not survive restart:\n" + sw.stdout + sw.stderr
    )

    rp = rpk("topic", "list")
    assert rp.returncode == 0, f"rpk topic list failed: {rp.stderr}"
    assert "smoke-probe-marker" in rp.stdout, (
        f"redpanda marker topic did not survive restart:\n{rp.stdout}"
    )


def test_22_cleanup_markers():
    """Remove markers so Phase 7 starts from a consistent state."""
    env = current_env()
    lk_user = env["POSTGRES_LAKEKEEPER_USER"]
    lk_pw = env["POSTGRES_LAKEKEEPER_PASSWORD"]

    # Marker cleanup is best-effort; we do not want Phase 7 to hinge on it.
    psql_exec(
        "postgres",
        lk_user,
        "lakekeeper",
        "DROP TABLE IF EXISTS smoke_probe_marker;",
        password=lk_pw,
    )
    weed_shell("s3.bucket.delete -name smoke-probe-marker\n")
    rpk("topic", "delete", "smoke-probe-marker")


# ---------------------------------------------------------------------------
# Phase 7 — Full-reset cycle
# ---------------------------------------------------------------------------


def test_23_make_nuke_hot_state():
    """`make nuke` must succeed from a fully-up platform and leave no
    trace — no volumes, no `.env`."""
    cp = run(["make", "nuke"], timeout=180)
    assert cp.returncode == 0, (
        f"`make nuke` from hot state failed:\nstdout:\n{cp.stdout}\nstderr:\n{cp.stderr}"
    )
    assert not ENV_PATH.exists(), f".env still present after second nuke: {ENV_PATH}"

    vol = run(
        ["docker", "volume", "ls", "--filter", "name=atmosphere_", "--format", "{{.Name}}"],
        timeout=15,
    )
    assert vol.returncode == 0
    lingering = [ln for ln in vol.stdout.splitlines() if ln.strip()]
    assert lingering == [], f"unexpected lingering volumes after second nuke: {lingering}"


def test_24_make_up_from_fresh_nuke():
    """Second `make up` after nuke must bring the platform healthy again."""
    cp = run(["make", "up"], timeout=600)
    if cp.returncode != 0:
        ps = compose_ps()
        logs = {
            s: dump_logs(s, tail=100)
            for s in ("postgres", "seaweedfs", "seaweedfs-init", "redpanda")
        }
        pytest.fail(
            f"second `make up` failed (returncode={cp.returncode}).\n"
            f"stdout:\n{cp.stdout}\nstderr:\n{cp.stderr}\n"
            f"compose ps:\n{ps}\n"
            + "\n".join(f"--- {s} logs ---\n{body}" for s, body in logs.items())
        )
    final = wait_for_healthy(EXPECTED_HEALTHY, timeout=240)
    unhealthy = {c: s for c, s in final.items() if s != "healthy"}
    assert not unhealthy, f"services unhealthy after second `make up`: {unhealthy}"


def test_25_superuser_password_regenerated():
    """The new `.env`'s superuser password must differ from the Phase-2 value
    — proves `init.sh` regenerates on every fresh nuke."""
    prior = state.get("phase2_superuser_password")
    assert prior, "Phase-2 captured password missing from module state"
    env = current_env()
    new = env["POSTGRES_SUPERUSER_PASSWORD"]
    assert new != prior, (
        "POSTGRES_SUPERUSER_PASSWORD identical across nukes — init.sh is not "
        "regenerating secrets per cycle"
    )


# ---------------------------------------------------------------------------
# Phase 8 — Cleanup
# ---------------------------------------------------------------------------


def test_26_leave_in_make_down_state():
    """Leave the platform in `make down` — services stopped, volumes and
    .env preserved for operator inspection."""
    cp = run(["make", "down"], timeout=120)
    assert cp.returncode == 0, f"`make down` failed:\nstdout:\n{cp.stdout}\nstderr:\n{cp.stderr}"
    # .env must still exist; volumes must still exist.
    assert ENV_PATH.exists(), ".env disappeared during `make down`"
    vol = run(
        ["docker", "volume", "ls", "--filter", "name=atmosphere_", "--format", "{{.Name}}"],
        timeout=15,
    )
    assert vol.returncode == 0
    present = sorted(ln.strip() for ln in vol.stdout.splitlines() if ln.strip())
    assert present == sorted(EXPECTED_VOLUMES), (
        f"`make down` removed volumes; expected preserved={sorted(EXPECTED_VOLUMES)} got={present}"
    )
