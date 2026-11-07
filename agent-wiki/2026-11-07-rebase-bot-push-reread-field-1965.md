# 2026-11-07 — rebase-bot push-time re-read fails 3/3 rc=1: a permanent argument error (issue #1965)

## What was wrong

rebase-bot run 42362455323 @ origin/main 6940f9e7 (the #1953 fix head) picked #1901 and
#1926. Both rebased cleanly — the agent resolved each CHANGES.md union and `git rebase
--continue` succeeded ("Successfully rebased and updated refs/heads/..." 10:08Z and 10:10Z).
Then the push-time dead-vehicle re-read (scripts/rebase_bot.sh:233) failed 3/3 rc=1 for BOTH
PRs. The sweep exited 1 ("rebased=0 failed=2 failed_prs=#1901,#1926"), nothing was pushed, and
both PRs stayed DIRTY.

Attribution (this fix): the command was `gh pr view "$PR" --repo asimov-agent/llgenie --json
state,merged --jq '.state + "/" + (.merged|tostring)'`. `gh pr view` does NOT expose a
`merged` json field — the real fields are `state`, `mergedAt`, `closed`, … — so gh rejects it
with `Unknown JSON field: "merged"` and rc=1 on EVERY call. It reproduces on this host identically
3/3. That is a PERMANENT argument error, indistinguishable from a transient relay drop because the
retry loop discarded stderr with `2>/dev/null` — so the #1952/#1953 bounded retry could not cure
it: 3 attempts, 4s apart, all rc=1, everything discarded.

A second latent bug rode the same read: gh returns `state` UPPERCASE (`OPEN`), and the script
compares `[ "$PR_STATE" != "open" ]` — so even with the field list fixed, an OPEN PR would still
have refused. Both are fixed together.

## What changed

- `scripts/rebase_bot.sh` push-time re-read now issues `gh pr view "$PR" --repo "$REPO" --json
  state,mergedAt --jq '(.state|ascii_downcase) + "/" + ((.mergedAt != null)|tostring)'`.
  `state` is the open/closed/merged vocabulary, lowercased; `mergedAt != null` is the merged
  boolean.
- The retry ring surfaces stderr (`2>"$LIVE_ERR"`) on every failing attempt and in the final
  refusal comment, so a mis-arg / auth / rate-limit / relay fault is NAMED in the run log, never
  masked (issue #1965 acceptance 1).
- `tests/test_rebase_bot_sweep.py`: the actor's fake `gh` now validates the `--json` field list
  exactly like real gh — a request for `merged` gets `Unknown JSON field: "merged"` + rc=1 — so a
  regression back to the dead spelling reddens the suite (I planted the old spelling and it
  refused `test_a_conflict_is_handed...` exactly as the live run did). New
  `test_a_permanent_read_argument_error_is_attributed_and_still_refuses` drives the fake gh with
  both spellings and asserts the dead one is named and the corrected one answers `open/false`.
- The #1733 fail-closed refusal is UNCHANGED: a genuinely merged/closed PR, or a read that still
  fails after retries, still refuses the force-push with the branch untouched.

## Proof

- Live attribution: `gh pr view 1901 --json state,merged` → rc=1 `Unknown JSON field: "merged"`;
  `--json state,mergedAt --jq '(.state|ascii_downcase) + "/" + ((.mergedAt != null)|tostring)'`
  → `open/false` rc=0 on both #1901 and #1926.
- Regression planted: sed-ing rebase_bot.sh back to `--json state,merged` makes
  `test_a_conflict_is_handed_to_the_agent_and_the_result_is_pushed_to_the_fork` fail with
  "could not re-read PR #42 state at push time (rc=1 after 3 attempts); refusing the force-push"
  — the exact live symptom. Restored; 84 rebase tests pass.
- `pytest tests/test_rebase_bot_sweep.py tests/test_rebase_lane_scripts.py`: 84 passed.

## Wire proof (the PRs themselves)

#1901 and #1926 are other vehicles; the rebase lane owns their next sweep. With this fix the
next rebase-bot dispatch that picks them will re-read `open/false`, pass the dead-vehicle guard,
push, and the sweep will report rebased=2 — expected on the next 6-hourly dispatch (29 */6 * * *)
or a manual one after this lands on main. This change removes the only blocker between a
resolved rebase and its push.

References: issue #1965; the #1953 change fixed the transient-fetch/read faults but could not
cure a permanent arg error.
