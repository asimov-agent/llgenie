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
import scripts.apply_hermes_base_config as chain  # the same seam the install uses (issue #2929)

REPO = Path(__file__).resolve().parent.parent


def _tree(tmp_path: Path, declared: list[str], installed: list[str],
          *, with_base: bool = True, with_chain: bool = True) -> tuple[Path, Path]:
    """agents/ tree declaring `declared` (each with a SOUL.md, the manifest is the truth, and the
    chain home `hermes-base-config.yaml` the gate also proves) and a profiles/ dir that holds
    exactly `installed` (each with a SOUL.md AND the chain landed through the real seam, so the
    fixture mirrors a properly installed image)."""
    agents, profiles = tmp_path / "agents", tmp_path / "profiles"
    agents.mkdir()
    (agents / "manifest.json").write_text(
        json.dumps({"profiles": [{"name": name} for name in declared]}))
    for name in declared:
        (agents / name).mkdir(parents=True)
        (agents / name / "SOUL.md").write_text(f"# {name}\n")
    if with_base:
        (agents / chain.BASE_CONFIG.split("/")[-1]).write_text(
            (REPO / chain.BASE_CONFIG).read_text(encoding="utf-8"))
    for name in installed:
        (profiles / name).mkdir(parents=True)
        (profiles / name / "SOUL.md").write_text(f"# {name}\n")
        if with_chain:
            chain.apply(profiles / name, chain.load_base(tmp_path))
    return agents, profiles


def test_an_installed_lane_without_the_chain_reds_the_build(tmp_path, capsys):
    """A lane installed without the model chain would run a model the repo no longer declares:
    the gate names the lane and the missing chain keys (issue #2929)."""
    agents, profiles = _tree(tmp_path, ["llgenie-planner", "llgenie-security"],
                             ["llgenie-planner", "llgenie-security"], with_chain=False)
    findings = lanes.findings(agents, profiles)
    assert findings, findings
    assert any("llgenie-planner" in f and "model.default" in f for f in findings), findings
    assert any("llgenie-security" in f and "model.default" in f for f in findings), findings


def test_a_tree_without_the_chain_home_reds_the_build(tmp_path):
    """If the ONE home for the chain is gone from the agents tree, no lane can be proven."""
    agents, profiles = _tree(tmp_path, ["llgenie-planner"], ["llgenie-planner"],
                             with_base=False, with_chain=False)
    findings = lanes.findings(agents, profiles)
    assert any("no home" in f for f in findings), findings


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


# ---- the skill-book half of the gate (issue #2669) --------------------------------------------

def _with_skills(agents: Path, name: str, *skill_paths: str) -> None:
    """Give a tree lane skills: a SKILL.md under each relative path (agents/<name>/skills/… )."""
    for rel in skill_paths:
        p = agents / name / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# {rel} rulebook for {name}\n")


def test_installed_soul_without_the_tree_skills_reds_the_build(tmp_path, capsys):
    """Issue #2669's exact failure: the old `cp -r` loop could land a lane's SOUL.md while its
    skills subtree silently missed. A tree lane carrying SKILL.md files and an installed home
    without them must RED the build, naming the lane and 'skillbooks'."""
    agents, profiles = _tree(tmp_path, ["llgenie-planner"], ["llgenie-planner"])
    _with_skills(agents, "llgenie-planner", "skills/llgenie-bot-orchestration/SKILL.md")
    findings = lanes.findings(agents, profiles)
    assert len(findings) == 1 and "llgenie-planner" in findings[0]
    assert "skillbooks" in findings[0]
    rc = lanes.run_cli(["--agents", str(agents), "--profiles", str(profiles)])
    err = capsys.readouterr().err
    assert rc == 1 and "llgenie-bot-orchestration" in err


def test_installed_skill_that_diverges_from_the_tree_reds(tmp_path, capsys):
    """Byte-identity is the contract: an installed SKILL.md whose bytes differ from the tree's is
    a finding naming the relative path — the image must not run a stale skill."""
    agents, profiles = _tree(tmp_path, ["llgenie-planner"], ["llgenie-planner"])
    _with_skills(agents, "llgenie-planner", "skills/bot-skill/SKILL.md")
    installed = profiles / "llgenie-planner" / "skills" / "bot-skill" / "SKILL.md"
    installed.parent.mkdir(parents=True)
    installed.write_text("# an OLD copy the image kept from a previous build\n")
    findings = lanes.findings(agents, profiles)
    assert findings and "skills/bot-skill/SKILL.md" in findings[0] and "differs" in findings[0]
    assert lanes.run_cli(["--agents", str(agents), "--profiles", str(profiles)]) == 1


def test_tree_skills_installed_byte_identical_green(tmp_path):
    """The positive control: every tree SKILL.md present and identical in the home greens the gate."""
    agents, profiles = _tree(tmp_path, ["llgenie-planner"], ["llgenie-planner"])
    _with_skills(agents, "llgenie-planner", "skills/a-skill/SKILL.md",
                 "skills/b-skill/SKILL.md")
    for rel in ("skills/a-skill/SKILL.md", "skills/b-skill/SKILL.md"):
        target = profiles / "llgenie-planner" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((agents / "llgenie-planner" / rel).read_bytes())
    assert lanes.findings(agents, profiles) == []
    assert lanes.run_cli(["--agents", str(agents), "--profiles", str(profiles)]) == 0


def test_lane_without_tree_skills_stays_green(tmp_path):
    """A lane the tree gives no skills is not a skill finding: the gate proves what the tree
    carries, it does not invent a requirement the fleet never declared."""
    agents, profiles = _tree(tmp_path, ["llgenie-security"], ["llgenie-security"])
    assert lanes.findings(agents, profiles) == []


def test_real_tree_provisioned_by_the_seam_passes_the_skill_gate(tmp_path):
    """Cross-seam proof on the REAL tree: provision_agent_profiles.py writes every declared lane
    into a fresh home, and the extended agent_lanes_check gate — which now compares every tree
    SKILL.md byte-for-byte — passes it. A lane whose skills the installer failed to copy would
    red THIS assertion, which is the #2669 build behaviour, proven without a container build."""
    import shutil
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    r = subprocess.run(
        [sys.executable, str(root / "scripts" / "provision_agent_profiles.py"),
         "--root", str(root), "--dest", str(tmp_path)],
        capture_output=True, text=True, timeout=300,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    items = lanes.findings(root / "agents", tmp_path)
    assert items == [], items
    shutil.rmtree(tmp_path, ignore_errors=True)
