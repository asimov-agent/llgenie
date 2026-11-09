"""Tests for the stall detector's corrected log axis (issue #2155).

The detector classifies on the lane `agent.log` mtime AND the `API call #N`
counter over two samples >= 60 s apart — never the per-run `<kanban>/logs/<task>.log`,
never `last_heartbeat_at` / `max_runtime_seconds` / bare task status. A task must
read STALLED on two consecutive verdicts before any action; the kanban path sends
no signal to a worker pid; the DM-waiter reaper is structurally separate.
"""

import ast
import importlib.util
import inspect
import sqlite3
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

# Load the shipped script WITHOUT adding a new import root and WITHOUT writing
# bytecode into the tree. `sys.path.insert` into `agents/.../scripts/` would trip
# the suite's one-import-root guard (issue #796, #1101: "a NEW import root is
# refused"), and a plain `import` drops `scripts/__pycache__/stall_reclaim.cpython-*.pyc`
# into the tree, which `make sync-agent-profile` would copy into the live profile
# (the #2155 lane's own `test_loading_the_shipped_scripts_leaves_no_bytecode_in_the_tree`
# exists for exactly this). A test must not mutate the tree it tests.
_prior_dwb = sys.dont_write_bytecode
sys.dont_write_bytecode = True
try:
    _stall_src = REPO / "agents" / "llgenie-planner" / "scripts" / "stall_reclaim.py"
    _spec = importlib.util.spec_from_file_location("stall_reclaim", _stall_src)
    sr = importlib.util.module_from_spec(_spec)
    # `stall_reclaim.py` is a module-level dataclass file; dataclasses resolve
    # `cls.__module__` against `sys.modules`, so the module must be registered
    # (the importlib pattern) or `_is_type` fails on the well-formed class.
    sys.modules[_spec.name] = sr
    _spec.loader.exec_module(sr)
finally:
    sys.dont_write_bytecode = _prior_dwb

STALL_MIN = sr.STALL_MIN
MAX_CPU = sr.MAX_CPU_TICKS
NOW = 1_000_000.0


def stale(age_sec, api=41, cpu=100):
    """A sample with a fixed old log age, unchanged api and flat cpu."""
    return sr.Sample(log_mtime=NOW - age_sec, api_count=api, cpu_ticks=cpu)


def worker(tid="t_x", pid=9999, age_min=40, profile="test-lane"):
    return sr.Worker(task_id=tid, pid=pid, profile=profile,
                     started_at=int(NOW - age_min * 60))


def joins(*samples):
    """An iterator of samples consumed in order (2 per verdict)."""
    return iter(list(samples))


def counters():
    return {"stalled": 0, "active": 0, "young": 0, "orphan": 0,
            "reclaimed": 0, "blocked": 0}


def _dotted(node):
    """The dotted source name of a call/attribute target, e.g. `os.kill`."""
    parts = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return ".".join(reversed(parts)) if parts else None


def _signal_calls(src):
    """Map every signal-primitive call (kill / signal.*) to its enclosing function."""
    tree = ast.parse(src)
    out = {}

    def walk(node, fname):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fname = node.name
        if isinstance(node, ast.Call):
            dotted = _dotted(node.func)
            if dotted is not None and ("kill" in dotted or dotted.startswith("signal")):
                out.setdefault(fname, set()).add(dotted)
        for child in ast.iter_child_nodes(node):
            walk(child, fname)

    walk(tree, None)
    return out


@pytest.fixture
def kanban_worker_env(monkeypatch):
    """Monkeypatch the /proc-facing guards so sweep_worker sees a live kanban worker."""
    monkeypatch.setattr(sr, "pid_alive", lambda pid: True)
    monkeypatch.setattr(sr, "read_cmdline",
                        lambda pid: "python3 -m hermes_cli.kanban_worker_client")


# --------------------------------------------------------------------------- #
# threshold matrix (issue #2155 acceptance: threshold matrix)                 #
# --------------------------------------------------------------------------- #

def test_threshold_matrix():
    """The YOUNG/ACTIVE/STALLED matrix over the corrected operands."""
    # fresh process -> YOUNG
    assert sr.classify(5, 40, False, 1) == sr.YOUNG
    # old process + fresh log -> YOUNG
    assert sr.classify(40, 5, False, 1) == sr.YOUNG
    # old + stale log + busy CPU -> ACTIVE
    assert sr.classify(40, 40, False, MAX_CPU + 1) == sr.ACTIVE
    # old + stale + idle -> STALLED
    assert sr.classify(40, 40, False, 1) == sr.STALLED
    # old + stale + no agent.log + idle -> STALLED
    assert sr.classify(40, None, False, 1) == sr.STALLED


# --------------------------------------------------------------------------- #
# log axis (issue #2155 acceptance criteria)                                  #
# --------------------------------------------------------------------------- #

def test_advancing_agent_log_is_active_with_old_kanban_log_and_0_cpu():
    """Regression pin for the live false positive: a worker whose agent.log
    advances inside the sample window is ACTIVE even at ~0 CPU delta."""
    s1 = sr.Sample(log_mtime=NOW - 5 * 60, api_count=41, cpu_ticks=100)
    s2 = sr.Sample(log_mtime=NOW - 0.5 * 60, api_count=44, cpu_ticks=101)  # advanced
    v = sr.verdict_from(worker(), s1, s2, NOW)
    assert v.verdict == sr.ACTIVE


def test_no_log_and_no_api_and_idle_is_stalled():
    """A worker with no agent.log write, no API advance and ~0 CPU reads STALLED."""
    v = sr.verdict_from(worker(), stale(34 * 60), stale(34 * 60), NOW)
    assert v.verdict == sr.STALLED


def test_api_counter_advance_alone_is_active():
    """The API-call counter rising between samples is a live signal on its own."""
    s1 = sr.Sample(log_mtime=NOW - 34 * 60, api_count=41, cpu_ticks=100)
    s2 = sr.Sample(log_mtime=NOW - 33 * 60, api_count=44, cpu_ticks=100)
    v = sr.verdict_from(worker(), s1, s2, NOW)
    assert v.verdict == sr.ACTIVE


def test_unused_database_fields_are_not_operands():
    """last_heartbeat_at / max_runtime_seconds / bare status are never operands."""
    src = Path(sr.__file__).read_text()
    sel = src[src.find("SELECT task_id"):src.find("WHERE status='running'")]
    assert "last_heartbeat_at" not in sel
    assert "max_runtime_seconds" not in sel
    classify_src = inspect.getsource(sr.classify)
    assert "last_heartbeat_at" not in classify_src
    assert "max_runtime_seconds" not in classify_src


# --------------------------------------------------------------------------- #
# operands printed on every verdict line                                      #
# --------------------------------------------------------------------------- #

def test_verdict_line_prints_both_samples_operands():
    """Each verdict line carries both samples' operands (api before->after, cpu p/q)."""
    v = sr.verdict_from(worker("t_x", 555), stale(34 * 60), stale(34 * 60), NOW)
    line = v.line(555)
    assert v.verdict == sr.STALLED
    assert "pid=555" in line
    assert "api=#41->#41" in line
    assert "cpu=100t/100t" in line
    assert "samples=2" in line


# --------------------------------------------------------------------------- #
# two consecutive STALLED verdicts before any action                          #
# --------------------------------------------------------------------------- #

def test_two_consecutive_stalled_verdicts_required(monkeypatch, capsys, tmp_path):
    """A single STALLED verdict never acts; the second verdict must confirm."""
    monkeypatch.setattr(sr, "pid_alive", lambda pid: True)
    monkeypatch.setattr(sr, "read_cmdline",
                        lambda pid: "python3 -m hermes_cli.kanban_worker_client")
    monkeypatch.setattr(sr, "STATE", str(tmp_path / ".stall_reclaims.json"))
    # v1 STALLED (stale x2), v2 ACTIVE (log advanced) -> no action
    seq = joins(stale(34 * 60), stale(34 * 60),
                stale(34 * 60), sr.Sample(NOW - 0.5 * 60, 44, 101))

    def fake(pid, profile):
        return next(seq)

    c = counters()
    sr.sweep_worker(worker("t_A"), NOW, fake, 0.0, True, c)
    out = capsys.readouterr().out
    assert c["stalled"] == 0
    assert c["active"] == 1
    assert c["reclaimed"] == 0
    assert "STALLED" in out and "ACTIVE" in out


def test_reclaim_only_after_two_consecutive_stalled(monkeypatch, capsys, tmp_path):
    """Both verdicts STALLED -> the task is reclaimed."""
    monkeypatch.setattr(sr, "pid_alive", lambda pid: True)
    monkeypatch.setattr(sr, "read_cmdline",
                        lambda pid: "python3 -m hermes_cli.kanban_worker_client")
    monkeypatch.setattr(sr, "STATE", str(tmp_path / ".stall_reclaims.json"))
    monkeypatch.setattr(sr, "reclaim_count", lambda task: 1)  # below the cap
    reclaimed = []
    monkeypatch.setattr(sr, "reclaim_task",
                        lambda w, kind: reclaimed.append(w.task_id) or True)
    monkeypatch.setattr(sr, "reclaim_record", lambda task: None)

    seq = joins(stale(34 * 60), stale(34 * 60), stale(34 * 60), stale(34 * 60))

    def fake(pid, profile):
        return next(seq)

    c = counters()
    sr.sweep_worker(worker("t_A"), NOW, fake, 0.0, True, c)
    assert c["stalled"] == 1
    assert reclaimed == ["t_A"]
    assert c["reclaimed"] == 1


# --------------------------------------------------------------------------- #
# allowlist                                                                   #
# --------------------------------------------------------------------------- #

def test_allowlist_rejects_non_worker_and_unknown(tmp_path):
    """A non-worker pid and an unknown (not-running) task are never candidates."""
    assert sr.is_kanban_worker_cmd("python3 -m hermes_cli.kanban_worker_client")
    assert not sr.is_kanban_worker_cmd("python3 -m something.else")
    assert not sr.is_kanban_worker_cmd(None)

    db = tmp_path / "t.db"
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE task_runs(task_id TEXT, worker_pid INTEGER, "
                "profile TEXT, started_at INTEGER, status TEXT)")
    con.execute("INSERT INTO task_runs VALUES('t_unknown', 9999, 'lane', 100, 'done')")
    con.execute("INSERT INTO task_runs VALUES('t_running', 1000, 'lane', 100, 'running')")
    con.commit()
    con.close()
    cands = list(sr.running_candidates(str(db)))
    assert all(c.task_id != "t_unknown" for c in cands)
    assert any(c.task_id == "t_running" for c in cands)


# --------------------------------------------------------------------------- #
# churn cap                                                                   #
# --------------------------------------------------------------------------- #

def test_churn_cap_blocks_after_max_reclaims(monkeypatch, capsys, tmp_path):
    """3 reclaims in the window -> kanban block, never a recycle."""
    monkeypatch.setattr(sr, "pid_alive", lambda pid: True)
    monkeypatch.setattr(sr, "read_cmdline",
                        lambda pid: "python3 -m hermes_cli.kanban_worker_client")
    monkeypatch.setattr(sr, "STATE", str(tmp_path / ".stall_reclaims.json"))
    monkeypatch.setattr(sr, "reclaim_count", lambda task: sr.MAX_RECLAIMS)
    blocked = []
    monkeypatch.setattr(sr, "block_task", lambda w, p, l, c: blocked.append(w.task_id) or True)
    reclaimed = []
    monkeypatch.setattr(sr, "reclaim_task", lambda w, k: reclaimed.append(w.task_id) or True)
    seq = joins(stale(34 * 60), stale(34 * 60), stale(34 * 60), stale(34 * 60))

    def fake(pid, profile):
        return next(seq)

    c = counters()
    sr.sweep_worker(worker("t_A"), NOW, fake, 0.0, True, c)
    assert blocked == ["t_A"]
    assert reclaimed == []  # never recycled past the cap
    assert c["blocked"] == 1
    assert c["reclaimed"] == 0


def test_churn_cap_recycles_below_max(monkeypatch, tmp_path):
    """1 reclaim in the window -> recycle."""
    monkeypatch.setattr(sr, "STATE", str(tmp_path / ".stall_reclaims.json"))
    monkeypatch.setattr(sr, "reclaim_count", lambda task: 1)
    reclaimed = []
    monkeypatch.setattr(sr, "reclaim_task", lambda w, k: reclaimed.append(w.task_id) or True)
    monkeypatch.setattr(sr, "reclaim_record", lambda task: None)
    sr._act_on_stalled(worker("t_A"),
                       sr.verdict_from(worker("t_A"), stale(1), stale(1), NOW),
                       counters())
    assert reclaimed == ["t_A"]


def test_reclaims_older_than_window_pruned(monkeypatch, tmp_path):
    """Reclaims older than the window are pruned and do not count."""
    state = tmp_path / ".stall_reclaims.json"
    monkeypatch.setattr(sr, "STATE", str(state))
    old = NOW - (sr.STATE_WINDOW_H * 3600 + 3600)
    state.write_text(__import__("json").dumps({"t_A": [old, old + 60], "t_B": [old]}))
    assert sr.reclaim_count("t_A") == 0  # both outside the window
    assert sr.reclaim_count("t_B") == 0
    sr.reclaim_record("t_A")
    new = __import__("json").loads(state.read_text())
    assert len(new["t_A"]) == 1  # the old entries were pruned, only the new one remains
    assert "t_B" in new and new["t_B"] == []  # pruned to empty


# --------------------------------------------------------------------------- #
# negative control + DRY leaves no state file                                 #
# --------------------------------------------------------------------------- #

def _make_db(tmp_path, pid=9999, status="running", age_min=40):
    db = tmp_path / "board.db"
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE task_runs(task_id TEXT, worker_pid INTEGER, "
                "profile TEXT, started_at INTEGER, status TEXT)")
    con.execute("INSERT INTO task_runs VALUES('t_1', ?, ?, ?, ?)",
                (pid, "test-lane", int(NOW - age_min * 60), status))
    con.commit()
    con.close()
    return db


def test_negative_control_stalled_zero_changes_nothing(monkeypatch, capsys, tmp_path):
    """No stale worker -> stalled=0, nothing changed, no state file."""
    monkeypatch.setattr(sr, "pid_alive", lambda pid: True)
    monkeypatch.setattr(sr, "read_cmdline",
                        lambda pid: "python3 -m hermes_cli.kanban_worker_client")
    monkeypatch.setattr(sr, "DM_ENABLED", False)
    monkeypatch.setattr(sr, "STATE", str(tmp_path / ".stall_reclaims.json"))
    state = tmp_path / ".stall_reclaims.json"

    def fake(pid, profile):
        # always a live worker: log advancing inside the sample window
        return sr.Sample(NOW - 0.4 * 60, 44, 101)

    sr.run(apply=True, sample_fn=fake, delay=0.0,
           db_path=str(_make_db(tmp_path)), now=NOW)
    out = capsys.readouterr().out
    assert "tasks: stalled=0" in out
    assert not state.exists()


def test_dry_run_creates_no_state_file(monkeypatch, capsys, tmp_path):
    """A DRY run with a genuinely stalled worker still creates no state file."""
    monkeypatch.setattr(sr, "pid_alive", lambda pid: True)
    monkeypatch.setattr(sr, "read_cmdline",
                        lambda pid: "python3 -m hermes_cli.kanban_worker_client")
    monkeypatch.setattr(sr, "DM_ENABLED", False)
    monkeypatch.setattr(sr, "STATE", str(tmp_path / ".stall_reclaims.json"))
    state = tmp_path / ".stall_reclaims.json"

    def fake(pid, profile):
        # a dead-idle worker: no log write, no api advance, flat cpu
        return sr.Sample(NOW - 34 * 60, 41, 100)

    sr.run(apply=False, sample_fn=fake, delay=0.0,
           db_path=str(_make_db(tmp_path)), now=NOW)
    out = capsys.readouterr().out
    assert "stalled=1" in out
    assert "mode=DRY" in out
    assert not state.exists()


# --------------------------------------------------------------------------- #
# kanban path contains no signal; task_runs pid can never reach the DM reaper #
# --------------------------------------------------------------------------- #

def test_kanban_path_has_no_signal_primitive():
    """No kill / os.kill / SIGTERM is reachable from the kanban action path."""
    src = Path(sr.__file__).read_text()
    calls = _signal_calls(src)
    non_reaper = {f: toks for f, toks in calls.items() if f != "_reap_dm_waiters"}
    assert non_reaper == {}, \
        f"signal primitives outside the DM reaper (leaked into kanban path): {non_reaper}"
    # the DM reaper keeps the signal primitives (we did not delete coverage)
    assert "_reap_dm_waiters" in calls


def test_task_runs_pid_never_reaches_dm_reaper():
    """The DM reaper enumerates its own pids and takes no task_runs pid."""
    sig = inspect.signature(sr._reap_dm_waiters)
    assert set(sig.parameters) == {"apply"}  # no pid can be passed in
    tree = ast.parse(inspect.getsource(sr._reap_dm_waiters))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    attrs = {a.attr for a in ast.walk(tree) if isinstance(a, ast.Attribute)}
    # its pid source is its own pgrep enumeration of bot_mode_dm.py
    src = inspect.getsource(sr._reap_dm_waiters)
    assert "bot_mode_dm.py" in src and "pgrep" in src
    # it never references a task_runs row, a worker field, or the candidate source
    for forbidden in ("task_id", "worker_pid", "running_candidates", "db_path"):
        assert forbidden not in names and forbidden not in attrs, forbidden
    assert "Worker(" not in src
