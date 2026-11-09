# The #1250 gates: run_attempt supersession + cancelled/neutral merge red (#1422/#1423)

Two lane-owned gate fixes from one queue (Finding A + B), both guard-proofed red-before-green.

## Finding A — a re-run supersedes the attempt it replaced (#1422)
- GitHub keeps the run id AND created_at across a re-run; only run_attempt bumps. Supersession by
  created_at alone read a cancelled attempt-1 as the head's final conclusion while a live attempt-2
  owned the head.
- Consumers that decide supersession/re-run must read run_attempt:
  * `ci_verdict.superseding_run()` — a same-id run with a higher run_attempt wins the same-id case
    before any later-created run.
  * `ci_requeue.plan()` — track max run_attempt per (workflow, branch); requeue only the newest
    attempt, skip a cancelled run whose same id was re-run at a higher attempt.
- Proof shape: run the new test against the PRE-fix logic -> it reds (the guard catches the bug),
  then green after. Do not ship a rule only run on the fixed tree.

## Diagnosing a rout of this shape (reader side) — a red that names a still-`in_progress` run is attempt-supersession, not the gate racing a live run

`ci-verdict` fires on `workflow_run types:[completed]`, so it can never judge a run still in progress. When
a routed red check-run names a run id whose row reads `in_progress` at the verdict minute, do NOT conclude
the gate raced a live run (measured: red check-run posted 20:54:20Z "red (run 41910294154)" while that id's
job row started 20:54:11Z; the run was `run_attempt=2`, started 20:54:02Z, success 21:09:26Z):
- GitHub SHARES the run id across attempts (#1250), so "run X attempt-2 success" and "attempt-1 cancelled"
  are the same id. `cancel-in-progress` on the rerun cancelled attempt-1; ci-verdict fired on THAT completed
  (cancelled) event and posted red — a cancelled attempt has no decision, so red is correct. The later
  attempt-2 success fired ci-verdict again and posted green, superseding the red on the head.
- Verify: read `run_attempt` on the named run, then the head's CURRENT check-run list
  (`commits/<sha>/check-runs`, filter name=="ci-verdict"). A single green row posted after the named run's
  attempt-2 success means the transient red is gone by supersession, NOT a live gate bug.
- Only a head whose CURRENT ci-verdict row still reads failure is a genuine gate question. Never turn a
  same-id misread into a gate change.

## Finding B — a cancelled/neutral check-run is red, not green, at the merge gate (#1423)
- `auto_merge.RED_CONCLUSIONS` originally `{failure,timed_out,startup_failure}` (issue #843 excluded
  cancelled to avoid freezing the board on a docs-only head). Finding B: a CANCELLED run is a CI run
  killed mid-flight, and a `neutral` check-run is what `ci_verdict` posts for a superseded head (never
  `success`) - neither is green and both could walk the merge gate.
- Fix: add `cancelled` and `neutral` to RED_CONCLUSIONS; keep `skipped` non-red (the ONE legit
  docs-only-head "no verdict": a docs PR has no `linux` job). Update every spelling the old policy
  left behind: the module docstring, the RED_CONCLUSIONS comment, and failing_checks() docstring.
- Proof shape: the pre-fix logic MERGED a cancelled/neutral head (grep the old test/log output shows
  "merging PR #482 (green + CLEAN)") — that is the bug re-run; after the fix it defers. Keep a test
  that a genuine `skipped` still merges (#843 path is preserved).

## Own-PR reds to check before any push: doc-file trailing newline + adjacent close

Both reds in the same pass, both easy to ship (2026-11-02, PR #1531/#1532):
- write_file on a `docs/changes.d/<stem>.md` or `agent-wiki/<stem>.md` MAY leave the file WITHOUT a
  trailing newline -> the ci-lint linefeed gate (`scripts/lint_linefeeds.py`) reds the scope job.
  Verify before push: `python3 scripts/lint_linefeeds.py` -> "LINT OK". A fragment row ending the
  file has no newline if the tool dropped it; append `\n`.
- A commit whose body says `Issue: #N` (a claim) but has no adjacent `closes #N` reds the
  check-pr-closing squash-adjacency gate (#1417): the squash text must carry the SAME adjacent close.
  Put `closes #N` (or `fixes|resolves #N`) in the subject/body, not just `Issue:`.
- Fix is an amend + force-with-lease push of the lane's OWN PR head, but only when no run is
  in_progress at that head (never push a PR head under a live run).

## Wire head wins over a routing's quoted sha — the #1712 stale-coordinate playbook

When a correction/routing cites "the current head = <sha>" as proof a data- or gate-fix is incomplete, that
sha is NOT the wire head by authority: message shas are stale by the time they are read (measured 2026-11-04:
a correction cited `4bb3663b9` as the #1720 head, but `gh pr view` reported headRefOid `5e184a4d` and the
branch had been re-cut, HT_admin commits diverging 10:1, then merged as `031b652a`). Before doing ANY
predefined fix:
- Read `headRefOid` from the PR record and fetch THAT exact sha. Re-running the failing fix at a diverged
  lineage is how the corrector's own red is reproduced; the coordinate is the PR record at measurement time.
- Then run the generator's OWN probe at that wire head. If it returns `LIVE_RC=0`, `dead=0`, and
  "matches the generator" (byte-identical), the committed catalog is CORRECT there — do NOT re-run
  `make sync-quant-catalog` because a routing says "still stale". Re-running rewrites committed refs into a
  new diverged head for zero delta, closes nothing, and spends the data-owner's guard budget.
- `ci-hf-live` is main-only (`push: branches:[main]` + schedule + dispatch, never `pull_request`), so a
  manual `make check-quant-catalog LIVE=1` on a PR head is NOT that PR's merge gate — it is the post-merge
  main control. "The gate is red" on a PR head is a manual probe, not the PR's blocking rollup.
- `mss=BLOCKED` with `mergeable=MERGEABLE` and every check SUCCESS except one `in_progress` = a live required
  check still burning (the review-verdict `record` row), not a data red. The merge gate concludes at merge
  time; a MERGED PR whose post-merge main `ci-hf-live` (deterministic: `LIVE_RC=0`, `dead=0`) is green is
  the acceptance, closed with the run id + head sha when the wire run concludes green.

## A coordination split that commands a fix on an already-merged PR is a stale premise — answer, don't execute

A planner/rebase split may route "wait for the base re-cut, then run `make sync-quant-catalog` on the rebased
tip (dead-count 0) and report a LIVE=1 exit-0 run id" even after the PR is already MERGED (measured
2026-11-04: split routed #1720 work on the `ecd151229` rebase while the PR view showed state=MERGED
`031b652a`, mergedAt 22:49:58Z, and #1712 CLOSED 22:49:59Z). Before running ANY commanded fix:
- Read the PR record: `gh pr view <n> --json state,mergedAt,headRefOid` and the issue
  `gh issue view <n> --json state,closedAt`. A MERGED PR + CLOSED issue means the commanded data-drop is an
  already-landed delta; running it rewrites a dated catalog into a fresh head for zero dead-link change.
- A squash-merge folds the fix commit into the merge (a distinct-commit `--is-ancestor` check reads no even
  though the tree carries the change). Prove by CONTENT on the current main tip, not ancestry: run
  `scripts/gen_trending_quant_catalog.py --check` (`== make check-quant-catalog LIVE=1`) in a fresh checkout
  of today's main and read LIVE_RC / dead-count / "matches the generator". `LIVE_RC=0, dead=0` at the merged
  tip's ci-hf-live check-run (name the run id + completed_at) and again at the current main tip is the
  durable green — no new sync owed.
- Reply to the corrector with the merged+green measurement and ask it to re-read its board (the open/closed
  view it split from was stale). Executing a land-date-drop command on a merged PR is the duplicate-vehicle
  error (#824) wearing a coordination coat.


## Owner-escalation routing (#1169 class)

A drift whose writers live in HOST Hermes config (a cron in another lane's profile, or the curator
plugin lifecycle) is NOT repo-PR-able: a PR under `agents/` cannot touch host config and would be a
cosmetic no-op. This lane does not edit another lane's cron (SOUL) or host plugin config (owner's
domain). Measure the two dial locations (the cron job id + its profile path; the plugin-catalog /
`config.yaml` curator surface), post them on the issue, and escalate to the owner with the exact
config dial. Never fabricate a repo-side no-op to look like closure. 
