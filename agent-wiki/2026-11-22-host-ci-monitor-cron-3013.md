# Host CI monitor cron for the pipeline board (issue #3013)

Date: 2026-11-22. Issue: #3013. OpenSpec change: `host-ci-monitor-cron`.

## What was verified
- `scripts/ci_monitor.py` builds the incident snapshot from read-only `gh` reads through the
  `scripts/proc.py` seam: `MAIN-RED` (completed main runs concluding `failure`/`cancelled`/`timed_out`
  with `updatedAt` inside the `MAX_AGE_HOURS=72` window), `PR-CHECKS`, `PR-MERGE` (`DIRTY`/`BEHIND`),
  `PR-REVIEW` (`CHANGES_REQUESTED`), sorted, no timestamps; `MONITOR-OK` on a clean board;
  `MONITOR-ERROR gh-fetch-failed` (exception detail only on stderr). In-flight states and
  green/skipped outcomes are deliberately noise-suppressed.
- Live proof: `make -s ci-monitor` rc=0 twice — identical sha256 over a 14-line snapshot (age window
  dropped the 38-line stale-cancel flood seen earlier the same day).
- `tests/test_ci_monitor.py`: 7 tests replay recorded payloads through an injected fake fetch (no
  `gh` spawned): red main run, age-window in/out/unstamped, PR incident lines + draft/green
  suppression, clean-board byte-stability, fetch-failure contract. `make test-unit` collected them green.
- Host side: `~/.hermes/scripts/llgenie_ci_monitor.py` wraps `make ci-monitor` against a dedicated
  monitor clone (never the user's checkout) and emits stable `MONITOR-ERROR make-ci-monitor-failed`
  when make itself fails; exactly one `[active]` job `llgenie-ci-monitor` on profile
  `llgenie-ci-pipelines-maintainer` (`--monitor-script`, `--workdir` repo, deliver `local`); every
  other profile cron store stays empty.

## Key decision
The blanket host-cron ban of 2026-11-14 removed the watchdog without a replacement; the owner
sanctioned exactly one exception (AGENTS.md rewritten to ban-plus-one-named-exception). Monitor mode
is the trigger: unchanged snapshot hash suppresses the agent entirely; a changed snapshot wakes one
run that triages incidents per AGENTS or, on a clean board with no open lane, takes the next board
issue end-to-end — still one lane at a time, never fan-out, never queue-pump, never hand-merge.

## Current status
Script, target, tests, AGENTS rule, and docs on branch `feat/host-ci-monitor-cron` (PR pending for
#3013); the cron job is registered once the target lands on `main` (the wrapper degrades to a stable
error line until then).
