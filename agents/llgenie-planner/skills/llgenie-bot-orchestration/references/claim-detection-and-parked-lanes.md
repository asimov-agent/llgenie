# Claim detection & parked lanes

Rules for two measurement mistakes that cost real dispatches: reading a live claim as idle, and treating a
lane parked on an owner-only gate as finished.

## A lane claim has TWO shapes — grep both

The claim comment is either the `bot-claim:` prefix OR the status line

```
BOT <lane> · working on #<id> · branch <ref> · since <hh:mmZ> · blocked on <x|none> · next <y>
```

Searching only for `bot-claim:` reports a claimed issue as unclaimed → the lane looks idle and you double-dispatch a
live claim (two lanes on one issue = the race the fleet forbids). Measure with both shapes in one query:

```bash
gh api repos/asimov-agent/llgenie/issues/<n>/comments \
  --jq '[.[]|select(.body|test("bot-claim:|BOT .*working on"))]|last|.body|split("\n")[0]'
```

A claim count of zero from a `bot-claim:`-only grep is NOT evidence of an idle lane; re-measure with both shapes
before you dispatch.

## A claim with no visible branch is not automatically stale

`no branch on origin + no PR` does not mean phantom. Read the claim's own `blocked on` clause first:

- **Owner-only gate named** (push-protection bypass, a credential, an un-merged base only the owner can merge): the
  lane has committed locally and what is unpushed is *preserved*. Releasing the claim or re-dispatching races a
  preserved run and discards the trail. Leave it claimed; do not resend.
- **No gate and the branch simply does not exist**: now it is a phantom claim — release it in a comment, then
  re-dispatch (host implementer / owning lane).

Confirm which case it is before acting: `git branch -r --contains <sha the claim cites>` (empty = not pushed) plus
`gh pr list --state all --head <branch>` (empty = no PR). An empty pair with an owner-gate clause is a parked lane,
not a dead one.

## A lane parked on a real owner-gate is parked, not done

When a claim's `blocked on` names something only the owner can lift, the lane's own status comment often also names a
workaround that needs NO owner — e.g. redesigning a pinned build so the offending content never enters the push,
rather than editing a protected literal that trips push protection. Read the full claim body (not just its first line)
for that alternative and force the lane onto the gate-free slice; only if it names none does the own-domain
continuous-improvement audit become the fallback. "Parked on the gate" excuses only the gated slice, never the
gate-free work sitting next to it.

## The DM is a promise; the on-issue comment is the trail

A `message_agent` dispatch alone leaves the assignment only in a queue — invisible to the owner and the next reader.
After every dispatch, mirror it as one comment on the issue: who took it, the scope, the parked state, the gate-free
slice, and the exact "done" definition. Verify it is the newest comment:

```bash
gh api repos/asimov-agent/llgenie/issues/<n>/comments --jq '.[-1]|{id,first:(.body|split("\n")[0][0:60])}'
```

Diagnostic: when a completion check keeps firing against work you believe is finished, the genuinely-owed mutation is
usually exactly this missing on-issue anchor for a dispatch you sent by DM — post it, verify the id, then the pass is
complete.
