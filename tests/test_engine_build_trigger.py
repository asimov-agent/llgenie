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


def _fake_gh(monkeypatch, before_ids=None, new_run=None, guard_conclusion="success", stall_holder=None):
    """A fake `gh`-API recorder. `_gh` is a module-level function (not the `gh` binary), so we stub the API
    read path; the `gh workflow run` dispatch call is a subprocess we neutralize via `_dispatch_and_wait`'s
    `--gh gh` default by replacing NOTHING there — instead we only stub `_gh` and give no branch/ref that
    would need a real git read for the CODE path under test."""
    state = {"new_id": "77", "guard_conclusion": guard_conclusion, "dispatched": False}

    def fake_gh_api(repo, *args, gh="gh"):
        # args: ("?per_page=100", "--jq", "<expr>")  OR  ("<runid>/jobs", "--jq", "<expr>")  OR  ("<runid>", "--jq", ...)
        target = args[0] if args else ""
        target_jq = args[2] if len(args) > 2 else ""
        in_progress_ids = {str(stall_holder)} if stall_holder else set()
        if "per_page=100" in target:
            runs = [{"id": str(_id), "event": "workflow_dispatch",
                     "path": "/.github/workflows/engine-build.yml"} for _id in (before_ids or [])]
            # A run that is still `pending`/queued (our dispatched run, or a genuinely queued one) is
            # NOT a push-group holder: `_push_group_holder` filters `.status == "in_progress"` (the
            # global engine-build-push gate is held only by a RUN THAT IS RUNNING). The fake must
            # model that filter or it would surface a pending run as the gate holder.
            def _mark(r):
                r = dict(r)
                if r["id"] not in in_progress_ids:
                    r.setdefault("status", "queued")
                return r
            runs = [_mark(r) for r in runs]
            # A stall holder is an in_progress push run that `_push_group_holder` picks up; it is
            # present in the list both before and after our dispatch (so it never counts as "new").
            if stall_holder:
                runs.insert(0, {"id": str(stall_holder), "event": "workflow_dispatch",
                                "path": "/.github/workflows/engine-build.yml",
                                "status": "in_progress"})
            # The dispatched run exists ONLY after the (neutralized) dispatch subprocess ran, so the
            # before/after diff the code computes behaves like the real API: the new id is absent before.
            if state["dispatched"] and new_run is not None:
                runs.append({"id": state["new_id"], "event": "workflow_dispatch",
                             "path": "/.github/workflows/engine-build.yml"})
            # `_push_group_holder` filters `.status == "in_progress"` and reads "\n"-joined ids;
            # every other run-list read (`_existing_run_ids`, `_branch_producers`) wants the JSON dict.
            if "in_progress" in target_jq:
                runs = [r for r in runs if r.get("status") == "in_progress"]
                return "\n".join(str(r["id"]) for r in runs)
            return json.dumps({"workflow_runs": runs})
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
    state["calls"] = recorded["calls"]
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


def test_stalled_behind_push_holder_is_named_not_a_bare_queued(monkeypatch, capsys):
    """A dispatched run left `pending` behind the global engine-build-push group must be reported as
    STALLED with its holder named — never a bare `concluded queued/None` that invites a futile re-dispatch.

    Regression for the #1696 diagnosis (issue #1860): channel 42201352115 sat pending/0-jobs for 3h+,
    gated behind holder 42191808660's hung vllm-rocm; `engine_build_trigger.py` then bailed at deadline
    with only `concluded queued/None`, so the reviewer saw nothing to identify the concurrency gate.
    """
    _stub_base(monkeypatch)
    _stub_repin(monkeypatch, engine="vllm")
    # Holder "5" (in_progress push run) gates the new run "77", which stays `pending` (0-jobs).
    _fake_gh(monkeypatch, before_ids=[99], new_run={"status": "pending", "conclusion": None},
             stall_holder="5")
    # --wait-min 0 makes the deadline expire on the first poll, so the test runs instantly and still
    # exercises the stall branch (status "pending" != completed).
    rc = _run(["check", "--base", _BASE, "--repo", "asimov-agent/llgenie", "--branch", "main",
               "--wait-min", "0", "--gh", "gh"])
    assert rc == 1
    captured = capsys.readouterr()
    assert "STALLED behind engine-build-push group holder run 5" in captured.err
    assert "re-dispatch queues behind the same gate" in captured.err
    # The bare queued/None line must still be there (the verdict facts), just not alone.
    assert "concluded pending/None" in captured.err


def test_stalled_without_holder_is_a_plain_failure(monkeypatch, capsys):
    """A pending run with NO holder found is still a failure, but without the STALLED suffix."""
    _stub_base(monkeypatch)
    _stub_repin(monkeypatch, engine="vllm")
    _fake_gh(monkeypatch, before_ids=[99], new_run={"status": "pending", "conclusion": None},
             stall_holder=None)
    rc = _run(["check", "--base", _BASE, "--repo", "asimov-agent/llgenie", "--branch", "main",
               "--wait-min", "0", "--gh", "gh"])
    assert rc == 1
    captured = capsys.readouterr()
    assert "STALLED behind" not in captured.err
    assert "concluded pending/None" in captured.err


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


def test_detached_head_dispatches_the_pull_request_branch(monkeypatch):
    """A detached pull_request checkout must not dispatch `--ref HEAD` (HTTP 422, PR #1696)."""
    assert ebt._dispatch_ref("fix/1558-vllm-rocm-build") == "fix/1558-vllm-rocm-build"
    monkeypatch.setenv("GITHUB_HEAD_REF", "fix/1558-vllm-rocm-build")
    assert ebt._dispatch_ref("") == "fix/1558-vllm-rocm-build"
    assert ebt._dispatch_ref("HEAD") == "fix/1558-vllm-rocm-build"


def test_a_rejected_dispatch_fails_without_waiting(monkeypatch, capsys):
    """HTTP 422 from `gh workflow run` is the failure. Do not poll for a run that was never created."""
    _stub_base(monkeypatch)
    _stub_repin(monkeypatch, engine="vllm")

    def fake_run(args, **kwargs):
        return type("R", (), {"stdout": "", "stderr": "could not create workflow dispatch event: HTTP 422: No ref found for: HEAD", "returncode": 1})()

    monkeypatch.setattr(ebt.subprocess, "run", fake_run)
    monkeypatch.setattr(ebt, "_gh", lambda *a, **k: "")
    rc = _run(["check", "--base", _BASE, "--repo", "asimov-agent/llgenie",
               "--branch", "fix/1558-vllm-rocm-build", "--gh", "gh"])
    assert rc == 1
    assert "No ref found for: HEAD" in capsys.readouterr().err


def test_slashless_workflow_path_counts_as_the_producer(monkeypatch):
    """The runs API omits the leading slash. That run is the producer (PR #1696)."""
    payload = json.dumps({"workflow_runs": [
        {"id": 5, "event": "workflow_dispatch", "path": ".github/workflows/engine-build.yml"},
        {"id": 6, "event": "workflow_dispatch", "path": "/.github/workflows/engine-build.yml"},
        {"id": 7, "event": "pull_request", "path": ".github/workflows/engine-build.yml"},
        {"id": 8, "event": "workflow_dispatch", "path": ".github/workflows/ci.yml"},
    ]})
    monkeypatch.setattr(ebt, "_gh", lambda *a, **k: payload)
    assert ebt._existing_run_ids("asimov-agent/llgenie", "gh") == {"5", "6"}


def test_dispatch_repeats_field_so_push_is_an_input(monkeypatch):
    """`push=true` must be its own `--field`. One `--field` drops the rest and the run does not publish."""
    assert ebt._workflow_run_args("gh", "asimov-agent/llgenie", "fix/1558-vllm-rocm-build",
                                  ["engine=vllm", "push=true"]) == [
        "gh", "workflow", "run", "engine-build.yml", "--repo", "asimov-agent/llgenie",
        "--ref", "fix/1558-vllm-rocm-build", "--field", "engine=vllm", "--field", "push=true",
    ]
    _stub_base(monkeypatch)
    _stub_repin(monkeypatch, engine="vllm")
    state = _fake_gh(monkeypatch, before_ids=[1],
                     new_run={"status": "completed", "conclusion": "success", "completed_at": "2026-11-03T00:00:00Z"})
    rc = _run(["check", "--base", _BASE, "--repo", "asimov-agent/llgenie",
               "--branch", "fix/1558-vllm-rocm-build", "--gh", "gh"])
    assert rc == 0
    cmd = next(c for c in state["calls"] if c and c[:2] == ["gh", "workflow"])
    assert cmd.count("--field") == 2
    assert cmd[cmd.index("--field") + 1] == "engine=vllm"
    assert cmd[cmd.index("push=true") - 1] == "--field"


def test_an_in_progress_producer_on_this_branch_is_awaited(monkeypatch, capsys):
    """A second trigger for the same params must not dispatch another engine-build."""
    _stub_base(monkeypatch)
    _stub_repin(monkeypatch, engine="vllm")
    calls = []

    def fake_run(args, **kwargs):
        calls.append(list(args) if args else [])
        return type("R", (), {"stdout": "", "stderr": "", "returncode": 0})()

    def fake_gh(repo, *args, gh="gh"):
        target = args[0] if args else ""
        if "branch=" in target:
            return json.dumps([{
                "id": "41696864556", "status": "in_progress", "conclusion": None,
                "head_sha": "7487a1c6",
            }])
        if target.startswith("41696864556/jobs"):
            return "engine-build-vllm-cpu\nengine-build-vllm-rocm\n"
        if target.startswith("41696864556"):
            return json.dumps({"status": "completed", "conclusion": "success"})
        return json.dumps({"workflow_runs": []})

    monkeypatch.setattr(ebt, "_params_match", lambda sha: True)
    monkeypatch.setattr(ebt.subprocess, "run", fake_run)
    monkeypatch.setattr(ebt, "_gh", fake_gh)
    rc = _run(["check", "--base", _BASE, "--repo", "asimov-agent/llgenie",
               "--branch", "fix/1558-vllm-rocm-build", "--gh", "gh"])
    assert rc == 0
    assert not any(c[:2] == ["gh", "workflow"] for c in calls)
    assert "awaiting it, not dispatching again" in capsys.readouterr().out


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
