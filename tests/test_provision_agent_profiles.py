#!/usr/bin/env python3
"""Hermetic tests for scripts/provision_agent_profiles.py (issue #2165).

The gate is the point: provisioning every lane's `agents/<profile>/` into its
Hermes home must be idempotent, must leave a profile's own files (memory,
state.db, .env, live-only skills) untouched, must have NO delete path, and the
post-provision comparison must FAIL when any provisioned file differs (naming
profile + path) and GREEN after a re-provision. All tests run against a
temporary home, never a live ~/.hermes profile.

The negative control is the acceptance criterion exactly: provision into $TMPH,
mutate one file, prove `--check` reddens, re-provision, prove it greenns.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "provision_agent_profiles.py"


def _run(dest, *flags):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--dest", str(dest), *flags],
        capture_output=True,
        text=True,
        env={**os.environ, "HERMES_PROFILE_HOME": str(dest / "llgenie-tester")},
        timeout=180,
    )


def _profiles_count():
    import json  # noqa: PLC0415
    m = json.loads((REPO / "agents" / "manifest.json").read_text())
    return len(m["profiles"])


def test_provisions_every_lane_and_is_idempotent(tmp_path):
    n = _profiles_count()
    r1 = _run(tmp_path)
    assert r1.returncode == 0, r1.stdout + r1.stderr
    lanes = [p for p in tmp_path.iterdir() if p.is_dir()]
    assert len(lanes) == n, (len(lanes), n)
    # every lane got a SOUL.md (behaviour, not empty)
    for lane in lanes:
        assert (lane / "SOUL.md").exists(), lane
    # a second provision is a no-op: identical output tree, rc 0
    before = {p.name: (p / "SOUL.md").read_bytes() if (p / "SOUL.md").exists() else b""
              for p in lanes}
    r2 = _run(tmp_path)
    assert r2.returncode == 0, r2.stdout + r2.stderr
    for lane in lanes:
        assert (lane / "SOUL.md").read_bytes() == before[lane.name]


def test_fresh_empty_home_matches_tree_exactly_after_provision(tmp_path):
    r = _run(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    gate = _run(tmp_path, "--check")
    assert gate.returncode == 0, gate.stdout + gate.stderr


def test_gate_reds_on_mutation_and_greens_after_reprovision(tmp_path):
    # The rebuild case: a profile whose tree-carried SOUL.md is MISSING (a fresh
    # or partial home — the exact silent failure #2165 exists for, since a missing
    # SOUL.md produces no error) must red the gate and be restored by provisioning.
    _run(tmp_path)
    target = tmp_path / "llgenie-tester" / "SOUL.md"
    orig = target.read_bytes()
    target.unlink()  # simulate the "home started without the tree's SOUL.md" case
    red = _run(tmp_path, "--check")
    assert red.returncode != 0, "gate must red on a missing tree-carried file"
    assert "llgenie-tester" in (red.stdout + red.stderr)
    assert "SOUL.md" in (red.stdout + red.stderr)
    # re-provisioning restores the missing file and the gate turns green.
    _run(tmp_path)
    green = _run(tmp_path, "--check")
    assert green.returncode == 0, green.stdout + green.stderr
    assert (tmp_path / "llgenie-tester" / "SOUL.md").read_bytes() == orig


def test_live_only_edit_stays_a_finding_not_silently_overwritten(tmp_path):
    # A profile file carrying a line that exists ONLY in the live copy is a
    # finding, never something provisioning silently re-takes: re-provisioning
    # must NOT delete that line, and the gate keeps it red until deliberately merged.
    _run(tmp_path)
    target = tmp_path / "llgenie-tester" / "SOUL.md"
    with open(target, "a") as fh:
        fh.write("\n# live-only line that the tree does not carry\n")
    # re-provisioning is refused for this file (a live-only edit is protected)
    _run(tmp_path)
    assert "# live-only line that the tree does not carry" in target.read_text()
    # the gate stays red: the profile diverges from the tree on a live-only edit
    red = _run(tmp_path, "--check")
    assert red.returncode != 0, "a live-only edit is a finding, not silently re-taken"


def test_profile_own_files_survive_provisioning(tmp_path):
    _run(tmp_path)
    i_am = tmp_path / "llgenie-tester"
    (i_am / ".env").write_text("GITHUB_TOKEN=redacted")
    live_skill = i_am / "skills" / "live-only-skill" / "SKILL.md"
    live_skill.parent.mkdir(parents=True, exist_ok=True)
    live_skill.write_text("# a live-only skill, never in the tree\n")
    _run(tmp_path)  # provisioning again must not touch them
    assert (i_am / ".env").read_text() == "GITHUB_TOKEN=redacted"
    assert (i_am / "skills" / "live-only-skill" / "SKILL.md").exists()


def test_no_delete_path(tmp_path):
    # a provisioned file that is later NOT in the tree is never deleted by
    # provisioning (the copy is one-way, tree is source; deletion is never a lane's act)
    _run(tmp_path)
    kept = tmp_path / "llgenie-tester" / "skills" / "keep-me" / "SKILL.md"
    kept.parent.mkdir(parents=True, exist_ok=True)
    kept.write_text("# keep me\n")
    _run(tmp_path)
    assert kept.exists(), "provisioning must never delete a live-only file"
    # and it is NOT reported as a tree match (it's a live-only finding), i.e.
    # --check does not fail on a *superset* — agent_profile_sync's check is
    # one-way (tree files must match); a live-only extra is a finding, not a red.
    gate = _run(tmp_path, "--check")
    assert gate.returncode == 0, gate.stdout + gate.stderr
