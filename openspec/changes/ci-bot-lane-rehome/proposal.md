# Proposal: ci-bot-lane-rehome

## Why

Issue #2703, spun out of #2701's `Not covered`. #2701 removed the `schedule:` blocks from eight
bot/trigger lanes, leaving each workflow's `workflow_dispatch:`/`issues:` triggers in the tree but
with no driver. After #2701 merges, a reviewer cannot tell whether triage / dedupe / refinement /
architecture-scan / rebase still happen or where; the workflow files stay implying machinery that
no longer runs. The owner's stated replacement model: the scheduled lane set is the weekly
engine-bump/build + latest-models lane only; everything else is driven by GitHub events or by the
interactive host agent. This change carries that mapping out for the six in-scope lanes (all but
ci-requeue, which is #2702).

## What Changes

- **Six lanes stay, re-homed to documented manual/event dispatch.** `issue-bot`, `issue-dedupe`,
  `issue-refiner`, `architecture-bot`, `registry-sync-review` and `search-smoke` keep their
  workflows with `schedule:` removed; each header gains a line naming who triggers it now (a human
  `workflow_dispatch`, a GitHub `issues: labeled` event, or the interactive host agent). Their
  behaviour (triage, dedupe, body restatement, architecture scan, green-store review, web-reach
  smoke) is real repo machinery and is preserved on manual dispatch.
- **`rebase-bot` is retired.** Its landing function is already covered twice: AGENTS.md says agents
  rebase their own branches, and `engine-bump-rebase.yml` (allow-listed) covers the engine lane.
  So the workflow, `scripts/rebase_bot.sh`, `scripts/rebase_bot_sweep.py`, their `make` targets,
  the `rebase-bot` claim bot name, its roster/exemption entries and tests are removed — no orphaned
  wiring or script. `bot_claims` keeps the `rebase` work kind and the `engine-bump-rebase` bot name
  (still live and posting `rebase` claims). The `.hermes/skills/rebase-conflict/` skill is NOT
  removed: `llgenie-pr-rebase` (a surviving HOST skill) names it as its inner staging half, so it is
  kept and admitted to `check_agent_skills.py`'s `HOST_SKILLS`.
- **Retirement evidence stays on the issue + the PR.** Each lane's keep-vs-retire decision and its
  reason is recorded here and repeated in the PR body.

## Impact

- Affected specs: `ci-bot-lane-rehome` (ADDED requirement: deactivated lanes are dispatch-only or
  retired; retired lanes leave no orphans).
- Affected code: `.github/workflows/{issue-bot,issue-dedupe,issue-refiner,architecture-bot,
  registry-sync-review,search-smoke}.yml` (schedule removed + header), deleted `rebase-bot.yml` and
  the rebase-bot script/make/claim/skill surface, `scripts/bot_claims.py` (rebase-bot name dropped,
  `rebase` work kind kept), `bots/pause.toml`, docs + agent-wiki.
- Out of scope (own issue #2702, linked): retiring `scripts/ci_requeue.py` + `ci-requeue.yml`.
- After merge: a reviewer reads each remaining workflow header and knows exactly who runs it and
  when; nothing remains that implies a live scheduled lane that has none.
