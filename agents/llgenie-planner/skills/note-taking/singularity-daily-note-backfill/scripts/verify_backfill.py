#!/usr/bin/env python3
"""Verify singularity daily-note backfill: no unchecked boxes, no blanks,
8/8 reflection bullets filled, weekly sections filled for Sundays.

Usage: python3 verify_backfill.py <vault_root> <day> [<day> ...]
Example: python3 verify_backfill.py /home/asimov/repository/git/business/singularity \
    2026-10-04 2026-10-06 2026-10-07 2026-10-08 2026-10-09 2026-10-10 2026-10-11
"""
import re
import sys

SIGNAL_TAIL = " (scattered/fearful vs coherent/powerful)"


def check_day(root, day):
    path = f"{root}/04_daily_notes/{day}.md"
    t = open(path).read()
    problems = []

    if t.count("- [ ]"):
        problems.append(f"{t.count('- [ ]')} unchecked boxes")
    if t.count("_________________"):
        problems.append(f"{t.count('_________________')} blank fields")

    i = t.find("### Reflection")
    j = t.find("\n### ", i + 5)
    lines = t[i:j].split("\n")
    idxs = [k for k, l in enumerate(lines) if re.match(r"^- \*\*.+?\*\*", l)]
    empty = []
    for n, k in enumerate(idxs):
        m = re.match(r"^- \*\*(.+?)\*\*(.*)$", lines[k])
        key, tail = m.group(1), m.group(2).strip()
        if tail == SIGNAL_TAIL.lstrip():
            tail = ""
        end = idxs[n + 1] if n + 1 < len(idxs) else len(lines)
        body = "\n".join(lines[k + 1:end]).strip()
        if not (tail or body):
            empty.append(key)
    if empty:
        problems.append(f"empty bullets: {empty}")

    weekly = "## 📅 Weekly Review Every Sunday" in t
    if weekly:
        for marker in ("Monthly Wealth Audit", f"Clarity Review — {day}", f"GAIN Review — {day}"):
            if marker not in t:
                problems.append(f"weekly section missing: {marker}")

    return problems


def main():
    root, days = sys.argv[1], sys.argv[2:]
    ok = True
    for d in days:
        probs = check_day(root, d)
        print(f"{d}: {'OK' if not probs else '; '.join(probs)}")
        if probs:
            ok = False
    print("\nALL CLEAN" if ok else "\nISSUES REMAIN")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
