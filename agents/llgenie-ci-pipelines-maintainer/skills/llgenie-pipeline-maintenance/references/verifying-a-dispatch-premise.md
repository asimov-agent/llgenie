# Verifying a dispatch premise before you implement it

A dispatch (from the inbox/planner, or from the issue body) is a **claim about the tree at some
past sha**, not a fact about your baseline. Merge batches land between the dispatch being written
and you picking it up. The failure mode is implementing a fix for a gap that no longer exists —
which produces a no-op PR, recants a decision the owner already made (e.g. re-lowering a ceiling
that was deliberately raised), and burns a review cycle.

## Procedure — measure the acceptance criteria at YOUR baseline first

1. **Fetch canonical upstream and branch from the sha you fetched now**
   (`git fetch upstream main`; canonical remote is `asimov-agent/llgenie`, not a fork). Note the sha.
2. **Read the issue's own acceptance criteria, then prove each one at that baseline** — not by
   trusting the dispatch's summary:
   - Run the guard/regression suite that is supposed to hold the property. A green guard suite is
     the strongest single signal the gate is already enforced.
   - Prove the released fixes are actually in ancestry:
     ```
     for sha in <known-fix-shas>; do git merge-base --is-ancestor "$sha" upstream/main \
       && echo "$sha in main"; done
     ```
   - Read the exact config value the dispatch names (a `timeout-minutes`, a threshold, a marker)
     with `git show upstream/main:<workflow>` — do not assume the dispatch's number is current.
3. **Classify the gap honestly:**
   - **Guard suite green + all fixes in ancestry + config already at the target** -> the acceptance
     criteria are met; there is nothing to implement. Do not write a PR.
   - **A genuine residual gap** -> implement the narrow remaining change.

## When it is already satisfied

- **Do not fabricate a no-op PR.** A commit that changes nothing to close an issue is a lie on the
  board and a wasted review. My lane's standing rule dominates here: never weaken a gate or invent
  a change to go green/close.
- **Report the measured verdict instead:** name the sha, quote the guard-suite pass count, list the
  fix shas proven in ancestry, and quote the config line. Send it to the inbox/planner.
- **Route the close-vs-rescope decision to the owner.** If the only conceivable "fix" would counter
  an owner instruction (re-tightening a ceiling they raised, moving a trigger they moved), do not
  guess — state the fork and let the owner/inbox decide.
- **Leave the worktree in place** (report, never prune). No commit, no push.

## "Is this head YOUR push?" — prove ownership, never infer it from the author field

When the inbox/planner asks whether a named head is your push (before it routes more work onto the
same branch), answer from an object-level measurement, not from `git log` attribution:

```bash
git -C <repo> cat-file -t <sha>        # "Not a valid object name" = you never had it locally
git -C <repo> branch -a --contains <sha> # empty = no local ref of yours reaches it
```

If the object is absent from your local repo and no ref of yours contains it, it is **not your
push** — a commit you created and pushed from this machine leaves the object locally; its complete
absence is decisive. **Do not claim it and do not touch the branch.**

- **The author email is a shared allowlisted identity, so it cannot prove the lane pushed it.** The
  commits this lane makes carry the same `user.name`/`user.email` as the owner (`Andy Holst` /
  `andy.holst@protonmail.com`) because that is the arm-eligible identity. A commit showing that
  author may have been made by the owner or another lane using the same identity. Attribution by
  author field is not authorship by this lane.
- **Answer the ownership question, then stop.** If it is not yours, report "NO" with the
  `cat-file`/`--contains` evidence and route back for a different pick — never reopen, edit or
  "verify" a branch another lane owns.

## Re-measure the PR's live state before accepting a "CI is re-running / pending at your head" premise

A dispatch that says "run N is re-running at your head, `unit`+`install` pending, do not push while
it runs" is a snapshot of the moment the message was written. Measure it first:

```bash
gh pr view <n> --repo <o>/<r> --json state,mergedAt,mergeCommit,headRefOid \
  --jq '{state,at:.mergedAt,merge:.mergeCommit.oid,head:.headRefOid}'
```

- **`state=MERGED` supersedes the whole premise.** The "let CI conclude / do not push at your head /
  verify pending jobs" instruction is moot once the PR has landed — the branch is closed and must
  not be touched. Report the merge sha + `mergedAt` as the answer (the regen/fix landed
  green-on-merge) rather than waiting on jobs that already concluded.
- **A stale "pending" line usually means the reporter read an earlier snapshot.** Bind every reply to
  the head you actually measured now, and say explicitly that the earlier run/job state is
  superseded by the merge — do not re-verify work that already landed.

## Pitfalls

- **A passed test the dispatch said was "leaking" is your evidence, not a contradiction to argue
  away.** A network-marker/zero-offender guard that passes at baseline means the leak was already
  sealed — cite the test name and count.
- **Crude greps lie.** A regex flagging `huggingface.co` in a file does not mean the file reaches the
  Hub — most hits are stub/loopback/docstring sites the authoritative guard correctly exempts. Trust
  the guard's own AST/reach detector over an ad-hoc grep.
- **"Ceiling raised" can be the whole fix for a "hits the ceiling" issue.** Check the current
  `timeout-minutes` before designing a speed-up; the owner may have chosen to raise the wall
  instead of shrinking the work.
