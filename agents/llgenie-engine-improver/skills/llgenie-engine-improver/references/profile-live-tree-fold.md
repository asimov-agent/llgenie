# Folding a live-edited agent profile back into the committed tree

A live profile (`~/.hermes/profiles/<p>/`) drifts from `agents/<p>/` whenever the lane edits its own
skills/SOUL during a session. The committed tree is the source of truth for provisioning; the live
edit is a finding until it is committed. This is the recipe for turning live drift into a PR.

## Steps

1. **Clean worktree at fresh main.** Use a dedicated worktree cut from `origin/main` at the sha you
   just fetched. Never measure from the primary checkout: it is routinely parked on another lane's
   branch, and `CHECK=1` run from a stale tree reports drift against the wrong baseline.

2. **Measure with check mode only.**
   ```
   make sync-agent-profile PROFILE=<p> CHECK=1
   ```
   Exit 0 plus `OK: N file(s) ... match ... byte for byte` means clean. Otherwise it names every
   differing path with both sizes and calls out the first differing path.

3. **Fold live -> tree, byte for byte**, then prove it: compare the two files' bytes in the same
   step in which you copy them; a size match alone is not equality.

4. **Fold every file CHECK=1 names, not just the ones the issue lists.** The profile keeps being
   edited while the issue sits in the queue, so a file can start drifting after the issue was
   measured. Acceptance is whole-profile `tree == live`; folding only the listed subset leaves the
   gate red on the extra file and the PR cannot meet its own evidence clause. Record the extra file
   (name, both sizes, live mtime) as a scope note on the issue so the routing record stays exact.

5. **Change-note trio:** `agent-wiki/<date>-<slug>.md` + `docs/changes.d/<date>-<slug>.md` + the
   CHANGES.md row re-rendered with `make changes-index`. `check-pr-hygiene` cross-checks all three
   and rejects a note that appears twice.

6. **Local gate suite before commit:**
   ```
   make check-docs && make changes-index && make check-pr-hygiene && make lint \
     && make skills-validate && make check-agent-profiles-ratchet \
     && make sync-agent-profile PROFILE=<p> CHECK=1
   make bot-preflight   # prints the AGENTS:/BASE: lines for the PR body
   ```

7. **Commit as the allowlisted identity** (`git -c user.name=... -c user.email=... commit`), subject
   citing the issue. Then honour whatever push gate the issue carries; a prepared, verified, held
   branch with an evidence comment on the issue is the correct end state when that gate is closed.

## Pitfalls

- **Never run `make sync-agent-profile` without `CHECK=1` to fix drift.** Write mode copies
  tree -> live: it overwrites the live edit (destroying the specimen a review needs) and makes the
  gate green while the tree stays wrong. Only check mode, and fold in the direction live -> tree.
- **A green `ci-unit` is not proof the fold is complete.** `check-agent-profiles` is part of
  `ci-unit`, but on a CI runner there are no live profiles to compare against, so live drift never
  reds it there. The host-local `CHECK=1` is the completeness gate; the CI green covers only the
  structural tree rules.
- **Copy out a specimen before repairing anything.** If a stale file is the evidence, put it in
  `/tmp` first; repairing the workspace destroys what the review cites.
- **Do not touch another lane's profile.** A fold PR covers exactly one profile; other profiles in
  the same worktree stay untouched.
