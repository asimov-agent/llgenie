# Editing `engine-build.yml` itself (capacity / timeout / job-shape changes)

A change to the workflow that BUILDS the engines is still an engine lane PR — branch in a
`llgenie-wt/<slug>` worktree off a freshly fetched `origin/main`, one commit, docs pair, PR to `main`.
What differs from a params/Dockerfile change is the gate surface and the proof ordering.

## The workflow file is a NOTE_SURFACE path — the docs pair is mandatory

`.github/workflows/` is in the docs gate's NOTE_SURFACE, so the gate fails a workflow edit without
all three artefacts. Ship them in the SAME commit as the yml change:

1. `agent-wiki/<YYYY-MM-DD>-<slug>.md` — what changed, why the old shape was insufficient, and the
   verification that applies.
2. `docs/changes.d/<YYYY-MM-DD>-<slug>.md` — one row: `| date | title | [note](agent-wiki/...) | refs |`.
3. `make changes-index` (WRITE mode, not `check`) to regenerate `CHANGES.md` from the fragments —
   the diff must show exactly one new row plus the two new files.

Verify with `make check-docs` (and `CHECK_DOCS_BASE=<sha you branched from> python3
scripts/check_docs.py check`) before pushing. `make changes-index` writes; `make check-docs` checks —
never swap them and never quote an exit code as evidence without the printed fragment/target counts.

## Per-cell values: GitHub expressions have NO ternary

`timeout-minutes` and similar job fields accept `${{ }}` expressions, but the expression language has
no `cond ? a : b`. The idiom that returns an OPERAND (not a bool) is `&&` / `||`:

```yaml
timeout-minutes: ${{ (matrix.engine == 'vllm' && matrix.variant == 'rocm') && 480 || 240 }}
```

`cond && 480` yields `480` when cond is truthy (falls through `||`); a falsy cond falls through to
`240`. Parenthesise the condition — it makes the intent readable for the reviewer and keeps precedence
unambiguous. Use numeric literals, not quoted strings, for a numeric field.

## A timeout that fires is a claim about HOW LONG, not about WHY it failed

Before raising a cell's `timeout-minutes`, prove the cell dies of TIME and not of a STEP FAILURE that would reproduce at any budget. A run that is `cancelled` by its own 240-min cap on
`make build-engine` is ambiguous on its own — the same job also reports `step exited 1`. Reproduce
locally (a local build is a DIAGNOSTIC here, not a publish artifact — allowed only when the failure
cannot be read from the CI log, and the produced image is never claimed as a published one): if the
build fails at ~6 minutes with a hard error, the timeout was never the problem and raising it to 480
just buys a longer wait before the identical failure.

- Read the failing STEP and its error before the elapsed time. `step exited 1` + a uv/pip/compile
  message = a code or params defect; `conclusion: cancelled` with the build step still `in_progress`
  at the cap = genuinely time.
- A capacity PR and a defect PR are DIFFERENT vehicles. Do not fold the fix into the timeout diff: the
  timeout stays one line of capacity; the install/params defect goes in its own branch and PR.
- The measured discriminator is the local run's elapsed-to-failure. A cached-base local build reaching
  step `[N/M] RUN ... install` and dying in minutes is the defect; a local build that would itself
  exceed the budget is capacity.
- **Prove the cell is time-capped by the PIN, not broken by THIS PR, by comparing the SAME cell's run
durations across pin versions.** The decisive fact is usually not this one run but history: pull the
prior runs of the identical `<engine>-<variant>` cell from the runs API and read each cell's
`started_at`→end (or `timing.run_duration_ms`) alongside the pin it built from
(`git show <run-head>:containers/engines/params/<engine>.json | jq .pin`). If the cell SUCCEEDED at an
OLDER pin in ~N minutes but EVERY attempt at the NEW pin over-runs the fixed timeout and cancels at the
cap, the pin bump itself pushed the build past the budget — a CAPACITY blocker whose lever is the
timeout, and NO code change at this PR's head will make it fit. If instead the cell has NEVER completed
at ANY pin (no green baseline exists), suspect OOM/defect, not a tight budget — a timeout bump just buys
a longer wait before the identical death. The envelope is `successful-elapsed` from a green run at a
known-good pin; a fresh run past ~2× that envelope with the build step still `in_progress` is on the
same track to a cap-cancel. Cite the green run id + elapsed and the failing run id + `started_at +
timeout` self-termination instant — those numbers are what make the capacity PR derived, not guessed.

Rules that keep such a widening honest and reviewable:

- **Scope the exception to the ONE cell that needs it** (`(matrix.engine == X && matrix.variant == Y)`),
  so every other cell keeps the existing budget. Never raise the job-wide default to cover one heavy cell.
- **A capacity increase is not a gate change.** Say so explicitly: no step skipped, no assert weakened,
  no build step touched. The reviewer must be able to see the diff is one line of capacity.
- **State the measured reason in the note and the commit body** — how long the cell actually ran and
  whether its own timeout terminated it (run id + elapsed), so the number is derived, not guessed.
- **The one-line intent belongs in the commit subject**, so the diff is reviewable without the note.

## Ordering: the raised budget is only live on the ref the dispatch uses

`workflow_dispatch` executes the workflow file AT THE DISPATCH REF, so a new timeout/budget takes
effect only once the edit is on that ref. If the instruction is "raise it, then re-run the proof", the
re-dispatch goes at a head that CARRIES the edit (post-merge `main`, or the PR branch if that is what
you were told) — and the proof is still gated on a real `completed/success` run whose id and `head_sha`
you name. Dispatching before the edit is on the ref wastes the proof slot and produces a run that proves
the OLD budget.

Do not pre-emptively dispatch "while we wait for the merge"; one proof per merge, at the head that has
the change.

## Verifying the PR's own CI (GitHub API shapes that 404)

`GET /repos/{o}/{r}/pulls/{n}/checks` does not exist — it returns **404** and looks like "no checks
ran". The check-run list for a PR head is a COMMIT endpoint:

```bash
gh api repos/asimov-agent/llgenie/commits/<head-sha>/check-runs --jq '.check_runs[]|[.name,.status,(.conclusion//"")]|@tsv'
```

Cross-check it against the actual workflow runs, since a branch can show queued checks before a run
is visible:

```bash
gh api 'repos/asimov-agent/llgenie/actions/runs?branch=<urlenc-branch>&per_page=10' \
  --jq '.workflow_runs[]|[.id,.name,.status,(.conclusion//""),.created_at[11:19]]|@tsv'
```

One combined watcher polling the PR run, any in-flight publish run, AND `gh pr view <n> --json
state,mergedAt` is the cheap shape: one background process, one notification, breaking when both the
CI conclusion and the publish conclusion are non-null.
