"""The dispatch-form guard (issue #276): a workflow a human can start must state the work it does.

Every rule is tested on fixture workflows — a name that repeats the file stem, a bare
`workflow_dispatch:`, an input with no `description:`, an input with neither `default:` nor
`required: true`, a missing header key — and then the guard is run over THIS repository, because a
convention that the repo itself violates is not a convention.

The exit code matters as much as the rules: `make check-dispatch-forms` runs inside the `ci-unit` job,
so `main(["check"])` must return non-zero on a violation and 0 on a clean tree.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import check_dispatch_forms as cdf  # noqa: E402

HEADER = """# Trigger surface: schedule + workflow_dispatch.
# Flow: guard -> make something.
# Never: never merges, never pushes to main.
"""


def _tree(tmp_path: Path, workflows: dict[str, str]) -> Path:
    root = tmp_path / "repo"
    (root / cdf.WORKFLOWS).mkdir(parents=True, exist_ok=True)
    for name, body in workflows.items():
        (root / cdf.WORKFLOWS / name).write_text(body)
    return root


#: A valid, self-documenting dispatch form — the baseline every rule is tested AGAINST.
DISPATCH_OK = ("  workflow_dispatch:\n    inputs:\n      target:\n"
               "        description: \"the thing this run should act on\"\n        default: \"\"\n")


def _wf(name_line: str = "name: a-bot — does the work of a bot", dispatch: str | None = None,
        extra: str = "") -> str:
    """A workflow that passes the guard, so a test can break exactly one thing.

    `dispatch=None` means the valid form (`DISPATCH_OK`); a test that needs a broken or absent form
    passes its own text. Without a `workflow_dispatch` the guard skips the file entirely, so the
    baseline MUST include one or a violation test would pass for the wrong reason.
    """
    dispatch = DISPATCH_OK if dispatch is None else dispatch
    return (f"{name_line}\n\n{HEADER}{extra}\non:\n  schedule:\n"
            f"    - cron: \"23 6 * * *\"\n{dispatch}jobs:\n  a:\n    steps:\n      - run: make x\n")


# ---------------------------------------------------------------------------
# the name must state the work
# ---------------------------------------------------------------------------
def test_a_name_that_repeats_the_file_name_is_a_violation(tmp_path):
    root = _tree(tmp_path, {"a-bot.yml": _wf(name_line="name: a-bot")})
    bad = cdf.violations(root)
    assert any("repeats the file name" in b for b in bad), bad


def test_a_name_without_a_what_it_does_part_is_a_violation(tmp_path):
    root = _tree(tmp_path, {"a-bot.yml": _wf(name_line="name: PR fix-bot")})
    bad = cdf.violations(root)
    assert any("has no `— what it does` part" in b for b in bad), bad


@pytest.mark.parametrize("name_line", [
    "name: a-bot — does the work of a bot",
    "name: a-bot: does the work of a bot",
    'name: a-bot — "does the work of a bot"',
])
def test_a_described_name_passes(tmp_path, name_line):
    root = _tree(tmp_path, {"a-bot.yml": _wf(name_line=name_line)})
    assert cdf.violations(root) == []


def test_a_name_whose_description_is_too_short_is_a_violation(tmp_path):
    root = _tree(tmp_path, {"a-bot.yml": _wf(name_line="name: a-bot — does it")})
    assert any("fewer than" in b for b in cdf.violations(root))


# ---------------------------------------------------------------------------
# the dispatch form must document itself
# ---------------------------------------------------------------------------
def test_a_bare_workflow_dispatch_is_a_violation(tmp_path):
    root = _tree(tmp_path, {"a-bot.yml": _wf(dispatch="  workflow_dispatch:\n")})
    bad = cdf.violations(root)
    assert any("bare `workflow_dispatch:`" in b for b in bad), bad


def test_a_bare_workflow_dispatch_with_a_real_reason_is_allowed(tmp_path):
    root = _tree(tmp_path, {"a-bot.yml": _wf(
        dispatch="  workflow_dispatch:\n",
        extra="# dispatch: no inputs — it always runs the same sync, there is nothing to choose.\n",
    )})
    assert cdf.violations(root) == []


def test_a_bare_workflow_dispatch_with_an_empty_reason_is_a_violation(tmp_path):
    root = _tree(tmp_path, {"a-bot.yml": _wf(dispatch="  workflow_dispatch:\n",
                                            extra="# dispatch: no inputs — none.\n")})
    assert any("needs a real reason" in b for b in cdf.violations(root))


def test_an_input_without_a_description_is_a_violation(tmp_path):
    root = _tree(tmp_path, {"a-bot.yml": _wf(dispatch=(
        "  workflow_dispatch:\n    inputs:\n      n:\n        required: true\n"))})
    bad = cdf.violations(root)
    assert any("input `n` has no usable `description:`" in b for b in bad), bad


def test_an_input_with_neither_default_nor_required_is_a_violation(tmp_path):
    root = _tree(tmp_path, {"a-bot.yml": _wf(dispatch=(
        "  workflow_dispatch:\n    inputs:\n      n:\n        description: \"the PR number to repair\"\n"))})
    bad = cdf.violations(root)
    assert any("neither `default:` nor `required: true`" in b for b in bad), bad


def test_a_documented_input_passes_with_a_default_or_with_required(tmp_path):
    root = _tree(tmp_path, {"a-bot.yml": _wf(dispatch=(
        "  workflow_dispatch:\n    inputs:\n      a:\n        description: \"the PR number to repair\"\n"
        "        default: \"\"\n      b:\n        description: \"the issue to implement\"\n"
        "        required: true\n"))})
    assert cdf.violations(root) == []
    inputs = cdf.dispatch_inputs((root / cdf.WORKFLOWS / "a-bot.yml").read_text())
    assert [(i["key"], i["required"], i["has_default"]) for i in inputs] == [
        ("a", False, True), ("b", True, False)]


# ---------------------------------------------------------------------------
# the header block
# ---------------------------------------------------------------------------
def test_a_missing_header_key_is_a_violation(tmp_path):
    no_never = _wf().replace("# Never: never merges, never pushes to main.\n", "")
    root = _tree(tmp_path, {"a-bot.yml": no_never})
    bad = cdf.violations(root)
    assert any("missing `# Never:`" in b for b in bad), bad


def test_all_three_header_keys_pass(tmp_path):
    root = _tree(tmp_path, {"a-bot.yml": _wf()})
    assert cdf.header_block((root / cdf.WORKFLOWS / "a-bot.yml").read_text()) == [
        "Trigger surface", "Flow", "Never"]
    assert cdf.violations(root) == []


# ---------------------------------------------------------------------------
# scope: only what a human can start
# ---------------------------------------------------------------------------
def test_a_header_that_names_a_time_the_cron_does_not_have_is_a_violation(tmp_path):
    """Issue #275 moved every bot's minute; the prose moved with them in one file and not in three
    others. A header that says `05:17 UTC` over a `41 5 * * *` cron is the exact drift a reader
    believes, so the guard checks the claim against the schedule."""
    header = HEADER.replace("# Trigger surface: schedule + workflow_dispatch.",
                            "# Trigger surface: schedule daily 05:17 UTC, and workflow_dispatch.")
    stale = _wf().replace(HEADER, header)          # cron in _wf() is 23 6 * * *
    bad = cdf.violations(_tree(tmp_path, {"a-bot.yml": stale}))
    assert any("05:17 UTC" in b and "23 6 * * *" in b for b in bad), bad

    # And the SAME file with the header naming its real minute is clean
    ok_header = header.replace("05:17 UTC", "06:23 UTC")
    root = _tree(tmp_path, {"a-bot.yml": stale.replace(header, ok_header)})
    assert cdf.violations(root) == []


def test_a_header_time_with_no_schedule_at_all_is_a_violation(tmp_path):
    """`workflow_dispatch`-only, but the header claims a time: nothing schedules this, so the claim
    is about a run that does not exist."""
    no_sched = _wf().replace('  schedule:\n    - cron: "23 6 * * *"\n',
                             "").replace(HEADER, HEADER.replace("# Trigger surface: schedule + workflow_dispatch.",
                                                              "# Trigger surface: schedule daily 05:41 UTC."))
    bad = cdf.violations(_tree(tmp_path, {"a-bot.yml": no_sched}))
    assert any("no schedule" in b for b in bad), bad


def test_a_workflow_without_workflow_dispatch_is_out_of_scope(tmp_path):
    root = _tree(tmp_path, {"ci.yml": "name: CI\n\non:\n  push:\njobs:\n  a:\n    steps:\n      - run: make x\n"})
    assert cdf.violations(root) == []
    assert "ci.yml" not in cdf.table(root)


# ---------------------------------------------------------------------------
# the README table is generated from the workflows and verified against them
# ---------------------------------------------------------------------------
def test_the_table_lists_every_dispatchable_workflow_and_its_inputs(tmp_path):
    root = _tree(tmp_path, {
        "a-bot.yml": _wf(dispatch=("  workflow_dispatch:\n    inputs:\n      n:\n"
                                  "        description: \"the PR number to repair\"\n"
                                  "        default: \"3\"\n")),
        "ci.yml": "name: CI\n\non:\n  push:\njobs:\n  a:\n    steps:\n      - run: make x\n",
    })
    tbl = cdf.table(root)
    assert tbl.count("\n") == 2          # header + separator, then exactly ONE row (no trailing NL)
    assert "`a-bot.yml`" in tbl and "does the work of a bot" in tbl
    assert "`n` (optional, default `3`) — the PR number to repair" in tbl
    assert "ci.yml" not in tbl


def test_a_stale_readme_table_fails_and_a_fresh_one_passes(tmp_path):
    root = _tree(tmp_path, {"a-bot.yml": _wf()})
    (root / cdf.README).write_text(f"# t\n\n{cdf.BEGIN}\nstale\n{cdf.END}\n")
    assert "stale" in (cdf.readme_stale(root) or "")
    (root / cdf.README).write_text(f"# t\n\n{cdf.BEGIN}\n{cdf.table(root)}\n{cdf.END}\n")
    assert cdf.readme_stale(root) is None


def test_a_readme_without_the_markers_is_reported(tmp_path):
    root = _tree(tmp_path, {"a-bot.yml": _wf()})
    (root / cdf.README).write_text("# t\n\nno markers here\n")
    assert "no `<!-- dispatch-forms:begin -->`" in (cdf.readme_stale(root) or "")


# ---------------------------------------------------------------------------
# the exit code is what ci-unit gates on
# ---------------------------------------------------------------------------
def test_check_exits_non_zero_on_a_violation_and_zero_on_a_clean_tree(tmp_path, monkeypatch):
    bad_root = _tree(tmp_path / "bad", {"a-bot.yml": _wf(name_line="name: a-bot")})
    monkeypatch.setattr(sys, "argv", ["check_dispatch_forms.py", "check", "--root", str(bad_root)])
    assert cdf.main(["check", "--root", str(bad_root)]) == 1

    good_root = _tree(tmp_path / "good", {"a-bot.yml": _wf()})
    (good_root / cdf.README).write_text(f"# t\n\n{cdf.BEGIN}\n{cdf.table(good_root)}\n{cdf.END}\n")
    assert cdf.main(["check", "--root", str(good_root)]) == 0


def test_report_prints_the_table_and_exits_zero(tmp_path, capsys):
    root = _tree(tmp_path, {"a-bot.yml": _wf()})
    assert cdf.main(["report", "--root", str(root)]) == 0
    assert "| workflow | what the run does | dispatch inputs |" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# this repository passes its own guard
# ---------------------------------------------------------------------------
def test_this_repository_states_what_every_dispatchable_run_does():
    assert cdf.violations(REPO) == []
    assert cdf.readme_stale(REPO) is None
    assert cdf.main(["check"]) == 0


def test_every_bot_workflow_present_is_dispatchable_and_named():
    """The bots the goal names each have their own file, and each says what it does."""
    expected = {
        "issue-bot.yml", "fix-bot.yml", "engine-bump.yml", "engine-bump-rebase.yml",
        "registry-sync.yml", "queued-alarm.yml", "publish-agent-image.yml",
    }
    present = {p.name for p in cdf.workflow_files(REPO)}
    assert expected <= present, f"missing bot workflow(s): {sorted(expected - present)}"
    for name in sorted(expected):
        a = cdf.analyse(REPO / cdf.WORKFLOWS / name)
        assert a["dispatch"], f"{name} is not dispatchable by hand"
        ok, why = cdf.name_states_the_work(a["text"], a["stem"])
        assert ok, why
        assert a["inputs"] or a["exempt"], f"{name} has neither an input nor a reason for none"
