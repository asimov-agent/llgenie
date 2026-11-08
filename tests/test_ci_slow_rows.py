"""`linux / top-tier` is off the pull_request matrix, and the decision is real (issue #859).

The row downloads and serves a real model on every PR; what it proves is a property of `main` and of
the weekly engine/registry data, not of a diff — and it was one of the long poles of every matrix.
Measured on #767's run 40694228407 (a one-file docs PR): 26 green jobs, 0 failures, the run held open
on one heavy row alone. The macOS rows the issue also named are gone by deletion (#870), so this
change is the one row that is left.

The selection is `scripts/ci_slow_rows.py` (behind `make ci-slow-rows`), published by ci.yml's
`guard` job and consumed as the ONE matrix axis of `pipeline.yml`'s `top-tier` job. These tests drive
that script for real and then pin the wiring that carries its output, because a decision that runs
but is not wired (or wired but not decided) is the same defect from the other side.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
WF = REPO / ".github" / "workflows"


def _script():
    spec = importlib.util.spec_from_file_location("ci_slow_rows", REPO / "scripts" / "ci_slow_rows.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("ci_slow_rows", mod)
    spec.loader.exec_module(mod)
    return mod


def _run(tmp_path, *args):
    """Run the script's CLI in-process with a real $GITHUB_OUTPUT file."""
    csr = _script()
    out = tmp_path / "gh_output"
    out.write_text("")
    old = {k: os.environ.get(k) for k in ("GITHUB_OUTPUT", "EVENT", "LABELS")}
    os.environ.update({"GITHUB_OUTPUT": str(out), "EVENT": "", "LABELS": ""})
    try:
        rc = csr.main(list(args))
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    values = dict(line.split("=", 1) for line in out.read_text().splitlines() if "=" in line)
    return rc, values


def test_a_pull_request_without_the_label_does_not_schedule_the_heavy_row():
    """The measured defect: every PR paid for a real model download + serve."""

    # Given a pull request that carries no label
    csr = _script()

    # When  the row selection is decided
    values = csr.decide("pull_request", [])

    # Then  the heavy row is the placeholder and the reason is recorded in the value
    assert values["slow"] == "false"
    assert values["top_tier_rows"] == '["none"]'


def test_the_ci_slow_label_brings_the_row_back():
    """An engine- or serve-path change asks for the row with one label."""

    # Given a pull request labelled `ci:slow`
    csr = _script()

    # When  the row selection is decided
    values = csr.decide("pull_request", ["ci:slow"])

    # Then  the row is scheduled again
    assert values["slow"] == "true"
    assert values["top_tier_rows"] == '["run"]'


def test_every_non_pull_request_event_keeps_the_row():
    """A push to main (one run per merge) must still catch a model/engine regression."""

    # Given the events a run can have outside a pull request
    csr = _script()

    # When  each one is decided
    decided = {event: csr.decide(event, []) for event in ("push", "workflow_dispatch", "schedule",
                                                          "workflow_run", "", "pull_request_target")}

    # Then  every one of them schedules the row (fail closed: only a PR can lose it)
    for event, values in decided.items():
        assert values["slow"] == "true", event
        assert values["top_tier_rows"] == '["run"]', event


def test_a_labelled_release_branch_run_is_still_a_pull_request():
    """The gate is the EVENT, not the presence of a payload: a labelled PR is a PR."""

    # Given a pull request on a release branch carrying an unrelated label plus the opt-in
    csr = _script()

    # When  it is decided
    unrelated = csr.decide("pull_request", ["bug", "docs"])
    labelled = csr.decide("pull_request", ["bug", "ci:slow"])

    # Then  only the opt-in label schedules the row
    assert unrelated["top_tier_rows"] == '["none"]'
    assert labelled["top_tier_rows"] == '["run"]'


def test_the_labels_input_reads_the_github_payload_shapes():
    """`toJSON(github.event.pull_request.labels.*.name)` is a JSON array — and `null` on a push."""

    # Given the shapes the workflow can hand the script
    csr = _script()

    # When  each is parsed
    parsed = {
        "json": csr._labels('["bug", "ci:slow"]'),
        "null": csr._labels("null"),
        "blank": csr._labels(""),
        "csv": csr._labels("bug, compound ci:slow"),
        "json-string": csr._labels('"ci:slow"'),
    }

    # Then  a JSON array is read element-wise, `null`/blank is no label, and a plain list still works
    assert parsed["json"] == ["bug", "ci:slow"]
    assert parsed["null"] == [] and parsed["blank"] == []
    assert parsed["csv"] == ["bug", "compound", "ci:slow"]
    assert parsed["json-string"] == ["ci:slow"]


def test_the_cli_writes_every_output_the_workflow_consumes(tmp_path):
    """The job output names are the contract: ci.yml reads exactly these keys."""

    # Given a pull request with no labels and a real $GITHUB_OUTPUT file
    # When  the CLI decides through `make ci-slow-rows`'s own arguments
    rc, values = _run(tmp_path, "decide", "--event", "pull_request", "--labels", "[]")

    # Then  it exits 0 and publishes the keys ci.yml names, none of them empty
    assert rc == 0
    assert set(values) == {"slow", "top_tier_rows"}
    assert all(values.values())


def test_the_run_log_states_the_decision(tmp_path, capsys):
    """An absent row must be a sentence in the log, not a row that simply vanishes."""

    # Given a pull request without the label
    # When  the CLI runs
    _run(tmp_path, "decide", "--event", "pull_request", "--labels", '["bug"]')

    # Then  one line names the event, the labels, the row's state and the label that brings it back
    line = capsys.readouterr().out.splitlines()[0]
    assert line.startswith("[ci-slow-rows] event=pull_request")
    assert "labels=bug" in line and "linux/top-tier=absent" in line and "ci:slow" in line


def test_ci_yml_publishes_the_decision_and_the_caller_consumes_it():
    """The decision must reach the matrix: a guard output nobody passes selects nothing."""

    # Given ci.yml, its guard job and the one pipeline caller
    ci = yaml.safe_load((WF / "ci.yml").read_text())["jobs"]
    guard = ci["guard"]

    # When  the guard's outputs and the step that produces them are read
    step = next(st for st in guard["steps"] if "ci-slow-rows" in str(st.get("run", "")))

    # Then  the step runs the make target with the event and the PR labels, and the one published
    #       value comes from it (`slow` is not an output: nothing would read it —
    #       tests/test_workflow_guards.py refuses a guard output nobody consumes)
    assert step["run"].strip() == "make ci-slow-rows"
    assert step["env"]["EVENT"] == "${{ github.event_name }}"
    assert "pull_request.labels" in step["env"]["LABELS"]
    assert set(guard["outputs"]) == {"top_tier_rows"}
    assert guard["outputs"]["top_tier_rows"] == f"${{{{ steps.{step['id']}.outputs.top_tier_rows }}}}"

    # And  the caller passes it in, waits for that job, and carries a guard-decoupling `if` so a
    #       guard BODY-text red (check-pr-acceptance-form, issue #2285) does not skip the linux
    #       fan-out GitHub's needs-default would otherwise impose. The `with` still consumes the
    #       guard's row-selection, with a fallback (`|| ...`) for the red-guard case where the
    #       failed job's outputs are not propagated.
    top = ci["linux"]["with"]["top_tier_rows"]
    assert "needs.guard.outputs.top_tier_rows" in top    # still reads the guard's row selection
    assert " || " in top and "none" in top               # fallback placeholder on a guard body-red
    assert "guard" in ci["linux"]["needs"]
    assert ci["linux"]["uses"] == "./.github/workflows/pipeline.yml"
    lf = ci["linux"]["if"]
    assert "always()" in lf and "needs['ci-images'].result" in lf, lf


def test_the_top_tier_row_is_the_only_axis_and_runs_no_work_when_absent():
    """A placeholder row must be unable to run a make target — the whole point is not paying."""

    # Given pipeline.yml's top-tier job
    job = yaml.safe_load((WF / "pipeline.yml").read_text())["jobs"]["top-tier"]
    steps = job["steps"]

    # When  its matrix, runner and steps are read
    # Then  the row list is the caller's input, there is NO job-level if: (a skipped job hides the
    #       check name), and every step that does work is gated on the row
    assert list(job["strategy"]["matrix"]) == ["row"]
    assert job["strategy"]["matrix"]["row"] == "${{ fromJSON(inputs.top_tier_rows) }}"
    assert "if" not in job
    assert job["runs-on"] == "${{ inputs.runner }}"
    assert "if" not in steps[0]                       # the "say why" step runs on both rows
    assert "NOT SCHEDULED" in steps[0]["run"]
    for step in steps[1:]:
        assert step.get("if", "").startswith("matrix.row != 'none'"), step.get("name")


def test_the_other_rows_keep_their_pr_gates():
    """Only the heavy row moved: the suite gate and the health row still run on every PR."""

    # Given pipeline.yml
    jobs = yaml.safe_load((WF / "pipeline.yml").read_text())["jobs"]

    # When  the rows that decide a PR verdict are read
    # Then  `unit` has no row axis and no placeholder, and `cpu-health` is untouched
    assert "strategy" not in jobs["unit"]
    assert not [st for st in jobs["unit"]["steps"] if "matrix.row" in str(st.get("if", ""))]
    assert "strategy" not in jobs["cpu-health"]
    assert "if" not in jobs["cpu-health"]


def test_the_coverage_trade_is_written_down():
    """A row that stopped running is a decision a reader must be able to find (issue #859)."""

    # Given the bot documentation and the workflow header
    doc = (REPO / "docs" / "BOTS.md").read_text()
    header = (WF / "ci.yml").read_text().split("jobs:", 1)[0]

    # When  the sentence that states the trade is looked for
    # Then  both name the row and the opt-in label, and the doc states what did not change
    for text in (doc, header):
        assert "linux / top-tier" in text
        assert "ci:slow" in text
    assert "linux / unit" in doc and "cpu-health" in doc
    assert "#870" in doc                                # the macOS half, resolved by deletion
