# Tasks

- [x] Add `check_completeness()` to `scripts/check_pr_closing.py`: a resolvingly-named issue that is neither adjacent-closed nor on-record justified-open is `close-set/<n>` RED.
- [x] `closing_references()` strips a negated close clause so it is not an adjacent close; the squash/body close-set comparison reads matching sets.
- [x] `NOT_CLOSED` honours first- and third-person on-record justifications in the repo's own voice (`We do not close #1582 because …`).
- [x] `RESOLVING` excludes `clos(e|es|ed|ing)` forms so narrating an already-closed issue is not a resolving claim (pure-text guard, not tracker-state).
- [x] Wire `check_completeness` into `check_squash` (commit text + supplied body) and `check_body` (agent-head body surface).
- [x] Regression tests in `tests/test_check_pr_closing.py` for each hardened shape (both directions).
- [x] `make check-pr-closing` rc=0 on the change's own PR body + squash text; the package unit suite stays green.
- [x] Docs trio per #1123: `agent-wiki/` + `docs/changes.d/` fragment + `CHANGES.md` regenerated.
