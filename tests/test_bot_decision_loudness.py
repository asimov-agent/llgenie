"""A bot's DECISION step must be LOUD when the decision crashes (issue #312).

Every bot workflow first asks a `make` target which subject to work on (`…-sweep`, `…-pick`,
`…-dispatch`). Three of them swallowed the answer: the step ran under `set +e`, read the crash as
"nothing to do", and the run concluded GREEN while the bot never worked. Measured in this fleet:

- `rebase-bot.yml` (#310) — `action=${action:-unknown}` → `go=false`; the bot had never rebased a PR.
- `issue-refiner.yml` (#316) — the same shape on `make issue-refiner-pick`.
- `issue-bot.yml` (#312) — `rc=$?` captured, written to `GITHUB_OUTPUT`, and **never consulted**; an
  empty `action` falls through the cap/none test, `dispatch=true`, and the run marches on to
  triage/implement with no issue picked.

A `grep` for the check is not proof: `set -e` in the wrong place, or an `exit 0` at the end, both
make a step look guarded. So this test RUNS each decision step's own shell against a `make` that
fails, and requires the step to fail with it. The step's script is the product under test; `make` is
the external command it calls, stood in for the same way the `gh` tests stand in for `gh`.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
WF = REPO / ".github" / "workflows"

#: A bot's decision target: the pick/sweep/dispatch that chooses the subject of the run.
DECISION = re.compile(r"\bmake\s+(?:\S+\s+)?([a-z0-9-]+-(?:sweep|pick|dispatch))\b")
#: A `${{ … }}` in a `run:` block — substituted before execution, the way the runner does
#: (a real one is `REPO="${{ github.repository }}"`); bash must never see it.
EXPRESSION = re.compile(r"\$\{\{[^}]*\}\}")


def decision_steps() -> list[tuple[str, str, str]]:
    """(workflow file, step name, run text) for every step that runs a bot decision target."""
    out: list[tuple[str, str, str]] = []
    for path in sorted(WF.glob("*.yml")):
        data = yaml.safe_load(path.read_text())
        for job in (data.get("jobs") or {}).values():
            if not isinstance(job, dict):
                continue
            for step in job.get("steps") or []:
                if not isinstance(step, dict):
                    continue
                run = str(step.get("run") or "")
                if run and DECISION.search(run):
                    out.append((path.name, str(step.get("name") or "(unnamed)"), run))
    return out


def _fake_make(tmp_path: Path, rc: int) -> Path:
    """A `make` on PATH that records its argv and exits `rc` — the crash being modelled."""
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    fake = bindir / "make"
    fake.write_text(f'#!/usr/bin/env bash\necho "fake make: $*" >&2\nexit {rc}\n')
    fake.chmod(0o755)
    return bindir


def run_step(run: str, tmp_path: Path, rc: int = 7,
             make_body: str | None = None) -> subprocess.CompletedProcess:
    """Run a step's `run:` text the way the runner does: bash, with the command on PATH faked.

    `make_body` replaces the fake's whole body, for the direction where the decision must SUCCEED.
    """
    script = tmp_path / "step.sh"
    script.write_text(EXPRESSION.sub("x", run))
    output = tmp_path / "github-output.txt"
    output.write_text("")
    bindir = _fake_make(tmp_path, rc)
    if make_body is not None:
        fake = bindir / "make"
        fake.write_text("#!/usr/bin/env bash\n" + make_body)
        fake.chmod(0o755)
    env = {
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "HOME": str(tmp_path),
        "GITHUB_OUTPUT": str(output),
        "GITHUB_ACTIONS": "true",
        "REPO": "asimov-agent/llgenie",
        "GH_TOKEN": "not-a-real-token",
        "FORCE_ISSUE": "",
        "ISSUE": "1",
        "BRANCH": "bot/branch",
    }
    return subprocess.run(["bash", str(script)], env=env, capture_output=True, text=True,
                          cwd=tmp_path, timeout=120)


# ---------------------------------------------------------------------------
# the scope of the rule
# ---------------------------------------------------------------------------
def test_the_decision_steps_are_what_this_file_covers():
    """The rule is only as good as its scope: read the set from the tree, and require the three
    workflows whose decision was measured to be in it."""

    # Given the bot workflows in the tree
    steps = decision_steps()

    # When their decision steps are collected
    names = [w for w, _, _ in steps]

    # Then the measured ones are covered (a narrowed list is the failure this guards against)
    assert len(steps) >= 3, names
    for wf in ("issue-bot.yml", "issue-refiner.yml", "rebase-bot.yml"):
        assert wf in names, f"{wf} runs a decision target but is not covered: {names}"


def test_a_github_expression_in_a_step_is_substituted_before_it_runs():
    """Guard the guard: a `${{ … }}` left in a `run:` block would crash bash, which would make the
    loudness test below pass for the WRONG reason. `run_step` substitutes it the way the runner does
    (`fix-bot.yml` really does use `REPO="${{ github.repository }}"`), so the step is exercised, not
    tripped."""

    # Given a step whose run block interpolates a GitHub expression
    run = 'echo "repo=${{ github.repository }}"\nexit 0\n'

    with tempfile.TemporaryDirectory() as td:
        # When it is run
        r = run_step(run, Path(td))

        # Then bash saw a substituted value, not an expression
        assert r.returncode == 0, r.stdout + r.stderr
        assert "${{" not in r.stdout, r.stdout


# ---------------------------------------------------------------------------
# the rule: a crashed decision is a FAILED step
# ---------------------------------------------------------------------------
def test_a_crashed_decision_fails_the_step():
    """Table-driven over every decision step: run it against a `make` that exits 7 and require a
    non-zero exit. This is the rule of issue #312, proven by behaviour rather than by grep."""

    # Given every bot decision step in the tree
    steps = decision_steps()
    assert steps, "no decision step found — the rule would be vacuous"

    survivors: list[str] = []

    for wf, step, run in steps:
        with tempfile.TemporaryDirectory() as td:
            # When the decision command crashes
            r = run_step(run, Path(td), rc=7)

            # Then the step does not conclude success
            if r.returncode == 0:
                survivors.append(f"{wf} :: {step} — the step exited 0 while its decision crashed")

    assert survivors == [], "\n  ".join(["a crashed decision was swallowed:"] + survivors)


def test_the_step_that_had_no_check_now_reports_the_crash():
    """The specific defect: `issue-bot.yml`'s dispatch step captured `rc`, wrote it to
    `GITHUB_OUTPUT` and never consulted it."""

    # Given the issue-bot's dispatch step
    run = next(run for wf, _, run in decision_steps() if wf == "issue-bot.yml")

    with tempfile.TemporaryDirectory() as td:
        # When its decision crashes
        r = run_step(run, Path(td), rc=7)

        # Then the step fails, and says which target failed with which rc
        assert r.returncode != 0, r.stdout + r.stderr
        assert "issue-bot-dispatch rc=7" in r.stderr + r.stdout, r.stdout + r.stderr


def test_a_decision_that_succeeds_leaves_the_step_green():
    """The other direction, so the rule is not 'always fail': a decision that answers cleanly must
    leave the step successful."""

    # Given the issue-bot's dispatch step
    run = next(run for wf, _, run in decision_steps() if wf == "issue-bot.yml")

    with tempfile.TemporaryDirectory() as td:
        # When the decision succeeds, printing the machine-readable answer the step parses
        r = run_step(run, Path(td), rc=0, make_body='echo "action=none"\nexit 0\n')

        # Then the step concludes success
        assert r.returncode == 0, r.stdout + r.stderr
