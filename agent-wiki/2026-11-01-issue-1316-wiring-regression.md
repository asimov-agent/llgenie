# test(wiring): regression for the #1316 folded-tool wiring defect (2026-11-01) — issue #1316

## The defect this regression pins

`scripts/fold-live-profile.py` was merged on main (#1310) free of make-target wiring, so
`make check-wiring` reds on main and on every PR's `scope` gate — *"is wired to nothing: no make
target and no workflow names it"*. The wiring itself was fixed by #1319 (`make tester-fold-live`
target + a host-only record in `tests/fixtures/host-only-wiring.json`). This PR adds the regression
half — the part of #1316's acceptance that makes the fix durable for the NEXT folded lane tool.

## What the regression asserts

`test_a_folded_lane_tool_in_scripts_must_be_wired_or_the_gate_stays_loud` in `tests/test_wiring.py`:

1. **Loud unwired:** a `scripts/*.py` folded lane tool that no make target names must make
   `check-wiring` exit 1 naming the file — `scripts/<tool> is wired to nothing`. The guard may not
   be weakened or skipped;
2. **Wiring resolves it:** naming the tool in a make target is the fix — **and** because a folded
   lane tool hosts a live profile a CI runner does not have, a dated host-only record
   (`target`, `reason`, `decided`) is required, exactly the shape the real fix (#1319) took;
3. **Subset assert, not an exact list:** the resolved wiring set is asserted with
   `{wired} <= g["named_by_target"][target]` — `expected <= set(actual)` — never an exact-list
   equality, so a future legitimate `scripts/*.py` addition does not red a brittle roster.

## Deliberate decoupling

The scratch test tool is named `folded_lane_tool.py`, not the real `fold-live-profile.py`: naming
the real script inside `test_wiring.py` would make `check_wiring._imports()`, which scans this file's
source, treat the REAL script as CI-reachable through the test — which would then flag #1319's
host-only entry as stale. Using a generic name keeps the regression's concern (the wiring mechanism)
decoupled from the real tool's host-only decision.

## Proof at the head

`python3 -m pytest tests/test_wiring.py` in the canonical
`ghcr.io/asimov-agent/llgenie/test:5e0bae123ac9` container: 17 passed, incl. the new regression.
`make check-wiring` green at HEAD.
