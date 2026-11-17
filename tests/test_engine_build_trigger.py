"""The "will" arm of the pin-bump gate: a PR that repins an engine triggers the producer (issue #1633).

`scripts/check_engine_pins_published.py` is the merged "may" arm (#1631/#1622): a bump PR may not MERGE
until its image is published. `scripts/engine_build_trigger.py` is the "will" arm this issue adds: the PR
itself dispatches `engine-build push=true` for exactly the CELLS it repins and awaits each run's verdict,
so a bump does not sit red-and-idle until a human remembers to dispatch the producer. Cell granularity
is the dispatch unit (issue #2590): an arch-less dispatch of a `DEFAULT_CPU_ONLY` engine builds only its
cpu cell, so a repinned GPU cell (the #2582 rocm tag) was never built by the trigger.

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


def _stub_repin(monkeypatch, engine=None, variant="cpu") -> None:
    if engine is None:
        monkeypatch.setattr(ebt.cpp, "repinned_cells", lambda base, root=None: [])
    else:
        monkeypatch.setattr(ebt.cpp, "repinned_cells", lambda base, root=None: [(engine, variant)])


def _fake_gh(monkeypatch, before_ids=None, new_run=None, guard_conclusion="success", stall_holder=None,
             single_run_404=False, list_missing=False, dispatch_rc=0, dispatch_err="", checkout_ref="HEAD",
             published=False):
    """A fake `gh`-API recorder. `_gh` is a module-level function (not the `gh` binary), so we stub the API
    read path; the `gh workflow run` dispatch call is a subprocess we neutralize via `_dispatch_and_wait`'s
    `--gh gh` default by replacing NOTHING there — instead we only stub `_gh` and give no branch/ref that
    would need a real git read for the CODE path under test.

    Each `gh workflow run` spawns a NEW run id (`77`, `78`, ...), so a replacement dispatch (issue #2890)
    is found by the same before/after run-list diff the real API drives.

    `single_run_404=True` models the #2059 poll race: the SINGLE-run endpoint
    (`/actions/runs/<id>`) answers the API's real 404 body (`{"message":"Not Found","status":"404"}`)
    while the run LIST still carries the run's true verdict — so `_run_verdict`'s list fallback is what
    resolves it. `published=True` makes the registry published-skip probe resolve a manifest; by default
    it returns "not published" so a repinned cell dispatches (the hermetic stand-in for `ebt._digest`).
    """
    base = [str(x) for x in (before_ids or [])]
    state = {"guard_conclusion": guard_conclusion, "dispatched": [], "next_id": 77}

    def _ids():
        ids = base + list(state["dispatched"])
        if stall_holder and str(stall_holder) not in ids:
            ids = [str(stall_holder)] + ids
        return ids

    def fake_gh_api(repo, *args, gh="gh"):
        # args: ("?per_page=100", "--jq", "<expr>")  OR  ("<runid>/jobs", "--jq", "<expr>")  OR  ("<runid>", "--jq", ...)
        target = args[0] if args else ""
        target_jq = args[2] if len(args) > 2 else ""
        if "per_page=100" in target:
            # #2059 list fallback: `_run_verdict` re-reads a 404'd run from the LIST with the jq
            # `select((.id|tostring) == "<id>") | {status, conclusion, completed_at}`. Model THAT:
            # the list carries the true verdict of the dispatched run (single_run_404 only affects
            # the single-run endpoint).
            if "select((.id|tostring)" in target_jq:
                if list_missing:
                    return ""  # the id is invisible on BOTH endpoints (a genuine unresolved 404)
                return json.dumps(new_run if isinstance(new_run, dict) else {})
            # Discovery (`_existing_run_ids`) and the push-group-holder probe (`_push_group_holder`) read
            # the run LIST and filter it; return the base + every dispatched run id. A holder (an
            # in_progress push=true run) is present as such, and the `_push_group_holder` jq picks it.
            runs = [{"id": i, "status": "in_progress" if i == str(stall_holder) else "queued"} for i in _ids()]
            if "in_progress" in target_jq:
                runs = [r for r in runs if r.get("status") == "in_progress"]
            return "\n".join(r["id"] for r in runs)
        if "/jobs" in target:
            return json.dumps({"jobs": [{"name": "guard", "conclusion": state["guard_conclusion"]}]})
        # single-run verdict
        if single_run_404:
            # The API's real 404 body — exactly what `gh api .../actions/runs/<id>` prints on stdout
            # (measured: `{"message":"Not Found",...,"status":"404"}`, rc=1). The old code parsed this
            # as a dict whose `status` is the literal string "404" and never concluded (issue #2059).
            return json.dumps({"message": "Not Found",
                               "documentation_url":
                                   "https://docs.github.com/rest/actions/workflow-runs#get-a-workflow-run",
                               "status": "404"})
        return json.dumps(new_run if isinstance(new_run, dict) else {"status": "queued", "conclusion": None})

    monkeypatch.setattr(ebt, "_gh", fake_gh_api)

    # Neutralize the actual `gh workflow run` dispatch and any `git` read: the code path under test is the
    # await/verdict logic, driven by fake_gh_api above — the real binary must never be reached. Each
    # dispatch flips a FRESH run id into `state["dispatched"]`, so the values recorded here drive the
    # discovery + verdict of that dispatch (and of a single replacement, issue #2890).
    recorded = {"calls": []}

    def fake_run(*args, **kwargs):
        recorded["calls"].append(args[0] if args else None)
        arg0 = args[0] if args else []
        if len(arg0) >= 2 and arg0[:2] == ["gh", "workflow"]:
            state["dispatched"].append(str(state["next_id"]))
            state["next_id"] += 1
            return type("R", (), {"stdout": "", "stderr": dispatch_err,
                                  "returncode": dispatch_rc})()
        if len(arg0) >= 3 and arg0[:3] == ["git", "rev-parse", "--abbrev-ref"]:
            # A `pull_request` checkout is detached: the real command prints the literal `HEAD`.
            return type("R", (), {"stdout": checkout_ref + "\n", "stderr": "", "returncode": 0})()
        return type("R", (), {"stdout": "", "stderr": "", "returncode": 0})()

    monkeypatch.setattr(ebt.subprocess, "run", fake_run)

    # Registry published-skip probe, hermetic: not published by default (a repinned cell dispatches);
    # `published=True` makes every probed ref resolve a manifest (a digest of the pinned content).
    monkeypatch.setattr(ebt, "_digest",
                        lambda ref: ("sha256:" + ("a" * 64), "") if published else ("", "manifest unknown"))
    state["dispatch_argv"] = recorded
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


def test_success_producer_terminates_even_with_status_not_completed(monkeypatch, capsys):
    """A producer that concludes `success` is TERMINAL even when its `status` stays in_progress.

    Regression for the hung trigger (issue #1994): the trigger's await loop used to conclude ONLY on
    `status == \"completed\"`, so a SUCCESS producer whose run object reads to the poll as a stale/
    mid-flight snapshot (e.g. `{status: in_progress, conclusion: success}`) held the trigger in_progress
    until its wall-clock bound (measured: trigger run 42352054921 hung 3h54m on producer 42352074711
    which was `{status: completed, conclusion: success, completed_at: null}`). #1936 made `cancelled`/
    `skipped` terminal; `success` is the green mirror. A far `--wait-min` proves we do not wait it out.
    """
    _stub_base(monkeypatch)
    _stub_repin(monkeypatch, engine="llama.cpp")
    _fake_gh(monkeypatch, before_ids=[1],
             new_run={"status": "in_progress", "conclusion": "success"})
    # `--wait-min 0` becomes the wall-clock bound of the test: on the OLD code (no success branch)
    # the loop falls through to the deadline and expires — rc 1 — so a regression fails FAST instead
    # of polling out a long bound; the success branch returns before the deadline, rc 0.
    rc = _run(["check", "--base", _BASE, "--repo", "asimov-agent/llgenie", "--branch", "main",
               "--wait-min", "0", "--gh", "gh"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "producer run 77 success" in captured.out


def test_cancelled_producer_terminates_with_named_cause(monkeypatch, capsys):
    """A producer that concludes `cancelled` is TERMINAL: the trigger stops waiting and names the cause
    instead of polling a run whose `status` never flips to `completed`.

    Regression for the hung trigger (issue #1931): run 42326516316 sat `in_progress` 3.5h on producer
    run 42326545643 which was CANCELLED 12 s after the trigger started. GitHub may report a
    concurrency-cancelled run with `conclusion: cancelled` while its `status` stays `in_progress`, so
    the terminal decision must come from the CONCLUSION. A far `--wait-min` proves we do not wait it out.
    """
    _stub_base(monkeypatch)
    _stub_repin(monkeypatch, engine="llama.cpp")
    _fake_gh(monkeypatch, before_ids=[1],
             new_run={"status": "in_progress", "conclusion": "cancelled"})
    rc = _run(["check", "--base", _BASE, "--repo", "asimov-agent/llgenie", "--branch", "main",
               "--wait-min", "120", "--gh", "gh"])
    assert rc == 1
    captured = capsys.readouterr()
    assert "producer cancelled — nothing to wait for" in captured.err


def test_skipped_producer_terminates_with_named_cause(monkeypatch, capsys):
    """A producer that concludes `skipped` is equally terminal — nothing to wait for (#1931)."""
    _stub_base(monkeypatch)
    _stub_repin(monkeypatch, engine="llama.cpp")
    _fake_gh(monkeypatch, before_ids=[1],
             new_run={"status": "in_progress", "conclusion": "skipped"})
    rc = _run(["check", "--base", _BASE, "--repo", "asimov-agent/llgenie", "--branch", "main",
               "--wait-min", "120", "--gh", "gh"])
    assert rc == 1
    captured = capsys.readouterr()
    assert "producer skipped — nothing to wait for" in captured.err


def test_a_404_poll_that_is_visible_in_the_run_list_concludes_success(monkeypatch, capsys):
    """A producer that SUCCEEDED while its single-run endpoint kept answering 404 must conclude SUCCESS.

    Regression for the #2059 hung trigger: the old poll parsed the API's 404 body
    (`{"message":"Not Found","status":"404"}`) as a run whose `status` is the literal string "404",
    which matches NO terminal branch, so it polled the full 60-min bound and then reported
    `never concluded, last status 404` on a producer that had already succeeded (measured: #1982
    producer 42428385314 `success`). `_run_verdict` re-reads the id from the run LIST, which carries
    the same fields. A far `--wait-min` proves we do not wait the bound out.
    """
    _stub_base(monkeypatch)
    _stub_repin(monkeypatch, engine="surogate")
    # The run is INVISIBLE on /actions/runs/<id> but SUCCEEDED in the run list.
    _fake_gh(monkeypatch, before_ids=[1],
             new_run={"status": "completed", "conclusion": "success"},
             single_run_404=True)
    rc = _run(["check", "--base", _BASE, "--repo", "asimov-agent/llgenie", "--branch", "main",
               "--wait-min", "120", "--gh", "gh"])
    assert rc == 0, "a 404-visible-but-successful producer must not red the trigger"
    captured = capsys.readouterr()
    assert "producer run 77 success" in captured.out
    # The re-resolution is a RECORDED decision (#1796), not a silent skip: a reader must be able to
    # see that the single-run endpoint 404'd and the run list supplied the verdict.
    assert "404 on the single-run endpoint" in captured.out, captured.out


def test_an_unresolved_404_at_expiry_is_named_a_poll_race_not_a_build_failure(monkeypatch, capsys):
    """When the id resolves on NEITHER endpoint for the whole bound, the failure must SAY so.

    A reader has to be able to tell a poll-visibility race from a producer that genuinely concluded
    and failed — issue #2059's third acceptance criterion.
    """
    _stub_base(monkeypatch)
    _stub_repin(monkeypatch, engine="surogate")
    _fake_gh(monkeypatch, before_ids=[1],
             new_run={"status": "completed", "conclusion": "success"},
             single_run_404=True, list_missing=True)
    # --wait-min 0 expires on the first poll, so the test drives the bound instantly.
    rc = _run(["check", "--base", _BASE, "--repo", "asimov-agent/llgenie", "--branch", "main",
               "--wait-min", "0", "--gh", "gh"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "POLL-VISIBILITY race" in err, err
    assert "not a build result" in err, err


def test_wait_expiry_names_the_run_and_last_status(monkeypatch, capsys):
    """A producer that NEVER concludes cannot hold the trigger past `wait_min`: expiry fails with the
    run id and its last known status, never a bare `concluded queued/None` (#1931, wall-clock bound).
    `--wait-min 0` expires on the first poll so the test drives the bound instantly."""
    _stub_base(monkeypatch)
    _stub_repin(monkeypatch, engine="llama.cpp")
    _fake_gh(monkeypatch, before_ids=[1],
             new_run={"status": "in_progress", "conclusion": None})
    rc = _run(["check", "--base", _BASE, "--repo", "asimov-agent/llgenie", "--branch", "main",
               "--wait-min", "0", "--gh", "gh"])
    assert rc == 1
    captured = capsys.readouterr()
    assert "wait bound (0 min) expired" in captured.err
    assert "producer run 77 never concluded" in captured.err
    assert "last status in_progress" in captured.err


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
    # The wait bound expired while the run sat pending; the line names the run, its last status and
    # the holder — never a bare `concluded pending/None` (the message shape #1931 makes explicit).
    assert "wait bound (0 min) expired" in captured.err
    assert "last status pending" in captured.err


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
    # A pending run with no holder still fails at the wait bound, named with run + last status.
    assert "wait bound (0 min) expired" in captured.err
    assert "last status pending" in captured.err


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
    assert "would dispatch engine-build push=true engine=llama.cpp arch=cpu" in captured.out


def test_a_repinned_gpu_cell_is_dispatched_with_its_explicit_arch(monkeypatch, capsys):
    """#2590: a change repinning ONLY the rocm cell of a DEFAULT_CPU_ONLY engine gets THAT cell dispatched.

    `vllm` builds cpu only when the producer is dispatched with no arch (issue #1836 narrowing).
    On PR #2582 the repin was the rocm cell: the trigger dispatched a bare `engine=vllm`, run
    43248400389 built only the cpu cell, and the new rocm tag stayed unpublished — the may arm
    (which expands a repinned ENGINE to every committed cell, rocm included) stayed red until a
    human dispatched `arch=rocm` out-of-band (run 43264436280). The will arm now dispatches per
    cell, so the cell the may arm demands is the cell the trigger actually produces.
    """
    _stub_base(monkeypatch)
    _stub_repin(monkeypatch, engine="vllm", variant="rocm")
    state = _fake_gh(monkeypatch, before_ids=[1],
                     new_run={"status": "completed", "conclusion": "success",
                              "completed_at": "2026-11-12T00:00:00Z"})
    rc = _run(["check", "--base", _BASE, "--repo", "asimov-agent/llgenie",
               "--branch", "feat/rocm", "--gh", "gh"])
    assert rc == 0
    argv = _dispatch_argvs(state)[0]
    fields = [argv[i + 1] for i in range(len(argv) - 1) if argv[i] == "--field"]
    assert fields == ["engine=vllm", "push=true", "arch=rocm"]
    out = capsys.readouterr().out
    assert "1 repinned cell(s) vs" in out
    assert "OK engine=vllm arch=rocm" in out


def test_the_dry_plan_names_the_cell_arch_and_never_an_archless_dispatch(monkeypatch, capsys):
    """The dry plan IS the dispatch plan: `engine=<id> arch=<variant>` per cell, never arch-less."""
    _stub_base(monkeypatch)
    _stub_repin(monkeypatch, engine="vllm", variant="rocm")
    _fake_gh(monkeypatch, before_ids=[1], new_run=None)
    rc = _run(["check", "--base", _BASE, "--dry", "--repo", "asimov-agent/llgenie",
               "--branch", "main", "--gh", "gh"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "would dispatch engine-build push=true engine=vllm arch=rocm @ main" in out
    assert "engine=vllm @ main" not in out


# ---------------------------------------------------------------------------
# dispatch-at-the-branch (issue #2089) — a `pull_request` checkout is DETACHED
# ---------------------------------------------------------------------------
def _dispatch_argvs(state: dict) -> list[list[str]]:
    return [c for c in state["dispatch_argv"]["calls"] if c and c[:2] == ["gh", "workflow"]]


def test_a_detached_pull_request_checkout_dispatches_at_the_head_ref(monkeypatch, capsys):
    """A detached checkout dispatches at GITHUB_HEAD_REF, NEVER at the literal `HEAD` (issue #2089).

    `git rev-parse --abbrev-ref HEAD` prints `HEAD` on a `pull_request` checkout, and
    `gh workflow run --ref HEAD` is rejected with HTTP 422 `No ref found for: HEAD`, so the repin
    PR never actually built (PR #1696). No `--branch` is passed here: the ref must come from the
    variable Actions exports, and the dispatched run id must still be awaited and recorded.
    """
    _stub_base(monkeypatch)
    _stub_repin(monkeypatch, engine="llama.cpp")
    monkeypatch.setenv("GITHUB_HEAD_REF", "feat/bump-llamacpp")
    state = _fake_gh(monkeypatch, before_ids=[1],
                     new_run={"status": "completed", "conclusion": "success",
                              "completed_at": "2026-11-08T00:00:00Z"})
    rc = _run(["check", "--base", _BASE, "--repo", "asimov-agent/llgenie", "--gh", "gh"])
    assert rc == 0
    argvs = _dispatch_argvs(state)
    assert argvs, "nothing was dispatched at all"
    argv = argvs[0]
    assert argv[argv.index("--ref") + 1] == "feat/bump-llamacpp"
    assert "HEAD" not in argv
    # The dispatched run's own id is the verdict — recorded, not inferred from the exit code.
    assert "producer run 77 success" in capsys.readouterr().out


def test_a_detached_checkout_that_names_no_ref_refuses_instead_of_dispatching(monkeypatch, capsys):
    """With no branch anywhere, the trigger REFUSES and names the fix — it never dispatches at HEAD."""
    _stub_base(monkeypatch)
    _stub_repin(monkeypatch, engine="llama.cpp")
    monkeypatch.delenv("GITHUB_HEAD_REF", raising=False)
    state = _fake_gh(monkeypatch, before_ids=[1], new_run=None, checkout_ref="HEAD")
    rc = _run(["check", "--base", _BASE, "--repo", "asimov-agent/llgenie", "--gh", "gh"])
    assert rc == 1
    assert _dispatch_argvs(state) == [], "a reference-less checkout must not dispatch at all"
    err = capsys.readouterr().err
    assert "refusing to dispatch" in err
    assert "GITHUB_HEAD_REF" in err


def test_every_dispatch_input_gets_its_own_field_argument(monkeypatch):
    """`gh workflow run --field` takes ONE value: each input is its own `--field` (issue #2089).

    On `main` the argv was `["--field", "engine=x", "push=true"]`, which hands `push=true` to `gh`
    as a POSITIONAL argument — the CLI rejects the call and no run starts. Measured as a
    pull_request trigger run that dispatched nothing and printed a bare `run  concluded queued/None`
    (run 42423190271 job 128555865778).
    """
    _stub_base(monkeypatch)
    _stub_repin(monkeypatch, engine="llama.cpp", variant="rocm")
    state = _fake_gh(monkeypatch, before_ids=[1], new_run={"status": "completed", "conclusion": "success"})
    assert _run(["check", "--base", _BASE, "--repo", "asimov-agent/llgenie",
                 "--branch", "feat/bump", "--arch", "rocm", "--gh", "gh"]) == 0
    argv = _dispatch_argvs(state)[0]
    # every input pair is `--field <k=v>`; nothing dangles as a positional after the workflow name
    assert [argv[i] for i in range(len(argv) - 1) if argv[i] == "--field"] != []
    fields = [argv[i + 1] for i in range(len(argv) - 1) if argv[i] == "--field"]
    assert fields == ["engine=llama.cpp", "push=true", "arch=rocm"]
    assert sum(1 for tok in argv if tok.startswith(("engine=", "push=", "arch="))) == 3


def test_a_rejected_dispatch_reports_the_cli_reason_not_a_bare_failure(monkeypatch, capsys):
    """A dispatch the CLI refuses prints its own error text (HTTP 422 …), never an empty run id."""
    _stub_base(monkeypatch)
    _stub_repin(monkeypatch, engine="llama.cpp")
    state = _fake_gh(monkeypatch, before_ids=[1], new_run=None,
                     dispatch_rc=1,
                     dispatch_err="gh: HTTP 422 (Unprocessable Entity) — the workflow input 'arch' is not valid")
    rc = _run(["check", "--base", _BASE, "--repo", "asimov-agent/llgenie",
               "--branch", "feat/bump", "--gh", "gh"])
    assert rc == 1
    assert _dispatch_argvs(state), "the rejected dispatch was still attempted"
    err = capsys.readouterr().err
    assert "HTTP 422" in err
    assert "the workflow input 'arch' is not valid" in err


# ---------------------------------------------------------------------------
# published-skip (issue #2890): a cell whose exact tag already resolves a manifest
# ---------------------------------------------------------------------------
def test_every_cell_published_dispatches_zero_and_exits_zero(monkeypatch, capsys):
    """A trigger pass whose every repinned cell resolves its exact tag dispatches 0 producers, rc 0."""
    # Given a PR that repins one cell whose exact committed tag already resolves a registry manifest
    _stub_base(monkeypatch)
    _stub_repin(monkeypatch, engine="llama.cpp")
    _fake_gh(monkeypatch, before_ids=[1],
             new_run={"status": "completed", "conclusion": "success", "completed_at": "2026-11-17T00:00:00Z"},
             published=True)

    # When  the trigger runs check against that published cell
    rc = _run(["check", "--base", _BASE, "--repo", "asimov-agent/llgenie", "--branch", "main", "--gh", "gh"])

    # Then  it dispatches ZERO producers and exits 0 (the reopen costs seconds, not a matrix re-shuffle)
    assert rc == 0
    out = capsys.readouterr().out
    assert "PUBLISHED-SKIP" in out, out
    assert "no build dispatched" in out, out
    assert "every repinned cell's push=true build succeeded" in out, out


# ---------------------------------------------------------------------------
# per-arch-class wait budgets (issue #2890) — rocm 150, others 60, --wait-min overrides
# ---------------------------------------------------------------------------
def test_per_arch_wait_budgets_rocm_gets_150_cpu_cuda_vulkan_keep_60():
    """A cold ROCm cell gets a 150-min budget vs the 60-min flat default; --wait-min overrides every class."""
    # Given the measured cold-build history (a ROCm cell can still be building past 61 min)
    # When  the per-cell budget is resolved without an explicit --wait-min
    # Then  rocm is awaited with its cold-build bound and cpu/cuda/vulkan keep the flat 60
    assert ebt._cell_wait_min("rocm", None) == 150
    for variant in ("cpu", "cuda", "vulkan"):
        assert ebt._cell_wait_min(variant, None) == 60
    # An unknown/other arch falls back to the flat bound, never below it
    assert ebt._cell_wait_min("some-other-variant", None) == 60
    # And an explicit --wait-min overrides EVERY class
    assert ebt._cell_wait_min("rocm", 60) == 60
    assert ebt._cell_wait_min("cpu", 120) == 120


# ---------------------------------------------------------------------------
# replacement cap (issue #2890): at most ONE replacement dispatch per (cell, trigger run)
# ---------------------------------------------------------------------------
def test_a_cancelled_producer_yields_at_most_one_replacement_dispatch_per_cell(monkeypatch, capsys):
    """A queued producer cancelled gets exactly ONE replacement dispatch; a second cancellation fails the cell.

    The replacement inherits the cell's remaining budget, so a cancellation storm cannot re-queue the
    same cell unboundedly — the trigger exits 1 naming the per-cell cap it reached.
    """
    # Given a queued producer that is CANCELLED (a concurrency cancellation storm)
    _stub_base(monkeypatch)
    _stub_repin(monkeypatch, engine="llama.cpp")
    state = _fake_gh(monkeypatch, before_ids=[1],
                     new_run={"status": "in_progress", "conclusion": "cancelled"})

    # When  the trigger awaits the cell and its (also-cancelled) one replacement
    rc = _run(["check", "--base", _BASE, "--repo", "asimov-agent/llgenie", "--branch", "main",
               "--wait-min", "120", "--gh", "gh"])

    # Then  it dispatched at most ONE replacement (2 total) and failed naming the per-cell cap
    assert len(_dispatch_argvs(state)) == 2, "exactly one original + once replacement, never more"
    assert rc == 1
    err = capsys.readouterr().err
    assert "producer cancelled — nothing to wait for" in err
    assert "after ONE replacement dispatch" in err


def test_await_cell_withholds_replacement_when_the_budget_is_already_spent(monkeypatch):
    """When the cell spent its whole budget waiting on the cancelled producer, no replacement fires.

    The budget-carry is the point of the cap: a cancellation cannot buy a fresh full window — a cell
    with no remaining budget is NOT re-queued, locking the replace-at-most-once rule even against a
    mid-budget cancellation.
    """
    # Given a cell whose whole wait budget is already consumed by the (cancelled) first producer
    def fake_dispatch(repo, branch, engine, arch, wait_min, gh):
        return {"run_id": "77", "conclusion": "cancelled",
                "cause": "producer cancelled — nothing to wait for"}

    monkeypatch.setattr(ebt, "_dispatch_and_wait", fake_dispatch)

    # When  _await_cell runs with a zero/minimal budget
    outcome = ebt._await_cell("r", "b", "llama.cpp", "cpu", 0, "gh")

    # Then  no replacement is dispatched and the cap is recorded
    assert outcome["replace_cap"] is True
    assert outcome["replaced"] is True

