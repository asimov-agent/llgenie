# Red-run triage, dispatch diagnosis, and falsification in a worktree

Read this when a pipeline is red, when a dispatched workflow seems to do nothing, or when you need to
prove a test actually locks the behaviour you just changed.

## 1. Triage a red run in this order

```bash
gh run view <run> --repo asimov-agent/llgenie --json name,conclusion,event,headBranch,jobs \
  --jq '{name,concl:.conclusion,ev:.event,br:.headBranch,
         failed:[.jobs[]|select(.conclusion=="failure")|{name,id:.databaseId}]}'
gh run view --repo asimov-agent/llgenie --job <job-id> --log 2>&1 | grep -iE "FAILED|Error|no module|denied" | tail -20
```

- One red job in a 25-job run is usually NOT the pushed commit. Say what the job actually ran before
the commit is blamed; the failing step's own message is the verdict.
- `conclusion=failure`, `name` equal to a workflow FILE PATH, and **zero jobs** = GitHub refused the
  file at parse time, not a failed job. See the workflow-YAML reference; do not chase it as a code
  regression.
- A job that is `pending` with **`jobs: []`** (or a single job never created) is queued on a
  `concurrency:` group, not waiting for a runner. See §2.
- Transient network assertions in the suite (`HTTP 429`, `TimeoutError: The read operation timed out`
  from a live Hub call) look like real failures. Re-run that one test file in isolation before
  believing it; if it passes, the run's red is a flake and the code defect behind it may still be real
  (an un-retried read timeout is a code bug even when the retry of the *test* is green).

## 2. A dispatched workflow that "does not work"

Diagnose before changing the workflow: the dispatch surface, the guard, and the matrix can all be fine
while the run still does nothing visible.

```bash
gh workflow list --repo asimov-agent/llgenie --all          # is the file active, and its display name
gh run list --repo asimov-agent/llgenie --workflow <file>.yml --limit 5 \
  --json databaseId,status,conclusion,headBranch
gh run view <run> --repo asimov-agent/llgenie --json status,jobs --jq '{status, njobs:(.jobs|length)}'
```

**`status: pending` + `njobs: 0` = concurrency queue.** A constant `concurrency: group:` with
`cancel-in-progress: false` means every other dispatch of that workflow waits behind the running one —
including a narrow `engine=<id> arch=<cpu>` dispatch behind a multi-hour full sweep. It presents as
"the dispatcher is broken" with no log at all.

Fix the group, not the trigger surface:

```yaml
concurrency:
  # publishing runs share ONE group (two pushes must not race on the same :<arch> tag);
  # build-and-verify runs are keyed by the selection so a narrow dispatch runs alongside a sweep
  group: engine-build-${{ inputs.push == 'true' && 'push' || format('build-{0}-{1}', inputs.engine, inputs.arch) }}
  cancel-in-progress: false
```

Verify the fix by dispatching again **while the big run is still going** and watching the new run reach
`in_progress` with real jobs — not by re-reading the YAML. `make check-dispatch-forms` only proves the
inputs are documented in the README table; it says nothing about queueing.

A `workflow_dispatch` can only be dispatched against a ref that exists in the **target** repo. A fork
branch is un-dispatchable; if a live dispatch is the proof you need, either push the branch to the
upstream repo temporarily (then delete it) or accept that the post-merge run is the verification and say
so plainly.

## 3. A CI target that no matrix row reaches rots

When a matrix resolves to zero rows, its jobs show up as one `skipping` row with an **unexpanded**
name (`test-published-${{ matrix.engine }}-${{ matrix.variant }}`). That is the signal that the target
the row would run has not been exercised in a long time — when the matrix is repopulated (a new params
tree, a re-enabled variant), expect the target itself to be broken.

```bash
gh run view <run> --json jobs --jq '[.jobs[]|select(.name|startswith("test-published"))]|length'
```

## 4. A make recipe must never run pytest on the host

A bare `python3 -m pytest` in a recipe works locally (the venv has pytest) and fails on every CI runner
with `/usr/bin/python3: No module named pytest`. Run it through the seam the rest of the repo uses —
`$(TEST_RUN)`, `$(ENGINE_TEST_RUN)`, `$(call engine_test,…)` (the test image with the engine's env), or
an explicit `llgenie/test:latest` — and carry the env in with it:

```make
test-published-engine:
	$(call engine_test,LLGENIE_PUBLISHED_PULLED=1 LLGENIE_TEST_ENGINE="$(ENGINE)" LLGENIE_TEST_ARCH="$(ARCH)") \
		python3 -m pytest -q -p no:cacheprovider tests/test_published_engine_binary.py
```

Lock it with a text-level guard, not a comment: parse the Makefile, join `\`-continuations, skip recipe
comments, and fail on any recipe line that runs pytest without a seam. Allow the host-side venv seams
(`$(PY)`, `$(VENV_GUARD)`, `$(NATIVE_GUARD)`, `.../bin/python -m pytest`) — those carry pytest by
their nature, and flagging them makes the guard noisy enough to be disabled. Expose the rule as
`offenders(text)` so a synthetic Makefile can prove both directions; a clean real file proves nothing
about whether the rule works.

## 5. Falsify a fix without `git stash`

Do **not** use `git stash push <path>` / `git stash pop` to undo a committed change for a falsification
run in a worktree repo. The stash stack is **repo-wide and shared by every worktree**: if the push has
nothing to stash (the change is already committed) it still looks fine under `-q`, and the following
`pop` then applies *another* worktree's entry into yours — `UU` conflicts, untracked files from someone
else's branch, and a preserved entry you must not drop.

Use the file instead:

```bash
# 1. put the OLD behaviour back in the working tree (edit the file, do not stash)
# 2. run the targeted test in the test image and confirm it FAILS for the reason you expect
# 3. restore and confirm it PASSES
git checkout -- Makefile
```

Recovering from a stray `git stash pop`: `git reset -q HEAD -- <conflicted paths>`,
`git checkout -- <conflicted paths>`, delete files the pop created that are untracked, and re-restore any
TRACKED file you deleted while cleaning up. Leave the other worktree's stash entry in `git stash list`
— it is someone else's work, not yours to drop.

## 6. When the progress guard asks for a task-relevant mutation

A guard that watches for implementation progress may only observe the primary checkout, so commits and
edits made in `../llgenie-wt/<branch>` do not register and the guard keeps firing after real work. Do not
loop re-editing the worktree. Do a task-relevant action it does observe — `git pull` in the primary
checkout, or a live upstream dispatch/verification — and state plainly in the report where the change
actually lives (worktree path, commit sha, branch).
