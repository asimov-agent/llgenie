"""Pins for the shared fake-gh field guard (issue #2975).

The #513 class: a leg asks `gh pr view --json …authorAssociation…`, real gh
refuses the whole call (`Unknown JSON field`, exit 1), and the unit suite
never saw it because no fake gh looked at the requested names. These pins
make the harness itself refuse that shape.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# `tests/` is a pytest rootdir: prepend mode puts this file's directory on
# sys.path, so the seam imports bare — no new import root (issue #1101).
import gh_fake  # noqa: E402

TESTS_DIR = Path(__file__).resolve().parent


def _captured() -> dict[str, list[str]]:
    return json.loads((TESTS_DIR / "fixtures" / "gh-json-fields.json").read_text())["commands"]


def test_the_513_field_shape_is_refused_with_gh_own_error_and_exit_1(capsys):
    with pytest.raises(SystemExit) as boom:
        gh_fake.enforce(
            ["pr", "view", "7", "--repo", "asimov-agent/llgenie", "--json", "authorAssociation"]
        )
    assert boom.value.code == 1
    err = capsys.readouterr().err
    assert 'Unknown JSON field: "authorAssociation"' in err


def test_a_valid_field_list_passes_through_the_guard():
    assert (
        gh_fake.enforce(
            ["pr", "view", "7", "--repo", "asimov-agent/llgenie",
             "--json", "title,state,mergeStateStatus,headRefOid"]
        )
        == 0
    )


def test_the_guard_validates_against_the_captured_fixture_identity():
    captured = _captured()
    allow = gh_fake.load_allowlists()
    assert set(allow) == set(captured)
    for cmd, fields in captured.items():
        assert allow[cmd] == sorted(fields)
    # the #513 name is on NO captured list anywhere: refusing it is the whole point
    assert all("authorAssociation" not in fields for fields in captured.values())


def test_a_guarded_subcommand_with_an_uncovered_pair_fails_closed(capsys):
    with pytest.raises(SystemExit) as boom:
        gh_fake.enforce(["pr", "status", "7", "--json", "author"])
    assert boom.value.code == 1
    assert "no captured field list" in capsys.readouterr().err


def test_a_gh_command_outside_the_guarded_roster_answers_fine(capsys):
    # `gh search prs --json number` is a real gh shape (rebase_bot_sweep asks
    # it); the guard's roster is pr|issue|run, exactly like the scanner's.
    assert gh_fake.enforce(["search", "prs", "--repo", "asimov-agent/llgenie",
                            "--json", "number", "--limit", "50"]) == 0
    assert gh_fake.enforce(["api", "repos/asimov-agent/llgenie/pulls/7", "--jq", ".merged"]) == 0


def test_a_request_without_json_is_not_gated():
    assert gh_fake.enforce(["issue", "comment", "7", "--body", "hi"]) == 0
    assert gh_fake.enforce(["pr", "merge", "7", "--delete-branch"]) == 0


def test_a_field_list_joined_with_equals_signs_is_still_checked(capsys):
    with pytest.raises(SystemExit) as boom:
        gh_fake.enforce(["issue", "list", "--json=authorAssociation,title"])
    assert boom.value.code == 1
    assert 'Unknown JSON field: "authorAssociation"' in capsys.readouterr().err


def test_a_path_ending_in_gh_attributes_the_leg_call_after_it():
    argv = ["/tmp/fixture/bin/gh", "run", "list", "--json", "status"]
    assert gh_fake.attribute(argv) == "run list"
    assert gh_fake.enforce(argv) == 0


def test_a_heredoc_fake_installs_the_guard_through_the_preamble(tmp_path):
    script = tmp_path / "gh"
    script.write_text(
        "#!/usr/bin/env python3\n"
        + gh_fake.preamble(TESTS_DIR)
        + "\nimport json, sys\n"
        + "print(json.dumps({'title': 'ok'}))\n"
    )
    script.chmod(0o755)
    good = subprocess.run(
        [str(script), "pr", "view", "7", "--json", "title"], capture_output=True, text=True
    )
    assert good.returncode == 0
    assert json.loads(good.stdout) == {"title": "ok"}
    bad = subprocess.run(
        [str(script), "pr", "view", "7", "--json", "authorAssociation"],
        capture_output=True,
        text=True,
    )
    assert bad.returncode == 1
    assert 'Unknown JSON field: "authorAssociation"' in bad.stderr
