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

A close QUEUES what it cites (issue #521). The picker only lists `agent:implement` /
`agent:ready`, and the canonical issue a duplicate points at is usually filed without either —
so retiring the copy used to leave the real work queued nowhere: #400 was closed as a duplicate
of the unlabelled #254, and two days later #440 was closed as a duplicate of the unlabelled
#399, with the defect never once implemented. Every open, agent-label-free issue a close verdict
cites now gets `agent:implement`, so the next run implements the canonical issue instead of
closing the next copy.

Commands (stdlib only, no LLM):
  count                  PRs the bot already opened today (the cap numerator)
  dispatch [--dry]       cap -> pick one issue -> claim -> write issue.md (body + thread) + branch
  apply-verdict FILE     act on the agent's TRIAGE verdict (implement|refine|close)
  changed                did the implement step change the tree? (run inputs excluded; tree, not rc)
  open-pr                open a draft-free PR linking the issue (never merges)

The GitHub API is reached ONLY through a `gh` on PATH (or `--gh`): every test
asserts the exact argv the product builds by pointing this at a fake `gh`, the
same shape `tests/test_engine_skill_gap.py` uses for its spawn.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import bot_claims  # the shared claim protocol (scripts/bot_claims.py)

# How the cap recognises the bot's OWN PRs (issue #409). The author alone is not it:
# `make issue-bot-open-pr` runs `gh` with the owner PAT, so the PR is authored by the PAT's
# account (`asimov-agent`), never `github-actions[bot]` — counting by that login read 0 on a
# day the bot opened 7 PRs, so the 3-per-day cap never tripped. The dispatcher's branch shape
# (`agent/issue-<n>-<slug>`) is what it actually creates, so that is the primary signal; the
# author is still counted when it happens to be the bot's.
BOT_AUTHOR = "github-actions[bot]"
BOT_BRANCH_PREFIX = "agent/issue-"

#: How many PRs `gh pr list` may return before the count can be wrong (a day never reaches this).
PR_LIST_LIMIT = 200
MAX_PER_DAY = 3
SLUG_LEN = 40


#: The files the bot itself writes into the working tree it inspects. They are run inputs, never a
#: change: an earlier revision shipped `triage.md` (`TRIAGE: implement`) as the "implementation" of an
#: issue because `git add -A` staged it (issue #427), and reading the tree must not repeat that
#: (issue #428).
RUN_INPUTS = ("issue.md", "triage.md", "refine-in.md", "refine.md", "comment.md")


def changed(root: str = ".", git: str = "git") -> bool:
    """Whether the working tree carries a change that is not one of the bot's own run inputs.

    The TREE is the evidence, not the process: Hermes exits 0 even when what it reports was written
    outside this checkout (a deleted container worktree did exactly that, run 39513850754). A `git`
    that cannot read the tree is a loud SystemExit — an unreadable tree must never look like a run
    that changed something, or like a green one.
    """
    r = subprocess.run([git, "-C", root, "status", "--porcelain", "--untracked-files=all"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        # Exit 2, the same contract `scripts/require_env.py` uses: an unreadable tree is a plumbing
        # failure, not a verdict about the implementation.
        print(f"[issue-implementer] {git} status failed ({r.returncode}) in {root}: {r.stderr.strip()}",
              file=sys.stderr)
        raise SystemExit(2)
    for line in r.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        if " -> " in path:  # a rename lists both sides; the destination is what changed
            path = path.split(" -> ", 1)[1]
        if path.strip('"') in RUN_INPUTS:
            continue
        return True
    return False


def _gh(gh: str, args: list[str], token: "str | None" = None) -> str:
    """Run `gh` with the token that can perform THIS write (issue #430).

    One token for both writes is the defect: `secrets.BUMP_TOKEN` opens a PR but carries no Issues
    write, so the claim comment failed AFTER the PR already existed (run 39513850754). The caller
    passes `GH_TOKEN` for a comment and `PR_TOKEN` for `pr create`; `None` inherits the leg's own env.
    """
    env = dict(os.environ)
    if token:
        env["GH_TOKEN"] = token
    r = subprocess.run([gh, *args], capture_output=True, text=True, env=env)
    if r.returncode != 0:
        raise SystemExit(f"[issue-implementer] {gh} {' '.join(args)} failed ({r.returncode}): {r.stderr.strip()}")
    return r.stdout


#: The token that opens the PR. The PAT when the leg supplies one (so CI runs on the PR), else the
#: job's own token — never the other way round, which is what shipped a PR no bot had claimed.
def pr_token() -> "str | None":
    return os.environ.get("PR_TOKEN") or None




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


def count(gh: str, repo: str, bot: str, today: str | None = None) -> int:
    """PRs the bot already opened in the current UTC day — the cap numerator, from GitHub.

    A PR counts when it was created today AND it is the bot's: its head branch carries the
    dispatcher's `agent/issue-` prefix, or its author is `bot`. The prefix is the signal that
    works — the bot's PRs are opened with the owner PAT, so their author is the PAT's account
    (`asimov-agent`), and counting by `github-actions[bot]` returned 0 every day (issue #409).
    A human's PR is never counted, whatever its author.
    """
    d = today or _today()
    out = _gh(gh, ["pr", "list", "--repo", repo, "--state", "all", "--limit", str(PR_LIST_LIMIT),
                   "--json", "headRefName,author,createdAt"])
    n = 0
    for pr in json.loads(out or "[]") or []:
        if str(pr.get("createdAt") or "")[:10] != d:
            continue
        branch = str(pr.get("headRefName") or "")
        author = str((pr.get("author") or {}).get("login") or "")
        if branch.startswith(BOT_BRANCH_PREFIX) or author == bot:
            n += 1
    return n


def _slug(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s[:SLUG_LEN].rstrip("-") or "issue"


VERDICTS = ("implement", "refine", "close")
#: An issue carrying either label has already been decided this way and is never picked again.
DECIDED_LABELS = ("agent:refined", "agent:closed")
#: The labels that put an issue in front of the picker (`dispatch()`), in priority order.
QUEUE_LABELS = ("agent:implement", "agent:ready")
#: An issue reference in a verdict's prose: `#399`. The lookup decides whether it is an issue at all
#: (a PR number, a typo or a deleted issue answers nothing and is skipped with a line).
ISSUE_REF = re.compile(r"(?<![\w/])#(\d+)\b")

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
    """The issue WITH its comments: the thread is the specification, not just the body.

    `--json ...comments` already returns the thread; `gh` rejects `--comments` together with
    `--json` ("specify only one of --comments or --json"), which is what broke every dispatch
    until this was fixed. Ask for the comments through `--json` only.
    """
    out = _gh(gh, ["issue", "view", str(num), "--repo", repo,
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
        comments = (_thread(gh, repo, num) or {}).get("comments")
        why = bot_claims.occupied(comments, bot_claims.IMPLEMENTER,
                                  is_live=lambda rid: run_is_live(gh, rid))
        if why:
            print(f"[issue-implementer] #{num} is {why}: skipping it and taking the next one")
            continue
        gone = bot_claims.released(comments, bot_claims.IMPLEMENTER,
                                   is_live=lambda rid: run_is_live(gh, rid))
        if gone:
            print(f"[issue-implementer] #{num}: {gone}")
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
        # `gh issue view --json state` returns the CLI's own enum: "OPEN" / "CLOSED", uppercase.
        # Comparing against a lowercase literal refused every real issue ("is 'OPEN', not open"),
        # so the check is case-insensitive — and the fixtures below use the REAL values.
        if (detail.get("state") or "").strip().lower() != "open":
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
                                          datetime.now(timezone.utc),
                                          run_id=os.environ.get("GITHUB_RUN_ID"))
                 + f"\n\nbranch `{branch}`; one issue per run, at most {MAX_PER_DAY}/day, "
                   "PR left for review (never merged)."])

    print(f"[issue-implementer] picked #{num}: {title} -> {branch} (daily count {n}/{MAX_PER_DAY})")
    return {"action": "dispatch", "count": n, "issue": num, "title": title, "branch": branch}


#: The four labelled parts every bot PR body carries (AGENTS.md: the issue, the fix, the benefit, the
#: technical extension). The bot builds the body from the run's OWN material — the agent writes
#: `pr-body.md` as part of the implementation — because a fixed string is exactly what made the empty
#: PR #424 look like a description (issue #429).
PR_BODY_FILE = "pr-body.md"
PR_PARTS = ("Issue:", "Fix:", "Benefit:", "Technical:")


def pr_title(title: str, num: int) -> str:
    """The PR subject: the issue's own typed Conventional Commit, else a typed prefix. Never a fixed
    string like `issue-bot implementation` (issue #429)."""
    subject = (title or "").strip() or f"implement #{num}"
    if not re.match(r"^[a-z]+(\([\w./-]+\))?!?: ", subject):
        subject = f"feat: {subject}"
    return f"{subject} (#{num})"


def render_pr_body(text: str, num: int, diffstat: str) -> str:
    """Validate the agent's PR body and compose it with the commit's own file list.

    Refuses — loudly, naming what is missing — rather than opening a PR whose description says nothing.
    """
    problems = []
    for part in PR_PARTS:
        m = re.search(rf"(?m)^{re.escape(part)}[ \t]*(.*)$", text or "")
        if not m:
            problems.append(f"`{part}` is missing")
        elif not m.group(1).strip():
            problems.append(f"`{part}` states nothing")
    if problems:
        raise SystemExit(f"[issue-implementer] {PR_BODY_FILE} cannot become a PR body: "
                         + "; ".join(problems))
    if f"#{num}" not in text:
        raise SystemExit(f"[issue-implementer] {PR_BODY_FILE} must name the issue it implements "
                         f"(`#{num}`) in its `Issue:` part")
    stat = diffstat.strip() or "(the pushed commit's file list is unavailable)"
    return f"{text.strip()}\n\nFiles changed:\n\n```\n{stat}\n```\n\ncloses #{num}\n"


def diffstat(git: str = "git") -> str:
    """The files the pushed commit touched — read from git, never from the agent's prose."""
    r = subprocess.run([git, "show", "--stat", "--format=", "HEAD"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def open_pr(gh: str, repo: str, num: int, branch: str, title: str, body_file: str = PR_BODY_FILE,
            dry: bool = False, git: str = "git") -> str:
    """Open a draft-free PR linking the issue, built from the run's material. Never merges."""
    if not title:
        title = str(_thread(gh, repo, num).get("title") or "")
    pr_title_text = pr_title(title, num)
    path = Path(body_file)
    if not path.exists():
        raise SystemExit(f"[issue-implementer] {path} is missing: the implement step must write the "
                         f"PR body ({', '.join(PR_PARTS)}) at the repo root; refusing to open a PR "
                         f"whose description says nothing (issue #429)")
    body = render_pr_body(path.read_text(), num, diffstat(git))
    if dry:
        print(f"[issue-implementer] would open {pr_title_text} from {branch} -> main")
        print(body)
        return ""
    # The comment runs BEFORE the PR, with the issues-scoped token: a denied write then costs a
    # comment attempt, not a PR nobody has claimed, and it is the failure the log names.
    _gh(gh, ["issue", "comment", str(num), "--repo", repo, "--body",
             f"Opening the PR for `{branch}`; this bot never merges."],
        token=os.environ.get("GH_TOKEN"))
    out = _gh(gh, ["pr", "create", "--repo", repo, "--base", "main", "--head", branch,
                   "--title", pr_title_text, "--body", body],
              token=pr_token())
    url = out.strip().splitlines()[-1] if out.strip() else ""
    print(f"[issue-implementer] opened {url}")
    # `done` with the kind `pr-open`: implemented, NOT yet approved. It keeps occupying the issue -
    # nobody should start a second implementation while this PR is in review - and the marker is
    # what tells every other bot that.
    _gh(gh, ["issue", "comment", str(num), "--repo", repo, "--body",
             bot_claims.done_comment(bot_claims.IMPLEMENTER, datetime.now(timezone.utc), "pr-open")
             + f"\n\nImplemented on `{branch}`" + (f": {url}" if url else "") +
               ". Awaiting review; this bot never merges."],
        token=os.environ.get("GH_TOKEN"))
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


def cited_issues(text: str, own: int = 0) -> list[int]:
    """Every distinct `#<n>` a verdict cites, in order, never the issue being decided."""
    seen: list[int] = []
    for raw in ISSUE_REF.findall(text or ""):
        ref = int(raw)
        if ref == own or ref in seen:
            continue
        seen.append(ref)
    return seen


def _issue_meta(gh: str, repo: str, ref: int) -> dict | None:
    """`state` and `labels` for one cited reference, or None when it is not a readable issue.

    A verdict may cite a PR number, a typo, or a deleted issue; `gh issue view` answers non-zero for
    those, and that is "not an issue to queue" — never a crash after the close already happened.
    """
    r = subprocess.run([gh, "issue", "view", str(ref), "--repo", repo, "--json", "state,labels"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return json.loads(r.stdout or "{}")


def queue_canonical(gh: str, repo: str, refs: list[int], dry: bool = False) -> list[int]:
    """Put the canonical issue(s) a close verdict cites in front of the picker (issue #521).

    Without this a duplicate close retires the COPY while the canonical issue stays unlabelled, so
    the picker never lists it and the defect is never implemented: #400 pointed at #254, #440 pointed
    at #399, and neither canonical issue carried an agent label. An issue already decided
    (`agent:refined`/`agent:closed`) or already queued is left exactly as it is.
    """
    queued: list[int] = []
    for ref in refs:
        meta = _issue_meta(gh, repo, ref)
        if meta is None:
            print(f"[issue-implementer] #{ref}: not a readable issue (a PR, a typo, or gone) — not queued")
            continue
        state = (meta.get("state") or "").strip().lower()
        names = [l.get("name") for l in (meta.get("labels") or []) if l.get("name")]
        if state != "open":
            print(f"[issue-implementer] #{ref}: {state or 'unknown'} — not queued")
            continue
        decided = [n for n in names if n in DECIDED_LABELS]
        if decided:
            print(f"[issue-implementer] #{ref}: already decided ({', '.join(decided)}) — not queued")
            continue
        if any(n in QUEUE_LABELS for n in names):
            print(f"[issue-implementer] #{ref}: already queued")
            continue
        if dry:
            print(f"[issue-implementer] would queue #{ref} as the canonical issue")
        else:
            _gh(gh, ["issue", "edit", str(ref), "--repo", repo, "--add-label", "agent:implement"])
            print(f"[issue-implementer] queued #{ref} as the canonical issue (agent:implement)")
        queued.append(ref)
    return queued


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
    # What the verdict cites is the canonical work item; queue it so closing the copy cannot orphan it.
    refs = cited_issues(f"{v['reason']}\n{v['evidence']}", own=num)
    if dry:
        print(f"[issue-implementer] would close #{num} (comment + close + agent:closed)")
        queue_canonical(gh, repo, refs, dry=True)
        return v
    _gh(gh, ["issue", "comment", str(num), "--repo", repo, "--body", body])
    _gh(gh, ["issue", "close", str(num), "--repo", repo, "--reason", "not planned"])
    _gh(gh, ["issue", "edit", str(num), "--repo", repo,
             "--add-label", "agent:closed", "--remove-label", "agent:implement"])
    print(f"[issue-implementer] closed #{num} with cited evidence; labelled agent:closed")
    queue_canonical(gh, repo, refs)
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

    ch = sub.add_parser("changed")
    ch.add_argument("--root", default=".")
    ch.add_argument("--git", default="git")

    o = sub.add_parser("open-pr")
    o.add_argument("--gh", default="gh")
    o.add_argument("--repo", required=True)
    o.add_argument("--issue", type=int, required=True)
    o.add_argument("--branch", required=True)
    o.add_argument("--title", default="", help="the issue title (fetched when empty)")
    o.add_argument("--body-file", default=PR_BODY_FILE,
                   help="the agent's four-part PR body (default pr-body.md)")
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
    elif args.cmd == "changed":
        print(f"changed={'true' if changed(args.root, args.git) else 'false'}")
    elif args.cmd == "open-pr":
        url = open_pr(args.gh, args.repo, args.issue, args.branch, args.title,
                      args.body_file, args.dry)
        print(f"pr_url={url}")
    else:
        p.error("need a command: count | dispatch | apply-verdict | changed | open-pr")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
