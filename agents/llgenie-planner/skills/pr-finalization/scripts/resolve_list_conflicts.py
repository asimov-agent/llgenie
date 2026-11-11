#!/usr/bin/env python3
r"""Resolve a llgenie-shaped Makefile list conflict after a rebase.

Usage: python3 resolve_list_conflicts.py <path-to-Makefile> [--dry]

WHY this exists: a PR that adds a test or a make target collides with EVERY sibling PR
that does the same, because the colliding text is one long recipe line (the `test-unit`
pytest list) or one long `.PHONY`-style target list. Resolving it by hand, five times in
one session, produced two distinct defects that no other check caught:

  * a DUPLICATED list line (both sides kept) - `make -n <target>` still parses, so the
    parse check stays silent; and
  * a DROPPED continuation line (the branch's `\`-continued second line vanished), which
    silently removes the targets the branch added from the list.

Rules encoded here:
  1. main's (HEAD) line is the base: it carries main's newest entries, including files
     main RENAMED or added while the PR was open.
  2. add only the branch's own tokens - and for a pytest list, only paths that EXIST in
     the resolved tree. A stale path (e.g. `tests/test_llama_ai.py` after main renamed it
     to `tests/test_llgenie_serve.py`) makes pytest fail with "file or directory not
     found" and trips the rename guard. Dropped paths are printed, never dropped quietly.
  3. when one side has continuation lines the other lacks, main's lines come first and the
     branch's extra lines are appended.
  4. the leading TAB survives every path (a stripped TAB makes `make` die with
     "target pattern contains no '%'").

ALWAYS follow up with: `make -n <target>` (parse), a count of the list lines (no
 duplicates), a grep for the branch's continuation line, and the affected test files.
"""
import pathlib
import sys


def resolve(path: pathlib.Path, dry: bool = False) -> list[str]:
    lines = path.read_text().splitlines()
    out, i, log = [], 0, []
    while i < len(lines):
        if lines[i].startswith("<<<<<<<"):
            mid = next(k for k in range(i + 1, len(lines)) if lines[k].startswith("======="))
            end = next(k for k in range(mid + 1, len(lines)) if lines[k].startswith(">>>>>>>"))
            head, branch = lines[i + 1:mid], lines[mid + 1:end]
            if len(head) == 1 and len(branch) == 1:
                h, b = head[0], branch[0]
                ht, bt = h.split(), b.split()
                only = [x for x in bt if x not in ht]
                if "pytest" in h:
                    only = [x for x in only if x.startswith("tests/")]
                    kept = [x for x in only if pathlib.Path(x).exists()]
                    dropped = [x for x in only if x not in kept]
                    if dropped:
                        log.append(f"line {i+1}: DROPPED {dropped} (main renamed/removed it)")
                    only = kept
                    idx = ht.index("-p") if "-p" in ht else len(ht)
                    merged = ht[:idx] + only + ht[idx:]
                else:
                    merged = ht + only
                out.append(("\t" if h.startswith("\t") else "") + " ".join(merged))
                log.append(f"line {i+1}: main + {only or 'nothing branch-only'}")
            else:
                extra = [ln for ln in branch if ln not in head]
                out.extend(head)
                out.extend(extra)
                log.append(f"line {i+1}: main's {len(head)} line(s) + branch's {len(extra)} line(s)")
            i = end + 1
        else:
            out.append(lines[i])
            i += 1
    if not dry:
        path.write_text("\n".join(out) + "\n")
    return log


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--dry"]
    print("\n".join(resolve(pathlib.Path(args[0]), "--dry" in sys.argv)) or "no conflicts")
