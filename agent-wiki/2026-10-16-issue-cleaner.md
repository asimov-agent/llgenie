# 2026-10-16 — issue-cleaner: close the issues a merged PR already implemented

Issue: [#325](https://github.com/asimov-agent/llgenie/issues/325) · PR: _opened from `feat/issue-cleaner`_

## What was verified

GitHub closes an issue at merge only when the PR body carries a closing keyword bound to it. When it does
not, the PR merges and the issue stays OPEN. Measured on `main`: 13 of 38 merged PRs carried no closing
reference. The repo's own `make check-pr-hygiene` reads bodies and producers, so it cannot see this — the
linkage exists only at PR time.

First real catch, measured: **#256** was implemented by merged PR **#344** (`closingIssuesReferences: []`;
merge commit `6601051` opens with `Issue: #256`; title carries `(#256)`) and left OPEN by the merge. The
cleaner found it, posted the evidence and closed it (COMPLETED).

The distinction that makes the bot safe: #344's own `Not covered` section named **#339** (the product-code
half — `scripts/hf_auth.py` `hub_open` still re-raises on the first Hub 5xx) plus #340–#343. Those are
tracked remainders, and a bot that could not tell a remainder from a missed close would have closed work
still being tracked. The bot reports them as `remainder` and leaves them open.

## Key decisions

- **Three signals, strongest first**: `closingIssuesReferences`, then the merge commit's `Issue: #<n>`, then
  the title's trailing `(#<n>)`. The merge commit is the strongest statement a PR makes about what it
  implemented, and the repo's hygiene rule already requires that line.
- **`Not covered` is a boundary, not prose.** The section is parsed to the next heading so a remainder list
  cannot swallow an unrelated later section — verified by a test that puts a `## Follow-up` heading after it.
- **The bot joins the shared claim protocol** (#279) rather than inventing a second: `scripts/bot_claims.py`
  gains the `clean` verb and the `CLEANER` name, so it announces itself on the issue before mutating it.
- **The scan stays out of `ci-unit`** — it needs the API. Its tests stub `gh` on `PATH` and run in
  `make test-unit` with the rest of the hermetic suite.

## Status

Landing as a reviewable PR from `feat/issue-cleaner`; the merge is a reviewer's action. Deferred and tracked
elsewhere: #339 (the product-code retry) and the scheduled reporting job (#325's remaining scope).
