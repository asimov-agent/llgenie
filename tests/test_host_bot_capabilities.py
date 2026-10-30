#!/usr/bin/env python3
"""The host llgenie bots pin toolsets and skills from one fixture (issue #1038).

The guard is ``scripts/host_bot_capabilities.py``. These tests drive that module
against a fake profile tree. They do not read ``~/.hermes``.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import host_bot_capabilities as pin  # noqa: E402  (scripts/host_bot_capabilities.py)


def _skill(directory: Path, name: str, title: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: fixture\n---\n\n# {title}\n\nBody.\n",
        encoding="utf-8",
    )


def _profile(root: Path, name: str, *, with_browser: bool) -> None:
    profile = root / name
    profile.mkdir(parents=True)
    config = {
        "model": {"default": "deepseek/deepseek-v4-flash-0731"},
        "skills": {"external_dirs": []},
        "command_allowlist": [pin.load_fixture()["force_push_entry"]],
        "kanban": {"orchestrator_profile": "pm"},
    }
    if with_browser:
        config["platform_toolsets"] = {"cli": ["browser", "computer_use", "terminal"]}
    (profile / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    (profile / "profile.yaml").write_text("description: old blurb\n", encoding="utf-8")
    skills = profile / "skills"
    _skill(skills / "apple" / "notes", "apple-notes", "Notes")
    _skill(skills / "software-development" / "github", "github", "GitHub")
    lane = pin.load_fixture()["profiles"][name]["lane_skill"]
    _skill(skills / "lane", lane, "Lane")


def test_reviewer_pin_drops_browser_and_force_push(tmp_path: Path):
    """A reviewer profile keeps its lane skill and loses browser and force-push."""

    # Given a reviewer profile cloned with browser, computer use, and a force-push approval
    spec = pin.load_fixture()
    home = tmp_path / "hermes"
    _profile(home / "profiles", "llgenie-pr-reviever", with_browser=True)
    raw = yaml.safe_load((home / "profiles" / "llgenie-pr-reviever" / "config.yaml").read_text())
    discovered = pin.discover_skills(home / "profiles" / "llgenie-pr-reviever" / "skills")

    # When the pin is applied
    updated = pin.apply_config(raw, spec, "llgenie-pr-reviever", discovered)

    # Then browser and computer_use are gone, force-push is gone, and apple-notes is disabled
    assert updated["platform_toolsets"]["cli"] == pin.toolsets_for(spec, "llgenie-pr-reviever")
    assert "browser" not in updated["platform_toolsets"]["cli"]
    assert "computer_use" not in updated["platform_toolsets"]["cli"]
    assert spec["force_push_entry"] not in updated["command_allowlist"]
    assert "apple-notes" in updated["skills"]["disabled"]
    assert "github" not in updated["skills"]["disabled"]
    assert "llgenie-pr-review" not in updated["skills"]["disabled"]
    assert updated["kanban"]["orchestrator_profile"] == "llgenie-planner"


def test_rebase_lane_keeps_the_force_push_entry():
    """The rebase lane is the one profile allowed to rewrite a branch."""

    # Given the fixture and a config that already has the force-push approval
    spec = pin.load_fixture()
    config = {"command_allowlist": [spec["force_push_entry"]], "skills": {}, "kanban": {}}

    # When the rebase profile is pinned
    updated = pin.apply_config(config, spec, "llgenie-pr-merge-conflict", [])

    # Then the approval stays, and a check of that result is clean
    assert spec["force_push_entry"] in updated["command_allowlist"]
    assert pin.check_config(updated, spec, "llgenie-pr-merge-conflict", []) == []


def test_check_flags_a_profile_that_still_has_browser():
    """check_config names a profile whose cli pin still contains browser."""

    # Given a reviewer config whose cli list is only browser
    spec = pin.load_fixture()
    config = {
        "platform_toolsets": {"cli": ["browser"]},
        "skills": {"disabled": []},
        "command_allowlist": [spec["force_push_entry"]],
        "kanban": {"orchestrator_profile": "pm"},
    }

    # When the config is checked against the fixture
    findings = pin.check_config(config, spec, "llgenie-pr-reviever", [{"name": "apple-notes", "rel": "a", "path": Path(".")}])

    # Then the toolset finding is reported
    assert any("platform_toolsets.cli" in item for item in findings)


def test_tools_block_is_idempotent_and_names_the_pin():
    """The lane skill carries the toolset list once."""

    # Given a skill body and the architect tool block
    spec = pin.load_fixture()
    body = "---\nname: llgenie-architecture-issue-pass\n---\n\n# Architecture\n\nMeasure.\n"
    block = pin.tools_block(spec, "llgenie-architect")

    # When the block is inserted twice
    once = pin.insert_tools_block(body, block)
    twice = pin.insert_tools_block(once, block)

    # Then it appears once and names web, which is this lane's extra toolset
    assert twice.count(pin.MARKER_BEGIN) == 1
    assert "`web`" in twice
    assert "issue #1038" in twice


def test_repo_host_skills_carry_the_marker():
    """The two HOST skills in this tree state the same pin the fixture enforces."""

    # Given the engine and architecture host skills after the change
    engine = (REPO / ".hermes" / "skills" / "llgenie-engine-improver" / "SKILL.md").read_text(encoding="utf-8")
    architect = (REPO / ".hermes" / "skills" / "llgenie-architecture-pass" / "SKILL.md").read_text(encoding="utf-8")

    # When the marker is read
    # Then each skill names its lane toolsets and the issue
    assert pin.MARKER_BEGIN in engine
    assert "`code_execution`" in engine
    assert pin.MARKER_BEGIN in architect
    assert "`web`" in architect
    assert "issue #1038" in engine
    assert "issue #1038" in architect


def test_fixture_covers_the_ten_live_profiles():
    """Every desktop llgenie profile is named, and only the rebase lane may force-push."""

    # Given the committed fixture
    spec = pin.load_fixture()

    # When the profile rows are read
    names = set(spec["profiles"])

    # Then the ten lanes are present and force-push is rebase-only
    assert names == {
        "llgenie-architect",
        "llgenie-ci-pipelines-maintainer",
        "llgenie-documentation-maintainer",
        "llgenie-engine-improver",
        "llgenie-issse-implementer",
        "llgenie-planner",
        "llgenie-pr-merge-conflict",
        "llgenie-pr-reviever",
        "llgenie-security",
        "llgenie-tester",
    }
    force = [name for name, row in spec["profiles"].items() if row["allow_force_push"]]
    assert force == ["llgenie-pr-merge-conflict"]
    for row in spec["profiles"].values():
        assert "browser" not in row["extra_toolsets"]
        assert "computer_use" not in row["extra_toolsets"]
