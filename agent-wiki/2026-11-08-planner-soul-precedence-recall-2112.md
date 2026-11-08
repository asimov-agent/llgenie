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

The rule text was lifted from `references/host-lane-precedence-over-ci.md` in the planner skill and the
orchestrator tick prompt (cron `cc5d2bd4083a`, its `PRECEDENCE — HOST LANES FIRST` and
`RECALL BEFORE YOU CLASSIFY` steps), per the issue's instruction.

Note: that reference file is **live-only** at this sha — it does not exist under `agents/llgenie-planner/`
in the tree. That is part of #2084's missing-references defect, tracked separately; this PR does not
attempt to fold it.

## Deliberately not added (already present under different wording)

- Log-first ("read the failing job's actual log before any dispatch or green/red/reviewable claim") — **L166**.
- `cancelled` is not a verdict, and `green` is not `mergeable` — **L132**.

Restating either under new wording would teach the next reader to trust neither.

## Placement

Both rules went into the lane-rules section, **not** the `## Standing rules (fleet, learned 2026-10-28)`
block: that block is gate-compared byte-for-byte against the canonical `agents/standing-rules.md`
(`fleet-block-drift`), so a planner-only rule there would red the gate.
`python3 scripts/check_agent_profiles.py check --only fleet-block-drift,fleet-block-source` stays rc=0.

## Files

- `agents/llgenie-planner/SOUL.md` (+2 rules, 21,129 b → 23,200 b)
- `docs/changes.d/2026-11-08-planner-soul-precedence-recall-2112.md`
- `agent-wiki/2026-11-08-planner-soul-precedence-recall-2112.md` (this note)
- `CHANGES.md` (regenerated index)
