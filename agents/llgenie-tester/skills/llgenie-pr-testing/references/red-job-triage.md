# Triage recipe: from a red check to a named failing test

A red check on a PR gives you a name and nothing else. Two routes lead from it to the failing test:

- **The job log**, which IS readable — `gh api repos/<owner>/<repo>/actions/jobs/<job-id>/logs
  --allow-escape-sequences | sed 's/\x1b\[[0-9;]*m//g' | grep "FAILED tests/"`. Zero bytes means the
  `gh` escape-sequence guard refused, or the RUN is still in flight (`--log-failed` only works after
  the run completes, even when the job has), not that the log is gone.
- **The metadata**, when the log genuinely is not there (rerun deleted, retention): the steps below.

The check-run annotation frequently carries only `Process completed with exit code 2` — make's word
for "a recipe failed", not pytest's — so it identifies no test on its own.

## 1. Resolve the job, then read its steps

```bash
gh api repos/<owner>/<repo>/actions/jobs/<job-id> \
  -q '.name, (.steps[] | "  \(.number) \(.conclusion//"-")\t\(.name)")'
```

- `steps[]` names the failing step exactly (`make ci-unit (…gates…)`, `make ci-install (…)`, …) even
  when the run-level conclusion is `cancelled` — cancelling a run after a job failed rewrites the
  run's word, never the job's.
- `gh pr checks` collapses cancelled runs and duplicated check names into `fail`; use it to find *which*
  check to look at, never as a count of failures.
- `started_at`/`completed_at` on the same payload give the duration, which is evidence by itself:
  compare it with the wait/timeout constants the script declares (`grep -n "TIMEOUT\|WAIT" <script>`).
  A job that dies just past a `30 * 60` wait cap died of that cap, so the assertion you are looking
  for does not exist — the missing artifact is the finding.

## 2. Narrow the target before running anything

1. The PR's changed files: their own test modules are the first suspects, and they are cheap.
2. Then every test that *references* the changed modules (`grep -rl "<module>" tests/`), not just the
   ones in the diff.
3. Then the job's other steps in execution order: a `ci-<job>` mega-target runs its gates in a fixed
   sequence, so the first failing gate decides. Run them individually with `PATH` pointing at a venv
   that has the gate's imports (`pyyaml`), capturing each exit code.
4. Only then the whole suite, and only with `-x` so it stops at the first failure.

Reading a mega-target's recipe is also how you learn *which* sub-step owns a wait: `ci-install` may be
almost entirely `wait-for-published-artifact` + install, so a red install is a publication-ordering
fact, not an install bug.

**Reproduce a wait-for-artifact red in seconds — never by letting the cap expire.** Run the wait
target itself (`make ci-wait-engine-images ARCH=<arch>`) and read the first poll lines: they name the
exact missing reference (`[install] not published yet: <registry>/<image>:<hash>-<arch>; waiting 20s`),
which IS the finding. Then run the identical target at the base sha as the comparator: a tree whose
artifact exists prints `[install] every image install pulls is published` and exits 0. Stop the waiting
run once those lines are captured, and quote the script's own wait constant for the cap
(`grep -n "WAIT\|TIMEOUT" scripts/<script>.py`), never the CI job duration as the cap.

## 3. The baseline control is half the answer

Run the identical command at the branch's base sha (`git worktree add --detach <dir> <base-sha>`).
"Does not reproduce on `main`" only counts when you ran it there; a reviewer's first question is
whether the red came with the PR or was already on the branch.

## 4. Budget: know what a local full run costs before starting it

A gate that reaches a model/dataset hub is rate-limited without a token, and the same suite that takes
~15 minutes in CI can crawl for hours locally (measured shape: a few percent of the suite in ten
minutes). Before launching the suite, check whether the token the workflow injects is available
locally (`HF_TOKEN`, `GITHUB_TOKEN`); without it, treat targeted files + `-x` as the only viable loop
and say so in the report rather than quoting a run that never finished.

## 5. Pre-merge measurement routes and their limits

- `gh workflow run <wf> --ref <branch>` executes on any branch that CONTAINS the workflow file; it
  fails with `HTTP 422 Workflow does not have 'workflow_dispatch' trigger` when the default branch does
  not have that file yet. A dispatch also has no `base_ref`, so the run reports the diff against the
  default branch and proves the classifier's fallback only — never `paths-ignore` or a `push` run.
- A branch can never produce an empty diff against its base, so the "empty diff → widen to full
  pipeline" branch of a classifier has no CI observer before merge; the CLI run on the branch is the
  only pre-merge evidence, and that limitation belongs in the row rather than as a blank.

## 6. Row verdict vocabulary (so a table cannot be misread)

| word | meaning |
|---|---|
| proven | `status=completed`, `conclusion=success`, `headSha` == the probe's current head |
| RED | completed at that head with a failing conclusion |
| no verdict | `queued`/`in_progress`/`cancelled`, or the run sits at a head that has been force-pushed away |
| no evidence | no run exists at the current head at all |

## 7. A batch of reds is not necessarily one cause — bisect by commit

A dispatch that says "N PRs are red, find the cause" may be handing you one cause or several. Do not
accept the framing: take the failing node ids, then run that same set at each commit that touched the
file under test since the branch point.

```bash
git worktree add -q --detach /tmp/red-<commit> <commit>
# then the same pytest node ids in each worktree, in the CI image
```

Measured shape worth expecting: a batch of six went **6 failed at HEAD**, **4 failed / 2 passed** at the
commit that deleted a workflow group, so two of the six belonged to a *later* commit that rewrote an
unrelated part of the same file. Each cause needs its own decision, and the issue title (written from
the first cause) is usually wrong about the rest — say so explicitly rather than folding them together.

## 8. A job cancelled on an exact-minute boundary is a TIMEOUT CEILING, not a red

A `linux / unit` job that ends `completed / cancelled` after N minutes is the most misread red in this
repo: it is neither `failure` nor a hang, and it is not evidence about the diff.

**The three-read signature** (all three, or it is something else):

1. `started_at → completed_at` lands on a whole number of minutes, ±1 s (e.g. 11:30:08 → 12:30:24).
   GitHub's *default* job timeout is 360 min, so a 60/90/120 boundary is a number somebody configured;
   arbitrary durations (37 min, 51 min) are not a ceiling.
2. The log's last lines are teardown, not tests: `Post job cleanup.`, then
   `Terminate orphan process: pid (<n>) (make)` / `(docker)`, then the job's `##[warning]` epilogue.
3. The log contains **zero** `FAILED`, `Error`, `assertion`, `Killed` or `exit code` lines across its
   whole length — grep each and count. A red has these; a ceiling cancel has only cleanup chatter.

**Attribute the ceiling with the JOB BLOCK, never a grep line number.** `grep -n timeout-minutes`
returns bare line numbers, and the nearest preceding 2-space key is what owns each one:

```bash
awk '/^  [a-z0-9-]+:|timeout-minutes/{print NR": "$0}' .github/workflows/ci.yml
```

A row that is `uses: ./.github/workflows/<callee>.yml` (reusable workflow call) is bounded by a
`timeout-minutes` in the CALLEE, never by the caller's — a caller-side `timeout-minutes: 60` sitting
100 lines above the `linux:` row belongs to a different job (`ci-images`) and reading it as unit's cap
sends you to the wrong file. Grep the callee (`pipeline.yml`) for the stage's own bound, and if no
bound is found, say the boundary was measured and the source was not pinned — do not invent one.

**What it is worth, and what it is not:**

- It is **no verdict** (row vocabulary §6), never a `do-not-merge`, and never "unit hangs". The
  duration matched its configured cap, so the suite may well have been finishing.
- It is a **configuration/contention observation**, and the pipeline lane owns the remedy — hand it the
  run id, job id, head sha, the exact duration and the zero-marker log evidence, and say explicitly
  that you are not claiming a hang.
- **Get the same-window control before you say anything about the suite.** A same-suite run that
  concluded `success` while your job was in flight, at a fraction of the duration, is what separates
  "the ceiling is too low" from "this head is abnormal". Its branch name often IS the fix vehicle
  already open; never open a competing one.

**Clearing it is a re-run, and a re-run is safe where a push is not.**

```bash
gh run rerun <run-id> --failed      # re-executes the same head; cancels nothing
```

A re-run re-executes one run at its current sha — it does not push, does not create a run for a new
head, and triggers no `concurrency: cancel-in-progress`, so it cannot destroy another lane's matrix
(the warning against re-running into a lane's push is about pushing). It still has rules:

- Re-run **once**. Disclose it in the same comment (`attempt-2 job <id>, in_progress since <hh:mmZ>`) so
  the next reader is not comparing two runs at one sha without knowing why.
- If attempt-2 hits the ceiling too, **stop**. Do not loop: a loop of 60-minute units is a queue hog,
  not evidence, and the second identical cancel has told you everything the third would.
- A cancelled check keeps `mergeStateStatus=BLOCKED`; the PR stays OPEN and armed, which is correct —
  the queue waits for a green, it does not need the check deleted.

## 9. Rename greps: search BOTH names before believing a rename is complete

A rename PR commonly lands half-applied: the test definitions and the roster/fixture entries move to
the new symbol, while guard assertions and truth tables still name the old one. Grep the old AND the
new name across `tests/` and the fixtures, not just the diff — a red guard test asserting a roster key
that no longer exists is the signature, and the fix belongs inside the PR's own test file, not in the
roster.

## 10.5 The arm enablement FACT is `auto_merge.enabled_at`, never the request identity (#964-class)

A populated auto-merge request object does NOT mean the PR is armed. GraphQL `autoMergeRequest` and REST `auto_merge` both expose `enabledBy`/`enabled_by` and `mergeMethod`/`merge_method` as soon as the arm REQUEST is created — but the enablement TIMER is a separate field: REST `auto_merge.enabled_at` (GraphQL `enabledAt`). READ THAT: `enabled_at=null` with `enabled_by` populated means the request was created but NOT enabled — auto-merge cannot fire on its own. Claiming "armed" from a populated `enabled_by`+`merge_method` is the slip that recurred on #1247, #1256×3, #1259, #1260.

Check: `gh api repos/<owner>/<repo>/pulls/<n> | jq '.auto_merge.enabled_at'` — NON-NULL is the only state that fires on approval; null means "pending request, not enabled". For a PR blocked on `REVIEW_REQUIRED`, enablement often stays null until the required review is granted (that repopulates `enabled_at`). Post honest status; never claim armed until a fresh read shows `enabled_at` non-null.

## 10.5a The arm-fact lives in raw REST `auto_merge.enabled_at`, not GraphQL `enabledAt` (#964, 5-lane recurrence)

For an `--auto` request, the *request identity* is always populated (`enabledBy`, `mergeMethod`), but only a genuinely-enabled arm populates the *enablement fact*. On GraphQL `autoMergeRequest` the field is `enabledAt`; on raw REST `auto_merge` it is `enabled_at`. Read the one the checker keys on: `gh api repos/<o>/<r>/pulls/<n> --jq '.auto_merge.enabled_at'`. Null = "pending request, not enabled" — quote that verbatim instead of "armed". Verify the SAME call the checker uses; a GraphQL identity-enabler is never a REST enablement fact.

## 10. Verify a census-repoint PR (shared-gate unblocker, #1221/#1222)

When a PR exists only to re-point `docs/ARCHITECTURE.md`'s `measured at <sha>` off a non-ancestor
(merged-but-squashed-away sha) onto a real ancestor with re-measured counts, `scope/check-docs` is red
for everyone on `main` and this PR is the fleet unblocker. Verify it as carefully as the gate it fixes,
and do not let a re-point weaken the ancestor + re-measure requirement.

1. **Fetch the PR head into a LOCAL ref first — `refs/pull/<n>/head` is not a mergeable argument.**
   `git merge-tree --write-tree origin/main refs/pull/<n>/head` dies with `not something we can merge`:
   `refs/pull/*` lives on the remote only and no local object happens to have that name yet. Fetch it,
   then use the local ref everywhere: `git fetch origin refs/pull/<n>/head:refs/remotes/pr/<n>` and
   `git merge-tree --write-tree origin/main refs/remotes/pr/<n>`. The same local ref feeds the
   worktree add — one fetch, then never re-reference `refs/pull/*` locally.
2. **Prove the merge is clean BEFORE trusting any count.** `git merge-tree --write-tree <main>
   refs/remotes/pr/<n>` exit 0 = merges into current `main` with no conflict; the printed tree id is
   your clean-tree evidence. A conflict here makes every later count meaningless.
3. **Check the pointer on the SHA, not the file.** `git cat-file -t <pointer>` must be `commit` and
   `git merge-base --is-ancestor <pointer> HEAD` must be YES. A pointer to the `main` you just fetched
   is trivially an ancestor of anything built on it — that is why re-pointing onto current `main` is
   the cheap correct fix.
4. **Run the REAL gate on the clean tree, never the PR body's claim.** `git worktree add --detach <dir>
   refs/remotes/pr/<n>` (base is current `main`, so the checkout IS the post-merge content), then
   `make check-architecture-census` and `make check-docs`. Expect RC 0 and the gate's own line:
   `[census-gate] OK — census measured at \`<sha>\` (tracked=…, testspp=…, changes=…); referent
   \`<sha>\` is an ancestor of HEAD (<head>)`. **Prove the gate is not weakened:** read
   `scripts/check_architecture_census.py` — `commit_is_ancestor` + `measure(<pointer>)` must still be in
   `check()`. A legitimate re-point PR changes ONLY the pointer sha + numbers, never the gate.
5. **Cross-check the CI leg.** `gh pr checks <n>` plus the check-runs on that exact head; the `scope`
   job's log must show `make check-docs` invoking `check_architecture_census.py`. Report run id, job id
   and conclusions — a local RC 0 alone is not the PR's verdict.
6. **`mergeStateStatus=BLOCKED` here is usually `reviewDecision=REVIEW_REQUIRED`, not a red.** Read
   `--json mergeable,mergeStateStatus,reviewDecision`: `MERGEABLE` + BLOCKED + REVIEW_REQUIRED means a
   required owner approval is pending. `gh pr merge --auto` exits 0 and leaves `autoMergeRequest=null`
   because the arm cannot engage before the approval exists. Report `auto=none (blocked on required
   review)` and hand the arm decision on — never hand-approve, never `--admin`.
7. **Clean up the verify worktrees** — the evidence lives in the PR comment, not the tree: `git
   worktree remove --force <dir>` + `git worktree prune`, then confirm `git worktree list` no longer
   shows it. A verify-only dispatch that leaves a worktree behind is unfinished housekeeping.
