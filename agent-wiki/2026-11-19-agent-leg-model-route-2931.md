# Agent-leg model route: every bot leg reports which chain model served it (issue #2931, PR #TBD)

## What was verified against the spec (`openspec/changes/agent-leg-model-route/`)

- **The report script exists and is loud.** `scripts/hermes_model_route.py` reads the lane's Hermes
  session store and prints exactly one `model-route: <model-id>` line for the newest session that
  started inside the leg's `--since` window (with a 5s launch tolerance). Store resolution is
  profile-home-first, exactly the smoke's `state_db` rule (issue #2929 measurement: a
  `hermes -p <lane>` run writes to `$HERMES_HOME/profiles/<lane>/state.db`); a lane with no profile
  home falls back to the global store. All three evidence failures exit non-zero and name the reason
  on stderr with no line invented: absent/unreadable store (exit 2), no session in the window
  (exit 3), session carries no model value (exit 4). Stdlib-only; reads only the `model` column —
  never `model_config`, never an env var value, nothing secret on the line.
- **All nine Hermes leg recipes are wired.** `mk/bots.mk` ×6, `mk/agents.mk` ×1, `mk/engines.mk` ×2:
  each captures `leg_start=$$(date +%s)`, runs `hermes` first, then
  `python3 scripts/hermes_model_route.py --lane <same lane as -p> --since $leg_start`, then
  `exit $rc` — the leg's status is Hermes' status, never the report's (proven by a shell-shape test:
  a failed leg stays 1 even when the report itself fails, a green leg stays 0).
- **The standing smoke proof names the model too.** `scripts/hermes_smoke.py` prints the same
  `model-route:` line for the session its own run creates (verdict semantics unchanged); a passing
  session with no recorded model gets a named stderr note, never a fabricated route (two new
  stub-backed tests green: named model reaches stdout, model-less session passes with a note).
- **Registration measured.** `hermes_model_route` added to package-layers "Bots and automation"
  (`check-package-layers` green); the script is proven in the unit battery via
  `tests/test_hermes_model_route.py` (11 tests: profile-first, global fallback, window filter,
  launch tolerance, all three failures, exact line shape, no-config-text line, exit-preservation,
  and a wiring test pinning all 9 recipes) — so no host-only-wiring entry is owed.
  One test finder follows the new leg shape: `tests/test_agent_web_reach.py` identified the fetch
  leg by the line STARTING with `hermes -z`; it now matches the call by content
  (`"hermes -z" in line and "-s agent-fetch" in line`), since recipes open with the epoch capture.
- **Targeted battery green**: `tests/test_hermes_model_route.py` + `test_hermes_smoke.py` +
  `test_agent_skills.py` + `test_agents_unattended.py` + `test_issue_implementer.py` +
  `test_rebase_bot_sweep.py` + `test_scrub_log.py` + `test_agent_model_pin.py` +
  `test_package_layers.py` → 236 passed, rc=0.

## Key decisions

- The report never changes a leg's exit code: the recipes carry `rc=$?` right after hermes and
  `exit $rc` last. Reporting is evidence, not a new verdict.
- The window filter (`started_at >= since - 5s tolerance`) prevents attributing a previous leg's
  session to this one; the tolerance absorbs Hermes' heartbeat between recipe start and session
  stamp. Both bounds are pinned by tests.

## Current status

Implementation + tests green locally; gates and the live `make hermes-smoke` proof run at the final
head; the PR lands through the normal CI lane (issue #2931).
