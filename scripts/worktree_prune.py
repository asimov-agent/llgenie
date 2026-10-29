"""Prune the worktrees and local branches whose PR already merged — proven by the PR, not by ancestry (#431).

Every merged PR leaves a worktree under `../llgenie-wt/` and a local `feat/*` branch behind. The
agent stops at the PR (the merge is the reviewer's action), so no agent step ever sees the merge, and
nothing swept the debris after the watch-loop dispatcher — and its `cleanup_merged_worktrees()` — was
removed in `99ce5b9` (#211). Measured on this host on 2026-10-20: 138 local branches, 93 worktrees,
955 MB, zero open PRs.

The obvious test — "is the branch's HEAD an ancestor of `origin/main`?" — cannot work here, because
this repository **squash-merges**: the squashed commit on `main` is a new commit, so the branch tip is
never an ancestor and `git branch --merged` reports the work as unmerged forever. The only evidence
that survives a squash merge is the PR itself, so eligibility is read from GitHub and from nowhere
else:

* a branch is prunable only when it is the `headRefName` of a MERGED PR, and
* that PR's `mergeCommit.oid` is an ancestor of the base (`origin/main` by default).

Everything else is kept **with its reason printed**: a branch naming an OPEN or CLOSED PR, a branch
naming no PR at all, a branch whose merge commit is not on the base, a dirty worktree, a detached
worktree (it holds no branch, so no merge can license deleting it) and the repository's main checkout.

`--dry` prints the same plan and mutates nothing. Any failure — the `gh` lookup, a `git worktree
remove`, a `git branch -D` — exits 2 naming the branch and the step, and never continues past a failed
worktree removal to delete that branch.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import base_ref  # noqa: E402  (the base ref resolver, issue #925)

#: The base a merge commit must be an ancestor of, unless `--base` says otherwise. RESOLVED, not assumed
#: (issue #925): deciding that a branch is merged by testing ancestry against `origin/main` is only correct in
#: a clone whose `origin` is the BASE repository. In this host's other layout `origin` is the owner's fork, so
#: the sweep would judge branches against a different tree - and this is the sweep that DELETES worktrees.
DEFAULT_BASE = None


def default_base() -> str:
    """The base to test ancestry against, resolved from this clone's remotes (issue #925)."""
    if DEFAULT_BASE:
        return str(DEFAULT_BASE)
    return base_ref.resolve_base(quiet=True)

#: How many PRs one lookup reads. The repository has never held more than 500.
PR_LIMIT = "500"

#: The label every line of output carries, so a prune is greppable in a long log.
TAG = "[worktree-prune]"

#: Exit code for a hard failure (a failed lookup or git step), never a silent partial prune.
EXIT_FAILURE = 2


class PruneError(RuntimeError):
    """A step that must stop the prune: a failed lookup or a failed git operation."""


@dataclass
class Worktree:
    """One entry of `git worktree list --porcelain`."""

    path: str
    head: str = ""
    branch: str | None = None
    detached: bool = False
    bare: bool = False


@dataclass
class Decision:
    """What the prune decided about one local branch, and why."""

    branch: str
    action: str  # "prune" | "keep"
    reason: str
    pr: int | None = None
    path: str | None = None

    @property
    def prunable(self) -> bool:
        return self.action == "prune"


@dataclass
class Outcome:
    """The result of applying (or drying) a plan."""

    decisions: list[Decision] = field(default_factory=list)
    removed_branches: list[str] = field(default_factory=list)
    removed_worktrees: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def kept(self) -> list[Decision]:
        return [d for d in self.decisions if not d.prunable]


def _run(args: list[str], *, cwd: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """One subprocess call. With `check`, a non-zero exit raises `PruneError` naming the step."""
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise PruneError(f"{' '.join(args)} failed: {detail}")
    return result


def _git(args: list[str], *, cwd: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return _run(["git", *args], cwd=cwd, check=check)


def repo_root(cwd: str | None = None) -> str:
    """The worktree root the prune operates on."""
    return _git(["rev-parse", "--show-toplevel"], cwd=cwd).stdout.strip()


def worktrees(cwd: str | None = None) -> list[Worktree]:
    """Every worktree git knows about, the main checkout first (git's own order)."""
    blocks: list[Worktree] = []
    current: Worktree | None = None
    for line in _git(["worktree", "list", "--porcelain"], cwd=cwd).stdout.splitlines():
        if line.startswith("worktree "):
            current = Worktree(path=line[len("worktree ") :])
            blocks.append(current)
        elif current is None:
            continue
        elif line.startswith("HEAD "):
            current.head = line[len("HEAD ") :]
        elif line.startswith("branch "):
            current.branch = line[len("branch ") :].replace("refs/heads/", "", 1)
        elif line.strip() == "detached":
            current.detached = True
        elif line.strip() == "bare":
            current.bare = True
    return blocks


def local_branches(cwd: str | None = None) -> list[str]:
    """Every local branch name, in refname order."""
    out = _git(["for-each-ref", "--format=%(refname:short)", "refs/heads"], cwd=cwd).stdout
    return [line.strip() for line in out.splitlines() if line.strip()]


def pull_requests(repo: str, cwd: str | None = None) -> dict[str, list[dict]]:
    """`headRefName` -> the PRs opened from it, read from GitHub through `gh`.

    Every state is read in ONE call so a branch naming a CLOSED or OPEN PR can be told apart from a
    branch naming nothing at all — the two keep reasons differ.
    """
    out = _run(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "all",
            "--limit",
            PR_LIMIT,
            "--json",
            "number,state,headRefName,mergeCommit",
        ],
        cwd=cwd,
    ).stdout
    try:
        rows = json.loads(out or "[]")
    except json.JSONDecodeError as exc:  # a corrupt answer must not read as "no PRs"
        raise PruneError(f"gh pr list returned no readable JSON: {exc}") from exc
    by_head: dict[str, list[dict]] = {}
    for row in rows:
        by_head.setdefault(str(row.get("headRefName") or ""), []).append(row)
    return by_head


def is_ancestor(oid: str, base: str, cwd: str | None = None) -> bool:
    """Is `oid` reachable from `base`? The one question a squash merge cannot fake."""
    if not oid:
        return False
    return _git(["merge-base", "--is-ancestor", oid, base], cwd=cwd, check=False).returncode == 0


def is_dirty(path: str, cwd: str | None = None) -> bool:
    """Does the worktree hold a change git would lose? Unknown counts as dirty (fail safe)."""
    result = _git(["status", "--porcelain"], cwd=path, check=False)
    if result.returncode != 0:
        return True
    return bool(result.stdout.strip())


def _merged(entries: list[dict]) -> dict | None:
    """The merged PR a branch names, if any. A branch can name several over its life."""
    for row in entries:
        if str(row.get("state", "")).upper() == "MERGED":
            return row
    return None


#: The path git names in `cannot delete branch '…' used by worktree at '<path>'` (issue #593).
_REFUSED_BY = re.compile(r"used by worktree at '([^']+)'")


def _refused_by_worktree(message: str) -> str | None:
    """The worktree path a `git branch -D` refusal names, or None when it names none."""
    m = _REFUSED_BY.search(message or "")
    return m.group(1) if m else None


def _detached_and_clean(path: str, cwd: str | None = None) -> bool:
    """Whether `path` is a worktree git reports as branch-line-less and detached, holding no changes.

    That is the only shape `apply()` may remove on a `branch -D` refusal: no branch is checked out
    there, so nothing of anyone's work depends on the directory, and a dirty one is refused (the same
    rule the planner applies to every other worktree).
    """
    for tree in worktrees(cwd):
        if os.path.realpath(tree.path) == os.path.realpath(path):
            if tree.branch or not tree.detached:
                return False
            return not is_dirty(tree.path, cwd=cwd)
    return False


def plan(
    base: str,
    branches: list[str],
    trees: list[Worktree],
    prs: dict[str, list[dict]],
    cwd: str | None = None,
    current: str | None = None,
) -> list[Decision]:
    """Decide, with a printed reason, what happens to every local branch. Mutates nothing.

    `current` is the worktree this run is executing in: git refuses to remove the directory it is
    standing in, so it is never a candidate — running the prune from a merged branch's own worktree
    must report that instead of failing on it.
    """
    main_checkout = trees[0].path if trees else None
    tree_by_branch = {t.branch: t for t in trees if t.branch}
    # A DETACHED worktree carries no branch name, so `tree_by_branch` can never match it — while git
    # still refuses `git branch -D` for a branch that worktree holds, and removing the branch first
    # strands the directory with no ref (issue #570: the plan said "prune 1 branches, 0 worktrees" and
    # `branch -D` then failed the whole sweep forever). Match it by HEAD instead: one detached
    # worktree parked on this branch's tip IS its checkout, and it is removed before the branch.
    detached_by_head: dict[str, list[Worktree]] = {}
    for t in trees:
        if t.detached and t.head:
            detached_by_head.setdefault(t.head, []).append(t)
    decisions: list[Decision] = []

    for branch in branches:
        entries = prs.get(branch) or []
        merged = _merged(entries)
        if merged is None:
            if entries:
                row = sorted(entries, key=lambda r: int(r.get("number") or 0))[-1]
                state = str(row.get("state") or "UNKNOWN").upper()
                decisions.append(
                    Decision(branch, "keep", f"PR #{row.get('number')} is {state} (unmerged)", pr=int(row.get("number") or 0) or None)
                )
            else:
                decisions.append(Decision(branch, "keep", "names no PR at all"))
            continue

        number = int(merged.get("number") or 0) or None
        merge_oid = str((merged.get("mergeCommit") or {}).get("oid") or "")
        if not merge_oid:
            decisions.append(Decision(branch, "keep", f"PR #{number} carries no merge commit", pr=number))
            continue
        if not is_ancestor(merge_oid, base, cwd=cwd):
            decisions.append(
                Decision(branch, "keep", f"PR #{number}'s merge commit {merge_oid[:9]} is not on {base}", pr=number)
            )
            continue

        tree = tree_by_branch.get(branch)
        if tree is None:
            # The branch may still be checked out somewhere detached at exactly its tip.
            tip = _git(["rev-parse", "--verify", branch], cwd=cwd, check=False).stdout.strip()
            candidates = detached_by_head.get(tip) or []
            if len(candidates) == 1:
                tree = candidates[0]
        if tree is not None and main_checkout is not None and tree.path == main_checkout:
            decisions.append(Decision(branch, "keep", "checked out in the repository's main checkout", pr=number))
            continue
        if tree is not None and current is not None and tree.path == current:
            decisions.append(Decision(branch, "keep", "is the worktree this run is executing in", pr=number, path=tree.path))
            continue
        if tree is not None and is_dirty(tree.path, cwd=cwd):
            decisions.append(Decision(branch, "keep", f"worktree {tree.path} holds uncommitted changes", pr=number, path=tree.path))
            continue

        decisions.append(Decision(branch, "prune", f"PR #{number} merged, its merge commit is on {base}", pr=number, path=tree.path if tree else None))

    return decisions


def apply(decisions: list[Decision], cwd: str | None = None) -> Outcome:
    """Run the plan for real: remove each prunable worktree, then delete its branch.

    A failed worktree removal keeps the branch: deleting the branch first would strand the worktree
    with no ref, which is how a prune leaves a directory nobody can explain.
    """
    outcome = Outcome(decisions=decisions)
    for decision in decisions:
        if not decision.prunable:
            continue
        if decision.path:
            try:
                _git(["worktree", "remove", decision.path], cwd=cwd)
            except PruneError as exc:
                outcome.errors.append(f"{decision.branch}: could not remove worktree {decision.path}: {exc}")
                continue
            outcome.removed_worktrees.append(decision.path)
        try:
            _git(["branch", "-D", decision.branch], cwd=cwd)
        except PruneError as exc:
            # `git branch -D` is the only authority on which worktree holds a branch: the planner read
            # `worktree list`, and a worktree can refuse a delete while that listing shows it as pure
            # `detached` with no branch line (issue #593). When the refusal names such a worktree —
            # detached, branch-less, clean — that directory is debris of the branch being pruned: remove
            # it and retry the delete ONCE. A named worktree is another checkout and is never touched.
            holder = _refused_by_worktree(str(exc))
            if holder and _detached_and_clean(holder, cwd=cwd):
                try:
                    _git(["worktree", "remove", holder], cwd=cwd)
                    outcome.removed_worktrees.append(holder)
                    _git(["branch", "-D", decision.branch], cwd=cwd)
                except PruneError as retry_exc:
                    outcome.errors.append(
                        f"{decision.branch}: could not delete the branch even after removing the "
                        f"detached worktree {holder}: {retry_exc}")
                    continue
                print(f"{TAG} removed the detached worktree {holder} holding {decision.branch} "
                      f"(issue #593), then deleted the branch")
                outcome.removed_branches.append(decision.branch)
                continue
            if holder:
                # A worktree that git says holds the branch and that is NOT removable debris — a
                # branch checked out there, or uncommitted/unmerged work in it — is the planner's
                # own KEEP case ("a dirty worktree"): say so and move on. Erroring here is what made
                # `make worktree-prune` exit 2 forever on this checkout (issue #593), and refusing to
                # touch someone's half-merged tree is the correct behaviour, not a failure.
                decision.action = "keep"
                decision.reason = (f"held by the worktree {holder} (a branch is checked out there, "
                                   f"or it holds uncommitted/unmerged work)")
                continue
            outcome.errors.append(f"{decision.branch}: could not delete the branch: {exc}")
            continue
        outcome.removed_branches.append(decision.branch)
    return outcome


def render(outcome: Outcome, *, dry: bool, base: str) -> list[str]:
    """The lines a run prints: one per decision, then one summary. Never a value, always a count."""
    lines = []
    for decision in outcome.decisions:
        if decision.prunable:
            where = f" worktree={decision.path}" if decision.path else ""
            lines.append(f"{TAG} {'would prune' if dry else 'prune'} {decision.branch} — {decision.reason}{where}")
        else:
            lines.append(f"{TAG} keep {decision.branch} — {decision.reason}")
    verb = "would prune" if dry else "pruned"
    worktree_count = sum(1 for d in outcome.decisions if d.prunable and d.path)
    lines.append(
        f"{TAG} {verb} {len(outcome.removed_branches) if not dry else sum(1 for d in outcome.decisions if d.prunable)} "
        f"branches, {worktree_count} worktrees; kept {len(outcome.kept)} "
        f"(base {base})"
    )
    return lines


def prune(*, repo: str, base: str | None = None, dry: bool = False, cwd: str | None = None) -> Outcome:
    """Read the tree and GitHub, decide, and (unless `dry`) apply."""
    base = base or default_base()
    root = repo_root(cwd)
    trees = worktrees(cwd)
    prs = pull_requests(repo, cwd)
    decisions = plan(base, local_branches(cwd), trees, prs, cwd=cwd, current=root)
    if dry:
        return Outcome(decisions=decisions)
    return apply(decisions, cwd=root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prune worktrees and branches whose PR already merged (#431).")
    parser.add_argument("--repo", default="asimov-agent/llgenie", help="the slug `gh pr list` reads (default asimov-agent/llgenie)")
    parser.add_argument("--base", default=None,
                        help="the ref a merge commit must be on (default: resolved from this clone's "
                             "remotes, issue #925)")
    parser.add_argument("--dry", action="store_true", help="print the plan and mutate nothing")
    parser.add_argument("--cwd", default=None, help="the repository to prune (default: the current directory)")
    args = parser.parse_args(argv)

    try:
        outcome = prune(repo=args.repo, base=args.base, dry=args.dry, cwd=args.cwd)
    except PruneError as exc:
        print(f"{TAG} FAILED: {exc}", file=sys.stderr)
        return EXIT_FAILURE

    for line in render(outcome, dry=args.dry, base=args.base):
        print(line)
    for error in outcome.errors:
        print(f"{TAG} FAILED: {error}", file=sys.stderr)
    return EXIT_FAILURE if outcome.errors else 0


if __name__ == "__main__":
    sys.exit(main())
