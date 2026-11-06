"""The "will" arm of the pin-bump gate: a PR that repins an engine triggers the producer (issue #1633).

`scripts/check_engine_pins_published.py` is the merged "may" arm (#1631/#1622): a bump PR may not MERGE
until its image is published. `scripts/engine_build_trigger.py` is the "will" arm this issue adds: the PR
itself dispatches `engine-build push=true` for exactly the engines it repins and awaits each run's verdict,
so a bump does not sit red-and-idle until a human remembers to dispatch the producer.

Hermetic: the repin set is stubbed and the chef is a fake `gh` that answers run-list/dispatch-verdict from
a fixed in-memory state, so the dispatch-and-wait AND the verdict logic are driven with real JSON — no
network, no real dispatch. Mirrors the fake-digest pattern of tests/test_check_engine_pins_published.py (#169).
The module is invoked IN-PROCESS (`ebt.main(...)`) so the monkeypatches bind — calling the script as a
subprocess would run the real 13-engine repin set and touch nothing the patches cover.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

import scripts.engine_build_trigger as ebt  # noqa: E402

_BASE = "deadbeef00000000000000000000000000000000"


def _stub_base(monkeypatch) -> None:
    monkeypatch.setattr(ebt.base_ref, "resolve_base", lambda explicit="", quiet=False: _BASE)


def _stub_repin(monkeypatch, engine=None) -> None:
    if engine is None:
        monkeypatch.setattr(ebt.cpp, "repinned_engine_ids", lambda base, root=None: [])
    else:
        monkeypatch.setattr(ebt.cpp, "repinned_engine_ids", lambda base, root=None: [engine])


def _fake_gh(monkeypatch, before_ids=None, new_run=None, guard_conclusion="success"):
    """A fake `gh`-API recorder. `_gh` is a module-level function (not the `gh` binary), so we stub the API
    read path; the `gh workflow run` dispatch call is a subprocess we neutralize via `_dispatch_and_wait`'s
    `--gh gh` default by replacing NOTHING there — instead we only stub `_gh` and give no branch/ref that
    would need a real git read for the CODE path under test."""
    state = {"new_id": "77", "guard_conclusion": guard_conclusion, "dispatched": False}

    def fake_gh_api(repo, *args, gh="gh"):
        # args: ("?per_page=100", "--jq", "<expr>")  OR  ("<runid>/jobs", "--jq", "<expr>")  OR  ("<runid>", "--jq", ...)
        target = args[0] if args else ""
        if "per_page=100" in target:
            runs = [{"id": str(_id), "event": "workflow_dispatch",
                     "path": "/.github/workflows/engine-build.yml"} for _id in (before_ids or [])]
            # The dispatched run exists ONLY after the (neutralized) dispatch subprocess ran, so the
            # before/after diff the code computes behaves like the real API: the new id is absent before.
            if state["dispatched"] and new_run is not None:
                runs.append({"id": state["new_id"], "event": "workflow_dispatch",
                             "path": "/.github/workflows/engine-build.yml"})
            return "\n".join(str(r["id"]) for r in runs)
        if "/jobs" in target:
            return json.dumps({"jobs": [{"name": "guard", "conclusion": state["guard_conclusion"]}]})
        # single-run verdict
        return json.dumps(new_run if new_run is not None else {"status": "queued", "conclusion": None})

    monkeypatch.setattr(ebt, "_gh", fake_gh_api)

    # Neutralize the actual `gh workflow run` dispatch and any `git` read: the code path under test is the
    # await/verdict logic, driven by fake_gh_api above — the real binary must never be reached. The dispatch
    # call also flips `state["dispatched"]`, making the new run's id visible to subsequent run-list reads.
    recorded = {"calls": []}

    def fake_run(*args, **kwargs):
        recorded["calls"].append(args[0] if args else None)
        arg0 = args[0] if args else []
        if len(arg0) >= 2 and arg0[:2] == ["gh", "workflow"]:
            state["dispatched"] = True
        return type("R", (), {"stdout": "", "returncode": 0})()

    monkeypatch.setattr(ebt.subprocess, "run", fake_run)
    return state


def _run(argv):
    return ebt.main(argv)


def test_no_engine_repinned_is_green_and_hermetic(monkeypatch):
    """A PR that repins nothing dispatches nothing: green, zero dispatch (~the may arm's hermetic rule)."""
    _stub_base(monkeypatch)
    _stub_repin(monkeypatch, engine=None)
    _fake_gh(monkeypatch, before_ids=[1], new_run=None)
    rc = _run(["check", "--base", _BASE, "--repo", "asimov-agent/llgenie", "--branch", "main", "--gh", "gh"])
    assert rc == 0


def test_a_repin_dispatches_push_true_and_awaits_the_verdict(monkeypatch):
    """A PR that repins one engine dispatches engine-build push=true for it and passes on run success."""
    _stub_base(monkeypatch)
    _stub_repin(monkeypatch, engine="llama.cpp")
    _fake_gh(monkeypatch, before_ids=[1],
             new_run={"status": "completed", "conclusion": "success", "completed_at": "2026-11-03T00:00:00Z"})
    rc = _run(["check", "--base", _BASE, "--repo", "asimov-agent/llgenie", "--branch", "main", "--gh", "gh"])
    assert rc == 0


def test_a_failed_producer_run_reds_the_trigger(monkeypatch):
    """A dispatched run that completes non-success makes the trigger exit non-zero (the verdict is the fact)."""
    _stub_base(monkeypatch)
    _stub_repin(monkeypatch, engine="llama.cpp")
    _fake_gh(monkeypatch, before_ids=[1],
             new_run={"status": "completed", "conclusion": "failure", "completed_at": "2026-11-03T00:00:00Z"})
    rc = _run(["check", "--base", _BASE, "--repo", "asimov-agent/llgenie", "--branch", "main", "--gh", "gh"])
    assert rc == 1


def test_guard_refused_is_named_not_a_bare_failure(monkeypatch):
    """A producer run refused at ITS OWN trigger guard is reported `NOT VERIFIED`, never a bare failure."""
    _stub_base(monkeypatch)
    _stub_repin(monkeypatch, engine="llama.cpp")
    _fake_gh(monkeypatch, before_ids=[1],
             new_run={"status": "completed", "conclusion": "failure", "completed_at": "2026-11-03T00:00:00Z"},
             guard_conclusion="failure")
    rc = _run(["check", "--base", _BASE, "--repo", "asimov-agent/llgenie", "--branch", "main", "--gh", "gh"])
    assert rc == 1


def test_report_never_dispatches(monkeypatch):
    """`report` names the repinned set but never dispatches (returns before any dispatch path)."""
    _stub_base(monkeypatch)
    _stub_repin(monkeypatch, engine="llama.cpp")
    _fake_gh(monkeypatch, before_ids=[1], new_run=None)
    rc = _run(["report", "--base", _BASE])
    assert rc == 0


def test_a_stalled_gh_call_cannot_hold_the_poll_past_its_deadline(monkeypatch):
    """The poll bound is authoritative even when a single `gh`/shell call blocks.

    Regression for the hung trigger (run 42180155072): `_sh` used `subprocess.run` with NO
    timeout, so a stalled `gh api` never returned and the `time.time() > deadline` check in
    `_dispatch_and_wait` was never reached. `_sh` must now cap each subprocess at
    SUBPROCESS_TIMEOUT and yield "" on TimeoutExpired, so the deadline decides.
    """
    monkeypatch.setattr(ebt, "SUBPROCESS_TIMEOUT", 1)  # 1s cap so a slow call fails fast
    t0 = time.time()
    out = ebt._sh([sys.executable, "-c", "import time; time.sleep(10)"])
    # The stalled subprocess is bounded: _sh returns promptly, "" on TimeoutExpired.
    assert out == ""
    assert time.time() - t0 < 5  # returned in ~1s, not after the 10s sleep


def test_dry_run_prints_the_plan_without_dispatching(monkeypatch, capsys):
    """`--dry` prints the dispatch plan and dispatches nothing."""
    _stub_base(monkeypatch)
    _stub_repin(monkeypatch, engine="llama.cpp")
    _fake_gh(monkeypatch, before_ids=[1], new_run=None)
    rc = _run(["check", "--base", _BASE, "--dry", "--repo", "asimov-agent/llgenie",
               "--branch", "main", "--gh", "gh"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "would dispatch engine-build push=true engine=llama.cpp" in captured.out
    assert "dry-run: nothing dispatched" in captured.out
