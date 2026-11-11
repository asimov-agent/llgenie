# Proving a gate gates, and proving a diff does not revert

A lane reporting "gate added, verified green" hands you two claims at once: that the new gate detects the
class it was written for, and that the diff contains only what the issue asked. Both are cheap to settle
and both are routinely false. Settle them before routing the PR onward.

## A gate that has only ever been observed GREEN is unproven

`rc=0` proves the script does not crash. It does not prove the gate can fail — an inverted matcher, a regex
that never matches, or a loop over an empty set all exit 0 forever while catching nothing. Prove the gate
gates by breaking the invariant it exists to catch, in a throwaway tree, then restoring it:

```bash
make <gate>; echo rc=$?                 # expect 0
cp <file-with-cited-anchor> /tmp/anchor.bak
sed -i 's|<a real cited symbol>|<a symbol that does not exist>|' <file-with-cited-anchor>
make <gate>; echo rc=$?                 # MUST be non-zero, and MUST name Makefile:<line>
cp /tmp/anchor.bak <file-with-cited-anchor>
make <gate>; echo rc=$?                 # expect back to 0
git status --porcelain                  # MUST be empty
```

A gate you could break without it going red is not a gate; report that as the finding, not as "green".

- **Never read a make target's verdict through a pipe.** `make x | tail -3` returns `tail`'s exit code, so a
  red gate prints as `rc=0`. Run it unpiped (output is auto-truncated) or read `${PIPESTATUS[0]}`. This is the
  single most common way a planner talks itself into a false green.
- **Quote the failing line, not just the non-zero code.** `make: *** [Makefile:<n>: <target>] Error 1` names
  the target that failed; a bare rc does not distinguish the gate from a missing prerequisite.

## A "read-only" reporter is proven by a clean tree, not by its claim

A reporting tool (a parity/drift/lint reporter documented as "reports without modifying") is only read-only if
it leaves the tree byte-identical. After running it:

```bash
make <report-target> > /tmp/report.txt 2>&1; echo rc=$?
git status --porcelain                   # empty = genuinely read-only
```

A non-empty status means the reporter writes (a cache, a regenerated index, a `.pyc`) and cannot be trusted
to run against a tree you care about. Also read the exit code literally: a REPORT tool that exits non-zero
whenever it finds drift is correct behaviour for a report and unusable as a CI gate — say which one it is
rather than treating the non-zero as a defect.

## A PR diff that DELETES recently-merged files is a stale-branch revert, not a conflict

Distinct from a conflict and far more dangerous, because it reads healthy: the branch was cut from a main that
then merged something, the PR is `MERGEABLE` with most checks green, and its diff contains the *removal* of the
merged work. Merging it silently undoes the other PR. Nothing about `mergeable` or a green rollup detects it —
the diff content does.

```bash
gh api repos/<o>/<r>/pulls/<n> --jq '{head:.head.sha,base:.base.sha,ms:.mergeable_state}'
gh api repos/<o>/<r>/commits/main --jq .sha                     # base.sha != this ⇒ branch predates a merge
gh api repos/<o>/<r>/pulls/<n>/files --jq '[.[]|select(.status=="removed")|.filename]'
gh api repos/<o>/<r>/pulls/<n>/files --jq '.[]|select(.deletions>5)|{"-\(.deletions)":.filename}'
```

Any path that exists on current main and is *removed* by the PR is the revert. Confirm attribution against
history before naming it — `git log --oneline <base>..<main> -- <path>` names the merge the branch predates:

- **Remedy is a rebase of the SAME branch onto the live tip** (never a new PR — one vehicle per issue). State
  plainly that the earlier "gates verified" was a claim about a tree that can never merge.
- **Prove the revert is gone after the rebase**, do not infer it from "rebased": re-read `pulls/<n>/files` and
  confirm `length` dropped and no `removed` entries remain. Then check the deletions that DO remain are all
  in-scope for the issue — a gate that surfaces its own stale reference (a renamed script, a moved symbol) is
  in scope; anything touching another lane's content is not.
- A lane's "gates verified" is a claim about the tree it ran them on. A gate green on a tree that cannot
  merge is not evidence about the PR.

## Probe in a throwaway detached worktree at the PR head — and remove it

Never probe in the primary clone (owner-mediated, routinely behind `main`, so a probe there measures the wrong
tree) and never leave the worktree behind:

```bash
git worktree add --detach <scratch>/wt-<n> <head-sha>
# …all probes here…
git worktree remove --force <scratch>/wt-<n>     # then confirm: git worktree list --porcelain | grep -c wt-<n>
```

## Separate the gate's own red from the reviewer-gated one before routing

On an implementation PR the remaining reds usually split: a substantive gate red (a real defect → back to the
implementer lane) and a `check-pr-acceptance` red (unchecked ACs on an unreviewed PR → normal pre-review state,
cleared only by a reviewer proving and ticking). Only the first is a defect. Report the two duties separately
so a rebase is never dispatched at an acceptance red.
