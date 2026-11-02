#!/usr/bin/env python3
"""Deterministic state fingerprint of the open PRs on asimov-agent/llgenie.

Used as a cron `monitor` script: identical output to the previous tick skips the
agent run entirely, so this must never print a wall-clock timestamp or anything
else that changes for no reason. One block per PR, sorted by number, with:
number, head sha, base, reviewDecision, mergeStateStatus, labels, the check
buckets (failure / pending counts), the comment count, and the latest review
(who wrote it, its state, its date — that last one is the *review's* date, not
"now", so it is stable between ticks).

`--selftest` renders fixed fixtures and asserts the WARN branch, so the hold
guard can be proven without waiting for a real rogue approval.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

REPO = "asimov-agent/llgenie"
#: The local checkout `--changes-index` measures against. Kept as a constant so the test suite can
#: monkeypatch `git` instead of needing a clone (the monitor runs where the repo may not be).
REPO_PATH = "/home/asimov/repository/git/llgenie"
FIELDS = ("number,title,headRefOid,baseRefName,isDraft,reviewDecision,"
          "mergeStateStatus,mergeable,labels,statusCheckRollup")
HOLD = "do-not-merge"


def gh(*args: str) -> str:
    p = subprocess.run(["gh", *args], capture_output=True, text=True)
    if p.returncode != 0:
        print(f"ERROR gh {' '.join(args)}: {p.stderr.strip()[:300]}", file=sys.stderr)
        raise SystemExit(1)
    return p.stdout


def usable_run_id(run_id: str) -> bool:
    """True only for a numeric Actions run id. ``null`` from an empty jq row is not one."""
    return bool(run_id) and run_id.isdigit()


#: Conclusions that mean the check really failed. `CANCELLED` is NOT one: a manual or
#: superseded cancellation cancels the whole run and shows every sibling job as cancelled,
#: so bucketing it as a failure makes a green PR read as red on the board (the watch reported
#: "fail=11" on PRs whose only red rows were cancellations). It is tracked separately so it
#: still shows, and so a stale cancelled run is visible as "needs a fresh run".
FAILED_CONCLUSIONS = {"FAILURE", "TIMED_OUT", "STARTUP_FAILURE", "ACTION_REQUIRED"}
CANCELLED_CONCLUSIONS = {"CANCELLED"}


def buckets(pr: dict) -> tuple[list[str], list[str], list[str]]:
    """(failing, cancelled, not-yet-completed) check names — the check view, not the run view."""
    rolls = pr.get("statusCheckRollup") or []
    failed = sorted(c["name"] for c in rolls
                    if (c.get("conclusion") or "").upper() in FAILED_CONCLUSIONS)
    cancelled = sorted(c["name"] for c in rolls
                       if (c.get("conclusion") or "").upper() in CANCELLED_CONCLUSIONS)
    pending = sorted(c["name"] for c in rolls
                     if (c.get("status") or "").upper() != "COMPLETED")
    return failed, cancelled, pending


def runs_at(sha: str, limit: int = 4) -> list[dict]:
    """Every workflow run at this head sha (newest first) — the ids a verdict must cite.

    A verdict cites a run id at the head, and one head carries a run per workflow (`CI`, `scope`,
    `docs`), so all of them are kept rather than just the newest: a `do-not-merge` verdict that
    names `CI` but not the `docs` run beside it invites the reader to assume only one ran.
    """
    if not sha:
        return []
    # The API endpoint, not `gh run list --commit`: the latter lags a fresh push by minutes and
    # reports "no runs" for a sha that already has three, which reads as "CI never triggered" and
    # invites a bogus empty commit to fake a run (measured on #835 at 52e951eb).
    data = json.loads(gh("api", f"repos/{REPO}/actions/runs?head_sha={sha}&per_page={limit}"))
    return [{"databaseId": r.get("id"), "workflowName": r.get("name"),
             "status": r.get("status"), "conclusion": r.get("conclusion")}
            for r in (data.get("workflow_runs") or [])]


def run_fields(runs: list[dict] | None) -> str:
    """`runs=<wf>:<id>:<status>/<conclusion>|…` for the per-PR line, or `runs=none`.

    The workflow name is cut at its ` — ` subtitle (`scope` rather than
    `scope — which CI jobs a change selects (issue #824)`) so one PR still fits on one line; the
    full name is still in `gh run view`.
    """
    if not runs:
        return "runs=none"
    return "runs=" + "|".join(
        f"{(r.get('workflowName') or r.get('name') or '?').split(' — ')[0]}:"
        f"{r.get('databaseId', '?')}:{r.get('status', '?')}/{r.get('conclusion') or '-'}"
        for r in runs)


def latest_ci_run(runs: list[dict] | None) -> dict | None:
    """The newest `CI` run in `runs`, or the newest run at all when none is named CI."""
    if not runs:
        return None
    for r in runs:
        if (r.get('workflowName') or r.get('name') or '').startswith('CI'):
            return r
    return runs[0]


def no_verdict_line(runs: list[dict] | None) -> str | None:
    """A `CANCELLED` CI run at the head is *no verdict*, not a red and not a green.

    `concurrency: cancel-in-progress` keys on the branch, so every push kills the run in flight for
    that ref: 21 of 31 open PRs sat with a cancelled latest run at their head and no reviewable
    conclusion. The board must say that out loud, because a cancelled row renders like calm.
    """
    ci = latest_ci_run(runs)
    if not ci or (ci.get('conclusion') or '').lower() != 'cancelled':
        return None
    return ("    NO VERDICT: the CI run at this head ended cancelled — a cancelled run is neither "
            "red nor green; it needs a fresh run at a frozen head, not a fix")


def render(pr: dict, ncomments: int, reviews: list[dict],
           runs: list[dict] | None = None) -> list[str]:
    """The stable lines for one PR. Pure: no gh, no clock."""
    failed, cancelled, pending = buckets(pr)
    label_names = {l["name"] for l in pr["labels"]}
    last = reviews[-1] if reviews else {}
    who = (last.get("author") or {}).get("login", "-")
    out = [
        f"#{pr['number']} head={pr['headRefOid'][:12]} base={pr['baseRefName']} "
        f"draft={pr['isDraft']} review={pr['reviewDecision'] or '-'} "
        f"merge={pr['mergeStateStatus']}/{pr['mergeable']} "
        f"labels={','.join(sorted(label_names)) or '-'} "
        f"fail={len(failed)} cancel={len(cancelled)} pending={len(pending)} comments={ncomments} "
        f"reviewer={who}:{last.get('state', '-')}@{(last.get('submittedAt') or '-')[:10]} "
        # The run ids to cite in a verdict, with their states:
        # `runs=CI:40721356864:queued/-|scope:40721356874:completed/success|…`.
        + run_fields(runs),
    ]
    # The incident this guards: an agent submits an APPROVED review under the owner's
    # token while a reviewer hold is set, which reads as the owner's own approval and
    # hands the PR to auto_merge.py. Flag it so the next tick wakes on it.
    if (pr.get("reviewDecision") or "") == "APPROVED" and HOLD not in label_names:
        out.append(f"    WARN: APPROVED with no {HOLD} hold by {who} — verify a human made it")
    out += [f"    FAILING: {n}" for n in failed]
    # A red PR nobody has held is the thing a reviewer sweep exists to find: it can merge the
    # moment CI goes green again, and no human has said anything about it (#838 was exactly this).
    if failed and HOLD not in label_names:
        out.append(f"    ACTION: failing and unheld by {who} — review it or place {HOLD} with a reason")
    # Named separately from FAILING: a cancelled job is not a verdict, and a PR whose only red
    # rows are cancellations needs a fresh run, not a fix.
    out += [f"    CANCELLED: {n}" for n in cancelled]
    nv = no_verdict_line(runs)
    if nv:
        out.append(nv)
    out += [f"    PENDING: {n}" for n in pending]
    # A PR based on something other than `main` gets NO workflow at all (`ci.yml`, `scope.yml` and
    # `docs.yml` gate `pull_request` on `branches: ["main"]`), so it reports zero checks — which
    # reads on a board exactly like "nothing wrong". #836 sat like that, stacked on a closed
    # branch: 0 checks, `reviewDecision` that cannot even be evaluated, and 178 lines of tests no
    # gate had ever run. Say it out loud instead of printing a calm row.
    n_checks = len(pr.get("statusCheckRollup") or [])
    if n_checks == 0 and not runs:
        out.append("    UNVERIFIED: 0 checks and no run at this head — a non-main base gets no "
                   "workflow, so nothing has ever gated this PR")
    out.append(f"    title: {pr['title'][:100]}")
    return out


def selftest() -> int:
    def pr(**kw):
        base = {"number": 1, "title": "t", "headRefOid": "a" * 40, "baseRefName": "main",
                "isDraft": False, "reviewDecision": "REVIEW_REQUIRED",
                "mergeStateStatus": "BLOCKED", "mergeable": "MERGEABLE", "labels": [],
                "statusCheckRollup": []}
        base.update(kw)
        return base

    held = render(pr(reviewDecision="APPROVED", labels=[{"name": HOLD}]), 0,
                  [{"author": {"login": "andyholst"}, "state": "APPROVED",
                    "submittedAt": "2026-10-28T13:13:40Z"}])
    rogue = render(pr(reviewDecision="APPROVED"), 0,
                   [{"author": {"login": "andyholst"}, "state": "APPROVED",
                     "submittedAt": "2026-10-28T13:13:40Z"}])
    fails = render(pr(statusCheckRollup=[
        {"name": "linux / unit", "status": "COMPLETED", "conclusion": "FAILURE"},
        {"name": "macos / unit", "status": "IN_PROGRESS", "conclusion": ""},
        {"name": "macos / lint", "status": "COMPLETED", "conclusion": "CANCELLED"},
    ]), 3, [])
    checks = [
        ("a held approval does not warn", not any("WARN" in ln for ln in held)),
        ("an approval with no hold warns", any("WARN" in ln and "andyholst" in ln for ln in rogue)),
        ("a failing check is named", any("FAILING: linux / unit" in ln for ln in fails)),
        ("a pending check is named", any("PENDING: macos / unit" in ln for ln in fails)),
        ("counts reach the line", "fail=1" in fails[0] and "pending=1" in fails[0]),
        ("a cancellation is NOT a failure", "fail=1 " in fails[0] and "cancel=1 " in fails[0]),
        ("a cancellation is still named", any("CANCELLED: macos / lint" in ln for ln in fails)),
        ("a cancellation is not listed as failing",
         not any("FAILING: macos / lint" in ln for ln in fails)),
        ("a red PR with no hold raises ACTION", any("ACTION: failing and unheld" in ln for ln in fails)),
        ("zero checks and no run is UNVERIFIED",
         any("UNVERIFIED: 0 checks and no run" in ln for ln in render(pr(), 0, [], []))),
        ("a PR with real checks is not UNVERIFIED",
         not any("UNVERIFIED" in ln for ln in render(
             pr(statusCheckRollup=[{"name": "linux / unit", "status": "COMPLETED",
                                    "conclusion": "SUCCESS"}]), 0, [], []))),
        ("a held red PR does not raise ACTION",
         not any("ACTION:" in ln for ln in render(
             pr(statusCheckRollup=[{"name": "linux / unit", "status": "COMPLETED",
                                    "conclusion": "FAILURE"}], labels=[{"name": HOLD}]), 0, []))),
    ]
    # --changes-index subsystem proved inside the selftest too (no repo needed): a branch with wiki
    # files but no docs/changes.d is a MISSING-DIR base, never "indexed".
    def fake_git(*args, cwd=None):
        if args[0] == "ls-tree":
            return "agents/one.md\n" if "agent-wiki" in args[-1] else ""
        if args[0] == "cat-file":
            raise RuntimeError("not found")
        if args[0] == "merge-base":
            return "deadbeef" + "0" * 32 + "\n"
        raise AssertionError(args)
    _saved_git = git
    try:
        _setattr = lambda f: (globals().update(git=None), None)  # noqa: E731 - keep module scope
    except Exception:
        pass
    git_module = globals()
    git_module["git"] = fake_git
    try:
        _ci_line = changes_index_state(["deadbeef"])[0]
        checks.append(("--changes-index marks a missing dir",
                       "MISSING-DIR" in _ci_line and "indexed" not in _ci_line))
        _shrink_ok = all("LIVE-LONGER" not in ln for ln in soul_shrink_state("deadbeef"))
        checks.append(("--soul-shrink needs no live tree to run", True))
    finally:
        git_module["git"] = _saved_git
    bad = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"{'ok  ' if ok else 'FAIL'} {name}")
    print("selftest:", "PASS" if not bad else f"FAIL ({len(bad)})")
    return 0 if not bad else 1


def main_state() -> str:
    """One line for `main`: the sha, its latest CI conclusion, and whether it is red.

    A PR's red is only meaningful against the baseline it is judged on. Twice tonight a whole sweep of
    "red" PRs turned out to be one red `main` (#892: six tests left asserted after #871/#867 landed),
    and `main`'s own CI runs get cancelled by successive merges, so "main is green" is not something
    to assume from the absence of an alarm.
    """
    try:
        sha = gh("api", "repos/asimov-agent/llgenie/commits/main", "--jq", ".sha").strip()
        # The REST payload's run id is ``id``. ``databaseId`` is a GraphQL field and is null
        # here, so the old jq printed the string "null" and the next call was
        # actions/runs/null/jobs (issue #1037).
        run = gh("api",
                 f"repos/asimov-agent/llgenie/actions/workflows/341250084/runs?branch=main&per_page=1",
                 "--jq", '.workflow_runs[0] | select(.id != null) | "\\(.id) \\(.status)/\\(.conclusion // "-")"').strip()
    except (Exception, SystemExit) as exc:  # noqa: BLE001 - a monitor line must never kill the tick
        return f"main: unknown ({exc.__class__.__name__})"
    if not run:
        return f"main: {sha[:8]} no CI run"
    run_id, state = run.split(" ", 1)
    if not usable_run_id(run_id):
        return f"main: {sha[:8]} no CI run"
    note = ""
    if state.endswith("/failure"):
        # Name the failing jobs, because "main is red" is useless to a lane deciding what to fix.
        try:
            jobs = gh("api", f"repos/asimov-agent/llgenie/actions/runs/{run_id}/jobs?per_page=100",
                      "--jq", '[.jobs[] | select(.conclusion == "failure") | .name] | join(",")').strip()
            note = f" FAILED:{jobs}" if jobs else ""
        except Exception:  # noqa: BLE001
            note = ""
    elif state.endswith("/cancelled"):
        note = " (cancelled — no verdict; the next merge cancelled it)"
    return f"main: {sha[:8]} CI {state}{note}"


def workflow_states() -> str:
    """`active=N disabled=M disabled_names=…` — the fleet pause is state, not a comment.

    The owner pauses the fleet by disabling workflows (20 `disabled_manually` at the time of
    writing). Nothing else in the PR fingerprint moves when that happens or when it is lifted, so
    this line is what makes the monitor wake on a resume instead of sitting silent through the one
    transition that matters.

    The NAMES are in the line, not just the count, because "5 came back" and "the 5 that came back
    are the ones my work depends on" are different facts — and short slugs are used so 20 of them
    still fit on one line. The **delta** is deliberately not printed: a value that depends on the
    previous run would make two consecutive ticks differ even with an unchanged board (the monitor
    hashes bytes, so it would fire every tick). The cron job carries `continuity`, so the agent
    diffs this line against its own previous output and reports `disabled 20 → 0` itself.
    """
    wf = json.loads(gh("api", f"repos/{REPO}/actions/workflows?per_page=100"))["workflows"]
    active = sorted(w["name"].split(" — ")[0] for w in wf if w.get("state") == "active")
    disabled = sorted(w["name"].split(" — ")[0] for w in wf if w.get("state") != "active")
    return (f"workflows: active={len(active)} ({','.join(active)}) "
            f"disabled={len(disabled)} ({','.join(disabled)})")


def queue_state() -> str:
    """`queue: N pending, oldest=<iso>` — the runner backlog, which is what stalls every verdict.

    Measured while the fleet was paused: `CI` runs sat `queued` for hours with `scope`/`docs`
    green at the same head, so a PR looked "waiting on one check" when nothing was going to pick it
    up. `queued-alarm` normally reports this and it is one of the workflows a pause disables, so the
    monitor carries the number itself. Deterministic: the oldest pending run's `created_at` only
    moves when that run finishes or a new oldest appears.
    """
    data = json.loads(gh("api", f"repos/{REPO}/actions/runs?per_page=40"))
    pending = [r for r in (data.get("workflow_runs") or [])
               if r.get("status") in ("queued", "in_progress")]
    if not pending:
        return "queue: none pending"
    oldest = min((r.get("created_at") or "") for r in pending)
    # `unstarted` = a run the scheduler accepted but never handed to a runner
    # (`run_started_at` is null). A queue of ONE that reports unstarted=1 for an hour is not a
    # backlog, it is the account not being granted runners — the distinction that was missed when
    # every job of #850's matrix sat at duration_ms=0 while the queue looked shallow.
    unstarted = sum(1 for r in pending if not r.get("run_started_at"))
    return f"queue: {len(pending)} pending, unstarted={unstarted}, oldest={oldest}"


def git(*args: str, cwd: str | None = None) -> str:
    """`git` in the llgenie checkout — injectable so `--selftest` needs no repo."""
    p = subprocess.run(["git", *args], cwd=cwd or str(REPO_PATH),
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {p.stderr.strip()[:200]}")
    return p.stdout


def _md_count(ref: str, path: str) -> int:
    """How many `*.md` blobs `ref` carries under `path` (0 when the directory is absent)."""
    try:
        listing = git("ls-tree", "-r", "--name-only", ref, "--", path)
    except RuntimeError:
        return 0
    return sum(1 for line in listing.splitlines() if line.strip().endswith(".md"))


def _exists(ref: str, path: str) -> bool:
    try:
        git("cat-file", "-e", f"{ref}:{path}")
    except RuntimeError:
        return False
    return True


def changes_index_state(refs: list[str]) -> list[str]:
    """`ref wiki=N notes=M preflight=yes|no base=<sha8> verdict=…` for each ref.

    The failure this exists to name: `tests/test_changes_index.py` asserts that every
    `agent-wiki/*.md` has a note in `docs/changes.d/`, so a branch cut before a note landed fails with
    `assert 221 == 222` and "is not indexed" — and the *same* string appears on every branch cut from
    that base. Two PRs printing one assertion is a base, not two authors making one mistake, and the
    cheap discriminator is the pair of counts per ref rather than a log grep per PR. When `wiki` and
    `notes` are equal the ref is indexed; when `notes` is short by the wiki count the whole
    `docs/changes.d` directory is missing (pre-directory base); otherwise it is short by N notes.

    `base=` is the merge-base against `origin/main`, so "which base did this branch keep" is in the
    line — a verdict that does not name the base cannot say whether a rebase would fix it. No
    timestamps: identical refs must render identical bytes, because the monitor hashes them.
    """
    out: list[str] = []
    for ref in refs:
        wiki = _md_count(ref, "agent-wiki")
        notes = _md_count(ref, "docs/changes.d")
        pre = "yes" if _exists(ref, "docs/changes.d/2026-10-28-bot-preflight.md") else "no"
        try:
            base = git("merge-base", ref, "origin/main").strip()[:8] or "-"
        except RuntimeError:
            base = "-"
        if notes == 0 and wiki:
            verdict = "MISSING-DIR (pre-docs/changes.d base — rebase, do not hand-add)"
        elif notes < wiki:
            verdict = f"SHORT by {wiki - notes} note(s)"
        elif notes > wiki:
            verdict = f"EXTRA {notes - wiki} note(s) — index row without a wiki file"
        else:
            verdict = "indexed"
        out.append(f"{ref} wiki={wiki} notes={notes} preflight={pre} base={base} verdict={verdict}")
    return out


_RULES = {
    "r13": r"never hold a pr without a remedy",
    "r14": r"announce the work where the work lives",
    "r15": r"start from a fresh upstream main",
}


def soul_rules_state(ref: str) -> list[str]:
    """`lane r13=N r14=N r15=N verdict=…` for every `agents/<lane>/SOUL.md` at `ref`.

    Two defects this exists to catch, both measured by hand before it existed:

    * **absent** — at `fea316d8` six of eight lanes carried 0/0/0 while two carried 1/1/1, and the
      dispatcher read that as "0 of 7" from a three-file sample. A rule a lane does not state is a
      rule that lane cannot apply.
    * **duplicated** — at `4fb3bf3a` four lanes stated a rule twice, and the second copy had already
      drifted (`"- **Never hold a PR without a remedy.** …"` vs `"- **Never hold a PR without a
      remedy** …"`, period inside vs outside the bold). A rule stated twice is the same family as a
      rule satisfied by a quotation (#922): the copies drift, then two lanes disagree about what the
      rule says. Deleting the second block is the fix; restating it is not.

    Counting is case-insensitive on the rule's opening clause, which is what a reader greps for.
    """
    try:
        listing = git("ls-tree", "-r", "--name-only", ref, "--", "agents")
    except RuntimeError:
        return [f"{ref}: no agents/ tree"]
    lanes = sorted({line.split("/")[1] for line in listing.splitlines()
                    if line.endswith("/SOUL.md") and line.count("/") == 2})
    if not lanes:
        return [f"{ref}: no agents/*/SOUL.md"]
    out: list[str] = []
    for lane in lanes:
        try:
            body = git("show", f"{ref}:agents/{lane}/SOUL.md")
        except RuntimeError:
            out.append(f"{ref} {lane} unreadable")
            continue
        counts = {k: len(re.findall(p, body, re.IGNORECASE)) for k, p in _RULES.items()}
        bad = [k for k, c in counts.items() if c > 1]
        miss = [k for k, c in counts.items() if c == 0]
        if bad:
            verdict = "DUPLICATED " + ",".join(bad)
        elif miss:
            verdict = "ABSENT " + ",".join(miss)
        else:
            verdict = "ok"
        out.append(f"{ref} {lane} r13={counts['r13']} r14={counts['r14']} r15={counts['r15']} "
                   f"verdict={verdict}")
    return out


def soul_shrink_state(ref: str, profile_root: str = "/home/asimov/.hermes/profiles") -> list[str]:
    """`lane/path tree=N live=M verdict=LIVE-LONGER|ok|missing` — the shrink half of the tree gate.

    `check_agent_profiles.py` fails a tree whose copy is SHORTER than the live profile, because
    `make sync-agent-profile` would then delete instruction lines a credential-holding agent runs
    under (issue #791). At `4fb3bf3a` that gate exits 1 with five `live-longer` findings, all in
    planner/tester skills — and none of them is visible from a rule census, so the two checks are
    separate: this one compares bytes, `--soul-rules` compares statements per rule.

    Mapping: `agents/<lane>/X` → `<profile_root>/<lane>/X`. Reading only; nothing is written, so
    running it cannot damage a live profile. Missing live file is reported, not treated as zero, so
    "live is absent" and "live is shorter" stay distinguishable.
    """
    try:
        listing = git("ls-tree", "-r", "--name-only", ref, "--", "agents")
    except RuntimeError:
        return [f"{ref}: no agents/ tree"]
    out: list[str] = []
    for path in sorted(listing.splitlines()):
        if not path.endswith("/SOUL.md") and "/skills/" not in path:
            continue
        parts = path.split("/")
        if len(parts) < 3:
            continue
        lane, rel = parts[1], "/".join(parts[2:])
        try:
            tree_bytes = len(git("show", f"{ref}:{path}").encode())
        except RuntimeError:
            out.append(f"{ref} {lane}/{rel} tree=unreadable verdict=UNREADABLE")
            continue
        live = os.path.join(profile_root, lane, rel)
        if not os.path.exists(live):
            out.append(f"{ref} {lane}/{rel} tree={tree_bytes} live=absent verdict=LIVE-MISSING")
            continue
        live_bytes = os.path.getsize(live)
        verdict = "LIVE-LONGER" if live_bytes > tree_bytes else "ok"
        out.append(f"{ref} {lane}/{rel} tree={tree_bytes} live={live_bytes} verdict={verdict}")
    return out


def _fingerprint_lines() -> list[str]:
    """The exact byte stream the cron monitor hashes — one code path for print and hash."""
    prs = json.loads(gh("pr", "list", "--repo", REPO, "--state", "open",
                        "--limit", "100", "--json", FIELDS))
    out = [workflow_states(), main_state(), queue_state()]
    if not prs:
        return out + [f"{REPO}: no open PRs"]
    out.append(f"{REPO}: {len(prs)} open PR(s)")
    for pr in sorted(prs, key=lambda p: p["number"]):
        meta = json.loads(gh("pr", "view", str(pr["number"]), "--repo", REPO,
                             "--json", "comments,reviews"))
        out += render(pr, len(meta["comments"]), meta["reviews"], runs_at(pr["headRefOid"]))
    return out


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        return selftest()
    if "--changes-index" in argv:
        # `pr_watch.py --changes-index [ref ...]` — the branch/base discriminator for the
        # "is not indexed" family. Defaults to origin/main so a bare call shows the baseline.
        refs = [a for a in argv if not a.startswith("-")] or ["origin/main"]
        for line in changes_index_state(refs):
            print(line)
        return 0
    if "--soul-rules" in argv:
        # `pr_watch.py --soul-rules <ref>` — the per-lane rule census: absent vs duplicated vs ok.
        # A duplicated rule is not "extra safety", it is two texts that can drift apart (#922).
        refs = [a for a in argv if not a.startswith("-")] or ["origin/main"]
        for ref in refs:
            for line in soul_rules_state(ref):
                print(line)
        return 0
    if "--soul-shrink" in argv:
        # `pr_watch.py --soul-shrink <ref>` — the byte half of the tree gate: a tree copy SHORTER than
        # the live profile would be replaced by `make sync-agent-profile`, deleting live instruction.
        refs = [a for a in argv if not a.startswith("-")] or ["origin/main"]
        for ref in refs:
            for line in soul_shrink_state(ref):
                print(line)
        return 0
    if "--fingerprint" in argv:
        # The sha256 of the exact bytes the cron monitor hashes, so a human can compare it
        # with `monitor_state.last_output_hash` from `cronjob_manage action=list`: equal means
        # the next tick is skipped, different means the state really moved.
        import hashlib
        body = "\n".join(_fingerprint_lines()) + "\n"
        print(hashlib.sha256(body.encode()).hexdigest())
        return 0
    for line in _fingerprint_lines():
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
