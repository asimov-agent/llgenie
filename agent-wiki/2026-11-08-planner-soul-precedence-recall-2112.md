# Planner SOUL: host-lane precedence + recall-before-classify (#2112)

## What changed

`agents/llgenie-planner/SOUL.md` gained the two standing rules it was missing, in its
**"This lane's rules (kept outside the fleet block)"** section. This was a **content** gap, not a drift:
the tree SOUL and the live profile were byte-identical (21,129 b both sides), so `make sync-agent-profile`
would have been a no-op — the tree had never received these two rules at all.

## The two rules added

1. **Host-lane precedence over CI (issue #2073).** Encodes the owner's instruction — *"your own behaviour
   for working with your bots should always take precedence on the host; the CI is just the CI really"*
   (recorded on #2073, comment `6716290537`). The operational test: ask "which host lane owns unblocking
   this?" and answer it before any in-repo CI bot is touched, re-dispatched or diagnosed; a red CI job is
   evidence, never a repair target; the planner does not implement. Carries the per-lane precedence chain
   (rebase → pr-merge-conflict, product code → issue-implementer, docs → documentation-maintainer,
   scripts/workflows/gates → ci-pipelines-maintainer, engine pins → engine-improver, test evidence →
   tester, verdict/write-back → pr-reviever).
2. **Recall before you classify.** `hindsight_recall` the shared bank for the failure class before deciding
   what a red means, and `hindsight_retain` the class→cause→owner mapping for any class that had to be
   diagnosed by hand.

## Lifted, not reinvented

The rule text was lifted from `references/host-lane-precedence.md` in the planner skill (landed with
#2073's skill half, `c3f3b2ac`) and the orchestrator tick prompt (cron `cc5d2bd4083a`, its
`PRECEDENCE — HOST LANES FIRST` and `RECALL BEFORE YOU CLASSIFY` steps), per the issue's instruction.

Note: at the dispatch sha (`648896aa`) that reference did not yet exist in the tree — it was live-only
under the name `host-lane-precedence-over-ci.md`, which is part of #2084's missing-references defect.
Main advanced to `c3f3b2ac` (#2077) mid-flight with the skill half, so this SOUL rule now cites the real
tree path `references/host-lane-precedence.md`.

## Deliberately not added (already present under different wording)

- Log-first ("read the failing job's actual log before any dispatch or green/red/reviewable claim") — **L166**.
- `cancelled` is not a verdict, and `green` is not `mergeable` — **L132**.

Restating either under new wording would teach the next reader to trust neither.

## Placement

Both rules went into the lane-rules section, **not** the `## Standing rules (fleet, learned 2026-10-28)`
block.

The reason is not that a gate would fire today — it would not: `llgenie-planner` is currently in
`agents/fleet-block-exemptions.json` (it has not yet stated fleet rule 15, #1706), so `fleet-block-drift`
tolerates its drift. **Measured**: inserting a test bullet inside the block leaves
`check_agent_profiles.py check --only fleet-block-drift` at rc=0.

The reason is that the block is defined as a **verbatim copy** of the canonical
`agents/standing-rules.md`, and the exemption is a *debt*, not a permanent state. Two lane-specific rules
placed in it would mean the planner can never state the canonical block verbatim, so the exemption could
never be retired — `fleet-exemption-stale` exists precisely to force that retirement. Lane-specific rules
therefore belong beside the block, not in it, which is what the section header already says.
`check_agent_profiles.py check --only fleet-block-drift,fleet-block-source` stays rc=0 either way.


## Third and fourth changes: the live-only rules (#2117, #2144)

Two further gaps were found while rebasing, both **live-only** — the reverse of the tree-missing case
above, and the dangerous direction:

1. **The docs/architect nudge rule (#2117).** Live carried it; the tree did not. Lifted verbatim
   (1,773 chars) into the lane-rules section, so tree and live no longer disagree on it.
2. **Two owner-dated standing-behaviour paragraphs (#2144)** — *"A 'failed main pipeline' or a 'failed PR'
   is only a fact at the sha you just fetched"* and *"When the checkout is dirty, measure at `origin/main`,
   never in the working tree"*. Both dated `owner 2026-11-08`, both carrying the planner's core reading
   discipline, and both present **nowhere** in the repository:

   ```
   grep -rl "is only a fact at the sha you just fetched" agents/ docs/   →  (nothing)
   ```

   Folded verbatim from live into the standing-behaviour prose, **above** the fleet block — same section
   live keeps them in, and not the block, because they are planner-specific.

**Why live-only is the worse direction:** `make sync-agent-profile PROFILE=llgenie-planner` copies tree
over live. While live was ahead, a routine sync would have **deleted** all three rules — the #791
destructive class. The repo was not merely missing text; it was the weaker side.

Verified after folding: both paragraphs are `cmp`-identical to their live copies, both appear exactly once,
and a block-scoped grep confirms **none of the three rules sits inside the fleet block** (all counts 0).

Known and deliberate divergence after this change: the tree is now *richer* than live by design — the tree
carries the two #2112 rules and the restored lane-rules explanatory prose that live lost. A tree→live sync
restores live; a live→tree sync would now destroy the tree. Direction matters.

## Files

- `agents/llgenie-planner/SOUL.md` (+2 rules from #2112, + the #2117 nudge rule, + the two #2144 paragraphs)
- `tests/test_agent_profiles.py` — `test_the_planner_soul_states_host_lane_precedence_and_recall_before_classify`,
  the same content-pin pattern this lane used for #1889 (`test_fleet_rule_19`) and #1891
  (`test_fleet_rule_20`). It reds if either rule disappears and asserts neither pre-existing rule was
  duplicated. AC5 says "verifiable after merge by grep at the merged sha"; a pin makes that true at any
  sha by running one test, which is strictly stronger than a grep.
- `docs/changes.d/2026-11-08-planner-soul-precedence-recall-2112.md`
- `agent-wiki/2026-11-08-planner-soul-precedence-recall-2112.md` (this note)
- `CHANGES.md` (regenerated index)
