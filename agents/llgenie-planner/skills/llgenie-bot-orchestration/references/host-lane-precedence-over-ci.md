# Precedence: host lanes first, CI is only the reporter

**Owner rule (2026-11-08): "your own behaviour for working with your bots should always take precedence on the
host.. the CI is just the CI really."**

## The rule

A pass reaches for the **owning host lane first**. CI workflows are *support* — they report red; they are never
the thing the planner repairs. Red CI output is **evidence**, and the response to evidence is a dispatch to the
lane that owns the action.

## Precedence chain, every pass

1. **Host lane owns it → dispatch it.**
   - rebase / force-push → `llgenie-pr-merge-conflict`
   - product code → `llgenie-issse-implementer`
   - docs (`docs/**`, `agent-wiki/**`, `CHANGES.md`) → `llgenie-documentation-maintainer`
   - scripts / workflows / gates / make targets → `llgenie-ci-pipelines-maintainer`
   - engine pins / serving drift → `llgenie-engine-improver`
   - test evidence → `llgenie-tester`
   - review verdict / acceptance write-back → `llgenie-pr-reviever`
2. **An in-repo CI bot declined or is blind → still step 1.** Dispatch the host lane AND file the CI defect
   as its own issue in the code lane. Two trails, never one repaired in place.
3. **The planner never repairs the CI bot.** A branch, commit or code change from the planner is a defect
   (SOUL: "You do not implement"). Reading a script to *diagnose* is fine; editing/pushing it is not.

## The failure this rule prevents (measured)

Six PRs stale-base at main `88ead5b9`. What happened: dispatched `rebase-bot.yml` (run `42438486613`,
`completed/success`, report said `rebased: 0, failed: 0`), then read `scripts/rebase_bot_sweep.py` locally to
diagnose the classifier, then churned issue-bot labels trying to make the automation fire — **before** finally
dispatching `@llgenie-pr-merge-conflict` (`proc_c25a93c420cc`), which was the correct first and only action.

The planner looked busy for several cycles while **zero PRs moved**. The owner had to correct it explicitly.

## Why CI-repair is the wrong instinct

`rebase-bot`'s sweep passed over all six with one reason — `pass-over: #N is BLOCKED against main`,
`action=none` — because GitHub reports `BLOCKED` (never `BEHIND`) when a check is red. That is a genuine code
defect, but it is **the code lane's** to fix (its own issue), and it does not unblock today's PRs: the host lane
does that regardless of what the classifier thinks.

## Test before ending a pass

Ask: *did I dispatch the host lane that owns this action?* If the answer is "I dispatched a CI bot" or "I
diagnosed a script", the pass is not finished. File the CI defect as an issue if it is real, then dispatch the
host lane in the same pass.

## Measure the lane before calling it stalled

A `queued` dispatch ack is a hand-off, not a receipt — but "not landed yet" is NOT "nothing is happening".
Before reporting a lane idle or the board stuck, measure all three:

1. **`stat -c '%y' /home/asimov/.hermes/profiles/<lane>/state.db`** — a mtime within the last few minutes means
   the lane is taking turns right now. Compare against `date`; do not read a stale mtime as proof of death
   without also checking the clock.
2. **Start bookends on the PRs** — the lane posts a `**Rebase lane — start.**` (or equivalent) comment naming
   the branch, the main sha and `merge-tree rc=0` *before* it pushes. Those comments are the lane saying
   "I am working on this right now". Query them: `gh api repos/<r>/issues/<n>/comments --jq '[.[]|select(.created_at>"<dispatch-time>")]'`.
3. **`ps aux | grep <lane-profile>`** — a live `bot_mode_dm.py --run-delivery … -p <lane>` process means the
   turn is executing.

**A lane that has posted start bookends on some PRs and not others is mid-run, working sequentially — report
progress by PR (#N start bookend seen, #M not yet reached), never "nothing moved".** Head shas only change at
push time, so PR heads alone cannot distinguish "lane is working" from "lane is dead"; they lag the lane's
work by the whole turn. Re-measure heads on a loop (poll every ~40s, break when all are base-current) rather
than declaring a stall after one read.

This is the mirror of the precedence rule: the CI bot is not the thing to repair, and the host lane is not the
thing to eulogise while it works. Both errors come from trusting a single status field over a direct
measurement.

## When EVERY lane looks idle, stop looking at lanes

One quiet lane is a lane problem. **All thirteen quiet at once is a dispatch problem** — lanes are
per-turn processes, so nothing dispatches them unless a scheduler fires. Check `hermes cron status` and
whether your own tick is enabled *before* measuring any lane; the full diagnostic order lives in
`references/fleet-quiet-diagnosis.md`.

## Versioned from the live profile (issue #2084)

description: Use when routing llgenie work to lanes or a bot looks idle.
> Pointers: `references/board-work-cadence.md`, `references/merged-pr-stale-rebase-loop.md`, `references/merged-over-red-gate.md`, `references/actions-run-attempt-reconciliation.md`, `references/verifying-lane-claims.md`+`references/false-green-claim-check.md`+`references/red-signal-triage.md`, `references/board-binding-assignees-field.md`, `references/protected-instruction-write-approval.md` (the gate no dispatch can satisfy; the active profile's own home is EXEMPT — live is writable, the repo tree copy is not; never copy live→tree, the subset check; the 100k skill-writer cap), `references/ci-gate-vs-live-pipeline.md`+`references/ceiling-config-verdict-vs-defect.md`, `references/pr-closing-gate.md`, `references/pr-body-hygiene.md`, `references/pr-head-location-and-base-gates.md`, `references/domain-ownership-dispatch.md`, `references/incident-closure-and-board-mutation.md`, `references/actions-job-log-reading-midrun.md`, `references/second-gate-stale-base-and-stuck-run.md`, `references/pipeline-verify-matrix.md`, `references/settled-run-void-vehicle.md`, `references/byte-identity-verification.md`, `references/auto-merge-approve-and-handle-throttle.md`, `references/orchestrator-tick-contract.md` (tick = fleet's only scheduler: overdue `next_run`, ordered pass, failure-class table, stale-base treadmill, **both disk axes** (`df -i` can be 0 while `df -h` looks empty → every write fails), fork-vs-canonical poll trap, lane skill/SOUL drift audit, prompt-is-unversioned), `references/docs-and-architect-nudge.md` (nudge docs+architect EVERY pass; gaps live between the gates), `references/host-lane-precedence-over-ci.md` (host lanes first; red CI is evidence, never a repair target), `references/lane-gap-audit.md` (silent no-ops, unrunnable output, un-retryable aborts), `references/host-tmp-and-worktree-reclaim.md` (the shared /tmp tmpfs: gate it with `make check-host-space`, the three causes of a 0-inode wedge, and the ONLY safe test for deleting a worktree), `references/one-builder-and-duplicate-proof.md` (one builder per file; prove no duplicate before dispatch), `references/pass-contract-and-sweep.md` (12+12 sweep, triggering is the act of the pass, loop-escape, empty-queue audit, propagation hub), `references/change-note-gate.md`, `references/change-proposal-task-gates.md`, `references/nerve-guard-ghost-loop.md`, `references/measurement-hygiene.md`, `references/never-pushed-lane-audit.md`, `references/concurrent-red-classification.md` (before dispatching a second vehicle, `comm -12` the open PRs' file

## One builder per file
`references/one-builder-and-duplicate-proof.md` — the full rule lives verbatim in the reference.
