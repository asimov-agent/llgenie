#!/usr/bin/env python3
"""Classify a diverged worktree: stale copy, or genuinely unique work?

A sweep that reports "worktree X is ahead N / behind M of its PR's remote" is NOT evidence that the
worktree holds work nothing else has: an older base guarantees a non-empty tree diff. This decides it
by mechanism instead of by eyeball.

Per file that differs between the worktree's HEAD and the target ref, classify:

  =main            blob is byte-identical to the main ref (older; main has moved past it)
  =target          blob is byte-identical to the target (nothing to reconcile)
  absent-locally   the target added it (new upstream work, not yours)
  in-main-history  blob matches no single ref but occurs somewhere in main's history (older)
  CANDIDATE        matches none of the above; then tested for line-set containment:
                   `diff base..HEAD` additions/removals SUBSET OF `diff base..target`
                   both subsets -> OLDER (every line this file has, the newer version has too)
                   otherwise    -> UNIQUE (report it; it goes in a push, never a reset)

git operations are read-only: nothing is fetched, checked out, reset or pushed.

Usage:
    worktree_divergence_audit.py --worktree /path/wt --target origin/<pr-branch> \\
        [--main origin/main] [--base <sha>] [--json]

Exit: 0 = nothing unique (safe to re-point), 1 = unique work found, 2 = cannot read a ref.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

SHA = re.compile(r"[0-9a-f]{40}")


def git(wt: str, *args: str) -> str | None:
    r = subprocess.run(["git", "-C", wt, *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def blob(wt: str, rev: str, path: str) -> str | None:
    out = git(wt, "rev-parse", f"{rev}:{path}")
    return out if out and SHA.fullmatch(out) else None


def changed(wt: str, a: str, b: str) -> list[str]:
    out = git(wt, "diff", "--name-status", f"{a}..{b}") or ""
    return [ln.split("\t", 1)[1] for ln in out.splitlines() if "\t" in ln]


def hist_blobs(wt: str, rev: str, path: str) -> set[str]:
    """Every blob this path ever had on `rev` — 'the content exists upstream, just older'."""
    out = git(wt, "rev-list", "--objects", rev, "--", path) or ""
    return {ln.split(" ", 1)[0] for ln in out.splitlines() if ln and not ln.startswith(" ")}


def line_sets(wt: str, a: str, b: str, path: str) -> tuple[set[str], set[str]]:
    diff = subprocess.run(["git", "-C", wt, "diff", f"{a}..{b}", "--", path],
                          capture_output=True, text=True).stdout
    adds = {ln[1:] for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++")}
    rems = {ln[1:] for ln in diff.splitlines() if ln.startswith("-") and not ln.startswith("---")}
    return adds, rems


def audit(wt: str, target: str, main: str, base: str | None) -> dict:
    base = base or git(wt, "merge-base", target, "HEAD")
    rows = []
    for path in changed(wt, target, "HEAD"):
        h, m, t = blob(wt, "HEAD", path), blob(wt, main, path), blob(wt, target, path)
        if h and t and h == t:
            cls = "=target"
        elif h is None:
            cls = "absent-locally"
        elif h and m and h == m:
            cls = "=main"
        elif h in hist_blobs(wt, main, path):
            cls = "in-main-history"
        else:
            # Matches no ref: the decisive test is whether its LINES are a subset of the newer file.
            l_add, l_rem = line_sets(wt, base, "HEAD", path)
            t_add, t_rem = line_sets(wt, base, target, path)
            subset = l_add <= t_add and l_rem <= t_rem
            cls = "older (lines subset of target)" if subset else "UNIQUE"
            rows.append({"file": path, "class": cls, "blob": (h or "")[:10],
                         "unique_adds": len(l_add - t_add), "unique_removes": len(l_rem - t_rem)})
            continue
        rows.append({"file": path, "class": cls, "blob": (h or "")[:10]})
    return {"head": git(wt, "rev-parse", "--short", "HEAD"),
            "target": target, "base": (base or "")[:10], "rows": rows,
            "unique": [r for r in rows if r["class"] == "UNIQUE"]}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Is this worktree stale, or does it hold unique work?")
    p.add_argument("--worktree", required=True)
    p.add_argument("--target", required=True, help="ref the PR's remote carries, e.g. origin/<branch>")
    p.add_argument("--main", default="origin/main")
    p.add_argument("--base", default=None, help="the chain's own base sha (default: merge-base)")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    for ref in (a.target, a.main):
        if not git(a.worktree, "rev-parse", "--verify", ref):
            print(f"[divergence] cannot resolve {ref} in {a.worktree} — fetch first", file=sys.stderr)
            return 2

    rep = audit(a.worktree, a.target, a.main, a.base)
    if a.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"[divergence] {a.worktree}  HEAD={rep['head']}  target={rep['target']}  base={rep['base']}")
        print(f"{'file':44} {'class':30} blob")
        for r in rep["rows"]:
            extra = ""
            if "unique_adds" in r:
                extra = f"  (+{r['unique_adds']} unique adds, -{r['unique_removes']} unique removes)"
            print(f"{r['file'][:44]:44} {r['class']:30} {r['blob']}{extra}")
        counts: dict[str, int] = {}
        for r in rep["rows"]:
            counts[r["class"]] = counts.get(r["class"], 0) + 1
        print("\n[divergence] " + " | ".join(f"{k}: {v}" for k, v in sorted(counts.items())))
        if rep["unique"]:
            print(f"[divergence] {len(rep['unique'])} file(s) carry lines no upstream version has — "
                  "do NOT reset; that work goes in a push")
        else:
            print("[divergence] nothing unique — safe to re-point: "
                  f"git -C {a.worktree} reset --hard {a.target}  (worktree must be clean; never force-push)")
    return 1 if rep["unique"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
