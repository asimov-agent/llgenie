# Tasks

## The ancestor exemption in the gate

- [x] 1.1 `scripts/check_pr_base.py::check` passes when `base..rev` is empty (the head is an
      ancestor of the live base), refusing only on a non-empty foreign diff.
- [x] 1.2 `render` names the ANCESTOR exemption in its OK verdict (auditable, distinct from a
      clean cut).

## Guard proves the catch

- [x] 2.1 Ancestor/push-to-main case passes (RED on old tree, GREEN on fix) —
      `test_a_pushed_main_commit_overtaken_by_a_newer_main_passes` reproduces
      `merge-base != base`, foreign (0) on the OLD code; GREEN on the new code.
- [x] 2.2 A genuine #845 foreign-commit leak still FAILS and names the foreign commit
      (`test_a_foreign_commit_fails_and_is_named`, unchanged).
- [x] 2.3 A clean one-commit-ahead branch still PASSES (`test_a_clean_one_ahead_branch_passes`,
      unchanged).
- [x] 2.4 The whole `tests/test_check_pr_base.py` file passes (8 tests).

## Note trio + gate hygiene

- [x] 3.1 `agent-wiki/2026-11-07-*.md` note references the issue and the PR (check-docs).
- [x] 3.2 `docs/changes.d/2026-11-07-*.md` fragment + `CHANGES.md` row via `make changes-index`
      (check-docs).
- [x] 3.3 `make openspec-validate NAME=ci-check-pr-base-ancestor-push-exempt` passes.
- [x] 3.4 `make lane-preflight` green.
