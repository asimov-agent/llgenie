# 2026-10-26 — the issue-bot re-checks the fast gates before it pushes

Issue: [#475](https://github.com/asimov-agent/llgenie/issues/475)
OpenSpec: `openspec/changes/issue-bot-gates`

## What was wrong

The issue-bot decides from the tree (`make issue-bot-changed`, #428) and refuses an empty PR body
(`pr-body.md`, #429), but it published the branch **before** any gate judged the change against the
repository. CI then found the bookkeeping reds. In the run that implemented #407 the six PRs
#443–#448 all carried the change correctly and passed the functional gates; the reds were
`check_openspec_tasks` on an unticked `- [ ]` in `tasks.md`, a stale README target list and a
wiring count — seconds of host-side work each, paid for with a CI round trip and a `fix-bot`
dispatch (up to an hour).

`trending-local-llms` answers this with a repair loop after the PR opens. That is the expensive
shape here and a second implementation of a stage `fix-bot`/`rebase-bot` already own, which AGENTS.md
forbids, so the loop was not imported.

## What changed

`scripts/issue_bot_gates.py` owns the ONE gate roster: `FAST_GATES` (the six the issue names, in
its order) and `DEFERRED` (every other `ci-unit` gate, with the reason it is not re-checked before
the push). `run` executes the fast gates in order through real `make`, prints each as it starts and
stops at the first failure, naming it. `check` reads the real `Makefile` and
`.github/workflows/issue-bot.yml` and fails on an unclassified `ci-unit` gate, a stale or
contradictory classification, a fast gate that is not a `.PHONY` target or that no `ci-*` job
reaches, a target that stopped running the runner, or a gate step that is missing, duplicated,
unconditional on a change, or not strictly between the detection and the push.

`make issue-bot-gates` and `make issue-bot-gates-check` are both `.PHONY` host-side targets and both
run in `ci-unit`. `.github/workflows/issue-bot.yml` runs `make test-image` and then
`make issue-bot-gates` between `Detect what the implementation changed` and
`Commit + push the feature branch`, conditioned on `verdict == 'implement'` and `changed == 'true'`
— a red gate fails the job before the branch is pushed.

The `make test-image` step is not decoration: `lint` is one of the gates and it executes in
`llgenie/test`, the same path `ci-lint` takes, and a fresh runner has no such tag. Measured on this
host while verifying (`docker: Unable to find image 'llgenie/test:latest' locally`), the gate would
otherwise have died on the runtime before checking anything — so `check` now fails a workflow whose
gate step has no earlier `make test-image`/`make test-env`.

## Verified

- `make issue-bot-gates-check` exits 0 on the real tree: "6 fast gate(s) run before the push, 14
  deferred with a reason, wired into the issue-bot between the change detection and the push".
- `tests/test_issue_bot_gates.py` — 9 passed, including "run stops at the first failing gate" over
  real `make`, the mis-ordered workflow, the unclassified-gate lock, the stale `DEFERRED` entry and
  the missing test-image preparation.
- `python3 scripts/lint_linefeeds.py`, `check_workflows.py check`, `check_wiring.py check`,
  `check_docs.py check`, `check_pr_hygiene.py check` and `check_openspec_tasks.py` all exit 0.

No Docker daemon was reachable on this host, so the container-only gates (`test-unit` inside
`llgenie/test:latest`, `make openspec-validate-all`) were not run here; the workflow's own CI runs
them on the PR.

## Follow-up (CI run 40330321787, `linux / openspec` + `macos / openspec`)

`make openspec-validate-all` failed: the requirement *"the gate is wired into the pipeline it
protects"* carried no `#### Scenario:`, and the claim in it — that `ci-unit` calls both
`make issue-bot-gates` and `make issue-bot-gates-check` — was asserted by nothing: dropping either
line from `ci-unit` left every test green while the runner became dead code. `check` now reports a
target `ci-unit` no longer calls, and
`tests/test_issue_bot_gates.py::test_a_runner_ci_unit_stopped_calling_is_a_finding` locks it. Both
are the same defect from the two directions AGENTS.md names: a scenario with no test, and a test with
no scenario.

Verified after the fix (in `llgenie/test:latest`): `make openspec-validate NAME=issue-bot-gates` ->
valid; `make openspec-validate-all` -> 213 passed; `tests/test_issue_bot_gates.py` -> 10 passed.
