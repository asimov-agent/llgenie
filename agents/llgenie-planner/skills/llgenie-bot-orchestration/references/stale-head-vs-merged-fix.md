# A red CI leg on a stale head whose cause was fixed on main

A lane reports "the PR is red on `linux / unit`" and calls it ambient. Often it is not ambient at
all: the PR head was cut before the fix that greens that leg reached `main`. Re-running CI at the
current head will red forever, because the branch does not contain the fix. The remedy is a
rebase/merge of `main` into the branch, not a re-run and not a bug hunt.

## Procedure

1. Identify the fix commit on `main` (the merge commit of the PR that fixed the gate).
2. Test ancestry — never assume the head has it:

```bash
git -C <tree> fetch origin main
git -C <tree> fetch origin 'refs/pull/<n>/head:refs/remotes/origin/pr<n>head'
fix=<merge-commit-sha-of-the-fix>
head=$(git -C <tree> rev-parse origin/pr<n>head)
git -C <tree> merge-base --is-ancestor "$fix" "$head" \
  && echo "head already has the fix" \
  || echo "head pre-dates the fix -> needs a main merge"
```

3. Confirm the fix does not overlap the PR's own files, so the merge is clean rather than
   conflicting:

```bash
git -C <tree> show --stat "$fix"
```

   No overlapping paths + `mergeable: MERGEABLE` = a stale-head-behind-main case. Say that
   explicitly, because "MERGEABLE" otherwise reads as "nothing to do".
4. Dispatch the owning lane — the lane that wrote the branch, not the conflict lane — with the
   fix sha, the ancestry verdict, the non-overlap evidence, and one instruction: merge/rebase
   `origin/main` (`<fix sha>`) into the branch, keep the design, push, re-run, and cite a
   **completed** run at the NEW head. The acceptance gate stays "the red leg SUCCESS at the head
   that carries the fix", not "SUCCESS at any head".

## Pitfalls

- **"Ambient red" is a hypothesis, not a finding.** Before repeating a lane's "it's the same
  tree-wide failure", check whether the head contains the commit that fixed it. The two look
  identical in the job matrix (one leg red, every other leg green).
- **A green run at an older head proves nothing.** Quote the run by id with `status`,
  `conclusion` and `headSha` together; a `completed/failure` at the head is the verdict even
  while an earlier head's run was green.
- **Do not re-dispatch a re-run.** A re-run at an unchanged stale head reproduces the same red
  and burns the lane's slot. The rebase is the task; the re-run follows it.
- **When the guard/review machinery insists a mutation is owed and you think none is**, re-measure
  the state instead of inventing a write: a run that has since *completed*, or a base that has
  since *merged*, is new state and often makes one genuinely owed (a verdict comment, a rebase
  dispatch). Satisfy it with that real, in-scope action; never fabricate a peer-lane edit to
  silence the check.
