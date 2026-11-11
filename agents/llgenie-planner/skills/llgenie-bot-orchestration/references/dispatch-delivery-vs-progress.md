# Dispatch delivery vs. lane progress: a DM state is not a work state

A `message_agent` delivery state (`claimed`, still-running turn, no reply) records only whether the
MESSAGE was consumed — not whether the WORK was done. A dispatch that rides the durable on-issue route
(claim comment → branch → ready-for-review PR → a "green"/finish comment) completes independently of the
DM channel, so the DM frequently still reads `claimed` after the lane has already delivered.

## Before any nudge or re-send, measure the lane's OUTPUT, not its inbox

```bash
# 1. is there a branch / open PR for the dispatched work?
gh pr list --repo <o>/<r> --state open --head <the-branch-or-agent/issue-N> \
  --json number,state,mergeable,mergeStateStatus,headRefOid
# 2. did the lane claim and finish on the issue thread?
gh issue view <issue> --repo <o>/<r> --comments | grep -iE 'BOT .* (implementing|working)|finish|green|ready'
# 3. are there runs at the reported head?
gh api "repos/<o>/<r>/actions/runs?head_sha=<head>" \
  --jq '.workflow_runs[]|"\(.id) \(.status)/\(.conclusion) \(.name[0:30])"'
```

Decision rule:

- **Branch, open PR, or finish comment exists** → the lane already delivered. Re-sending is a DUPLICATE
dispatch: it wakes the lane onto finished work, or races a second branch against the single vehicle.
Do not resend. Report the measured delivery instead (PR number + head sha + the green run/comment id).
- **No claim, no branch, no PR past the expected window** → the lane is genuinely idle on this item;
nudge once, and name what you measured ("no branch, no PR after <T>") so the next reader sees the
evidence the nudge rested on.

## When the owner pushes "nudge it now"

The right answer is proof the work landed, not a blind re-send. Run the three checks above; if delivery
exists, say so with the PR number, head sha and the concrete green evidence (a completed run id or the
finish comment id). Owner impatience is satisfied by a measured delivery, not by repeating the request —
and a duplicate dispatch is the thing that actually wastes the lane's run.

## Corollary: a "still out / not dropped" status is itself a claim about a moment — re-measure it

Before repeating your own earlier "dispatch still out, no pickup" line, re-run step 1/2. A lane can pick
up and ship between your dispatch and your next pass; the staleness is the same class as a lane's stale
report, just on your side of the table.

## Distinguishing a body-stamp red from a code red at a fix PR's head

A head that carries a real code fix but reds `guard` / `ci-verdict` / `scope` while `linux` is `skipped`
is usually NOT the code — read the `guard` job log for `check-pr-agents-line`:
`no AGENTS: <sha> <bytes>b <lines>l line — run make bot-preflight`. That is the missing PR-body stamp
(#792), a body-hygiene gate; the pick/engine logic itself can be green (a green pick-set measured in a
test container is the evidence for the code, the body stamp is a separate remedy). Report the two facts
separately — "fix logic green, body stamp missing" — and route the stamp to the body-hygiene leg, never
as a code defect.
