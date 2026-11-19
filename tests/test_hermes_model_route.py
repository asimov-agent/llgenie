"""Issue #2931: the model-route report names the chain member that actually served a leg.

`scripts/hermes_model_route.py` runs after every Hermes bot recipe and reads the lane's Hermes
session store: it prints exactly one `model-route: <model-id>` line for the newest session that
started inside the leg's window, or fails loudly when no evidence backs such a line. These are
that contract's proofs: profile-home-first store resolution (the #2929 measurement: a
`-p <lane>` run writes to the profile home), the window filter, every named failure, the exact
line shape, the no-secret line, and the wiring rule that the report never changes the leg's
own exit status.
"""
from __future__ import annotations

import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "hermes_model_route.py"

PRIMARY = "meituan/longcat-2.5:free"
LAST_RESORT = "deepseek/deepseek-v4-flash-0731"


def _store(path: Path, sessions: list[tuple[str, str | None, float]]) -> Path:
    """A lane store with the shape Hermes keeps: sessions(id, model, started_at, model_config)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE sessions (id TEXT PRIMARY KEY, model TEXT, started_at REAL, model_config TEXT);"
    )
    for sid, model, started in sessions:
        conn.execute("INSERT INTO sessions VALUES (?, ?, ?, ?)", (sid, model, started, None))
    conn.commit()
    conn.close()
    return path


def _run(home: Path, lane: str, since: float | None = None) -> subprocess.CompletedProcess:
    """Run the report as the legs do: HERMES_HOME in the env, the lane and window as arguments."""
    env = {"HERMES_HOME": str(home), "PATH": os.environ.get("PATH", "")}
    argv = [sys.executable, str(SCRIPT), "--lane", lane]
    if since is not None:
        argv += ["--since", str(since)]
    return subprocess.run(argv, capture_output=True, text=True, env=env, timeout=30)


def test_profile_home_store_is_read_before_the_global_one(tmp_path):
    """The lane's own home is the answer when it exists (issue #2929 measurement); the global
    store's model must never surface for a lane that has a profile home."""

    # Given  a global store naming the last resort AND a profile store naming the primary
    _store(tmp_path / "state.db", [("g", LAST_RESORT, 5000.0)])
    _store(tmp_path / "profiles" / "llgenie-planner" / "state.db", [("p", PRIMARY, 5000.0)])

    # When   the report runs for that lane
    proc = _run(tmp_path, "llgenie-planner")

    # Then   the line names the profile store's model, and the global store never speaks
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout == f"model-route: {PRIMARY}\n", proc.stdout
    assert LAST_RESORT not in proc.stdout + proc.stderr


def test_a_lane_without_a_profile_home_falls_back_to_the_global_store(tmp_path):
    """Only a lane with no profile home is audited in the global store (same rule as the smoke)."""

    # Given  only the global store
    _store(tmp_path / "state.db", [("g", PRIMARY, 5000.0)])

    # When   the report runs for a lane whose profile home does not exist
    proc = _run(tmp_path, "llgenie-no-such-lane")

    # Then   it reads the global store
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout == f"model-route: {PRIMARY}\n", proc.stdout


def test_the_window_selects_the_legs_own_session(tmp_path):
    """An earlier leg's session must not be attributed to this leg: the window is the filter."""

    # Given  a store holding a stale session AND this leg's session
    _store(tmp_path / "profiles" / "llgenie-planner" / "state.db",
           [("stale-leg", LAST_RESORT, 1000.0), ("this-leg", PRIMARY, 2000.0)])

    # When   the report runs with the window opened at 1900
    proc = _run(tmp_path, "llgenie-planner", since=1900.0)

    # Then   only this leg's model is named
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout == f"model-route: {PRIMARY}\n", proc.stdout


def test_a_window_after_every_session_fails_loudly_invents_nothing(tmp_path):
    """No session started inside the window: a named failure, a non-zero code, no line."""

    # Given  the same store, and a window opened after both sessions
    _store(tmp_path / "profiles" / "llgenie-planner" / "state.db",
           [("stale-leg", LAST_RESORT, 1000.0)])

    # When   the report runs with --since past every session (beyond the launch tolerance)
    proc = _run(tmp_path, "llgenie-planner", since=3000.0)

    # Then   exit 3, nothing on stdout, and the failure names the store and the window
    assert proc.returncode == 3, proc.stdout + proc.stderr
    assert "model-route:" not in proc.stdout
    assert "no session started at or after 3000" in proc.stderr, proc.stderr


def test_launch_tolerance_absorbs_the_heartbeat_between_start_and_session(tmp_path):
    """Hermes stamps started_at a heartbeat after the recipe captured --since; a few seconds
    of latency must not orphan the leg's own session, and must not reach back a full leg."""

    # Given  a session started at 2000.0
    _store(tmp_path / "profiles" / "llgenie-planner" / "state.db", [("this-leg", PRIMARY, 2000.0)])

    # When   since is a heartbeat past the session start, and  again a full window past it
    near = _run(tmp_path, "llgenie-planner", since=2004.0)
    far = _run(tmp_path, "llgenie-planner", since=2010.0)

    # Then   the heartbeat still attributes the session, and 10s past it does not
    assert near.returncode == 0 and near.stdout == f"model-route: {PRIMARY}\n", near.stdout
    assert far.returncode == 3, far.stdout + far.stderr


def test_a_missing_store_is_a_named_failure_not_a_fabricated_route(tmp_path):
    """Nothing on stdout when nothing can be read; the failure names the store path it tried."""

    # Given  no store anywhere under the home
    proc = _run(tmp_path, "llgenie-planner")

    # Then   exit 2, no line, and the tried path is named (no profile home → the global store
    #        is the fallback, exactly like the smoke's state_db rule)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "model-route:" not in proc.stdout
    assert "absent or unreadable" in proc.stderr, proc.stderr
    assert str(tmp_path / "state.db") in proc.stderr, proc.stderr


def test_an_unreadable_store_is_named_not_invented(tmp_path):
    """A file in the store's place that sqlite cannot open is a store failure, not an empty pass."""

    # Given  a non-database blob where the store should be
    garbage = tmp_path / "state.db"
    garbage.write_bytes(b"not a database at all")

    # When   the report runs for a default-home lane
    proc = _run(tmp_path, "llgenie-no-such-lane")

    # Then   exit 2 with the store named, and no line printed
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "model-route:" not in proc.stdout
    assert "absent or unreadable" in proc.stderr, proc.stderr


def test_a_session_without_a_model_value_fails_loudly(tmp_path):
    """The session exists but Hermes recorded no model for it: unevidenced is unevidenced."""

    # Given  a leg-window session whose model column is NULL
    _store(tmp_path / "profiles" / "llgenie-planner" / "state.db", [("this-leg", None, 2000.0)])

    # When   the report runs inside the window
    proc = _run(tmp_path, "llgenie-planner", since=1900.0)

    # Then   exit 4, no line, and the failure names the session and the reason
    assert proc.returncode == 4, proc.stdout + proc.stderr
    assert "model-route:" not in proc.stdout
    assert "this-leg" in proc.stderr and "carries no model value" in proc.stderr, proc.stderr


def test_the_line_carries_only_the_model_id(tmp_path):
    """The line is the model value and nothing else: config columns are never read or printed."""

    # Given  a session whose config column carries a key-env NAME (env names are never secrets,
    #        and this proves the script reads the model column only)
    path = tmp_path / "profiles" / "llgenie-planner" / "state.db"
    _store(path, [("this-leg", PRIMARY, 2000.0)])
    conn = sqlite3.connect(path)
    conn.execute("UPDATE sessions SET model_config = ?", ('{"key_env": "SOME_LANE_KEY_ENV"}',))
    conn.commit()
    conn.close()

    # When   the report runs
    proc = _run(tmp_path, "llgenie-planner", since=1900.0)

    # Then   stdout is the one line naming the model, and no config text reaches anywhere
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout == f"model-route: {PRIMARY}\n", proc.stdout
    assert "SOME_LANE_KEY_ENV" not in proc.stdout + proc.stderr
    assert "key_env" not in proc.stdout + proc.stderr


def test_the_report_never_changes_the_legs_exit_status(tmp_path):
    """A leg fails exactly when hermes failed: the report runs in between, and its own failure
    code (or its own success) never overwrites the leg's status."""

    # Given  the shell shape every wired recipe uses (hermes first, rc kept, exit rc last)
    def leg(hermes: str) -> int:
        return subprocess.run(
            ["bash", "-lc",
             f"leg_start=$(date +%s); {hermes}; rc=$?; "
             f"python3 {SCRIPT} --lane no-such-lane-home --since 999999999; exit $rc"],
            env={"HERMES_HOME": "/nonexistent-hermes-home", "PATH": os.environ.get("PATH", "")},
            capture_output=True, text=True, timeout=30,
        ).returncode

    # Then   a failed leg stays failed (1, not the report's 2/3), and a green leg stays green
    assert leg("false") == 1
    assert leg("true") == 0


def test_every_hermes_leg_recipe_reports_its_serving_model():
    """All nine Hermes bot recipes are wired: window captured at leg start, the report after
    hermes with the SAME lane as the -p flag, and `exit $$rc` preserving the leg's status."""

    # Given  every recipe line that invokes hermes directly
    lines: list[str] = []
    for name in ("mk/bots.mk", "mk/agents.mk", "mk/engines.mk"):
        lines += [l for l in (ROOT / name).read_text().splitlines() if "hermes -z" in l]

    # Then   each of the nine call sites carries the full report pattern, same lane as -p
    assert len(lines) == 9, lines
    for line in lines:
        lane = re.search(r"-p (llgenie-[a-z-]+)", line)
        assert lane, line
        assert "leg_start=$$(date +%s)" in line, line
        assert f"python3 scripts/hermes_model_route.py --lane {lane.group(1)} --since $$leg_start" in line, line
        assert "exit $$rc" in line, line
