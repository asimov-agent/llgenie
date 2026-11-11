# GitHub Actions workflow YAML validation (files GitHub refuses)

## The `${{ ... }}` inside a `run:` block-scalar pitfall

A `#` line inside a `run: |` (or `run: >`) block is **script text, not a YAML
comment**. GitHub's expression parser scans the whole scalar, so a `${{ ... }}`
written inside what you believe is a comment is still parsed as a real
expression. A malformed or `...`-laced expression there refuses the ENTIRE
workflow file — the file never compiles, no job ever exists.

`yaml.safe_load` / PyYAML will NOT catch this: PyYAML has no notion of `${{ }}`, so
it parses the file cleanly and every reviewer or gate that only YAML-parses misses
the defect entirely.

Rule: never write literal expression syntax in a `run:` block, even in a
"comment". If prose must show expression syntax, keep it out of any `run:`
scalar (or write it so it is not a parseable `${{ ... }}`).

## Diagnostic: a workflow GitHub refused at startup

A startup failure (file refused before any job existed) has a signature that
distinguishes it from a job that ran and failed:

- run `name` == the **file path** (e.g. `engine-bump-rebase.yml`), not the
  workflow's top-level `name:`;
- `jobs: total_count == 0`;
- `gh run view <id> --log-failed` -> `log not found`.

That combination means the file was rejected at startup; the red run is noise no
job produced. A real failure has jobs, a real name, and a log. A missing
workflow `name:` is what makes a refused run present itself as a file path
instead of its own name.

## `on.workflow_run` REQUIRES a non-empty `workflows:` list

A `workflow_run:` block with no (or an empty) `workflows:` list refuses the whole
file at startup — same signature as the `${{ }}` case: run `name` = the file path,
`jobs: 0`, `log not found`. GitHub's run page gives the exact reason
(`on.workflow_run does not reference any workflows`); it is a real message on the
run, not in `--log-failed` and not reachable from any local parse.

- `yaml.safe_load` AND `actionlint` both pass the broken file: the defect is a
  semantic trigger gap, not an expression or YAML error. A guard that only parses
  expressions/keys (the `make check-workflows` shape) will NOT catch it.
- `workflows:` takes each watched workflow's **`name:`**, not the file path.
- A `workflow_run`-triggered bot MUST exclude its own workflow from the list —
  leaving itself watched makes it re-trigger on its own runs, an infinite loop.
- Guard both directions: every name in `workflows:` resolves to an existing
  sibling workflow `name:`, and the bot's own workflow is absent from the list.
  After pushing a file that adds one, confirm no new 0-job run appears for it.

## A grep for a guard is not proof of one (decision-loudness)

A bot's decision step asks a `make` target which subject to work on
(`…-sweep` / `…-pick` / `…-dispatch`). When that command CRASHES the run must
fail loudly — it must never read the crash as "nothing to do". This class bit
three bots in a row: rebase-bot (#310, `action=${action:-unknown}` -> `go=false`,
never rebased a PR), issue-refiner (#316, same shape, never refined an issue),
and issue-bot (#312, `rc=$?` captured, written to GITHUB_OUTPUT, never read — an
empty `action` made the cap/none test false, so `dispatch=true` and the run
proceeded to triage/implement with no issue picked).

Three ways a guard LOOKS present but is not:

- `set -e` in the wrong place (not on the step that runs the decision);
- a trailing `exit 0` that swallows the rc;
- an rc captured into a variable / GITHUB_OUTPUT and never consulted.

Rule: the guard must RUN the step, not read it. The regression test executes
each decision step's OWN shell with a `make` on `PATH` that exits non-zero and
requires a non-zero exit — the step's script is the product under test, `make`
is the external command stood in for (same as the `gh` tests stand in for `gh`).
Derive the step set from the tree (so a bot added later is covered the moment it
exists), and SUBSTITUTE `${{ … }}` the way the runner does before running the
step's shell — `fix-bot.yml` really does use `REPO="${{ github.repository }}"` in
a `run:` block, and left in place it crashes bash, which makes a loudness test
pass for the WRONG reason. Assert the other direction too: a decision that
answers cleanly leaves the step green.

## Local validation

- `actionlint <file>.yml` is the authoritative local check: it runs the real
expression parse and names the exact line/col + token (e.g. `unexpected token
"." ... [expression]`). Do not trust a YAML-only parse.
- Before fixing, confirm singularity: `git grep -n '\${{ *\.\.\.' -- '*.yml'`
(or your token) proves it is one offender and not a class you must sweep.
- Repo gate (this repo): `make check-workflows` (scripts/check_workflows.py,
stdlib, wired into `ci-unit`) validates EVERY YAML file in the repo: each
`${{ ... }}` must parse, each file ends in a newline, each
`.github/workflows/*.yml` has a top-level `name:`. A workflow-validity gate is
worth having so a file GitHub would refuse fails locally before merge; a
missing `name:` is what makes a refused run present as a file path.
