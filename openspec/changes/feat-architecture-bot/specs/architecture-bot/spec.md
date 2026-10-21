# architecture-bot

## ADDED Requirements

### Requirement: the architecture bot runs every 6 hours, on its own slot, and only for the owner or a collaborator

`.github/workflows/architecture-bot.yml` MUST declare `name:` stating the work, a
`schedule` of `47 */6 * * *`, and a `workflow_dispatch` carrying a documented `dry`
input and a documented `doc` input with defaults. It MUST declare its own
`concurrency:` group with `cancel-in-progress: false`. Before any step that reads a
secret or calls the agent it MUST reject an actor that is neither the repository
owner nor a collaborator with `admin`/`maintain`/`write` permission.

WHEN the schedule fires every sixth hour
THEN the run starts on minute `:47`, owns that slot alone, and queues behind an
in-progress run instead of starting a parallel one.

#### Scenario: the workflow is 6-hourly, dispatchable, and guarded
- **Given** `.github/workflows/architecture-bot.yml`
- **When** its triggers, concurrency block, and first job are read
- **Then** the cron is `47 */6 * * *`, dispatch inputs `dry` and `doc` are documented with defaults, and the concurrency group is its own with `cancel-in-progress: false`
- **And** the first job refuses an actor that is not the owner or a collaborator with admin/maintain/write, before any `secrets.*` value is used
- **Test:** `tests/test_architecture_bot.py::test_workflow_is_six_hourly_dispatchable_and_guarded`

### Requirement: the brief is derived from the real tree and the doc's own history

`scripts/architecture_bot.py brief` MUST write a brief from the checked-out
repository, not from a maintained list: the tracked top-level layout, every
`scripts/*.py` module with the first line of its docstring, every public make
target and its `##` help text, every workflow with its crons, the `data/`,
`skills/`, `containers/` and `tests/` trees, and the commits/files that changed
since the commit that last touched the doc. It MUST make no model call and MUST
NOT write any file except the brief.

WHEN the doc was last updated at commit `C` and the tree has moved
THEN the brief names `C`, the commits after it, and the changed paths, and still
carries the current doc verbatim.

#### Scenario: the brief names what changed since the doc's last commit
- **Given** a real git repository whose doc was committed and then a script was changed
- **When** `architecture_bot.brief(root, doc)` runs
- **Then** it reports the doc's last commit, the changed path, and the current doc text
- **And** it reports the make targets and script modules actually present in that tree
- **Test:** `tests/test_architecture_bot.py::test_brief_names_the_drift_since_the_docs_last_commit`

#### Scenario: a doc that has never been committed is a full rebuild
- **Given** a real git repository with no commit touching the doc path
- **When** `architecture_bot.brief(root, doc)` runs
- **Then** it says the doc has no history and lists the tracked files as the surface
- **And** the brief instructs the agent to create the doc
- **Test:** `tests/test_architecture_bot.py::test_brief_treats_an_uncommitted_doc_as_a_full_rebuild`

### Requirement: a run publishes ONE linked issue and ONE PR, and nothing when there is no drift

`scripts/architecture_bot.py publish` MUST create exactly one issue whose body carries
`Issue:`, `Fix:`, `Benefit:`, `Technical:`, then create `agent/architecture-<UTC stamp>`,
commit ONLY the doc (authored `Asimov Agent <support@docondee.com>`), push it, and open
one PR to `main` whose body ends with `closes #<issue>`. It MUST NOT merge and MUST NOT
push to `main`. It MUST do nothing — no issue, no branch, no PR — when the doc is
unchanged against `HEAD`, when the doc is missing or shorter than 200 characters, or when
an `agent/architecture-*` PR is already open.

WHEN the agent's rewritten doc differs from `HEAD` and no architecture PR is open
THEN one issue is filed, one branch carries the doc change, and one PR closes that issue.

#### Scenario: drift opens a linked issue and PR authored by the bot identity
- **Given** a repository with a changed doc and a recorded `gh` call log
- **When** `publish` runs with a stamp
- **Then** one issue is filed with all four body parts, the branch is `agent/architecture-<stamp>`, the commit is authored `Asimov Agent`, and the PR body ends with `closes #<n>`
- **And** no `gh pr merge`, no push to `main`, and no file other than the doc is committed
- **Test:** `tests/test_architecture_bot.py::test_publish_opens_one_linked_issue_and_pr`

#### Scenario: an unchanged doc files nothing
- **Given** a repository whose doc is identical to `HEAD`
- **When** `publish` runs
- **Then** it reports `action=none` with the reason, and creates no issue, branch, or PR
- **Test:** `tests/test_architecture_bot.py::test_publish_files_nothing_without_drift`

#### Scenario: an open architecture PR suppresses the next run's issue
- **Given** an open PR whose head is `agent/architecture-20261021T1200`
- **When** `publish` runs again with drift on the doc
- **Then** it reports `action=pending`, names the open PR, and files nothing
- **Test:** `tests/test_architecture_bot.py::test_publish_skips_when_an_architecture_pr_is_open`

#### Scenario: a run that edited the code is refused
- **Given** a changed doc and a tracked source file the agent modified
- **When** `publish` runs
- **Then** it exits non-zero naming the stray file, and files nothing
- **And** an untracked run artifact (the brief) is not treated as a stray edit
- **Test:** `tests/test_architecture_bot.py::test_publish_refuses_when_the_agent_edited_the_code`

#### Scenario: a refresh never starts from a feature branch
- **Given** a repository checked out on `feat/other-work` with a changed doc
- **When** `publish` runs
- **Then** it exits non-zero naming the branch, and files nothing
- **Test:** `tests/test_architecture_bot.py::test_publish_refuses_to_commit_on_a_feature_branch`

#### Scenario: an empty or truncated doc is refused
- **Given** a doc shorter than 200 characters, or a missing doc
- **When** `publish` runs
- **Then** it exits non-zero naming the doc, and files nothing
- **Test:** `tests/test_architecture_bot.py::test_publish_refuses_an_empty_doc`

### Requirement: the one model leg edits only the architecture doc, inside the agent image

`make architecture-bot-doc` MUST require `NOUS_API_KEY`, ensure the pinned agent image,
forward credentials through the existing `AGENT_SHELL_FORWARD`/scrubbed seam, and run
Hermes with a prompt that restricts writes to the doc path. The transcript MUST be
redacted before it prints, and the workflow MUST upload `hermes-run.scrubbed.log`, never
the raw log.

WHEN the doc stage runs
THEN it invokes Hermes inside `llgenie/agent:latest` with the brief and the doc path, and
only `docs/ARCHITECTURE.md` may change.

#### Scenario: the doc leg is one scrubbed container call
- **Given** the `architecture-bot-doc` recipe and `_architecture-bot-doc` prompt
- **When** both are read
- **Then** the public recipe requires NOUS_API_KEY, resolves the agent image, forwards the credentials, and pipes through `scrubbed_run`
- **And** the prompt names only the doc as writable and forbids branches, pushes, and merges
- **Test:** `tests/test_architecture_bot.py::test_doc_leg_is_one_scrubbed_container_call`

### Requirement: the architecture doc is wired into the repository's gates

`docs/ARCHITECTURE.md` MUST exist and describe the shipped path; `make
architecture-bot-brief`, `architecture-bot-doc`, `architecture-bot-publish`, and
`architecture-bot` MUST be documented `##` targets (so `make help`, `check-docs` and
`check-wiring` see them); the README MUST document the bot and regenerate the dispatch
table.

WHEN `make ci-unit` runs
THEN the wiring, docs, dispatch-form, workflow, and bot-isolation gates all pass with the
bot in the tree.

#### Scenario: the targets and the doc are part of the repository's gates
- **Given** the Makefile, README, and `docs/ARCHITECTURE.md`
- **When** the wiring/docs/dispatch gates run
- **Then** every new target is documented in README and declared in `.PHONY`, and the doc exists with real content
- **Test:** `tests/test_architecture_bot.py::test_targets_and_doc_are_wired_into_the_gates`
