# The orchestrator tick: what it must do every 10 minutes

The tick (`cc5d2bd4083a`, profile `llgenie-planner`) is the mechanism that makes "never stay idle" true.
Lanes are **turn-based** — they act on a dispatch then exit — so if the tick does not fire, nothing works and
the fleet looks lazy when it is in fact never being triggered.

**First thing to check whenever the board looks stuck: is the tick actually firing?**

```bash
hermes cron runs <job-id>        # AUTHORITATIVE: the run ledger, newest first
hermes cron status               # active job count + ticker heartbeat
```

**Never judge liveliness from `jobs.json`.** Its `last_run`, `next_run` and `last_status` can all read
`None`/`ok` while the ledger shows a dozen completed runs — measured on a 10m tick that had fired
`20:12 → 23:32` and was mid-run at the moment `jobs.json` reported `last_run=None, next_run=None`.
A `None` there is a **metadata lie, not a fact**: it is indistinguishable from a job that never fired, so
reporting it as "never ran" is a false stall diagnosis. Read `hermes cron runs <id>`, which lists
`running`/`completed`/`claimed` with real timestamps.

Distinguish the three stall shapes, because the remedy differs:

| ledger shows | meaning | remedy |
|---|---|---|
| runs at a regular cadence, then a multi-hour hole, ticker heartbeat healthy | scheduler skipped slots (overdue `next_run`) | `hermes cron run <id>` recomputes `next_run` into the future; set `--catch-up on` |
| no runs at all, `enabled=False` | job disabled | `hermes cron resume <id>`, then `--catch-up on` |
| runs present but all `skipped` | the job wakes and declines | read the skip reason, not the cadence |

**A prompt edit is proven only by the NEXT run's dump, never by the job record.** `hermes cron edit` writing
the new text back to `jobs.json` proves storage, not execution — an in-flight run keeps the prompt it started
with. Verify with a substring probe against the run's own dump:

```bash
D=$(ls -dt <profile>/cron/output/<job-id>/* | head -1)
grep -oP 'Prompt Characters:\*\* \K[0-9]+' "$D"     # size changed?
grep -cF 'PRECEDENCE — HOST LANES FIRST' "$D"       # the new step is present?
sed -n '/^## Response/,$p' "$D"                      # and did it ACT on it?
```

Measure the edit's timestamp against the run's start time before claiming a fix took effect: a run started
*before* the edit used the old prompt, and reporting it as confirmation is the same rounding error the tick
itself was fixed for. Confirm the new rules were **behaved**, not merely carried — a report that quotes real
job ids, leaves a `pending` PR alone, or retracts a stale prior claim is proof; a report that repeats last
pass's conclusions is not.

The dumps live at `<profile>/cron/output/<job-id>/<YYYY-MM-DD_HH-MM-SS>.md` and each contains the full prompt
plus a `## Response` section — read the Response, not the prompt half.

## The pass, in order

0. **Precedence — host lanes first.** Ask "which host lane owns unblocking this?" and dispatch it *before*
touching or re-dispatching any in-repo CI bot. Red CI is evidence, never a repair target.
1. **Recall before you classify.** `hindsight_recall` the failure class from the shared bank before deciding
what a red means. The same handful of classes recur nightly; recognise, don't re-derive.
2. **Measure quiescence.** In-repo workflows' last runs, AND each host lane's
`/home/asimov/.hermes/profiles/<lane>/state.db` mtime — a lane whose state.db is >30 min stale while work
waits on it is idle-capable and must be dispatched.
3. **Measure the backlog.** Open PRs with `mergeStateStatus`; `agent:implement` issues; branches with no PR;
expired `bot-claim:`s.
4. **Read the log, then classify.** Open the failing job's own log and quote the failing step + error line
before any dispatch or red/green claim. A `conclusion` is a verdict, not a cause.
5. **Never call a PR green while any check is `pending`.** Quote a fresh COMPLETED run at the head and report
measured counts (N pass / N pending / N fail), never the word "green".
6. **Dispatch by ownership** (see `host-lane-precedence-over-ci.md` for the map).
7. **Close only what is proven dead**, citing path:line / commit / run id / PR.

## Failure classes that recur (recognise these, don't re-diagnose)

| red | meaning | owner |
|---|---|---|
| `check-pr-base` "HEAD is NOT cut from origin/main" | stale base — main moved after the branch was cut | `llgenie-pr-merge-conflict` (rebase) |
| `check-pr-acceptance` | linked issue's `## Acceptance criteria` unticked; verdict-gated write-back (#1644) | `llgenie-pr-reviever` |
| `check-docs` "changes <file> but adds no agent-wiki note" | behavioural change owes a note + `docs/changes.d` row (#1123) | `llgenie-ci-pipelines-maintainer` |
| `check-pr-openspec-change` | non-docs bot PR needs `openspec/changes/<name>/` or an `OPENSPEC:` line (#1807) | `llgenie-ci-pipelines-maintainer` |
| `ci-verdict` red | the judged run failed its scope gate, or lost its `ci-scope-decision` artifact | depends on the judged run's real red |
| `trigger` red, ran ~60m | `engine_build_trigger.py` waited out the full bound on a **404 poll** of a producer that succeeded (#2059) | `llgenie-engine-improver` |
| green + armed + unmerged (`BLOCKED`, `REVIEW_REQUIRED`) | **not** an owner gate — the merge retry path is starved/blind (`cap reached`, `no deferral marker`, cancelled by `cancel-in-progress`, cron under-firing) | `llgenie-ci-pipelines-maintainer` |

Before filing the last row, prove the merge machinery fires at all (a recent `APPROVED` + merged pair) and
measure the sweep's real cron rate and cancellation share — the commands are in
`auto-merge-approve-and-handle-throttle.md`. A sweep that runs and correctly refuses red heads is working;
the defect is how often and how many it can see.

## Filing an issue: the six sections have a FIXED ORDER

The issue-body checker enforces section order, not just presence. It fails with
`## Technical must be the LAST section` and `## Not covered must sit between ## Benefit and ## Technical`.
Write them in this order and validate before `gh issue create`, or you pay a re-order round-trip:

```
## Problem → ## Why it matters → ## How we fix it → ## Benefit
→ ## Acceptance criteria → ## Not covered → ## Technical
```

`## Not covered` and `## Technical` are the two that get swapped. Validate the draft through the repo's own
checker before posting, and count `- [ ]` boxes in the acceptance section as a separate assertion — a body
can be order-valid and still ship zero testable criteria.

## Two traps measured on this board

- **Stale-base treadmill.** Every merge moves `main`, re-staling *every* open PR. With the in-repo rebase-bot
  blind to `BLOCKED`-masked staleness (#2071), each round is a host-lane dispatch. Expect rounds, not one fix.
- **Delivery ack ≠ landed.** A `message_agent` ack is a hand-off. Only a branch, PR, label or on-issue comment
  proves it landed. DM to `llgenie-pr-merge-conflict` also hits the 4-message hop cap — use the durable
  on-issue anchor as the channel.
