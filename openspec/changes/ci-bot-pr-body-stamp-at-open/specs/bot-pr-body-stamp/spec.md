# bot-pr-body-stamp

## ADDED Requirements

### Requirement: a bot PR body carries the preflight pair when it is opened

Every producer that composes a bot PR body MUST write the two lines the `check-pr-agents-line` gate reads —
`AGENTS: <sha> <bytes>b <lines>l` and `BASE: <sha> (== origin/main at open)` — at the moment it opens or
edits the PR. The pair MUST be produced by `bot_preflight.stamp_body` (via `make bot-stamp-body` for a shell
producer), MUST sit flush-left and adjacent, and MUST cite a sha measured from `origin/main` or from the
`main` the producer's own checkout stands on.

A producer that cannot measure such a ref MUST refuse to open the PR and exit non-zero, naming `#2050`, rather
than open a body the gate will red. The pair MUST NOT be left to an agent remembering `make bot-preflight`.

#### Scenario: a producer's body is stamped at open

- **Given** a bot producer that has composed a four-part PR body and a checkout whose `main` resolves
- **When** it opens the PR
- **Then** the body carries the measured `AGENTS:` line and the `BASE:` line directly beneath it

- **Test:** `tests/test_bot_stamp_body.py::test_the_issue_bot_body_carries_the_pair_at_open`,
  `tests/test_security_bot.py::test_green_gates_edit_push_and_open_the_pr`

#### Scenario: the stamped body passes the gate, the unstamped one does not

- **Given** a real bot-authored branch cut from `main`
- **When** the gate's own `pr_agents_line_findings` reads a stamped body and the same body without the pair
- **Then** the stamped body yields no finding and the unstamped body yields an `agents-line` finding

- **Test:** `tests/test_bot_stamp_body.py::test_a_stamped_body_passes_the_gate_and_the_unstamped_one_does_not`

#### Scenario: an unmeasurable checkout refuses instead of opening

- **Given** a leg whose checkout has no `origin/main`, `origin/HEAD` or `main` ref to measure
- **When** it tries to open the PR
- **Then** it exits non-zero naming `#2050` and no PR is opened

- **Test:** `tests/test_bot_stamp_body.py::test_open_pr_refuses_to_open_a_body_it_cannot_stamp`,
  `tests/test_bot_stamp_body.py::test_the_record_is_measured_from_the_ref_the_checkout_stands_on`

#### Scenario: a stale or mangled pair is replaced, not duplicated

- **Given** a body already carrying an old valid pair and a prose line about the rulebook
- **When** it is re-stamped
- **Then** exactly one `AGENTS:` line and one `BASE:` line remain, both the measured ones, and a second
  stamping changes nothing

- **Test:** `tests/test_bot_stamp_body.py::test_a_stale_or_mangled_pair_is_replaced_not_duplicated`,
  `tests/test_bot_stamp_body.py::test_stamping_is_idempotent`

### Requirement: a repair pass re-stamps and never claims a push it did not make

`fix-bot` MUST re-stamp the PR body after it repairs a PR whose branch was synced onto the latest `main`, and
its outcome comment MUST claim a push only when the push step produced a sha. A green loop that pushed nothing
MUST say so — the loop's verdict is not the fact.

#### Scenario: a repaired PR keeps a valid stamp

- **Given** a PR the fix-bot repaired and synced onto the latest `main`
- **When** the repair lands
- **Then** the body is re-stamped from the new base through `make bot-stamp-body`

- **Test:** `tests/test_bot_stamp_body.py::test_the_fix_bot_re_stamps_a_repair_and_only_claims_a_push_it_made`

#### Scenario: a green loop with nothing to push claims nothing

- **Given** a fix-bot round whose loop ended green and whose tree had no change to commit
- **When** the outcome comment is written
- **Then** it states the head did not move instead of claiming a push

- **Test:** `tests/test_bot_stamp_body.py::test_the_fix_bot_re_stamps_a_repair_and_only_claims_a_push_it_made`
