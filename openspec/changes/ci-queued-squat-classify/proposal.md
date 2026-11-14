# Proposal: ci-queued-squat-classify

## Why

Issue #2656. Measured 2026-11-14 on main `fc39b4180` at 03:10Z: six CI-surface runs have squatted in
non-terminal states for 3 days. Five are `queued` since 2026-11-11 20:33-20:47Z with empty
`pull_requests` and their head branches deleted (`feat/2472-semgrep-ghost-runs` and
`feat/engine-bump-regen-guard` both 404 on the git refs API): runs 43096752613, 43096752703,
43098130674, 43098130679, 43098130785. A sixth, run 43096752585, reports `in_progress` since
2026-11-11 20:33Z while its job records have expired to the single ci-verdict self row (conclusion
`failure`) — the job-expiry shape of #1837/#1889, whose verdict can never conclude. `queued_run_alarm`
fires twice an hour but its JOB-ROW scan renders "no job has been queued longer than 30 minutes" for
all six: the orphan runs instantiate no queued jobs and the expired run's single job has concluded, so
the alarm reads CLEAN while the queue is squatted — the same starvation signal #817 raised, in
miniature. The zero-job monitor (#1410/#1704/#2600) names and retires the ZERO-JOB phantoms; nothing
in the tree classifies the orphan/live split or reads the trapped `in_progress` as expiry.

## What Changes

- **Run-level squat classification in `queued_run_alarm`.** The alarm learns, beside its job-row scan,
  a run-level classification of the runs still non-terminal past the `--minutes` threshold:
  - ORPHAN — no OPEN pull request tracks its head branch AND the head branch is deleted (git ref 404;
    a transient read is treated as present so a live run is never mis-called);
  - EXPIRED — a run still `in_progress` whose job records have ALL concluded: read as JOB EXPIRY
    (#1889 wording), never as a live matrix, and never counted toward the live queued/in_progress
    supply.
  - a run with an OPEN PR, or a head branch still present, is LIVE and not a squat.
- **One report per EPISODE.** The squat is rendered (run ids + orphan/live expired split) and, with
  `--comment`/`--dry`, filed as ONE deduped issue whose marker `<!-- queued-run-alarm: queued-run-squat
  episode <sorted ids> -->` is keyed on the sorted run-id set — the same squat is reported once, a new
  squatted run is a fresh episode. Rendered through `issue_body.render`, the one issue shape.
- **Never cancelled.** The alarm never cancels nor deletes any run it reports: the fleet standing rule
  reserves cancellation for the owner's explicit word. The handling rule is written in `docs/BOTS.md`.

## Impact

- Affected specs: `queued-run-alarm` (ADDED requirements: run-level orphan/expired classification;
  once-per-episode reporting; expiry not a live matrix).
- Affected code: `scripts/queued_run_alarm.py`, `tests/test_queued_run_alarm.py`, the `docs/BOTS.md`
  handling rule, a docs fragment, and an agent-wiki note.
- Out of scope (separate, the issue's own `Not covered`): cancelling any run (owner's word only), and
  the cause of queued-alarm run 43550202976's red `scope` job (unfetched step log — diagnosed at run
  completion or as its own issue).
- After merge, the running queued-alarm classifies and names the orphan/expired squat once per episode
  and reads run 43096752585 as job expiry rather than a live matrix.
