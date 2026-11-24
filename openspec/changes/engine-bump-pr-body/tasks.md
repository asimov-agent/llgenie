# Tasks

- [x] 1. `scripts/engine_bump_pr_body.py` — the ONE composer of the engine-bump PR body and of its
      commit-text acceptance mirror: sections joined through a list, the `OPENSPEC:` line last with
      nothing after the change name, the ticked checklist provable through
      `check_pr_acceptance._is_provable_tick` (proven: `pytest tests/test_engine_bump_pr_body.py` rc=0, 13 passed)
- [x] 2. `make engine-bump-pr-body` in `mk/engines.mk` — ENGINE/REF/OLD/NEW/RUN/OUT required,
      COMMIT_OUT/AUTHOR/REPO_SLUG/REVIEW_FILE/HARD_FAIL/DEPS optional, no raw script call from the workflow
      (proven: `make -n engine-bump-pr-body ENGINE=ollama …` rc=0)
- [x] 3. `.github/workflows/engine-bump.yml` — the bump job's "Open / update the bump PR" step renders the
      body through the make target and passes the mirror as a commit-message paragraph; the inline
      `printf`/`$(cat params-review-section.md)` composition is gone
      (proven: `pytest tests/test_engine_bump_pr_body.py -k 'wired_through_make or composer_is_gone or valid_bash'` rc=0)
- [x] 4. `scripts/check_pr_hygiene.py::_openspec_detail` — the OpenSpec-presence finding names the shape it
      saw: a line that does not parse, a name that is not an ACTIVE change, or no line at all
      (proven: `pytest tests/test_pr_hygiene_openspec_change.py` rc=0, 15 passed)
- [x] 5. `tests/test_engine_bump_pr_body.py` rewritten to the new seam: the bash-slice tests of issues
      #144/#583 keep their meaning (real newlines, hard-fail paragraph, dependency line, `bash -n` on the
      step) and the #3050 regressions are pinned (glued reference, acceptance form, commit mirror)
      (proven: `pytest tests/test_engine_bump_pr_body.py` rc=0, 13 passed)
- [x] 6. The suites that read the bump workflow or these gates stay green: `tests/test_engine_bump.py`,
      `test_engine_bump_companions.py`, `test_engine_bump_rebase.py`, `test_engine_params_review.py`,
      `test_workflows_valid.py`, `test_pr_hygiene.py`, `test_ci_discipline.py`, `test_dispatch_forms.py`,
      `test_bot_stamp_body.py`, `test_bot_body_write_fleet.py`, `test_hf_auth.py`,
      `test_strata_check_hermetic.py`
      (proven: `pytest` on those files rc=0, 265 passed)
- [x] 7. `make openspec-validate NAME=engine-bump-pr-body` exits 0
- [x] 8. The gates run on the tree the PR carries: `make test-unit` is green on the committed tree
      (proven: `make test-unit` rc=0, 4425 passed, 0 failed) and the fast lane gates `lint`,
      `check-workflows`, `check-wiring`, `check-docs`, `check-pr-hygiene` and `check-package-layers`
      print OK on that same tree (proven: `make lane-preflight` prints `preflight: OK`)
