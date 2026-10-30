#!/usr/bin/env python3
"""Gate the architecture census in `docs/ARCHITECTURE.md` against the tree (issue #896).

The document states a census of the tree ("The tree is N tracked files: data/ 9, skills/ 17, ...")
and two table cells with the `tests/test_*.py` count and the `openspec` change count. Twice in two
days that census drifted one merge behind the tree and nothing noticed until a lane tripped on the
number. This gate measures the tree with `git ls-tree -r --name-only HEAD` and fails when the
document's claims disagree, naming both values.

Usage:
    python3 scripts/check_architecture_census.py check     # exit 1 on any drift
    python3 scripts/check_architecture_census.py report    # print the census, exit 0 always

Stdlib only; runs in the repo checkout (`HEAD` = the working tree's commit). Wired into `check-docs`
via the Makefile.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _ls_names(path: str = "") -> list[str]:
    cmd = ["git", "ls-tree", "-r", "--name-only", "HEAD"]
    if path:
        cmd += ["--", path]
    out = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT).stdout
    return [l for l in out.split("\n") if l]


def measure() -> dict[str, int]:
    tracked = len(_ls_names())
    tests_names = _ls_names("tests")
    changes = {l.split("/")[2] for l in _ls_names("openspec/changes")}
    return {
        "tracked": tracked,
        "data": len(_ls_names("data")),
        "skills": len(_ls_names("skills")),
        "containers": len(_ls_names("containers")),
        "tests": len(tests_names),
        "scripts": len(_ls_names("scripts")),
        "openspec": len(_ls_names("openspec")),
        "agent-wiki": len(_ls_names("agent-wiki")),
        "docs": len(_ls_names("docs")),
        "test_py": len([n for n in tests_names if n.rsplit("/", 1)[-1].startswith("test_") and n.endswith(".py")]),
        "openspec-changes": len(changes),
    }


def doc_flat() -> str:
    """Collapse whitespace/newlines so the wrapped census sentence matches one regex."""
    doc = (REPO_ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    return re.sub(r"\s+", " ", doc)


def claims(m: dict[str, int]) -> list[tuple[str, str]]:
    ok = doc_flat()
    return [
        ("tracked", f"The tree is {m['tracked']} tracked files"),
        ("data", f"`data/` {m['data']}"),
        ("skills", f"`skills/` {m['skills']}"),
        ("containers", f"`containers/` {m['containers']}"),
        ("tests", f"`tests/` {m['tests']}"),
        ("scripts", f"`scripts/` {m['scripts']}"),
        ("openspec", f"`openspec/` {m['openspec']}"),
        ("agent-wiki", f"`agent-wiki/` {m['agent-wiki']}"),
        ("docs", f"`docs/` {m['docs']}"),
        ("openspec-changes", f"({m['openspec-changes']} changes)"),
        ("agent-wiki-entries", f"({m['agent-wiki']} entries)"),
        ("test_py", f"{m['test_py']} `tests/test_*.py`"),
    ]


def short_head() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True, cwd=REPO_ROOT).stdout.strip()


def doc_measured_sha() -> str | None:
    """The `measured at <sha>` pointer the document states next to its census."""
    m = re.search(r"measured at `([0-9a-f]{7,})`", doc_flat())
    return m.group(1) if m else None


def commit_is_real(sha: str) -> bool:
    """A real, non-dangling commit (not a sha from an amend that vanished)."""
    return subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"],
                          capture_output=True, cwd=REPO_ROOT).returncode == 0


def tracked_at(sha: str) -> int:
    out = subprocess.run(["git", "ls-tree", "-r", "--name-only", sha],
                         capture_output=True, text=True, cwd=REPO_ROOT).stdout
    return len([l for l in out.split("\n") if l])


def check() -> int:
    m = measure()
    ok = doc_flat()
    bad = 0
    for label, token in claims(m):
        if token in ok:
            continue
        bad += 1
        print(f"[census-gate] {label}: the doc has no claim the tree already states as {token}")
    sha = short_head()
    stated = doc_measured_sha()
    if stated is None:
        bad += 1
        print("[census-gate] measured-at: the doc states no `measured at <sha>` pointer; it must name the sha it was measured at")
    elif not commit_is_real(stated):
        bad += 1
        print(f"[census-gate] measured-at: the doc's pointer `{stated}` is not a real commit (dangling from an amend?)")
    else:
        at_head = m["tracked"]
        at_stated = tracked_at(stated)
        if at_stated != at_head:
            bad += 1
            print(f"[census-gate] measured-at: the doc was measured at `{stated}` (a {at_stated}-file tree) but HEAD is "
                  f"a {at_head}-file tree — the census was not measured against the tree the gate sees. Re-derive it now.")
    verdict = "OK" if bad == 0 else f"{bad} claim(s) stale"
    print(f"[census-gate] {verdict} — measured at {sha} (tracked={m['tracked']}, " +
          f"testspp={m['test_py']}, changes={m['openspec-changes']})")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="gate the ARCHITECTURE census (issue #896)")
    ap.add_argument("cmd", choices=("check", "report"))
    args = ap.parse_args()
    if args.cmd == "report":
        m = measure()
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
        print(f"measured at {sha}: " + ", ".join(f"{k}={v}" for k, v in m.items()))
        return 0
    return check()


if __name__ == "__main__":
    sys.exit(main())
