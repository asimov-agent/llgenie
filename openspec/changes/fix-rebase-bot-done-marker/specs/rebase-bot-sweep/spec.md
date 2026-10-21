# rebase-bot-sweep

## MODIFIED Requirements

### Requirement: "already rebased today" is read from the bot's DONE marker, never from any comment

`scripts/rebase_bot_sweep.py::rebased_today` MUST parse the thread with
`bot_claims.DONE_RE` and count a PR only when the marker names `bot_claims.REBASER`, its
timestamp is today's UTC date, and its kind is `rebased`. A `bot-claim` comment, a marker of
another kind, a marker from another bot, and a marker from another day MUST NOT count.

`scripts/rebase_bot.sh` MUST record kind `rebased` on the success path only, and `gave-up` on
every failure path (agent could not resolve, `rebase --continue` failed, conflict markers remain,
structural checks failed), so a failed attempt never records the day as done.

WHEN the sweep runs on a PR whose newest marker is a claim, or a `gave-up`
THEN that PR is a candidate again, and the run states it was not already rebased today.

#### Scenario: a claim-only thread is not "already rebased today"
- **Given** a PR whose only bot comment is a `bot-claim: rebase-bot …` marker dated today
- **When** the sweep runs over it
- **Then** the PR is picked (when it is BEHIND/DIRTY), not passed over as already rebased
- **Test:** `tests/test_rebase_bot_sweep.py::test_a_claim_is_not_a_rebase_record`

#### Scenario: a rebased DONE marker dated today keeps the PR out of the day's work
- **Given** a PR whose comments carry `<!-- bot-done: rebase-bot <today>… rebased -->`
- **When** the sweep runs over it
- **Then** it is passed over as already rebased today
- **Test:** `tests/test_rebase_bot_sweep.py::test_a_rebased_done_marker_is_the_record`

#### Scenario: a gave-up marker does not record the day as done
- **Given** a PR whose comments carry `<!-- bot-done: rebase-bot <today>… gave-up -->`
- **When** the sweep runs over it
- **Then** the PR is a candidate again
- **Test:** `tests/test_rebase_bot_sweep.py::test_a_gave_up_marker_does_not_record_the_day`
