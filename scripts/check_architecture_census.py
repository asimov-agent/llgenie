#!/usr/bin/env python3
"""Gate the architecture census in `docs/ARCHITECTURE.md` against the tree (issues #896, #1053).

The document states a census of the tree ("The tree is N tracked files: data/ 9, skills/ 17, ...")
and two table cells with the `tests/test_*.py` count and the `openspec` change count.

The census is a fact about **the tree at the sha the document names**, not about `HEAD` (#1053).
`check()` therefore:

  - counts `git ls-tree -r --name-only <named-sha>` — the referent is the pointer's tree, so a PR
    that adds or removes files but leaves `docs/ARCHITECTURE.md` untouched still passes (its doc
    names a `main` sha whose tree the numbers describe);
  - requires the pointer be a **real commit and an ancestor of `HEAD`** — a pointer to an unmerged
    branch head, or to any sha that merely has the right file count, reds before it can dangle
    after a squash-merge;
  - keeps the stale-census teeth: doc numbers that disagree with the tree at the pointer's sha
    still red, on `main` and in PRs alike.

Usage:
    python3 scripts/check_architecture_census.py check     # exit 1 on any drift
    python3 scripts/check_architecture_census.py report    # print the census at HEAD, exit 0 always

Stdlib only; runs in the repo checkout. Wired into `check-docs` via the Makefile.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _ls_names(rev: str, path: str = "") -> list[str]:
    """Tracked paths in the tree at `rev`, optionally under `path`."""
    cmd = ["git", "ls-tree", "-r", "--name-only", rev]
    if path:
        cmd += ["--", path]
    out = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT).stdout
    return [l for l in out.split("\n") if l]


def measure(rev: str = "HEAD") -> dict[str, int]:
    """The census counts for the tree at `rev` (default `HEAD`, for re-deriving the doc)."""
    tests_names = _ls_names(rev, "tests")
    changes = {l.split("/")[2] for l in _ls_names(rev, "openspec/changes")}
    return {
        "tracked": len(_ls_names(rev)),
        "data": len(_ls_names(rev, "data")),
        "skills": len(_ls_names(rev, "skills")),
        "containers": len(_ls_names(rev, "containers")),
        "tests": len(tests_names),
        "scripts": len(_ls_names(rev, "scripts")),
        "openspec": len(_ls_names(rev, "openspec")),
        "agent-wiki": len(_ls_names(rev, "agent-wiki")),
        "docs": len(_ls_names(rev, "docs")),
        "test_py": len([n for n in tests_names if n.rsplit("/", 1)[-1].startswith("test_") and n.endswith(".py")]),
        "openspec-changes": len(changes),
    }


def doc_flat() -> str:
    """Collapse whitespace/newlines so the wrapped census sentence matches one regex."""
    doc = (REPO_ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    return re.sub(r"\s+", " ", doc)


def claims(m: dict[str, int]) -> list[tuple[str, str]]:
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
    """A real, non-dangling commit (not a sha from an amend or squash that vanished)."""
    return subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"],
                          capture_output=True, cwd=REPO_ROOT).returncode == 0


def is_ancestor(sha: str, rev: str = "HEAD") -> bool:
    """True when `sha` is reachable from `rev` — a pointer must name an ancestor, never a branch head (#1053)."""
    return subprocess.run(["git", "merge-base", "--is-ancestor", sha, rev],
                          capture_output=True, cwd=REPO_ROOT).returncode == 0


def check() -> int:
    bad = 0
    stated = doc_measured_sha()
    stated_tree: str | None

    # The pointer must exist, be a real commit, AND be an ancestor of HEAD. Until it satisfies all
    # three there is no tree to compare the claims against.
    if stated is None:
        bad += 1
        print("[census-gate] measured-at: docs/ARCHITECTURE.md states no `measured at <sha>` pointer; "
              "it must name the sha its census was measured at")
        stated_tree = None
    elif not commit_is_real(stated):
        bad += 1
        print(f"[census-gate] measured-at: the doc's pointer `{stated}` is not a real commit "
              f"(dangling from an amend or squash?)")
        stated_tree = None
    elif not is_ancestor(stated):
        bad += 1
        print(f"[census-gate] measured-at: the doc's pointer `{stated}` is a real commit but NOT an "
              f"ancestor of HEAD ({short_head()}) — a pointer must name a commit reachable from this "
              f"branch, or it will dangle after the next squash-merge")
        stated_tree = None
    else:
        stated_tree = stated

    # The census describes the tree at the pointer's sha — NOT HEAD (#1053). A file-adding PR that
    # leaves the doc untouched still passes: its doc names a main sha whose tree the numbers describe.
    if stated_tree is not None:
        m = measure(stated_tree)
        ok = doc_flat()
        for label, token in claims(m):
            if token in ok:
                continue
            bad += 1
            print(f"[census-gate] {label}: the doc has no claim the tree at `{stated_tree}` already "
                  f"states as {token}")

    verdict = "OK" if bad == 0 else f"{bad} claim(s) stale"
    if stated_tree is not None:
        m = measure(stated_tree)
        print(f"[census-gate] {verdict} — measured at {stated_tree} (tracked={m['tracked']}, "
              f"testspp={m['test_py']}, changes={m['openspec-changes']})")
    else:
        print(f"[census-gate] {verdict} — no usable `measured at` pointer (HEAD={short_head()})")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="gate the ARCHITECTURE census (issues #896, #1053)")
    ap.add_argument("cmd", choices=("check", "report"))
    args = ap.parse_args()
    if args.cmd == "report":
        m = measure("HEAD")
        sha = short_head()
        print(f"measured at {sha}: " + ", ".join(f"{k}={v}" for k, v in m.items()))
        return 0
    return check()


if __name__ == "__main__":
    sys.exit(main())
