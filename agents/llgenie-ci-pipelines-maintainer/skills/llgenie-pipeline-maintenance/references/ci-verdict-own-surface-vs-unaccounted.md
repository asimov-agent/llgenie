# ci-verdict: own-surface red vs ci-scope unaccounted — two different layers (#2221)

When a main-tip ci-verdict is red, distinguish the two messages before diagnosing anything:

- **`[ci-scope] NO VERDICT: N job(s) unaccounted for`** comes from `ci_scope.verify`
  (`ci_scope.py:421/431`) and counts a genuinely-failed/skipped/absent row against the judged run's
  OWN decision table. If the judged run really failed a selected ci.yml job (e.g. `linux/unit`), this
  red is CORRECT and must stay — `#2231` deliberately leaves it untouched.
- **`[ci-verdict] UNJUDGED RED: this head carries N check-run(s)`** comes from
  `ci_verdict.py::unjudged_reds` and counts blocking rows whose workflow the verdict does NOT judge
  (roster = `{ci.yml}`). The verdict's own workflow's `judge`/`guard` JOB auto-rows land on the
  default-branch head on EVERY `workflow_run` run (`#1871`), and counting them is a feedback loop:
  once red, every re-judge re-counts it (`measured 42467328605 at b984afae`).

## The fix (in #2231 / `55d0623a`): exclude the own workflow FILE, and only genuine reds

`unjudged_reds` now skips, before the judged-files check:

```python
# ci_verdict.py:241
if Path(found["path"]).name == OUR_WORKFLOW_FILE:   # OUR_WORKFLOW_FILE = "ci-verdict.yml"
    continue
# ci_verdict.py:243
if conclusion not in UNJUDGED_RED_CONCLUSIONS:     # {failure, timed_out, startup_failure}
    continue
```

Line 241 excludes the verdict's own workflow rows by FILE (not by row name — the older code only
skipped the posted `CHECK_NAME` row, so the `judge` JOB auto-rows leaked through). Line 243 drops the
auto-merge cancelled/neutral transient half `#2221` also named. Both halves are required; `#2231`
covers them both. `BLOCKING_CONCLUSIONS` (the merger's #1386 rule) is deliberately unchanged.

## Measuring which rows block a head

```
gh api repos/O/R/commits/<head>/check-runs?per_page=100&filter=latest --jq '.check_runs[] | \
  select(.conclusion=="failure" or .conclusion=="neutral" or .conclusion=="cancelled") | {name, conclusion, details_url}'
```
Resolve each blocking `details_url`'s run to its workflow file (`GET /actions/runs/<run>` → `path`);
a row is "own" if that path basename is `ci-verdict.yml`.

## Post-fix proof pattern

A GREEN main push CI at the merge head (`event=push conclusion=success`, all 10 jobs green) triggers a
fresh `workflow_run` ci-verdict that MUST conclude success even while older own-workflow `judge`
failure rows still sit on the head — `unjudged_reds` returns `[]` because every blocking row is its own.
Measured: `42469085844` `success` at `55d0623a` → check-run `128695522545` title `ci-verdict: green (run 42467969018)`, while 3 own `judge` failure rows (42468060814/42468477567/42468816334) were present.
