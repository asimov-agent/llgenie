# #1707: doc-maintainer SOUL synced to fleet rule 15 (#1706)

The #1706 fleet rule ("the lane that opens a PR owns its CI until every required gate is green at the current head sha") was added to canonical `agents/standing-rules.md` by #1707. Because `fleet_block()` reads that canonical and the pinned unit test (`tests/test_agent_profiles.py:test_the_doc_soul_stated_block_matches_the_gate_canonical`) asserts each stated SOUL block equals it verbatim (exemptions are NOT honored by that test), every SOUL that states the fleet block must carry rule 15.

This change synced `agents/llgenie-documentation-maintainer/SOUL.md` to rule 15 — de-duping in-lane per the assertion's own instruction (never re-sourced from live) — and dropped that profile's now-stale entry from `agents/fleet-block-exemptions.json`. The other 12 lanes' SOULs remain legitimately exempt pending their own #1706 sync, each owned by its lane.

Relevant files: `agents/llgenie-documentation-maintainer/SOUL.md`, `agents/fleet-block-exemptions.json`, `agents/standing-rules.md`.
