#!/usr/bin/env python3
"""Delta-only merge-readiness tally for asimov-agent/llgenie.

Reports exactly two facts, and nothing else:

  NEW-GREEN    <n> @<sha>   a PR became green-and-mergeable
  NEW-FAILURE  <n> @<sha>   a PR gained a genuine FAILURE conclusion (not cancelled)

Empty stdout means no delta — which is what a `--no-agent` cron job needs to stay silent.
A cancelled run is neither a pass nor a verdict: it means a newer run superseded it, so it is
reported as neither green nor failed. That distinction is the whole reason this script exists;
`gh pr checks` renders `cancelled` as "fail", which reads as red when it only means "not yet".

State: <script dir>/tally-state.json (atomic rewrite). `--reset` re-baselines silently.
Exit: always 0 — this is a reporter, not a gate.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
from datetime import datetime, timezone

REPO = "asimov-agent/llgenie"
HERE = pathlib.Path(__file__).resolve().parent
# STATE and OUTBOX must NOT live beside __file__: for a script shipped into the repo tree that is
# the checkout itself, so running the reporter dirties tracked-adjacent files (measured: the
# versioned copy put tally-state.json and tally-outbox.log next to itself under agents/). Resolve
# to a runtime state dir, overridable per deployment. The profile copy and the repo copy then stay
# behaviourally identical without sharing files.
_STATE_DIR = pathlib.Path(os.environ.get("LLGENIE_STATE_DIR",
                                        str(pathlib.Path.home() / ".local/state/llgenie")))
_STATE_DIR.mkdir(parents=True, exist_ok=True)
STATE_DIR = _STATE_DIR
STATE = _STATE_DIR / "tally-state.json"
# Record of the lines this reporter has emitted that are still ACTIONABLE. A `--no-agent` job's
# delivery can fail with `queue_full`; the state file is already advanced by then, so without this
# the delta exists nowhere. Read it to recover a lost alarm instead of re-deriving one.
#
# It is NOT append-only, and that was a defect: measured on this host the file held 8 lines with
# the SAME delta recorded twice 48 seconds apart, plus entries for PRs that had already merged.
# A file that only grows is a replay machine -- a late `queue_full` drain re-delivers an hours-old
# "NEW-FAILURE #932" naming a PR that merged two hours earlier, which is exactly the confusion this
# reporter exists to prevent. `merge_outbox` therefore prunes closed PRs and collapses duplicates.
OUTBOX = _STATE_DIR / "tally-outbox.log"
OUTBOX_MAX = 200

PASS = {"success", "skipped", "neutral"}

_STAMP_RE = re.compile(r"\s*\[measured [^\]]*\]\s*$")
_PR_RE = re.compile(r"#(\d+)")


def _signature(line: str) -> str:
    """The line minus its measurement stamp: two runs reporting one condition are the same fact."""
    return _STAMP_RE.sub("", line.strip())


def merge_outbox(existing: list[str], fresh: list[str], open_numbers: set[int],
                 limit: int = OUTBOX_MAX) -> list[str]:
    """The outbox after appending `fresh`, holding only lines that are still actionable.

    Three rules, each a measured defect:
      1. a line naming a PR that is no longer open is dropped -- re-delivering it later names a
         merged PR as a fresh failure;
      2. a line whose signature (minus the stamp) already exists is not added again; the NEWER
         stamp is kept, so the file states the latest measurement of each condition;
      3. the file is capped, because it is a recovery record, not a history.
    """
    out: list[str] = []
    seen: dict[str, int] = {}
    for line in [*existing, *fresh]:
        if not line.strip():
            continue
        m = _PR_RE.search(line)
        if m and int(m.group(1)) not in open_numbers:
            continue
        sig = _signature(line)
        if sig in seen:
            out[seen[sig]] = line          # same condition, newer measurement replaces it
            continue
        seen[sig] = len(out)
        out.append(line)
    # `out[-limit:]` with limit == 0 is `out[0:]` -- the whole list. A cap that returns everything
    # at zero is not a cap; guard it explicitly.
    return out[-limit:] if limit > 0 else []


def gh(*args: str) -> str:
    out = subprocess.run(["gh", *args], capture_output=True, text=True)
    if out.returncode != 0:
        # A failed read must never look like "no change".
        print(f"TALLY-ERROR: gh rc={out.returncode} ({out.stderr.strip()[:120]})")
        raise SystemExit(0)
    return out.stdout


def open_prs() -> list[dict]:
    raw = gh("pr", "list", "--repo", REPO, "--state", "open", "--limit", "100",
             "--json", "number,headRefOid,isDraft,mergeable,mergeStateStatus")
    return json.loads(raw or "[]")


def conclusions(number: int, sha: str) -> list[dict]:
    raw = gh("api", f"repos/{REPO}/commits/{sha}/check-runs?per_page=100")
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return []
    return [{"name": r.get("name"), "conclusion": r.get("conclusion"), "status": r.get("status")}
            for r in data.get("check_runs", [])]


def newest_runs(shas: list[str]) -> dict[str, dict]:
    """sha -> the newest workflow run on that exact commit.

    Queried per commit (`gh run list --commit`), not from the repo-wide run list: after a capacity
    sweep the top of that list is dominated by newer runs and an older PR's retry silently falls out of
    the window — measured: with `--limit 100` mapped over 100 runs, #815's `ce503ecb` (attempt 2,
    cancelled) was absent, so the stuck state read as 0.
    """
    out: dict[str, dict] = {}
    for sha in shas:
        raw = gh("run", "list", "--repo", REPO, "--commit", sha, "--limit", "1",
                 "--json", "databaseId,status,conclusion,attempt,headSha")
        try:
            runs = json.loads(raw or "[]")
        except json.JSONDecodeError:
            runs = []
        if runs:
            r = runs[0]
            out[sha] = {"id": r.get("databaseId"), "status": r.get("status"),
                        "conclusion": r.get("conclusion"), "attempt": r.get("attempt") or 1}
    return out


def is_stuck(sha: str, runs_by_sha: dict[str, dict]) -> int:
    """The attempt number when a PR cannot reach a verdict, else 0.

    A first cancellation is ordinary: `cancel-in-progress`, a re-push, or a capacity sweep. A SECOND
    (`attempt >= 2`) means the retry was cancelled too, so the PR will never produce a check verdict
    however long anyone waits. That is the silent hazard — nothing alerts on "still cancelled".
    """
    r = runs_by_sha.get(sha)
    if not r or r.get("conclusion") != "cancelled":
        return 0
    attempt = r.get("attempt") or 1
    return attempt if attempt >= 2 else 0


def readiness(pr: dict, runs: list[dict]) -> dict:
    """The two readiness facts, kept apart because they answer different questions.

    `owner_ready`  every check on this head has settled green (nothing pending, cancelled or failed),
                   the PR is non-draft and `MERGEABLE`. The owner's approval is what is missing — for a
                   human this PR is *ready to merge*, and calling it "not green" would be misleading.
    `bot_green`    the stricter auto-merge rule from the repo's AGENTS.md: `mergeStateStatus == CLEAN`.
                   A bot may only merge this; `BLOCKED`/`REVIEW_REQUIRED` is not CLEAN even when every
                   check passed, so a PR can be owner-ready and not bot-green at the same time.
    """
    failed = sorted({r["name"] or "?" for r in runs if r["conclusion"] == "failure"})
    settled = len([r for r in runs if r["status"] == "completed"]) == len(runs)
    cancelled = any(r["conclusion"] == "cancelled" for r in runs)
    ok_checks = bool(runs) and settled and not cancelled and not failed
    eligible = not pr.get("isDraft") and pr.get("mergeable") == "MERGEABLE"
    owner_ready = bool(ok_checks and eligible)
    bot_green = bool(owner_ready and pr.get("mergeStateStatus") == "CLEAN")
    return {"owner_ready": owner_ready, "bot_green": bot_green, "failures": failed}


def classify(pr: dict, runs: list[dict]) -> tuple[bool, list[str]]:
    """(is_green_and_mergeable, failing_check_names) — the strict bot rule. See readiness()."""
    r = readiness(pr, runs)
    return r["bot_green"], r["failures"]


def selftest() -> int:
    """Prove merge_outbox on the states actually measured on this host. `--selftest` runs it."""
    # Measured: the same delta appended twice, 48 seconds apart.
    dup = [
        "NEW-FAILURE     #1077 @c8e47261  linux / unit  [measured 23:16:29Z]",
        "NEW-FAILURE     #1077 @c8e47261  linux / unit  [measured 23:17:17Z]",
    ]
    # Measured: an entry for a PR that had already merged.
    closed = "NEW-FAILURE     #932 @0a710920  linux / unit  [measured 19:19:00Z]"
    fresh = "NEW-FAILURE     #1117 @3a2357f6  linux / lint  [measured 00:49:56Z]"

    out = merge_outbox(dup, [], {1077})
    assert len(out) == 1, f"duplicate delta kept twice: {out}"
    assert "23:17:17Z" in out[0], f"the NEWER measurement must win: {out[0]}"

    out = merge_outbox([closed], [], {1117})
    assert out == [], f"a line naming a closed PR must be dropped: {out}"

    out = merge_outbox([dup[0]], [fresh], {1077, 1117})
    assert len(out) == 2 and out[-1] == fresh, out

    out = merge_outbox([f"NEW-FAILURE #1 @a i  [measured 00:00:00Z]"], [], {1}, limit=0)
    assert out == [], f"the cap must apply: {out}"

    # A line with no PR number must survive: not everything is per-PR.
    out = merge_outbox(["STRAY LINE"], [], set())
    assert out == ["STRAY LINE"], out
    print("selftest OK: dedupe keeps the newer stamp, closed PRs dropped, fresh appended, cap applies")
    return 0


def main(argv: list[str]) -> int:
    if argv and argv[0] == "--selftest":
        return selftest()
    prs = open_prs()
    shas = [p["headRefOid"] for p in prs if p.get("headRefOid")]
    runs_by_sha = newest_runs(shas)
    now: dict[str, dict] = {}
    for pr in sorted(prs, key=lambda p: int(p["number"])):
        num, sha = int(pr["number"]), pr["headRefOid"]
        runs = conclusions(num, sha)
        r = readiness(pr, runs)
        now[str(num)] = {"sha": sha, "owner_ready": r["owner_ready"],
                         "bot_green": r["bot_green"], "failures": r["failures"],
                         "stuck_attempt": is_stuck(sha, runs_by_sha)}

    if "--reset" in argv:
        STATE.write_text(json.dumps(now, indent=2, sort_keys=True) + "\n")
        print(f"TALLY-BASELINE: {len(now)} open, "
              f"{sum(1 for v in now.values() if v['bot_green'])} bot-green, "
              f"{sum(1 for v in now.values() if v['owner_ready'] and not v['bot_green'])} owner-ready, "
              f"{sum(1 for v in now.values() if v['failures'])} with failures, "
              f"{sum(1 for v in now.values() if v['stuck_attempt'])} stuck-cancelled")
        return 0

    try:
        before = json.loads(STATE.read_text())
    except (OSError, json.JSONDecodeError):
        before = {}

    lines: list[str] = []
    # Stamp the measurement time on every reported line. A `--no-agent` job's delivery can be
    # delayed (measured: `last_delivery_error: queue_full` re-delivered an hours-old delta whose
    # PRs had since MERGED, which reads exactly like a fresh alarm and cost a full re-measure to
    # disprove). A timestamp makes staleness self-evident instead of inferable.
    stamp = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
    for num, cur in sorted(now.items(), key=lambda kv: int(kv[0])):
        was = before.get(num, {})
        same_sha = was.get("sha") == cur["sha"]
        if cur["bot_green"] and not (was.get("bot_green") and same_sha):
            lines.append(f"NEW-GREEN       #{num} @{cur['sha'][:8]}  (mergeable by a bot: CLEAN)  [measured {stamp}]")
        elif cur["owner_ready"] and not cur["bot_green"] and not (was.get("owner_ready") and same_sha):
            # Every check is settled and green but the merge state is not CLEAN: a human's approval is
            # what is missing. Saying "not green" here would be false for the person who can merge it.
            lines.append(f"NEW-OWNER-READY #{num} @{cur['sha'][:8]}  (checks green, approval outstanding)  [measured {stamp}]")
        # A new head sha is a fresh measurement, so its failures are new information even when the
        # same check name failed on the previous commit.
        known = (was.get("failures") or []) if same_sha else []
        gained = [f for f in cur["failures"] if f not in known]
        if gained:
            lines.append(f"NEW-FAILURE     #{num} @{cur['sha'][:8]}  {'; '.join(gained[:4])}  [measured {stamp}]")
        # A retry that was cancelled too: no verdict is coming, however long anyone waits.
        if cur["stuck_attempt"] and cur["stuck_attempt"] != (was.get("stuck_attempt") or 0):
            lines.append(f"STUCK-CANCELLED #{num} @{cur['sha'][:8]}  attempt={cur['stuck_attempt']}  [measured {stamp}]")

    tmp = STATE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(now, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, STATE)

    # Persist the delta BEFORE returning, because state has already advanced: if the delivery
    # fails (`last_delivery_error: queue_full` is measured on this job), an in-memory delta is
    # lost permanently — the next run diffs against the new state and reports nothing, so the
    # alarm becomes both unrepeatable and stale. The outbox makes a lost delivery recoverable by
    # reading the file instead of re-deriving it.
    #
    # Rewrite UNCONDITIONALLY, not only when this run produced a line. Gating the write on `lines`
    # meant a quiet tick never pruned: measured, the file kept 8 lines — duplicates and entries for
    # merged PRs — for hours, and a late `queue_full` drain of it named #932 as a new failure two
    # hours after #932 merged. Pruning on every run is what keeps the file actionable.
    existing = OUTBOX.read_text().splitlines() if OUTBOX.exists() else []
    merged = merge_outbox(existing, lines, {p["number"] for p in prs})
    if merged != existing:
        tmp_out = OUTBOX.with_suffix(".log.tmp")
        tmp_out.write_text("".join(ln + "\n" for ln in merged))
        os.replace(tmp_out, OUTBOX)
    if lines:
        print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
