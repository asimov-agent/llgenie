# Batch dispatch: mechanical hygiene vs domain verification

Automation-produced PR batches (engine bumps, dependency bumps, registry sync)
carry TWO separable duties. A dispatch that assigns only one leaves the other
unowned, and the uncovered lane reads as idle on its own domain — the defect is
in the routing, not in the lane.

1. **Mechanical gate hygiene** — body shape (adjacent `closes #N` beside the
   claim), change-note/census row, labels, frontmatter. Content-agnostic; the
   implementer does it and owns the branch push.
2. **Domain verification** — is the bumped pin real and reachable? does the cell
   build? do serving/runtime params match the committed pin? does it match the
   trending source? This belongs to the specialist lane whose profile names that
   domain (engine-improver: trending-engine sync + serving params; security: pin
   validity and vulnerability class; docs: note/AGENTS alignment).

## The failure mode

Dispatch the mechanical half to the implementer, then tell the specialist lane to
"stay clear of the batch" while it works an unrelated ticket. The batch then has
nobody verifying its substance, and the specialist lane looks idle on precisely
the work its profile names. Its reply ("staying clear as routed") confirms the
fence rather than catching it.

## Route from the issue's own claim line before overlaying one

Before stamping a `bot-claim:` on any issue, read the body's own first line and
its comment trail. A continuous-improvement finding filed by a lane from its OWN
idle audit (`bot-claim: <that lane> · filed from own-lane idle audit`) already has
its correct owner: the lane whose sweep the finding is about. Overlaying an
implementer claim on top creates two lanes in one vehicle and hands the finder's
own-domain sweep fix to a lane that cannot do it. This is the same one-owner rule
as the batch split above, violated from the other direction (adding an owner the
body did not name, rather than omitting one it did).

- The filing lane keeps its own-audit findings: it implements them through the
  normal queue (subset-gated, its narrow sweep fix), it does not hand them off.
- A routing correction is a board comment naming the correct owner, the dropped
  owner's new queue, and the reason — then a DM to each affected lane. The
  dropped lane must be told explicitly to remove the item, or it dutifully keeps
  it queued behind its live work.

## Checklist before dispatching a batch

- Write BOTH halves into the dispatch; name the domain half's acceptance criteria
  (pin exists on a reachable index, cell builds, params match the pin).
- Mechanical half -> implementer / vehicle author, explicit "one vehicle, you own
  the push".
- Domain half -> specialist lane as per-PR verification comments, explicit "you do
  not branch, the implementer owns the push" so two lanes never write one branch.
- If the specialist lane is already on a live vehicle, QUEUE the verification
  behind it and say so out loud. "Stay clear" with no queued verification duty is
  the defect; "queued behind #N, verify on completion" is the fix.
- Open one batch tracker issue; each PR carries a comment naming its verifier.
- HARD CHECK before the dispatch comment is posted: the tracker's "owned by"
  line names BOTH halves (implementer for hygiene AND domain lane for
  verification) on the FIRST comment — a later "oh, also the domain lane" DM is
  invisible to the board until someone posts it, and hours of board reads show
  one owner only. If the split was forgotten, the correction belongs on the
  tracker as a board comment in the same breath as the DM (incident
  2026-11-02 #1523: 8 bump PRs carried implementer-only comments for ~1h while
  the engine lane was told "stay clear" — the skill file said two halves, the
  dispatch comment said one).

## "Why is lane X not doing its work?"

Measure before answering: `gh pr view <live-pr> --json state,headRefOid,updatedAt`
plus `gh pr checks <live-pr>`. A lane on its own domain is never idle; a red gate
on its live vehicle usually explains why its queue has not advanced, and that red
may itself be an artifact (wrong-body `check-pr-closing` — see
pr-closing-gate.md). Never accept "it should just be doing that" as an answer from
memory; quote the live head and the check row.
