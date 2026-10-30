#!/usr/bin/env python3
"""Gate the architecture census in `docs/ARCHITECTURE.md` against the tree (issues #896, #1053).

The document states a census of the tree ("The tree is N tracked files: data/ 9, skills/ 17, ...")
and two table cells with the `tests/test_*.py` count and the `openspec` change count, next to a
`measured at <sha>` pointer naming the commit it was counted on. A census is a claim about ONE
commit, so that commit — not `HEAD` — is the referent (issue #1053):

- the counts are read with `git ls-tree -r --name-only <sha>` at the sha the doc names, so a branch
  that adds a file does not have to rewrite the doc (and a pointer naming its own branch head no
  longer dangles once the PR is squashed);
- the pointer must be a real commit AND an ancestor of `HEAD`, so the census is reproducible from a
  tree this branch actually contains (the surviving half of #1043);
- a doc whose numbers disagree with the tree at that sha still fails, naming the claim it could not
  find, on `main` and in a PR alike.

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


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], capture_output=True, text=True, cwd=REPO_ROOT)


def _ls_names(path: str = "", ref: str = "HEAD") -> list[str]:
    cmd = ["ls-tree", "-r", "--name-only", ref]
    if path:
        cmd += ["--", path]
    return [l for l in _git(*cmd).stdout.split("\n") if l]


def measure(ref: str = "HEAD") -> dict[str, int]:
    """Count the census of the tree AT `ref` (never implicitly the working tree's HEAD)."""
    tracked = _ls_names(ref=ref)
    tests_names = _ls_names("tests", ref)
    changes = {l.split("/")[2] for l in _ls_names("openspec/changes", ref)}
    return {
        "tracked": len(tracked),
        "data": len(_ls_names("data", ref)),
        "skills": len(_ls_names("skills", ref)),
        "containers": len(_ls_names("containers", ref)),
        "tests": len(tests_names),
        "scripts": len(_ls_names("scripts", ref)),
        "openspec": len(_ls_names("openspec", ref)),
        "agent-wiki": len(_ls_names("agent-wiki", ref)),
        "docs": len(_ls_names("docs", ref)),
        "test_py": len([n for n in tests_names if n.rsplit("/", 1)[-1].startswith("test_") and n.endswith(".py")]),
        "openspec-changes": len(changes),
    }


def doc_flat() -> str:
    """Collapse whitespace/newlines so the wrapped census sentence matches one regex."""
    doc = (REPO_ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    return re.sub(r"\s+", " ", doc)


# How the document spells each counted claim's NUMBER, so a failure can name both values.
CLAIM_SPELLINGS = {
    "tracked": r"The tree is (\d+) tracked files",
    "openspec-changes": r"\((\d+) changes\)",
    "agent-wiki-entries": r"\((\d+) entries\)",
    "test_py": r"(\d+) `tests/test_\*\.py`",
}


def doc_stated(label: str, text: str) -> int | None:
    """The number the document itself states for `label`, or None when it states none."""
    pattern = CLAIM_SPELLINGS.get(label, rf"`{label}/` (\d+)")
    found = re.search(pattern, text)
    return int(found.group(1)) if found else None


def claims(m: dict[str, int]) -> list[tuple[str, str]]:
    """The census tokens the document must state, rendered from a measured census `m`."""
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


def short_sha(ref: str = "HEAD") -> str:
    return _git("rev-parse", "--short", ref).stdout.strip()


def doc_measured_sha() -> str | None:
    """The `measured at <sha>` pointer the document states next to its census."""
    m = re.search(r"measured at `([0-9a-f]{7,})`", doc_flat())
    return m.group(1) if m else None


def commit_is_real(sha: str) -> bool:
    """A real, non-dangling commit (not a sha from an amend that vanished)."""
    return _git("cat-file", "-e", f"{sha}^{{commit}}").returncode == 0


def commit_is_ancestor(sha: str, ref: str = "HEAD") -> bool:
    """The pointer names a commit this branch contains, so the census is reproducible from it."""
    return _git("merge-base", "--is-ancestor", sha, ref).returncode == 0


def check() -> int:
    problems: list[str] = []
    stated = doc_measured_sha()
    measured: dict[str, int] | None = None
    if stated is None:
        problems.append("measured-at: docs/ARCHITECTURE.md states no `measured at <sha>` pointer; it must "
                        "name the commit its census was counted on")
    elif not commit_is_real(stated):
        problems.append(f"measured-at: the doc's pointer `{stated}` is not a real commit (dangling from "
                        "an amend?)")
    elif not commit_is_ancestor(stated):
        problems.append(f"measured-at: the doc's pointer `{stated}` is not an ancestor of HEAD "
                        f"({short_sha()}); the census must name a commit this branch contains")
    else:
        measured = measure(stated)
        text = doc_flat()
        for label, token in claims(measured):
            if token in text:
                continue
            stated_number = doc_stated(label, text)
            doc_value = (f"the doc states {stated_number}" if stated_number is not None
                         else "the doc states no such claim")
            problems.append(f"{label}: {doc_value} but the tree at `{stated}` states {token}")

    for problem in problems:
        print(f"[census-gate] {problem}")

    m = measured if measured is not None else measure()
    verdict = ("OK" if not problems else
               f"{len(problems)} claim(s) stale" if measured is not None else
               "the census has no usable referent")
    referent = (f"referent `{stated}` is an ancestor of HEAD ({short_sha()})" if measured is not None
                else f"no usable referent; HEAD is {short_sha()}")
    print(f"[census-gate] {verdict} — census measured at `{stated or 'nowhere'}` (tracked={m['tracked']}, "
          f"testspp={m['test_py']}, changes={m['openspec-changes']}); {referent}")
    return 1 if problems else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="gate the ARCHITECTURE census (issues #896, #1053)")
    ap.add_argument("cmd", choices=("check", "report"))
    args = ap.parse_args()
    if args.cmd == "report":
        m = measure()
        print(f"measured at {short_sha()}: " + ", ".join(f"{k}={v}" for k, v in m.items()))
        print(f"doc pointer: {doc_measured_sha() or '(none)'}")
        return 0
    return check()


if __name__ == "__main__":
    sys.exit(main())
