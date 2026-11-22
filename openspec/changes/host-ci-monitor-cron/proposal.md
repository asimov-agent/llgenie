# host-ci-monitor — proposal

Issue: [#3013](https://github.com/asimov-agent/llgenie/issues/3013)

## Why

The host follows the `main` CI pipelines and the open-PR pipelines only while an interactive lane
happens to be open. Red `main` runs, failing PR checks, and PRs drifting to `DIRTY`/`BEHIND` sit
unnoticed between sessions, and when no lane PR is open nothing keeps the board moving. The blanket
host-cron ban of 2026-11-14 ("Hermes cron jobs never run on the host") removed the only scheduled
watchdog without replacing it. The owner directed (2026-11-22) exactly one replacement: a Hermes
gateway monitor cron that watches the pipelines through `gh`, wakes the agent only on incidents, and
keeps the next issue moving when no PR was created.

## What Changes

1. **`scripts/ci_monitor.py`** — a read-only, `gh`-backed incident snapshot of the repo: completed
   `main`-branch runs with a failing/cancelled/timed-out conclusion, open (non-draft) PRs with failing
   check buckets, open PRs whose `mergeStateStatus` is `DIRTY` or `BEHIND`, and open PRs with
   `CHANGES_REQUESTED` review. Output is sorted, timestamp-free, and byte-stable while the incident
   set is unchanged; a clean board prints exactly `MONITOR-OK`. A gh fetch failure prints the stable
   line `MONITOR-ERROR gh-fetch-failed` (details to stderr).
2. **`make ci-monitor`** — the Makefile target that runs it against `$(GH_REPO)`.
3. **`tests/test_ci_monitor.py`** — each snapshot shape (red main run, failing PR checks,
   `DIRTY`/`BEHIND`, `CHANGES_REQUESTED`, clean board, fetch failure, byte-stability) proven through
   an injected fetch seam against recorded payloads.
4. **One sanctioned Hermes cron job** — `llgenie-ci-monitor` on profile `llgenie-ci-pipelines-maintainer`,
   created with `--monitor-script ~/.hermes/scripts/llgenie_ci_monitor.py` (a stable-stdout wrapper
   over `make ci-monitor`), `--workdir` at the repo root so `AGENTS.md` is the cron agent's project
   context, deliver `local`. Unchanged snapshot output suppresses the agent run entirely; a changed
   snapshot dispatches exactly one agent run that triages per AGENTS behaviour, and on a clean board
   with no open lane PR the job advances the next open issue end-to-end.
5. **`AGENTS.md`** — the "Hermes cron jobs never run on the host" section becomes ban-plus-one-named-exception:
   every other cron store stays empty/paused, kanban launches stay forbidden, and the monitor job's
   one-lane / no-queue-pump / no-hand-merge / no-draft-PR contract is written down.

## Impact

- New script + target + tests; no CI workflow change (`make check-ci-discipline` and the schedule
  allow-list are untouched — the monitor is host-side).
- `AGENTS.md` rule rewrite (protected file, owner-directed).
- Hermes host state: one active cron job on one dedicated profile; all other stores unchanged.
