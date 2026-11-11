# Auditing a bot fleet end-to-end (exercise → fix PR → merge → re-verify)

The full loop for a fleet of GitHub-Action bot dispatchers: exercise each bot one at
a time, create a fix PR where a defect surfaces, wait for each PR to merge, then
re-verify each bot individually on merged `main`. This file carries the lessons that
are NOT in SKILL.md (which is at its size limit).

## A workflow's `Flow:` comment can name a make target that does not exist

Do not trust a bot workflow's documented flow to be real. The
`# Flow: guard -> make <a> -> make <b> -> ...` header comment is narrative, not a
step list, and nothing validates it: `make check-dispatch-forms` checks the header's
presence and cross-checks things like the cron time against reality, but it does NOT
check that each `make <target>` named in the flow resolves to a Makefile target.
Measured across a 13-workflow fleet, one file documented `make agent-image-push-check`
(a target that does not exist — the "is it already on GHCR" decision lives inside the
`publish` recipe, not in a make target) and nothing caught it. The other apparent
misses were `ci-<job>`-style placeholders, which are fine.

- To audit: extract every `make <target>` from a workflow's comments AND `run:` steps
  and diff against the Makefile's defined targets (`^([a-zA-Z0-9_.-]+):`), excluding
  placeholders that contain `<...>` or a trailing `-`. A real-looking name that is
  absent is a doc inaccuracy worth filing.
- If you extend the dispatch-forms guard, add the make-target-existence check to it
  (same class as the cron-time cross-check it already does) and pin it with a
  table-driven test on fixture workflows.

## After a fleet of bot-fix PRs merge, re-verify each bot one at a time on merged main

A bot-fix PR's own green CI is not the final proof — the merge can change behavior
(a later merge touching shared files, a rebase onto a moved main, a bot whose fix
only holds on the exact tree it was tested on). When a batch of bot-fix PRs lands,
re-verify each bot INDIVIDUALLY on the merged tree, in order, never in a batch: run
its deterministic half (`make <bot>-scan`, `make <bot>-pick DRY=1`, `make
<bot>-sweep`, `make <bot>-plan`, `make agent-image-ref`) from a checkout of merged
`main` and confirm it now ACTS (files a finding, picks a PR, produces a matrix)
where it previously crashed or no-opped. A bot that only files issues: re-run its
scan and confirm the bogus finding is gone and only the real ones remain. This is
the "verify each bot at a time" close-out — do not declare the sweep done from the
PRs' green checks alone.

## A run stuck in `queued` with `runner=(none)` on a label = no runner matches (full diagnosis)

When main's CI runs never conclude — every `linux` job `success` but the run stays
`queued` — check the macOS jobs: `gh api /repos/<o>/<r>/actions/runs/<id>/jobs` shows
`status=queued`, `started_at` = dispatch time, `labels=macos-15-intel`, `runner=` empty.
That usually means NO runner matches the label: either a self-hosted runner is offline
or not registered under exactly that label, or hosted macOS minutes/spending limit is
exhausted (macOS jobs queue rather than fail at the limit). It blocks every open PR:
checks stay `pending` and `mergeStateStatus` stays `BLOCKED` even with all Linux jobs
green, and it also blunts a fix-bot whose dispatch keys on a run FAILING (a hung run
never fails).

But the signature is NOT proof of "no runner exists": a PR run can drain macOS runners
to completion while a main `push` run with the same signature sits `queued` untouched.
Before concluding the label matches nothing, compare a `pull_request` run against the
stuck `push` run — if the PR run's macOS jobs ran and passed, capacity exists and the
stuck run is simply not being claimed (label mismatch on that run, or a limit that
applied to the later run). Report the fact set (event, branch, sha, labels, runner,
timings) and do not claim a mechanism you have not proven.

Diagnose the label's source in `ci.yml` (`with: runner: <label>` → `pipeline.yml`), and
do not change the gate unilaterally — scoping macOS to `push` only is a coverage cut
that is the maintainer's call.

## Quick health sweep: read the LATEST run, not the S/F ratio

To answer "do the bots work as supposed to" fast, sweep every workflow with one
`gh run list` each and count green/red:

```bash
for wf in fix-bot rebase-bot queued-alarm code-review-bot issue-refiner \
          engine-bump-rebase registry-sync issue-bot; do
  f=$(ls .github/workflows/ | grep -i "$wf" | head -1)
  gh run list --workflow="$f" --limit 12 \
    --json conclusion,event,createdAt \
    --jq '[.[] | "\(.conclusion)"] | "\(length) runs: \([.[] | select(.=="success")]|length)S/\([.[] | select(.=="failure")]|length)F"'
done
```

The S/F ratio alone is MISLEADING. A bot with 11F and 1S can be either fixed or
still broken — the discriminator is the LATEST run's conclusion and timestamp,
not the count. `engine-bump-rebase` showed 1S/11F but its newest run was a clean
success (the 11 reds were all pre-fix pushes) = FIXED. `registry-sync` showed the
same 1S/11F but its newest run was red = STILL BROKEN. Always pull
`--json conclusion,event,createdAt` and read the newest row before declaring a
bot fixed or broken; a weekly bot (registry-sync) may have no recent run at all,
so say "no run since <date>" rather than guessing from stale history.

## Before implementing an issue fix, check whether a merged PR already fixed it

An open issue is not evidence the work is undone — it stays open until its implementing
PR merges, so a fix can land while you are mid-sweep and the issue still reads open.
Before implementing, check for an already-merged fix with the SAME file set, not just
the same symptom: `gh pr list --repo <o>/<r> --state merged --search '<issue> in:body'`,
then diff the merged PR's files against what you plan to touch. A fix that already
landed makes your branch a duplicate: close the branch and the issue rather than
re-implementing. The duplicate is only visible if you look — the issue's open state
never tells you.
