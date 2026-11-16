# fix-bot-body-write-guard

## ADDED Requirements

### Requirement: a bot body-write must never drop a lane's protected content

A bot body-write (`make bot-stamp-body` / any `gh pr edit --body` in the fix-bot path) MUST
preserve the LIVE body's protected content: every `## ` heading (a section) and every ticked
`- [x]` line carrying a `(proven: …)` marker. When the body about to be written would drop any of
them, the write MUST be refused — the LIVE body is left untouched and the refusal is logged.

WHEN a bot body-write would drop a section or a `(proven: …)` tick that the live body carries
THEN the write is refused (no `gh pr edit`), the skip is logged, and the live body is left intact.

#### Scenario: a rewrite that would drop `## Not covered` is refused and names the section

- **Given** a live body carrying a lane's `## Not covered` section and a ticked `- [x] … (proven: …)` item
- **And** a proposed body (the template) that regenerated the body WITHOUT that section
- **When** the body-write guard compares them (`body_write_guard(live, proposed)`)
- **Then** it is non-empty, and names both the dropped `## Not covered` heading and the dropped `(proven: …)` tick
- **Test:** `tests/test_bot_stamp_body.py::test_body_write_guard_refuses_a_write_that_would_drop_the_lane_section`

#### Scenario: a re-stamp that only refreshes the AGENTS:/BASE: pair is a safe write

- **Given** a live body carrying a lane's `## Not covered` section and a `- [x] (proven: …)` item
- **And** the re-stamp that refreshes the `AGENTS:`/`BASE:` pair while preserving every section and tick
- **When** the guard compares the live body with its own re-stamp
- **Then** nothing is refused — the write is safe
- **Test:** `tests/test_bot_stamp_body.py::test_body_write_guard_passes_when_the_write_preserves_every_protected_item`

### Requirement: the re-stamp step drives the fix-bot body-write through the guard

The fix-bot repair must re-read the LIVE body and re-stamp only the `AGENTS:`/`BASE:` pair, then run
`make bot-body-guard LIVE=… PROPOSED=…` before any `gh pr edit`. When the guard refuses, the step
MUST NOT write the body — it leaves the live body untouched, logs the skip, and posts a PR comment
naming the section/item it refused to drop, so the lane that owns the body sees the decision.

WHEN the fix-bot re-stamp is about to write a body that would drop a lane's section or tick
THEN it leaves the live body untouched, logs the skip, and comments on the PR naming the refused item.

#### Scenario: the fix-bot repair runs the body-write guard before `gh pr edit`

- **Given** the fix-bot workflow (`.github/workflows/fix-bot.yml`)
- **When** its re-stamp step is read
- **Then** it runs `make bot-body-guard` before `gh pr edit`, leaves the live body untouched on a refusal, and posts `gh pr comment` naming the refused section
- **Test:** `tests/test_bot_stamp_body.py::test_the_fix_bot_re_stamp_runs_the_body_write_guard_before_gh_pr_edit`

### Requirement: the body-write step preserves a lane's section and its ticks

Writing the body over a fixture whose body carries a lane's `## Not covered` section MUST leave that
section and its `- [x]` items intact — the re-stamp may only touch the `AGENTS:`/`BASE:` pair.

WHEN a body carrying `## Not covered` and `- [x] … (proven: …)` items is stamped
THEN the `## Not covered` section, every heading, and every ticked `(proven: …)` item survive unchanged.

#### Scenario: a fixture `## Not covered` section and its ticks survive the write step

- **Given** a live body with a `## Not covered` section and a ticked `- [x] … (proven: …)` item
- **When** `stamp_body` is run over it
- **Then** the section, its heading, and every ticked `(proven: …)` item are present in the result, beside the refreshed `AGENTS:`/`BASE:` pair
- **Test:** `tests/test_bot_stamp_body.py::test_stamp_body_preserves_the_not_covered_section_and_its_ticks`

### Requirement: the guard target is wired, phony and documented

`make bot-body-guard` MUST exist, be declared `.PHONY` (it writes no file of its own name), refuse
without both `LIVE=` and `PROPOSED=`, require them both via `--guard-live`/`--guard-proposed`, and
document that a refusal is a non-zero exit (safe to write is exit 0).

WHEN the Makefile is read
THEN `bot-body-guard` is declared phony, its recipe requires LIVE/PROPOSED and the two guard flags, and the exit contract is documented.

#### Scenario: the guard target is wired and documents its exit contract

- **Given** the Makefile and `mk/bots.mk`
- **When** the `bot-body-guard` target is read
- **Then** it is declared `.PHONY` in the top Makefile, requires `LIVE=`/`PROPOSED=` and `--guard-live`/`--guard-proposed`, and states a refusal is non-zero
- **Test:** `tests/test_bot_stamp_body.py::test_the_body_guard_target_is_wired_phony_and_documented`
