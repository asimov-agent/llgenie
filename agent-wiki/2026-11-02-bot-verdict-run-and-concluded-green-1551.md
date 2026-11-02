# Auto-merge: a bot verdict names the run that proved it, and the head must be verified (#1551)

2026-11-02. The `bot-verdict` marker carried no run id and the merge-on-verdict path required no
concluded green run at the head. Measured at `main@27e2f4fa`:

- `MARKER_RE` captured only `head`, `verdict`, `reviewer`; `bot_verdict post` (and `make bot-verdict`)
  refused no `--run`. This lane's SOUL mandates "a verdict cites the run id at that head", and the
  marker literally could not carry it.
- `auto_merge._merge_review_cleared` guarded only `failing_checks`, which is absence-of-red: it returns
  `None` when the head has **zero check-runs** (`runs == []` → `red == []` → `if not red: return None`)
  and for an unfinished run. The scheduled recheck (`auto-merge.yml` `recheck` job, `if: always()`, no
  `workflow_run.conclusion == 'success'` gate) reached `run()` → `_merge_review_cleared` →
  `gh pr merge --admin` on a verdict marker alone — a PR whose head CI never finished could merge.

## Fix

1. The marker now carries the run: `<!-- bot-verdict: head=<sha> run=<run id> verdict=<approve|changes>
   reviewer=<login> -->`. `make bot-verdict` requires `RUN=<run id>` and `post` refuses a post without
   it; the slot is REQUIRED in `MARKER_RE`, so a legacy no-run marker does not parse as a verdict.
2. `auto_merge.no_concluded_green()` is the ONE shared read both the CI-triggered path and the scheduled
   recheck use: a head is verified only when (a) an `actions/runs?head_sha=` list exists, (b) at least
   one run concluded `success`, and (c) no run is still in progress. It is wired into `run()`,
   `_merge_review_cleared()` and `explain()`, so a verdict on an unverified head defers with the reason —
   `make auto-merge-explain` prints "defers", never "would merge".

## Tests / acceptance

`test_bot_verdict.py` + `test_auto_merge.py`: a marker with no run id is refused and never clears the
block; a head with zero runs defers the verdict (even with nothing red); a mid-flight head and a
concluded-but-not-success head defer; recheck defers on an un-concluded head; explain prints the
deferral reason. Guard-proofed the pre-fix defect path (zero-run head merged), and the verified-head
path still merges. 94 tests pass. Issue: #1551. Closed by the `#1551` PR.
