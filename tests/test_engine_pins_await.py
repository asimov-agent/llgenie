"""Tests for `scripts/engine_pins_await.py` — the ordering seam issue #3051 is about (issue #3051).

The engine-pin publication gate (#178) ran inside a PR lane while the job that publishes the tag
this very change repins was still running: PR #3030's unit lane read
`[pins] tensorfold cuda tensorfold:cpu-2026-11-24-c1a4024c865f -> HTTP Error 404: Not Found` at
2026-11-24T06:20Z, then `NOT PUBLISHED .../tensorfold:cpu-2026-11-24-c1a4024c865f (HTTP Error 404)` at
19:08:53Z, while `engine-build-pr-trigger.yml` for the same PR ran 18:53:30Z -> 20:50:34Z (2 h 57 m).
`needs:` cannot express that ordering because the producer is a job of a DIFFERENT workflow.

These tests pin the seam's contract: it is bounded, read-only (never dispatches, re-triggers or
re-runs), injectable (`lookup`/`sleep`/`clock`), never reddens the lane (always exit 0), and it sits
in the unit job BEFORE `make ci-unit`, which owns the verdict (`PINS-PENDING`).
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import engine_pins_await as apa  # noqa: E402
from conftest import REPO_ROOT, makefiles_text  # noqa: E402

WORKFLOWS = REPO_ROOT / ".github" / "workflows"
WORKFLOW = apa.PRODUCER_WORKFLOW


class FakeClock:
    """A clock that advances only when the code under test sleeps, so a bounded window is
    deterministic and instant without touching real time."""

    def __init__(self) -> None:
        self.now = 1000.0

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        assert seconds > 0, "the await loop must not busy-poll"
        self.now += seconds


def _run(run_id=7, status="in_progress", conclusion=None, head_branch="feat/x",
         head_sha="abc123"):
    """A row in the shape the Actions runs API actually returns (measured on the live API):
    `name` is the workflow display title (truncated), and `path` is the workflow FILE. A fixture
    whose `name` is the file stem hides the fact that matching on `name` finds nothing."""
    return {"id": run_id,
            "name": f"{WORKFLOW.removesuffix('.yml')} — a pin-bump PR starts the producer and wai",
            "path": f".github/workflows/{WORKFLOW}",
            "status": status, "conclusion": conclusion,
            "head_branch": head_branch, "head_sha": head_sha}


def _lookup(runs):
    calls: list[tuple[str, str]] = []

    def fake(repo, workflow):
        calls.append((repo, workflow))
        return list(runs)

    return fake, calls


def _env(monkeypatch, repo="asimov-agent/llgenie", head_sha="abc123", head_ref="feat/x"):
    monkeypatch.setenv("GITHUB_REPOSITORY", repo)
    monkeypatch.setenv("GITHUB_SHA", head_sha)
    monkeypatch.setenv("GITHUB_HEAD_REF", head_ref)


# ---------------------------------------------------------------- the await contract

def test_no_repinned_engine_skips_the_await(monkeypatch, capsys):
    """A lane that repins no engine has no producer to wait for: one lookup-free skip, exit 0."""
    monkeypatch.setattr(apa, "repinned_engine_ids", lambda base: [])
    monkeypatch.setattr(apa, "run_lookup",
                        lambda *a, **k: pytest.fail("must not look a producer up when nothing is repinned"))
    assert apa.await_producer("origin/main") == 0
    assert "nothing to await" in capsys.readouterr().out


def test_window_zero_probes_once_and_reports(monkeypatch, capsys):
    """Default window is 0 s (AGENTS: bounded, never an unbounded wait): the seam does exactly one
    lookup, prints the producer state, and never calls sleep."""
    monkeypatch.setattr(apa, "repinned_engine_ids", lambda base: ["tensorfold"])
    monkeypatch.setenv("GITHUB_REPOSITORY", "asimov-agent/llgenie")
    monkeypatch.delenv("ENGINE_PINS_AWAIT_SECONDS", raising=False)
    fake, calls = _lookup([_run(status="in_progress")])
    clock = FakeClock()
    rc = apa.await_producer("origin/main", lookup=fake, sleep=lambda s: pytest.fail("must not sleep"),
                            clock=clock.clock, head_sha="abc123", head_ref="feat/x")
    assert rc == 0
    assert calls == [("asimov-agent/llgenie", WORKFLOW)], "one bounded lookup at window 0"
    out = capsys.readouterr().out
    assert f"AWAIT 7 in_progress/None" in out
    assert "WINDOW-EXPIRED after 0s" in out


def test_window_waits_until_the_producer_concludes(monkeypatch, capsys):
    """An in-progress producer is awaited across polls; when it concludes the seam returns 0 and
    says so, leaving the verdict to the pins gate that follows it."""
    monkeypatch.setattr(apa, "repinned_engine_ids", lambda base: ["tensorfold"])
    monkeypatch.setenv("GITHUB_REPOSITORY", "asimov-agent/llgenie")
    seen = {"n": 0}

    def fake(repo, workflow):
        seen["n"] += 1
        if seen["n"] < 3:
            return [_run(status="in_progress", conclusion=None)]
        return [_run(status="completed", conclusion="success")]

    clock = FakeClock()
    rc = apa.await_producer("origin/main", lookup=fake, sleep=clock.sleep, clock=clock.clock,
                            seconds=600.0, poll_seconds=5.0, head_sha="abc123", head_ref="feat/x")
    assert rc == 0
    assert seen["n"] == 3
    out = capsys.readouterr().out
    assert "AWAIT 7 in_progress/None" in out
    assert "AWAIT DONE 1 producer run(s) concluded: 7 completed/success" in out
    assert clock.now < 1000.0 + 600.0, "returned as soon as the producer concluded, not at the window"


def test_window_expiry_reports_and_exits_zero(monkeypatch, capsys):
    """The expired window is a REPORT, not a red: the seam always returns 0 and names the producer
    runs still in progress; the pins gate is what reports them PINS-PENDING."""
    monkeypatch.setattr(apa, "repinned_engine_ids", lambda base: ["tensorfold"])
    monkeypatch.setenv("GITHUB_REPOSITORY", "asimov-agent/llgenie")
    fake, calls = _lookup([_run(status="in_progress")])
    clock = FakeClock()
    rc = apa.await_producer("origin/main", lookup=fake, sleep=clock.sleep, clock=clock.clock,
                            seconds=30.0, poll_seconds=10.0, head_sha="abc123", head_ref="feat/x")
    assert rc == 0
    out = capsys.readouterr().out
    assert "AWAIT WINDOW-EXPIRED after 30s with 1 producer run(s) still in progress" in out
    assert "the pins gate reports them PENDING (issue #3051)" in out
    assert len(calls) >= 2, "a bounded window still polls, it does not give up after one read"


def test_already_concluded_producer_is_not_waited_on(monkeypatch, capsys):
    """A producer that already finished (published, failed, cancelled) is reported and skipped —
    the gate then reads the registry state that producer left behind."""
    monkeypatch.setattr(apa, "repinned_engine_ids", lambda base: ["tensorfold"])
    monkeypatch.setenv("GITHUB_REPOSITORY", "asimov-agent/llgenie")
    fake, calls = _lookup([_run(status="completed", conclusion="failure")])
    clock = FakeClock()
    rc = apa.await_producer("origin/main", lookup=fake,
                            sleep=lambda s: pytest.fail("a concluded producer must not be polled"),
                            clock=clock.clock, seconds=300.0, head_sha="abc123", head_ref="feat/x")
    assert rc == 0
    assert len(calls) == 1
    out = capsys.readouterr().out
    assert "PRODUCER 7 already completed/failure" in out
    assert "AWAIT DONE 1 producer run(s) concluded" in out


def test_a_missing_producer_run_is_not_a_failure(monkeypatch, capsys):
    """No dispatch for this head (a fork head the trigger refuses, a local run): say so, exit 0,
    and let the pins gate make the call."""
    monkeypatch.setattr(apa, "repinned_engine_ids", lambda base: ["tensorfold"])
    monkeypatch.setenv("GITHUB_REPOSITORY", "asimov-agent/llgenie")
    fake, calls = _lookup([_run(head_branch="feat/other", head_sha="deadbeef")])
    rc = apa.await_producer("origin/main", lookup=fake, sleep=lambda s: None, clock=FakeClock().clock,
                            seconds=120.0, head_sha="abc123", head_ref="feat/x")
    assert rc == 0
    assert len(calls) == 1
    assert "no engine-build-pr-trigger.yml run for this head; nothing to await" in capsys.readouterr().out


def test_a_live_api_row_matches_on_path_not_display_name(monkeypatch, capsys):
    """The bug this case exists for (issue #3051): the runs API reports a run's display `name`, which
    is the workflow's `name:` line truncated — never the file name. A seam that filters on `name`
    finds no producer for any real head and prints "no run for this head" while a 2 h producer is
    running. Matching is on the workflow FILE (`path`)."""
    monkeypatch.setattr(apa, "repinned_engine_ids", lambda base: ["vllm"])
    monkeypatch.setenv("GITHUB_REPOSITORY", "asimov-agent/llgenie")
    row = _run(status="in_progress", head_branch="chore/engine-bump-vllm",
               head_sha="20b3f0307f8ed18f990f7ad4702bd7c1840e74c0")
    assert row["name"] not in (WORKFLOW, WORKFLOW.removesuffix(".yml")), \
        "the fixture must carry the real API row, not a convenient name"
    fake, calls = _lookup([row])
    clock = FakeClock()
    rc = apa.await_producer("origin/main", lookup=fake, sleep=clock.sleep, clock=clock.clock,
                            seconds=120.0, poll_seconds=10.0,
                            head_sha=row["head_sha"], head_ref=row["head_branch"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "no engine-build-pr-trigger.yml run for this head" not in out
    assert "AWAIT 7 in_progress/None" in out


def test_a_row_from_another_workflow_file_is_not_this_lane_s_producer(monkeypatch, capsys):
    """The path match is what makes the filter real: a row from a different workflow file must not be
    waited on, so the seam cannot be satisfied by any recent run of anything."""
    monkeypatch.setattr(apa, "repinned_engine_ids", lambda base: ["vllm"])
    monkeypatch.setenv("GITHUB_REPOSITORY", "asimov-agent/llgenie")
    row = _run(status="in_progress")
    row["path"] = ".github/workflows/engine-build.yml"
    fake, calls = _lookup([row])
    rc = apa.await_producer("origin/main", lookup=fake, sleep=lambda s: None,
                            clock=FakeClock().clock, seconds=60.0,
                            head_sha="abc123", head_ref="feat/x")
    assert rc == 0
    assert "no engine-build-pr-trigger.yml run for this head; nothing to await" \
        in capsys.readouterr().out


def test_a_lookup_failure_never_reddens_the_lane(monkeypatch, capsys):
    """The seam is informational: a failed Actions read warns and defers to the pins gate."""
    monkeypatch.setattr(apa, "repinned_engine_ids", lambda base: ["tensorfold"])
    monkeypatch.setenv("GITHUB_REPOSITORY", "asimov-agent/llgenie")

    def boom(repo, workflow):
        raise RuntimeError("API 403 Resource not accessible by integration")

    rc = apa.await_producer("origin/main", lookup=boom, sleep=lambda s: None,
                            clock=FakeClock().clock, seconds=60.0, head_sha="abc123", head_ref="feat/x")
    assert rc == 0
    err = capsys.readouterr().err
    assert "could not read engine-build-pr-trigger.yml runs" in err
    assert "the pins gate decides on its own" in err


def test_no_repository_warns_without_looking(monkeypatch, capsys):
    monkeypatch.setattr(apa, "repinned_engine_ids", lambda base: ["tensorfold"])
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    rc = apa.await_producer("origin/main", lookup=lambda *a: pytest.fail("no repo -> no lookup"),
                            sleep=lambda s: None, clock=FakeClock().clock)
    assert rc == 0
    assert "GITHUB_REPOSITORY is unset" in capsys.readouterr().err


def test_malformed_window_warns_and_waits_zero(monkeypatch, capsys):
    monkeypatch.setattr(apa, "repinned_engine_ids", lambda base: ["tensorfold"])
    monkeypatch.setenv("GITHUB_REPOSITORY", "asimov-agent/llgenie")
    monkeypatch.setenv("ENGINE_PINS_AWAIT_SECONDS", "not-a-number")
    fake, calls = _lookup([_run(status="in_progress")])
    clock = FakeClock()
    assert apa.await_producer("origin/main", lookup=fake, sleep=lambda s: None,
                              clock=clock.clock, head_sha="abc123", head_ref="feat/x") == 0
    assert "not a number" in capsys.readouterr().err
    assert len(calls) == 1, "a malformed window must not turn into an open-ended wait"


def test_await_is_read_only_no_dispatch_rerun_or_requeue():
    """AGENTS CI discipline: this seam may only READ run status. The script carries no
    dispatch, rerun, re-trigger or cancel call."""
    src = (REPO_ROOT / "scripts/engine_pins_await.py").read_text()
    names = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Call):
            f = node.func
            names.add(f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", ""))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            names.add(node.value)
    for forbidden in ("dispatches", "reruns", "cancel", "merge", "POST", "workflow_dispatch"):
        assert forbidden not in names, f"the await seam must be read-only, found {forbidden!r}"
    assert "runs?per_page" in src, "the only Actions call is the bounded read of run status"


# ---------------------------------------------------------------- the wiring into the lane

def test_the_await_runs_before_the_gate_that_uses_it():
    """Ordering is the whole change: in the unit job, `make engine-pins-await` must appear before
    `make ci-unit` (which runs `check-engine-pins-published`), or the seam achieves nothing."""
    wf = (WORKFLOWS / "pipeline.yml").read_text(encoding="utf-8")
    jobs = re.split(r"(?m)^  ([a-zA-Z0-9_-]+):\n", wf)
    unit = ""
    for name, body in zip(jobs[1::2], jobs[2::2]):
        if name == "unit":
            unit = body
            break
    assert unit, "pipeline.yml has no unit job to wire the await into"
    await_at = unit.index("make engine-pins-await")
    unit_at = unit.index("make ci-unit")
    assert await_at < unit_at, "the await step landed after the gate it is meant to precede"
    assert "actions: read" in unit.split("steps:", 1)[0], (
        "the Actions runs API needs the job token's actions:read (issue #893's lesson)")
    assert "ENGINE_PINS_AWAIT_SECONDS" in unit, "the window is configured in the lane, not in code"


def test_the_target_is_wired_in_the_makefile():
    mk = makefiles_text()
    assert "\nengine-pins-await:" in mk, "the seam is unreachable without a make target"
    phony = " ".join(ln for ln in (REPO_ROOT / "Makefile").read_text().splitlines()
                     if ln.startswith(".PHONY:") or ln.startswith("\t") or ln.startswith(" "))
    assert "engine-pins-await" in phony, "engine-pins-await is not declared .PHONY"
    assert "issue #3051" in mk


def test_the_verdict_lives_in_the_gate_not_the_await():
    """Two halves, one contract: the await never prints a verdict word, and the gate is the one
    that says PINS-PENDING / PINS DEFERRED."""
    await_src = (REPO_ROOT / "scripts/engine_pins_await.py").read_text()
    gate_src = (REPO_ROOT / "scripts/check_engine_pins_published.py").read_text()
    printed = []
    for node in ast.walk(ast.parse(await_src)):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "print":
            for arg in list(node.args) + list(node.keywords):
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    printed.append(arg.value)
                elif isinstance(arg, ast.JoinedStr):
                    printed.append("".join(
                        v.value for v in arg.values if isinstance(v, ast.Constant)))
    printed_text = " ".join(printed)
    assert "PINS-PENDING" not in printed_text and "PINS DEFERRED" not in printed_text, (
        "the await seam must not print a verdict; only the gate does")
    assert "PINS-PENDING" in gate_src and "PINS DEFERRED" in gate_src
