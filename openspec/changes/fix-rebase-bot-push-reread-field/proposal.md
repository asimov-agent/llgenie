# fix-rebase-bot-push-reread-field

## Why

rebase-bot run 42362455323 @ origin/main 6940f9e7 (the #1953 fix head) picked #1901 and #1926,
the agent resolved both CHANGES.md union conflicts, and `git rebase --continue` succeeded on
both. At push time the dead-vehicle re-read (`gh pr view "$PR" --repo asimov-agent/llgenie --json
state,merged --jq '.state + "/" + (.merged|tostring)'`, scripts/rebase_bot.sh:233) failed 3/3
rc=1 for both PRs, the sweep exited 1 ("rebased=0 failed=2"), nothing was pushed, and both PRs
stayed DIRTY.

The #1952 fix (landed as #1953) bounded-retried that read assuming a TRANSIENT fault, but the
fault is NOT transient in the runner: it reproduces on every call on this host with the same
rc=1. The retry ring burns its 3 attempts and the fail-closed refusal (issue #1733) then reads
as a total failure, discarding the fully-resolved rebase work.

Issue: [#1965](https://github.com/asimov-agent/llgenie/issues/1965).

## What Changes

- Attribute the rc=1: reproduce the exact command with stderr surfaced. The error is
  `Unknown JSON field: "merged"` — `gh pr view` does NOT expose a `merged` field (the real
  fields are `state`, `mergedAt`, `closed`, `mergeCommit`, …). So `--json state,merged` is a
  permanent ARGUMENT error, not a transient relay drop: no retry count can cure it.
- Fix the invocation to the field gh actually exposes: `--json state,mergedAt --jq
  '(.state|ascii_downcase) + "/" + ((.mergedAt != null)|tostring)'`. `state` is the
  open/closed/merged vocabulary and `mergedAt != null` is the merged boolean; `state` comes
  back UPPERCASE from gh (`OPEN`), so it is lowercased or the existing `!= "open"` test below
  reds an open PR too (a second latent bug the same read carried).
- Surface stderr in the retry ring (the old code discarded it with `2>/dev/null`), so a
  mis-arg / auth / rate-limit / relay fault is NAMED in the run log, never masked.
- Make the actor test harness's fake `gh` faithfully validate the `--json` field list (reject
  `merged` exactly like real gh) so a regression back to the dead spelling reddens the suite.
- New test asserts a PR whose re-read mis-args (old spelling) is refused fail-closed and never
  pushed — the exact run 42362455323 symptom.

## Impact

- Affected specs: `rebase-bot-sweep` (modified — the push-time re-read field list and its
  fail-closed attribution).
- Affected code: `scripts/rebase_bot.sh`, `tests/test_rebase_bot_sweep.py`, `agent-wiki/`.

## Not covered

- The two PRs themselves (#1901, #1926) stay under their own run-failure-reactored claims; this
  change cures the sweep so the NEXT run can rebase them.
- #1959 claim-liveness and the #1960 standing-rule prose are separate issues/tasks.
