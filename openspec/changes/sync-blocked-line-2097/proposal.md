# sync-blocked-line-2097

<!-- OpenSpec change for issue #2097 -->

## Why

`make check-pr-sync-line` (issue #1724) demands a `SYNC: <p> make sync-agent-profile PROFILE=<p>` line for every profile a bot PR edits — but when the tree copy is a truncated seed, `make sync-agent-profile PROFILE=<p> CHECK=1` refuses (measured on `llgenie-planner`: 60/115 files differ, 56 would SHRINK the live profile). The lane's only options today are (a) write a `SYNC:` line for a sync that was never run and must not run — a false-green claim — or (b) get stuck red. The gate has no honest input for the blocked case (issue #2097).

## What Changes

- `make check-pr-sync-line` accepts an alternative per-profile line `SYNC-BLOCKED: <p> #<issue> <measured reason>` (reason carries the measured counts/bytes). It is honored only when the block is real: where the live profile home is readable, the gate re-measures the truncation (a differing file whose live copy is larger, the same criterion `agent_profile_sync.check` uses) and reds a claimed-but-not-measurable line as fabrication; where the home does not exist (CI), the line is accepted on format and the gate says so. A body with no line at all for a touched profile stays red, and the exact `SYNC:` line contract is unchanged.
- `make bot-preflight` (the host pre-push seam) becomes the honesty producer: for a touched profile whose tree copy is a truncated seed it prints the paste-ready `SYNC-BLOCKED: <p> #<issue> <measured byte/count reason>` line (ISSUE=<n> names the tracking issue); for a profile that is not truncated it keeps printing the `SYNC:` obligation. A `SYNC-BLOCKED:` line in the prospective body that the host cannot measure is refused pre-push.
- `scripts/agent_profile_sync.py` exposes the quiet measurement both seams share (`truncation_report`), so the gate, the preflight and the sync refuse from one implementation.
- `tests/test_pr_hygiene_sync_line.py` covers the three cases (blocked line passes when measured, no line fails, exact SYNC line passes) plus the fabrication red and the unmeasurable-CI acceptance.

## Impact

- Affected specs: `sync-line-gate` (ADDED: honest blocked-line acceptance; preflight emits the measured blocked line)
- Affected code: `scripts/check_pr_hygiene.py`, `scripts/agent_profile_sync.py`, `scripts/bot_preflight.py`, `mk/bots.mk` (ISSUE= pass-through), `scripts/package-layers.json` (one allowed edge), `tests/test_pr_hygiene_sync_line.py`, `tests/test_bot_preflight.py`
- No live-profile writes, no agents/ edits in this change.
