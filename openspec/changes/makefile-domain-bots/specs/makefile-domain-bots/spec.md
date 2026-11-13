# makefile-domain-bots — Spec Delta

## ADDED Requirements

### Requirement: The bot-domain surface lives in mk/bots.mk

The repository SHALL keep the bot-leg surface in `mk/bots.mk`, included from the top
Makefile, with every target name and recipe identical to the pre-split top Makefile.
The file SHALL contain exactly these 72 targets: `bot-preflight`, `bot-stamp-body`,
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

#### Scenario: Target-set parity

- **WHEN** `make -qp` is run on the post-split tree and the target names are compared
  with the pre-split baseline
- **THEN** the filtered target sets are identical (no target added, removed or renamed)

#### Scenario: Help and wiring unchanged

- **WHEN** `make help` and `make check-wiring` output is compared before and after the
  split (directory banners normalized)
- **THEN** both outputs are byte-identical

### Requirement: The top Makefile includes mk/bots.mk

The top Makefile SHALL carry exactly one new line `include mk/bots.mk` beside the
existing include lines, and SHALL still expose every moved target through that
include. Shared variables (`AGENT_IMAGE`, `HERMES_LOG*`, and the rest) stay in the
top Makefile.

#### Scenario: A moved target still runs from the top

- **WHEN** `make -n auto-merge` or `make -n issue-bot-gates` is run at the repository
  root
- **THEN** the recipe prints and the exit status is 0

### Requirement: Makefile-text readers resolve the include chain

Every guard or test that slices Makefile text for a bot-domain target SHALL resolve
`include mk/*.mk` before slicing (the `conftest.makefiles_text()` /
`_makefile_list()` reader pattern), so no gate goes blind after the move.

#### Scenario: Battery green

- **WHEN** `make test-unit` runs on the final PR head
- **THEN** the full battery passes with zero failures
