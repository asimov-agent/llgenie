# Splitting the bot domain out of the Makefile into mk/bots.mk (issue #2460)

Part of the Makefile decomposition family (issue #800 → engines split #2456 merged as
`mk/engines.mk`, gates split #2457 merged as `mk/gates.mk`, ci #2458 and security #2459 in
flight; this lane is the bots domain; the install domain stays open as #2461; the big-bang
PR #2454 stays closed and superseded).

## What changed

The top `Makefile` (1,539 lines at branch point; 1,445 after the security split #2459 landed; rebased in-lane onto the post-#2643 tip `322225867f`, 1,326 lines) carried the whole bot-leg surface inline.
This lane moves 72 bot-domain target blocks — `bot-preflight` / `bot-stamp-body` /
`bot-sync-main` / `bot-sync-branch` / `bot-verdict` / `bot-verdict-read`, the
`issue-refiner-*` / `issue-dedup-*` / `issue-cleaner-*` families, `issue-bot-dispatch` /
`issue-bot-triage` / `issue-bot-changed` / `issue-bot-verdict` / `issue-bot-gates` /
`issue-bot-gates-check` / `issue-bot-pr-body-check` / `issue-bot-open-pr` /
`issue-bot-image`, the `orchestrator-tick` family + `check-tick-prompt`, `web-coverage` /
`issue-evidence`, `implement-issue` + its internal seam, `run-failure-reactor`,
`queued-alarm` / `check-zero-job-pending` / `bots-restore-health`, the `fix-bot-*` /
`fix-loop*` family, the `auto-merge*` family + `check-merge-on-red` / `alert-merged-red` /
`stacked-merge-detect` / `verify-closure` / `check-holds` / `holds-report`, the
arms family (`arm-auto-merge*`, `check-arms`, `arms-report`), the `rebase-bot-*` family,
the `architecture-bot*` family, the `audit-ticks*` family and `code-review-scan` /
`code-review-file` — out of the top file into a new `mk/bots.mk`, byte-for-byte. The top
`Makefile` (now 1,080 lines on the rebased base `322225867f`) keeps the shared environment (`AGENT_IMAGE`, `HERMES_LOG*`),
`.PHONY`, `version`/`help` and carries `include mk/gates.mk` + `include mk/engines.mk` + `include mk/security.mk` +
`include mk/bots.mk`.

Domain boundary: shared agent-leg plumbing used by every domain (`scrub-log`,
`agent-fetch`, the `agent-image*` family, `agent-shell-keys-check`, `jev-preflight*`,
`provision-agent-profiles`, `sync-agent-profile`, `profile-drift-alarm`,
`lane-preflight`, `verdict-roster`) stays in the top file; the roster has zero overlap
with the ci domain (#2458, 20 targets) and the security domain (#2459, 36 targets),
verified by set difference.

Measured parity at the branch head:

- `make -qp` target list identical before/after (428 filtered callable target names vs the `322225867f` base, `diff` empty).
- `make help` byte-identical before/after.
- `make check-wiring` output byte-identical before/after, rc=0.
- `make check-docs` rc=0 before/after, only its fragment/entry counts advanced by this lane's own row.
- affected unit modules green in the `llgenie/test` container on the split tree; full
  battery green on the final head.

## Key decisions

- Span rule (proven on the engines/ci/security lanes): a block runs from its target header
  through the first blank line, the next target header (`^[A-Za-z0-9_.%-]+:(?:[^=]|$)`) or
  variable assignment — whichever comes first — while tracking `ifeq/else/endif` depth, so
  adjacent non-bot targets never bleed into `mk/bots.mk`.
- Blind Makefile-text readers: the scripts side (`architecture_bot.py`,
  `check_dispatch_forms.py`, `issue_bot_gates.py`) already resolved `include mk/*.mk`
  (merged with #2457); 17 test files that sliced the top Makefile text for moved bot
  targets (`test_agent_legs_quoting`, `test_agent_nerve`, `test_agent_shell_keys`,
  `test_agent_web_reach`, `test_architecture_bot`, `test_auto_merge`, `test_bot_in_place`,
  `test_bot_pr_body`, `test_bot_stamp_body`, `test_bot_sync`, `test_issue_bot_implement_leg`,
  `test_issue_implementer`, `test_issue_refiner`, `test_jev_preflight_tracker`,
  `test_rebase_bot_sweep`, `test_resolve_run_pr`, `test_scrub_log` — 28 failures) are
  routed through `conftest.makefiles_text()` the same way #2458/#2459 fixed theirs.
- Local-battery environment gap: `salvage-four-bucket.py` (rebase-lane audit script) crashes
  with `FileNotFoundError: 'gh'` inside the gh-less test container on this dirty
  multi-worktree host — reproduced on the unsplit `61155e9af` tree, so it is a pre-existing
  defect, not this split's. Filed as its own issue #2638 (it links back to #2460); the
  local battery is unblocked meanwhile by mounting the host `gh` read-only into the test
  container. CI is unaffected (GitHub runners ship `gh`).
- Target identity: recipes, comments and internal (`_`-prefixed) seams move byte-for-byte;
  only the file they live in changes. `mk/bots.mk` (321 lines) keeps a blank line between
  every target block, exactly as the top Makefile separated them — several tests slice a
  recipe up to the next blank line, so packed blocks bleed into the next target and those
  slices read another target's flags.

## Current status

Branch `feat/makefile-split-bots`; issue #2460; the lane ends with a green PR and the
three-mirror (issue body / PR body / commit message) acceptance checklist.
