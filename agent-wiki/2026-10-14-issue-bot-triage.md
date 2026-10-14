# The issue bot reads the whole thread and decides: implement / refine / close (issue #261, PR #262)

## Why

The implementer (#248) read the issue **body** and implemented it. An issue whose fifth comment
narrows the request ("only for CPU builds") was therefore implemented wrongly, an issue that was
already done or superseded still burned one of the three daily PR slots, and an ambiguous issue
got a confident guess. The comment thread *is* the specification, and the bot ignored it.

## What

- `scripts/issue_implementer.py`: `dispatch` fetches the issue with `--comments` and writes
  `issue.md` as the **body + every comment in order with author and date + a decision
  instruction** whose verdict format (`TRIAGE:` plus `REFINED:` / `EVIDENCE:` / `REASON:`) is
  machine-read. Issues labelled `agent:refined` / `agent:closed` are skipped, so no verdict loops.
- New `apply-verdict` (deterministic, no LLM): `implement` mutates nothing; `refine` posts ONE
  comment with the restatement and labels `agent:refined`; `close` posts the reason with its
  **cited evidence**, closes, and labels `agent:closed`. A close with no `EVIDENCE:` block is
  refused loudly, as is an unrecognised verdict.
- Makefile: `issue-bot-triage` (the Hermes review, inside the agent image) and
  `issue-bot-verdict` (apply it) — both phony, both documented in the README (issue #257's gate).
- Workflow: dispatch -> triage -> verdict -> implement/push/PR only when the verdict is
  `implement`. A refine or a close ends the run with a comment instead of a PR.
- Tests (22 in `tests/test_issue_implementer.py`): the `--comments` fetch, the rendered thread,
  the decided-skip, the verdict grammar (including the two refusals), and each outcome's exact
  argv — including that a refine/close never opens a PR.

## Measured

- `tests/test_issue_implementer.py`: 22 passed.
- `make check-docs` (issue #257's gate) on this change: the two new targets are documented.
