# Proposal: reviewer-finding-dedupe

## Why

`scripts/code_review.py` files one issue per finding with idempotence only from its own
`<!-- code-review:<key> -->` marker. It never consults open pull requests, so a finding whose fix is
already in an open PR is filed as a fresh issue: the maintainer gets an issue and a PR for the same
line (measured: it filed #270 while PR #277 changed that exact line — issue #293's evidence).

## What Changes

- `code_review.py`'s `file` run fetches the repo's open PRs with their changed files once
  (`gh pr list --state open --json number,files`, via the existing soft-gh helper — a refused read is
  a loud WARNING and the run proceeds as before).
- Before filing each finding (after the existing marker check), the finding's named files (its `where`
  value, str or list) are matched against the open-PR file map; a hit is NOT filed and the run prints
  `already in flight: PR #N (<file>)` — the decision is visible in the run's output.
- Marker dedupe is unchanged; a finding re-appears on a later run once the PR closes without the fix.
- `tests/test_code_review.py` fake-gh gains a `pr list` branch; new tests pin both directions:
  open PR touching the file -> not filed + reported; no open PR -> filed.

## Impact

- Affected spec: `ci-code-review-bot` (ADDED requirement)
- Affected code: `scripts/code_review.py`, `tests/test_code_review.py`
- No workflow, engine, or destructive behaviour changes.
