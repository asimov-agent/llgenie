## ADDED Requirements

### Requirement: a trigger-green sweep clears the verdict lane's own stale artifact row
The merge sweep that a green workflow-run completion triggered SHALL treat a concluded-red check-run row whose workflow file is the verdict lane's own (`ci-verdict.yml`) as a cleared, named non-block — the green completion IS this head's newest verdict decision. All other reds keep deferring, and every sweep without a green trigger keeps the strict reading.

#### Scenario: the measured wedge clears and the PR merges
- **GIVEN** a review-blocked PR whose head carries green rows for its CI attempt plus a red `ci-verdict` row posted by an earlier `ci-verdict.yml` run (the #2990 shape: red row `136684722878`, green row landing ten seconds after the sweep's read)
- **WHEN** the merge job runs with `trigger_green` set (the workflow's `conclusion == 'success'` gate)
- **THEN** the PR merges, and the log names the stale verdict-artifact row it cleared and why

#### Scenario: no green trigger keeps the strict reading
- **GIVEN** the same head
- **WHEN** the merger decides WITHOUT `trigger_green` (the recheck sweep, `red-check`, `explain`)
- **THEN** the red `ci-verdict` artifact row still defers, naming it

#### Scenario: a red verdict JOB row of the CI attempt is not an artifact
- **GIVEN** a head whose newest `ci.yml` attempt carries a red `ci-verdict` JOB row (the attempt judged itself red)
- **WHEN** a trigger-green sweep reads the head
- **THEN** the sweep still defers and names that red — the skip is by workflow FILE, never by row name

#### Scenario: foreign reds stay blocking under a green trigger
- **GIVEN** a trigger-green sweep reading a head that carries a red row from a foreign workflow (an issue-bot `implement` failure)
- **THEN** the sweep defers and names that foreign red
