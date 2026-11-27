"""Issue #3106: the fleet roster gate is a subset of the documented profiles."""
from __future__ import annotations

import json

import pytest

from scripts.check_fleet_roster import check, section_text


def _doc(tmp_path, names, section="Host lane fleet", extra=()):
    lines = ["# Fixture", "", f"## {section}", ""]
    lines += [f"| `{n}` | role |" for n in list(names) + list(extra)]
    path = tmp_path / "architecture.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _manifest(tmp_path, names):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"profiles": [{"name": n} for n in names]}), encoding="utf-8")
    return path


def test_all_manifest_profiles_documented_passes(tmp_path, capsys):
    names = ["llgenie-planner", "llgenie-tester"]
    rc = check(_manifest(tmp_path, names), _doc(tmp_path, names))
    assert rc == 0
    assert "OK" in capsys.readouterr().out


def test_missing_profile_is_named(tmp_path, capsys):
    names = ["llgenie-planner", "llgenie-tester"]
    rc = check(_manifest(tmp_path, names), _doc(tmp_path, ["llgenie-planner"]))
    out = capsys.readouterr().out
    assert rc == 1
    assert "llgenie-tester" in out


def test_extra_documented_lane_is_allowed(tmp_path, capsys):
    names = ["llgenie-planner", "llgenie-tester"]
    rc = check(_manifest(tmp_path, names), _doc(tmp_path, names, extra=["a-future-lane"]))
    assert rc == 0
    assert "OK" in capsys.readouterr().out


def test_missing_subsection_is_a_finding(tmp_path, capsys):
    names = ["llgenie-planner"]
    rc = check(_manifest(tmp_path, names), _doc(tmp_path, names, section="Some other heading"))
    assert rc == 1
    assert "no `## Host lane fleet`" in capsys.readouterr().out


@pytest.mark.parametrize("heading", ["## Host lane fleet", "## host lane fleet  "])
def test_section_heading_is_case_insensitive(heading):
    assert "llgenie-planner" in section_text(f"{heading}\n\n`llgenie-planner`\n\n## Next\n")
