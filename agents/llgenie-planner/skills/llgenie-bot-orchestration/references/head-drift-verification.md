# Verifying a lane's reported HEAD against the branch

A lane reports a head sha and an acceptance result at it. The branch is the truth; the report is a
claim about a moment that may already be past. This is the most common reconciliation failure in the
fleet: the lane gated a real sha, described it accurately, and never noticed the branch moved.

## The three reads must agree

```bash
gh pr view <n> --json headRefOid,headRefName,mergeStateStatus,mergeable,isDraft,autoMergeRequest
# fetch the PR's own head ref — works even when the local branch ref name is stale or renamed
git fetch origin 'refs/pull/<n>/head:refs/remotes/origin/pr<n>head'
git rev-parse origin/pr<n>head                 # must equal headRefOid
git log --oneline --first-parent <base>..origin/pr<n>head   # read newest commit subjects
```

Branch API, `headRefOid`, and `rev-parse` of the fetched PR head are three independent reads; if any
disagrees the report is stale, full stop.

## Ancestry separates "stale" from "superseded"

```bash
git merge-base --is-ancestor <quoted> origin/pr<n>head && echo ancestor || echo SUPERSEDED
```

- **Ancestor but not the tip** — the branch advanced past the quoted sha. The lane's gate was real,
  just pointed at an older commit. Re-measure at the tip; do not repeat the quoted head.
- **Not an ancestor** — the quoted sha was amended away or belongs to a sibling history and never
  lived on this branch. A gate at it is not the PR's gate.

## Design drift hides in the newest commit subjects

Read the subjects between the quoted sha and the tip. A design change ("run X as a completion
reaction, not a new scheduled bot"; "redesign to ride an existing cadence") means the lane's report
*and the PR body* likely still describe the abandoned approach. Reconcile both: the correction names
the real head, the new design, and asks the lane to update the body. A report can be stale on head,
design, and `mergeStateStatus` simultaneously — check all three.

## `mergeStateStatus` is not what the lane calls it

`BLOCKED`/`UNSTABLE`/`DIRTY` are distinct. A lane often says "BLOCKED = checks in flight" when the
status is `UNSTABLE` (a leg still `in_progress`, nothing blocking on review). Grade the label from
the live rollup (`gh pr view --json statusCheckRollup`), not the lane's word — and an acceptance
criterion that says "green at the PR head" is **not met** until the last leg is COMPLETED SUCCESS at
the real head, however many other legs already pass.

## gh JSON field names that bite

`gh pr view --json` has no `draft` and no `autoMerge` — they are `isDraft` and `autoMergeRequest`
(read `autoMergeRequest.enabledAt` to prove an arm; `--auto` can exit 0 and arm nothing off the
default base). Inside a jq object the key shorthand needs the dot: `{base:.baseRefName}` works,
`{base:baseRefName}` reds the whole call with "function not defined: baseRefName/0" — and an
unknown `--json` field aborts the entire call with the available-field list. Validate field names
before trusting the read; one typo costs a round-trip.
