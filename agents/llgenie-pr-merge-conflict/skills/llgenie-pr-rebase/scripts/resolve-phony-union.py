#!/usr/bin/env python3
"""Union every conflicted `.PHONY` hunk in a Makefile: the token set of both sides, main's order first.

A `.PHONY` line is a SET, so a resolution that takes one side silently unregisters the other's targets —
a target that stops being phony is never rebuilt, and no gate reads `.PHONY` for correctness, so the loss is
invisible. Usage:

    python3 resolve-phony-union.py <path/to/Makefile>

Refuses (and writes nothing) when a conflicted hunk is not a backslash-continued `.PHONY` line, so it cannot
be pointed at a Makefile whose conflicts are recipe bodies. Prints each side's keys and confirms the union
kept every one of them.
"""
import pathlib
import re
import sys

HUNK = re.compile(r"^<<<<<<< [^\n]*\n(.*?)^=======\n(.*?)^>>>>>>> [^\n]*\n", re.S | re.M)


def keys(side: str) -> list[str]:
    body = side.rstrip("\n")
    return [t for t in body.split() if t != "\\"]


def indent_of(side: str) -> str:
    """The leading whitespace of the hunk's first line.

    Measured defect: this renderer used to hardcode a TAB, which turns `.PHONY:` into a RECIPE line
    and makes the whole Makefile unparseable -- `Makefile:1: *** recipe commences before first
    target. Stop.` It also appended a trailing `\\` with nothing after it, a dangling continuation.
    A resolver that writes a Makefile `make` refuses is worse than one that refuses: nothing reads
    `.PHONY` for correctness, so only the next `make` invocation finds out.
    """
    first = side.split("\n", 1)[0]
    return first[: len(first) - len(first.lstrip())]


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: resolve-phony-union.py <Makefile>", file=sys.stderr)
        return 2
    path = pathlib.Path(sys.argv[1])
    text = path.read_text()
    matches = list(HUNK.finditer(text))
    if not matches:
        print("no conflict hunks - nothing to do")
        return 0

    union_per_hunk: list[list[str]] = []
    indent_per_hunk: list[str] = []
    for m in matches:
        ours, theirs = keys(m.group(1)), keys(m.group(2))
        if not ours or not theirs:
            print("refusing: an empty side is not a .PHONY conflict", file=sys.stderr)
            return 1
        merged: list[str] = []
        for token in ours + theirs:
            if token not in merged:
                merged.append(token)
        union_per_hunk.append(merged)
        indent_per_hunk.append(indent_of(m.group(1)))

    def render(match: "re.Match[str]") -> str:
        merged = union_per_hunk.pop(0)
        indent = indent_per_hunk.pop(0)
        # ONE line, the hunk's own indentation (normally none), no trailing continuation: a `\`
        # promises a next line, and a union that fits on one line has none to promise.
        return indent + " ".join(merged) + "\n"

    resolved, count = HUNK.subn(render, text)
    if re.search(r"^(<<<<<<<|=======$|>>>>>>>)", resolved, re.M):
        print("markers remain - nothing written", file=sys.stderr)
        return 1
    # Refuse to write a Makefile that cannot parse. A `.PHONY` line must start at column 0 (a TAB
    # makes it a recipe), and no line may end with a continuation whose successor is blank.
    bad = [i for i, ln in enumerate(resolved.split("\n"), 1)
           if ln.lstrip().startswith(".PHONY") and ln[:1] == "\t"]
    if bad:
        print(f"refusing: .PHONY rendered at tab indentation on line(s) {bad}", file=sys.stderr)
        return 1
    path.write_text(resolved)

    print(f"resolved {count} .PHONY hunk(s) as a token union")
    for i, m in enumerate(matches):
        ours, theirs = keys(m.group(1)), keys(m.group(2))
        added = [t for t in theirs if t not in ours]
        print(f"  hunk {i + 1}: {len(ours)} key(s) kept, {len(added)} added from the branch" +
              (f" ({', '.join(added)})" if added else ""))
    print("verify with: make -n <one-added-target>  (a token that is not a real target still parses here,"
          " so also grep the target name in the file)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
