# Tasks

## The stale-but-clean discriminator in the gate

- [x] 1.1 `scripts/check_pr_base.py::check` returns a distinct `stale` verdict when the merge-base
      IS a `main` ancestor AND every commit in `base..rev` is reachable only from the base or the
      head's own branch (no commit belongs to another ref).
- [x] 1.2 `render` emits the distinct "rebase onto a fresh origin/main" message for a stale verdict
      — never the #845 "carries commits from another PR" accusation — and the CLI exits 0 (gate
      passes, walking legs not cancelled).
- [x] 1.3 A genuine #845 leak still FAILS with the original message (foreign commit reachable from
      another ref → named; merge-base off main → named). `tests/test_check_pr_base.py` RED on old
      / GREEN on fix for the stale case; the foreign + clean-one-ahead controls unchanged.

## Proving the guard catches the cases

- [x] 2.1 `test_a_stale_but_clean_branch_passes_with_distinct_message`: branch cut from an OLDER
      main, only its own commit — exits 0, message says "rebase onto a fresh origin/main", no #845
      accusation. RED on the old tree (merge-base != base → foreign red), GREEN on the fix.
- [x] 2.2 `test_a_foreign_commit_fails_and_is_named` unchanged (genuine leak still reds).
- [x] 2.3 `test_a_clean_one_ahead_branch_passes`, `test_a_missing_base_ref...`,
      `test_a_fetch_failure...`, `test_stale_local_main...`, `test_the_cli_exits...`,
      `test_a_pushed_main_commit...` all pass unchanged.
- [x] 2.4 Real-tree gate check: `python3 scripts/check_pr_base.py check --base origin/main --rev
      <#1969-head>` now reports STALE/rebase (exit 0) where it previously reported #845 foreign.

## Review-pass classification (criterion 3)

- [x] 3.1 This lane's own-domain audit reference / dispatch-protocol note gains the stale-vs-foreign
      distinction ("code green, stale base, rebase owed") so a stale-but-clean red is a verdict,
      not a stand-down.
- [x] 3.2 Reviewer skill's "own-gate red = not a review target" is annotated with the stale-exception.

## Note trio + gate hygiene

- [x] 4.1 `agent-wiki/2026-11-07-ci-check-pr-base-stale-clean-attribution.md` references the issue
      and the PR (check-docs).
- [x] 4.2 `docs/changes.d/2026-11-07-ci-check-pr-base-stale-clean-attribution.md` fragment +
      `CHANGES.md` row via `make changes-index` (check-docs).
- [x] 4.3 `make openspec-validate NAME=ci-check-pr-base-stale-clean-attribution` passes.
- [x] 4.4 `make lane-preflight` green.
