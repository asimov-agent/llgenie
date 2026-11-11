# The workflow-guard-consistency gate (adding `workflow_dispatch` enrolls a workflow)

`tests/test_workflow_guards.py` derives its roster from a trigger, not a hand list:

```python
def _dispatchable():
    return [p for p in sorted(WF.glob("*.yml")) if "workflow_dispatch" in _on(_load(p))]
```

So the moment a PR adds a `workflow_dispatch:` trigger to a workflow that did not have one, that
workflow **enters the dispatchable set** and every guard-consistency test now expects it to behave
like every other dispatchable workflow:

- `test_every_dispatchable_workflow_has_the_guard` — it carries a `guard` job
- `test_every_guard_step_is_byte_identical` — the guard step's `run` body is byte-identical to every
  other guard site (count assertion is `len(bodies) == len(_dispatchable()) + 1`, the `+1` being
  `ci.yml`, guarded though not human-dispatched)
- `test_the_guard_actually_gates_the_work` — the guard is a `needs:` dependency of the work jobs
  ("ungated guards" / "a `guard` job nothing needs")
- `test_the_guard_checks_both_actors_and_a_write_level` — same actor + write-level rule
- `test_dispatch_forms.py::test_this_repository_states_what_every_dispatchable_run_does` and
  `test_issue_bot_manual_pick.py::test_the_header_and_the_dispatch_table_state_the_same_contract` —
  the workflow is listed in the dispatch table / issue-bot manual-pick header

## Recognizing it from a red

A `linux / unit` failure whose `--log-failed` names `test_workflow_guards.py`, `test_dispatch_forms.py`,
`test_issue_bot_manual_pick.py`, and prints `AssertionError: <workflow>.yml` / `ungated guards:`, on a PR
whose diff ADDS a `workflow_dispatch` trigger, is THIS class. The other ~N thousand unit tests pass;
the red is the guard roster reacting to a legitimate new dispatchable workflow — not a flaky test and
not an unrelated regression. Do not accept a "check name passed" read in its place: a passing
`guard`/`scope` check beside a red `linux / unit` is exactly this shape, because the suite that fails
is only the unit job.

```bash
H=$(gh pr view <n> -R <o>/<r> --json headRefOid --jq .headRefOid)
RID=$(gh api "repos/<o>/<r>/commits/$H/check-runs?per_page=100" \
  --jq '[.check_runs[]|select(.name=="linux / unit")|.details_url]|.[]' | grep -oE 'runs/[0-9]+' | cut -d/ -f2)
gh run view "$RID" -R <o>/<r> --log-failed 2>&1 | grep -aE 'FAILED tests/|AssertionError: |ungated' | tail -20
```

## The fix goes in the WORKFLOW, not the test

Do NOT weaken, delete, or hand-list-lengthen the test to accommodate the new trigger. Either (a) the
trigger was not actually wanted — remove it, and the workflow leaves the dispatchable set, or (b) the
trigger IS wanted — then the workflow must carry the full dispatchable-workflow guard contract:
byte-identical guard step, a `guard` job the re-judge/work jobs `needs:`, and its entry in the
dispatch table + manual-pick header. The contract applies uniformly; the derived count means no test
edit is needed for a legitimate addition.

**Never widen the roster test to an equality list.** If the test itself ever asserts the exact set of
workflows, that is the roster defect — the guard must stay a subset/derived check
(`expected <= set(actual)`), never `==`, or it reds on the next legitimate workflow and teaches the
next person to edit the test to match.

## Dispatch wording

Route the fix to the lane that authored the workflow change (the PR author), not the rebase lane:
done = the new workflow satisfies every dispatchable-workflow guard contract, and a fresh `linux / unit`
run at the pushed head reports all the guard tests passing (quote the run id). One vehicle, force-push
the same branch, no second PR; no gate weakened.
