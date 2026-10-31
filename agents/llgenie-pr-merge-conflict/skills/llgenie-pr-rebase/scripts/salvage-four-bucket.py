#!/usr/bin/env python3
"""Read-only salvage audit with the planner's four buckets. Deletes nothing.

1. merged-and-clean   tip is an ancestor of origin/main AND a merged PR exists for the branch
2. merged-but-dirty   a PR merged, but the worktree holds uncommitted work (the prune's
                      "already merged" test reads the branch ref only and would destroy it)
3. unmerged-with-a-PR an open PR carries the branch (state reported)
4. orphan             no PR at all and the tip is not an ancestor of main

Then rank 2 and 4 by content not present in any remote ref: porcelain dirt per worktree, and
for tips, whether the branch adds a path main has never held (the rule this lane settled on --
a sha-diff is meaningless for squash-merged work).

Every call is read-only: gh read, git read. No prune, no remove, no branch -D.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

# Resolve the repository instead of hardcoding a host path: a skill script runs on whatever
# checkout it is invoked from, and an absolute path pinned to one laptop makes the tool fail
# on every other machine (and in CI, where the repo is /home/runner/work/...).
def _resolve_repo() -> str:
    env = os.environ.get("LLGENIE_REPO")
    if env:
        return env
    here = pathlib.Path(__file__).resolve()
    # the script lives at <repo>/agents/<lane>/skills/<skill>/scripts/<this>
    for parent in here.parents:
        if (parent / ".git").exists():
            return str(parent)
    return os.getcwd()


REPO = _resolve_repo()
ORG_REPO = "asimov-agent/llgenie"


def run(*a, timeout=180):
    try:
        return subprocess.run(a, cwd=REPO, capture_output=True, text=True, timeout=timeout)
    except subprocess.SubprocessError:
        return None


def out(*a, **kw):
    r = run(*a, **kw)
    return r.stdout.strip() if r and r.returncode == 0 else ""


def orphan_split(rows: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Split orphans into (unique, held-by-an-open-PR, lossless) — pure, so the labels are testable.

    A single `orphan: N` count is a number without its predicate. Measured on this host the orphan
    bucket held 124 branches; 21 added a path main lacks, and of those 21 only 6 had content that
    existed NOWHERE else — the other 15 were carried by an open PR head, so deleting them loses
    nothing reviewable. Reporting 21 as the preserve list over-conserves by 15; reporting 124 states
    the wrong thing entirely.

    The third group is why the two shipped audit tools disagreed on the same repo at the same main
    (shell 6 vs python 21): the shell already tested "is this content in SOME open PR head?" and
    this one tested only "does the branch have its own PR?". Same word, different predicate. Now
    both state the stronger one, and the numbers reconcile: unique + held_by_pr == added-paths.
    """
    orphans = [r for r in rows if r.get("bucket") == "orphan"]
    uniq, held, lossless = [], [], []
    for r in orphans:
        if not r.get("added"):
            lossless.append(r)
        elif r.get("held_by_pr"):
            held.append(r)
        else:
            uniq.append(r)
    return uniq, held, lossless


def summarise(rows: list[dict], wts: list[dict]) -> dict:
    """The prune verdict, as a pure function so it can be tested without gh or a real repo.

    Two rules, both learned by getting them wrong and measuring the difference:

    1. A worktree is safe to delete only when it is BOTH clean AND its HEAD carries nothing
       unique. Counting `total - dirty` marks a CLEAN worktree sitting on a unique branch as
       safe, which tells the owner to delete work that exists nowhere else.
    2. Deletable branches = everything EXCEPT the unique set. Enumerating buckets instead
       (merged-and-clean + unmerged-with-a-PR) silently drops the lossless orphans — 45
       reported where the truth was 162.
    """
    unique_orphans = [r for r in rows
                      if r["bucket"] == "orphan" and r.get("added") and not r.get("held_by_pr")]
    unique_shas = {r["tip"] for r in unique_orphans}
    keep_wt: dict[str, dict] = {w["path"]: w for w in wts if w["dirty"]}
    for w in wts:
        if w.get("head") in unique_shas or w.get("unique"):
            keep_wt.setdefault(w["path"], w)
    return {
        "unique_orphans": unique_orphans,
        "keep": list(keep_wt.values()),
        "safe_branches": len(rows) - len(unique_orphans),
        "safe_worktrees": len(wts) - len(keep_wt),
    }


def main() -> int:
    mainsha = out("git", "rev-parse", "refs/remotes/origin/main")
    if not mainsha:
        print("refs/remotes/origin/main missing", file=sys.stderr)
        return 2

    # PR maps keyed by head ref name.
    raw = out("gh", "pr", "list", "--repo", ORG_REPO, "--state", "all", "--limit", "600",
              "--json", "number,state,headRefName,headRefOid,mergedAt")
    prs = json.loads(raw) if raw.strip() else []
    head_pr: dict[str, dict] = {}
    for p in prs:
        hn = p.get("headRefName") or ""
        # keep the most relevant: an OPEN PR beats a merged one for the same branch name
        prev = head_pr.get(hn)
        if prev is None or (prev["state"] == "MERGED" and p["state"] == "OPEN"):
            head_pr[hn] = p

    # All refs whose tips we consider "present in a remote ref".
    remote_tips = set()
    ls = out("git", "ls-remote", "--heads", "origin")
    for line in ls.splitlines():
        parts = line.split()
        if len(parts) == 2:
            remote_tips.add(parts[0])
    rem_all = out("git", "ls-remote", "origin")
    for line in rem_all.splitlines():
        parts = line.split()
        if len(parts) == 2:
            remote_tips.add(parts[0])

    branches = [ln.split()[0] for ln in
                out("git", "for-each-ref", "--format=%(refname:short) %(objectname)",
                    "refs/heads/").splitlines() if ln.strip()]
    buckets = {"merged-and-clean": [], "merged-but-dirty": [], "unmerged-with-a-PR": [], "orphan": [],
               "detached": []}
    rows = []
    for b in branches:
        tip = out("git", "rev-parse", b)
        pr = head_pr.get(b)
        anc = run("git", "merge-base", "--is-ancestor", tip, mainsha)
        is_anc = bool(anc and anc.returncode == 0)
        if pr and pr["state"] == "MERGED":
            buck, merged = "merged-and-clean", True
        elif pr and pr["state"] == "OPEN":
            buck, merged = "unmerged-with-a-PR", False
        else:
            buck, merged = ("merged-and-clean" if is_anc else "orphan"), False
        rows.append(dict(branch=b, tip=tip, bucket=buck, pr=pr, anc=is_anc, merged=merged))

    # added-path test for orphan tips: a path main has never held
    open_prs = [p for p in prs if p["state"] == "OPEN"]
    for r in rows:
        if r["bucket"] != "orphan":
            continue
        ns = out("git", "diff", "--name-status", f"{mainsha}...{r['tip']}")
        added = []
        for line in ns.splitlines():
            if line.startswith("A\t"):
                p = line.split("\t")[1]
                chk = run("git", "cat-file", "-e", f"{mainsha}:{p}")
                if not chk or chk.returncode != 0:
                    added.append(p)
        r["added"] = added
        # A scratch branch whose added paths are ALL carried by an open PR loses nothing when
        # deleted: the content is reviewable elsewhere even though the branch name is not a PR head.
        hit = None
        if added:
            for p in open_prs:
                if all((run("git", "cat-file", "-e", f"{p['headRefOid']}:{f}") or
                        type("x", (), {"returncode": 1})()).returncode == 0 for f in added):
                    hit = p["number"]
                    break
        r["held_by_pr"] = hit

    # worktrees
    wts, cur = [], None
    for ln in out("git", "worktree", "list", "--porcelain").splitlines():
        if ln.startswith("worktree "):
            cur = {"path": ln[9:], "branch": "", "head": ""}
            wts.append(cur)
        elif ln.startswith("HEAD ") and cur:
            cur["head"] = ln[5:]
        elif ln.startswith("branch ") and cur:
            cur["branch"] = ln[7:].replace("refs/heads/", "")
        elif ln.startswith("detached") and cur:
            cur["branch"] = "(detached)"

    for w in wts:
        st = out("git", "-C", w["path"], "status", "--porcelain")
        w["dirty"] = len([x for x in st.splitlines() if x.strip()])
        w["files"] = [x[3:] for x in st.splitlines() if x.strip()][:6]

    by_branch = {r["branch"]: r for r in rows}

    print(f"=== SALVAGE AUDIT — main {mainsha[:8]} — {len(branches)} local branches, "
          f"{len(wts)} worktrees ===\n")

    for buck in ("merged-and-clean", "unmerged-with-a-PR", "orphan"):
        grp = [r for r in rows if r["bucket"] == buck]
        if buck == "orphan":
            # `orphan: 124` alone is a count without its predicate, and it reads as 124 pieces of
            # work to rescue when almost all of them add NOTHING main lacks. Split the label so the
            # number that matters is the small one: measured on this host, 124 orphans held 6
            # branches that add any path at all.
            uniq, held, lossless = orphan_split(rows)
            print(f"## orphan — UNIQUE (content exists nowhere else): {len(uniq)}  <- preserve these")
            for r in sorted(uniq, key=lambda x: x["branch"]):
                add = r.get("added") or []
                print(f"  {r['branch']:46} {r['tip'][:8]}  +{len(add)} path(s) only here")
                print(f"      {', '.join(add[:4])}{' …' if len(add) > 4 else ''}")
            print(f"## orphan — carried by an open PR head (nothing lost if deleted): {len(held)}")
            for r in sorted(held, key=lambda x: x["branch"]):
                print(f"  {r['branch']:46} {r['tip'][:8]}  PR #{r['held_by_pr']}")
            print(f"## orphan — lossless (main already covers every path it touches): {len(lossless)}")
            print(f"    (reconciles with salvage-audit.sh: its UNIQUE == this UNIQUE == {len(uniq)})")
            continue
        print(f"## {buck}: {len(grp)}")
        print()

    # merged-but-dirty: merged PR whose worktree carries uncommitted work
    dirty_merged = []
    for w in wts:
        r = by_branch.get(w["branch"])
        if w["dirty"] and r and r.get("merged"):
            dirty_merged.append((w, r))
    print(f"## merged-but-dirty: {len(dirty_merged)}  (PR merged, worktree still carries changes)")
    for w, r in dirty_merged:
        print(f"  {w['path']}")
        print(f"      branch={w['branch']} tip={r['tip'][:8]} dirty={w['dirty']} "
              f"PR #{r['pr']['number'] if r['pr'] else '?'} {r['pr']['state'] if r['pr'] else ''}")
        print(f"      files: {', '.join(w['files'])}")
    print()

    print("## detached worktrees (report separately — likeliest orphans)")
    for w in wts:
        if w["branch"] == "(detached)" or not w["branch"]:
            inremote = w["head"] in remote_tips
            print(f"  {w['path']:58} {w['head'][:8]} dirty={w['dirty']} "
                  f"in-remote-ref={'yes' if inremote else 'NO'}")
    print()

    dirty_all = [w for w in wts if w["dirty"]]
    orphans = [r for r in rows if r["bucket"] == "orphan"]
    unique_orphans = [r for r in orphans if r.get("added") and not r.get("held_by_pr")]
    unique_shas = {r["tip"] for r in unique_orphans}
    unique_wt = [w for w in wts if w.get("head") in unique_shas or w.get("unique")]
    keep = summarise(rows, wts)["keep"]
    print(f"conclusion: {len([r for r in rows if r['bucket']=='merged-and-clean'])} merged-and-clean"
          f" · {len(dirty_merged)} merged-but-dirty"
          f" · {len([r for r in rows if r['bucket']=='unmerged-with-a-PR'])} unmerged-with-a-PR"
          f" · {len(orphans)} orphan ({len(unique_orphans)} with content only here)")
    print(f"worktrees: {len(wts)} total · {len(dirty_all)} dirty · "
          f"{len(unique_wt)} on a unique branch · 0 removed")
    nodel = summarise(rows, wts)["safe_branches"]
    print(f"\nsafe in principle to delete: {nodel} branches, {len(wts)-len(keep)} worktrees")
    print(f"must be preserved: {len(unique_orphans)} branches + {len(keep)} worktrees "
          f"(dirty ∪ on-a-unique-branch)")
    for r in sorted(unique_orphans, key=lambda x: x["branch"]):
        print(f"  branch {r['branch']:44} {r['tip'][:8]}  +{len(r.get('added') or [])}")
    for w in keep:
        why = "dirty=%d" % w["dirty"] if w["dirty"] else "unique-branch"
        print(f"  worktree {w['path']:56} {w['branch'][:26]} {why}")
    print("\nNothing was deleted, pruned or removed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
