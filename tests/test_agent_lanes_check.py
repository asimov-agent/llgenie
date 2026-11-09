#!/usr/bin/env python3
"""The Hermes agent image must carry every lane the fleet declares (issue #2181).

``containers/agent/Dockerfile`` is the container every bot lane runs in, but before #2181 it
carried ZERO references to ``agents/`` or to profiles — the Hermes CLI installed, no lane, so a
job asking for a named profile resolved against an empty profile home. ``scripts/agent_lanes_check.py``
is the build-time half of the fix: the Dockerfile installs each lane that ``agents/manifest.json``
declares into ``$HERMES_HOME/profiles/<name>/``, then this gate re-reads that same manifest against
the installed profiles and REFUSES a build whose image is missing a declared lane.

These tests drive the REAL script (never a copy of its logic) against fixture trees, proving the
two things the issue names: that a missing lane reds the build naming it, and that a complete
install passes. ``run_cli`` exit codes: 0 all declared lanes present, 1 a lane or the manifest is
missing, 2 the agents dir is not even a directory — never a silent pass.
"""
from __future__ import annotations

import json
from pathlib import Path

import scripts.agent_lanes_check as lanes  # noqa: E402  (the real gate, never a copy)


def _tree(tmp_path: Path, declared: list[str], installed: list[str]) -> tuple[Path, Path]:
    """agents/ tree declaring `declared` (each with a SOUL.md, the manifest is the truth) and a
    profiles/ dir that holds exactly `installed` (each with a SOUL.md)."""
    agents, profiles = tmp_path / "agents", tmp_path / "profiles"
    agents.mkdir()
    (agents / "manifest.json").write_text(
        json.dumps({"profiles": [{"name": name} for name in declared]}))
    for name in declared:
        (agents / name).mkdir(parents=True)
        (agents / name / "SOUL.md").write_text(f"# {name}\n")
    for name in installed:
        (profiles / name).mkdir(parents=True)
        (profiles / name / "SOUL.md").write_text(f"# {name}\n")
    return agents, profiles


def test_every_declared_lane_installed_greens(tmp_path, capsys):
    """A complete install — every manifest lane present with a SOUL.md — passes the build."""
    agents, profiles = _tree(tmp_path, ["llgenie-planner", "llgenie-security"],
                             ["llgenie-planner", "llgenie-security"])
    assert lanes.findings(agents, profiles) == []
    rc = lanes.run_cli(["--agents", str(agents), "--profiles", str(profiles)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "OK" in out and "2 lane(s)" in out


def test_a_declared_lane_missing_from_the_image_reds_the_build(tmp_path, capsys):
    """The failure mode the issue names: a manifest lane whose home is absent must fail the build,
    naming the missing lane — it is not a warning, not a skip."""
    agents, profiles = _tree(tmp_path, ["llgenie-planner", "llgenie-security"],
                             ["llgenie-security"])  # llgenie-planner never installed
    findings = lanes.findings(agents, profiles)
    assert len(findings) == 1 and "llgenie-planner" in findings[0]
    out = capsys.readouterr()  # drain findings' own noise; run_cli below re-prints
    rc = lanes.run_cli(["--agents", str(agents), "--profiles", str(profiles)])
    err = capsys.readouterr().err
    assert rc == 1
    assert "FAIL" in err and "llgenie-planner" in err
    assert "no rulebook" in err
    _ = out


def test_two_missing_lanes_are_both_named(tmp_path, capsys):
    """Every missing lane is named, not just the first: the fix must not silently prefer some."""
    agents, profiles = _tree(tmp_path, ["llgenie-planner", "llgenie-security"],
                             [])
    rc = lanes.run_cli(["--agents", str(agents), "--profiles", str(profiles)])
    err = capsys.readouterr().err
    assert rc == 1
    assert "llgenie-planner" in err and "llgenie-security" in err


def test_a_missing_manifest_reds_loudly(tmp_path, capsys):
    """No manifest means no declared lane set: the build must fail rather than assume the empty."""
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "llgenie-planner").mkdir()
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    rc = lanes.run_cli(["--agents", str(agents), "--profiles", str(profiles)])
    assert rc == 1
    assert "manifest.json is missing" in capsys.readouterr().err


def test_agents_dir_that_is_not_a_directory_aborts(tmp_path, capsys):
    """A bad invocation is an error (exit 2), never a silent pass over nothing."""
    rc = lanes.run_cli(["--agents", str(tmp_path / "nope"), "--profiles", str(tmp_path)])
    assert rc == 2
    assert "not a directory" in capsys.readouterr().err


def test_the_committed_agents_tree_carries_every_manifest_lane():
    """The gate's real input in the repo must hold in the tree what the build installs: every
    lane agents/manifest.json declares has a SOUL.md in agents/. Without this, the manifest and
    the installed set drift apart and the image builds a fleet different from the one declared."""
    import shutil
    import tempfile

    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "agents" / "manifest.json").read_text())
    declared = [p["name"] for p in manifest["profiles"]]
    tmp = Path(tempfile.mkdtemp(prefix="agents-tree-check-"))
    try:
        missing = [n for n in declared if not (root / "agents" / n / "SOUL.md").is_file()]
        assert not missing, f"manifest declares lanes missing a SOUL.md in the tree: {missing}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
