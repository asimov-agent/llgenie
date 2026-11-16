# Fleet-memory pointer in the lane profiles reference

## Why

Issue #2064: #2057 AC5 requires the fleet-memory section to be linked from the lane profiles
reference the lanes preload (`agents/llgenie-ci-pipelines-maintainer/skills/llgenie-pipeline-maintenance/references/agent-profiles.md`).
The docs PR #2063 could only add the pointer in `docs/BOTS.md` (its AC7 restricted the vehicle to
`docs/`), so the `agents/` side of the requirement never landed. A lane that adds a profile or
recovers after a daemon restart must find the fleet-memory topology in the skill it preloads, not
only in a doc it has to know exists.

## What Changes

- ADDED: the preloaded lane profiles reference links to the `docs/BOTS.md` section
  "Fleet memory: one Hindsight daemon per host, shared plugin profile (issue #2057)". Measured: the
  tree contains exactly one `agent-profiles*.md` reference under `agents/*/skills/*/references/`
  (only the ci-pipelines-maintainer profile carries it), so that single file carries the pointer.
- ADDED: a hermetic test pins the requirement: every `agents/*/skills/*/references/agent-profiles*.md`
  contains the anchor link to the Fleet memory section; planting the removal reds it.
- The live lane profile is re-synced from the tree with `make sync-agent-profile` (issue #1724 rule);
  the PR body carries the `SYNC:` line.

## Impact

- Affected specs: `agent-profiles` (ADDED requirement)
- Affected code: `agents/llgenie-ci-pipelines-maintainer/skills/llgenie-pipeline-maintenance/references/agent-profiles.md`,
  `tests/test_fleet_memory_pointer.py`
- No script, gate, or Makefile behaviour changes.
