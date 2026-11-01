# Idle slack: drive it, don't narrate it

## Never fill a turn with repeated "standing by"

A pass that ends with nothing to act on owes one short line naming the concrete waiters — not a loop of
"standing by" repetitions. Padding is a defect: it hides the fact that no measurement was taken, and the
owner reads it as an idle lane pretending to work. The correct end-of-pass output is: the tip sha, the
in-motion vehicles (id + branch + owner lane), and who specifically is being waited on with *why*
(e.g. "pipeline lane: 3 DM acks queued/pending, no settled reply; board claim posted on #N").

## When the owner asks "who are you waiting for"

Answer with named waiters and the evidence for each (queued-vs-settled delivery state, branch, run id),
then concede any padding you emitted. Then act: an orchestrator that answers the question with prose
and no measurement has not done the job.

## Queued/pending DM acks are not a landed task

Three consecutive `queued` acks for the same dispatch mean the DM channel is not delivering. Do not
resend (that duplicates). Make the assignment durable where the work lives: post the claim on the issue
itself — owner lane, acceptance, one-vehicle, `Closes #N`, never merge/arm — and note in the comment that
the DM deliveries were queued/pending and the board comment supersedes them.

## Slack you can pull without crossing a gate

Draft-to-ready work has two halves, and only one is the owner's:

- **Refinement completion is planner-owned.** Strip a stale `Draft:` title prefix once the body is
  genuinely issue-ready (six sections in `scripts/issue_body.py` SECTIONS order, tickable
  `## Acceptance criteria`). The prefix is board state — the planner's — and it misrepresents refined
  work as unrefined.
- **Promotion is not.** Leave `parked`/`initiative` labels in place; adding `ready-to-go` is the owner's
  call. Verify labels after a rename to prove you did not promote.

Other gate-free planner moves on a quiet pass: re-verify refined bodies never regressed (count matching
`## ` section headers), check the open board for actionable `agent:implement` issues matching an
idle-capable lane, and measure `gh run list` per bot workflow against its cron before concluding a lane
is quiet.
