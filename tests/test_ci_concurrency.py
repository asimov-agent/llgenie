"""The CI pipeline terminates the run that a push to the same PR supersedes (issue #288).

`ci.yml` is the only workflow this repo triggers on a pull request, and it declared no
`concurrency:` group at all — while every bot workflow declared one (with
`cancel-in-progress: false`, deliberately, so a bot run is never killed by its own next tick). So a
second push to a PR branch started a second run BESIDE the first.

Measured 2026-10-15 on `main` `9675c1fa`: `feat/bot-pipeline-isolation` had run `38680205632`
(sha `345e7eb8`, 04:11Z) and run `38683422700` (sha `846d4ed8`, 04:48Z) both live; `feat/dispatch-forms`
had two queued runs one minute apart; `main` had two queued runs. One superseded run costs the linux
suite (`make ci-unit` is measured at 11-20 min), the macOS job, and the `engine-image-*` matrix —
which also pushes to GHCR on a same-repo PR run.

The group carries `github.ref` (for a `pull_request` run that is `refs/pull/<n>/merge`), so one PR
supersedes its own predecessor and two different PRs never cancel each other. `cancel-in-progress` is
TRUE for `pull_request` ONLY: a `main` run cancelled mid-publish leaves a content-hash tag
half-pushed, so a `push` run is never superseded by its successor.

The `cancel-in-progress` value is EVALUATED for each event name, not grepped: a `true` copied for
every event is exactly the bug this guards.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
WF = REPO / ".github" / "workflows"
CI = "ci.yml"

#: The event whose run supersedes its own predecessor on the same ref.
SUPERSEDING_EVENT = "pull_request"


def _load(name: str) -> dict:
    return yaml.safe_load((WF / name).read_text())


def _on(wf: dict) -> dict:
    """The workflow's triggers. YAML 1.1 reads the bare key `on` as the boolean `True`, and a
    workflow may spell its triggers as a list (`on: [pull_request]`), so accept both."""
    on = wf.get("on") or wf.get(True)
    if isinstance(on, list):
        return {str(k): None for k in on}
    return on if isinstance(on, dict) else {}


def _concurrency(wf: dict):
    """`(group, cancel-in-progress)`, or None when the workflow declares no group."""
    conc = wf.get("concurrency")
    if conc is None:
        return None
    if isinstance(conc, dict):
        return conc.get("group"), conc.get("cancel-in-progress")
    return conc, None


def _evaluate(value, event_name: str):
    """What GitHub would do with a `cancel-in-progress` value for one triggering event.

    A literal boolean is returned as-is — that is the unconditional form the tests reject. An
    expression (`${{ ... }}`) is evaluated with `github.event_name` bound to the event, so the
    assertion is about behaviour, not about the string.
    """
    if isinstance(value, bool) or value is None:
        return value
    m = re.fullmatch(r"\$\{\{\s*(.*?)\s*\}\}", str(value), re.S)
    assert m, f"not a workflow expression: {value!r}"
    bound = re.sub(r"github\.event_name", repr(event_name), m.group(1))
    return bool(eval(bound, {"__builtins__": {}}, {}))  # noqa: S307 — a repo-owned workflow expression


def test_ci_cancels_the_run_a_push_supersedes():
    """ci.yml declares a per-ref group, so a push to a PR terminates that PR's previous run."""
    # Given the CI workflow's concurrency block
    conc = _concurrency(_load(CI))

    # Then it exists at all
    assert conc is not None, (
        f"{CI} declares no concurrency group: a push to a PR leaves the previous run alive"
    )
    group, cancel = conc

    # And the group is per-ref, so two different PRs never cancel each other
    assert "github.ref" in group, (
        f"{CI}: concurrency group {group!r} is not per-ref — a constant group would make one PR "
        "cancel another PR's run"
    )

    # And it is not an unconditional literal (that would kill a main run mid-publish)
    assert not isinstance(cancel, bool), (
        f"{CI}: cancel-in-progress must be conditional on the event, not the literal {cancel!r}"
    )


def test_cancel_in_progress_is_true_for_a_pr_and_false_for_main():
    """Superseding is for a pull request only; a main run is never cancelled by its successor."""
    # Given the cancel-in-progress expression of the CI workflow
    _, cancel = _concurrency(_load(CI))

    # Then a pull request supersedes its predecessor
    assert _evaluate(cancel, SUPERSEDING_EVENT) is True, (
        f"{CI}: cancel-in-progress must be true for {SUPERSEDING_EVENT}"
    )

    # And a push to main (the GHCR publish path) is never superseded mid-flight
    assert _evaluate(cancel, "push") is False, (
        f"{CI}: cancel-in-progress must be false for push — a cancelled main run leaves the "
        "content-hash image tag half-pushed"
    )


def test_every_pull_request_workflow_declares_a_group():
    """A new workflow on the pull-request path cannot silently re-introduce the leak."""
    # Given every workflow file
    missing: list[str] = []
    for path in sorted(WF.glob("*.yml")):
        wf = _load(path.name)

        # When it triggers on a pull request but declares no group
        if "pull_request" in _on(wf) and _concurrency(wf) is None:
            missing.append(path.name)

    # Then the test names it
    assert not missing, (
        "these workflows run on a pull_request with no concurrency group: " + ", ".join(missing)
    )


#: A workflow may cancel unconditionally only if it SAYS why (issue #917). The rule this gate defends is
#: real - a bot run hands up to 180 minutes of agent work to the runner, and a main run publishes images to
#: GHCR - but it is a rule about WORK, not about the word `true`: a sweep that reads fresh state and takes
#: one atomic action is idempotent, so superseding it costs nothing while starving it costs the fleet its
#: merger (measured: sixteen of forty queued runs were `auto-merge` waiting for itself). So the exemption is
#: greppable text IN THE WORKFLOW, reviewed in the same diff as the setting it explains - not an entry in a
#: list here, which is the shape that drifts.
SUPERSEDE_MARKER = "# concurrency: superseding is safe"


def _states_superseding_is_safe(path: Path) -> bool:
    """Does this workflow carry the reasoned marker that allows an unconditional `true`?"""
    return SUPERSEDE_MARKER in path.read_text()


def test_no_workflow_cancels_every_run_unconditionally():
    """`cancel-in-progress: true` for every event is never right here WITHOUT a stated reason: a bot run
    hands up to 180 minutes of agent work to the runner, and a main run publishes images to GHCR.

    The reason is per workflow and it lives in the workflow (see SUPERSEDE_MARKER); this test is what stops
    the word `true` appearing silently.
    """
    # Given every workflow file
    offenders: list[str] = []
    for path in sorted(WF.glob("*.yml")):
        conc = _concurrency(_load(path.name))

        # When it cancels every run unconditionally and says nothing about why
        if conc is not None and conc[1] is True and not _states_superseding_is_safe(path):
            offenders.append(path.name)

    # Then the test names it
    assert not offenders, (
        "cancel-in-progress: true would let a next tick kill an in-flight bot run or a GHCR "
        "publish: " + ", ".join(offenders)
    )


def test_engine_build_serialises_publishing_runs_but_not_a_narrow_dispatch():
    """A narrow `engine-build` dispatch must not vanish behind a full sweep (issue #621).

    Measured: `engine=llama.cpp arch=cpu push=false` (run 40199747645) was created while the full sweep
    (run 40199122842) was running, and it sat `pending` with **zero jobs** — the global `engine-build`
    group queued it behind four hours of work, which looks exactly like a dispatcher that does not work.
    The group is therefore keyed by the selection for a build-only run, while every run that PUBLISHES
    shares one group (two pushes must not race on the same `:<arch>` tag).
    """

    # Given the engine-build workflow's concurrency block
    conc = _concurrency(_load("engine-build.yml"))
    assert conc, "engine-build.yml declares no concurrency group"
    group, cancel = conc

    # When  the group expression is read
    text = str(group)

    # Then  it is keyed by the dispatch inputs, not a constant
    assert text.startswith("engine-build-"), text
    assert "inputs.engine" in text and "inputs.arch" in text, \
        f"the group is not keyed by the selection, so a narrow dispatch queues behind a sweep: {text}"

    # And  a publishing run still serialises globally, because two pushes could race on a tag
    assert "inputs.push" in text and "'push'" in text, \
        f"a publishing run must share one global group (tag race), got: {text}"

    # And  it never cancels a running sweep
    assert cancel is False or str(cancel).lower() == "false", cancel


def test_the_unconditional_cancel_escape_needs_the_marker_in_the_workflow(tmp_path):
    """The hatch is one greppable line, so an unexplained `true` cannot ride along with a reasoned one."""
    reasoned = tmp_path / "a.yml"
    reasoned.write_text("# concurrency: superseding is safe — a sweep re-reads and merges atomically\n"
                        "concurrency:\n  group: a\n  cancel-in-progress: true\n", encoding="utf-8")
    silent = tmp_path / "b.yml"
    silent.write_text("concurrency:\n  group: b\n  cancel-in-progress: true\n", encoding="utf-8")

    assert _states_superseding_is_safe(reasoned) is True
    assert _states_superseding_is_safe(silent) is False
