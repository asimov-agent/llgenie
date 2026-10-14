"""The issue-implementer's deterministic dispatcher (issue #248).

Scope: there is no bot that **implements an issue** — a red PR gets repaired
(#222), open PRs get kept rebased (#246), the container is specified (#238) —
but the first PR is still written by hand. This is the unit-testable core: pick
exactly ONE issue, at most 3 per UTC day, one at a time, each left as a
draft-free reviewable PR that is **never merged**. The LLM step (Hermes reading
`issue.md` + AGENTS.md and implementing) is `make implement-issue` in the
workflow; this dispatcher only decides *what* to implement and opens the PR.

The bot reads the issue **and its whole comment thread** before deciding, because the
thread is where an issue is usually specified: a body that says "add --foo" with a fifth
comment that says "only for CPU builds" is a different issue. It then decides ONE of:

  implement   actionable as written       -> branch, gates, reviewable PR (never merged)
  refine      real ambiguity left         -> ONE comment with an implementable restatement,
                                             the `agent:refined` label, no PR that run
  close       no longer makes sense       -> comment the reason WITH cited evidence, close it

Closing requires evidence: a close whose verdict carries no `EVIDENCE:` block is refused
loudly, because "hard" or "vague" is `refine`, and "already done / superseded / duplicate /
not a code change" is what closing is for. An issue labelled `agent:refined` or
`agent:closed` is never picked again, so neither verdict can loop.

Commands (stdlib only, no LLM):
  count                  PRs the bot already opened today (the cap numerator)
  dispatch [--dry]       cap -> pick one issue -> claim -> write issue.md (body + thread) + branch
  apply-verdict FILE     act on the agent's TRIAGE verdict (implement|refine|close)
  open-pr                open a draft-free PR linking the issue (never merges)

The GitHub API is reached ONLY through a `gh` on PATH (or `--gh`): every test
asserts the exact argv the product builds by pointing this at a fake `gh`, the
same shape `tests/test_engine_skill_gap.py` uses for its spawn.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import bot_claims  # the shared claim protocol (scripts/bot_claims.py)

# Author the PRs count as from the bot; a human's work is never counted toward the cap.
BOT_AUTHOR = "github-actions[bot]"
MAX_PER_DAY = 3
SLUG_LEN = 40


def _gh(gh: str, args: list[str]) -> str:
    r = subprocess.run([gh, *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"[issue-implementer] {gh} {' '.join(args)} failed ({r.returncode}): {r.stderr.strip()}")
    return r.stdout


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def count(gh: str, repo: str, bot: str, today: str | None = None) -> int:
    """PRs the bot already opened in the current UTC day — the cap numerator, from GitHub."""
    d = today or _today()
    out = _gh(gh, ["search", "prs", "--repo", repo, "--author", bot,
                   "--created", f">={d} 00:00Z", "--json", "number", "--limit", "100"])
    items = json.loads(out or "[]")
    return len(items or [])


def _slug(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s[:SLUG_LEN].rstrip("-") or "issue"


VERDICTS = ("implement", "refine", "close")
#: An issue carrying either label has already been decided this way and is never picked again.
DECIDED_LABELS = ("agent:refined", "agent:closed")

#: The instruction block inside issue.md. The verdict format is machine-read by
#: `apply-verdict`, so the agent is told the exact lines to emit rather than asked for prose.
DECISION_BLOCK = """## Decide first, then act

Read the issue text AND every comment above (oldest first). The thread is the issue's real
specification: a comment that narrows, reverses or answers the body wins over the body. Then
choose exactly ONE verdict and put it in `triage.md` at the repo root, in this shape:

    TRIAGE: implement

    TRIAGE: refine
    REFINED:
    <a restatement that is implementable: acceptance criteria explicit, the open question named>
    REASON: <one line: what is still undecided>

    TRIAGE: close
    EVIDENCE: <what you checked — a merged PR/commit that already does it, the issue that
              supersedes or duplicates it, or why this is not a change this repo can make>
    REASON: <one line>

Rules for the verdict:

- `implement` — the body plus thread are actionable now. Then implement exactly the acceptance
  criteria they agree on; do not widen the scope.
- `refine` — a real decision is still open or the acceptance criteria are missing, so any
  implementation would be a guess. Post nothing yourself: write the `REFINED:` block and stop.
  Do NOT open a PR on a refine.
- `close` — the issue no longer makes sense: already implemented, superseded, a duplicate, or
  not a code change this repo can make. `EVIDENCE:` is REQUIRED and must name what you checked;
  a close without it is refused. Never close because an issue is hard, large or vague — that is
  `refine`, or a human's call.
"""


def render_issue_md(detail: dict, comments: list[dict]) -> str:
    """The agent's input: the issue, its thread in order, and the decision instruction."""
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
        lines += ["_No comments: the body is the whole specification._", ""]
    for c in comments:
        who = (c.get("author") or {}).get("login") or "?"
        when = c.get("createdAt") or ""
        lines += [f"### {who} · {when}", "", (c.get("body") or "").rstrip(), ""]
    lines += [DECISION_BLOCK]
    return "\n".join(lines)


def _issue_list(gh: str, repo: str, label: str) -> list[dict]:
    out = _gh(gh, ["issue", "list", "--repo", repo, "--state", "open", "--label", label,
                   "--limit", "100", "--json", "number,title,createdAt,labels"])
    return json.loads(out or "[]")


def _thread(gh: str, repo: str, num: int) -> dict:
    """The issue WITH its comments: the thread is the specification, not just the body."""
    out = _gh(gh, ["issue", "view", str(num), "--repo", repo, "--comments",
                   "--json", "number,title,body,state,author,labels,comments"])
    return json.loads(out or "{}")


def _pick(cands: list[dict]) -> dict | None:
    """The oldest candidate that has not already been decided (refined or closed)."""
    for issue in sorted(cands, key=lambda i: i.get("createdAt") or ""):
        names = [l.get("name") for l in (issue.get("labels") or []) if l.get("name")]
        if any(n in DECIDED_LABELS for n in names):
            continue
        return issue
    return None


def _pick_free(gh: str, repo: str, cands: list[dict]) -> dict | None:
    """The oldest candidate nobody else is on.

    A bot that is going to refine or implement an issue says so ON THE ISSUE, and any recent
    comment that has not been concluded by a `done` comment means someone is on it - so this run
    skips THAT issue and takes the next one in the list (scripts/bot_claims.py). The implementer's
    own `pr-open` marker counts too, so an implemented issue is never implemented twice.
    """
    for issue in sorted(cands, key=lambda i: i.get("createdAt") or ""):
        names = [l.get("name") for l in (issue.get("labels") or []) if l.get("name")]
        if any(n in DECIDED_LABELS for n in names):
            continue
        num = issue["number"]
        why = bot_claims.occupied((_thread(gh, repo, num) or {}).get("comments"),
                                  bot_claims.IMPLEMENTER)
        if why:
            print(f"[issue-implementer] #{num} is {why}: skipping it and taking the next one")
            continue
        return issue
    return None


def dispatch(gh: str, repo: str, bot: str, dry: bool = False, today: str | None = None,
             out_path: Path = Path("issue.md"), force_issue: int | None = None) -> dict:
    """Apply the cap, pick ONE issue, claim it, and emit the branch + issue.md."""
    d = today or _today()
    n = count(gh, repo, bot, d)
    if n >= MAX_PER_DAY:
        print(f"[issue-implementer] cap reached: {n}/{MAX_PER_DAY} today, next issue tomorrow")
        return {"action": "cap", "count": n, "issue": None}

    if force_issue is not None:
        # A workflow_dispatch pins dispatch to the explicit issue (owner-only path).
        detail = _thread(gh, repo, force_issue)
        if detail.get("state") != "open":
            print(f"[issue-implementer] forced issue #{force_issue} is '{detail.get('state')}', not open")
            return {"action": "none", "count": n, "issue": None}
        title = detail["title"]
        num = detail["number"]
    else:
        # Labeled `agent:implement` first (oldest label first); else the oldest `agent:ready`.
        issue = _pick_free(gh, repo, _issue_list(gh, repo, "agent:implement"))
        if issue is None:
            issue = _pick_free(gh, repo, _issue_list(gh, repo, "agent:ready"))
        if issue is None:
            print("[issue-implementer] no issue labelled agent:implement or agent:ready left "
                  "(decided issues carry agent:refined / agent:closed and are skipped)")
            return {"action": "none", "count": n, "issue": None}
        num = issue["number"]
        title = issue["title"]
        detail = _thread(gh, repo, num)

    branch = f"agent/issue-{num}-{_slug(title)}"
    comments = list(detail.get("comments") or [])
    out_path.write_text(render_issue_md(detail | {"title": detail.get("title") or title}, comments))
    print(f"[issue-implementer] issue.md: body + {len(comments)} comment(s) + the decision block")

    if not dry:
        _gh(gh, ["issue", "comment", str(num), "--repo", repo, "--body",
                 bot_claims.claim_comment(bot_claims.IMPLEMENTER, "implement",
                                          datetime.now(timezone.utc))
                 + f"\n\nbranch `{branch}`; one issue per run, at most {MAX_PER_DAY}/day, "
                   "PR left for review (never merged)."])

    print(f"[issue-implementer] picked #{num}: {title} -> {branch} (daily count {n}/{MAX_PER_DAY})")
    return {"action": "dispatch", "count": n, "issue": num, "title": title, "branch": branch}


def open_pr(gh: str, repo: str, num: int, branch: str, title: str, body: str,
            wants: str, dry: bool = False) -> str:
    """Open a draft-free PR linking the issue. Never merges; reports the URL."""
    pr_title = f"{title} (implements #{num})"
    if dry:
        print(f"[issue-implementer] would open #implements{num} from {branch} -> main")
        return ""
    out = _gh(gh, ["pr", "create", "--repo", repo, "--base", "main", "--head", branch,
                   "--title", pr_title, "--body", f"{body}\n\ncloses #{num}\n{wants}"])
    url = out.strip().splitlines()[-1] if out.strip() else ""
    print(f"[issue-implementer] opened {url}")
    # `done` with the kind `pr-open`: implemented, NOT yet approved. It keeps occupying the issue -
    # nobody should start a second implementation while this PR is in review - and the marker is
    # what tells every other bot that.
    _gh(gh, ["issue", "comment", str(num), "--repo", repo, "--body",
             bot_claims.done_comment(bot_claims.IMPLEMENTER, datetime.now(timezone.utc), "pr-open")
             + f"\n\nImplemented on `{branch}`" + (f": {url}" if url else "") +
               ". Awaiting review; this bot never merges."])
    return url


def parse_verdict(text: str) -> dict:
    """The agent's machine-readable verdict: TRIAGE plus optional REFINED/EVIDENCE/REASON."""
    m = re.search(r"(?m)^\s*TRIAGE:\s*(\w+)\s*$", text or "")
    if not m:
        raise SystemExit("[issue-implementer] no `TRIAGE:` verdict in the agent's output; "
                         "expected `TRIAGE: implement|refine|close`")
    verdict = m.group(1).lower()
    if verdict not in VERDICTS:
        raise SystemExit(f"[issue-implementer] unknown verdict {verdict!r}; expected one of "
                         f"{' | '.join(VERDICTS)}")

    def block(name: str) -> str:
        b = re.search(rf"(?ms)^\s*{name}:\s*(.*?)(?=^\s*[A-Z][A-Z_]+:\s|\Z)", text)
        return b.group(1).strip() if b else ""

    return {"verdict": verdict, "refined": block("REFINED"), "evidence": block("EVIDENCE"),
            "reason": block("REASON").splitlines()[0].strip() if block("REASON") else ""}


def apply_verdict(gh: str, repo: str, num: int, text: str, dry: bool = False) -> dict:
    """Act on the verdict: nothing (implement), one comment + label (refine), or comment +
    close + label (close). A close without EVIDENCE is refused: that rule is the whole point."""
    v = parse_verdict(text)
    if v["verdict"] == "implement":
        print(f"[issue-implementer] verdict: implement #{num} — the existing path runs")
        return v

    if v["verdict"] == "refine":
        if not v["refined"]:
            raise SystemExit("[issue-implementer] verdict refine carries no `REFINED:` block; "
                             "a refine must restate the issue, not just say it is unclear")
        body = ("**Refined specification** (issue-implementer, from the whole thread)\n\n"
                f"{v['refined']}\n")
        if v["reason"]:
            body += f"\n**Still open:** {v['reason']}\n"
        if dry:
            print(f"[issue-implementer] would refine #{num} (comment + agent:refined, no PR)")
            return v
        _gh(gh, ["issue", "comment", str(num), "--repo", repo, "--body", body])
        _gh(gh, ["issue", "edit", str(num), "--repo", repo, "--add-label", "agent:refined"])
        print(f"[issue-implementer] refined #{num}: one comment, labelled agent:refined, no PR")
        return v

    # close: evidence or nothing
    if not v["evidence"]:
        raise SystemExit("[issue-implementer] refusing to close without an `EVIDENCE:` block — "
                         "'hard', 'large' or 'vague' is a refine, and already-done / superseded / "
                         "duplicate / not-a-code-change is what closing is for")
    body = f"Closing this issue. {v['reason'] or ''}".rstrip() + f"\n\n**Evidence**\n\n{v['evidence']}\n"
    if dry:
        print(f"[issue-implementer] would close #{num} (comment + close + agent:closed)")
        return v
    _gh(gh, ["issue", "comment", str(num), "--repo", repo, "--body", body])
    _gh(gh, ["issue", "close", str(num), "--repo", repo, "--reason", "not planned"])
    _gh(gh, ["issue", "edit", str(num), "--repo", repo,
             "--add-label", "agent:closed", "--remove-label", "agent:implement"])
    print(f"[issue-implementer] closed #{num} with cited evidence; labelled agent:closed")
    return v


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="issue_implementer")
    sub = p.add_subparsers(dest="cmd")

    c = sub.add_parser("count")
    c.add_argument("--gh", default="gh")
    c.add_argument("--repo", required=True)
    c.add_argument("--bot", default=BOT_AUTHOR)
    c.add_argument("--today", default=None)

    d = sub.add_parser("dispatch")
    d.add_argument("--gh", default="gh")
    d.add_argument("--repo", required=True)
    d.add_argument("--bot", default=BOT_AUTHOR)
    d.add_argument("--today", default=None)
    d.add_argument("--dry", action="store_true")
    d.add_argument("--out", default="issue.md")
    d.add_argument("--force-issue", type=int, default=None)

    a = sub.add_parser("apply-verdict")
    a.add_argument("verdict_file")
    a.add_argument("--gh", default="gh")
    a.add_argument("--repo", required=True)
    a.add_argument("--issue", type=int, required=True)
    a.add_argument("--dry", action="store_true")

    o = sub.add_parser("open-pr")
    o.add_argument("--gh", default="gh")
    o.add_argument("--repo", required=True)
    o.add_argument("--issue", type=int, required=True)
    o.add_argument("--branch", required=True)
    o.add_argument("--title", default="issue-bot implementation")
    o.add_argument("--body", default="")
    o.add_argument("--wants", default="Verification notes land on the PR as CI runs it.")
    o.add_argument("--dry", action="store_true")

    args = p.parse_args(argv)
    if args.cmd == "count":
        print(count(args.gh, args.repo, args.bot, args.today))
    elif args.cmd == "dispatch":
        res = dispatch(args.gh, args.repo, args.bot, args.dry, args.today,
                       Path(args.out), force_issue=args.force_issue)
        # Machine-readable lines the workflow parses after the human log line.
        print(f"action={res.get('action')}")
        if res.get("issue"):
            print(f"issue={res['issue']}")
            print(f"branch={res['branch']}")
    elif args.cmd == "apply-verdict":
        text = Path(args.verdict_file).read_text() if Path(args.verdict_file).exists() else ""
        v = apply_verdict(args.gh, args.repo, args.issue, text, args.dry)
        print(f"verdict={v['verdict']}")
    elif args.cmd == "open-pr":
        url = open_pr(args.gh, args.repo, args.issue, args.branch, args.title, args.body,
                      args.wants, args.dry)
        print(f"pr_url={url}")
    else:
        p.error("need a command: count | dispatch | apply-verdict | open-pr")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
