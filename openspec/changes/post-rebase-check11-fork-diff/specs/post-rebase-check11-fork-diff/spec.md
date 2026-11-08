# post-rebase-check11-fork-diff

## ADDED Requirements

### Requirement: a deliberate edit passes, a `-X theirs` revert reds

`post-rebase-verify.sh` check 11 MUST NOT report `FAIL` on a tracked text file whose base-line
losses are all accounted for by the branch's own diff (the pre-rebase tip `git rebase` records in
`ORIG_HEAD`, diffed against `merge-base(base, ORIG_HEAD)`); such an edit is reported as a `NOTE`.
It MUST report `FAIL` exactly when a base line HEAD lacks was never a deletion in the branch's own
diff — the provable `-X theirs` / `-X ours` revert shape. Without `ORIG_HEAD`, intent is
unprovable, so the check MUST fall back to a `NOTE`, never `FAIL`.

[comment]: # (AC / how to verify: `test-revert-detector.sh`'s case 1 (clean rebase carrying a branch edit) rc=0 and case 2 (`-X theirs` rebase) rc=1; both quoted in the PR body.)

#### Scenario: a branch's own substitution after a clean rebase passes

- **Given** a branch whose only change is its own rewrite of a tracked text file, rebased onto a
  base that advanced an unrelated file
- **When** `post-rebase-verify.sh <base>` runs
- **Then** it prints `base lines replaced by branch's own diff` as a NOTE and exits 0

#### Scenario: a `-X theirs` rebase reverting an untouched base line fails

- **Given** a branch rebased with `-X theirs` whose head drops a base line the branch's own diff
  never deleted
- **When** `post-rebase-verify.sh <base>` runs
- **Then** it prints `base lines reverted` and exits 1 (`DO NOT PUSH`)

#### Scenario: no ORIG_HEAD (no rebase) is a NOTE, never a FAIL

- **Given** a tree with no pre-rebase tip recorded
- **When** `post-rebase-verify.sh <base>` runs on a branch that lost base lines
- **Then** the loss is reported as a NOTE and the push is not blocked (over-firing was the defect)
