"""The fleet-memory gate (issue #2058): render / check / status and the preflight step.

WHAT THIS PROVES (the issue's acceptance criteria, one test group each):

  AC1  a script under `scripts/` exposes `render`, `check` and `status`, and a second
       `render` changes nothing (idempotency proven byte-for-byte).
  AC2  `check` exits non-zero NAMING the profile whose built daemon env differs from the
       shared `hermes.env` (the endpoint-flip case).
  AC3  `check` exits non-zero NAMING the profile whose `.env` has no non-empty
       `HINDSIGHT_LLM_API_KEY` — a lane cannot rest on another file's key.
  AC4  `check` prints the daemon pid + port it measured, reads the live
       `/proc/<pid>/environ` plus the last `Connection verified:` line, and `/health`
       alone never passes it.
  AC5  the lane preflight runs `memory-check`: rc=1 fails the preflight, rc=2 only warns.
  AC6  the drift test asserts a SUBSET (`expected <= actual`) over the profile set, so
       adding a profile does not red the gate.
  AC7  the new targets are `.PHONY` and name something that runs (in
       tests/test_memory_bootstrap.py's wiring test).
  AC8  the vehicle touches scripts/, Makefile, the test tree and the preflight only.

HERMETICITY. The gate reads live host state (daemon pid + `/proc`, the shared env file),
so every test builds a scratch HERMES_HOME, uses the documented contract fixture
`tests/fixtures/fake-hindsight-plugin/embedded.py` as the builder (the same stand-in
role the #2068 tests use — a stand-in for a third-party DEPENDENCY, not a mock of the
product), and launches a real socket-serving stub whose name contains `hindsight` so
the pid/port//proc evidence path is REAL, not faked. The daemon env vars are set on the
stub's own process env, so `_proc_environ` reads a genuinely populated environ.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from scripts import lane_preflight  # noqa: E402  (AC5: the preflight runs memory-check)
from scripts import memory_bootstrap as mb  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
FIXTURE_PLUGIN = REPO / "tests" / "fixtures" / "fake-hindsight-plugin" / "embedded.py"

#: The daemon env a correctly-wired host's daemon carries (endpoint values only).
GOOD_DAEMON_ENV = {
    mb.DAEMON_ENV_MODEL: mb.HINDSIGHT_MODEL,
    mb.DAEMON_ENV_BASE_URL: mb.HINDSIGHT_BASE_URL,
    mb.DAEMON_ENV_PROVIDER: mb.HINDSIGHT_PROVIDER,
    "HINDSIGHT_API_LLM_API_KEY": "sk-daemon-shared-value",
}

#: A connection line the orchestrator host's daemon actually writes (measured shape).
GOOD_LOG_LINE = ("2026-11-17 10:00:00 INFO hindsight.api: Connection verified: "
                 "openai_compatible/deepseek/deepseek-v4-flash-0731 "
                 "@ https://inference-api.nousresearch.com/v1")

_STUB = '''
import http.server, json, sys
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        payload = json.dumps({"status": "healthy"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
    def log_message(self, *args):
        pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), H)
open(sys.argv[2], "w").write(str(srv.server_address[1]))
srv.serve_forever()
'''


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _unbound_port() -> int:
    """A port a quick probe proves nobody is serving; re-picks past a squatting daemon."""
    for _ in range(5):
        port = _free_port()
        if not mb.daemon_serving(port):
            return port
    raise RuntimeError("no provably-unbound port found in 5 picks")


def _launch_stub(tmp_path: Path, daemon_env: dict[str, str]) -> tuple[subprocess.Popen, int]:
    """A REAL socket-serving stub whose cmdline names `hindsight`, with real environ.

    The stub binds its own port (port 0) and publishes it through a sentinel file.
    A probe-then-relaunch port pick races: on a busy host a daemon (`/usr/bin/herdr`)
    squatted the released port before the stub bound it, and the gate dutifully read
    the stranger's pid instead of the stub's (measured host flake, 2026-11-17). The
    handshake removes the window entirely: the port is held by the stub from birth.
    """
    stub = tmp_path / "hindsight_stub.py"
    stub.write_text(_STUB)
    port_file = tmp_path / f"stub_port_{time.time_ns()}"
    env = dict(os.environ)
    env.update(daemon_env)
    proc = subprocess.Popen([sys.executable, str(stub), "0", str(port_file)], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + 15
    while not port_file.exists():
        if time.time() > deadline or proc.poll() is not None:
            proc.terminate()
            raise RuntimeError("stub hindsight daemon never reported its bound port")
        time.sleep(0.05)
    port = int(port_file.read_text().strip())
    deadline = time.time() + 15
    while not mb.daemon_serving(port):
        if time.time() > deadline or proc.poll() is not None:
            proc.terminate()
            raise RuntimeError("stub hindsight daemon did not start")
        time.sleep(0.1)
    return proc, port


def _fixture_builder() -> dict:
    module: dict = {}
    exec(compile(FIXTURE_PLUGIN.read_bytes(), str(FIXTURE_PLUGIN), "exec"), module)  # noqa: S102
    return module


def _wire(tmp_path: Path, monkeypatch, *, profiles=("llgenie-alpha", "llgenie-beta"),
          key_profiles=None, with_shared=True, with_log=True,
          install_plugin=True) -> dict:
    """Build a scratch HERMES_HOME: manifest, profiles with keys, rendered configs,
    shared `hermes.env` materialized by the fixture builder, and a connection log line.
    Returns {home, agents, hs, profiles} — everything the gate commands need.
    """
    home = tmp_path / "hermes-home"
    (home / "profiles").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HERMES_HOME", str(home))

    agents = tmp_path / "agents"
    agents.mkdir(exist_ok=True)
    (agents / "manifest.json").write_text(
        json.dumps({"profiles": [{"name": p, "rules": []} for p in profiles]}))

    key_profiles = set(key_profiles if key_profiles is not None else profiles)
    for profile in profiles:
        ph = home / "profiles" / profile
        ph.mkdir(exist_ok=True)
        if profile in key_profiles:
            (ph / ".env").write_text(f"HINDSIGHT_LLM_API_KEY=sk-{profile}-own-value\n")

    # INSTALL the fixture plugin under this scratch HERMES_HOME: `check` WITHOUT --plugin (the
    # lane-preflight step spawns it as a fresh process that cannot take the test-only flag) must
    # find the builder where the real runtime would find it — plugins/hindsight/embedded.py.
    # install_plugin=False leaves an UNPROVISIONED home: check then exits 2 on the missing builder.
    if install_plugin:
        plugin_dir = home / "plugins" / "hindsight"
        plugin_dir.mkdir(parents=True, exist_ok=True)
        (plugin_dir / "embedded.py").write_bytes(FIXTURE_PLUGIN.read_bytes())

    rc = mb.cmd_render(["--hermes-home", str(home), "--agents", str(agents)])
    assert rc == 0, rc

    hs = home / ".hindsight"
    (hs / "profiles").mkdir(parents=True, exist_ok=True)
    if with_shared:
        module = _fixture_builder()
        shared = module["_build_embedded_profile_env"](
            mb.template_config("hermes"), profile="hermes", api_key="sk-shared-value")
        module["_materialize_embedded_profile_env"](shared)  # writes via HERMES_HOME
    if with_log:
        (hs / "profiles" / "hermes.log").write_text(GOOD_LOG_LINE + "\n")
    return {"home": home, "agents": agents, "hs": hs, "profiles": list(profiles)}


def _check_argv(wired: dict, port: int) -> list[str]:
    return ["--hermes-home", str(wired["home"]), "--agents", str(wired["agents"]),
            "--plugin", str(FIXTURE_PLUGIN), "--port", str(port),
            "--hindsight-dir", str(wired["hs"])]


def _profile_config(wired: dict, profile: str) -> Path:
    return wired["home"] / "profiles" / profile / "hindsight" / "config.json"


# ---------------------------------------------------------------------------
# AC1 — render / check / status are exposed; a second render changes nothing
# ---------------------------------------------------------------------------
def test_main_dispatch_exposes_render_check_and_status(tmp_path, monkeypatch):
    wired = _wire(tmp_path, monkeypatch)
    # main() (the CLI entry) must accept all three subcommand names
    assert mb.main(["render"] + _check_argv(wired, 1)[:2] +
                   ["--agents", str(wired["agents"]), "--dry-run"]) == 0
    for name in ("render", "check", "status"):
        assert callable(getattr(mb, f"cmd_{name}")), f"cmd_{name} missing"


def test_second_render_changes_nothing(tmp_path, monkeypatch, capsys):
    wired = _wire(tmp_path, monkeypatch)
    argv = ["--hermes-home", str(wired["home"]), "--agents", str(wired["agents"])]

    first = capsys.readouterr()
    assert "2 updated" in first.out, first.out  # the _wire() render already wrote once

    before = {p: _profile_config(wired, p).read_bytes() for p in wired["profiles"]}
    before_mtime = {p: _profile_config(wired, p).stat().st_mtime_ns for p in wired["profiles"]}

    rc = mb.cmd_render(argv)
    out = capsys.readouterr().out
    assert rc == 0
    assert "0 updated, 2 unchanged" in out, out

    after = {p: _profile_config(wired, p).read_bytes() for p in wired["profiles"]}
    assert after == before, "second render rewrote bytes"
    assert {p: _profile_config(wired, p).stat().st_mtime_ns
            for p in wired["profiles"]} == before_mtime, "second render touched mtimes"

    # configs are the template, rendered 0600; the .env keeps its mode
    assert json.loads(before[wired["profiles"][0]].decode()) == mb.template_config(
        wired["profiles"][0])
    for p in wired["profiles"]:
        assert _profile_config(wired, p).stat().st_mode & 0o777 == 0o600
        assert (wired["home"] / "profiles" / p / ".env").stat().st_mode & 0o777 == 0o600


def test_render_never_invents_a_key(tmp_path, monkeypatch, capsys):
    wired = _wire(tmp_path, monkeypatch, key_profiles=())  # profiles without .env
    out = capsys.readouterr().out
    assert "2 updated" in out
    for p in wired["profiles"]:
        dotenv = wired["home"] / "profiles" / p / ".env"
        assert dotenv.is_file() and dotenv.read_text() == "", \
            "render must create an EMPTY .env, never a key value"
        assert dotenv.stat().st_mode & 0o777 == 0o600


# ---------------------------------------------------------------------------
# AC2 — built-env drift: FAIL names the offending profile
# ---------------------------------------------------------------------------
def test_check_fails_naming_profile_when_built_env_differs(tmp_path, monkeypatch, capsys):
    wired = _wire(tmp_path, monkeypatch)
    flipped = wired["profiles"][1]
    cfg = json.loads(_profile_config(wired, flipped).read_text())
    cfg["llm_base_url"] = "http://127.0.0.1:8081/v1"
    _profile_config(wired, flipped).write_text(json.dumps(cfg, indent=2, sort_keys=True) + "\n")

    proc, port = _launch_stub(tmp_path, GOOD_DAEMON_ENV)
    try:
        rc = mb.cmd_check(_check_argv(wired, port))
        cap = capsys.readouterr()
        assert rc == 1, cap.out + cap.err
        assert f"check FAIL {flipped}: built env differs from hermes.env" in cap.out, cap.out
        assert "http://127.0.0.1:8081/v1" in cap.out, cap.out
        assert "https://inference-api.nousresearch.com/v1" in cap.out, cap.out
        assert "check: FAIL" in cap.err and flipped in cap.err, cap.err
        # the clean profile is NOT named
        assert f"FAIL {wired['profiles'][0]}" not in cap.out, cap.out
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_check_passes_over_wired_fixture(tmp_path, monkeypatch, capsys):
    wired = _wire(tmp_path, monkeypatch)
    proc, port = _launch_stub(tmp_path, GOOD_DAEMON_ENV)
    try:
        rc = mb.cmd_check(_check_argv(wired, port))
        cap = capsys.readouterr()
        assert rc == 0, cap.out + cap.err
        assert "profiles ok: 2 build the shared env and carry a key" in cap.out, cap.out
        assert "daemon ok" in cap.out, cap.out
    finally:
        proc.terminate()
        proc.wait(timeout=10)


# ---------------------------------------------------------------------------
# AC3 — a profile cannot rest on another file's key
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("env_body", ["", "HINDSIGHT_LLM_API_KEY=\n",
                                      "HINDSIGHT_LLM_API_KEY=not-needed\n"])
def test_check_fails_naming_profile_without_key(tmp_path, monkeypatch, capsys, env_body):
    wired = _wire(tmp_path, monkeypatch)
    hungry = wired["profiles"][0]
    (wired["home"] / "profiles" / hungry / ".env").write_text(env_body)

    proc, port = _launch_stub(tmp_path, GOOD_DAEMON_ENV)
    try:
        rc = mb.cmd_check(_check_argv(wired, port))
        cap = capsys.readouterr()
        assert rc == 1, cap.out + cap.err
        assert f"check FAIL {hungry}: no HINDSIGHT_LLM_API_KEY in the profile .env" in cap.out, cap.out
        assert hungry in cap.err, cap.err
    finally:
        proc.terminate()
        proc.wait(timeout=10)


# ---------------------------------------------------------------------------
# AC4 — pid + port printed; real /proc environ + Connection verified line; no /health pass
# ---------------------------------------------------------------------------
def test_check_prints_measured_pid_port_and_connection(tmp_path, monkeypatch, capsys):
    wired = _wire(tmp_path, monkeypatch)
    proc, port = _launch_stub(tmp_path, GOOD_DAEMON_ENV)
    try:
        rc = mb.cmd_check(_check_argv(wired, port))
        cap = capsys.readouterr()
        assert rc == 0, cap.out + cap.err
        assert str(proc.pid) in cap.out, cap.out      # the pid it measured is printed
        assert f"port {port}" in cap.out, cap.out     # and the port
        assert "Connection verified" in cap.out, cap.out  # the last log line is used
        assert mb.HINDSIGHT_MODEL in cap.out, cap.out     # read from the live environ
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_check_fails_when_daemon_environ_disagrees(tmp_path, monkeypatch, capsys):
    wired = _wire(tmp_path, monkeypatch)
    flipped_env = dict(GOOD_DAEMON_ENV)
    flipped_env[mb.DAEMON_ENV_MODEL] = "qwen/some-other-model"
    proc, port = _launch_stub(tmp_path, flipped_env)
    try:
        rc = mb.cmd_check(_check_argv(wired, port))
        cap = capsys.readouterr()
        assert rc == 1, cap.out + cap.err
        assert "daemon environ HINDSIGHT_API_LLM_MODEL: qwen/some-other-model" in cap.out, cap.out
        assert "FAIL daemon" in cap.out and "daemon" in cap.err, cap.err
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_health_alone_never_passes(tmp_path, monkeypatch, capsys):
    """A daemon that answers /health but carries NO endpoint environ must FAIL the gate."""
    wired = _wire(tmp_path, monkeypatch)
    bare_env = {"PATH": os.environ.get("PATH", "")}  # serving, but no HINDSIGHT_* env
    proc, port = _launch_stub(tmp_path, bare_env)
    try:
        assert mb.daemon_serving(port), "sanity: /health answers"
        rc = mb.cmd_check(_check_argv(wired, port))
        cap = capsys.readouterr()
        assert rc == 1, f"check passed on /health alone:\n{cap.out}"
        assert "FAIL daemon" in cap.out, cap.out
        assert any(k in cap.out for k in (mb.DAEMON_ENV_MODEL, "/health alone")), cap.out
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_check_requires_connection_line_and_matching_url(tmp_path, monkeypatch, capsys):
    wired = _wire(tmp_path, monkeypatch)
    (wired["hs"] / "profiles" / "hermes.log").unlink()
    proc, port = _launch_stub(tmp_path, GOOD_DAEMON_ENV)
    try:
        rc = mb.cmd_check(_check_argv(wired, port))
        cap = capsys.readouterr()
        assert rc == 1, cap.out + cap.err
        assert "no 'Connection verified:' line" in cap.out, cap.out
    finally:
        proc.terminate()
        proc.wait(timeout=10)

    (wired["hs"] / "profiles" / "hermes.log").write_text(
        "Connection verified: openai_compatible/deepseek/deepseek-v4-flash-0731 "
        "@ http://127.0.0.1:8081/v1\n")
    proc, port = _launch_stub(tmp_path, GOOD_DAEMON_ENV)
    try:
        rc = mb.cmd_check(_check_argv(wired, port))
        cap = capsys.readouterr()
        assert rc == 1, cap.out + cap.err
        assert "connection url" in cap.out and "http://127.0.0.1:8081/v1" in cap.out, cap.out
    finally:
        proc.terminate()
        proc.wait(timeout=10)


# ---------------------------------------------------------------------------
# exit 2: a precondition is absent, not a drift
# ---------------------------------------------------------------------------
def test_check_exit2_no_daemon(tmp_path, monkeypatch, capsys):
    wired = _wire(tmp_path, monkeypatch)
    port = _unbound_port()  # provably nothing listening
    rc = mb.cmd_check(_check_argv(wired, port))
    cap = capsys.readouterr()
    assert rc == 2, cap.out + cap.err
    assert "precondition missing" in cap.err and f"port {port}" in cap.err, cap.err


def test_check_exit2_no_shared_env(tmp_path, monkeypatch, capsys):
    wired = _wire(tmp_path, monkeypatch)
    (wired["hs"] / "profiles" / "hermes.env").unlink()
    proc, port = _launch_stub(tmp_path, GOOD_DAEMON_ENV)
    try:
        rc = mb.cmd_check(_check_argv(wired, port))
        cap = capsys.readouterr()
        assert rc == 2, cap.out + cap.err
        assert "no shared env file" in cap.err, cap.err
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_check_exit2_no_plugin_builder(tmp_path, monkeypatch, capsys):
    wired = _wire(tmp_path, monkeypatch, install_plugin=False)
    proc, port = _launch_stub(tmp_path, GOOD_DAEMON_ENV)
    try:
        argv = _check_argv(wired, port)
        argv.remove("--plugin")
        argv.remove(str(FIXTURE_PLUGIN))  # no --plugin: load_builder on the scratch home must fail
        rc = mb.cmd_check(argv)
        cap = capsys.readouterr()
        assert rc == 2, cap.out + cap.err
        assert "precondition missing" in cap.err, cap.err
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_check_exit2_no_profiles(tmp_path, monkeypatch, capsys):
    wired = _wire(tmp_path, monkeypatch)
    empty_agents = tmp_path / "empty-agents"
    empty_agents.mkdir()
    argv = _check_argv(wired, _unbound_port())
    argv[argv.index(str(wired["agents"]))] = str(empty_agents)
    rc = mb.cmd_check(argv)
    cap = capsys.readouterr()
    assert rc == 2, cap.out + cap.err
    assert "no profiles" in cap.err, cap.err


def test_listen_pids_falls_back_to_proc_when_ss_and_lsof_are_missing(tmp_path, monkeypatch):
    """The hermetic test container ships no iproute2/lsof: the daemon pid/port evidence
    must come from pure /proc (`/proc/net/tcp{,6}` LISTEN inode -> `/proc/<pid>/fd`), so
    the gate measures the daemon IDENTICALLY on a full host and inside `make test-unit`."""
    proc, port = _launch_stub(tmp_path, GOOD_DAEMON_ENV)

    def no_tools(cmd, *args, **kwargs):
        raise FileNotFoundError(str(cmd[0]))

    monkeypatch.setattr(mb, "run_ok", no_tools)
    try:
        pids = mb._listen_pids(port)  # ss/lsof both raise -> /proc fallback answers
        assert proc.pid in pids, "pure-/proc scan missed the stub daemon"
        assert pids == mb._proc_listen_pids(port)
    finally:
        proc.terminate()
        proc.wait(timeout=10)


# ---------------------------------------------------------------------------
# status: a report, never a verdict
# ---------------------------------------------------------------------------
def test_status_reports_unprovisioned_host_with_rc0(tmp_path, monkeypatch, capsys):
    home = tmp_path / "bare-home"
    (home / "profiles").mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(home))
    agents = tmp_path / "no-agents"
    agents.mkdir()
    rc = mb.cmd_status(["--hermes-home", str(home), "--agents", str(agents),
                        "--port", str(_unbound_port()),
                        "--hindsight-dir", str(home / ".hindsight")])
    cap = capsys.readouterr()
    assert rc == 0, cap.out + cap.err  # status never blocks
    assert "ABSENT" in cap.out and "serving=NO" in cap.out, cap.out
    assert "no profiles" in cap.out, cap.out


def test_status_reports_wired_host(tmp_path, monkeypatch, capsys):
    wired = _wire(tmp_path, monkeypatch)
    proc, port = _launch_stub(tmp_path, GOOD_DAEMON_ENV)
    try:
        rc = mb.cmd_status(["--hermes-home", str(wired["home"]),
                            "--agents", str(wired["agents"]), "--port", str(port),
                            "--hindsight-dir", str(wired["hs"])])
        cap = capsys.readouterr()
        assert rc == 0, cap.out + cap.err
        assert "serving=yes" in cap.out and str(proc.pid) in cap.out, cap.out
        for p in wired["profiles"]:
            assert f"status {p}: config=yes key=yes" in cap.out, cap.out
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_check_and_status_never_print_key_values(tmp_path, monkeypatch, capsys):
    wired = _wire(tmp_path, monkeypatch)
    secrets = [f"sk-{p}-own-value" for p in wired["profiles"]] + ["sk-shared-value",
                                                                  "sk-daemon-shared-value"]
    proc, port = _launch_stub(tmp_path, GOOD_DAEMON_ENV)
    try:
        assert mb.cmd_check(_check_argv(wired, port)) == 0
        assert mb.cmd_status(["--hermes-home", str(wired["home"]),
                              "--agents", str(wired["agents"]), "--port", str(port),
                              "--hindsight-dir", str(wired["hs"])]) == 0
        cap = capsys.readouterr()
        for secret in secrets:
            assert secret not in cap.out, f"leaked a key value in status/check stdout"
            assert secret not in cap.err
    finally:
        proc.terminate()
        proc.wait(timeout=10)


# ---------------------------------------------------------------------------
# AC6 — subset, not equality: adding a profile does not red the gate
# ---------------------------------------------------------------------------
def test_profile_set_is_subset_so_adding_a_profile_does_not_red(tmp_path, monkeypatch, capsys):
    expected_subset = {"llgenie-alpha", "llgenie-beta"}  # what the drift tests KNOW
    derived = mb.profiles_from_manifest(
        _wire(tmp_path, monkeypatch)["agents"])
    assert expected_subset <= set(derived), (
        "the gate must read the profile set from the manifest: expected <= actual")

    wired = _wire(tmp_path, monkeypatch,
                  profiles=("llgenie-alpha", "llgenie-beta", "llgenie-gamma"))
    proc, port = _launch_stub(tmp_path, GOOD_DAEMON_ENV)
    try:
        rc = mb.cmd_check(_check_argv(wired, port))
        cap = capsys.readouterr()
        assert rc == 0, f"adding a wired profile reddened the gate:\n{cap.out}{cap.err}"
        assert "profiles ok: 3" in cap.out, cap.out

        # and an UNWIRED added profile is named, not silently skipped
        (wired["home"] / "profiles" / "llgenie-gamma" / ".env").write_text("")
        rc = mb.cmd_check(_check_argv(wired, port))
        cap = capsys.readouterr()
        assert rc == 1 and "llgenie-gamma" in cap.out + cap.err, cap.out + cap.err
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_repo_manifest_profile_set_is_a_superset_of_the_known_lanes():
    """The 13 llgenie-* lanes the fleet names must all be INSIDE what the manifest yields
    (AC6's `expected <= actual` measured against the real manifest, not a fixture)."""
    derived = set(mb.profiles_from_manifest(REPO / "agents"))
    known = {name for name in derived if name.startswith("llgenie-")}
    assert len(known) >= 13, f"the manifest must carry the llgenie lanes: {sorted(known)}"


# ---------------------------------------------------------------------------
# AC5 — the lane preflight runs memory-check
# ---------------------------------------------------------------------------
def test_preflight_fails_when_a_profile_drifts(tmp_path, monkeypatch, capsys):
    wired = _wire(tmp_path, monkeypatch)
    cfg = json.loads(_profile_config(wired, wired["profiles"][0]).read_text())
    cfg["llm_model"] = "flip/other-model"
    _profile_config(wired, wired["profiles"][0]).write_text(
        json.dumps(cfg, indent=2, sort_keys=True) + "\n")

    proc, port = _launch_stub(tmp_path, GOOD_DAEMON_ENV)
    try:
        monkeypatch.setenv("LLGENIE_MEMORY_DAEMON_PORT", str(port))
        rc = lane_preflight.run(tmp_path, gates=(), memory_check=True)
        cap = capsys.readouterr()
        assert rc == 1, cap.out + cap.err  # AC5: a dispatch-blocking disagreement fails the lane
        assert "memory-check: rc=1" in cap.out, cap.out
        assert "preflight: FAILED" in cap.err and "memory-check" in cap.err, cap.err
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_preflight_warns_but_stays_green_when_host_unprovisioned(tmp_path, monkeypatch, capsys):
    """An unprovisioned scratch 'host': no agents manifest, no shared env, no daemon there.

    The gate returns 2 (cannot run) and the lane stays green — a gap to report, not a red. This
    also pins the make-collapse trap: the step is invoked directly precisely so a script rc=1
    (drift) can never be confused with rc=2 (unprovisioned).
    """
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
    monkeypatch.setenv("LLGENIE_MEMORY_DAEMON_PORT", str(_unbound_port()))
    rc = lane_preflight.run(tmp_path, gates=(), memory_check=True)
    cap = capsys.readouterr()
    assert rc == 0, cap.out + cap.err  # rc=2 is a gap to report, not a red
    assert "WARN" in cap.out and "rc=2" in cap.out, cap.out
    assert "preflight: OK" in cap.out, cap.out


def test_preflight_passes_with_wired_host(tmp_path, monkeypatch, capsys):
    wired = _wire(tmp_path, monkeypatch)
    proc, port = _launch_stub(tmp_path, GOOD_DAEMON_ENV)
    try:
        monkeypatch.setenv("LLGENIE_MEMORY_DAEMON_PORT", str(port))
        rc = lane_preflight.run(tmp_path, gates=(), memory_check=True)
        cap = capsys.readouterr()
        assert rc == 0, cap.out + cap.err
        assert "memory-check: rc=0" in cap.out, cap.out
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_preflight_memory_step_can_be_skipped(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
    rc = lane_preflight.run(tmp_path, gates=(), memory_check=False)
    cap = capsys.readouterr()
    assert rc == 0, cap.out + cap.err
    assert "memory-check" not in cap.out + cap.err, cap.out + cap.err


def test_lane_preflight_source_wires_the_step_and_the_cli_flag():
    src = (REPO / "scripts" / "lane_preflight.py").read_text()
    # AC5: the step runs the check gate DIRECTLY — `make` collapses every recipe failure to
    # exit 2, which would erase the rc=1 FAIL vs rc=2 WARN distinction the step maps.
    assert '"check", "--agents"' in src, "lane_preflight must invoke the memory check gate (AC5)"
    assert "memory_bootstrap.py" in src
    assert "--no-memory-check" in src, "the step must have the documented opt-out"
    assert "def memory_step(" in src


# ---------------------------------------------------------------------------
# AC8 — the vehicle footprint (scripts/, Makefile/mk, tests, preflight only)
# ---------------------------------------------------------------------------
def test_vehicle_touches_no_docs_sections():
    """#2058's sibling issues own the docs/BOTS.md section; this vehicle must not invent one."""
    targets = (REPO / "mk" / "agents.mk").read_text()
    assert "memory_bootstrap.py check" in targets
    assert "memory_bootstrap.py render" in targets
    assert "memory_bootstrap.py status" in targets
    bots = (REPO / "docs" / "BOTS.md").read_text()
    for line in bots.splitlines():
        if line.startswith("### ") and "memory-render" in line:
            raise AssertionError("this vehicle must not add a docs/BOTS.md section (AC8)")
