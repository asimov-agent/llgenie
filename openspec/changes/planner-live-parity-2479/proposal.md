# Proposal: planner-live-parity-2479

## Why

Issue #2479 (the rollout lane of #2174) tracks the residual live↔tree drift of the
`llgenie-planner` agent profile after the #2174 fold. The fold (#2391) landed the
named files, but the merged fleet PRs since then advanced the tree copy while the
live profile stayed on the pre-#2447 versions — the CHECK reports 48 differing
files today, including the 8 tree-only prompt/script updates that never reached
the live profile, and 3 "live-longer" findings whose live-side bytes are the
ORIGINAL vendor text the fold intentionally sanitized (secret-shaped placeholders,
a hardcoded host path replaced by `$HOME`, a truncated console URL).

## What Changes

- Resolve all 48 differing planner-profile files with a recorded per-file decision
  (tree kept, with reason) — no file is synced while its tree copy is the truncated one.
- Re-sync the live profile from the tree once the tree carries the folded content,
  so `make sync-agent-profile PROFILE=llgenie-planner CHECK=1` reports 0 differences.
- Record the per-file resolution table in `agent-wiki/` plus the change trio.
- The two live-longer behaviour findings named by #2479 (`github-issue-triage`,
  `llgenie-bot-orchestration` SKILL.md) are verified byte-identical (folded
  verbatim by merged PR #2391) — evidence recorded.

## Impact

- Affected capability: agent-profile parity for the `llgenie-planner` lane.
- Affected code: none under `agents/` (host-state parity + records).
- Affected host state: `~/.hermes/profiles/llgenie-planner` receives the tree copy.
