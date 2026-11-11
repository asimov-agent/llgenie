# Adding a pipeline to trending-local-llms (the five registrations)

A new `.github/workflows/*.yml` is not one file's work. Each of these gates is
INDEPENDENT and each one goes red on its own, so run all five before pushing:

1. **`tests/test_workflows.py` → `BOT_GUARDS`** — every guarded pipeline must be
   listed with its guard job name, or the guard-behaviour sweep is vacuous for it.
2. **`tests/test_workflows.py` → `DISPATCH_ONLY_COVERAGE`** — a pipeline with no
   `pull_request`/`push` trigger must name the test module that exercises its
   logic (`"bot.yml": "tests/test_x.py"`). Missing it fails with
   `runs only on [...] — no PR exercises it and no coverage is named`.
3. **`ARCHITECTURE.md`** — a §3 target-table row for every new make target, a §4
   subsection for the pipeline, `make architecture-refresh` for the generated §10
   inventory block, and a **§6 row for every new script** (the check requires a §6
   row per file in `scripts/`; a name that appears only in the generated block does
   not count). `make architecture-check` fails on a missing name, a missing §6 row
   and a stale block.
4. **`AGENTS.md`** — a §6b bullet, a §8 row for the new guard, and (rule 3c) a
   comment on the issue stating exactly which sections change and why.
5. **An OpenSpec change** — `make openspec-new NAME=<kebab>` FIRST, then
   `proposal.md` (Why / What / Impact / Not covered), `specs/<cap>/spec.md` where
   every Scenario carries `- **Test:** <path>::<test>`, and `tasks.md` with every
   box ticked. `make openspec-index` afterwards, or `openspec-check` is red.

## Branch naming is contract, not taste

`scripts/pr_closure.py` reads the head branch: `ci/data-gap-<n>-<slug>` or a
TRAILING `-<n>` means "this branch implements issue n", which forces exactly one
closing keyword bound to that issue. A bot that implements NO issue must use a
branch that no rule parses (a UTC stamp ending in `Z` does it) and a body with no
closing keyword — the refresh bot's `Closes #1` is the measured mistake.

## Prove the write path, never the YAML

Grepping a workflow (`"steps.x.outputs.y == 'true'" in wf`) is green over a step
that has never executed. Read the shipped `run:` body out of the YAML (PyYAML) and
execute it: real `git`, a real bare local remote, the repo's own identity seam
(`make git-identity`), and a stub `gh` on `PATH` for the network only — asserting
on the args and stdin the real code sent (`tests/test_architecture_bot.py`,
`tests/test_workflows.py::test_fix_bot_push_behaviour`). Prove it bites by
mutating the workflow once and watching the test fail — drop the `Z` from a branch
stamp, add a `Closes #1` to the PR body — then restore it.

## A wrapper that forwards an EMPTY value is a missing setting

A public make target that always passes `VAR="$(VAR)"` exports the variable
**empty** for every call that does not set it, and `int(os.environ.get(name, d))`
treats *unset* as the default but *empty* as the value — `int("")` kills the
process before it reads anything. Both layers need fixing, and neither alone is
enough: the wrapper forwards only when set (`$(if $(VAR),VAR="$(VAR)",)`), and the
reader goes through ONE helper that maps unset **or** blank to the default and
fails LOUDLY (naming the variable) on a non-numeric value. Add a repo-wide guard
that fails on a new bare `int(os.environ…)` / `float(os.environ…)`, so the class
cannot come back in a script nobody re-read.

## Triage a bot the user reports as broken

1. Read the RUN, not the source: `gh run view <id> --json jobs`, then
   `gh run view <id> --log-failed` (or `--log | grep -B5 -A20 Traceback`). The
   failing step's own traceback is the diagnosis; a red scheduled bot nobody reads
   is itself a finding worth filing.
2. Reproduce at EVERY layer the value crosses — the script directly
   (`VAR= python3 scripts/x.py`) **and** through the real target (`make target …`)
   — because the wrapper and the reader can each be wrong, and the first
   reproduction hides the second.
3. Then file an issue, cut a worktree, fix the CLASS (not the call site), prove the
   new guard is RED on the pre-change source (see
   `references/guards-that-actually-bite.md`), and open the PR.
4. Verify in production, not in the PR: dispatch the pipeline after the merge and
   read `jobs[].conclusion`. A bot that has only ever run its no-op path has not
   been verified.

A scheduled bot whose check ALREADY runs on every PR is idle by construction: it
can only ever regenerate an identical file, so "it never does anything" is the
design, not a defect. Say which one the workflow is — an alarm behind CI, or a
scheduled writer with a diff source CI does not check — and give the bot a real
source of drift or say plainly that its green means "nothing drifted that CI
could not see".

## The generated-file merge race

Any generated file that carries a COUNT or an index (`OPENSPEC.md`,
`data/gap_baseline.json`) goes stale when two PRs merge in the same hour: each
regenerates against its own base, and the squash merge lands the older text on
newer content. Master then fails `openspec-index-check` while every PR was green.
Fix = one-line PR from the generator's own output (`make openspec-index`), no
hand edits, body with no closing keyword.
