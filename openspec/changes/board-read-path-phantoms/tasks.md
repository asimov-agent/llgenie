# Tasks — board-read-path-phantoms

- [x] Write `scripts/pr_reconcile_guard.py`: read `pulls/<n>` via `gh pr view --json` (state,
      mergedAt, closedAt, mergeCommit, headRefOid, headRefName, mergeable, mergeStateStatus —
      `gh pr view` normalizes merged into the state word; `mergeCommit` is an object), print the
      one-line verdict `#<n> merged|closed, read-only …` or `#<n> open, actionable …`; exit
      non-zero (no verdict) when the read fails. Stdlib only.
- [x] Wire `make lane-reconcile-guard PR=<n> [REPO=…]` in `mk/bots.mk` + the Makefile target
      roster; register the module in `scripts/package-layers.json` ("Bots and automation"); record
      the host-only target in `tests/fixtures/host-only-wiring.json`; document it in `docs/BOTS.md`.
- [x] Tests `tests/test_pr_reconcile_guard.py` (fake-gh fixture, the `test_resolve_run_pr.py`
      pattern): merged → "merged, read-only" + merge sha; closed → "closed, read-only"; open →
      "open, actionable" + mergeStateStatus; failed read → non-zero, no verdict line.
- [x] Standing rule in `agents/standing-rules.md`: the reconcile trigger carries the state re-read —
      no reconcile action on a PR-numbered red before the guard verdict.
- [x] Board-read recipe text: planner `llgenie-bot-orchestration`, maintainer
      `llgenie-pipeline-maintenance` `verifying-planner-claims.md`, issse-implementer claim
      reading (`llgenie-issue-to-pr`) — merged rows get the guard verdict, act only on
      `open, actionable`. Sync each touched profile with `make sync-agent-profile`.
- [x] Live proof: `make lane-reconcile-guard PR=1742` and `PR=1743` both print
      `merged, read-only` (record the run output as the AC evidence).
- [x] Final alignment check: the issue #1749 body, the PR body, and the commit text carry the same
      ticked acceptance items with replayable proven clauses at the final head, and the PR closes
      #1749 — tickable only once all three mirror each other.
