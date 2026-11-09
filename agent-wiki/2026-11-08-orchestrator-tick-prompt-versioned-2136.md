# The orchestrator tick prompt is a versioned, refreshable repo artifact (issue #2136)

## What changed

Issue #2136 asked to bring the planner tick's prompt into the repo — the fleet's largest single
standing instruction had existed only as a string inside the live `jobs.json`, unreviewable and
undiffable. The structural piece landed with PR #2162 (refs #2159): the versioned copy under
`agents/llgenie-planner/prompts/llgenie-orchestrator-tick.md`, the `make check-tick-prompt` drift
gate (`scripts/check_tick_prompt.py`, host-only, byte-compares the live `jobs.json` prompt against
the committed file naming both byte counts), and the BOTS.md gate note.

This vehicle closes the remaining refresh gap: the live prompt had moved **ahead** of the versioned
copy after the #2159 snapshot. Measured this pass: the committed file at the base sat at 14,046 chars
(`STEP 1 … STEP 13`), while the live `jobs.json` prompt (`cc5d2bd4083a`, every 30m, enabled) had
grown to 16,522 chars / 16,678 bytes (`STEP 1 … STEP 15`). The live prompt gained four pieces the
reviewed copy never saw:

- **STEP 9 — VERIFY LANE RESPONSIBILITY** (`verify_lane_contract.py`, planner owns the regression)
- **STEP 10 — WORKTREE CLEANUP** (owner mandate #2262, `make worktree-prune CONFIRM=1`)
- **engine-domain map inside STEP 5 ownership** (#2270 + two-trails #2073)
- **renumbering STEP 9–13 → STEP 11–15** to make room

At the base the drift gate reds (`LIVE prompt (16522 b) != versioned (14046 b)`); at the head of this
PR it is green (`OK live prompt == versioned (16522 b)`) because the committed file now carries the
real running instruction. Folding live→tree is exactly #2136's own rule — a behaviour artifact must
be versioned when it changes — and the direction proof was that the live side was the richer one.

The one `/home/asimov` literal inside the prompt is the standing rule's own "never /home/<user>"
prose (naming the anti-pattern), unchanged; the rest of the file uses `$HOME`. No added line
introduces a hardcoded path.

## What stays open

The remaining #2136 acceptance work is the `make tick-prompt-install` render-from-file path (item 2
of the issue) — a Makefile/workflow change, out of the doc lane's scope, routed to
ci-pipelines-maintainer. This PR lands the versioned artifact and restores the drift gate's green,
which is the documentation lane's share of #2136.

## Verification

- `make check-tick-prompt` → `OK live prompt == versioned (16522 b)`, rc 0
- `make -s lint check-docs check-wiring check-pr-authors check-issue-bodies check-pr-hygiene` → rc 0
  at the head
- Live prompt re-read from `$HOME/.hermes/profiles/llgenie-planner/cron/jobs.json` in this pass and
  byte-compared to the committed copy
