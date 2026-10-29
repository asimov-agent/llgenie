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

## 8. Rename greps: search BOTH names before believing a rename is complete

A rename PR commonly lands half-applied: the test definitions and the roster/fixture entries move to
the new symbol, while guard assertions and truth tables still name the old one. Grep the old AND the
new name across `tests/` and the fixtures, not just the diff — a red guard test asserting a roster key
that no longer exists is the signature, and the fix belongs inside the PR's own test file, not in the
roster.
