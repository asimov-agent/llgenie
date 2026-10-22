# 2026-10-22 — a close queues the canonical issue it cites (#521)

**Issue:** [#521](https://github.com/asimov-agent/llgenie/issues/521) · **PR:** the PR that closes it

## What was wrong

The issue-bot's picker only lists issues labelled `agent:implement` (then `agent:ready`). The
run-failure reactor files its issues *with* that label, so the bot only ever sees reactor copies. When
one is a duplicate, the bot closes it and cites the canonical issue in prose — and never labels it.

Measured on `main` (`1d36673`), run `39806884507`:

```
[issue-implementer] picked #440
[agent] Verdict: TRIAGE: close
EVIDENCE: Open issue #399 tracks this exact failure …
[issue-implementer] closed #440 with cited evidence; labelled agent:closed
```

Post-run state: `#399` OPEN with no labels, `#254` OPEN with no labels, `#440` CLOSED, `#466`/`#469`
OPEN and labelled. So each recurrence: reactor copy → bot closes the copy → canonical issue invisible →
defect reproduces. `#400` closing as a "flake" toward `#254` two days earlier is the loop completing
once with no fix.

Because the canonical issue names a concrete root cause (`scripts/llgenie_serve.py::_hf_get` retries
`HTTPError`/`URLError` but not a mid-body-read `TimeoutError`), the loop was wasting the bot's three
daily runs on retiring copies of an issue nobody could reach.

## What changed

- `scripts/issue_implementer.py`: `QUEUE_LABELS`, `ISSUE_REF`, `cited_issues()`, `_issue_meta()` and
  `queue_canonical()`; the close path calls `queue_canonical()` (dry included). Every cited issue that
  is open and carries no agent label gets `agent:implement`; a closed, decided or already-queued one is
  left alone, and a cited number that is not a readable issue is printed and skipped.
- `tests/test_issue_implementer.py`: the fake `gh` answers the `--json state,labels` lookup, and four
  cases lock the behaviour (queue the canonical; leave closed/decided/queued/self alone; unreadable
  reference still closes; dry mutates nothing).
- `README.md`: the rule is documented in the issue-bot section.

## Verified

- `python -m pytest tests/test_issue_implementer.py tests/test_bot_claims.py` in `llgenie/test:latest`
  → 51 passed.
- Real, read-only proof: `apply-verdict --dry` against the live repo printed
  `#399: already decided (agent:refined)`, `#466/#470: already queued`,
  `#999: not a readable issue`, `would queue #254 as the canonical issue` — the decision is made against
  real issue state, not a fixture.
- `make lint`, `make check-docs`, `make check-wiring`,
  `make openspec-validate NAME=issue-bot-queue-canonical`, `make test-unit` → recorded in the PR.

## Follow-up found while doing this

A refine parks an issue forever: `agent:refined` is in `DECIDED_LABELS`, so the picker skips a refined
issue even though the refine verdict just made it *more* implementable. #399 itself ended up carrying
`agent:implement` **and** `agent:refined` and was therefore unpickable. Filed as
[#522](https://github.com/asimov-agent/llgenie/issues/522); #399 was re-queued by hand
(`agent:refined` removed, `agent:ready` added) so the next run can implement it.
