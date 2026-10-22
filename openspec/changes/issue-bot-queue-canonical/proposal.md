# A close queues the canonical issue it cites

## Why

The picker lists only issues labelled `agent:implement` (then `agent:ready`). The run-failure reactor
files its issues **with** that label, so those are the ones the bot sees — and when one of them is a
duplicate, the bot closes it and cites the canonical issue in prose, never labelling it. Measured on
`main` (`1d36673`), run `39806884507`:

```
[issue-implementer] picked #440: ci: CI / macos / top-tier failed
[agent] Verdict: TRIAGE: close
EVIDENCE: Open issue #399 tracks this exact failure: same job, same assertion …
[issue-implementer] closed #440 with cited evidence; labelled agent:closed
```

Right after that run: `#399` OPEN with **no labels**, `#254` OPEN with **no labels**, `#440` CLOSED
labelled `agent:closed`, `#466`/`#469` OPEN and labelled. So the loop runs: the reactor files a
labelled copy → the bot closes it as a duplicate of an unlabelled canonical issue → the canonical issue
is queued nowhere → the defect reproduces → another copy. `#400` was closed as a "flake" pointing at
`#254` two days earlier: the loop had already completed once and fixed nothing.

The canonical issue's root cause is concrete: `scripts/llgenie_serve.py::_hf_get` retries `HTTPError`
and `URLError` but not a mid-body-read `TimeoutError`, which is what reds `macos / top-tier`.

## What Changes

- **`apply_verdict`'s close path queues what the verdict cites.** `cited_issues()` pulls every `#<n>`
  from the `EVIDENCE:`/`REASON:` blocks; `queue_canonical()` reads each one with
  `gh issue view --json state,labels` and adds `agent:implement` to an issue that is **open** and
  carries **no** agent label. The current issue is excluded, and an already decided (`agent:refined` /
  `agent:closed`) or already queued one is left alone.
- **A cited number that is not a readable issue is skipped with a line**, never a crash: a verdict may
  cite a PR number, a typo or a deleted issue, and the close has already happened by then.
- **`--dry` prints the queueing decision** and issues no mutating request.
- `QUEUE_LABELS`, `ISSUE_REF`, `cited_issues()`, `_issue_meta()` and `queue_canonical()` are the named
  pieces, so the rule is testable without a network.

## Impact

- A duplicate close can no longer orphan the real work: the next run implements the canonical issue
  instead of closing the next copy.
- The bot's three daily runs stop being spent retiring copies of one unqueued defect.
- Nothing changes for an `implement` or `refine` verdict, and a close that cites no issue behaves
  exactly as before.
