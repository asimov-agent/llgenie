# Reading CI run state accurately; judge re-runs; filing out-of-scope defects

## Report a run's cell state from its FULL job list, never a partial log

A default engine sweep is not two cells — it is every `engine-build-<engine>-<arch>` row
(20+). Never describe "the two failing cells" from the logs you happened to read. Enumerate the
whole list and name every non-success row with its ACTUAL conclusion:
```
gh run view <run_id> --repo <o>/<r> --json jobs \
  --jq '.jobs[] | [.name, .conclusion] | @tsv' | grep -v success
```
Rules that cost a correction when broken:
- **Call `failure` a FAILURE, never soften it to "cancelled".** A cell killed by the runner
  (`Killed`, exit 143) or a dependency error completes `conclusion=failure`; "cancelled" is a
  distinct conclusion and misreporting it hides a real defect behind an infra excuse.
- **Never omit a failing cell.** If you only opened one cell's step log, you have NOT seen the
  others — a sweep with three reds must be reported as three, each attributed to its own error
  line (buildcache ref not found ≠ `No module named 'poetry'` ≠ a `-h/--help` flag probe).
- Attribute each red to a SPECIFIC error line from that cell's own log, and say whether it is in
  this PR's scope or a separate defect. "X reds, cause Y, tracked at #Z" — never a vague roll-up.

## A judge/`workflow_run` job re-run does NOT pick up a fix merged to main

The `ci-verdict` judge resolves its checkout to the **default-branch head at the workflow_run
event time**, not to whatever is on `main` now. So after you merge a fix to `main` and then
re-run the judge job, it re-checks-out the OLD main (pre-fix) and re-posts the same red — the exit
code and re-run both "succeed" while reproducing the pre-fix verdict. Confirming the fix is
literally present in the merged commit (grep the merged tree) does NOT mean the re-run judge used
it. To get a judge run that sees the fix: push a FRESH head on the PR branch (rebase onto the new
main, or push any new commit) so a new `workflow_run` event fires and the judge checks out a head
that already contains the fix. Repeatedly re-running the stale judge job also corrupts the target
run's attempts (`startup_failure`, absent jobs) — prefer a clean full re-run or a fresh head, and
never claim re-judge fixed the check until you read the NEW check-run's own verdict at the new head.

## File an identified out-of-scope defect IMMEDIATELY, do not "announce-and-forget"

When you discover a failure outside the current PR's scope (a flag defect, a packaging error, a
runner-kill), the follow-up issue must be FILED in the same turn — a reply that says "that's a
separate issue for another lane" without an issue number is a false claim once the turn ends, and
the defect is invisible on the board. File it as a six-section issue (Problem / Acceptance
criteria / Scope / Out of scope / Evidence), quote the measured log lines and run id, and state
explicitly what it is DISTINCT from (e.g. "distinct from the buildcache write-tolerance issue").
Then reference the new issue number in the reconciliation comment on the PR/issue you were on.
