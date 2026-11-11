# The orchestrator tick: a 13-step procedure, not a paragraph

The tick (`cc5d2bd4083a`, profile `llgenie-planner`) is the mechanism that makes "never stay idle" true.
Lanes are **turn-based** — they act on a dispatch then exit — so if the tick does not fire, nothing works
and the fleet looks lazy when it is in fact never being triggered.

**Schedule: `every 30m`** (owner directive 2026-11-08; it was 10m before, and that setting never delivered
10m — median 21.0 min measured). `every 30m` is the **configured** value; what it actually **delivered**, measured
start-to-start over 34 fires (30m era, executions.db), is a **median 40.0 min** because Hermes re-arms `next_run`
from completion — delivered cycle = interval + run duration (#2340). Do not quote 30 as the cycle time. Read the
schedule from `jobs.json`'s `schedule.display`, never from a
sentence in a document: this file said "every 10 minutes" for a day after the change.

**First thing to check whenever the board looks stuck: is the tick actually firing?**

```bash
hermes cron runs <job-id>        # AUTHORITATIVE: the run ledger, newest first
hermes cron status               # active job count + ticker heartbeat
```

**Never judge liveliness from `jobs.json`.** Its `last_run`, `next_run` and `last_status` can all read
`None`/`ok` while the ledger shows a dozen completed runs — measured on a tick that had fired
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
sed -n '/^## Response/,$p' "$D"                      # and did it ACT on it?
```

Measure the edit's timestamp against the run's start time before claiming a fix took effect: a run started
*before* the edit used the old prompt. Confirm the new rules were **behaved**, not merely carried — a report
that quotes real job ids, leaves a `pending` PR alone, or retracts a stale prior claim is proof; a report
that repeats last pass's conclusions is not.

## The procedure is 13 ordered steps, each with a command

The prompt used to be prose: 13 numbered steps of which **only 2 named a runnable command**, so any step
could be satisfied by *asserting* it happened. Measured 2026-11-08, a pass satisfied every step textually
while dispatching three lanes onto new backlog issues with **12 of 14 open PRs on a stale base** and
**7 lanes idle**. A step that cannot be executed is a step that can be hallucinated.

It is now `STEP 0 … STEP 13`, read top to bottom, **no forward references** (the old "READ 6a FIRST" from
step 3 was precisely why order drifted), and every step names its command plus the line to quote as evidence:

| # | step | command |
|---|---|---|
| 0 | PREFLIGHT FETCH | `git -C "$REPO" fetch origin main` + `git -C "$REPO" rev-list --left-right --count HEAD...origin/main` — the explicit fetch that puts `origin/main` under the pass, ahead of the precedence step |
| 1 | PREFLIGHT | `bash "$TB"` section A — the sha for the whole pass |
| 2 | RECALL | agent tool if the turn has it, else the pinned `curl` on **127.0.0.1:9177** (see below) |
| 3 | MEASURE | `bash "$TB"` — sections A–G, once |
| 4 | RED PRs FIRST | section B; **4d–4g = arm auto-merge** |
| 5 | IDLE LANES | section C; every idle lane gets a red PR |
| 6 | HOW TO DELEGATE | `bash "$DG" --lane … --issue … --brief … --message` |
| 7 | BACKLOG LAST | section D |
| 8 | STALLED | `bash "$SW"` / `--apply` |
| 9 | CI AT TIP | `gh run view <id> --json status,conclusion,headSha` |
| 10 | LANE DRIFT | `make sync-agent-profile PROFILE=… CHECK=1` |
| 11 | DOCS + ARCHITECT | `message_agent` both lanes |
| 12 | FORK ≠ UPSTREAM | `git rev-list --left-right --count` |
| 13 | REPORT | re-run `$TB`, quote its summary lines |

Set these up once, before step 1:

    export REPO="$HOME/repository/git/llgenie"
    export SLUG=asimov-agent/llgenie
    export TB="$HOME/.hermes/profiles/llgenie-planner/bin/tick_board.sh"
    export SW="$HOME/.hermes/profiles/llgenie-planner/bin/stall_reclaim.sh"
    export DG="$HOME/.hermes/profiles/llgenie-planner/bin/delegate.sh"
    export HERMES_BIN="$HOME/.hermes/hermes-agent/.hermes/bin/hermes"

**These live in `bin/`, not `cache/scratch/`.** The scratch directory prunes entries idle for 24 h, so a
canonical script there is one quiet day from silent deletion — and every step that calls it then fails with
no explanation. `bin/` is durable; scratch is for pass records and throwaway worktrees only.

`tick_board.sh` prints fixed sections `A. PREFLIGHT` … `G. LANE DRIFT`. A step either has output there or it
did not run — that is the whole point of the rewrite.

## Arming: four states, and only one gets a `gh pr merge --auto`

Measured 2026-11-08 on 18 open PRs: `armed=9  unarmed=9  armed-but-DIRTY=1`.

- **`armed`** — `autoMergeRequest` present; nothing to do.
- **`unarmed`** — no arm at all.
- **`armed-but-DIRTY`** — the trap. An armed PR that is `DIRTY` can **never** merge: DIRTY gets no CI run
  and the merge queue never sees it. Report it as **inert**, route it to a rebase, never count it handled.
  An expired hold and an impossible arm look identical on the board otherwise.
- **`green+approved+unarmed`** — the only state you arm.

Arm **only** after the last push, then **read it back**:

    gh pr merge <n> --repo "$SLUG" --squash --auto
    gh pr view <n> --repo "$SLUG" --json autoMergeRequest   # the proof

`gh pr merge --auto` **exits 0 and arms nothing** when the base is not the default branch (#964), so the
exit code is not the fact. Never arm a PR with a live run at the head or one that is mid-rebase — the next
push destroys the green the arm waits on (#2069: green+armed at `cc72588c`, rebased, green lost, never
merged).

**`REVIEW_REQUIRED` is not an arming problem.** The author token cannot approve its own PR (#1088);
approval comes from `github-actions[bot]` via `auto-merge.yml`. Arming makes a green PR merge; it cannot
make it approved.

**A systemic red is ONE defect, not N.** If every open PR reds the same check, name it once and route it to
that check's tracker instead of dispatching per-PR fixes that cannot succeed. Measured 2026-11-08: all 17
PRs redded `ci-verdict` because `ci-scope` published no scope decision (`[ci-scope] NO DECISION: this run
published no scope decision — no skip is legitimate`).

## Delegation is one command that proves itself

`delegate.sh` refuses to continue unless every part lands:

1. validates the brief — **rejected** (exit 1) without the `AGENTS:` stamp, the `$HOME` rule, a branch and
   the `BOT <lane> · …` report line, because such a brief produces a PR that reds its own gates;
2. **refuses a second vehicle** — a running/ready task for that lane+issue prints
   `ALREADY DELEGATED: t_xxxx <status>` and creates nothing;
3. creates the task on the owning lane; 4. dispatches; 5. **confirms by reading the board back**.

The confirmation is the only proof, and states exactly one of:

    CONFIRMED t_xxxx running -> <lane>
    CONFIRMED t_xxxx ready (queued on capacity, spawned=0)   <- QUEUED, not running
    CONFIRMED t_xxxx BLOCKED — will not run until unblocked

**`Spawned: 0` is capacity-full, not a lost task.** Conflating those two is how an idle board reads busy.
The script **cannot send the message** — `message_agent` is an agent tool, not a shell command — so it
prints a `TODO (planner, this turn)` line. The task and the message are two channels for one assignment, and
a lane with neither was never delegated to.

## A step must not name a mechanism the runner lacks

A cron turn does **not** carry the agent tool surface. It has no `hindsight_recall` and no `message_agent`
— a real pass says so itself: *"`message_agent` is not in this cron toolset"*. So a step written as
"call tool X" is not merely inconvenient there; it **degrades into whatever substitute the running model
reaches for**, and that substitute brings defaults nobody chose.

That is how a healthy subsystem gets reported as broken. A pass ran the recall CLI, it defaulted to port
**8888**, nothing listened there, and the report said *"the API is down — no prior match, and no retain
possible this pass"* — while the daemon was `active`, listening on **9177**, and `curl /health` answered
`{"status":"healthy","database":"connected"}`. The step was skipped on every pass and each report read
as an honest negative.

**Rules that follow, and they apply to every step:**

1. **Every tool-dependent step carries a shell fallback with the host, port and path pinned.** Never leave
   one to a CLI default — read it from the config that owns it. Here: `HINDSIGHT_API_PORT=9177` in
   `$HOME/.hindsight/profiles/hermes.env`; the only `8888` in that file is **commented out**.
2. **Give the pass a probe that separates "daemon down" from "command wrong".** `curl -s -m 3
   http://127.0.0.1:9177/health` succeeding while a recall fails means the *caller* is wrong, not the service.
3. **Forbid the false negative in the step text** — `report "no prior match" only after the fallback has
   actually answered`. Otherwise "the instrument is absent" is a sentence nothing downstream questions.
4. **Use the lane's own bank id, not a placeholder** — a placeholder 404s and reads as an outage.
5. **Discover paths instead of guessing them:** `curl -s http://127.0.0.1:9177/openapi.json` lists
   `/v1/default/banks/{bank_id}/memories/recall`. A guessed path fails as silently as a guessed port.

The working fallback — with no agent tool present, this still answers and returns the class:

    curl -s -m 8 -X POST http://127.0.0.1:9177/v1/default/banks/llgenie-planner/memories/recall \
      -H 'Content-Type: application/json' -d '{"query":"<failure class>","limit":3}'

Where a step genuinely cannot be done from a shell (`message_agent` is an agent tool, not a binary), say so
and name the durable substitute — the board task plus an on-issue comment — rather than leaving a dead tool
call in the procedure.

## Host-lane precedence

Ask "which host lane owns unblocking this?" **before** touching or re-dispatching any in-repo CI bot. Red CI
is evidence, never a repair target. The ownership map is in `host-lane-precedence-over-ci.md`.

## The pass, in order (the pre-STEP summary, kept for orientation)

0. **Precedence — host lanes first.**
1. **Recall before you classify.** Recall the failure class from the shared bank (agent tool if the turn has
   it, else the pinned 9177 `curl` above). The same handful recur nightly; recognise, don't re-derive.
2. **Measure quiescence.** In-repo workflows' last runs AND each host lane's
   `$HOME/.hermes/profiles/<lane>/state.db` mtime — a lane whose state.db is >30 min stale while work waits
   on it is idle-capable and must be dispatched. Steps 3 and 5 do this with `$TB`.
3. **Read the log, then classify.** Quote the failing step + error line before any dispatch or red/green
   claim. A `conclusion` is a verdict, not a cause.
4. **Never call a PR green while any check is `pending`.** Quote a fresh COMPLETED run at the head and report
   measured counts (N pass / N pending / N fail), never the word "green".
5. **Close only what is proven dead**, citing path:line / commit / run id / PR.

## Failure classes that recur (recognise these, don't re-diagnose)

| red | meaning | owner |
|---|---|---|
| `check-pr-base` "HEAD is NOT cut from origin/main" | stale base — main moved after the branch was cut | `llgenie-pr-merge-conflict` (rebase) |
| `check-pr-acceptance` | linked issue's `## Acceptance criteria` unticked; verdict-gated write-back (#1644) | `llgenie-pr-reviever` |
| `check-pr-agents-line` | PR body lacks the `AGENTS:`/`BASE:` ancestry stamp; bot-fixable metadata, never park the PR | the PR's own lane |
| `check-docs` "changes <file> but adds no agent-wiki note" | behavioural change owes a note + `docs/changes.d` row (#1123) | `llgenie-documentation-maintainer` |
| `check-pr-openspec-change` | non-docs bot PR needs `openspec/changes/<name>/` or an `OPENSPEC:` line (#1807) | `llgenie-ci-pipelines-maintainer` |
| `ci-verdict` red | the judged run failed its scope gate, or lost its `ci-scope-decision` artifact | depends on the judged run's real red |
| `trigger` red, ran ~60m | `engine_build_trigger.py` waited out the full bound on a **404 poll** of a producer that succeeded (#2059) | `llgenie-engine-improver` |
| green + armed + unmerged (`BLOCKED`, `REVIEW_REQUIRED`) | **not** an owner gate — the merge retry path is starved/blind (`cap reached`, `no deferral marker`, cancelled by `cancel-in-progress`, cron under-firing) | `llgenie-ci-pipelines-maintainer` |

Before filing the last row, prove the merge machinery fires at all (a recent `APPROVED` + merged pair) and
measure the sweep's real cron rate and cancellation share — commands in
`auto-merge-approve-and-handle-throttle.md`.

## Measurement traps that have produced false reports

- **A field you did not ask for comes back `null`, silently.** `gh pr list --json` without
  `autoMergeRequest,reviewDecision` printed `armed=0` for all 18 PRs — authoritative-looking and false.
  `gh pr view` and `gh pr list` agree *when asked for the right fields*.
- **`last_heartbeat_at` reads 0 minutes old for a worker idle 2.5 h.** It is a timer, not work.
  `max_runtime_seconds` is only printed into the worker's prompt; nothing enforces it. Use
  `log-mtime age + CPU delta + process age` together (`stalled-worker-detection.md`).
- **A red check-run attached to `main` may describe a PR's head.** Compare `headSha` to the fetched tip
  before reporting a main red.
- **Configured interval ≠ delivered interval.** `every 30m` is the configured value; what it delivers, measured
  start-to-start over 34 fires in the 30m era (2026-11-08 06:25 → 2026-11-09 04:42, executions.db), is a **median
  40.0 min** (min/max 37.0/43.0, 0 of 33 gaps under 35 min), because Hermes re-arms `next_run` from **completion**:
  `_advance_after_run()` sets `next_run_at = finish + interval`, so delivered cycle = interval + run duration
  (median run duration 10.1 min: 30 + 10.1 ≈ 40). Same single cause explains the old 10m setting's 21.0 min
  median (10 + ~11 min run). Root-cause and fix tracked in #2340; the executions.db query is recorded on #2126.
- **A reclaimed kanban task returns to `ready` and is dispatched before newer work.** All tasks sit at
  `prio=0`, so order is arbitrary; raise the priority of what matters with `kanban edit --priority`.
- **Stale-base treadmill.** Every merge re-stales every open PR. Expect rounds, not one fix; a stale base is
  **one board-wide sweep**, not N tasks, and never against a sha quoted in an older task title.
- **Delivery ack ≠ landed.** A `message_agent` ack is a hand-off. Only a branch, PR, label or on-issue
  comment proves it landed. DM to `llgenie-pr-merge-conflict` also hits the 4-message hop cap — use the
  durable on-issue anchor as the channel.
- **A wrapper masks the exit code it was supposed to report.** `make <target>` returns **2** for *any*
  failing recipe, so a checker whose own exit `1` means "found a difference" is indistinguishable from
  "the tool broke". Call the script directly (`python3 scripts/<checker>.py --check`) and read *its*
  code, or a pass will either treat real findings as a broken pipeline or ignore a genuine error.
  Before trusting any exit code, find what the tool documents for it — `0` clean / `1` differs /
  `2` usage error is a common split and `2` is not "differs".
- **A grep over a whole directory inflates by orders of magnitude.** `grep -ro` across a profile counted
  an internal ledger (2,253 hits in one lane) and retired `.archive/` skills as if they were live
  instructions, producing a "thousands of violations" figure that was off by ~30×. Scope the search to the
  files the rule governs (`agents/**/*.md`, or `SOUL.md` + `skills/**/*.md` excluding `.archive/`), and if
  a count looks catastrophic, check what files it came from before publishing it.

- **A metric that was already true before you acted proves nothing about whether you acted.** A report of
  "13 of 13 lane SOULs clean" meant only that those files never contained the string in the first place —
  their mtimes predated the dispatch, no lane had edited anything, and the delivery processes had exited
  non-zero waiting for replies that never came. Asserting the *absence* of text is not measuring a
  behaviour: choose a metric that is **false before** the work and **true after** it, and check its before
  state first. When a delivery's own receipt says "never answered", the honest status is *unconfirmed* —
  never a number that happens to read zero.
- **A scratch/`cache` directory is not storage.** Entries idle for a day are pruned, so a canonical script
  parked there is one quiet day from silent deletion, and every step invoking it then fails with no
  explanation. Keep durable scripts in a stable `bin/`, and have a script resolve its siblings from its own
  location (`"$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"`) so moving it cannot break a cross-reference.

## The tree is the source of record — but establish which side is truncated first

`agents/<profile>/` is the versioned source and a live profile is a copy of it, so the instinct is to
"sync" tree → live. **Check the direction before you write anything.** A comparator run per lane showed
**13 of 13 lanes differing, every one with the tree copy SHORTER than the live profile** — the tree was the
truncated side, accumulated from bots learning in their live profiles and never folding back.

Consequences, and the order that follows from them:

1. **A tree → live sync destroys live behaviour.** The comparator itself says so: *"syncing would REPLACE
   N b of live behaviour … fix the TREE"*. Never run the sync until the fold has landed.
2. **Fold live → tree first** (commit it via an issue+PR), *then* sync, *then* prove `0 of N file(s) differ`.
3. **A file whose live copy is shorter is the opposite case** — the tree is newer there. Keep the tree and
   say which direction you resolved, per file. Do not blanket-apply one direction.
4. **This ordering also gates anything that consumes the tree** — an image that bakes `agents/` in would
   freeze thirteen truncated trees into an artefact that looks authoritative.

## Filing an issue: the six sections have a FIXED ORDER

The issue-body checker enforces section order, not just presence. It fails with
`## Technical must be the LAST section` and `## Not covered must sit between ## Benefit and ## Technical`.
Write them in this order and validate before `gh issue create`:

```
## Problem → ## Why it matters → ## How we fix it → ## Benefit
→ ## Acceptance criteria → ## Not covered → ## Technical
```

`## Not covered` and `## Technical` are the two that get swapped. Validate the draft through the repo's own
checker before posting, and count `- [ ]` boxes in the acceptance section as a separate assertion — a body
can be order-valid and still ship zero testable criteria.

### An issue owes implementation detail, not just a problem statement

The owner asks for issues that a lane can execute on the first read. A body that names files and describes
behaviour still leaves the implementer inventing how to prove the work — and "satisfied by assertion" is the
same defect as a prose procedure. Every issue carries, inside the body:

1. **A `### Implementation detail` table**: *what changes* → *which file* → *the command that proves it*.
   Name real paths (`scripts/<x>.py`, `containers/agent/Dockerfile`, the `Makefile` target), never "the
   code" or "the config".
2. **Runnable blocks**, indented so they read as commands, using the same tools the lane will use
   (`python3`, `make`, `gh`, `git`, `bash`).
3. **A negative control, stated explicitly** — the step that makes the check FAIL. Without it the
   acceptance criterion is untested: *"prove the gate reds before proving it greens"*.
4. **The trap you hit while investigating**, so the implementer does not repeat it. A brief that admits
   "I measured X and it was wrong because Y" prevents the same false reading.

Place it inside `## How we fix it` (or immediately before `## Benefit`) so the enforced section order
survives; a new top-level `##` section will trip the ordering checker.

**A brief for a lane follows the same standard**, plus the `AGENTS:`/`BASE:` stamp, the report line, and the
main sha fetched *in the turn that writes it* — a sha quoted from an earlier message is stale by the time
the lane reads it.

## Related

#2158 (red PRs before the backlog), #2159 (this procedure versioned in the repo), #2182 (arming),
#2155 (stalled workers), #2136 (prompt versioning), #2135/#2090 (lane drift), #2101 (auto-merge delivery),
#1088 (one authoring identity), #964 (arm exits 0 without arming).
