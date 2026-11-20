"""The gh --json field-name guard (issue #515, the generalised #513 class).

#513 was one hand-pinned field name (`authorAssociation` on `gh pr view`) in one
script. This guard is structural: every `--json` call site in `scripts/*.py` and
the real lane shell (`gh <cmd> --json …`) resolves against the per-subcommand
allowlists captured from the real CLI (`tests/fixtures/gh-json-fields.json`).
The gate fails CLOSED: a `--json` whose subcommand is unknown or whose fields
are not statically resolvable is a finding, not a skip.

Only synthetic trees are built; no gate logic and no gh call is mocked.
"""
from __future__ import annotations

import json
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
from scripts import check_gh_json_fields as guard  # noqa: E402

FIXTURE = REPO / "tests" / "fixtures" / "gh-json-fields.json"


def _synth_tree(tmp_path: pathlib.Path, py: str = "", yml: str = "") -> pathlib.Path:
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
    if py:
        (tmp_path / "scripts" / "bot.py").write_text(py)
    if yml:
        (tmp_path / ".github" / "workflows" / "lane.yml").write_text(yml)
    return tmp_path


def test_the_invalid_author_association_shape_is_red(tmp_path):
    # Given the exact #513 call site re-synthesized
    tree = _synth_tree(
        tmp_path,
        'cmd = ["gh", "pr", "view", "2319", "--repo", "r", "--json",\n'
        '    "number,headRefOid,authorAssociation"]\n',
    )
    findings, coverage = guard.run(tree, FIXTURE)
    # Then it reports the invalid field with file and line, and the call site is counted
    assert coverage["sites"] == 1
    assert len(findings) == 1
    assert findings[0]["kind"] == "unknown-field"
    assert "authorAssociation" in findings[0]["detail"]
    assert findings[0]["file"] == "scripts/bot.py"
    assert findings[0]["line"] == 1


def test_a_field_built_from_a_constant_list_is_red(tmp_path):
    # Given fields assembled via ",".join(<constant list>) (auto_merge's shape)
    tree = _synth_tree(
        tmp_path,
        'FIELDS = ["number", "bogusOid"]\n'
        'cmd = ["gh", "issue", "view", "1", "--json", ",".join(FIELDS)]\n',
    )
    findings, coverage = guard.run(tree, FIXTURE)
    assert coverage["sites"] == 1
    assert [f["kind"] for f in findings] == ["unknown-field"]
    assert "bogusOid" in findings[0]["detail"]


def test_a_json_call_that_cannot_be_attributed_to_a_known_subcommand_is_red(tmp_path):
    # Given a gh argv list whose subcommand pair is not on the measured roster
    tree = _synth_tree(
        tmp_path,
        'cmd = ["gh", "bogus", "thing", "--json", "body"]\n',
    )
    findings, coverage = guard.run(tree, FIXTURE)
    assert coverage["sites"] == 1  # counted, not skipped
    assert [f["kind"] for f in findings] == ["unattributable-subcommand"]


def test_unresolvable_fields_are_red_not_skipped(tmp_path):
    # Given a --json whose value comes from a runtime expression
    tree = _synth_tree(
        tmp_path,
        'cmd = ["gh", "pr", "view", "1", "--json", build_fields()]\n',
    )
    findings, coverage = guard.run(tree, FIXTURE)
    assert [f["kind"] for f in findings] == ["unresolvable-fields"]


def test_shell_lane_json_fields_are_scanned(tmp_path):
    # Given a real-lane shell invocation with an invalid field and one with a runtime var
    tree = _synth_tree(
        tmp_path,
        py="x = 1\n",
        yml=(
            "jobs:\n  s:\n    steps:\n      - run: |\n"
            '          gh pr view "$N" --repo R --json headRefOid,bogusField -q .x\n'
            '      - run: gh pr view "$N" --json "$FIELDS"\n'
        ),
    )
    findings, _coverage = guard.run(tree, FIXTURE)
    kinds = [f["kind"] for f in findings]
    assert kinds == ["unknown-field", "unresolvable-fields"]
    assert findings[0]["file"] == ".github/workflows/lane.yml"


def test_gh_issue_create_json_is_a_finding_because_the_verb_has_no_json(tmp_path):
    # Given a shell `gh issue create … --json number` (the shape the guard found live
    # in registry-liveness.yml: the real CLI rejects the flag outright, exit 1)
    tree = _synth_tree(
        tmp_path,
        py="x = 1\n",
        yml=(
            "jobs:\n  s:\n    steps:\n      - run: |\n"
            '          gh issue create --repo R --title t --body b --json number --jq .number\n'
        ),
    )
    findings, _coverage = guard.run(tree, FIXTURE)
    assert [f["kind"] for f in findings] == ["unattributable-subcommand"]


def test_a_repo_owned_argument_like_a_cli_flag_is_scanned(tmp_path):
    # Given an OWNED script invoked with `--json` (issue #515's boundary: only real gh
    # invocations are against the allowlist) — a false-positive control
    tree = _synth_tree(
        tmp_path,
        py=(
            "import argparse\n"
            'p = argparse.ArgumentParser()\n'
            'p.add_argument("--json", action="store_true")\n'
        ),
    )
    findings, coverage = guard.run(tree, FIXTURE)
    assert findings == []
    assert coverage["sites"] == 0


def test_the_committed_tree_is_green_and_covers_at_least_the_measured_surface():
    # Given the real scripts/ and workflow lanes at this head
    findings, coverage = guard.run(REPO, FIXTURE)
    # Then no call site violates an allowlist…
    assert findings == [], findings
    # …and the scan really read the whole surface the issue measured
    # (issue #515: "19 scripts pass --json … 46+ call sites"; the roster has grown since)
    assert coverage["scripts"] >= 19
    assert coverage["sites"] >= 46


def test_the_fixture_covers_every_subcommand_the_scan_attributes():
    fixture = json.loads(FIXTURE.read_text())
    commands = fixture["commands"]
    assert set(commands) == {"pr view", "pr list", "pr checks", "issue view",
                             "issue list", "run view", "run list"}
    for sub, fields in commands.items():
        assert fields and all(f.strip() == f and f for f in fields), sub


def test_the_pinned_pr_view_fields_are_a_subset_of_the_captured_allowlist():
    # The #514 allowlist must stay consistent with the freshly captured superset
    fixture = json.loads(FIXTURE.read_text())
    from scripts.auto_merge import PR_VIEW_FIELDS
    assert set(PR_VIEW_FIELDS) <= set(fixture["commands"]["pr view"])


def test_cli_main_returns_1_when_a_finding_exists(tmp_path, capsys):
    tree = _synth_tree(
        tmp_path,
        'cmd = ["gh", "run", "list", "--json", "nope"]\n',
    )
    rc = guard.main(["check", "--root", str(tree), "--fixture", str(FIXTURE)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "finding(s)" in out and "nope" in out
