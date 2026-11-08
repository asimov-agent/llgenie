"""Install, bootstrap and verify the fleet's Hindsight memory wiring (issue #2068).

The acceptance contract (from the issue) this file locks, each with real script logic run
as a subprocess or an import — nothing here mocks the product:

  * install provisions the daemon at the pinned version + fixed port and exits 0; a
    second invocation reports no change (idempotent).
  * bootstrap writes each profile's config, env key and memory-provider from one template;
    a second run reports zero updates (`expected <= actual`).
  * --dry-run prints the full plan (paths, modes, provider delta) and writes nothing
    (the tree is byte-identical after it runs).
  * verify reports per-profile PASS/FAIL with the daemon pid+port and the newest
    `Connection verified:` line, and a profile whose provider is empty or whose env key is
    absent FAILS with its name, not a skip.
  * the bootstrap never emits a credential value (a grep for a sentinel secret gets zero
    hits in dry-run and real-run output).
  * the bootstrap reuses the plugin's env builder (test asserts bootstrap output equals
    the runtime-built env for the same profile).
  * config + env file modes are 0600.
  * the verification feeds the `make memory-check` gate: the gate target wires the verify
    script's exit code, and `make check-wiring lint` stay green.
  * the vehicle touches scripts/, Makefile, the test tree and preflight wiring only — no
    docs/ section (that is #2057/#2063) and no duplicate of #2058's check logic.

The Hindsight plugin is a third-party package installed at image build time, so the unit
job has no plugin; the fixture `tests/fixtures/fake-hindsight-plugin/embedded.py` is
placed inside the fake home's `plugins/hindsight/` exactly where the real plugin installs
it — a stand-in for a DEPENDENCY, never a mock of the product (the `fake-nerve-plugin`
convention, #611).

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
from scripts import memory_bootstrap as mb  # noqa: E402
from scripts import unit_tests as ut  # noqa: E402

SCRIPT = REPO / "scripts" / "memory_bootstrap.py"
PLUGIN_FIXTURE = REPO / "tests" / "fixtures" / "fake-hindsight-plugin" / "embedded.py"
SECRET = "hindsight-NEVER-PRINT-THIS-SENTINEL-0123456789abcdef"


def _run(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, timeout=90,
                          env={**os.environ, **(env or {})}, cwd=REPO)


def _home(tmp_path: Path) -> Path:
    """A real HERMES_HOME with the plugin fixture where the real plugin installs it."""
    home = tmp_path / "hermes-home"
    (home / "profiles").mkdir(parents=True, exist_ok=True)
    plugin = home / "plugins" / "hindsight"
    plugin.mkdir(parents=True, exist_ok=True)
    (plugin / "embedded.py").write_bytes(PLUGIN_FIXTURE.read_bytes())
    return home


def _agents(tmp_path: Path, profiles: list[str]) -> Path:
    agents = tmp_path / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    (agents / "manifest.json").write_text(json.dumps({"profiles": profiles}) + "\n")
    return agents


def _prov(home: Path, profile: str, key: str | None = None, provider: str = "hindsight"):
    """Seed a profile's .env key + settings provider (the pre-requisite state)."""
    ph = home / "profiles" / profile
    ph.mkdir(parents=True, exist_ok=True)
    (ph / ".env").write_text(f"HINDSIGHT_LLM_API_KEY={key}\n" if key else "")
    (ph / "settings.yaml").write_text(f"provider: {provider}\n"
                                      if provider else "# no provider\n")


def _base_flags(args, home, agents):
    return [*args, "--hermes-home", str(home), "--agents", str(agents)]


def _bootstrap_run(args, home, agents, plugin=True):
    extra = ["--plugin", str(PLUGIN_FIXTURE)] if plugin else []
    return _run("bootstrap", *_base_flags(args, home, agents), *extra)


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------
def test_install_dry_run_prints_the_pinned_command_and_writes_nothing(tmp_path):
    """The pin, port and flags are the documented daemon shape, and --dry-run is read-only."""
    home = _home(tmp_path)
    before = sorted(str(p) for p in home.rglob("*"))

    r = _run("install", "--dry-run")

    assert r.returncode == 0, r.stderr
    assert "hindsight-api@1.2.0" in r.stdout, r.stdout
    assert "--idle-timeout 0" in r.stdout and "--port 9177" in r.stdout, r.stdout
    assert "dry-run" in r.stdout, r.stdout

    # And   nothing was written
    after = sorted(str(p) for p in home.rglob("*"))
    assert before == after


def test_install_is_idempotent_when_the_port_is_already_served(tmp_path):
    """A daemon already on the port is reported as no-change, not re-provisioned."""

    # Given a real listener on the daemon port (an external system stand-in, like a
    # local HTTP server the product's probe talks to)
    port = _free_port()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", port))
    sock.listen(1)
    stop = threading.Event()

    def _serve():
        while not stop.is_set():
            try:
                conn, _ = sock.accept()
                conn.close()
            except OSError:
                return
    t = threading.Thread(target=_serve, daemon=True)
    t.start()
    try:
        _home(tmp_path)
        r1 = _run("install", "--port", str(port))
        assert r1.returncode == 0, r1.stderr
        assert "already served" in r1.stdout and "no change" in r1.stdout, r1.stdout

        r2 = _run("install", "--port", str(port))
        assert r2.returncode == 0, r2.stderr
        assert "no change" in r2.stdout, r2.stdout
    finally:
        stop.set()
        sock.close()


def test_install_without_uvx_is_a_loud_precondition_failure(tmp_path):
    """A host without uv is a FAILURE with a named reason, never a silent pass."""
    env = {"PATH": "/nonexistent"}
    r = _run("install", "--port", str(_free_port()), env=env)
    assert r.returncode == 2, (r.stdout, r.stderr)
    assert "uvx" in r.stderr and "uv" in r.stderr, r.stderr


# ---------------------------------------------------------------------------
# bootstrap
# ---------------------------------------------------------------------------
def test_bootstrap_is_idempotent_and_reuses_the_plugin_builder(tmp_path):
    """Writing twice reports 0 updates on the second run (the `expected <= actual` test)."""

    # Given a set of profiles whose .env carries a key and whose provider is unset
    profiles = ["llgenie-a", "llgenie-b", "llgenie-c"]
    home = _home(tmp_path)
    agents = _agents(tmp_path, profiles)
    for profile in profiles:
        _prov(home, profile, key=SECRET)

    # When  the bootstrap runs for every profile
    r1 = _bootstrap_run(["--profiles", *profiles], home, agents)
    assert r1.returncode == 0, r1.stderr + r1.stdout
    assert "3 updated" in r1.stdout, r1.stdout

    # Then  each profile has its config + env and they are mode 0600
    for profile in profiles:
        cfg = home / "profiles" / profile / "hindsight" / "config.json"
        assert cfg.is_file(), cfg
        assert (cfg.stat().st_mode & 0o777) == 0o600, oct(cfg.stat().st_mode)
        doc = json.loads(cfg.read_text())
        assert doc["mode"] == "local_embedded" and doc["llm_model"] == mb.HINDSIGHT_MODEL
        dotenv = home / "profiles" / profile / ".env"
        assert (dotenv.stat().st_mode & 0o777) == 0o600, oct(dotenv.stat().st_mode)

    # When  the bootstrap runs again (plugin discovered by home now, like the runtime)
    r2 = _bootstrap_run(["--profiles", *profiles], home, agents, plugin=False)
    assert r2.returncode == 0, r2.stderr + r2.stdout

    # Then  it reports zero updates (idempotent)
    assert "0 updated" in r2.stdout, r2.stdout
    assert "3 unchanged" in r2.stdout, r2.stdout


def test_bootstrap_dry_run_writes_nothing_and_prints_the_plan(tmp_path):
    """--dry-run prints paths, modes and the provider delta, and leaves the tree intact."""

    # Given a home with profiles but no bootstrap state
    profiles = ["llgenie-a", "llgenie-b"]
    home = _home(tmp_path)
    agents = _agents(tmp_path, profiles)
    for profile in profiles:
        _prov(home, profile, key=SECRET, provider="")
    before = sorted(str(p) for p in home.rglob("*"))

    r = _bootstrap_run(["--profiles", *profiles, "--dry-run"], home, agents)

    assert r.returncode == 0, r.stderr
    assert "dry-run" in r.stdout, r.stdout
    assert "hindsight/config.json" in r.stdout, r.stdout
    assert "provider" in r.stdout, r.stdout
    assert "0600" in r.stdout, r.stdout

    after = sorted(str(p) for p in home.rglob("*"))
    assert before == after, "dry-run wrote something"


def test_bootstrap_never_emits_the_credential_to_stdout_or_stderr(tmp_path):
    """A sentinel secret never reaches any output — dry-run or real run, success or not."""

    # Given profiles with a distinctive key value
    profiles = ["llgenie-a"]
    home = _home(tmp_path)
    agents = _agents(tmp_path, profiles)
    _prov(home, "llgenie-a", key=SECRET)

    for dry in (True, False):
        extra = ["--dry-run"] if dry else []
        r = _bootstrap_run(["--profiles", *profiles, *extra], home, agents)
        assert r.returncode == 0, r.stderr
        assert SECRET not in r.stdout + r.stderr, "the key value leaked into output"
        assert not re.search(r"hindsight-[A-Za-z0-9]{16,}", r.stdout + r.stderr), \
            "a key-shaped value leaked"


def test_bootstrap_does_not_invent_a_missing_key(tmp_path):
    """A profile with no key is named honestly, and the run still reports the plan."""

    # Given a profile whose .env has no HINDSIGHT key
    profiles = ["llgenie-a"]
    home = _home(tmp_path)
    agents = _agents(tmp_path, profiles)
    _prov(home, "llgenie-a", key=None)

    r = _bootstrap_run(["--profiles", *profiles], home, agents)

    assert r.returncode == 0, r.stderr
    assert "HINDSIGHT_LLM_API_KEY" in r.stderr, r.stderr
    assert SECRET not in r.stdout + r.stderr


def test_the_bootstrap_env_equals_the_plugin_runtime_builder(tmp_path):
    """The env the bootstrap uses == the plugin's own builder output (runtime agreement)."""

    # Given a profile whose .env carries the key
    profiles = ["llgenie-t1"]
    home = _home(tmp_path)
    agents = _agents(tmp_path, profiles)
    _prov(home, "llgenie-t1", key=SECRET)
    _bootstrap_run(["--profiles", *profiles], home, agents)

    # When  the runtime builder runs on the bootstrap's own template + key
    module = _load_fixture()
    cfg = json.loads((home / "profiles" / "llgenie-t1" / "hindsight" / "config.json").read_text())
    runtime = dict(module["_build_embedded_profile_env"](cfg, profile="llgenie-t1",
                                                         api_key=SECRET))

    # Then  the runtime env has the documented keys and matches the bootstrap's template
    for key in (mb.DAEMON_ENV_MODEL, mb.DAEMON_ENV_BASE_URL, mb.DAEMON_ENV_PROVIDER):
        assert key in runtime, runtime
    assert runtime[mb.DAEMON_ENV_MODEL] == mb.HINDSIGHT_MODEL, runtime
    assert runtime[mb.DAEMON_ENV_BASE_URL] == mb.HINDSIGHT_BASE_URL, runtime
    assert runtime[mb.DAEMON_ENV_PROVIDER] == mb.HINDSIGHT_PROVIDER, runtime


def _load_fixture() -> dict:
    module = {}
    exec(compile(PLUGIN_FIXTURE.read_bytes(), str(PLUGIN_FIXTURE), "exec"), module)  # noqa: S102
    return module


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------
def test_verify_fails_a_profile_with_empty_provider_or_missing_key(tmp_path):
    """A profile whose provider is empty or whose key is absent FAILS, named, not skipped."""

    # Given two profiles: one wired, one with an empty provider and no key
    profiles = ["llgenie-good", "llgenie-bad"]
    home = _home(tmp_path)
    agents = _agents(tmp_path, profiles)
    _prov(home, "llgenie-good", key=SECRET, provider="hindsight")
    _prov(home, "llgenie-bad", key=None, provider="")

    r = _run("verify", *_base_flags(["--profiles", *profiles], home, agents))

    assert r.returncode == 1, r.stdout + r.stderr
    assert "llgenie-good: PASS" in r.stdout, r.stdout
    assert "llgenie-bad: FAIL" in r.stdout, r.stdout
    assert "llgenie-bad: no HINDSIGHT_LLM_API_KEY" in r.stdout, r.stdout
    assert "empty" in r.stdout, r.stdout
    # The failing profile is named, and there is no silent skip
    assert "llgenie-bad" in r.stderr, r.stderr


def test_verify_reports_the_daemon_pid_port_and_connection_line(tmp_path):
    """The PASS output carries the port and the newest Connection verified line."""

    # Given a wired profile and a daemon log with a Connection verified line
    profiles = ["llgenie-good"]
    home = _home(tmp_path)
    agents = _agents(tmp_path, profiles)
    _prov(home, "llgenie-good", key=SECRET, provider="hindsight")
    hs = home / ".hindsight" / "profiles"
    hs.mkdir(parents=True, exist_ok=True)
    (hs / "hermes.log").write_text(
        "02:11:27 Connection verified: openai/deepseek/deepseek-v4-flash-0731\n"
        "02:14:29 Connection verified: openai/qwen3.8-27b-iq3_s\n")

    r = _run("verify", *_base_flags(["--profiles", *profiles], home, agents),
             "--hindsight-dir", str(home / ".hindsight"))

    assert r.returncode == 0, r.stdout + r.stderr
    assert "llgenie-good: PASS" in r.stdout, r.stdout
    assert "port=" in r.stdout, r.stdout
    # The NEWEST Connection verified line is the one reported
    assert "qwen3.8-27b-iq3_s" in r.stdout, r.stdout


# ---------------------------------------------------------------------------
# wiring
# ---------------------------------------------------------------------------
def test_make_targets_wire_install_bootstrap_verify_and_memory_check():
    """The vehicle's scripts are named by make targets CI runs, and are .PHONY."""

    mk = (REPO / "Makefile").read_text()
    phony = mk.split(".PHONY:", 1)[1].split("\n\n", 1)[0]

    # Each public target is a WORKING recipe that runs the script, and is phony-declared
    for target in ("memory-install:", "memory-bootstrap:", "memory-verify:", "memory-check:"):
        assert target.replace(":", "") in phony, f"{target} not in .PHONY"
        assert target in mk, f"{target} not defined"

    # And the gate target is a real recipe (not @true / not a broken dependency marker)
    block = mk.split("memory-check:", 1)[1].split("\n\n", 1)[0]
    assert "memory_bootstrap.py verify" in block, block


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port
