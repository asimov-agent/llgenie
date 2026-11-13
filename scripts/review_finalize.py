#!/usr/bin/env python3
"""A verification-first, idempotent wrapper over the reviewer-finalize write-back (issue #1808).

`acceptance_writeback.py` (the #1644 seam) is deterministic: the transformation is pure and the
write is one thin `gh api PATCH`. What failed on #1806 was the CALLER — the reviewer's finalize step
replayed at the same head and (a) posted duplicate verdict evidence and (b) reported "landed" from a
read-back that had not confirmed the body matched the verdict. This file guards that caller:

* **idempotent** — before posting anything or running a write-back, count the acceptance boxes on
  the live body at the judged head sha; if every box already carries `(proven: comment=<id>)` at the
  criteria count, the verdict is already-finalized: reuse that comment id, post nothing, PATCH
  nothing (a replay is a no-op that returns the existing id).
* **verification-first** — "landed" is only reported after a read-back asserts: exactly one verdict
  comment id, the body's ticked-box count == the criteria count, and every `(proven: comment=…)` on
  the body equals that single id. A read-back that returns the body unticked (0/6) against a 6/6
  verdict reports `unconfirmed, re-read the wire` and is never re-posted.
* **head-guarded** — the write-back refuses to PATCH a body whose live head moved past the verdict's
  judged sha (a verdict describes one tree).

Pure core is stdlib-only (unit-testable on a bare host, no network). The thin `gh` wrapper mirrors
`acceptance_writeback` / `bot_verdict`: procs through `scripts/proc` where available.

Bounding: this does NOT weaken `check_issue_body` / `check-pr-acceptance` or change the #1644 seam —
it refuses instead of mutating when the read-back cannot confirm the write-back. The write itself is
still the seam's single PATCH.

Usage:
    review_finalize.py finalize --repo R --pr N --issue M --head SHA --criteria K \
        [--proven i,j] [--verdict-ref '…comment=<id>…'] [--comment-id ID] [--dry]
    review_finalize.py check --body-file F --criteria K --comment-id ID
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import acceptance_writeback as aw  # noqa: E402  the #1644 seam (pure tick + the one PATCH)
import bot_verdict  # noqa: E402  the verdict marker / dedupe-on-head vocabulary

BASE_REPO = "asimov-agent/llgenie"

#: A ticked acceptance line's inline citation, e.g. `(proven: reviewer=… comment=42 …)`.
PROVEN_COMMENT_RE = re.compile(r"\(proven:[^)]*comment=(?P<id>\d+)[^)]*\)")


def criteria_count(body: str) -> int:
    """The number of `- [ ]` / `- [x]` items under `## Acceptance criteria` (lenient heading)."""
    return len(aw.acceptance_items(body or ""))


def cited_ids(body: str) -> set[str]:
    """Every `comment=<id>` cited across all ticked acceptance lines, in the verified shape."""
    ids = set()
    for line in aw.acceptance_items(body or ""):
        m = aw.CHECKBOX_RE.match(line)
        if not m or m.group("state").lower() != "x":
            continue
        c = PROVEN_COMMENT_RE.search(line)
        if c:
            ids.add(c.group("id"))
    return ids


def _ticked_items(body: str) -> list[str]:
    """Acceptance lines currently ticked (`- [x]`)."""
    out = []
    for i in aw.acceptance_items(body or ""):
        m = aw.CHECKBOX_RE.match(i)
        if m and m.group("state").lower() == "x":
            out.append(i)
    return out


def is_finalized(body: str, criteria: int, comment_id: str) -> bool:
    """True when the write-back already happened: exactly `criteria` boxes ticked AND all cite `comment_id`.

    Idempotence pre-check. `criteria` == 0 is a contradiction (no boxes to prove) → False, and a
    criteria mismatch (too few ticked, or a body that grew/shrunk) is also False so a replay on a
    changed body re-verifies rather than trusting a stale count.
    """
    if criteria <= 0:
        return False
    ticked = _ticked_items(body)
    if len(ticked) != criteria:
        return False
    ids = {m.group("id") for i in ticked for m in [PROVEN_COMMENT_RE.search(i)] if m}
    return ids == {str(comment_id)}


def readback_ok(body: str, criteria: int, comment_id: str) -> tuple[bool, str]:
    """Assert the body that POST-write-back read-back describes the verdict, before "landed".

    ok=True  ⇔ the TICKED-box count == `criteria` and every `(proven: comment=…)` == `comment_id`.
    A body reading 0 ticked against a 6/6 verdict is NEVER ok and is never re-posted.
    """
    try:
        ticked = _ticked_items(body)
    except aw.BodyError:
        return False, "unconfirmed, re-read the wire"
    if len(ticked) != criteria:
        # 0-ticked against a >0 criteria verdict is the #1806 mis-read — never "landed".
        return False, "unconfirmed, re-read the wire"
    ids = {m.group("id") for i in ticked for m in [PROVEN_COMMENT_RE.search(i)] if m}
    if ids != {str(comment_id)}:
        return False, f"unconfirmed, re-read the wire (citations {sorted(ids)} != {comment_id})"
    return True, "landed"


def head_moved(live_head: str, judged_head: str) -> bool:
    """A verdict binds one tree: a live head different from the judged head invalidates write-back."""
    return (live_head or "").strip().lower() != (judged_head or "").strip().lower()


def _gh(gh: str, args: list[str]) -> str:
    r = __import__("subprocess").run([gh, *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"[review-finalize] {gh} {' '.join(args)} failed ({r.returncode}): {r.stderr.strip()}")
    return r.stdout


def _fetch_body(gh: str, repo: str, issue: int) -> str:
    out = _gh(gh, ["issue", "view", str(issue), "--repo", repo, "--json", "body"])
    return json.loads(out)["body"]


def _live_head(gh: str, repo: str, pr: int) -> str:
    out = _gh(gh, ["pr", "view", str(pr), "--repo", repo, "--json", "headRefOid"])
    return (json.loads(out).get("headRefOid") or "").lower()


#: `run=<id>` citations inside a verdict-ref (#2288): finalize checks their live conclusion at the
#: judged head through the same `gh` seam BEFORE `aw.tick_acceptance` stamps any tick.
RUN_REF = re.compile(r"\brun\s*=\s*(\d+)")


def _run_state(gh: str, repo: str, run_id: int) -> "tuple[str, str, str] | None":
    """Live (status, conclusion, head_sha) of a cited run through the seam's `gh`; None if unreadable."""
    try:
        out = _gh(gh, ["api", f"repos/{repo}/actions/runs/{run_id}",
                       "--jq", "[.status, .conclusion, .head_sha] | @tsv"])
    except SystemExit:
        return None
    parts = (out or "").strip().split("\t")
    if not parts or not parts[0].strip() or parts[0].strip() == "null":
        return None
    return (parts[0].strip(),
            (parts[1] if len(parts) > 1 else "").strip(),
            (parts[2] if len(parts) > 2 else "").strip())


def verdict_ref_runs_ok(gh: str, repo: str, ref: str, head: str) -> tuple[bool, str]:
    """True only when every `run=<id>` cited in `ref` concluded `success` at the judged head (#2288).

    A cited run the seam cannot read, a run that ended failure/cancelled/timed_out, or a green run
    belonging to a different head each refuse the write-back: a tick may not cite evidence that did
    not prove the very head the tick claims. A verdict-ref citing no run (reviewer/comment + head sha
    form) has nothing to look up and passes to the seam's grammar floor.
    """
    for m in RUN_REF.finditer(str(ref or "")):
        rid = int(m.group(1))
        st = _run_state(gh, repo, rid)
        if st is None:
            return False, (f"run {rid} is unreadable via `gh api repos/{repo}/actions/runs/{rid}` — "
                           "a verdict-ref may not cite what the seam cannot read (issue #2288)")
        status, conclusion, run_head = st
        if conclusion.lower() != "success" or status.lower() != "completed":
            return False, (f"run {rid} concluded `{conclusion or status}` — only a completed `success` "
                           "run proves a tick (issue #2288)")
        if head and run_head and run_head.lower() != head:
            return False, (f"run {rid} belongs to head {run_head[:12]}, not the judged head "
                           f"{head[:12]} (issue #2288)")
    return True, ""


def finalize(gh: str, repo: str, pr: int, issue: int, head: str, criteria: int,
             proven: set[int], verdict_ref: str, comment_id: str,
             dry: bool = False) -> int:
    """The guarded finalize step. Returns 0 landed/idempotent, 2 refused, 1 unconfirmed."""
    head = (head or "").strip().lower()
    live = _live_head(gh, repo, pr)
    if head_moved(live, judged_head=head):
        print(f"[review-finalize] refusing: PR #{pr} head moved to {live[:12]} (judged {head[:12]}) — "
              f"write-back would PATCH a superseded head; re-read the wire", file=sys.stderr)
        return 2

    body = _fetch_body(gh, repo, issue)
    if is_finalized(body, criteria, comment_id):
        print(f"[review-finalize] already finalized: #{issue} carries "
              f"{criteria}/{criteria} ticked, all (proven: comment={comment_id}); "
              f"reusing existing comment, no post, no PATCH (idempotent no-op)")
        return 0

    # #2288 verification-first: every `run=<id>` in the verdict-ref must have concluded GREEN at the
    # judged head before any tick is computed. Unreadable or red lookups return 2 with NO PATCH made.
    ok_runs, why = verdict_ref_runs_ok(gh, repo, verdict_ref or "", head)
    if not ok_runs:
        print(f"[review-finalize] refusing: {why}; no write-back issued", file=sys.stderr)
        return 2

    # The seam's one write (tick + PATCH). No weakening: `proven` is explicit, ref required.
    out = aw.tick_acceptance(body, proven, verdict_ref)
    if dry:
        print(f"[review-finalize] would PATCH #{issue} write-back (dry)")
        return 0
    if out == body:
        print("[review-finalize] no-op: tick produced byte-identical body; nothing to PATCH")
        return 0
    aw._write(gh, repo, issue, out)  # the single PATCH (seam #1644)

    # Read-back BEFORE reporting landed.
    read = _fetch_body(gh, repo, issue)
    ok, msg = readback_ok(read, criteria, comment_id)
    if ok:
        # Exactly one CITED comment id on the body, at the criteria count.
        print(f"[review-finalize] {msg}: #{issue} {criteria}/{criteria} ticked, "
              f"all (proven: comment={comment_id}))")
        return 0
    print(f"[review-finalize] {msg}; do NOT re-post — reread the #1806-style wire for the "
          f"single verdict comment", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="review_finalize", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("finalize")
    f.add_argument("--repo", default=BASE_REPO)
    f.add_argument("--pr", type=int, required=True)
    f.add_argument("--issue", type=int, required=True)
    f.add_argument("--head", required=True, help="the FULL 40-hex sha this verdict judged")
    f.add_argument("--criteria", type=int, required=True, help="the acceptance criteria count")
    f.add_argument("--proven", default="", help="comma-separated 1-based item positions to prove")
    f.add_argument("--verdict-ref", default="", help="reviewer + review id + head sha + run id")
    f.add_argument("--comment-id", default="", help="the single verdict comment id to cite")
    f.add_argument("--gh", default="gh")
    f.add_argument("--dry", action="store_true")

    c = sub.add_parser("check")
    c.add_argument("--body-file", required=True)
    c.add_argument("--criteria", type=int, required=True)
    c.add_argument("--comment-id", required=True)

    args = p.parse_args(argv)

    if args.cmd == "check":
        body = Path(args.body_file).read_text()
        ok, msg = readback_ok(body, args.criteria, args.comment_id)
        print(f"[review-finalize] check: {msg}")
        return 0 if ok else 1

    comment_id = (args.comment_id or "").strip()
    if not comment_id:
        print("[review-finalize] refusing: --comment-id must name the single verdict comment to cite",
              file=sys.stderr)
        return 2
    proven = set()
    for tok in (args.proven or "").split(","):
        tok = tok.strip()
        if tok:
            proven.add(int(tok))
    return finalize(args.gh, args.repo, args.pr, args.issue, args.head, args.criteria,
                    proven, args.verdict_ref, comment_id, args.dry)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
