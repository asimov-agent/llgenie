#!/usr/bin/env python3
"""Union a conflicted rulebook file (SOUL.md / SKILL.md): keep the base's text, append the branch's unseen bullets.

Both sides of a fleet-rules file add `- **rule.**` bullets, so picking a side deletes somebody's rule and the
deletion is invisible — the gate only proves the bullets the manifest declares. This keeps the base's ordering
and wording and inserts only the branch's *new* bullets after the last bullet of each conflicted block.

    python3 resolve-rule-union.py <conflicted file> [more files…]

It does NOT decide whether the branch's edit was legitimate: after running it, re-run `make check-agent-profiles`
and expect `fleet-block-drift` / `fleet-exemption-stale` findings if you regenerated a profile another lane owns.
"""
import pathlib
import re
import sys

MARK = re.compile(r"^<<<<<<< [^\n]*\n(.*?)^=======\n(.*?)^>>>>>>> [^\n]*\n", re.S | re.M)
BULLET = re.compile(r"^- \*\*|^- ")


def bullets(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if BULLET.match(line.strip())]


def union(raw: str) -> str:
    out: list[str] = []
    last = 0
    for match in MARK.finditer(raw):
        ours, theirs = match.group(1), match.group(2)
        out.append(raw[last:match.start()])
        have = {b[:80] for b in bullets(ours)}
        extra = [b for b in bullets(theirs) if b[:80] not in have]
        block = ours
        if extra:
            anchor = max((m.end() for m in re.finditer(r"^- .*$", block, re.M)), default=len(block.rstrip("\n")))
            block = block[:anchor] + "\n" + "\n".join(extra) + block[anchor:]
        out.append(block)
        last = match.end()
    out.append(raw[last:])
    return "".join(out)


def main() -> int:
    files = sys.argv[1:]
    if not files:
        print("usage: resolve-rule-union.py <conflicted file>…", file=sys.stderr)
        return 2
    for name in files:
        path = pathlib.Path(name)
        resolved = union(path.read_text())
        if MARK.search(resolved):
            print(f"UNRESOLVED {name}: markers remain", file=sys.stderr)
            return 1
        path.write_text(resolved)
        print(f"union {name}: {len(bullets(resolved))} bullet(s) total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
