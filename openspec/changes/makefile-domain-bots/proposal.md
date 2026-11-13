# Change: Split the bot-domain targets out of the top Makefile into mk/bots.mk

## Why

Issue #2460 (decomposed from #800): the top Makefile still piles the bot-leg surface —
issue-bot, fix-bot, rebase-bot, auto-merge/arms, architecture-bot, code-review,
run-failure-reactor, issue refiner/dedup/cleaner, orchestrator tick, acceptance-tick
audit, and the queue/merge alarms — onto every other domain. Each of those legs is
independently owned and independently red, yet any recipe fix drags the whole monolith
through review. This change moves exactly that surface into `mk/bots.mk`, following the
proven single-domain pattern of `mk/engines.mk` (#2456), `mk/gates.mk` (#2457),
`mk/ci.mk` (#2458) and `mk/security.mk` (#2459).

## What Changes

- **Moved (72 targets, recipes byte-identical):** `bot-preflight`, `bot-stamp-body`,
  `bot-sync-main`, `bot-sync-branch`, `bot-verdict`, `bot-verdict-read`,
  `check-tick-prompt`, `issue-refiner-pick`, `issue-refiner`, `_issue-refiner`,
  `issue-refiner-apply`, `issue-dedup-pick`, `issue-dedup`, `_issue-dedup`,
  `issue-dedup-apply`, `issue-bot-dispatch`, `orchestrator-tick`,
  `orchestrator-tick-pending`, `orchestrator-tick-report`, `issue-bot-image`,
  `issue-bot-triage`, `_issue-bot-triage`, `issue-bot-changed`, `issue-bot-verdict`,
  `issue-bot-gates`, `issue-bot-gates-check`, `issue-bot-pr-body-check`,
  `issue-bot-open-pr`, `web-coverage`, `issue-evidence`, `implement-issue`,
  `_implement-issue`, `run-failure-reactor`, `issue-cleaner-scan`,
  `issue-cleaner-apply`, `queued-alarm`, `check-zero-job-pending`,
  `bots-restore-health`, `fix-loop-image`, `fix-bot-sweep`, `fix-bot-report`,
  `fix-loop`, `fix-bot-resolve`, `auto-merge`, `auto-merge-resolve`,
  `auto-merge-channel`, `auto-merge-recheck`, `auto-merge-explain`,
  `check-merge-on-red`, `alert-merged-red`, `stacked-merge-detect`, `verify-closure`,
  `check-holds`, `holds-report`, `arm-auto-merge`, `arm-auto-merge-report`,
  `check-arms`, `arms-report`, `rebase-bot-sweep`, `rebase-bot-agent`,
  `rebase-bot-abort`, `rebase-bot`, `architecture-bot-brief`, `architecture-bot-doc`,
  `_architecture-bot-doc`, `architecture-bot-publish`, `architecture-bot`,
  `audit-ticks`, `audit-ticks-notes`, `audit-ticks-post`, `code-review-scan`,
  `code-review-file`.
- **Added:** `mk/bots.mk` holding those blocks, and one `include mk/bots.mk` line in
  the top Makefile beside the existing includes.
- **Unchanged:** target names, recipes, variables (shared variables like `AGENT_IMAGE`,
  `HERMES_LOG*` stay in the top Makefile), `version`, `help`, `.PHONY`,
  `DEFAULT_GOAL`; every CI/workflow caller keeps calling the identical target names.
- **Re-pointed Makefile-text readers:** any test or guard that slices the top Makefile
  text for a moved target resolves the include chain first (the
  `conftest.makefiles_text()` / `_makefile_list()` pattern from #2458/#2459).
- **Not moved:** shared agent-leg plumbing that every domain uses (`scrub-log`,
  `agent-fetch`, `agent-image*`, `agent-shell-keys-check`, `jev-preflight*`,
  `provision-agent-profiles`, `sync-agent-profile`, `profile-drift-alarm`,
  `lane-preflight`, `verdict-roster`) and the host-install surface (issue #2461's
  lane). No overlap with the ci-domain roster (#2458) or the security-domain roster
  (#2459) — verified by set difference.

## Impact

- Affected specs: `makefile-domain-bots` (new capability delta)
- Affected code: `Makefile`, `mk/bots.mk`, Makefile-text-reading tests
- Parity gate: `make -qp` target set, `make help`, `make check-wiring`,
  `make check-docs` all byte-identical to the pre-split baseline; full `make
  test-unit` battery green on the final head.
