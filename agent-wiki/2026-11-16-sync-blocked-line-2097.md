# SYNC-BLOCKED: the honest input for the sync-line gate (issue #2097, PR #2864)

## What was verified against the spec

- Gate half (`openspec/changes/sync-blocked-line-2097/specs/sync-line-gate/spec.md`): a body
  carrying `SYNC-BLOCKED: <profile> #<issue> <measured reason>` passes only when
  `truncation_report()` re-measures a real shrink; a claim about a profile whose sync would NOT
  shrink is red; a count-free reason is red; a profile with no live home is accepted on format
  and recorded in `UNMEASURED_BLOCKS` with an explicit NOTE. The exact `SYNC:` line and the
  no-line finding are unchanged — the claim path is not loosened.
- Host proof at landing head `7f7927f8` (scratch tree touching `agents/llgenie-planner/SOUL.md`,
  live home `/home/asimov/.hermes/profiles/llgenie-planner`):
  `make bot-preflight ISSUE=2090` printed three paste-ready `SYNC-BLOCKED` lines with measured
  counts (planner 3/965 differ, 1 would SHRINK, first skills/llgenie-bot-orchestration/SKILL.md
  tree 95033 b vs live 102764 b) and kept the plain `SYNC:` guidance for
  `llgenie-ci-pipelines-maintainer`; `make -s check-pr-sync-line` with those pasted lines
  returned 0, and a body claiming a 0-shrink blocked line reds.
- `make sync-agent-profile PROFILE=llgenie-planner CHECK=1` still refuses today (3 of 965
  differ, 1 SHRINK) — the AC1 premise holds at the landing head. The issue body's 2026-11-08
  numbers (60 of 115 differ, 56 SHRINK) measured an older tree state; the tree has since been
  re-copied and the superseding numbers are stated in the issue's Technical section.

## Key decisions

- One measurement, three readers: `truncation_report()` in `scripts/agent_profile_sync.py` is
  the single criterion shared by the sync refusal, `check_pr_hygiene._blocked_line_finding()`,
  and `bot_preflight.sync_blocked_guidance()`; the gate imports the sync module (new
  `check_pr_hygiene -> agent_profile_sync` edge in `scripts/package-layers.json`).
- The blocked line must name an issue and carry measured counts — the gate's honesty check is
  the re-measurement, not the prose; CI checkouts without live homes accept on format loudly.
- Preflight, not the lane author, writes the line: `ISSUE=<n>` makes it paste-ready.

## Current status

PR #2864 open against main (base `44869221b`), OpenSpec change `sync-blocked-line-2097`
validated, tests extended in `tests/test_pr_hygiene_sync_line.py` and
`tests/test_bot_preflight.py`. The content reconciliation (#2084) and fleet drift measurement
(#2090) remain open issues; this change only gives the gate its honest input.
