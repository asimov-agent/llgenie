# Keeping the unit gate hermetic (and why a dump is not a failure)

A `make test-unit` gate runs on every change, on every OS, in CI and on a laptop. Anything
in it that leaves the machine turns a tree-correct branch red (rate limits, DNS, outages)
— or worse, hides a hang.

## A `faulthandler` dump is a warning, not a verdict

`[pytest] faulthandler_timeout = 300` (the pytest built-in, no plugin needed) prints the
stack of every thread and **keeps going**. A test can sit five minutes inside
`subprocess.run(...)` on a network call and the run still ends `N passed`. Symptoms:

- a `Timeout (0:05:00)!` block wedged between progress dots with no test name in the summary;
- the gate's wall time drifting well above its baseline (e.g. 20 min where 11-13 was normal);
- `N passed` with a suspiciously long duration.

Grep the log for `Timeout (` and compare durations; a dump is the only trace you get, so
treat one as a defect even when the exit code is 0.

## Moving a live test out, without losing the coverage

The sanctioned shape (used by repos with a discovery-based suite roster):

1. **Split** a test whose only network step is one assert — the hermetic part stays in the
gate, the live part becomes its own small test (`test_<thing>_links_all_answer`). Do not
delete coverage to make the gate green.
2. **De-select by exact node id** in the roster fixture (`deselect: {path: {test: reason}}`),
never with `-k`: `-k` matches substrings, so a new test whose name contains a deselected
name is silently dropped from the gate.
3. **Give the live checks their own target** (`make test-<area>-live`) that names exactly
those node ids, is `.PHONY`, and is documented in the README (a doc gate usually requires
that). Wiring it into `ci-unit` would make CI need network again — usually not the goal.
4. **Guard the decision** in a test: every deselected node id is still defined in its file
(a rename must move the decision), every reason names its owning target, and the target's
recipe still names exactly those ids. A stale de-selection silently shrinks the gate.

## Do not run two suites at once

Two concurrent `make test-unit` runs fetch the same external pages and the live tests go red
with `HTTP Error 429: Too Many Requests` **while the tree is fine**. Chain branches in one
shell (`run a; run b; run c`) or run them one at a time; when a lone 429 appears, wait and
re-run rather than chasing a phantom regression. The same 429s also mean "stop hammering it"
— a Hub/GitHub limit is self-inflicted by repeated full-suite runs.

## Reading a red gate

Before touching code, classify the failure:

| Symptom | Cause | Action |
|---|---|---|
| `Timeout (` in the log, exit 0 | a test left the machine and stalled | move it to the live target (above) |
| `429` / `5xx` from an external host | network test in the gate, or concurrent runs | re-run sequentially; if repeatable, move it |
| every test green, job red on `openspec`/`docs`/`wiring` | bookkeeping gate | fix the checklist/docs/wiring, not tests |
| `no checks reported`, `mergeable=CONFLICTING` | the PR's head cannot be merge-tested | rebase + force-push; GitHub schedules nothing for a conflicting head |
