# ci-discipline — Spec Delta

## MODIFIED Requirements

### Requirement: The agent never queues or pumps a pipeline; the owner, a collaborator, and GitHub may dispatch one

A CI pipeline starts from a GitHub event, or from a `workflow_dispatch` started by one of the
permitted principals: **the owner, a collaborator, or GitHub itself (the Actions bot)**. The automated
agent SHALL NOT dispatch or queue-pump a pipeline: no `gh run rerun`, no `gh workflow run` /
`workflow_dispatch`, no requeue or re-trigger loops — not even to unblock a wedge. A wedge is fixed by
pushing a commit (rebase, body fix, gate fix), never by pumping the queue. Retired machinery (#2702)
stays dead and is never resurrected in any form. `AGENTS.md` SHALL state this roster and this ban, and
`scripts/check_ci_discipline.py::AGENTS_PIN_PHRASES` SHALL pin the roster wording and the
queue-pumping ban.

#### Scenario: a dispatch by a permitted principal is legitimate

- **Given** the repository after this change, with the CI-discipline section carrying the dispatch
  roster (owner, a collaborator, and GitHub itself / the Actions bot) and the queue-pumping ban,
- **When** `python3 scripts/check_ci_discipline.py check --root <repo>` runs,
- **Then** it exits 0 and prints `check-ci-discipline: OK`, and no finding names the dispatch roster.
- **Test:** `tests/test_ci_discipline.py::test_the_gate_is_green_on_this_repository`

#### Scenario: the blanket-ban phrasing is gone and the roster is pinned

- **Given** the `scripts/check_ci_discipline.py` pin list names the roster wording (not a blanket ban),
- **When** the check runs on a repository whose CI-discipline section has lost that roster wording,
- **Then** it exits non-zero naming the missing pin phrase.
- **Test:** `scripts/check_ci_discipline.py::check` fails on a tree where `AGENTS.md` lost the pin
  phrase `"the owner, a collaborator, and GitHub itself"`; `tests/test_ci_discipline.py` covers the
  section-pin failure direction via `test_the_durable_agents_md_section_is_pinned`.

#### Scenario: queue-pumping stays forbidden

- **Given** the CI-discipline section and its pin phrases,
- **When** the check runs,
- **Then** it keeps pinning the queue-pumping ban (`no gh run rerun`, no requeue loops), and any edit
  that erases the roster or the ban makes the gate red.
- **Test:** `make check-ci-discipline` on the head of this change prints `check-ci-discipline: OK`.
