"""The issue-refiner's deterministic core (issue #263): review an issue, leave it implementable.

The implementer (#248/#261) decides implement/refine/close, but only for the ONE issue it is
about to implement. Nothing makes the *backlog of not-yet-implemented issues* implementable
ahead of time — missing acceptance criteria, scope settled in an old comment, duplicates —
and that is discovered by an agent that has already spent a branch and a run.

This bot exists for exactly that, on an hourly cadence: it reviews ONE issue per run and opens NO
PR at all. The only thing it refuses to do is race the implementer: while an issue is *waiting*
for the implementer (labelled `agent:implement`/`agent:ready` with no PR yet) it yields and says
so, and it never picks an issue the implementer has claimed or that a PR already links.

Its outcome is ONE comment plus the `agent:refined` label, and that label is what stops it from
reviewing the same issue run after run. It never rewrites an issue body (a human owns that
text), never decides an open question for a human, and never merges anything.

Commands (stdlib only, no LLM):
  count                  refines posted today (this bot's own daily budget)
  pick [--dry]           the oldest eligible issue -> write refine-in.md (yields while the
                         implementer has queued work; runs hourly, one issue per run)
  apply FILE             post ONE comment from the review (refine.md) + label `agent:refined`

The GitHub API is reached ONLY through a `gh` on PATH (or `--gh`): every test asserts the exact
argv the product builds by pointing this at a fake `gh` (the shape tests/test_issue_implementer.py
uses for the implementer).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import bot_claims

#: The bot's own PRs are the implementer's; this bot's work is counted by its LABEL instead.
BOT_AUTHOR = "github-actions[bot]"
MAX_PER_DAY = 3
REFINED_LABEL = "agent:refined"
#: Issues the refiner must never touch: already decided, or claimed for implementation.
SKIP_LABELS = (REFINED_LABEL, "agent:closed", "agent:implement", "agent:ready")

REVIEW_BLOCK = """## Review it, do not implement it

Read the issue, its WHOLE comment thread (oldest first), `AGENTS.md`, and the `scripts/`/OpenSpec
surfaces it would touch. Then write `refine.md` at the repo root (NEXT TO this file) with ONE
verdict:

    REFINE: refined
    RESTATED:
    <an implementable restatement: acceptance criteria as a checklist, scope in/out, the
     files/surfaces it touches, and any open question named as a QUESTION for a human>
    REASON: <one line: what was missing>

    REFINE: already-clear
    REASON: <one line: why nothing needs adding>

Rules:

- `refined` — you must supply `RESTATED:`. State acceptance criteria a reviewer could tick off,
  the scope boundary, and where the change lands. If the thread leaves a decision open, NAMED it
  as a question in the restatement; do not decide it for a human.
- `already-clear` — the issue is already implementable: say why in one line. This is recorded so
  the issue is not reviewed again.
- Do NOT implement anything, do NOT create a branch, do NOT push, do NOT open a PR, do NOT edit
  the issue body or any other file. The only output is `refine.md`.
"""


def _gh(gh: str, args: list[str]) -> str:
    r = subprocess.run([gh, *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"[issue-refiner] {gh} {' '.join(args)} failed ({r.returncode}): {r.stderr.strip()}")
    return r.stdout




#: Cache of the liveness probe: one lookup per run id per process (scripts/bot_claims.py, #291).
_LIVE: dict[int, "bool | None"] = {}


def run_is_live(gh: str, run_id: int) -> "bool | None":
    """Whether the run that posted a claim is still going (cached).

    A cancelled/preempted run must not hold a subject for the rest of the claim's TTL (#291): the
    marker carries the run, and this asks GitHub about it. Unknown stays unknown - it never
    releases a claim.
    """
    if run_id not in _LIVE:
        _LIVE[run_id] = bot_claims.run_is_live(lambda args: _gh(gh, args), run_id)
    return _LIVE[run_id]


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def count(gh: str, repo: str, today: str | None = None) -> int:
    """Issues this bot refined in the current UTC day, from the label it applies."""
    d = today or _today()
    out = _gh(gh, ["issue", "list", "--repo", repo, "--state", "all", "--label", REFINED_LABEL,
                   "--search", f"updated:>={d}", "--limit", "100", "--json", "number"])
    return len(json.loads(out or "[]") or [])


def _labels(issue: dict) -> list[str]:
    return [l.get("name") for l in (issue.get("labels") or []) if l.get("name")]


def _has_bot_pr(gh: str, repo: str, num: int) -> bool:
    """True when a PR from the bot links this issue — i.e. it is already being implemented."""
    out = _gh(gh, ["issue", "view", str(num), "--repo", repo,
                   "--json", "closedByPullRequestsReferences"])
    refs = json.loads(out or "{}").get("closedByPullRequestsReferences") or []
    return bool(refs)


def implementer_has_work(gh: str, repo: str) -> tuple[bool, str]:
    """The one thing this bot must not do is race the implementer for an issue.

    Hourly cadence, one issue per run: it yields only while an issue is *waiting* for the
    implementer — labelled `agent:implement`/`agent:ready` and not yet implemented (no PR links
    it). An issue that already has a PR is not waiting for anyone, so it does not block the
    refiner; that is what keeps the hourly runs useful instead of quiet.
    """
    for label in ("agent:implement", "agent:ready"):
        out = _gh(gh, ["issue", "list", "--repo", repo, "--state", "open", "--label", label,
                       "--limit", "10", "--json", "number"])
        waiting = [i["number"] for i in (json.loads(out or "[]") or [])]
        for num in waiting[:5]:
            if not _has_bot_pr(gh, repo, num):
                return True, f"#{num} is labelled {label} and has no implementation yet"
    return False, "nothing is waiting for the implementer"


def _candidates(gh: str, repo: str) -> list[dict]:
    out = _gh(gh, ["issue", "list", "--repo", repo, "--state", "open", "--limit", "100",
                   "--json", "number,title,createdAt,labels"])
    issues = json.loads(out or "[]") or []
    return sorted(issues, key=lambda i: i.get("createdAt") or "")


def _thread(gh: str, repo: str, num: int) -> dict:
    """The issue WITH its comments - where the claim protocol lives (scripts/bot_claims.py)."""
    return json.loads(_gh(gh, ["issue", "view", str(num), "--repo", repo, "--comments",
                               "--json", "number,title,body,state,author,labels,comments"]) or "{}")


def pick(gh: str, repo: str, bot: str = BOT_AUTHOR, dry: bool = False,
         out_path: Path = Path("refine-in.md"), today: str | None = None) -> dict:
    """Spare capacity -> the oldest open issue that is not decided, claimed or already PR'd."""
    n = count(gh, repo, today)
    if n >= MAX_PER_DAY:
        print(f"[issue-refiner] own cap reached: {n}/{MAX_PER_DAY} refines today")
        return {"action": "cap", "issue": None}
    busy, why = implementer_has_work(gh, repo)
    if busy:
        print(f"[issue-refiner] yielding to the implementer: {why}")
        return {"action": "busy", "issue": None}

    chosen = None
    for issue in _candidates(gh, repo):
        if any(l in SKIP_LABELS for l in _labels(issue)):
            continue
        if _has_bot_pr(gh, repo, issue["number"]):
            continue
        comments = (_thread(gh, repo, issue["number"]) or {}).get("comments")
        why = bot_claims.occupied(comments, bot_claims.REFINER,
                                  is_live=lambda rid: run_is_live(gh, rid))
        if why:
            print(f"[issue-refiner] #{issue['number']} is {why}: leaving it to that bot")
            continue
        gone = bot_claims.released(comments, bot_claims.REFINER,
                                   is_live=lambda rid: run_is_live(gh, rid))
        if gone:
            print(f"[issue-refiner] #{issue['number']}: {gone}")
        chosen = issue
        break
    if chosen is None:
        print("[issue-refiner] no eligible issue: every open one is decided, claimed or already implemented")
        return {"action": "none", "issue": None}

    detail = _thread(gh, repo, chosen["number"])
    comments = list(detail.get("comments") or [])
    if not dry:
        _gh(gh, ["issue", "comment", str(chosen["number"]), "--repo", repo, "--body",
                 bot_claims.claim_comment(bot_claims.REFINER, "refine",
                                          dt.datetime.now(dt.timezone.utc),
                                          run_id=os.environ.get("GITHUB_RUN_ID"))])
        print(f"[issue-refiner] claimed #{chosen['number']} to refine it, before the agent runs")
    out_path.write_text(render(detail, comments))
    print(f"[issue-refiner] picked #{chosen['number']}: {chosen.get('title')} "
          f"(body + {len(comments)} comment(s)); {out_path.name} written")
    return {"action": "pick", "issue": chosen["number"], "title": chosen.get("title")}


def render(detail: dict, comments: list[dict]) -> str:
    """The agent's input for a REVIEW: the issue, its thread, and the review instruction."""
    lines = [f"# {detail.get('title') or ''}", ""]
    meta = [f"state: {detail.get('state') or '?'}"]
    author = (detail.get("author") or {}).get("login")
    if author:
        meta.append(f"opened by: {author}")
    labels = [l.get("name") for l in (detail.get("labels") or []) if l.get("name")]
    if labels:
        meta.append("labels: " + ", ".join(labels))
    lines += [" · ".join(meta), "", "## Issue body", "", (detail.get("body") or "").rstrip(), ""]
    lines += [f"## Comments (oldest first, {len(comments)})", ""]
    if not comments:
        lines += ["_No comments: the body is everything a reader has._", ""]
    for c in comments:
        who = (c.get("author") or {}).get("login") or "?"
        lines += [f"### {who} · {c.get('createdAt') or ''}", "", (c.get("body") or "").rstrip(), ""]
    lines += [REVIEW_BLOCK]
    return "\n".join(lines)


def parse_review(text: str) -> dict:
    """The agent's machine-readable review: REFINE plus optional RESTATED/REASON."""
    m = re.search(r"(?m)^\s*REFINE:\s*([\w-]+)\s*$", text or "")
    if not m:
        raise SystemExit("[issue-refiner] no `REFINE:` verdict in the agent's output; "
                         "expected `REFINE: refined` or `REFINE: already-clear`")
    verdict = m.group(1).lower()
    if verdict not in ("refined", "already-clear"):
        raise SystemExit(f"[issue-refiner] unknown verdict {verdict!r}; expected refined | already-clear")

    def block(name: str) -> str:
        b = re.search(rf"(?ms)^\s*{name}:\s*(.*?)(?=^\s*[A-Z][A-Z_]+:\s|\Z)", text)
        return b.group(1).strip() if b else ""

    return {"verdict": verdict, "restated": block("RESTATED"),
            "reason": block("REASON").splitlines()[0].strip() if block("REASON") else ""}


def apply_review(gh: str, repo: str, num: int, text: str, dry: bool = False) -> dict:
    """ONE comment plus the label. No branch, no PR, no body edit — the argv tests pin that."""
    v = parse_review(text)
    if v["verdict"] == "refined" and not v["restated"]:
        raise SystemExit("[issue-refiner] verdict `refined` carries no `RESTATED:` block; "
                         "a refinement must restate the issue, not just say it is unclear")
    if v["verdict"] == "refined":
        body = ("**Refined specification** (issue-refiner, from the whole thread)\n\n"
                f"{v['restated']}\n")
    else:
        body = ("**Reviewed: already implementable** (issue-refiner)\n\n"
                f"{v['reason'] or 'Acceptance criteria are explicit; nothing to add.'}\n")
    # The review IS the done comment: its marker releases the claim this run opened, so the other
    # bot is free to take the issue as soon as the review lands (and the issue does not stay
    # occupied until the claim expires).
    body = body.rstrip() + "\n\n" + bot_claims.done_comment(
        bot_claims.REFINER, dt.datetime.now(dt.timezone.utc), "refined")
    if dry:
        print(f"[issue-refiner] would comment on #{num} and label {REFINED_LABEL} (no PR)")
        return v
    _gh(gh, ["issue", "comment", str(num), "--repo", repo, "--body", body])
    _gh(gh, ["issue", "edit", str(num), "--repo", repo, "--add-label", REFINED_LABEL])
    print(f"[issue-refiner] #{num}: one comment, labelled {REFINED_LABEL}, no PR")
    return v


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="issue_refiner")
    sub = p.add_subparsers(dest="cmd")

    c = sub.add_parser("count")
    c.add_argument("--gh", default="gh")
    c.add_argument("--repo", required=True)
    c.add_argument("--today", default=None)

    k = sub.add_parser("pick")
    k.add_argument("--gh", default="gh")
    k.add_argument("--repo", required=True)
    k.add_argument("--bot", default=BOT_AUTHOR)
    k.add_argument("--today", default=None)
    k.add_argument("--out", default="refine-in.md")
    k.add_argument("--dry", action="store_true")

    a = sub.add_parser("apply")
    a.add_argument("review_file")
    a.add_argument("--gh", default="gh")
    a.add_argument("--repo", required=True)
    a.add_argument("--issue", type=int, required=True)
    a.add_argument("--dry", action="store_true")

    args = p.parse_args(argv)
    if args.cmd == "count":
        print(count(args.gh, args.repo, args.today))
    elif args.cmd == "pick":
        res = pick(args.gh, args.repo, args.bot, args.dry, Path(args.out), args.today)
        print(f"action={res.get('action')}")
        if res.get("issue"):
            print(f"issue={res['issue']}")
    elif args.cmd == "apply":
        text = Path(args.review_file).read_text() if Path(args.review_file).exists() else ""
        v = apply_review(args.gh, args.repo, args.issue, text, args.dry)
        print(f"verdict={v['verdict']}")
    else:
        p.error("need a command: count | pick | apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
