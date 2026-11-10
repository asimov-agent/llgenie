# Settling a disputed gate claim by re-running the gate

Use when a reviewer, planner or dispatch claims a specific gate is red (or still red) and
the run list does not reproduce it, or when you must prove a fix that already merged
actually satisfies the gate that redded it.

## The rule

**Prove a gate by executing that gate against the live artifact, not by re-reading a status
roll-up.** A check-run conclusion, a badge and a reviewer's recollection are all claims
about a sha and a moment. The gate executable is the fact.

## Procedure

1. Re-measure the PR first:
   `gh api repos/<o>/<r>/pulls/<n> --jq '[.state,.merged,(.merged_at//"-"),.head.sha]'`.
   If it already shows `merged=true`, the red at the cited head is superseded — do not amend,
   re-open or re-cut the vehicle to satisfy a stale dispatch.
2. Find the gate's entry point: gates live in `scripts/check_*.py` with a `check` / `report`
   subcommand pair. Discover the invocation instead of guessing:
   `python3 scripts/check_<gate>.py --help` — its docstring states the acceptance semantics.
3. Feed the gate the **live** artifact, not a file from memory:
   `gh api repos/<o>/<r>/pulls/<n> --jq .body > /tmp/pr-body.md`, then
   `python3 scripts/check_pr_acceptance.py check --body-file /tmp/pr-body.md --repo <o>/<r>`.
   **A gate that reads an artifact you did not pass exits 0 trivially — that is a false
   verification, not a pass.** Omitting `--body-file` makes the body `""`, `closing_references("")`
   returns no linked issues, and `check-pr-acceptance` prints `OK` with rc=0 while proving
   nothing. Pass every argument the CI step passes (`--body-file`, `--repo`, and for the
   hygiene gates `--head`/`--base`); a green you cannot reproduce with the CI's own args is
   not evidence. Same trap for a `tail -1; echo $?` pipeline (step 4): the pipe hides the
   real exit code.
4. Run it **unpiped**. `cmd | tail -1; echo RC=$?` reports `tail`'s status, so a red gate
   reads `RC=0`. Run the gate alone and read its own exit code; do the same for any
   `make check-*` target. **Pass an explicit `workdir=` on every terminal call** — the session's
   persisted cwd survives across calls, so a prior `cd` into a pruned/recreated worktree leaves
   later commands failing with `cd: <stale path>: No such file or directory`, exit 126, as if the
   tool were broken; setting `workdir=` per call sidesteps the stale cwd entirely.
5. Record the quoted output and exit code on the issue as the task-relative proof.

## Refreshing a stale gate run (the artifact changed, the head did not)

When a gate redded on a **stale snapshot** — the thing the gate reads (an issue body, an
acceptance tick, a review marker) changed *after* the run started, while the head sha is
unchanged — the red is an honest past reading, not a live defect. Do **not** push an empty
commit, do **not** weaken the gate, do **not** tick boxes yourself (a lane never self-ticks).
Refresh the run and let the gate re-read the live artifact.

1. Re-measure first: `gh api repos/<o>/<r>/pulls/<n> --jq '[.head.sha,.mergeable]'` and confirm
the artifact the gate reads now satisfies it (e.g. `gh api repos/<o>/<r>/issues/<i> --jq .body | grep -c '\[x\]'`).
2. **`ci.yml` is trigger-only (`push`, `pull_request`) — it has no `workflow_dispatch`.** So a
   same-head re-evaluation has exactly one honest mechanism: `rerun-failed-jobs` on that run,
   not a dispatch. Never fabricate a push to force a run.
   `gh api -X POST repos/<o>/<r>/actions/runs/<run>/rerun-failed-jobs` (accepted; rc=0 is only
   the HTTP accept — read the run back).
   Prefer `rerun-failed-jobs` over rerun-all: the failed **`scope`** job re-executes
   `check-pr-acceptance`, which reads the issue body at **run time**, so the tick is now seen;
   rerun-all re-runs the heavy matrix for nothing.
3. Poll to completion and record the fresh conclusion — `queued` with `conclusion:null` is
   not yet a result: `gh api repos/<o>/<r>/actions/runs/<run> --jq '.status+"/"+(.conclusion//"running")'`.

**The `make check-pr-*` gate steps run in the `scope` job, not the `guard` job.** In a PR ci
run the `guard` job executes only the owner/collaborator trigger guard; `check-pr-closing`,
`check-pr-acceptance-form`, `check-pr-acceptance`, `check-pr-agents-line`, `check-pr-sync-line`
and `check-pr-openspec-change` are steps of the `scope` job. To read a gate's verdict, enumerate
the `scope` job's steps — `gh api repos/<o>/<r>/actions/jobs/<scope-job-id> --jq '.steps[]|[.conclusion//.status,.name]|@tsv'`.
Pulling the `guard` job's log shows only the collaborator gate and looks like the gate never ran;
the run-level `conclusion: success` is authoritative that every gate step passed, but name the
specific `scope` step for the report.

**Map a check-run to its workflow by API, never by name.** A check-run called `guard`, `scope`
or `ci-verdict` does not name its workflow, and they live in *different* files (`guard` in
`ci.yml`, `scope` in `scope.yml`, `ci-verdict` in `ci-verdict.yml`). Enumerate from the
**upstream** API — `gh api repos/<o>/<r>/actions/workflows --jq '.workflows[]|{id,name,path,state}'` —
not the local working copy: a clone is often a stale fork snapshot whose `.github/workflows/`
is missing the files you are looking at on the wire. To read a workflow file at a remote sha,
`git show <main-sha>:.github/workflows/<f>.yml` after fetching that sha.

## Reading the result

- **`check-pr-acceptance` has two finding classes; only one is a designed hold.**
  `acceptance-unchecked` = a criterion in the linked issue is still `- [ ]` and the PR body
  does not name it out of scope. On an OPEN, un-reviewed PR this is the normal #1644
  verdict-gated hold — the reviewer's write-back ticks it; a lane never self-ticks (#948).
  `acceptance-exceeds` = the PR body carries its OWN `- [x]` for a criterion the issue still
  has `- [ ]` — that is a real defect in the PR body, not the hold. To tell them apart: grep
  the live PR body for `- [x]`; if none overlap the issue's unticked leads, every finding is
  `acceptance-unchecked` and the red is the designed pre-review state, not your bug.
- `check-pr-acceptance check` exits 0 when the closed issue's unticked `## Acceptance criteria`
  are named out of scope in the PR body. `report` printing `<issue>: 0/3 criteria ticked`
  alongside exit 0 is **correct**, not a contradiction: criteria stay honestly unticked
  while a single-lane vehicle passes via the exemption. Never tick boxes to "fix" the report.
- **`skipped` is not `passed`.** Filtering a run's jobs/steps to `conclusion==failure` makes every `skipped` step look green. An early non-success guard step (`check-pr-base`, `check-pr-acceptance`) short-circuits the workflow, so downstream jobs (`linux`, an openspec job) report `skipped`, not run-and-passed — the gate that would have judged your change never executed. Enumerate **every** step with its conclusion (`gh api repos/<o>/<r>/actions/runs/<run>/jobs --jq '.jobs[]|select(.id==<job>)|.steps[]?|"\(.name[:55]) | \(.conclusion // "RUNNING")"'` via `python3 -c` since jq's `@tsv` mis-serialises the step object) and treat `skipped` as *unmeasured*; prove the change's own gate locally rather than inferring a pass from the failure set.
- **A red `ci-verdict` check-run that reports `NO DECISION` / `NO VERDICT` is a *cascade*, not a
  separate defect.** When a run's guard step fails, it publishes no scope decision, and
  ci-verdict reds the whole run (`ci-verdict: red (run <id>)`, `[ci-scope] NO DECISION`). Trace
  it back to the failing guard step — do not file it as a new red. Both guard and scope runs
  red on the same single step; read the step list, not the check colours.
- Census-style gates measure at a recorded referent sha and red only when that referent is
  **not** an ancestor of HEAD (`census measured at <sha>; referent <sha> is not an ancestor of
  HEAD`). A stale referent is a genuine red; a member referent is a genuine pass.
- `make check-docs` chains the index gate, the doc gate and the census gate; read all three
  lines, since one can pass while the census referent is stale.

## The ci.yml guard gate-set — exact invocations

The arg shape differs per gate; `--help` confirms it, and these worked as-is:

```
python3 scripts/check_pr_authors.py   check --base <base-sha> --head <head-sha>
python3 scripts/check_pr_closing.py   check --body-file /tmp/pr-body.md --base <base-sha> --rev <head-sha>
python3 scripts/check_pr_hygiene.py   agents-line     --head <head-sha> --base <base-sha> --body-file /tmp/pr-body.md
python3 scripts/check_pr_hygiene.py   sync-line       --head <head-sha> --base <base-sha> --body-file /tmp/pr-body.md
python3 scripts/check_pr_hygiene.py   openspec-change --head <head-sha> --base <base-sha> --body-file /tmp/pr-body.md
python3 scripts/check_workflows.py    check
python3 scripts/check_wiring.py       check
python3 scripts/changes_index.py      check
```

Run the whole set against the committed head before pushing — a hygiene red is cheaper to
find here than in a review cycle. `check-wiring` and `changes_index.py check` catch a new
script/note that is not wired or not indexed.

## When the fix lives in a retained/sibling vehicle, not yours

If a dispatch names a defect but the owner has reconciled it to another lane's vehicle (or a
sibling landed the identical fix), the fix is **not** yours to re-implement — one vehicle per
issue (#824). Your task-relative act is to **measure that vehicle green on the wire and record
the measurement on it**, never to open a second fixing PR.

Enumerate every check-run on the head (not the rollout badge — a cancelled run reads red, a
job that fails to load shows zero jobs and reads clean):

```
head=$(gh api repos/<o>/<r>/pulls/<n> --jq .head.sha)
gh api repos/<o>/<r>/commits/$head/check-runs --jq '.check_runs[]|"\(.name): \(.conclusion)"' | sort
```

all-`success` across the full set (unit, guard, scope, openspec, hygiene jobs) is the wire
evidence. Reproduce the fix's deterministic path locally too (the guard tests pass, rc=0
unpiped) so the re-judge shape is proven, then post the measured state as a comment on the
retained vehicle and verify it landed. To read a comment back, take the **numeric** id from the
URL (`gh issue comment` prints `.../pull/<n>#issuecomment-<id>` — `basename` on that yields
`<n>#issuecomment-<id>` and 404s; strip the fragment and use the trailing digits), then
`gh api repos/<o>/<r>/issues/comments/<id> --jq '{id,issue:.issue_url|split("/")|last,user:.user.login}'`.
Landing/review is the implementer/reviewer/owner call — this lane never merges or arms (#1088).

## An aggregate pass count is not proof the named test passed

A CI log that ends `3156 passed, 13005 deselected` proves *something* ran, not that the six
tests your fix targets executed and passed — under `-q` a passing test prints nothing, and a
suite run with `-m not network` can deselect the very file you changed. When a dispatch says
"confirm all N pass", an aggregate line is not the confirmation.

- Run the exact nodeids **with `-v`** at the wire head so each `PASSED` is a visible line:
  `python -m pytest <file>::<test> ... -v -p no:cacheprovider`. Quote the six `PASSED` lines plus
  `N passed` in the report; an aggregate-only claim invites a re-run demand you then have to earn.
- Cross-check the file names appear in the deselect-safe invocation (grep the CI log for the
  three changed test files) so you know the aggregate actually included them.

## Mutation proof — prove the guard catches the bug, on the OLD tree

A gate that only ever ran on the fixed tree has demonstrated nothing (my rule #4). Before
trusting a new/edited test, run it against the pre-fix blob and count the reds, then against
the fix and count zero. Recipe inside the worktree container:

```
W=<worktree>; OLD=<pre-fix-sha>; NEW=<fix-head-sha>
git -C "$W" checkout -q $OLD -- .github/workflows/<f>.yml docs/<doc>.md   # plant the old blob
docker run --rm -u root -e PYTHONPATH=/repo/scripts -v "$W":/repo:rw -e HOME=/root -w /repo \
  <test-image> python -m pytest <the nodeids> -q   # MUST fail, record "6 failed"
git -C "$W" checkout -q $NEW -- .github/workflows/<f>.yml docs/<doc>.md   # restore the fix
```

Then verify the tree is genuinely back at the fix before you report — three cheap checks, all
must hold: `git -C "$W" rev-parse --short HEAD` == the PR head from
`gh api repos/<o>/<r>/pulls/<n> --jq .head.sha`; `git -C "$W" status --porcelain | wc -l` == `0`
(delete any monitoring scratch file you left, e.g. a poll-loop state file, so status is truly
clean); and re-run the nodeids once on the restored tree to see `N passed` again. A stash/checkout
round can leave a stash entry or an uncommitted hunk behind — the clean status count is the proof
it did not.

## Verify at the wire head, across every gate class — not one test

A green needs more than the unit result. Before declaring a workflow-file fix done, produce all
of: (1) YAML-parse assertions on the committed file (the `jobs`, `needs`, and step `run` strings
you added — assert them, do not eyeball); (2) `make check-workflows` (every YAML parses, every
`workflow_run` roster is routed, no load-rejected job-level keys) unpiped so its own exit code
shows; (3) the workflow's own test file in full (`tests/test_<workflow>.py`), not just the guard
subset; (4) the six targeted nodeids `-v`. All four, then the per-test lines are the evidence.

## Disposition

A merged and green vehicle is not re-opened and not amended. Report the gate replay, the merge
sha and its ancestor status, then stop.
