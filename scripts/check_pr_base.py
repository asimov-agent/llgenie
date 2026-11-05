#!/usr/bin/env python3
"""A PR must be cut from `origin/main` itself, not from another PR (issue #845).

The defect #845 names: a kanban `worktree` task inherits the primary checkout's
CURRENTLY CHECKED-OUT branch instead of `origin/main`, so a spawned lane starts
on someone else's unmerged diff. Measured twice on 2026-10-28 — a worktree
byte-identical to another PR's head, and work committed in the primary checkout
itself. The merge-base is the test: when the branch was cut from `origin/main`
(clean, even one commit ahead), `git merge-base <base> <rev>` IS `<base>`
itself. When the branch carries commits from another open PR (cut from that
PR's tip, which is neither an ancestor of nor equal to `main`), the merge-base
is an OLDER commit — `origin/main` is not an ancestor of the head at all, so a
PR opened from such a branch would leak the other PR's diff under its own
`closes #n`.

A measure is only as good as the `main` it was measured against (issue #1734):
a clone whose `refs/remotes/origin/main` was last fetched before main advanced
judges every not-yet-anchored branch as stale, which the #845 re-anchor cycle
then re-wakes. So THIS gate, before it reads the merge-base, re-fetches the
base ref's remote `main` branch freshly (the same fetches the ci.yml guard
step and the other PR gates run), records the main sha it measured at in every
verdict, and REFUSES to judge when that fetch fails — a stale measure must
never pass, and a failed fetch must fail the gate, not fall back.

Commands:

    check_pr_base.py check --base <ref> --rev <rev>
        exit 0 when `git merge-base <base> <rev> == <base>`; exit 1 when the
        branch was not cut from the base (naming the foreign commit(s)) or when
        the base ref cannot be fetched freshly.

    check_pr_base.py report --base <ref> --rev <rev>
        print the merge-base and its verdict, exit 0 either way.

The gate is bounded to git facts (real fetch / merge-base / rev-list reads); it
writes nothing except the remote-tracking ref the fetch refreshes. `--base`
defaults to `refs/remotes/origin/main` and `--rev` to `HEAD`, the two values a
PR gate wants to compare. A caller that pins `--base <remote>/main` gets the
fresh ref of that remote.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: The ref the PR is expected to be cut from. Resolved via the merge-base itself,
#: never compared to a branch the primary checkout happens to be parked on (#845).
DEFAULT_BASE = "refs/remotes/origin/main"

TAG = "[check-pr-base]"


def _git(root: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
    return r.stdout.strip()


def _base_remote(base: str) -> str | None:
    """The remote name a base ref names, when it is a remote-tracking/`<remote>/main` shape.

    `refs/remotes/origin/main` and `origin/main` both name the `origin` remote;
    `upstream/main` names `upstream`. A bare commit-ish ref (e.g. `HEAD~1`, a sha)
    has no remote and returns None — nothing to fetch for a local comparison.
    """
    b = base
    if b.startswith("refs/remotes/"):
        b = b[len("refs/remotes/"):]
    if not b or "/" not in b:
        return None
    remote, _, _ = b.partition("/")
    return remote or None


def fetch_base(root: Path, base: str) -> tuple[list[str], str]:
    """Re-fetch `base`'s remote `main` so the merge-base is live, not a stale ref (#1734).

    Returns (warnings, error). On success `warnings` is empty (a fresh fetch is the
    norm and is silent); on failure `error` names the fetch error — the caller must
    refuse to judge then, because a stale measure must never pass. When the base ref
    names no remote (a local comparison), fetches nothing: (warnings=[], error="").
    """
    remote = _base_remote(base)
    if not remote:
        return [], ""
    # The base ref names its own remote, so that is the one to refresh — never the
    # URL-detected "best" remote, which can differ (e.g. `upstream` in a fork-origin
    # clone) and would refresh a ref this gate does not compare.
    ref = f"+refs/heads/main:refs/remotes/{remote}/main"
    r = subprocess.run(
        ["git", "-C", str(root), "fetch", "--no-tags", remote, ref],
        capture_output=True, text=True,
    )  # proc-allow: direct subprocess call site, tracked remainder for issue #797
    if r.returncode != 0:
        err = (r.stderr or r.stdout).strip()
        return [], (f"could not fetch fresh `{remote}/main` for base `{base}` " +
                    f"(exit {r.returncode}): {err[:400]} — a stale measure must never pass, "
                    f"so the gate refuses to judge without a freshly-fetched base")
    return [], ""


def _measured_sha(root: Path, base: str) -> str:
    """The main sha this gate measured against — the fresh post-fetch base ref (#1734)."""
    return _git(root, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}") or "(unresolved)"


def foreign_commits(root: Path, base: str, rev: str) -> list[str]:
    """The commits the head carries that are not on the base, newest first.

    `base..rev` — for a branch cut from another PR this is exactly the work the
    branch INHERITED from elsewhere, which is the foreign diff #845 means.
    """
    out = _git(root, "log", "--no-merges", "--oneline", "--no-decorate", f"{base}..{rev}")
    return [ln for ln in out.splitlines() if ln.strip()]


def check(root: Path, base: str, rev: str) -> tuple[bool, list[str]]:
    """Is the branch cut from `base` itself? Returns (ok, foreign_or_error_lines).

    Fetches `base`'s remote `main` freshly first (#1734), so the verdict is against
    the live main tip, not a stale `refs/remotes/origin/main`. A fetch failure is a
    refusal (False), never a stale pass. `ok` is True exactly when
    `git merge-base <base> <rev> == <base>`, i.e. when `<base>` is an ancestor of
    the head — the head adds commits on top of the base and nothing else. A
    one-commit-ahead clean branch passes (the negative control of #845); a branch
    cut from another PR has the base NOT an ancestor, so the merge-base is older
    and the head carries commits not on the base.
    """
    _warnings, err = fetch_base(root, base)
    if err:
        return False, [err]
    base_sha = _git(root, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}")
    if not base_sha:
        return False, [f"base `{base}` does not resolve to a commit in this clone"]
    mb = _git(root, "merge-base", base, rev)
    if not mb:
        return False, [f"`{base}` and `{rev}` share no common ancestor in this clone"]
    if mb.splitlines()[0] != base_sha:
        return False, foreign_commits(root, base, rev)
    return True, []


def render(ok: bool, base: str, rev: str, foreign: list[str], root: Path = REPO_ROOT) -> list[str]:
    """The verdict as lines; the OK path and the refusal both name their facts.

    Every verdict carries the main sha it measured against (#1734), so a FAILED is
    auditable at a glance and a stale measure is provable instead of assumed.
    """
    measured = f"{TAG} measured against `{base}` at `{_measured_sha(root, base)}`"
    if ok:
        return [
            f"{TAG} OK: `{rev}` is cut from `{base}` (merge-base == base) — ",
            f"{TAG} no foreign commits carried",
            measured,
        ]
    if foreign and (foreign[0].startswith("base `") or foreign[0].startswith("could not fetch ")
                    or foreign[0].startswith("`")):
        # A refusal that already names its own cause (a resolvable-base failure or a
        # fetch failure): there is no measure, so no measured-sha line is appended.
        return [f"{TAG} FAILED: {foreign[0]}"]
    # The base IS a commit and the head DOES share history; the refusal names the
    # foreign work. The merge-base is re-read in the SAME root the merge-base was
    # measured in, so the message carries the sha that proved the defect.
    mb = _git(root, "merge-base", base, rev)
    head = [f"  {f}" for f in foreign] if foreign else ["  (no commits in base..rev)"]
    return [
        f"{TAG} FAILED: `{rev}` is NOT cut from `{base}` — its merge-base with ",
        f"{TAG} `{base}` is `{mb.splitlines()[0] if mb else '(none)'}`, not `{base}` itself, ",
        f"{TAG} so the branch carries commits from another PR / another base (issue #845).",
        f"{TAG} foreign commits ({len(foreign)}):",
        *head,
        f"{TAG} The next lane to open a PR from this branch would leak that diff under ",
        f"{TAG} its own `closes #n`; rebase onto a fresh `{base}` before pushing.",
        measured,
    ]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="check_pr_base", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("check", "report"):
        c = sub.add_parser(name)
        c.add_argument("--base", default=DEFAULT_BASE, help=f"the ref the PR must be cut from (default {DEFAULT_BASE})")
        c.add_argument("--rev", default="HEAD", help="the PR head rev (default HEAD)")
        c.add_argument("--cwd", default=None, help="repository the merge-base is read from")
    args = p.parse_args(argv)
    root = Path(args.cwd) if args.cwd else REPO_ROOT
    ok, foreign = check(root, args.base, args.rev)
    for line in render(ok, args.base, args.rev, foreign, root):
        print(line)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
