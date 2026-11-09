# Base integrity and merge integrity

Rules for keeping a review verdict tied to a real base, and for confirming a finding
actually landed after a merge.

## Never rebase a branch stacked on a squash-merged ancestor

When the base PR landed as a **squash**, `main` carries one commit while your branch carries
the base PR's whole lineage. `git rebase <new-base>` therefore replays all of it and conflicts
on files that are **not yours** — measured once as `Makefile` plus a dozen foreign `agents/*`
files, none of which the branch had touched.

Correct shape:

```bash
git rebase --abort                     # first, if you already started one
git checkout -B <branch> <new-base>    # sit on the real base
git diff <old-base> <old-head> > p.patch   # YOUR change only
git apply --check p.patch              # clean iff new-base blobs == old-base blobs
git apply p.patch
# re-sync anything sourced from a live copy, then verify and commit
```

`git apply --check` passing is the assertion worth making: it means the new base's blobs equal
your old base's, so your diff is the only delta. If it fails, inspect which path diverged — do
not force it through.

## Re-verify your findings against the merged sha

A defect found on a branch is only fixed once it is fixed **on main**. After a merge, re-run the
specific check that failed and say which of your findings survived:

- a stale golden that was regenerated pre-merge shows as the suite passing on `main`;
- an issue closed as "ruling recorded" is **not** evidence that behaviour changed — re-measure the
  numbers the ruling cites at the merged commit.

Report both outcomes explicitly. "Merged" answers a different question from "the defect is gone".

## A squash merge rewrites the sha — verify content, not ancestry

After a **squash** merge the branch's commits are not on `main`; they are collapsed into one new
commit with a different sha. So `git merge-base --is-ancestor <branch-head> refs/remotes/live/main`
returns **non-zero** for a merge that succeeded, and reading that as "it did not land" is a false
alarm about a PR that is already in.

Verify by **content** instead — the files the PR was supposed to change, at the merged tip:

```bash
git show refs/remotes/live/main:<the/changed/file> | grep -c '<a phrase the change introduced>'
git ls-tree -r --name-only refs/remotes/live/main -- <dir>/ | grep -c '<the file the PR added>'
```

And state which verification you ran, because they answer different questions: `state: MERGED` +
`mergedAt` is the merge decision, ancestry is a property of the commit graph, and only the content
check says the change is in the tree. Quote the merge commit sha beside them.

The same rewrite makes every downstream expectation shift: the merged file may be **older than the
live copy** if work continued on the live side while the PR was in flight, so a `cmp -s` mismatch
after a merge is not a failed merge — it is new drift to version, which is a separate PR.

## A versioned skill is the first time a live skill meets CI

A lane's live skill lives under the agent home, where **nothing lints it**. The first time it is
versioned under `agents/<lane>/skills/`, the repo's gates (`lint_linefeeds.py`, `check-docs`,
`check_wiring`) run over it for the first time — so a live copy can be lint-red indefinitely and
nobody learns until a PR versions it.

Concretely: a `<!-- host-bot-tools:begin -->` marker sitting directly above `## Tools` with no
blank line reds `lint_linefeeds.py` at that heading, because a marker line is not blank. Fix it
in the **live** copy and re-sync, never only in the tree copy: patching the tree alone re-creates
the live-vs-tree drift the versioning PR exists to remove, and the next sync silently reverts it.

Run the repo lints locally before pushing a versioning PR (`python3 scripts/lint_linefeeds.py`,
`make check-docs`) — and expect the first push to find something, because the host copy has never
been checked.

## Do not push while a run at the head is in progress

A CI run at the current head plus a push equals a cancelled run when the workflow sets
`cancel-in-progress`. That turns a legitimate fix into a destroyed matrix: the old run is neither
green nor red, it is **no verdict**, and the reviewer's own rule forbids reading it either way.
Wait for the head's run to conclude, or say explicitly that the push supersedes and a new run is
required. Recording a lesson in a live skill does **not** require pushing it — do that, and defer
the sync to a moment when no run is in flight.

## Diff a PR against its MERGE-BASE, not against `main`

`git diff main...HEAD` and `git diff main..HEAD` both misreport a branch that is merely **behind**
`main`: the two-dot form shows every file that landed on main since the branch forked, so a PR's
own change is buried among dozens of unrelated files and a real finding can be attributed to the
wrong PR (measured twice in one evening: two PRs each looked like they touched 20+ `agent-wiki/`
files that had actually arrived via another PR's merge).

Use the merge-base:

```bash
MB=$(git merge-base refs/remotes/live/main HEAD)
git diff --name-only "$MB" HEAD        # what THIS branch changed
git diff "$MB" HEAD                    # the same, with content
```

Then state the merge-base sha next to `main`, e.g. "measured against merge-base `36cfa8c1`
(main is `ac12cae9`)" — a reviewer reading a file list needs to know which base produced it.
The three-dot form (`main...HEAD`) is equivalent to the merge-base call and is fine, but naming
the sha removes the ambiguity entirely.

A branch being behind `main` is **not** itself a `CONFLICTING` state, so per the fleet's rebase
rule it is not a reason to rewrite — but it does mean CI at that head ran against a superseded
base, which changes how a red may be attributed.

## A cited witness HEAD can go stale too — re-anchor a fresh-all-green AC witness to the LIVE head

A record that pins a required witness to a specific PR head (e.g. "#1836-AC4 fresh all-green must
be read at an ancestor-of-`781f698a7e` head emitting vllm-rocm cells") must be re-read against the
BRANCH's live head before the witness is measured, not just against main. The PR's branch advances
independently: measured 13:38Z — the #1837 live head had moved to `545a4e49db` while the record
cited `c139ca97`. Wiring the newer head into the requirement is a task-relative edit, not noise:
quoting a stale head invites a future re-measure at a branch state that no longer exists (or was
already superseded), and the deterministic-read class would be judged on the wrong tree. State the
live head (via `gh api repos/<o>/<r>/pulls/<n> --jq .head.sha`) beside the required-shape wording
each time the witness must actually be taken.

The sibling case is a head cited by a RUN RECORD: it can be orphaned outright (`git merge-base
--is-ancestor <cited> <live head>` non-zero, the branch advanced past it). Measure the live head and
say both — see `dispatch-red-attribution-vs-leg-log.md`, "Check the cited head is still an ANCESTOR".

## A `(proven:)` pin orphaned by a SQUASH MERGE — re-anchor to the merge commit, still no re-judge

The re-anchor-not-rejudge class has a post-merge variant: a head you DID judge gets merged as a
**squash** (the merge commit has ONE parent), and the merge commit is a brand-new sha — your branch
head is NOT an ancestor of main, so a `(proven: … head=<branch-head> …)` tick on the closed issue now
cites an unreachable sha. Measured on #1862: re-anchored to `0dd9fa63ae` pre-merge (15:19Z), then
#1864 squash-merged 15:23Z into `5bb742b2c2` (single parent `760a50372a`);
`git merge-base --is-ancestor 0dd9fa63ae 5bb742b2c2` → rc=1.

Prove content, then re-point, in this order (never re-judge):

```bash
git merge-base --is-ancestor <branch-head> <merge-commit>          # rc=1 → squash orphaned it
git diff --quiet <branch-head> <merge-commit> -- <graded paths>    # rc=0 → content carried intact
```

Both hold ⇒ the judgement stands, only the pin's sha is gone from every future tree. Re-run the
proving command AT the merge commit and `writeback --proven <same> --verdict-ref '… head=<merge-commit> …'`
on the (possibly closed) issue — a closed row still records the AC state the fleet reads and the
planner may dispatch the re-point. Verify the old sha appears ZERO times on-wire, quote both shas + the
prove shape, name the pre-merge record it supersedes, and keep the unproven marker row untouched.

A local command at the merge commit is the pin's anchor; the stronger complement is a **concluded CI
run whose own head is the merge commit** (`gh api "repos/<o>/<r>/actions/runs?per_page=100" --jq
'.workflow_runs[]|select(.head_sha|startswith("<merge>") and .conclusion!="" )|{id,name,conclusion}'`).
Post it as a separate read-back record listing each green run id — but attribute reds by the log's
`pr=` line, never by the run list's `head_sha`: a `workflow_run`-triggered `ci-verdict` leg runs at
the tip and carries the tip's sha while judging some OTHER open PR (see
`dispatch-red-attribution-vs-leg-log.md`, "A `workflow_run` verdict leg inherits the TIP's head_sha").
A merged tip can therefore show green CI plus unrelated ci-verdict reds at the same sha; both belong
in the record, and neither reopens the re-anchored row.

## A write-back `(proven:)` pin that is not the mergeable head — re-anchor, do NOT re-judge

Same class, one level deeper: the stale pin lives INSIDE an acceptance tick. A `(proven: … head=X …
rc=0 X…)` citation written after a rebase-only push can name an intermediate head that is **not an
ancestor** of the current head — the tick's substance is right, but a strict tick re-verifier at
merge time may red a sha that is not the mergeable head.

Prove rebase-not-content before doing anything, in this order:

```bash
git diff --quiet <cited> <live-head> -- <the graded paths>   # rc=0 → byte-identical content
git merge-base --is-ancestor <cited> <live-head>              # rc=1 → superseded, not an ancestor
```

Both together mean the pin is stale, the judgement is not — so **re-anchor, never re-judge** (no new
verdict, no flipped tick, no re-read of a criterion that already passed). Re-anchor shape:

1. Re-run the proving command **at the live head**, so the new pin cites evidence actually executed
   there (a pin is an execution record, not a content claim).
2. `writeback --issue <n> --proven <same list> --verdict-ref 'reviewer=… head=<LIVE 40-hex> <cmd>
   rc=0 <LIVE 40-hex>'` — same proven positions, only the sha changes; unproven rows keep their `- [ ]`.
3. Render locally with `apply --body-file <fetched body> --proven … --verdict-ref …` and confirm the
   old sha appears **zero** times before PATCHing (see `verdict-writeback-verification.md` for the two
   subcommands' differing argument shapes).
4. Re-run the gate on the live PR body afterwards, and confirm the PR head did not move during the
   write-back.
5. Post a short correction comment quoting **both** shas and the prove-shape (byte-identical +
   non-ancestor), naming the earlier record it supersedes. The old comment's content judgement stays;
   only its cited sha was stale, and the board must be able to tell which of the two it may trust.
6. Expect repeats under a fast-moving base: measured twice on #1862 within ~1h (`43d0544c` re-anchor,
   then the live head moved again via another rebase onto `760a50372a` → `0dd9fa63ae`, same graded
   files byte-identical). Each flag is a fresh pass, not a re-judge — the reply cites the newest live
   head and the same byte-identical proof, and names the record it supersedes. Never promise this is
   the last time until the PR actually merges.

## A stale base reds `check-pr-base`, which CANCELS the walking legs — no unit verdict at that head

When the branch's merge-base with current `origin/main` is an older main (the base moved under it
after another PR merged), the `guard` job's `check-pr-base` step (issue #845) FAILS — and because the
`guard` leg gates the matrix, the walking legs (`linux / unit`, `install`, …) are **skipped/cancelled,
not run**. `gh pr checks` then shows `linux … skipping` and a `guard … fail`, plus a derived
`ci-verdict … fail` (the echo of the guard, #58). Do **not** read that as "unit pending, wait for it":
no unit run will ever conclude at that head — the gate that would launch it already redded.

The verdict is therefore "**not green, rebase owed**", not "waiting": the prior head's fix may be
correct in the tree (verify it locally, e.g. the marker/line the last verdict asked for), but no run
id can yet certify it under CI. Remedy = rebase onto current `origin/main` (the #1015/#845
trigger — a genuine stale base, unlike a merely-behind-but-clean branch), then a fresh matrix runs
`linux / unit` at the new head; post the green verdict citing THAT run id. State plainly which
sub-facts are done (hold lifted, fix in tree) and which is blocked (no unit verdict — cancelled by
the `check-pr-base` red), so the board does not read a cancelled matrix as a failing fix.

## A `check-pr-base` red on a MAIN-TIP run is a phantom when main advances mid-run

A CI run triggered on `main` right after a merge has head = the merge commit. If **another** PR
merges while that run is executing, `origin/main` advances past the run's head, and `check-pr-base`
then FAILS on that merge-tip run — `HEAD is NOT cut from origin/main — its merge-base is <the
merge-commit>, measured against origin/main at <a newer tip>`. That red is a **phantom**, not a
regression in the just-merged content, and it is a *different* case from the stale-branch red above
(there a branch must be rebased; here nothing is wrong with the merged work).

Confirm the phantom before reporting it, in this order:

```bash
git merge-base --is-ancestor <merge-commit> <current-main-tip>   # YES → the content IS on main
git log --oneline <run-head>..<current-main-tip>                # a later, unrelated merge moved the base
```

Then read the failing leg's own log (`linux / unit` → `make ci-unit` → `check-pr-base`) to show it
is the **only** red — every real gate (authors, closing, hygiene, openspec, agents-read, lint) passes.
A `check-pr-base` red alone, on a head that is merely *behind* the current tip, is base-staleness,
not a product defect. For the fleet-merge variant — the `foreign commits (0): (no commits in
base..rev)` tell, the chain-gate/PR-side applicability, and the re-anchor-to-fleet-complete-tip rule
— see `references/phantom-check-pr-base-fleet-merge.md`; do not treat each sibling's phantom red as
blocking, and never fabricate a green off the phantom itself.

The correct "main green at merge tip" evidence therefore **re-anchors**: it is a CI run at the
**current** main tip (whose ancestry includes the merge commit), not the run that reddened while the
tip moved. Do not write "main green" off a run that is behind the current tip and do not close the
acceptance row on it — state "no verdict at the re-anchored head yet" and wait for a concluded CI at
the current tip (or the next main-tip run). Report the phantom red beside the re-anchored green; never
sweep it under, because the red run is part of the record even when it was not the merge's fault.

## A phantom-red label covers only the leg it was measured on — re-attribute every leg

A dispatcher (or a PR body, or your own last record) may hand you a blanket "all N reds are the
tracked <class> noise" attribution. Treat that as a **claim about the run**, not a finding: the
noise class was measured on one leg, and the other legs have their own failure text. Read each
failing leg's own log and name what it actually says before you discount any of it.

Measured: a dispatch declared three reds (guard, scope, ci-verdict) all "#1862-class noise, not this
PR's defect". The scope leg's own log said something else entirely —

```
[check-docs] ERROR: change->note: this branch changes scripts/<x>.py but adds no
agent-wiki/<stem>.md note — a behavioural change owes a note (and its docs/changes.d/<stem>.md row)
```

— a real, merge-blocking gate red caused by **this** diff (a behavioural change to a `scripts/`
file with no `agent-wiki/` note, no `docs/changes.d/` row and no `CHANGES.md` row). The guard leg
was the expected pre-write-back `check-pr-acceptance` red and the ci-verdict leg was genuinely the
noise class; only one of the three was the PR's own defect, and the blanket label would have hidden
it. Confirm the diff really adds no note:

```bash
gh api repos/<o>/<r>/pulls/<n>/files --jq '[.[]|select(.filename|test("agent-wiki|docs/changes.d|CHANGES.md"))|.filename]'
```

So: attribute per leg, each with its own quoted failure line, and when one red survives the noise
label, it is a REVIEW FINDING with the implementer's fix named (which files to add) — not an approval
blocker you quietly absorb, and not a green you may write off.

## Reproducing a gate locally: `| tail` eats the exit code

`python3 scripts/<gate>.py check 2>&1 | tail -15; echo rc=$?` prints **tail's** status, so a failing
gate reads `rc=0` and the repro looks green beside its own ERROR line. Run the gate on its own, then
tail separately:

```bash
python3 scripts/check_docs.py check; rc=$?; echo "rc=$rc"
```

When the container gates a step (`make check-docs` → `scripts/changes_index.py check`,
`scripts/check_docs.py check`, …) reproduce the same script the leg runs, not a nearby sibling —
and quote the gate's own `[name] ERROR:` sentence as the evidence anchor at the head sha.

## A rebase can clear the conflict and leave the cause

`mergeStateStatus` going `DIRTY → BLOCKED` after a rebase is **not** evidence that the problem was
fixed. A rebase re-applies your change onto the new base; if the base's version of the contested
file moved, the same hunk can now apply without a textual collision. The commit still carries it.

Measured: a PR `DIRTY` on `CHANGES.md` was rebased onto the new `main`, went `BLOCKED`, and
`git diff --name-only "$(git merge-base main HEAD)" HEAD | grep -c '^CHANGES.md$'` still returned
`1` with the same appended row. It will go `DIRTY` again the next time that file changes on main.

So after a rebase that “clears” a conflict, re-run the same check that found it:

```bash
MB=$(git merge-base refs/remotes/live/main HEAD)
git diff --name-only "$MB" HEAD      # is the offending path still in the diff?
git merge-tree --write-tree refs/remotes/live/main HEAD   # does it merge RIGHT NOW?
```

"Merges right now" and "no longer carries the defect" are different claims. Report them separately,
and credit the rebase for clearing a real conflict while saying the underlying change is still
there — otherwise `BLOCKED` reads as repaired and the defect ships.

## Render a shared append AFTER rebasing, never before

A generated aggregate that every PR appends to (`CHANGES.md` and its fragment renderer are the
canonical case) is a **shared append**, and its generator is deterministic against the fragment set
*on the base it reads*. So rendering on the stale base writes a file whose rows sit where the old
base put them, and landing that on a moved `main` produces a conflict in the very file the rebase
existed to escape. Measured: `make changes-index` on the pre-rebase tree → `git merge-tree` against
the new tip reported **1 conflict**, in `CHANGES.md` alone.

Correct order, every time:

```bash
git checkout -B <branch> refs/remotes/live/main   # or re-apply your diff onto it
make changes-index                                 # render from the base you will target
python3 -m pytest <the aggregate's own test> -q    # the render is only correct if this passes
```

Corollary: if a rebase is required for any reason, re-render afterwards even when you rendered
before — the earlier render is now a claim about a base that no longer exists.

## Test the MERGED RESULT, not the merge

A textual `git merge-tree` answers *"do these two hunks collide"*, not *"is the result correct"*. An
invariant that holds over a **rendered file** — a committed aggregate equal to its render, a manifest
equal to its inventory — can fail on the merged tree even when the merge is textually clean, because
each side rendered against its own base and the composition of two correct renders is not necessarily
a correct render.

So when `main` moves under an open PR, do not stop at `merge-tree`. Build the merge and run the check
on the result:

```bash
git worktree add --detach /tmp/mg refs/remotes/live/main
cd /tmp/mg && git merge --no-commit <head>
python3 -m pytest <the invariant's own test> -q
```

"No conflicts" and "the merged result passes" are different claims. The first is cheap; the second is
the one that decides whether a re-cut is needed — and it frequently answers *no* when intuition says
yes, which is a matrix saved rather than a risk taken. Do not let "the base moved" stand in for
"the merged result fails": only the second is a rebase trigger.

## An arm records a time, never a head

`autoMergeRequest.enabledAt` is stamped when someone enables auto-merge and is **not** cleared by a
later push. Measured: one arm timestamp survived **three** head moves, including a head where the
deciding gate had been cancelled and never executed.

So the field answers *"was an arm requested"*, never *"is this head armed"*. Report arm state with the
head beside it, and treat an arm older than the current head as **unverified** rather than as intent to
merge the current one. When you read someone else's "it's armed" claim, the same gap applies: a live
`enabledAt` says nothing about which sha it applies to, so neither party can conclude from it that the
present head will merge.

## Quote the base at the moment of the claim

Every finding, control and verdict is relative to a base sha. Read it *in the same turn* as the
claim, and require the fetched ref to match the API tip:

```bash
git fetch origin refs/heads/main:refs/remotes/live/main --force   # --force is required, see below
gh api repos/<o>/<r>/commits/main --jq .sha                       # the true tip; require equality
```

**A bare `git fetch origin refs/heads/main:refs/remotes/live/main` with no `--force` is silently
REJECTED** (`! [rejected] … (non-fast-forward)`) whenever the local `live/main` ref already exists and
has moved — the fetch updates nothing and leaves you measuring the OLD tip, so a merge-base you compute
afterwards is against a base that is not the current main. Add `--force`; then the API cross-check is
the guard that the ref really moved (`live/main` short sha == `commits/main` API sha). A clean merge at a superseded base proves nothing about
the base you will target; a control run against yesterday's main proves nothing about today's.

**Fetching the PR head does NOT refresh the base ref — and a stale `live/main` shows the PREVIOUS
merge's work as if the current PR were adding it.** `git fetch origin refs/pull/<n>/head:…` moves only
the head; `refs/remotes/live/main` stays wherever it was. Diff `live/main..head` then reads as the PR
carrying whole sections that actually landed in main via an earlier merge (measured: a base-PR's whole
fork-skip test block appeared as additions under the follow-on PR, because `live/main` was one merge
behind). The tell is that the "new" code is the just-merged PR's exact content — verify by comparing the
true base: `gh api repos/<o>/<r>/commits/main --jq .sha` must equal `git rev-parse --short refs/remotes/live/main`,
else `git fetch origin refs/heads/main:refs/remotes/live/main --force` and re-diff. Fetch the base with
`--force` **in the same turn** you fetch the head, before any `git diff`; the head fetch is never enough.
