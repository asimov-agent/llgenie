"""The issue-bot re-checks the FAST gates before it pushes (issue #475).

The run that implemented #407 opened six PRs (#443-#448) that were functionally green and red only
on bookkeeping: an unticked `- [ ]` in `tasks.md`, a stale README target list, a wiring count. Each
was detectable on the host in seconds, each cost CI a round trip and up to an hour of the hourly
`fix-bot`. `make issue-bot-gates` closes that gap, and this file is what keeps it wired:

- the six gates are the ones the issue names, in its order;
- the real tree passes the static check (`scripts/issue_bot_gates.py check`);
- the target really runs the script (a target that stopped naming it is a green no-op);
- the issue-bot's step sits BETWEEN `Detect what the implementation changed` and
  `Commit + push the feature branch`, conditioned on a changed tree;
- a `ci-unit` gate nobody classified is a finding (the lock on "a new fast gate cannot be
  silently skipped"), and so is a stale `DEFERRED` entry;
- `run` stops at the FIRST failing gate, names it, and never starts the next one.

Every scratch tree is a real directory with a real Makefile and a real workflow, and `run` is
exercised through real `make` - no mock stands in for the product.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]

from scripts import issue_bot_gates

#: What the issue's "What done looks like" names, in that order: an independent pin on the list.
SPEC_GATES = (
    "lint",
    "check-workflows",
    "check-wiring",
    "check-docs",
    "check-pr-hygiene",
    "openspec-tasks-check",
)
WF = REPO / ".github" / "workflows" / "issue-bot.yml"


def _real_tree(tmp_path: Path, workflow: str | None = None) -> Path:
    """A copy of the real Makefile (optionally edited) and workflow, as a scratch checkout."""
    root = tmp_path / "tree"
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / "Makefile").write_text((REPO / "Makefile").read_text())
    (root / ".github" / "workflows" / "issue-bot.yml").write_text(
        workflow if workflow is not None else WF.read_text())
    return root


def test_the_fast_gates_are_exactly_the_six_the_issue_names():
    """The acceptance criterion is a fixed list, in order; widening it is a different issue."""
    # Given the guard module
    # When  its fast gates are read
    # Then  they are exactly the six the issue names, in the order it names them
    assert issue_bot_gates.FAST_GATES == SPEC_GATES


def test_the_real_tree_is_wired():
    """The real checkout: every fast gate is a phony target a ci-* job runs, and the bot runs it."""
    # Given the real checkout
    # When  the static check runs
    # Then  it reports no finding
    assert issue_bot_gates.check(REPO) == []


def test_the_issue_bot_runs_the_gate_between_detection_and_push():
    """Position is the whole contract: after the tree is known to have changed, before it is pushed."""
    # Given the real issue-bot workflow
    wf = yaml.safe_load(WF.read_text())

    # When  its implement job's steps are read in order
    steps = wf["jobs"]["implement"]["steps"]
    names = [s.get("name", "") for s in steps]
    gate = [i for i, s in enumerate(steps) if "make issue-bot-gates" in str(s.get("run") or "")]

    # Then  the gate is one step, BETWEEN the change detection and the push, gated on a change
    assert len(gate) == 1, f"expected one `make issue-bot-gates` step, found {len(gate)}"
    detect = names.index("Detect what the implementation changed")
    push = names.index("Commit + push the feature branch")
    assert detect < gate[0] < push
    assert "changed == 'true'" in str(steps[gate[0]].get("if") or "")


def test_the_target_runs_the_gate_script():
    """A target that stopped naming the script would report success having checked nothing."""
    # Given the real Makefile
    text = (REPO / "Makefile").read_text()

    # When  make is asked what the target would do (a dry run, nothing executes)
    out = subprocess.run(["make", "-n", "issue-bot-gates"], cwd=REPO, capture_output=True, text=True)

    # Then  it is declared .PHONY and its recipe is the script
    assert "issue-bot-gates" in issue_bot_gates._phony(text)
    assert out.returncode == 0, out.stderr
    assert "scripts/issue_bot_gates.py run" in out.stdout


def test_a_runner_ci_unit_stopped_calling_is_a_finding(tmp_path):
    """The runner and its own check must be reached from `ci-unit`, or they are dead code."""
    # Given checkouts whose ci-unit no longer calls one of the guard's own targets
    for target in ("issue-bot-gates", "issue-bot-gates-check"):
        text = (REPO / "Makefile").read_text().replace(f"\t$(MAKE) {target}\n", "", 1)
        root = _real_tree(tmp_path / target)
        (root / "Makefile").write_text(text)

        # When  the static check runs
        errors = issue_bot_gates.check(root)

        # Then  it names the target `ci-unit` dropped
        assert any(f"`make {target}`" in e and "ci-unit" in e for e in errors), (target, errors)


def test_a_new_ci_unit_gate_nobody_classified_reds_the_check(tmp_path):
    """The requested lock: adding a gate to ci-unit must force a fast/deferred decision."""
    # Given a checkout whose ci-unit runs one more gate than the guard classifies
    text = (REPO / "Makefile").read_text().replace(
        "\t$(MAKE) issue-bot-gates-check\n",
        "\t$(MAKE) issue-bot-gates-check\n\t$(MAKE) brand-new-gate\n", 1)
    root = _real_tree(tmp_path)
    (root / "Makefile").write_text(text)

    # When  the static check runs
    errors = issue_bot_gates.check(root)

    # Then  it fails, naming the gate and both ways to classify it
    found = [e for e in errors if "brand-new-gate" in e]
    assert found, errors
    assert "FAST_GATES" in found[0] and "DEFERRED" in found[0]


def test_a_stale_deferred_entry_is_named(tmp_path):
    """A classification for a gate ci-unit no longer runs has to be deleted, not left to rot."""
    # Given a checkout whose ci-unit dropped a gate DEFERRED still records
    text = (REPO / "Makefile").read_text().replace("\t$(MAKE) check-strata-models\n", "", 1)
    root = _real_tree(tmp_path)
    (root / "Makefile").write_text(text)

    # When  the static check runs
    errors = issue_bot_gates.check(root)

    # Then  the stale entry is named
    assert any("check-strata-models" in e and "stale" in e for e in errors), errors


def test_a_step_moved_after_the_push_reds_the_check(tmp_path):
    """A guard that runs after the push buys nothing: the red branch is already published."""
    # Given a workflow whose gate step follows the push
    wf = """name: scratch
on: [workflow_dispatch]
jobs:
  implement:
    runs-on: ubuntu-latest
    steps:
      - name: Detect what the implementation changed
        if: always() && steps.diff.outputs.changed == 'true'
        run: make issue-bot-changed
      - name: Commit + push the feature branch
        if: always() && steps.diff.outputs.changed == 'true'
        run: git push -u origin "$BRANCH"
      - name: Re-check the fast gates BEFORE the branch is pushed (issue #475)
        if: always() && steps.diff.outputs.changed == 'true'
        run: make issue-bot-gates
"""
    root = _real_tree(tmp_path, wf)

    # When  the static check runs
    errors = issue_bot_gates.check(root)

    # Then  it names the ordering violation
    assert any("AFTER" in e and "Commit + push" in e for e in errors), errors


def test_a_gate_that_never_prepares_the_test_image_reds_the_check(tmp_path):
    """`lint` runs in llgenie/test: a fresh runner has no such tag, so the gate must pull it first."""
    # Given a workflow whose gate step follows the detection and precedes the push, with no
    # `make test-image`/`make test-env` before it
    wf = """name: scratch
on: [workflow_dispatch]
jobs:
  implement:
    runs-on: ubuntu-latest
    steps:
      - name: Detect what the implementation changed
        if: always() && steps.diff.outputs.changed == 'true'
        run: make issue-bot-changed
      - name: Re-check the fast gates BEFORE the branch is pushed (issue #475)
        if: always() && steps.diff.outputs.changed == 'true'
        run: make issue-bot-gates
      - name: Commit + push the feature branch
        if: always() && steps.diff.outputs.changed == 'true'
        run: git push -u origin "$BRANCH"
"""
    root = _real_tree(tmp_path, wf)

    # When  the static check runs
    errors = issue_bot_gates.check(root)

    # Then  it names the missing environment preparation
    assert any("test-image" in e and "test-env" in e for e in errors), errors


def test_run_stops_at_the_first_failing_gate_and_names_it(tmp_path):
    """A red gate must end the run there: the gates after it would report on a change nobody fixed."""
    # Given a scratch Makefile whose second gate fails and whose third writes a marker
    root = tmp_path / "gates"
    root.mkdir()
    (root / "Makefile").write_text(
        ".PHONY: lint check-docs check-wiring\n"
        "lint:\n\t@echo lint-ok\n"
        "check-docs:\n\t@echo docs-bad && false\n"
        "check-wiring:\n\t@echo ran > later.marker\n")

    # When  the gate runner runs three gates in order (the real script, over real make)
    out = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "issue_bot_gates.py"), "run", "--root", str(root),
         "--gates", "lint", "check-docs", "check-wiring"],
        capture_output=True, text=True)

    # Then  it exits non-zero (make's own status for a failed recipe), names the failing gate,
    #       and never starts the next one
    assert out.returncode != 0, (out.returncode, out.stdout, out.stderr)
    assert "[issue-bot-gates] 1/3 make lint" in out.stdout
    assert "[issue-bot-gates] 2/3 make check-docs" in out.stdout
    assert "FAIL `make check-docs`" in out.stderr
    assert "3/3" not in out.stdout + out.stderr
    assert not (root / "later.marker").exists()
