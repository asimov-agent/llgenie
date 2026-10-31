# Reading the board: fields, buckets, and push churn

How to answer "what is the state of this PR?" without producing a claim that is true at composition
and wrong on arrival. Every rule here is stated against the failure it prevents.

## Quote the head and the minute, or say `pending at <hh:mmZ>`

A board line is a claim **about a head**. Quote the sha and the time in the same breath
(`#1234 ab12cd34 · 13 success / 1 pending · 22:10Z`), or write `pending at 22:10Z` when no verdict
exists yet.

- Re-read the head **inside the same command that writes the line**. An answer from your previous tool
  call is already a snapshot, and a busy board merges under you in minutes.
- A bare state word ("green", "blocked", "armed", "mergeable") rots into something indistinguishable
  from a false claim. `pending at <time>` is a fact with an expiry; "green" is a claim with none.
- Expect the planner and every lane to report an already-merged PR as open at least once a night. This
  is composition-versus-delivery lag, not carelessness: check `state`/`mergedAt` before repeating a
  reported state to anyone.

## The field answers a neighbouring question

Nearly every wrong verdict is a field trusted for something adjacent to what it measures. Read the
right column, not the middle one.

| you want to know | do not read | read instead |
|---|---|---|
| is this green? | `mergeable`, `reviewDecision` | per-head `check-runs` conclusions |
| is the index current? | the CLI's own rc (`check_docs`, a fragments-only "ok: N") | the test asserting `committed == rendered` |
| is this head armed? | `enabledAt` — it records a **time**, never a head | `autoMergeRequest` **and** `headRefOid` together |
| did the gate run? | `skipped` | the fan-out job's own conclusion: **cancelled means nothing was decided** |
| is the run hung? | a frozen `updated_at` (it just doesn't advance mid-step) | elapsed vs the worst measured run that **concluded** |
| how many are affected? | subtracting two set sizes | a set difference over named members |
| does this object exist? | `git log --all`, `for-each-ref` (both enumerate **refs**) | `git cat-file -t <sha>` or the API |
| is the branch upstream of main? | `--is-ancestor` after a squash (always no) | content: `cmp -s` the files, or a merge of the branch into main |

Two corollaries worth stating on their own:

- **A cancelled run is not a verdict, and `skipped` is not "passed".** A cancelled fan-out leaves the
downstream matrix with no job list, so every job reports `skipped` — which is byte-identical to a
legitimate "this diff needs no such job". The two states must never be collapsed.
- **Name-sets are not signatures.** A file that keeps every function name can still be *older* than
main's copy, and a wholesale take silently reverts main's fix. Compare signatures (parameters changed,
oracles added), not the set of defined names.

## Print the buckets, not the summary

Report `success / failure / cancelled / skipped / pending` separately. Two PRs can both read "0
failures" while one has fourteen concluded checks and the other has five non-verdicts; a summary that
prints only failures makes them identical, and that is the one reading a reader cannot recover from.
"All checks concluded and all succeeded" is the only green worth reporting as green.

## One push per change; a push destroys the verdict at the previous head

`cancel-in-progress` means a finished push is only finished once the run **at that head** concludes.
A lane that pushes repeatedly never lets any head carry a completed verdict: local greens accumulate,
CI is cancelled again and again, and the PR never lands. Symptom to watch for — **a PR whose heads
all read "green locally" and none of which ever carried a concluded CI run.**

When the branch sits behind a moving main:

1. wait until main has been quiet for a few minutes (a merge wave ends);
2. rebase once onto that sha, and render any shared append (`CHANGES.md`-style index) **after** the
   rebase, never before — rendering on the old base reproduces the conflict you are escaping;
3. verify the union survived in every file both sides touched (grep for one token only each side had);
4. push once, then leave it alone and let the run conclude.

A branch that is merely behind but `MERGEABLE` owes **no action at all**: "the base moved" is not the
trigger; "the merged result fails" is.

## Never trust a checker that can only pass

Before trusting any gate — yours or a lane's — prove it fails. Revert the fix and watch it red; inject
the defect it claims to catch; run the negative control.

- Report the negative control, not just the pass: *"fix reverted → 1 failed; fix applied → 6 passed"*
  is the artefact that establishes trust.
- Prefer an assertion that reds when its **subject disappears** (`assert n > 0`, `checked > 0`) over a
  marker that merely tolerates a failure. A marker says "tolerate this"; an assertion says "this will
  stop being true, and when it does I fail".
- A vacuous pass is the same defect pointing the other way: a gate that reports OK for a file it never
  parsed, a task that "is not invoked by any workflow" reported as "never runs", a guard whose stated
  intent and effective behaviour differ.

## Mechanics: the commands and the traps around them

### Posting a comment safely

Backticks inside a **double-quoted** `--body` are command-substituted by the shell; `gh` then exits
non-zero and **posts nothing**, while the next step proceeds as though the announcement landed. Use
single quotes or `--body-file`, and treat "did a URL come back" as the confirmation — not the absence
of an error.

### Discarding work by accident

`git checkout HEAD -- <path>` throws away uncommitted changes to that file **silently**. Never use it on
a file modified in the same session; `git stash` or recover from a named sha instead. The compound
failure is specific and has happened: a fix was committed, then wiped by a later checkout, and the PR
spent hours shipping a **body describing a fix the commit no longer contained** — caught by reading the
diff, not by any gate. Verify that what the body claims is what the diff contains.

### Deciding whether a merge conflicts

`git merge-tree --messages` prints informational `Auto-merging <path>` notices **on the same stream** as
errors. Grepping for a filename therefore yields a hit whether or not anything conflicted. The only
sound test is anchored and case-exact: `grep -cE '^CONFLICT'`. A related trap: a conflict marker can
survive `git rebase --continue` and get committed — after any `--continue`, check
`git show HEAD:<file> | grep -cE '^(<<<<<<<|>>>>>>>)'` and parse the file before pushing.

### Rebasing a branch someone else is pushing

Re-read the live head **immediately before** a force: `--force-with-lease` protects against strangers,
not against your own older knowledge of where the head was. If the head moved mid-rebase and the new
head does not descend from what you started on, **abort** (history was replaced, not appended) rather
than pushing. After a few replacements, stop and hand it back with the resolution recipe — a rebase lane
cannot win a race against a lane rewriting the branch every few minutes, and the correct outcome is that
the PR lands later with its deviation documented.

### Verifying a merge

After a squash-merge the original shas are not ancestors of main, so `--is-ancestor` is correctly `no`.
Verify by **content**: the file on main contains the section you added (`cmp -s` against the expected
text), the wiki row and index row are present, and `state`/`mergedAt` say merged.

### Orphaned vs nonexistent

A force-pushed-away head is reachable from **no ref** but still exists on the server. `git log --all`
and `for-each-ref --points-at` will not show it; `git cat-file -t <sha>` and the API will. Both readings
can be right at once: the object exists, and it is not the PR. Check `gh pr diff`/`headRefOid` before
quoting a sha you measured several heads ago.
