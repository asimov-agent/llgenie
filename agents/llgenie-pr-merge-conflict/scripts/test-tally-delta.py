#!/usr/bin/env python3
"""Controls for tally-delta.py's classifier — the rule that decides whether a PR is green-and-mergeable.

Every case is synthetic: no network, no GitHub state touched. The point is that the *distinctions*
are pinned, because the whole reason this script exists is that `gh pr checks` renders `cancelled`
as "fail", which makes a superseded run read as a red one.

Run: python3 scripts/test-tally-delta.py
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("tally_delta", HERE / "tally-delta.py")
td = importlib.util.module_from_spec(spec)
spec.loader.exec_module(td)

PR_CLEAN = {"number": 1, "isDraft": False, "mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN"}
PR_BLOCKED = dict(PR_CLEAN, mergeStateStatus="BLOCKED")
PR_DIRTY = dict(PR_CLEAN, mergeable="CONFLICTING", mergeStateStatus="DIRTY")
PR_DRAFT = dict(PR_CLEAN, isDraft=True)


def run(*pairs: str) -> list[dict]:
    """(name, conclusion) pairs -> check-run dicts, all completed."""
    return [{"name": n, "conclusion": c, "status": "completed"} for n, c in pairs]


CASES = []


def case(name):
    def wrap(fn):
        CASES.append((name, fn))
        return fn
    return wrap


@case("CLEAN + all success  -> green")
def _():
    ok, fails = td.classify(PR_CLEAN, run(("guard", "success"), ("linux / unit", "success")))
    return ok is True and fails == []


@case("CLEAN + skipped only -> green (skipped is settled, not a failure)")
def _():
    ok, _ = td.classify(PR_CLEAN, run(("guard", "success"), ("macos / install", "skipped")))
    return ok is True


@case("CANCELLED is neither green nor failed")
def _():
    ok, fails = td.classify(PR_CLEAN, run(("guard", "success"), ("linux / unit", "cancelled")))
    return ok is False and fails == []


@case("FAILURE is reported by name")
def _():
    ok, fails = td.classify(PR_CLEAN, run(("guard", "success"), ("linux / unit", "failure")))
    return ok is False and fails == ["linux / unit"]


@case("BLOCKED with all checks green is NOT mergeable-green")
def _():
    ok, _ = td.classify(PR_BLOCKED, run(("guard", "success")))
    return ok is False


@case("BLOCKED + all checks green IS owner-ready (a human's approval is what is missing)")
def _():
    r = td.readiness(PR_BLOCKED, run(("guard", "success"), ("linux / unit", "success")))
    return r["owner_ready"] is True and r["bot_green"] is False


@case("owner-ready and bot-green agree only when the state is CLEAN")
def _():
    r = td.readiness(PR_CLEAN, run(("guard", "success")))
    return r["owner_ready"] is True and r["bot_green"] is True


@case("a cancelled run makes a PR neither owner-ready nor bot-green")
def _():
    r = td.readiness(PR_BLOCKED, run(("guard", "success"), ("linux / unit", "cancelled")))
    return r["owner_ready"] is False and r["bot_green"] is False


@case("a still-running check is not green")
def _():
    runs = run(("guard", "success")) + [{"name": "linux / unit", "conclusion": None, "status": "in_progress"}]
    ok, _ = td.classify(PR_CLEAN, runs)
    return ok is False


@case("no check runs at all is not green")
def _():
    ok, _ = td.classify(PR_CLEAN, [])
    return ok is False


@case("draft and DIRTY are not green")
def _():
    return td.classify(PR_DRAFT, run(("guard", "success")))[0] is False and \
           td.classify(PR_DIRTY, run(("guard", "success")))[0] is False


@case("the five cancelled PRs are not green (regression on the reported bug)")
def _():
    five = [(f"engine-image-{i}", "cancelled") for i in range(17)] + [("guard", "success")]
    return td.classify(PR_CLEAN, run(*five))[0] is False


@case("main() emits NEW-OWNER-READY for BLOCKED+green and NEW-GREEN for CLEAN (delta lines, not snapshots)")
def _():
    """Exercise the real emit path with stubbed reads: the two readiness lines must stay distinct."""
    import tempfile

    old_state, old_open, old_conc, old_runs = td.STATE, td.open_prs, td.conclusions, td.newest_runs
    with tempfile.TemporaryDirectory() as tmp:
        td.STATE = pathlib.Path(tmp) / "s.json"
        try:
            td.open_prs = lambda: [
                {"number": 1, "headRefOid": "a" * 40, "isDraft": False,
                 "mergeable": "MERGEABLE", "mergeStateStatus": "BLOCKED"},
                {"number": 2, "headRefOid": "b" * 40, "isDraft": False,
                 "mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN"},
            ]
            td.conclusions = lambda n, sha: run(("guard", "success"))
            td.newest_runs = lambda *a, **k: {}
            td.STATE.write_text("{}")           # empty baseline: both are new
            import io
            import contextlib
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                td.main([])
            out = buf.getvalue()
            return ("NEW-OWNER-READY #1" in out
                    and "NEW-GREEN       #2" in out
                    and "approval outstanding" in out)
        finally:
            td.STATE, td.open_prs, td.conclusions, td.newest_runs = old_state, old_open, old_conc, old_runs


@case("main() is silent when the same state is re-measured (no repeat alerts)")
def _():
    import contextlib
    import io
    import tempfile

    old_state, old_open, old_conc, old_runs = td.STATE, td.open_prs, td.conclusions, td.newest_runs
    with tempfile.TemporaryDirectory() as tmp:
        td.STATE = pathlib.Path(tmp) / "s.json"
        try:
            td.open_prs = lambda: [{"number": 3, "headRefOid": "c" * 40, "isDraft": False,
                                    "mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN"}]
            td.conclusions = lambda n, sha: run(("guard", "success"))
            td.newest_runs = lambda *a, **k: {}
            td.STATE.write_text("{}")
            with contextlib.redirect_stdout(io.StringIO()):
                td.main([])                     # first run: reports
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                td.main([])                     # second run, identical: must print nothing
            return buf.getvalue() == ""
        finally:
            td.STATE, td.open_prs, td.conclusions, td.newest_runs = old_state, old_open, old_conc, old_runs


@case("is_stuck: attempt 1 is noise, attempt >= 2 is stuck, a non-cancel is never stuck")
def _():
    sha = "d" * 40
    return (td.is_stuck(sha, {sha: {"conclusion": "cancelled", "attempt": 1}}) == 0
            and td.is_stuck(sha, {sha: {"conclusion": "cancelled", "attempt": 2}}) == 2
            and td.is_stuck(sha, {sha: {"conclusion": "cancelled", "attempt": 3}}) == 3
            and td.is_stuck(sha, {sha: {"conclusion": "success", "attempt": 4}}) == 0
            and td.is_stuck(sha, {}) == 0)


@case("main() reports STUCK-CANCELLED only for a retried cancellation")
def _():
    import contextlib
    import io
    import tempfile

    old = (td.STATE, td.open_prs, td.conclusions, td.newest_runs)
    with tempfile.TemporaryDirectory() as tmp:
        td.STATE = pathlib.Path(tmp) / "s.json"
        try:
            sha_stuck, sha_first = "e" * 40, "f" * 40
            td.open_prs = lambda: [
                {"number": 4, "headRefOid": sha_stuck, "isDraft": False,
                 "mergeable": "MERGEABLE", "mergeStateStatus": "BLOCKED"},
                {"number": 5, "headRefOid": sha_first, "isDraft": False,
                 "mergeable": "MERGEABLE", "mergeStateStatus": "BLOCKED"},
            ]
            td.conclusions = lambda n, sha: run(("guard", "cancelled"))
            td.newest_runs = lambda *a, **k: {
                sha_stuck: {"conclusion": "cancelled", "attempt": 2},
                sha_first: {"conclusion": "cancelled", "attempt": 1},
            }
            td.STATE.write_text("{}")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                td.main([])
            out = buf.getvalue()
            return "STUCK-CANCELLED #4" in out and "attempt=2" in out and "#5" not in out
        finally:
            td.STATE, td.open_prs, td.conclusions, td.newest_runs = old


def main() -> int:
    failures = []
    for name, fn in CASES:
        try:
            ok = fn()
        except Exception as exc:  # noqa: BLE001 - a raising case is a failing case
            ok, name = False, f"{name}  (raised {type(exc).__name__}: {exc})"
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
        if not ok:
            failures.append(name)
    print()
    if failures:
        print(f"FAILED: {len(failures)}/{len(CASES)}")
        return 1
    print(f"OK: {len(CASES)}/{len(CASES)} — cancelled is not red, BLOCKED is not green, failure is named")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
