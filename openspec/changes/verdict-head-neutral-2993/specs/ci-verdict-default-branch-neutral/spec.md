## ADDED Requirements

### Requirement: a green default-branch run posts a neutral verdict row, never a red one
When the judged CI run's event is neither empty nor `pull_request` (a `push`, `schedule`, or `workflow_dispatch` run at the default branch) and the judged verdict is GREEN while the head carries unjudged blocking check-runs, the verdict SHALL post a `neutral` check-run and exit 0, and SHALL print a `DEFAULT-BRANCH HEAD` line naming the event, the rule (no merge is gated at a default-branch commit), and every unjudged red it is not reddening. It SHALL NOT post `success` for such a head while a red sits on it.

#### Scenario: the measured main-head row set posts neutral
- **WHEN** a replay carries all-green judged jobs and the head's check-runs include failure rows from issue-bot runs `44822618375` and `44822619990` (job `implement`, measured at main `a4afb185e`, artifact `136591838065`) and the run event is `push`
- **THEN** the exit is 0, the posted conclusion is `neutral`, the output names each unjudged red with its run id, and a `DEFAULT-BRANCH HEAD` line explains why nothing reddens

#### Scenario: a replay carries the event without the API
- **WHEN** `--run-event` (or `CI_VERDICT_RUN_EVENT`) is given a non-`pull_request` event with `--jobs`/`--checks` and no run id
- **THEN** the default-branch arm applies exactly as it does for a fetched run whose `event` says the same, and a replay with NO event keeps the pull_request semantics (the forcing stays red)

### Requirement: pull_request heads keep the unjudged-red forcing unchanged
When the judged run's event is `pull_request` (or is unknown to the replay), a GREEN judged verdict with unjudged blocking check-runs at the head SHALL still post `failure` and exit 1, exactly as pinned by the #2116/#2221 tests.

#### Scenario: the specimen head without an event still reds
- **WHEN** the same green-judged / red-unjudged row set is judged with no event given
- **THEN** the exit is 1 and the posted conclusion is `failure` with the UNJUDGED RED naming intact

### Requirement: a run whose own judged jobs are red keeps its failure at any event
A judged verdict that is not GREEN (a failing or absent judged job) SHALL post `failure` and exit 1 even when the run's event is `push`.

#### Scenario: a red judged job on a push run
- **WHEN** a replay with run event `push` carries a judged job whose conclusion is `failure`
- **THEN** the exit is 1, the posted conclusion is `failure`, and no `DEFAULT-BRANCH HEAD` neutral line appears
