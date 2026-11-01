# Reading CI check rollups and polling a head

## Never read a rollup from a badge or a single status line

`gh pr checks <n> --repo <owner>/<repo>` prints `name / state / duration / url` per job. Read that
list and count the states at the head you care about:

```bash
gh pr checks <n> --repo <o>/<r> | grep -cE $'\tpass'
gh pr checks <n> --repo <o>/<r> | grep -cE $'\tfail'
```

A `pending` job is not green. A `cancelled` job reads as failure and is UNTESTED. A workflow that fails
to load contributes zero jobs, so every rollup looks clean — confirm the job you intended to gate on is
actually IN the list before declaring a head green.

## Check names contain spaces, slashes and parentheses

Names like `linux / unit` and `linux / top-tier (none)` break a shell `case` glob or a grep anchored on
the literal name. Extract the state by field instead of matching the name as a pattern:

```bash
gh pr checks <n> --repo <o>/<r> | awk -F'\t' '/^linux \/ unit/{print $2}'
```

## Keep every poll inside the tool timeout

A poll loop that outlives the terminal timeout returns a timeout error and you lose the loop's output.
Budget far under the limit (e.g. 30 iterations x 10 s at a 360 s timeout), break on `pass`/`fail`, then
re-poll in a FRESH call if the job is still running. Never background a sleep to beat the cap, and never
cancel a running job to "clear" a queue.

## Arm, then read the arm back

`gh pr merge <n> --squash --auto` exits 0 even when it armed nothing (e.g. base is not the default
branch). The exit code is not the fact — read it back:

```bash
gh pr view <n> --json autoMergeRequest,mergeStateStatus \
  --jq '{arm:(.autoMergeRequest.mergeMethod//"NONE"),at:(.autoMergeRequest.enabledAt//"-"),ms:.mergeStateStatus}'
```

`ms=BLOCKED` with `reviewDecision=REVIEW_REQUIRED` is a review-only hold, not a failed arm. Do not
hand-merge; let the repo's auto-merge land it on approval.

## Confirm the merge itself

After approval, `state`, `mergedAt`, `mergeCommit.oid` and `mergedBy` are the record:

```bash
gh pr view <n> --json state,mergedAt,mergeCommit,mergedBy \
  --jq '{state,at:.mergedAt,sha:.mergeCommit.oid,by:.mergedBy.login}'
```

Use `.isDraft` (not `.draft`) when querying draft state — the wrong field name silently yields an empty
answer and makes a draft look like a ready PR.

## A new gh-command make target: grep the shape-guard before you push

The repo asserts the SHAPE of every Makefile recipe that calls `gh`. My #902 PR added a target with
`--repo "$(REPO)"` and `tests/test_repo_slug.py::test_no_recipe_passes_the_checkout_path_to_gh` redded it:
`offenders = [line for line in MAKEFILE if re.search(r'--repo\s+\"?\$\(REPO\)', line)]` — every `gh
--repo` must be the `$(GH_REPO)` slug, never the checkout-path `$(REPO)` form. The guard worked exactly
as built; my recipe was the defect. Fetch the guard BEFORE adding a gh-calling target:

```bash
grep -nE -- '--repo.*\$\(REPO\)' Makefile   # must be empty; use '$(GH_REPO)' instead
```

A correct fix redded by an assertion about the shape it replaced is YOUR defect, not a gate bug —
classify it case 2, fix the branch, and prove the guard (RED on the old line, GREEN on the new) before
claiming green.

## Classify a red: gate defect (this lane) vs code defect (implementer)

A monitor lane reads the failing job's log and MUST decide which of two things a red is before it
reports or acts:

1. **Broken pipeline/gate** — the gate itself is wrong, misfires on valid input, or cannot load. This
   lane opens the gate-fix PR (fresh branch off the just-fetched `main`, one atomic commit).
2. **Code/test defect in the change under test** — the gate is working exactly as specified and the
   branch violated it. This lane reports the verdict + log to the planner/implementer and opens NO fix
   PR.

Read the failure at its source, not the check colour:

```bash
gh run view <run> --repo <o>/<r> --log-failed 2>&1 | grep -nE 'Error|FAIL|assert|over|now,' | head
```

**The ratchet/count-gate rule (the case most easily misread as a pipeline bug).** A gate that records a
COUNT of a thing it wants to keep shrinking (bare import roots, prose/decode debt, warnings) reds the
moment the branch ADDS one. Its log reads like `bare: N now, M recorded — … a new file adding its own
root is refused here`, then lists EVERY counted site. When the baseline stores only a count (not a
set), the gate cannot name the culprit — find the one the PR introduced by intersecting that list with
the diff:

```bash
gh pr diff <n> --repo <o>/<r> --name-only   # only a changed test/module can be the +1
```

That red is a **code/test defect (case 2)** — the ratchet is working as designed. Route it to the
implementer with the exact new line; **never 'fix' it by bumping the recorded count** (that defeats the
ratchet) and never open a gate-fix PR for it. Guard against the inverse: a red naming a DELETION on the
branch (`X is not indexed`) is a branch-local gap whose fix is restoring the row — classify the two
separately (addition→implementer, deletion→restore), report both, and let the owning lane act.

## A third class: a pre-existing red on `main` that reddens EVERY PR

Not every red is this lane's gate bug (case 1) or the branch's defect (case 2). A gate that reads a
file FROM `main` — `docs/ARCHITECTURE.md`'s `measured at <sha>` census pointer, a shared table, a pinned
baseline — can go red on `main` itself, and then EVERY open PR inherits that red regardless of its diff.
Three signs together confirm it is external:

- the failing step lives in a file your `git diff --name-only` does NOT touch, and the same check passes
at your own HEAD (e.g. your HEAD's pointer is a real ancestor while `main`'s is not);
- the IDENTICAL gate reddens on an unrelated open PR (`gh pr checks <other-n> | grep <gate>`);
- the failing log names a value that is wrong at `main`, not at your base.

When all three hold: (1) report the red with the file:line, the sha, the run id, AND the unrelated PR
that reddens identically — that third fact is what proves it external; (2) check whether a canonical fix
already exists (`gh pr list --state open --search <topic>`, or the issue/PR the planner cited) and route
the finding there; do NOT open a second fix. If a fix you already opened is closed as a duplicate, leave
it closed — re-cutting `main`'s shared file a second time is the duplicate the board rejects. Never fold a
`main`-wide fix into an unrelated PR: its diff must stay exactly the change under review.

## "My tests pass" is NOT "the PR is green"

The decisive verification is the PR's CI at its head, never your local or container suite. A locally
green suite plus a red `scope` / `linux/unit` leg is a RED PR: do not arm, merge, or claim completion.
State the attribution honestly — what your diff does and passes, what the external blocker is, and that
the PR goes green once that blocker merges and the branch re-runs. Claiming completion while a required
check is red is the exact overclaim the completion-integrity guard rejects; report standing, not victory.
