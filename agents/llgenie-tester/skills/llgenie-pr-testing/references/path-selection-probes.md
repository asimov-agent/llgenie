# Path-selection PRs: depth on probes, run ids and expectations

Only needed when the change under test decides WHICH CI stages exist for a diff (classifiers,
`paths-ignore`, stage gates). The rules for the tests themselves are in SKILL.md §4; this file is the
measurement side.

## The instruments, in cost order

1. **Red-proof the guard (mandatory before calling it real).** Re-introduce the defect the guard is
   supposed to catch, run the affected test files in the test image, capture the failure, restore,
   re-run green. Report both outputs. A guard never observed failing is decoration, and the shape of
   the failure matters: an exact-set pin fails with a set diff, a repository-walking invariant fails
   with a COUNT ("43 offending paths") — the count is the thing a sample list cannot produce.
2. **Repository invariants** over `git ls-files` (SKILL.md §4) — catch paths that do not exist yet.
3. **Pre-flight the expectation column.** When an issue publishes expected classes/family counts,
   re-derive them from the CLASSIFIER code at the current head, never from the workflow YAML or the
   issue text — and through the **CLI**, which is the code path the workflow itself runs:
   `python3 scripts/ci_scope.py jobs --paths <p> --json` (exit 0 selected / 1 unclassifiable). Never
   build a table from the library entry point: on an empty or unclassifiable diff it can return a far
   smaller set than the CLI prints (measured 3 vs 22 of 22) because the widening lives in the command
   layer — an expectation taken from it is wrong in the direction that looks like a broken pipeline.
   Matching numbers mean a probe that disagrees later is a real finding; drifting numbers mean either
   a superseded head OR two parallel branches for the same change whose class tables differ —
   restate the column against the named merge candidate before anything runs.
4. **Probe PRs** (one throwaway branch per row) — the only instrument that exercises the trigger.
5. **`workflow_dispatch` on a branch** — the only real-queue measurement available before the change
   is on the base branch: `gh workflow run <wf>.yml --ref <branch>` executes the workflow file ON that
   ref, so it works on a feature branch but returns **HTTP 422 "Workflow does not have
   'workflow_dispatch' trigger"** for a ref that does not contain the file at all. A dispatch carries
   no `base_ref`, so the workflow falls back to the default branch and says so in its log: it proves
   the classifier's reported selection and the fail-open default, and it proves **nothing** about
   `paths-ignore` or a `push` run.

## Probe rows: what makes a run admissible

- A row is proven ONLY by a **fresh completed** run at the probe's head sha:
  `gh run view <id> --json status,conclusion,headSha`. `cancelled` = no verdict — a re-push leaves one
  behind and it is what makes people misread a queue problem as a broken PR.
- `gh pr checks`'s `fail` column is NOT a failure count: it maps cancelled runs and duplicate check
  names from different workflows onto one word. Count from `gh run view <id> --json jobs`.
- One probe can produce several run ids (the main pipeline, the always-on scope check, the docs
  workflow). Record every one; a missing workflow is a finding, not an omission.
- Never re-push a probe branch while capturing: `cancel-in-progress` is on for PRs, so the re-push
  kills the run you were waiting for.
- Two probes in flight at most, report between batches — each probe re-queues a matrix and a starved
  queue produces cancellations, not verdicts.

## The base-branch trap (costs a whole table)

A probe is only an instrument if the branch it is cut from ALREADY CONTAINS the selection logic, and
only triggers if the PR targets a branch its workflows accept:

- Gate `pull_request` on `branches: ["main"]` ⇒ a PR based on any other branch triggers **nothing**.
- Cut the probe from the feature branch and target `main` ⇒ the PR diff includes the feature commit,
  which touches `.github/**` (a wildcard) ⇒ every row records the full matrix, and the table is green
  for the wrong reason.

So state the prerequisite explicitly rather than discovering it per row: **no row is measurable until
the selection change is on the base branch**, and each row records both the head sha and the base
branch sha it was probed against. Verify what the base actually contains before promising rows:
`git cat-file -e origin/main:scripts/<classifier>.py`.

## Shared branches drift under you

Other agents push to the same branches. Before force-pushing a stack:

- `git ls-remote origin <base-branch>` and compare with your parent commit.
- A PR whose `changedFiles` suddenly includes the parent PR's files means the base lineage was
  rewritten: rebase onto the new tip (`git rebase origin/<base>`), re-run the tests, force-push.
- `gh pr edit <n> --base <branch>` to point a stack at its real parent after a base PR closes — GitHub
  auto-retargets dependents to `main` when the base PR closes, which silently turns a 2-file delta into
  a duplicate of the parent.

## Rows that need a decision, not a run

Control rows usually stall on wording, so surface them early: a fail-open row needs the definition of
"forced failure" (classifier raises vs. empty diff); an unclassifiable-path row must record BOTH that
the scope check went red and that the matrix still ran, or fail-open reads like fail-silent; an
empty-diff row may be unreachable from CI before the change merges (the workflow file does not exist
on the default branch and a branch's diff against it is never empty), so measure it through the CLI
and write that limitation into the row rather than leaving a blank; a
"is a red non-required check blocking?" row needs a deliberately broken gate and a recorded
`mergeStateStatus` plus the auto-merge decision function. A row whose prerequisite is an unmerged
feature belongs to that feature's issue, not to a widened probe.
