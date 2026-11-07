#!/usr/bin/env python3
"""Verify a live->tree fold is byte-identical, the way the reviewer checks it.

Compares a set of files at a git ref (read from the canonical repo's object store,
i.e. what the reviewer sees) against the live profile files on disk, using RAW BYTES
(no shell .strip(), so a trailing newline can never manufacture a false mismatch).

Prints a single AGGREGATE sha256 over the files sorted by name (one line to compare
live-vs-tree at a glance) plus an explicit per-file mismatch list.

Usage:
  python3 verify_fold_identity.py \\
      --repo /home/asimov/repository/git/llgenie \\
      --ref refs/remotes/origin/main \\
      --tree-dir agents/<profile>/skills/<skill>/references \\
      --live-dir /home/asimov/.hermes/profiles/<profile>/skills/<skill>/references \\
      --files a.md b.md c.md

Exit 0 = every file byte-identical; 1 = one or more differ or are missing.
"""
from __future__ import annotations
import argparse, hashlib, subprocess, sys


def git_blob(repo: str, ref: str, path: str) -> bytes:
    """Raw bytes of `path` at `ref` in `repo` — bytes, never decoded/stripped."""
    r = subprocess.run(
        ["git", "-C", repo, "cat-file", "blob", f"{ref}:{path}"],
        capture_output=True,
    )
    if r.returncode != 0:
        raise FileNotFoundError(f"{ref}:{path}: {r.stderr.decode(errors='replace').strip()}")
    return r.stdout  # binary-safe: no strip, no text decode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--tree-dir", required=True)
    ap.add_argument("--live-dir", required=True)
    ap.add_argument("--files", nargs="+", required=True)
    a = ap.parse_args()

    agg_live = hashlib.sha256()
    agg_tree = hashlib.sha256()
    mismatches: list[tuple[str, str, str]] = []

    for name in sorted(a.files):
        with open(f"{a.live_dir}/{name}", "rb") as fh:
            live = fh.read()
        try:
            tree = git_blob(a.repo, a.ref, f"{a.tree_dir}/{name}")
        except FileNotFoundError as e:
            print(f"  MISSING at ref: {name}  ({e})")
            mismatches.append((name, "-", "absent"))
            continue
        agg_live.update(live)
        agg_tree.update(tree)
        if live != tree:
            mismatches.append(
                (name,
                 hashlib.sha256(live).hexdigest()[:16],
                 hashlib.sha256(tree).hexdigest()[:16])
            )

    print(f"files checked : {len(a.files)}")
    print(f"aggregate live: {agg_live.hexdigest()}")
    print(f"aggregate tree: {agg_tree.hexdigest()}")
    print(f"identical     : {agg_live.hexdigest() == agg_tree.hexdigest() and not mismatches}")
    if mismatches:
        print("mismatches:")
        for name, lh, th in mismatches:
            print(f"  {name}: live {lh} != tree {th}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
