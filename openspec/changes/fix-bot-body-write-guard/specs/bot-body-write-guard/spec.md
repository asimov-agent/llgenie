# bot-body-write-guard

## ADDED Requirements

### Requirement: a bot's PR-body write is guarded by the live body

Every bot leg that REPLACES the body of an existing pull request MUST write it through
`scripts/pr_body_write.py` (via `make bot-body-write` for a shell producer). The seam MUST read the live
body through `gh` before writing, and MUST skip the write when the live body carries content the proposed
body drops: any heading line the proposal lacks, or any ticked `- [x]` line carrying `(proven:` the
proposal lacks. A skipped write MUST log the reason naming each dropped heading/tick and MUST post a PR
comment naming the section it refused to drop. A proposal equal to the live body MUST write nothing. Only
a proposal that preserves every such live section may reach `gh pr edit`.

#### Scenario: a template that would drop a lane's evidence is refused

- **Given** a PR whose live body carries a `## Not covered` section with ticked `- [x]` items carrying
  `(proven: …)`
- **When** the seam is called with a proposed body that lacks that section
- **Then** no `gh pr edit` call is made, the run log names the skipped write and the dropped section, and a
  PR comment names the section the seam refused to drop

- **Test:** `tests/test_pr_body_write.py::test_a_body_dropping_the_live_not_covered_section_is_refused`,
  `tests/test_pr_body_write.py::test_the_skip_is_reported_as_a_pr_comment_naming_the_section`

#### Scenario: a content-preserving rewrite writes, an equal body does not

- **Given** a PR whose live body carries the same sections and proven ticks
- **When** the seam is called with a body that preserves them (a re-stamped copy), and again with an
  identical body
- **Then** the preserving copy reaches `gh pr edit`, the identical body produces no write at all, and no
  skip comment is posted

- **Test:** `tests/test_pr_body_write.py::test_a_preserving_rewrite_reaches_the_write`,
  `tests/test_pr_body_write.py::test_an_identical_body_writes_nothing`

#### Scenario: the fix-bot repair step routes through the seam

- **Given** the fix-bot re-stamp step in `.github/workflows/fix-bot.yml`
- **When** its steps are read
- **Then** the body write appears only as `make bot-body-write` after `make bot-stamp-body`, with no
  direct `gh pr edit --body-file` call left in the repair path

- **Test:** `tests/test_pr_body_write.py::test_fix_bot_repairs_through_the_seam`
