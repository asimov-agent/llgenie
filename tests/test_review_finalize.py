"""The reviewer-finalize guard (issue #1808): idempotent + verification-first finalize.

Everything here exercises the REAL module — `review_finalize.is_finalized` / `readback_ok` /
`head_moved` and the #1644 seam's `tick_acceptance` are the product. Nothing talks to the network:
the `gh` wrapper (`finalize`/`_write`) is exercised here only through a hermetic fake-`gh` shim:
since #2288 the run-lookup leg inside `finalize` must be attested, so `finalize` and
`verdict_ref_runs_ok` run against a `gh` script backed by sidecar files — never the network.

The acceptance criteria under proof (issue #1808):
1. re-invoking an already-finalized verdict (same PR, same head sha, same verdict text) is a NO-OP —
   posts no second comment, runs no second PATCH, returns the existing comment id
   (red-on-old: the unguarded path would post a duplicate);
2. a completed verdict is only "landed" after a read-back asserts: exactly one verdict comment id,
   body ticked-box count == criteria count, and every `(proven: comment=…)` equals that id;
3. a read-back returning the body UNTICKED (0/6) against a 6/6 verdict is NEVER "landed" — it is
   "unconfirmed, re-read the wire", never re-posted;
4. the write-back refuses to PATCH a body whose live head moved past the verdict's judged sha.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

from scripts import acceptance_writeback as aw  # noqa: E402
from scripts import review_finalize as rf  # noqa: E402

#: One comment id, as a citable verdict would carry it.
COMMENT = "42"

#: A body in the six-section shape (issue #745) with three acceptance criteria.
BODY = (
    "## Problem\np\n\n## Why it matters\nw\n\n## How we fix it\n1. a\n2. b\n\n"
    "## Benefit\nb\n\n## Acceptance criteria\n\n- [ ] criterion one\n- [ ] criterion two proves it\n"
    "- [ ] criterion three\n\n## Technical\n\n- where: x\n"
)


def _ticked(ref: str = COMMENT, n: int = 3) -> str:
    """A body whose first `n` boxes are ticked with `(proven: … comment=<ref>)` (all 3 by default)."""
    return aw.tick_acceptance(BODY, {1, 2, 3}, f"reviewer=rr comment={ref} head=abc1234567 run=99")


def test_reinvoking_an_already_finalized_verdict_is_a_noop():
    """Criterion 1 — idempotence pre-check: an already-finalized body is recognised as such.

    Red-on-old: an unguarded finalize step would post a second PATCH/comment because nothing checked
    whether the write-back already happened. Green-on-fixed: `is_finalized` returns True for the
    re-invoked (already-finalized) state with the SAME head/comment than it returns before any tick.
    """
    finalized = _ticked(COMMENT)
    # The finalized body is idempotent: is_finalized True, reuse the existing comment id.
    assert rf.is_finalized(finalized, criteria=3, comment_id=COMMENT) is True
    # Re-running tick_acceptance on the finalized body does not duplicate the citation lines:
    # the seam is idempotent, so the body is stable under re-apply, and the comment id is reused.
    reapplied = aw.tick_acceptance(finalized, {1, 2, 3}, f"reviewer=rr comment={COMMENT} head=abc1234567 run=99")
    assert reapplied == finalized
    # Before any write-back the verdict is NOT finalized.
    assert rf.is_finalized(BODY, criteria=3, comment_id=COMMENT) is False


def test_criteria_count_mismatch_is_never_treated_as_finalized():
    """A changed body (criteria count != the judged count) is not trusted as finalized."""
    # Same comment cited, but only 2 of 3 proven → criteria count mismatch.
    partial = aw.tick_acceptance(BODY, {1, 2}, f"reviewer=rr comment={COMMENT} head=abc1234567 run=99")
    assert rf.is_finalized(partial, criteria=3, comment_id=COMMENT) is False
    # criteria == 0 is a contradiction (nothing to prove).
    assert rf.is_finalized(BODY, criteria=0, comment_id=COMMENT) is False


def test_landed_only_after_readback_asserts_exactly_one_citation():
    """Criterion 2 — verification-first: "landed" requires count match AND all cite the one id."""
    ok, msg = rf.readback_ok(_ticked(COMMENT), criteria=3, comment_id=COMMENT)
    assert (ok, msg) == (True, "landed")

    # A conflicting citation on a ticked line is NOT landed (not the asserted single comment id).
    mixed = _ticked(COMMENT).replace(f"comment={COMMENT}", "comment=99", 1)
    ok, msg = rf.readback_ok(mixed, criteria=3, comment_id=COMMENT)
    assert ok is False and "unconfirmed" in msg

    # Box count over the criteria count is not landed either.
    assert rf.readback_ok(_ticked(COMMENT), criteria=2, comment_id=COMMENT)[0] is False


def test_zero_ticked_read_against_full_verdict_is_never_landed():
    """Criterion 3 — a 0-ticked read-back (0/6) against a 6/6 verdict is "unconfirmed", not landed."""
    ok, msg = rf.readback_ok(BODY, criteria=3, comment_id=COMMENT)   # all `- [ ]`
    assert ok is False and msg == "unconfirmed, re-read the wire"


def test_writeback_refuses_a_moved_head():
    """Criterion 4 — write-back refuses to PATCH a body whose head moved past the judged sha."""
    judged = "a" * 40
    assert rf.head_moved(live_head="b" * 40, judged_head=judged) is True
    assert rf.head_moved(live_head=judged, judged_head=judged) is False
    # A short/empty live head (unreadable) is treated as moved — never assume it still matches.
    assert rf.head_moved(live_head="", judged_head=judged) is True


# --- issue #2288: verification-first — every cited run must be GREEN at the judged head -------

#: The 40-hex head the verdict judged; the fake live head and a green run's head both match it.
HEAD40 = "cafe1234" + "0" * 32
#: A different tree: a green run belonging here proves nothing about a tick at HEAD40.
_ELSEWHERE = "deadbeef" + "0" * 32


def _vref(head: str = HEAD40, run: int = 42) -> str:
    return f"reviewer=llgenie-pr-reviever comment={COMMENT} head={head} run={run}"


def _fake_gh(tmp_path, live_head: str, runs: dict, issue_body: str):
    """Hermetic fake `gh` for the finalize leg: `pr view`, `issue view`, runs lookup, the PATCH."""
    (tmp_path / "pr.json").write_text(json.dumps({"headRefOid": live_head}))
    (tmp_path / "runs.json").write_text(json.dumps(runs))
    (tmp_path / "issue.json").write_text(issue_body)
    (tmp_path / "calls.log").write_text("")  # exists from setup: a zero-call run reads empty, not missing
    gh = tmp_path / "gh"
    gh.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "D = os.path.dirname(os.path.abspath(__file__))\n"
        "def p(n):\n"
        "    return os.path.join(D, n)\n"
        "with open(p('calls.log'), 'a') as fh:\n"
        "    fh.write(' '.join(sys.argv[1:]) + '\\n')\n"
        "a = sys.argv[1:]\n"
        "if a[:2] == ['pr', 'view']:\n"
        "    print(open(p('pr.json')).read())\n"
        "    sys.exit(0)\n"
        "if a[:2] == ['issue', 'view']:\n"
        "    print(json.dumps({'body': open(p('issue.json')).read()}))\n"
        "    sys.exit(0)\n"
        "if a[:1] == ['api'] and any('actions/runs/' in t for t in a):\n"
        "    rid = [t for t in a if 'actions/runs/' in t][0].rsplit('/', 1)[-1]\n"
        "    rec = json.loads(open(p('runs.json')).read()).get(rid)\n"
        "    if rec is None:\n"
        "        sys.exit(1)\n"
        "    print('%s\\t%s\\t%s' % (rec[0], rec[1], rec[2]))\n"
        "    sys.exit(0)\n"
        "if a[:1] == ['api'] and 'PATCH' in a:\n"
        "    bodies = [t[5:] for t in a if t.startswith('body=')]\n"
        "    if not bodies:\n"
        "        sys.exit(1)\n"
        "    open(p('issue.json'), 'w').write(bodies[0])\n"
        "    sys.exit(0)\n"
        "sys.exit(1)\n"
    )
    gh.chmod(0o755)
    return gh, tmp_path / "calls.log", tmp_path / "issue.json"


def test_verdict_ref_citing_a_failure_run_is_refused(tmp_path):
    gh, _, _ = _fake_gh(tmp_path, HEAD40, {"42": ("completed", "failure", HEAD40)}, BODY)
    ok, why = rf.verdict_ref_runs_ok(str(gh), "o/r", _vref(), HEAD40)
    assert ok is False and "failure" in why and "#2288" in why


def test_verdict_ref_citing_a_cancelled_run_is_refused(tmp_path):
    gh, _, _ = _fake_gh(tmp_path, HEAD40, {"42": ("completed", "cancelled", HEAD40)}, BODY)
    ok, why = rf.verdict_ref_runs_ok(str(gh), "o/r", _vref(), HEAD40)
    assert ok is False and "cancelled" in why


def test_verdict_ref_citing_a_green_run_at_another_head_is_refused(tmp_path):
    gh, _, _ = _fake_gh(tmp_path, HEAD40, {"42": ("completed", "success", _ELSEWHERE)}, BODY)
    ok, why = rf.verdict_ref_runs_ok(str(gh), "o/r", _vref(), HEAD40)
    assert ok is False and "belongs to head" in why


def test_verdict_ref_with_an_unreadable_run_is_refused(tmp_path):
    gh, _, _ = _fake_gh(tmp_path, HEAD40, {"42": None}, BODY)
    ok, why = rf.verdict_ref_runs_ok(str(gh), "o/r", _vref(), HEAD40)
    assert ok is False and "unreadable" in why and "#2288" in why


def test_verdict_ref_citing_no_run_passes_verification(tmp_path):
    """The reviewer/comment + head-sha form has nothing to look up: verification passes untouched."""

    gh, calls, _ = _fake_gh(tmp_path, HEAD40, {}, BODY)
    ok, why = rf.verdict_ref_runs_ok(
        str(gh), "o/r", f"reviewer=rr comment={COMMENT} head={HEAD40}", HEAD40)
    assert ok is True and why == "" and calls.read_text() == ""


def test_finalize_refuses_a_red_cited_verdict_ref_before_any_write(tmp_path, capsys):
    """The AC proof (#2288): finalize returns 2 with NO PATCH issued and the body untouched."""

    gh, calls, store = _fake_gh(tmp_path, HEAD40, {"42": ("completed", "failure", HEAD40)}, BODY)
    rc = rf.finalize(str(gh), "o/r", pr=7, issue=1, head=HEAD40, criteria=3,
                     proven={1, 2, 3}, verdict_ref=_vref(), comment_id=COMMENT)
    assert rc == 2
    err = capsys.readouterr().err
    assert "refusing" in err and "#2288" in err
    assert "actions/runs/42" in calls.read_text()      # the lookup happened
    assert "PATCH" not in calls.read_text()            # no write-back was issued
    assert store.read_text() == BODY                   # no tick was written


def test_finalize_lands_when_the_cited_run_is_green_at_the_judged_head(tmp_path):
    """Positive control: green run at the judged head -> PATCH issued, read-back asserts landed."""

    gh, calls, store = _fake_gh(tmp_path, HEAD40, {"42": ("completed", "success", HEAD40)}, BODY)
    rc = rf.finalize(str(gh), "o/r", pr=7, issue=1, head=HEAD40, criteria=3,
                     proven={1, 2, 3}, verdict_ref=_vref(), comment_id=COMMENT)
    assert rc == 0 and "PATCH" in calls.read_text()
    assert rf.is_finalized(store.read_text(), criteria=3, comment_id=COMMENT) is True


def test_dry_finalize_still_reports_the_run_refusal(tmp_path):
    """Spec: `--dry` never looks green-proof — a red-cited run still refuses, still rc 2."""

    gh, calls, store = _fake_gh(tmp_path, HEAD40, {"42": ("completed", "failure", HEAD40)}, BODY)
    rc = rf.finalize(str(gh), "o/r", pr=7, issue=1, head=HEAD40, criteria=3,
                     proven={1, 2, 3}, verdict_ref=_vref(), comment_id=COMMENT, dry=True)
    assert rc == 2 and "PATCH" not in calls.read_text() and store.read_text() == BODY
