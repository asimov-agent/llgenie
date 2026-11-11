#!/usr/bin/env python3
"""Drive a rebase to completion, resolving every conflict as a UNION of both sides.

llgenie's rebase conflicts are additive by construction: the `.PHONY:` continuation
block, the newest `CHANGES.md` row and the `README.md` docs-reference table are all
append-only lists. Taking either side silently drops a target, an index row or a doc
link, and the docs/wiring gates then red on a branch that looks resolved.

Usage (inside the branch's own worktree, mid-rebase or before starting one):

    python3 resolve_union_conflicts.py              # finish the rebase already in progress
    python3 resolve_union_conflicts.py --start main # git rebase origin/main first

`CHANGES.md` is the one file where ORDER carries meaning (newest first, and during a
rebase "theirs" is the commit being replayed), so the branch's row goes ABOVE the
base's. Every other file keeps the base's line first, then the branch's.

After it exits 0 you MUST still prove the result:
`make -s check-wiring check-docs lint` (a duplicated or dropped row is a red gate, and a
stray conflict marker is invisible to git — grep for `<<<<<<<` before committing).
"""

import re
import subprocess
import sys

BLOCK = re.compile(r"<<<<<<<[^\n]*\n(.*?)=======\n(.*?)>>>>>>>[^\n]*\n", re.S)


def sh(*args):
    return subprocess.run(args, capture_output=True, text=True)


def conflicted():
    out = sh("git", "status", "--porcelain").stdout
    return [line[3:] for line in out.splitlines() if line[:2] in ("UU", "AA")]


def resolve(path):
    text = open(path).read()
    if "<<<<<<<" not in text:
        return 0
    sep = (lambda a, b: b + a) if path.endswith("CHANGES.md") else (lambda a, b: a + b)
    new, count = BLOCK.subn(lambda m: sep(m.group(1), m.group(2)), text)
    if "<<<<<<<" in new or ">>>>>>>" in new:
        raise SystemExit(f"{path}: markers survive the union — resolve this file by hand")
    open(path, "w").write(new)
    return count


def main():
    if "--start" in sys.argv:
        base = sys.argv[sys.argv.index("--start") + 1]
        res = sh("git", "rebase", f"origin/{base}")
        print((res.stdout + res.stderr).strip().splitlines()[-1:])

    idle = 0
    for _ in range(60):
        files = conflicted()
        if files:
            idle = 0
            for path in files:
                print(f"{path}: {resolve(path)} block(s) unioned")
                sh("git", "add", path)
            res = sh("git", "-c", "core.editor=true", "rebase", "--continue")
            out = (res.stdout + res.stderr).strip()
            print("continue:", out.splitlines()[-1] if out else res.returncode)
            if res.returncode != 0 and "Could not apply" not in out:
                print(out)
                return 1
            continue

        # git can stop with nothing conflicted when rerere replays a previous
        # resolution, or the patch was already applied: just continue again.
        res = sh("git", "-c", "core.editor=true", "rebase", "--continue")
        out = (res.stdout + res.stderr).strip()
        if res.returncode == 0:
            print("rebase complete:", sh("git", "log", "--oneline", "-1").stdout.strip())
            return 0
        if "no rebase in progress" in out.lower():
            print("no rebase in progress")
            return 0
        idle += 1
        if idle > 3:
            print(out)
            return 1
    print("gave up after 60 rounds")
    return 1


if __name__ == "__main__":
    sys.exit(main())
