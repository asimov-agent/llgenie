#!/usr/bin/env python3
"""The sweep-concurrency report names the workflows that queue behind themselves (issue #917).

It is a REPORT, not a gate, because serialising a sweep that mutates shared state is a legitimate choice —
so what these tests pin is that the choice is **visible**: a scheduled workflow with no cancellation is
listed, one that supersedes is not, and the report always explains the cost and the decision either way.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import sweep_concurrency as sc  # noqa: E402

checker = sc


def wf(tmp_path: Path, name: str, body: str) -> Path:
    d = tmp_path / ".github" / "workflows"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(body, encoding="utf-8")
    return tmp_path


SCHEDULED = """name: {name}
on:
  schedule:
    - cron: "*/30 * * * *"
{concurrency}
jobs:
  sweep:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
"""

STACKING = 'concurrency:\n  group: {name}\n  cancel-in-progress: false\n'
SUPERSEDING = 'concurrency:\n  group: {name}\n  cancel-in-progress: true\n'


def test_a_scheduled_sweep_that_cannot_cancel_is_reported(tmp_path):
    """The measured #917 shape: a 30-minute sweep that waits for the previous one."""
    root = wf(tmp_path, "a.yml", SCHEDULED.format(name="a", concurrency=STACKING.format(name="a")))

    stacking, superseding = sc.classify(root)

    assert [e["name"] for e in stacking] == ["a.yml"], stacking
    assert superseding == [], superseding


def test_a_scheduled_sweep_that_supersedes_is_not_reported(tmp_path):
    """The fix's shape must leave the report quiet, or the report becomes noise nobody reads."""
    root = wf(tmp_path, "b.yml", SCHEDULED.format(name="b", concurrency=SUPERSEDING.format(name="b")))

    stacking, superseding = sc.classify(root)

    assert stacking == [], stacking
    assert [e["name"] for e in superseding] == ["b.yml"], superseding


def test_a_workflow_with_no_schedule_is_out_of_scope(tmp_path):
    """A `workflow_run` or `pull_request` trigger cannot stack on a clock, so it is not this report's business."""
    root = wf(tmp_path, "c.yml", "name: c\non:\n  push:\njobs:\n  j:\n    runs-on: ubuntu-latest\n"
                                "    steps:\n      - run: echo hi\n")

    stacking, superseding = sc.classify(root)

    assert stacking == [] and superseding == [], (stacking, superseding)


def test_the_report_states_the_cost_and_the_decision(tmp_path):
    """A list without the reasoning is a nag; the report must carry both the measurement and the judgement."""
    root = wf(tmp_path, "a.yml", SCHEDULED.format(name="a", concurrency=STACKING.format(name="a")))

    text = sc.report(root)

    assert "a.yml" in text, text
    assert "nine sweeps stacked" in text.lower(), text        # the measurement
    assert "cancel-in-progress: true" in text, text            # what to do when it is idempotent
    assert "MUTATES" in text, text                             # and when serialising is right


def test_it_runs_as_a_command(tmp_path):
    """The entry point a reader will actually use."""
    wf(tmp_path, "a.yml", SCHEDULED.format(name="a", concurrency=STACKING.format(name="a")))

    result = subprocess.run([sys.executable, str(REPO / "scripts" / "sweep_concurrency.py"), "report",
                             "--root", str(tmp_path)], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    assert "1 scheduled workflow(s) stack" in result.stdout, result.stdout


def test_a_stacking_sweep_that_states_why_is_decided_not_undecided(tmp_path):
    """Serialising a sweep that mutates shared state is right — but only if it SAYS so (#917).

    Otherwise the report repeats the same names forever and nobody can tell "nobody looked" from "we decided".
    """
    body = SCHEDULED.format(name="a", concurrency=STACKING.format(name="a")).replace(
        "concurrency:\n", "# concurrency: stacking is intended — it writes a shared file (issue #917).\nconcurrency:\n", 1)
    root = wf(tmp_path, "a.yml", body)

    stacking, _ = sc.classify(root)
    text = sc.report(root)

    assert stacking and stacking[0]["decided"] is True, stacking
    assert "0 scheduled workflow(s) stack with no stated decision" in text, text
    assert "UNDECIDED" not in text, text


def test_prose_in_the_block_cannot_flip_the_decision(tmp_path):
    """A comment that quotes the settings must not decide them (#917, found by the same bug in my own tests).

    The blocks in this tree explain themselves, and the explanation names `cancel-in-progress: true` while the
    setting is `false` (or the reverse). If the classifier read comments, this workflow would be filed as
    SUPERSEDING while it actually stacks — the report would say the opposite of the tree.
    """
    body = """name: a
on:
  schedule:
    - cron: "*/30 * * * *"
concurrency:
  # note: this file does not use cancel-in-progress: true, because it mutates a shared branch
  group: a
  cancel-in-progress: false
jobs:
  sweep:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
"""
    root = wf(tmp_path, "a.yml", body)

    stacking, superseding = checker.classify(root)

    assert [e["name"] for e in stacking] == ["a.yml"], (stacking, superseding)
    assert superseding == [], superseding
