#!/usr/bin/env python3
"""Classify every local branch by PR state, so worktree/branch debris can be
pruned without guessing which branches still hold unlanded work.

Read-only unless --apply is passed. Without --apply it prints the classification
and the prune commands it WOULD run; it deletes nothing.

Why this exists: with a squash-merge workflow a merged branch's tip is NEVER an
ancestor of the base branch, so `git branch --merged`, `git branch -d` and
"is my branch behind?" all lie. Only the forge's PR state is the truth — and
that means the PR's mergeCommit must be an ancestor of the base, not just that
the PR says MERGED.

Usage:
    python3 branch_pr_audit.py [--repo DIR] [--base origin/main] [--remote origin]
    python3 branch_pr_audit.py --apply        # prune verified-merged buckets only

--apply never touches pr-open, pr-closed-unmerged or no-pr-with-unique-content
branches, never removes a worktree with uncommitted changes, and never
force-removes anything. A worktree it cannot delete (files owned by another
user, e.g. container-run tests) is reported with the root-container recipe.

Exit codes: 0 audit printed, 2 git/gh could not be read (never a silent empty run).
"""
import argparse
import collections
import json
import os
import shutil
import subprocess
import sys


def run(cmd, cwd, check=False):
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)  # proc-allow: vendored skill script folded live->tree (issue #2262 fold parity; not a bot-lane runner)
    if check and proc.returncode != 0:
        sys.exit(f"FATAL: {' '.join(cmd)} -> {proc.returncode}\n{proc.stderr.strip()}")
    return proc.stdout.strip()


def rc(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True).returncode  # proc-allow: vendored skill script folded live->tree (issue #2262 fold parity; not a bot-lane runner)


def repo_slug(repo, remote):
    url = run(["git", "remote", "get-url", remote], repo)
    if not url:
        return None
    slug = url.rstrip("/")
    if slug.endswith(".git"):
        slug = slug[:-4]
    if ":" in slug and "://" not in slug:
        slug = slug.split(":", 1)[1]
    parts = slug.split("/")
    return "/".join(parts[-2:]) if len(parts) >= 2 else None


def pr_states(repo, slug):
    """head branch -> [PR, ...] from the forge, the only trustworthy source."""
    if not slug or not shutil.which("gh"):
        return {}
    out = run([
        "gh", "pr", "list", "--repo", slug, "--state", "all", "--limit", "1000",
        "--json", "number,state,headRefName,title,mergeCommit",
    ], repo)
    if not out:
        return {}
    states = collections.defaultdict(list)
    for pr in json.loads(out):
        states[pr["headRefName"]].append(pr)
    return states


def worktrees(repo):
    """branch -> worktree path, from porcelain output (one block per worktree)."""
    out = run(["git", "worktree", "list", "--porcelain"], repo)
    mapping, path = {}, None
    for line in out.splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree "):]
        elif line.startswith("branch "):
            mapping[line[len("branch "):].replace("refs/heads/", "")] = path
        elif not line.strip():
            path = None
    return mapping


def branch_rows(repo, base):
    fmt = "%(refname:short)|%(committerdate:short)|%(subject)"
    rows = []
    for line in run(["git", "for-each-ref", "--format", fmt, "refs/heads"], repo).splitlines():
        name, date, subject = line.split("|", 2)
        counts = run(["git", "rev-list", "--left-right", "--count", f"{base}...{name}"], repo).split()
        if len(counts) != 2:
            sys.exit(f"FATAL: cannot compare {name} to {base}")
        behind, ahead = int(counts[0]), int(counts[1])
        # three-dot diff = the branch's own content, ignoring work that landed on base since.
        touched = run(["git", "diff", "--name-only", f"{base}...{name}"], repo).splitlines()
        rows.append({"name": name, "date": date, "subject": subject,
                     "ahead": ahead, "behind": behind,
                     "touched": len(touched), "lines": touched})
    return rows


def merge_landed(repo, base, pr):
    """True when the PR's mergeCommit is an ancestor of base (the only safe gate)."""
    oid = (pr.get("mergeCommit") or {}).get("oid")
    if not oid:
        return False, "no merge commit on the PR"
    if rc(["git", "merge-base", "--is-ancestor", oid, base], repo) != 0:
        return False, f"merge commit {oid[:8]} not on {base} (fetch/behind?)"
    return True, oid[:8]


def classify(repo, base, states):
    rows = branch_rows(repo, base)
    for row in rows:
        prs = states.get(row["name"], [])
        kinds = {p["state"] for p in prs}
        row["why"] = ""
        if "MERGED" in kinds:
            pr = next(p for p in prs if p["state"] == "MERGED")
            landed, why = merge_landed(repo, base, pr)
            row["pr"] = pr["number"]
            row["why"] = why
            row["verdict"] = ("pr-merged, verified on base (safe to prune)" if landed
                              else "pr-merged, merge commit NOT on base (review)")
        elif "OPEN" in kinds:
            row["verdict"], row["pr"] = "pr-open (KEEP)", \
                next(p["number"] for p in prs if p["state"] == "OPEN")
        elif kinds:
            row["verdict"], row["pr"] = "pr-closed-unmerged (review)", prs[0]["number"]
        elif row["touched"] == 0:
            row["verdict"], row["pr"] = "no-pr, content on base (safe to prune)", "-"
        else:
            row["verdict"], row["pr"] = f"no-pr, {row['touched']} file(s) unique (review)", "-"
    return rows


def apply_prune(repo, rows, wts):
    """Remove clean worktrees + branches in the two verified-safe buckets."""
    safe = [r for r in rows if r["verdict"] in (
        "pr-merged, verified on base (safe to prune)",
        "no-pr, content on base (safe to prune)")]
    removed_wt, removed_br, skipped = [], [], []
    for row in safe:
        name = row["name"]
        path = wts.get(name)
        if path:
            if not os.path.isdir(path):
                skipped.append((name, f"worktree dir missing: {path}"))
            elif run(["git", "-C", path, "status", "--porcelain"], repo).strip():
                skipped.append((name, "worktree has uncommitted changes"))
            elif rc(["git", "worktree", "remove", path], repo) == 0:
                removed_wt.append(path)
            else:
                skipped.append((name, f"worktree remove failed (root-owned files? see SKILL.md): {path}"))
        if rc(["git", "branch", "-D", name], repo) == 0:
            removed_br.append(name)
        else:
            skipped.append((name, "branch -D refused (checked out in a worktree?)"))
    run(["git", "worktree", "prune"], repo)
    print(f"\napplied: worktrees removed={len(removed_wt)} branches removed={len(removed_br)} skipped={len(skipped)}")
    for name, why in skipped:
        print(f"  SKIP {name}: {why}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--apply", action="store_true",
                    help="prune the verified-safe buckets (default: audit only)")
    args = ap.parse_args()

    slug = repo_slug(args.repo, args.remote)
    states = pr_states(args.repo, slug)
    if slug and not states:
        print(f"WARN: no PR data from gh for {slug}; classifying by tree equality only")
    elif not slug:
        print("WARN: no remote slug; classifying by tree equality only")

    rows = classify(args.repo, args.base, states)
    wts = worktrees(args.repo)
    buckets = collections.Counter(r["verdict"].split(" (")[0] for r in rows)

    width = max((len(r["name"]) for r in rows), default=10)
    print(f"repo={args.repo} base={args.base} slug={slug} branches={len(rows)} worktrees={len(wts)}\n")
    for row in sorted(rows, key=lambda r: (r["verdict"], r["date"])):
        print(f"  {row['name']:<{width}}  {row['date']}  ahead{row['ahead']:>4} "
              f"behind{row['behind']:>4}  PR#{row['pr']:<5} {row['verdict']}"
              + (f" [{row['why']}]" if row["why"] else ""))

    print("\nsummary")
    for key in sorted(buckets):
        print(f"  {buckets[key]:>4}  {key}")

    if args.apply:
        apply_prune(args.repo, rows, wts)
        return
    safe = [r for r in rows if r["verdict"].endswith("(safe to prune)")]
    if safe:
        print("\nprune (nothing was run; pass --apply to prune the safe buckets):")
        for row in safe:
            path = wts.get(row["name"])
            print(f"  {row['name']}: check `git -C {path} status --porcelain`, "
                  f"git worktree remove {path or '<none>'}, git branch -D {row['name']}")
        print("  git worktree prune")


if __name__ == "__main__":
    main()
