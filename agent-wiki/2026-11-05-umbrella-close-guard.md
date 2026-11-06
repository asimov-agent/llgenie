# Squash-text umbrella-close guard (#1815)

GitHub's native close-on-merge reads the **squash commit text**, not just the PR body. The
merge-time issue-state gate `make check-pr-acceptance` (issue #1792) derived its linked-issue
set **only from the PR body** (`closing_references(body)`), so a lane whose squash commit message
carries an adjacent `(closes #N)` on a multi-lane rollout umbrella was never held to that umbrella's
`## Acceptance criteria` — and GitHub's native close COMPLETEd the umbrella while it measured
**0/5 ticked, 1/3 lanes merged**.

Measured instance (2026-11-05): #1813's squash `agents(pr-merge-conflict): … (closes #1812) (#1813)`
auto-closed #1812 as COMPLETED at 21:15:01Z; the planner reopened it at 21:17:59Z (comment
`6669797855`). Root cause: the `CLOSING` regex has no purpose-awareness of a rollout umbrella and no
negation awareness, and a GitHub-native close on merge bypasses every CI verdict — the gap #1811's
silent-verification fix does not cover.

## What changed

`scripts/check_pr_acceptance.py` now derives the linked-issue set from **both** the PR body and,
when `--base`/`--rev` are supplied, the joined squash commit messages (#1815):

- a close that lives **only in the squash text** is now in the held set — an unticked rollout
  umbrella is RED at merge time (the merge is blocked until umbrella-safe);
- the close parse is **negation-aware**: `does not close #N`, `won't close #N`, `can't close #N`,
  `never close #N`, `without closing #N` are NOT closes, so a lane can name an umbrella without
  triggering the prior premature-close hold;
- a squash-only close is named on-record (`squash-only-close`) in `report` so the mechanism is
  visible, while the actual hold stays `acceptance_verdict` on the unticked criteria.

Wiring: both guard workflows (`ci.yml`, `scope.yml`) pass the live squash range to the make target
(`PR_BASE: origin/main`, `PR_HEAD`, `git fetch --no-tags --prune origin main` — the same live read as
`check-pr-closing`, issue #1589).

Verification only: the gate never ticks a box — that stays `acceptance_writeback.py`'s verdict-gated
seam (issue #1644).

## Why it is not a weakening

`check-pr-acceptance` (#745/#1792) still holds on verified criteria, unchanged. This change only
makes the gate **see more closes** (the ones GitHub itself acts on from the squash text) and be
**negation-aware**, so a deliberate "does not close #N" is respected. The designed hold on an
unticked rollout umbrella is the gate working, not a new red to route around.

## Proof

Prove-the-guard (`tests/test_check_pr_acceptance.py`): 5 new tests are RED against the pre-fix
script (`AttributeError` on the new helpers and `unrecognized arguments: --base` on the CLI) and
GREEN against the fixed script; the suite counts 17 passed (acceptance) / 47 passed (acceptance +
closing), and the full `make test-unit` runs green at the committed head.

