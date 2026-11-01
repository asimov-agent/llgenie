#!/usr/bin/env python3
"""Fold a host-agent lane's live profile files back into the repo tree, or check for drift.

Why a script: the live profile home holds EVERY skill, while `agents/<profile>/` holds only the
versioned ones, so the lane's file set has to be derived from the TREE -- never from an assumed
layout. Hand-assuming a path (references/ one level up from where they actually live, or a category
subdirectory that the sync compares as flat) silently checks nothing and reports "in sync" while a
drifted SKILL.md ships a truncated rulebook.

Usage, from the repo root of the worktree you are editing:

    python3 <skill>/scripts/fold-live-profile.py --profile llgenie-tester           # report only
    python3 <skill>/scripts/fold-live-profile.py --profile llgenie-tester --copy    # live -> tree

Exit codes: 0 = no drift (or copy done), 1 = drift found in --check mode, 2 = mid-write detected.

Rules it encodes:
  * tree -> live mapping is repo/agents/<profile>/<rel>  ->  ~/.hermes/profiles/<profile>/<rel>
  * a file under a directory the tree already covers but absent from the tree is a `skill-reference-
    missing`-class finding (a new references/*.md the live SKILL now links) -- reported, never copied
    blindly, because a new reference also needs its SKILL.md link committed.
  * read the live file TWICE with a pause; a hash that moves between reads is another lane's active
    edit -- a mid-write capture passes `--check` because both sides carry the same truncation.
  * copy with shutil.copyfile (bytes only), then re-hash the destination to prove the copy landed.
"""

import argparse
import hashlib
import os
import shutil
import sys
import time


def sha12(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:12]


def stable_sha(path: str, pause: float = 2.0) -> tuple[str, bool]:
    """Hash twice; False means the file moved between reads (likely mid-write)."""
    first = sha12(path)
    time.sleep(pause)
    return sha12(path), first == sha12(path)


def git_ls_files(repo: str, prefix: str) -> list[str]:
    import subprocess

    out = subprocess.run(  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
        ["git", "ls-files", prefix], cwd=repo, capture_output=True, text=True, check=True
    ).stdout
    return [line for line in out.splitlines() if line.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--live-home", default=os.path.expanduser("~/.hermes/profiles"))
    ap.add_argument("--copy", action="store_true", help="copy drifted files live -> tree")
    ap.add_argument("--pause", type=float, default=2.0)
    args = ap.parse_args()

    repo = os.path.abspath(args.repo)
    tree_root = os.path.join(repo, "agents", args.profile)
    live_root = os.path.join(args.live_home, args.profile)
    if not os.path.isdir(tree_root):
        print(f"no tree lane at agents/{args.profile} -- nothing versioned", file=sys.stderr)
        return 2
    if not os.path.isdir(live_root):
        print(f"no live profile at {live_root}", file=sys.stderr)
        return 2

    tracked = git_ls_files(repo, f"agents/{args.profile}")
    rels = sorted(p[len(f"agents/{args.profile}/"):] for p in tracked)

    drift: list[tuple[str, str, str]] = []  # rel, tree hash, live hash
    same = 0
    missing_live: list[str] = []
    midwrite: list[str] = []

    for rel in rels:
        tpath = os.path.join(repo, "agents", args.profile, rel)
        lpath = os.path.join(live_root, rel)
        if not os.path.isfile(tpath):
            continue
        if not os.path.isfile(lpath):
            missing_live.append(rel)
            print(f"  LIVE-MISSING {rel} (tree has it, live does not -- do NOT copy tree -> live blindly)")
            continue
        th = sha12(tpath)
        lh, stable = stable_sha(lpath, args.pause)
        if not stable:
            midwrite.append(rel)
            print(f"  MID-WRITE  {rel} -- live hash moved between two reads; re-read later")
            continue
        if th != lh:
            drift.append((rel, th, lh))
            print(f"  DRIFT      {rel}: tree {th} vs live {lh}")
        else:
            same += 1
            print(f"  same       {rel}: {th}")

    # live-only files inside directories the tree already covers (new references/*.md class)
    covered = {os.path.dirname(r) for r in rels if os.path.dirname(r)}
    live_extra: list[str] = []
    for d in sorted(covered):
        ldir = os.path.join(live_root, d)
        if not os.path.isdir(ldir):
            continue
        for name in sorted(os.listdir(ldir)):
            rel = os.path.join(d, name)
            if os.path.isfile(os.path.join(ldir, name)) and rel not in rels:
                live_extra.append(rel)
                print(f"  LIVE-ONLY  {rel} -- not in the tree; a SKILL that links it reds skill-reference-missing")

    print(
        f"\n{args.profile}: {same} same, {len(drift)} drifted, {len(missing_live)} live-missing, "
        f"{len(live_extra)} live-only, {len(midwrite)} mid-write"
    )

    if args.copy:
        if midwrite:
            print("refusing to copy while a live file is mid-write", file=sys.stderr)
            return 2
        for rel, th, lh in drift:
            src = os.path.join(live_root, rel)
            dst = os.path.join(repo, "agents", args.profile, rel)
            shutil.copyfile(src, dst)
            after = sha12(dst)
            ok = after == lh
            print(f"  copied     {rel} -> {after} {'OK' if ok else 'MISMATCH'}")
            if not ok:
                return 2
        if not drift:
            print("nothing to copy")
        print("\nnow: write agent-wiki + docs/changes.d fragments, `make changes-index`,"
              " commit, then run check-docs + lint_linefeeds + `agent_profile_sync.py --check`")
        return 0

    return 1 if (drift or live_extra or missing_live or midwrite) else 0


if __name__ == "__main__":
    sys.exit(main())
