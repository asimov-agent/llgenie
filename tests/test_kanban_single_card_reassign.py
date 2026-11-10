#!/usr/bin/env python3
"""Host-only proof of #2353 AC3: a single-card `kanban reassign` leaves every
OTHER card's `assignee` byte-identical (the board-ownership invariant's write
side). The 2026-11-09 incident rewrote 114 cards' assignee in one event burst;
an orchestrator whose per-card write path is sound cannot do that by accident.
This test runs the REAL hermes CLI against a throwaway HERMES_KANBAN_DB: create
several cards across lanes, reassign exactly one, and assert every remaining
card's assignee is byte-for-byte unchanged.

HOST-ONLY: it needs the hermes CLI on PATH and mutates a temporary board its own
hermes instance owns. It is deliberately OUT of the hermetic gate (recorded in
tests/fixtures/unit-suite.json) and run on the tick host via
`make test-board-ownership-host` (tests/fixtures/host-only-wiring.json).
"""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

HERMES = os.environ.get("HERMES_BIN", "") or shutil.which("hermes")
# The repo pattern for the external seam: HERMES_BIN pins the binary; unset and
# no hermes on PATH means the test cannot honestly run the write path.
CAN_RUN = bool(HERMES) and os.path.exists(HERMES)


def _h(db):
    env = {**os.environ, "HERMES_KANBAN_DB": str(db), "HERMES_KANBAN_BOARD": "default"}
    # a delegated-child context forbids CLI mutation; the runner on the host is
    # not one, but strip the marker defensively so the test is honest about it
    env.pop("HERMES_DELEGATED_CHILD_CONTEXT", None)
    return env


def test_single_card_reassign_leaves_other_assignees_byte_identical(tmp_path):
    if not CAN_RUN:
        import pytest
        pytest.skip("hermes CLI not available; run on the tick host (test-board-ownership-host)")
    db = tmp_path / "kb.db"
    env = _h(db)
    lanes = ["llgenie-tester", "llgenie-security", "llgenie-engine-improver", "llgenie-tester"]
    ids = []
    for i, lane in enumerate(lanes):
        r = subprocess.run(
            [HERMES, "kanban", "create", f"proof card {i}", "--assignee", lane, "--json"],
            capture_output=True, text=True, env=env, timeout=120)
        assert r.returncode == 0, (i, r.stderr)
        ids.append(json.loads(r.stdout)["id"])
    before = subprocess.run([HERMES, "kanban", "list", "--json"],
                            capture_output=True, text=True, env=env, timeout=120)
    assert before.returncode == 0, before.stderr
    bm = {t["id"]: t["assignee"] for t in json.loads(before.stdout)}

    target = ids[1]  # reassign exactly one card
    r = subprocess.run([HERMES, "kanban", "reassign", target, "llgenie-planner"],
                       capture_output=True, text=True, env=env, timeout=120)
    assert r.returncode == 0, r.stderr

    after = subprocess.run([HERMES, "kanban", "list", "--json"],
                           capture_output=True, text=True, env=env, timeout=120)
    am = {t["id"]: t["assignee"] for t in json.loads(after.stdout)}

    # byte-identical: every OTHER card's assignee string is unchanged
    changed = [k for k in bm if bm.get(k) != am.get(k)]
    assert changed == [target], f"more than the target card changed: {changed}"
    assert am[target] == "llgenie-planner"
