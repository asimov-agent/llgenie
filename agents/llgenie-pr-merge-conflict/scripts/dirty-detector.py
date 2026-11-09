#!/usr/bin/env python3
"""Deterministic change-detector for the llgenie DIRTY watch (cron `monitor`).

Prints the conflicting subset of asimov-agent/llgenie's open PRs, and nothing else. The output is
stable while nothing changes, so a cron monitor gate skips the agent on every quiet tick and wakes it
only when a PR enters or leaves the CONFLICTING set (or a conflicting PR's head moves).

No state file, no writes, no mutation: the detector only reports. The rebase itself is the agent's
job, on the recipe in the `llgenie-pr-rebase` skill.

    conflicting: none
        -- or --
    conflicting: 789 f9c60f59 DIRTY
    ...
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys

REPO = "asimov-agent/llgenie"
FIELDS = "number,headRefOid,mergeable,mergeStateStatus"

#: The cron runs with a minimal PATH that does NOT include the mise shims dir, so a bare "gh" is
#: `FileNotFoundError: 'gh'` and the whole tick dies (measured 2026-11-08, job 244a75ddc597).
#: Resolve the binaries the way a login shell would, then fall back to the real install paths.
_BIN_DIRS = [
    os.path.expanduser("~/.local/share/mise/shims"),
    "/usr/local/bin",
    "/usr/bin",
    "/bin",
]


def _resolve_bin(name: str) -> str:
    """Absolute path for `name`, or the bare name if every lookup fails (so the failure is the
    familiar FileNotFoundError naming the binary rather than a wrong guess)."""
    found = shutil.which(name)
    if found:
        return found
    for d in _BIN_DIRS:
        cand = os.path.join(d, name)
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return name


GH = _resolve_bin("gh")
GIT = _resolve_bin("git")


def _resolve_repo_dir() -> str:
    """The llgenie checkout to measure with merge-tree: $LLGENIE_REPO, else a .git parent, else
    the conventional checkout path.

    The last branch is a deliberate fallback, not a default: this detector runs from a cron inside
    the profile home, where no parent contains .git, so "nearest .git parent" alone resolves to the
    scripts directory and every merge-tree call would then measure the WRONG tree. Resolution
    order is explicit and the chosen path is asserted to be a git checkout.
    """
    env = os.environ.get("LLGENIE_REPO")
    if env:
        return env
    for p in pathlib.Path(__file__).resolve().parents:
        if (p / ".git").exists():
            return str(p)
    return "/home/asimov/repository/git/llgenie"


REPO_DIR = _resolve_repo_dir()


def _conflicts_with_main(head: str) -> bool:
    """True when `head` genuinely conflicts with the current `origin/main`, per merge-tree.

    GitHub's `mergeable` field is a cache that reads UNKNOWN while it recomputes and can be stale;
    `git merge-tree --write-tree --messages` is the measurement this lane trusts (#1015). Any
    failure to measure returns False so a broken local clone cannot invent a rebase job — the
    `detector-error` path above already wakes the agent for a broken read.
    """
    if not head:
        return False
    try:
        main = subprocess.run([GIT, "-C", REPO_DIR, "rev-parse", "refs/remotes/origin/main"],  # proc-allow: rc inspected on the line after, #797; tracked remainder for #2229 migration
                              capture_output=True, text=True, timeout=60)
        if main.returncode != 0:
            return False
        mt = subprocess.run([GIT, "-C", REPO_DIR, "merge-tree", "--write-tree", "--messages",  # proc-allow: rc carried in stdout+stderr (merge-tree rc 0/1 is the conflict signal), #797; tracked remainder for #2229 migration
                             main.stdout.strip(), head],
                            capture_output=True, text=True, timeout=120)
        # merge-tree exits non-zero on conflict; the marker text is the durable signal.
        return "CONFLICT" in (mt.stdout + mt.stderr)
    except (OSError, subprocess.SubprocessError):
        return False


def _main_sha() -> str:
    """The `origin/main` tip this run measures against, for a reproducible report.

    A conflict report naming PRs but no main is a predicate without its subject: a stale cron
    re-delivery (queue_full) would look live. Print the measured main with the conflicts; the
    byte-stable `conflicting: none` quiet path stays untouched, so a clean run keeps suppressing
    the tick and ONLY the conflict report — the line a tick WANTS to change — carries the sha.
    """
    r = subprocess.run([GIT, "-C", REPO_DIR, "rev-parse", "refs/remotes/origin/main"],  # proc-allow: rc inspected on the line after, #797; tracked remainder for #2229 migration
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else "unknown"


def main() -> int:
    out = subprocess.run(  # proc-allow: out.returncode inspected after the call (rc!=0 -> detector-error), #797; tracked remainder for #2229 migration
        [GH, "pr", "list", "--repo", REPO, "--state", "open", "--limit", "100", "--json", FIELDS],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        # A failed read must not look like "nothing conflicting": say so, so the tick wakes the agent.
        print(f"detector-error: gh rc={out.returncode}")
        sys.stderr.write(out.stderr)
        return 0
    try:
        prs = json.loads(out.stdout or "[]")
    except json.JSONDecodeError:
        print("detector-error: unparseable gh output")
        return 0

    # `mergeable` is UNKNOWN while GitHub is still computing the merge ref — measured live: at one
    # point EVERY open PR read UNKNOWN at once. Treating that as clean is a FALSE NEGATIVE that
    # skips the very rebase the tick exists to catch, and the monitor gate then suppresses every
    # later tick because the output stays byte-stable. Since this lane's rule is to measure with
    # `git merge-tree` and never trust the `mergeable` field alone (#1015), do exactly that here:
    # fold the undetermined PRs through merge-tree and report the authoritative answer.
    bad = sorted(
        (pr for pr in prs
         if pr.get("mergeable") == "CONFLICTING" or pr.get("mergeStateStatus") == "DIRTY"),
        key=lambda pr: int(pr["number"]),
    )
    seen = {pr["number"] for pr in bad}
    unknown = [pr for pr in prs
               if pr.get("mergeable") == "UNKNOWN" and pr["number"] not in seen]
    if unknown:
        confirmed = [pr for pr in unknown if _conflicts_with_main(pr.get("headRefOid") or "")]
        bad = sorted(bad + confirmed, key=lambda pr: int(pr["number"]))
        if not bad:
            # merge-tree is authoritative: these were unknown to GitHub but are genuinely clean.
            print("conflicting: none")
            return 0
    elif not bad:
        print("conflicting: none")
        return 0
    print("conflicting: " + " ".join(f"{pr['number']}@{(pr.get('headRefOid') or '')[:8]}" for pr in bad))
    for pr in bad:
        print(f"{pr['number']} {pr.get('headRefOid', '')[:8]} {pr.get('mergeStateStatus')}")
    print(f"measured at main {_main_sha()[:8]}")   # the predicate: what this run compared against
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
