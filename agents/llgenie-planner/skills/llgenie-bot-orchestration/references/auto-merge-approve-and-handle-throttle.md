# Auto-merge/auto-approve is ALREADY live — the throttle is a green head, not a human

## The merge path is automatic (measured 2026-11-07)
`auto-merge.yml` is a `workflow_run` sweep that (a) merges with `secrets.BUMP_TOKEN` (owner PAT,
base-repo secret — fork PRs have no secrets, which is exactly why this is NOT a job in ci.yml)
and (b) **approves with `github.token` = `github-actions[bot]`**. Every llgenie PR is opened by
`andyholst` (bots push with the owner PAT), so `github-actions[bot]` =/= author and CAN self-approve
the bot PRs — the rule is `approver != author`, not "human only". An installation token cannot answer
`GET /user` (403), so its identity is the deterministic `github-actions[bot]`, which can never approve
a PR IT opened — that refusal is pinned in `scripts/auto_merge.py::WORKFLOW_BOT`.

## The gate is: head's full CI pipeline GREEN
Everything defers when the head is not green (`conclusion == 'success'` on the triggering CI/`ci-scope`
run). It fires on every green CI completion AND a cron `3,33 * * * *` (odd minutes — even minutes drop
under this repo's queued-alarm; #560). Concurrency is partitioned BY OUTCOME (`-success` / `-failure`),
never merged, so a failing run's sweep cannot cancel a green run's pending sweep.

**`cancel-in-progress: true` is only as safe as the retry it leans on — verify the retry, do not trust the
comment.** The in-file comment justifies the cancellation with "a PR whose sweep is preempted is picked up by
the next sweep, including the scheduled recheck". That sentence is load-bearing and measurably false when the
scheduled sweep under-fires: a GREEN head has no further CI completion coming, so "the next sweep" means
the 30-minute cron — at ~4 runs/day instead of 48, the cancelled sweep's merge waits hours, and a rebase
in the meantime discards the verified green and restarts the whole matrix. An armed PR that is fully green,
sits unmerged, and is then force-pushed to a new head is this failure, not a lane error. Measure the cron's
real rate before repeating "the next sweep catches it" (see the retry-path section below).

## What actually blocks bot PRs (the planner's real job)
A bot PR sits armed+unmerged because its REAL throttle is one of:
1. **A true code/build red** at head — dispatch the owning lane (engine-build = engine-improver).
2. **`check-pr-acceptance`** — the linked issue's `## Acceptance criteria` boxes are unticked (`- [ ]`)
   -> CI itself fails. Write-back is verdict-gated (#1644): a lane/review verdict ticks them. Not a review
   click — a CI job. `## Not covered` + linked work item is the escape.
3. **No `## Acceptance criteria` section at all** in the body -> `check-pr-acceptance-form` fails
   (fix by adding the section, criteria verbatim from the linked issue, boxes left unticked).
4. **`check-pr-closing`** — the PR body closes `#N` but the concatenated squash commit messages close
   nothing (or a different set). Fix is a commit-message amend carrying `closes #N`, then force-push the
   SAME branch — the body alone cannot satisfy it, the squash text is what `git log` keeps.
Once the head pipeline is green, `auto-merge` approves + merges on its own. Do NOT hand-merge or arm
manually — let the sweep do it. The planner's work is to make the head green and move the lane reds, not
to carry an approve token.

End-to-end proof it works unattended: the PR's review flips to `APPROVED` by **`github-actions[bot]`** (a
COMMENTED verdict from the reviewer lane precedes it), then the merge lands via the owner PAT — no human
click anywhere. Read `reviews --jq '.[].user.login + ": " + .state'` to confirm which identity approved.

## The `scope` and `guard` CHECK names each run a CHAIN of gates — read the failing STEP name, not the check name

`guard` and `scope` are umbrella check names; each executes several gates in sequence and dies at the
first failure. The same check name can mean acceptance, acceptance-form, closing, authors, agents-line, or
a scope decision on different PRs — and on the same PR across re-runs. Never diagnose from the check name:

```bash
gh pr checks <n> --repo <o>/<r>
# then, for the failing run, the STEP that actually failed:
gh run view <run-id> --repo <o>/<r> --json jobs \
  --jq '.jobs[]|select(.name=="guard" or .name=="scope")|.steps[]|select(.conclusion=="failure")|.name'
```

The step name carries the gate (`make check-pr-acceptance (…)`, `make check-pr-closing (…)`). Chasing the
wrong gate because the CHECK said `scope` sends you to fix a rebase when the real red is an unticked box.

## Completing the acceptance write-back loop: the gate does NOT re-run itself after a tick

`acceptance_writeback` edits the **ISSUE body**. Issue-body edits trigger no workflow — the PR's existing
`guard`/`scope` check runs still show red and were computed BEFORE the tick. A board that looks unchanged
after a successful write-back is not a failed write-back; it is a stale check run. Finish the loop:

1. Confirm the criteria actually flipped on the issue:
   `gh api repos/<o>/<r>/issues/<n> --jq '.body' | grep -cE '^- \[x\]'` — compare to the box count.
2. Find the failing `guard`/`scope` RUN ids at the PR head (not the check-run ids) and re-run them at the
   SAME head: `gh run rerun <run-id> --repo <o>/<r> --failed`. Safe when the run is completed and the head
   has not moved — verify `headRefOid` first. A body-tick is self-service verification of a gate the
   write-back just satisfied, not a "rerun someone else's work".
3. Only then does the check go green and the armed sweep merge the PR.

If the write-back cannot happen because the reviewer lane's runtime is down (`message_agent` returns
`runtime_unavailable` — "profile authority is not ready"), that is a TARGET-DOWN condition, not a queue
defect: it is safe to resend once the target is up, and the lane's own next turn may land the write-back
anyway. Measure the criteria on the issue before concluding nothing happened.

## A circular acceptance criterion blocks its own fix PR — resolve it with `## Not covered`

A fix-PR for a gate can carry a criterion of the form "the PR that fixes it is green in CI on the same job
that failed". That criterion cannot ever be ticked: the PR's CI reds on `check-pr-acceptance` precisely
because the criterion is unticked. Ticking requires a green PR; green requires a tick. Do not spin on it
and do not hand-tick it — the honest exit is to name the deferred criterion under `## Not covered` in the
PR body with a linked work item, which is what the gate itself accepts.

## A lane's re-stamp or rebase can DROP body sections — re-validate the body gates afterwards

A rebase lane that rebuilds a PR body from a generated summary can silently drop `## Acceptance criteria`
(or accumulate a second, unterminated `AGENTS:` line). So a PR that was body-clean before a rebase reads
`check-pr-acceptance-form` red after it, and the fix belongs to the ORCHESTRATOR (body metadata), not the
rebase lane. After any head move caused by another lane, re-validate both body gates and repair in place:

```bash
gh pr view <n> --json body --jq .body > /tmp/b.md   # insert the section from the linked issue, stamp intact
python3 scripts/check_pr_hygiene.py acceptance-form --head <head> --base <main> --body-file /tmp/b.md
python3 scripts/check_pr_hygiene.py agents-line     --head <head> --base <main> --body-file /tmp/b.md
gh pr edit <n> --body-file /tmp/b.md
```

Copy the criteria VERBATIM from the linked issue and leave the boxes unticked — the tick is the verdict's job.

## Flake-vs-defect probe for a `serve-leg`/readiness failure
`engines/<engine> (make test-published-engine)` that times out on readiness (`FAIL ... not ready after 600s`)
is often slow cold-start, NOT a serving-command/parameter defect (measured #1696: `docker run -d` at
T+0, readiness poll expires at T+600s, `vllm serve` LAUNCH LINE only reaches T+600s+2s — ~10 min consumed
BEFORE the server process starts, on a shared runner). Read the timestamps of the poll-expiry line vs the
serve-launch line before classifying. Rerun the failed engine-build run at the SAME head (a CI
verification, no branch mutation) as the flake-probe: green on rerun = flake confirmed; red again =
real defect -> the owning lane fixes on the same branch via `--force-with-lease --force-if-includes`.

## When the OWNER is merging bot PRs themselves, the board is a live rebase TREADMILL — not a frozen owner-gate

The auto-merge sweep merges bot PRs on green, and the owner also hand-merges some. Each such merge advances
`main`, and **every remaining open PR instantly goes stale-base** (and, when the merged PR touched files a
sibling also edits, `CONFLICTING`). So during an owner-merge burst the board is NOT "waiting on the owner's
approval" — it is a treadmill where the same pass keeps re-staling the set. Report it that way; do not post
"blocked on owner approval" while the tip is moving, or the next reader thinks the board is frozen when the
owners are actively draining it.

Per-pass routine while merges are landing:

1. `git fetch origin main`; read the live tip. If it moved since your last pass, EVERY open PR is a candidate.
2. Re-sweep all open PRs against the new tip — measure each head's containment (`git merge-base --is-ancestor
   origin/main <head>`), not a cached DIRTY flag, and prove any real conflict with `merge-tree --write-tree`.
3. Dispatch ONE batch rebase (all affected PRs, one branch-per-PR, `--force-with-lease --force-if-includes`,
   one message/anchors) to the lane that owns force-pushes — a single merge re-stales the whole set, so this is
   one class, not N defects.
4. **Read `autoMergeRequest` back after the rebase, every time.** An already-armed PR commonly keeps its arm
   through the force-push (measured: armed SQUASH before and after), but PRs that were never armed stay unarmed
   and will NOT merge even when green. Arm the un-armed ones with `gh pr merge <n> --squash --auto` and confirm
   `autoMergeRequest.mergeMethod` is non-null on read-back (exit 0 arms nothing on a non-default base).

A stale-base red is a rebase, never an acceptance verdict and never an owner-approval wait — read
`base == origin/main` (`rev-list --left-right --count`) BEFORE naming the cause, since the same `BLOCKED`
prints for both.

## The in-repo `rebase-bot` will NOT rebase a stale-and-RED PR — `BLOCKED` masks `BEHIND`

Do not dispatch `rebase-bot` to fix a stale-base red and assume it lands. `scripts/rebase_bot_sweep.py`
only acts on a PR whose `mergeStateStatus` is `BEHIND` or `DIRTY`. A PR that is stale **and** red prints
`BLOCKED` with `mergeable: MERGEABLE` — GitHub hides the `BEHIND` behind the failing checks — so the sweep
classifies it as not its work and reports `rebased: 0, failed: 0` (a green run that did nothing).

The bot's own rule hands a "merely-BEHIND PR that is RED" to **fix-bot**, but fix-bot repairs *code*, and
staleness is a branch-lineage problem it cannot fix: it will claim the PR and re-run `success` indefinitely
without moving the head. So a stale+red PR is owned by **neither automation**, and no amount of re-dispatching
either one unsticks it. Verify the deadlock before blaming a lane:

```bash
git merge-base --is-ancestor origin/main <head> || echo STALE      # direction, from ancestry
gh pr view <n> --json mergeStateStatus,mergeable                  # BLOCKED+MERGEABLE = the trap
gh run list --workflow rebase-bot.yml --limit 1                   # confirm 'rebased: 0' in the step summary
```

Prove staleness from `merge-base <head> origin/main` — if that is not the tip itself, the branch is not cut
from main, and `check-pr-base` (inside `linux/unit`) is the red that cascades into `ci-verdict`. The remedy is
a real force-rebase on the owning lane (or the owner's word to rebase branches you were not dispatched for);
dispatching an in-repo bot is not a remedy for this shape.

## "Why is this green PR not merged?" — measure the RETRY PATH before blaming the gate

A green, armed PR that stays unmerged is almost never a gate defect. Before filing anything, prove which of
four things is true, because they look identical on the board (`BLOCKED` / `REVIEW_REQUIRED` / all checks
green / arm timestamp present):

```bash
# 1. Is the merge path even working? Find a PR that DID merge and who approved it.
gh api repos/<o>/<r>/pulls/<merged-n>/reviews --jq '.[]|"\(.submitted_at[:19]) \(.user.login) \(.state)"'
gh api repos/<o>/<r>/pulls/<merged-n> --jq '{merged:.merged,by:.merged_by.login,at:.merged_at}'
#    A recent APPROVED + merged pair proves the machinery fires; stop calling it "owner-gated".

# 2. Does the scheduled safety net fire at its DECLARED rate?
gh api "repos/<o>/<r>/actions/workflows/<wf>.yml/runs?event=schedule&per_page=30" \
  --jq '[.workflow_runs[].created_at[:10]]|group_by(.)|map("\(.[0])=\(length)/day")|.[]'
#    Compare the counts against the cron's slot count ("3,33 * * * *" = 48/day).

# 3. How much of the sweep work is CANCELLED by its own concurrency group?
gh api "repos/<o>/<r>/actions/workflows/<wf>.yml/runs?per_page=100" \
  --jq '[.workflow_runs[].conclusion]|group_by(.)|map("\(.[0]//"null")=\(length)")|.[]'

# 4. Is the sweep's per-run cap smaller than the open-PR set?
gh pr list --repo <o>/<r> --state open --json number --jq 'length'   # vs the sweep's --max-prs
```

Then read the sweep's OWN decision log — it names its skips verbatim:

```bash
gh run view <sweep-run> --repo <o>/<r> --log | grep -E '\[recheck\]'
```

Two skip lines are the smoking gun, and neither means "the gate is broken":

- `cap reached (N PRs this sweep); the rest waits for the next one` — the sweep is **starved**, not wrong.
  With a cap of 5 against 12 open PRs, positions 6–12 are evaluated once every few sweeps; combined with an
  under-firing cron that is roughly once a day at best.
- `no deferral marker for <head> — not a retry` — the sweep is **blind** to any PR that carries no deferral
  marker at all. A cancelled sweep is exactly what leaves such a PR behind, so the two defects compound.

A sweep that runs and *correctly refuses* red/pending heads is working as designed — the defect is **how
often** and **how many** it can see, never the decision. Report that distinction explicitly so the next
reader does not chase a gate that is fine.

**A sweep with no `workflow_dispatch` cannot be recovered by hand.** `gh workflow run <wf>.yml` returns
`HTTP 422: Workflow does not have 'workflow_dispatch' trigger` — so any comment (or runbook) claiming the
sweep is runnable "by hand" is wrong for that workflow. The only self-service retry is re-running the last
completed run object: `gh run rerun <old-run-id>`. Check for the trigger before promising a manual unblock:
`git show origin/main:.github/workflows/<wf>.yml | grep -c workflow_dispatch`.

## An authorised force-push can DESTROY a verified green head — check mergeability before rebasing

Rebasing a head that is fully green, armed, and unmerged throws away a completed 16-job matrix and
re-queues it, so recovering from a missed merge costs MORE CI than the merge would have. Before dispatching
a rebase, confirm the head is not already mergeable-and-waiting: read its check conclusions, not just
`mergeStateStatus` — `BLOCKED` covers both "needs a rebase" and "the merger gave up".

```bash
gh api "repos/<o>/<r>/commits/<head>/check-runs" --jq '[.check_runs[]|select(.conclusion!="success")]|length'
# 0 non-success + an arm timestamp = do NOT rebase it; fix its retry path instead.
```

## `## Not covered` must be ONE line ending in a bare `#<n>`

The `check-pr-acceptance` exemption parser (`_declared_out_of_scope`) matches a **single-line** bullet
against `^-.*\s*#\d+\s*$`. A multi-line bullet, a bolded `**#1234**`, or trailing prose after the number
silently does not match and the gate stays red while the author believes the criterion is named out of scope.
Write exactly `- the deferred thing — #<n>` on one line, nothing after the number.

## The acceptance write-back ticks the ISSUE only — PR-body boxes stay `- [ ]` forever, by design

`acceptance_writeback.py` has no `--pr` path: it mutates the issue body. `check-pr-acceptance-form` only
requires the PR body to *carry* a checklist; it never ticks it, and `check-pr-acceptance` reads the LINKED
ISSUE's boxes (plus a squash-only `(closes #N)`). So a merged PR legitimately shows all body boxes unchecked
while its issue reads all-checked — that is correct behaviour, not a gate hole. Do not "fix" a merged PR's
body to match, and do not report the asymmetry as a defect. If PR-body ticks are genuinely wanted, that is a
new feature, not a repair.

## `main` has NO required status checks — the green gate is advisory, not enforced

`gh api repos/<o>/<r>/branches/main/protection` → `required_status_checks: null` (and the ruleset carries only
`deletion`/`non_fast_forward`). Nothing at the GitHub layer blocks a merge on a red PR; `auto_merge.py`
self-gates by reading `mergeStateStatus` and can `--admin` bypass. So "how did that merge" is answered by
"the merger chose to", never by "the checks allowed it" — when a red-criteria or red-CI merge looks impossible,
check the merger's path rather than re-deriving the gate logic.

## A docs/one-file PR is not the implementation — check the work has its own vehicle

When a PR satisfying an issue is docs-only (a topology write-up, an architecture refresh), do not let it stand
as the fix. Confirm each implementation half has a separately tracked issue, and file the missing one: a
documented topology is not an installer, and a gate that *checks* a config is not the bootstrap that *creates*
it. Before declaring an owner request satisfied, enumerate its parts and name the issue number for each.

## A green bot run is not proof the bot did anything — read what it DECIDED

Every sweep (rebase, fix, auto-merge, registry) can exit `success` having taken zero actions, and its own
step summary says so (`rebased: 0`, `failed: 0`) while the board is unchanged. Before reporting a dispatch
as landed, confirm the EFFECT on the wire — the head sha moved, the label exists, the comment id resolves —
never the exit code. And read the sweep's eligibility rule against the board BEFORE dispatching it: a bot
can be structurally unable to take the work you sent, in which case another run will idle forever and the
fix is a different actor, not a retry.

## Measure the object, not the name someone gave it

A lane reports a head sha, a PR number, a run id, or a "satisfied" verdict — re-read each from the API
before repeating it, and prefer the fact you already measured over the one just claimed. Merged PRs keep
receiving dispatches from lanes that re-measured a now-expired premise; close those on-record
(`<id> is MOOT — merged at <sha>`) instead of leaving an open task on a landed PR, because the next reader
will otherwise spend a whole turn re-deriving it.

## Keep working — do not end a pass by asking permission to continue

This owner's standing expectation is that the planner drives the board to green without checking in. Ending a
turn with "want me to file that / want me to push the lane?" reads as stalling; the answer is essentially
always yes, and asking costs a round-trip. File the issue, post the dispatch, take the next red, and REPORT
what you did. The only legitimate stop is a genuine authority limit — e.g. pushing to a branch you were not
dispatched for, or an admin/ruleset change only the owner can make — and then name that one limit in a
sentence, having already done everything up to it.

The same applies to "waiting": a lane that is mid-run, a check that is pending, or a bot that idled are all
things to REPORT with the measurement, not reasons to end the pass. If nothing can move, say which red is
blocked by which authority and what you did instead.

## This repo's rulesets
Main ruleset id=24862727 has NO required-review rule (only `deletion`/`non_fast_forward`) — the
`REVIEW_REQUIRED` block on PRs comes from repo-level required-review SETTINGS, not the ruleset.
