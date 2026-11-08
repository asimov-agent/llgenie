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

    check_pr_base.py check --base <ref> --rev <rev> [--head-ref-name <branch>] [--pr-number <n>]
        exit 0 when `git merge-base <base> <rev> == <base>`; exit 0 also when
        `base..rev` is EMPTY (the head is an ancestor of the live base — a push to
        main whose commit a newer main already overtook, where nothing foreign can
        leak, issue #1867/#1906..#1909); exit 0 also for a STALE-BUT-CLEAN branch
        (merge-base on `main` but older, every carry the branch's own, issue #2016);
        exit 1 when the branch was not cut from the base AND carries foreign commits
        (naming them) or when the base ref cannot be fetched freshly. On a branch the
        PR's head is checked out as its MERGE ref (`linux / unit`), pass
        `--head-ref-name <PR_BRANCH>` / `--pr-number <PR_NUM>` so the branch's own refs
        count as OWN and are never mis-reported foreign (issue #2138).

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
    r = subprocess.run(["git", "-C", str(root), "fetch", "--no-tags", remote, ref], capture_output=True, text=True)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
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


def _own_vs_foreign(root: Path, base: str, rev: str,
                    head_ref_name: str | None = None,
                    pr_number: str | None = None) -> tuple[list[str], list[str]]:
    """Split `base..rev` into the branch's OWN commits and genuine foreign (#845) commits.

    A commit the head carries that does not belong to this branch is reachable from a
    ref that is NOT the base and does NOT contain the head: it was added on ANOTHER
    branch/PR and inherited under the head's closes. The discriminator is reachability
    (`for-each-ref --contains`, one call per commit): for a clean-but-stale branch (cut
    from an older real main tip, carrying only its own work) every commit in `base..rev`
    is reachable ONLY from the base's history and the head's own branch — no other ref
    contains it. For the genuine #845 leak (a worktree that inherited the primary
    checkout's parked branch) the inherited PR's commits ARE contained by that other
    branch's ref, so they are provably foreign.

    The head's OWN refs are not just the refs that CONTAIN `rev`. In the `linux / unit`
    checkout GitHub checks out the PR **merge ref** (a synthetic 2-parent commit), so
    `rev` is that merge and the branch's own remote ref — which points at the head
    commit, an ancestor of the merge — does NOT contain `rev` (issue #2138). If the
    discriminator trusted only ``--contains rev`` it would see the branch's own remote
    ref as a foreign signal and accuse the branch of carrying a leak it never made. The
    head's own refs are therefore also the refs that NAME the head branch
    (`refs/heads/<branch>` and `refs/remotes/origin/<branch>`, from the PR's
    `head_ref_name`) and the PR's synthetic merge/head refs (`refs/pull/<n>/merge`,
    `refs/pull/<n>/head`), none of which is a foreign-signal for the branch's own work.
    A commit reachable only from those (plus the base) is OWN; one reachable from any
    other branch/tag/PR ref is genuinely foreign.

    `own` returns the commits attributable to the branch; `foreign` the ones reachable
    from another ref. The base ref itself, the head's own refs, and the PR's own refs
    are skipped — every other branch/tag/PR ref is a foreign-signal.
    """
    commits = foreign_commits(root, base, rev)
    own, foreign = [], []
    if not commits:
        return own, foreign
    head_refs = set(_git(root, "for-each-ref", "--contains",
                         rev, "--format=%(refname)").splitlines())
    own_refs = set(head_refs)
    if head_ref_name:
        # The head branch's own refs, whether or not they contain the (possibly merge)
        # `rev` — a branch ref pointing at the head commit is the PR's own lineage even
        # when the merge-base with `base` is not `base` itself (issue #2138).
        for line in _git(root, "for-each-ref",
                         "--format=%(refname)").splitlines():
            if line in (f"refs/heads/{head_ref_name}",
                        f"refs/remotes/origin/{head_ref_name}"):
                own_refs.add(line)
    if pr_number:
        own_refs.add(f"refs/pull/{pr_number}/head")
        own_refs.add(f"refs/pull/{pr_number}/merge")
    for commit in commits:
        sha = commit.split()[0] if commit.split() else None
        if not sha:
            own.append(commit)
            continue
        containing = [r for r in _git(root, "for-each-ref", "--contains", sha, "--format=%(refname)").splitlines()
                      if r != base and r not in own_refs]
        if containing:
            foreign.append(f"{commit}  (reachable from `{'`, `'.join(containing)}`)")
        else:
            own.append(commit)
    return own, foreign



def _verdict(root: Path, base: str, rev: str,
             head_ref_name: str | None = None,
             pr_number: str | None = None) -> tuple[str, list[str], list[str]]:
    """Classify the head against `base`. Returns (verdict, own_commits, foreign_commits).
    """
    _warnings, err = fetch_base(root, base)
    if err:
        return "refused", [], [err]
    base_sha = _git(root, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}")
    if not base_sha:
        return "refused", [], [f"base `{base}` does not resolve to a commit in this clone"]
    mb = _git(root, "merge-base", base, rev)
    if not mb:
        return "refused", [], [f"`{base}` and `{rev}` share no common ancestor in this clone"]
    mb = mb.splitlines()[0]
    if mb == base_sha:
        return "clean", [], []
    foreign = foreign_commits(root, base, rev)
    if not foreign:
        # merge-base != base but `base..rev` empty: the head IS an ancestor of the live
        # base — a push to main overtaken by a newer main (#1867/#1906..#1909). No diff
        # to leak; passes as the ANCESTOR exemption.
        return "clean", [], []
    own, leaked = _own_vs_foreign(root, base, rev, head_ref_name, pr_number)
    # Is the merge-base itself on `main`'s history (an older real main tip)? If YES and
    # nothing leaked from another ref, the branch is stale-but-clean. If the merge-base
    # is off `main` entirely, the branch forked from a divergent lineage — that IS a leak.
    on_main = subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", mb, base],  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
                             capture_output=True, text=True).returncode == 0
    if on_main and not leaked:
        return "stale", own, []
    return "foreign", own, leaked or foreign


def staleness_from_compare(compare: dict) -> bool:
    """Is the head of a GitHub `compare` payload behind the base? THE staleness definition.

    This is the single source both `check-pr-base`'s verdict and the rebase sweep's eligibility
    read (#2071, #845): a head is behind iff its **merge-base with the base is not the base tip**.
    The `compare` endpoint answers exactly those three facts —
    `merge_base_commit.sha`, `base_commit.sha`, `behind_by` — so a consumer that only has REST
    access (the rebase sweep, on a remote PR head the runner never fetched) can apply the same
    rule the local git gate applies, instead of restating it in a second place where the two
    could drift.

    `merge_base_commit` is the authoritative field; `behind_by` is cross-checked only when both
    are present, so a payload shape change surfaces as a disagreement rather than a silent
    "not behind".
    """
    mb = ((compare.get("merge_base_commit") or {}).get("sha") or "")
    tip = ((compare.get("base_commit") or {}).get("sha") or "")
    if mb and tip:
        behind = mb != tip
        if "behind_by" in compare:
            # Both signals must agree: a mismatch means the payload is not what we think it is.
            return behind or bool(compare.get("behind_by"))
        return behind
    return bool(compare.get("behind_by"))


def check(root: Path, base: str, rev: str,
          head_ref_name: str | None = None,
          pr_number: str | None = None) -> tuple[bool, list[str]]:
    """Is the branch cut from `base` itself? Returns (ok, foreign_or_error_lines).

    Fetches `base`'s remote `main` freshly first (#1734), so the verdict is against
    the live main tip, not a stale `refs/remotes/origin/main`. A fetch failure is a
    refusal (False), never a stale pass. `ok` is True for a clean cut, the
    #1867 ancestor/push exemption, and a STALE-BUT-CLEAN branch (merge-base on `main`,
    every carry the branch's own — issue #2016: a rebase clears it, not a #845 leak).
    `ok` is False only for a genuine #845 foreign-branch leak (a carry belonging to
    another ref) or a refused measure.
    """
    verdict, _own, foreign = _verdict(root, base, rev, head_ref_name, pr_number)
    return verdict in ("clean", "stale"), foreign


def render(ok: bool, base: str, rev: str, foreign: list[str], root: Path = REPO_ROOT,
           head_ref_name: str | None = None,
           pr_number: str | None = None) -> list[str]:
    """The verdict as lines; the OK/stale path and the refusal both name their facts.

    Every verdict carries the main sha it measured against (#1734), so a FAILED is
    auditable at a glance and a stale measure is provable instead of assumed. The pass
    path distinguishes the three shapes a green verdict can take from the git facts:
    the ordinary clean cut (merge-base == base), the ancestor/push-to-main exemption
    (`base..rev` empty, #1867/#1906..#1909), and the STALE-BUT-CLEAN branch (merge-base
    IS a `main` ancestor but older than the live tip, every carry the branch's own,
    issue #2016 — a rebase clears it, not a #845 leak).
    """
    verdict, own, leaked = _verdict(root, base, rev, head_ref_name, pr_number)
    measured = f"{TAG} measured against `{base}` at `{base and _measured_sha(root, base)}`"
    if verdict == "clean":
        mb = _git(root, "merge-base", base, rev)
        if mb and mb.splitlines()[0] != _measured_sha(root, base):
            return [
                f"{TAG} OK: `{rev}` is an ANCESTOR of `{base}` (`base..rev` empty) — ",
                f"{TAG} a push to main overtaken by a newer main; no foreign commit can leak",
                measured,
            ]
        return [
            f"{TAG} OK: `{rev}` is cut from `{base}` (merge-base == base) — ",
            f"{TAG} no foreign commits carried",
            measured,
        ]
    if verdict == "stale":
        mb = _git(root, "merge-base", base, rev)
        return [
            f"{TAG} STALE: `{rev}` is behind `{base}` — its merge-base with ",
            f"{TAG} `{base}` is `{mb.splitlines()[0] if mb else '(none)'}`, an OLDER ",
            f"{TAG} `{base}` ancestor, and every commit it carries is its OWN (nothing is ",
            f"{TAG} reachable from another ref). It is NOT the #845 foreign-commit leak — no ",
            f"{TAG} foreign diff present. Rebase onto a fresh `{base}` before opening/pushing.",
            f"{TAG} own commits carried ({len(own)}):",
            *([f"  {c}" for c in own] or ["  (none)"]),
            measured,
        ]
    # A refusal (verdict == "refused") or a genuine #845 leak. A refusal already names
    # its own cause (a fetch failure / unresolvable base / no-common-ancestor): no
    # measured-sha line is appended because there is no measure.
    if verdict == "refused" or (foreign and foreign[0].startswith(("base `", "could not fetch ", "`"))):
        refused = foreign[0] if foreign else (leaked[0] if leaked else "(no measure)")
        return [f"{TAG} FAILED: {refused}"]
    # The base IS a commit and the head DOES share history; the refusal names the
    # foreign work. The merge-base is re-read in the SAME root the merge-base was
    # measured in, so the message carries the sha that proved the defect.
    mb = _git(root, "merge-base", base, rev)
    head = [f"  {f}" for f in (leaked or foreign)] if (leaked or foreign) else ["  (no commits in base..rev)"]
    return [
        f"{TAG} FAILED: `{rev}` is NOT cut from `{base}` — its merge-base with ",
        f"{TAG} `{base}` is `{mb.splitlines()[0] if mb else '(none)'}`, not `{base}` itself, ",
        f"{TAG} so the branch carries commits from another PR / another base (issue #845).",
        f"{TAG} foreign commits ({len(leaked or foreign)}):",
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
        c.add_argument("--head-ref-name", "--pr-branch", default=None,
                       help="the PR's head branch name (its refs are the head's OWN, not a "
                            "foreign signal even when `rev` is the merge ref — issue #2138)")
        c.add_argument("--pr-number", default=None,
                       help="the PR number, for the `refs/pull/<n>/{head,merge}` own refs (issue #2138)")
        c.add_argument("--cwd", default=None, help="repository the merge-base is read from")
    args = p.parse_args(argv)
    root = Path(args.cwd) if args.cwd else REPO_ROOT
    ok, foreign = check(root, args.base, args.rev, args.head_ref_name, args.pr_number)
    for line in render(ok, args.base, args.rev, foreign, root,
                       args.head_ref_name, args.pr_number):
        print(line)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
