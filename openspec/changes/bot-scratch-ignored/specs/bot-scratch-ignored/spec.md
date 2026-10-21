# bot-scratch-ignored

## ADDED Requirements

### Requirement: A bot's run inputs are ignored by git, and the roster is checked with real git

Every artifact a bot leg writes at the repo root (`issue.md`, `triage.md`, `refine-in.md`, `refine.md`,
`comment.md`) SHALL be ignored by git, so `git add -A` in a bot run stages repository content only. The
push step SHALL NOT carry a per-file `git reset` exclude, which is a denylist that drifts.

WHEN the tree is inspected with git
THEN every run input SHALL be reported by `git check-ignore`, and the issue-bot push step SHALL carry no
`git reset -- <file>` exclude.

#### Scenario: the verdict file is not committable

Given the repository as committed
When  `triage.md` is checked with `git check-ignore`
Then  git reports it as ignored, so a run that writes only its verdict cannot stage it and a run whose
      implementation is missing stages nothing at all.

- **Test:** `tests/test_bot_scratch_ignored.py::test_every_run_input_is_ignored_by_real_git`

#### Scenario: the roster cannot go stale

Given the roster of run inputs the test declares
When  each name is looked for in the producers (the Makefile, `.github/workflows/*.yml`, `scripts/*.py`)
      and in the `.gitignore` run-input block
Then  every roster name is ignored and written by a producer, every ignored name is a roster entry or a
      name a producer writes (nothing is ignored by accident), and no roster entry is stale — a scratch
      file with no ignore line reds the suite, and so does an ignore line nothing writes. A later leg's
      input may join the ignore block before it joins the roster, so two changes never have to land
      together.

- **Test:** `tests/test_bot_scratch_ignored.py::test_the_roster_matches_what_the_producers_write`

#### Scenario: the push step has no denylist

Given `.github/workflows/issue-bot.yml`
When  its commit step is read
Then  it stages with `git add -A` and carries no `git reset -- <path>` exclude, because the ignore file
      is now the one place that decides what a bot may commit.

- **Test:** `tests/test_bot_scratch_ignored.py::test_the_push_step_carries_no_per_file_exclude`

#### Scenario: a scratch file already written does not appear as a change

Given a working tree where a leg wrote `triage.md`
When  `git status --porcelain` runs with untracked files listed
Then  the verdict file is absent from the output, while a real edit to a tracked file is present.

- **Test:** `tests/test_bot_scratch_ignored.py::test_a_written_scratch_file_is_not_a_pending_change`
