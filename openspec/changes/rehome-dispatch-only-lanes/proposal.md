# Change: Re-home the deactivated bot lanes as documented event/dispatch-only lanes

## Why

`ci-schedule-discipline` (#2701/#2704) removed the `schedule:` blocks of seven bot lanes
(architecture-bot, issue-bot, issue-dedupe, issue-refiner, registry-sync-review, search-smoke,
rebase-bot) but left their workflow headers describing clocks that no longer exist
("reads the real tree every 6 hours", "its own schedule", "hourly (minute :55)"). A contributor
reading `.github/workflows` cannot tell which machinery still runs or who triggers it — the files
lie about the CI surface (issue #2703).

## What Changes

- **Classification (the decision, recorded here and on issue #2703):** all seven lanes are
  **keep event/dispatch-only**; none is retired.
  - `issue-bot.yml` — event-driven: the `agent:implement` label (`issues:` trigger) plus manual
    dispatch. It already has a live GitHub-event trigger.
  - `architecture-bot.yml`, `issue-dedupe.yml`, `issue-refiner.yml`,
    `registry-sync-review.yml`, `search-smoke.yml`, `rebase-bot.yml` — dispatch-only: manual
    `workflow_dispatch` by the principals the owner allowed (issue #2718: owner, collaborator,
    GitHub itself). The interactive host agent performs triage/refinement/rebase work locally and
    never dispatches these lanes.
  - No retirement: the agent-executor scripts (`scripts/rebase_bot_sweep.py`,
    `scripts/rebase_bot.sh` and their `make` targets) are shared plumbing — `bot_claims`'s rebase
    claim subject is also how the allow-listed `engine-bump-rebase.yml` lane marks a PR taken.
    Deleting the lanes would orphan the claim protocol the weekly engine lane depends on. The
    human dispatch path stays real (owner/collaborator/GitHub), so the files describe machinery
    that can actually run.
- Every one of the seven workflow files gets a **`# Triggered now (issue #2703):` header line**
  stating its live trigger set and who may start it; the stale "Trigger surface" wording that
  names the removed clocks is corrected.
- `scripts/check_ci_discipline.py`: a `DISPATCH_ONLY_LANES` roster (the seven lanes -> the
  driver) becomes a checked fact: each roster file MUST declare no `on.schedule:` and MUST carry
  the `# Triggered now (issue #2703):` marker; a missing marker or a re-appearing schedule is a
  finding. `report` prints the classification.
- `tests/test_ci_discipline.py`: pin both directions (marker present -> green; marker missing or
  schedule re-added on a fixture -> finding).

## Impact

- Affected specs: `ci-discipline` (ADDED: deactivated lanes are classified and declare their live trigger)
- Affected code: the seven `.github/workflows/*.yml` headers (comments only), `scripts/check_ci_discipline.py`, `tests/test_ci_discipline.py`
- No make targets, scripts, or tests are deleted; no dispatch inputs change (dispatch-forms table stays valid).
