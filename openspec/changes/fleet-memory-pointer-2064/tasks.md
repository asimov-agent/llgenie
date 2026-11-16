# Tasks — fleet-memory-pointer-2064

## 1. Implement

- [x] Add the Fleet memory link (relative markdown link to the `docs/BOTS.md` anchor) to
      `agents/llgenie-ci-pipelines-maintainer/skills/llgenie-pipeline-maintenance/references/agent-profiles.md`
- [x] Add `tests/test_fleet_memory_pointer.py`: scan every
      `agents/*/skills/*/references/agent-profiles*.md`, assert the Fleet memory anchor link is
      present, and prove the test reddens when the link is removed

## 2. Verify

- [x] `make test-unit` green at the final head; targeted test green before/after sabotage
- [x] `make sync-agent-profile PROFILE=llgenie-ci-pipelines-maintainer` re-syncs the live profile
      (SYNC line recorded in the PR body)

## 3. Ship

- [x] Docs triad: `agent-wiki/` note + `docs/changes.d/` fragment + CHANGES.md row (`make check-docs`,
      `make openspec-tasks-check` green)
- [x] PR opened against upstream main referencing issue #2064; `make lane-preflight` green
