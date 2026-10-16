# Tasks

- [x] 1. Write the proposal + spec for the commit-author rule (issue #345).
- [x] 2. `scripts/check_pr_authors.py`: the guard — `check` / `report`, `commits_in_range`
      (`git rev-list --no-merges <base>..<head>`), `check_commits` (author + `Co-authored-by:`
      trailers), `check_producers` (the repo's own producers assign an allowed identity),
      `check_agents_mandate`, and `main(["check"])` returning non-zero on a violation.
- [x] 3. `tests/test_pr_authors.py`: the non-mocked suite — real git repositories in `tmp_path`, real
      identities via `git -c user.name=... -c user.email=...`, real merge commits, the real
      `git rev-list` output. 27 cases, one per spec scenario plus the spec-completeness case —
      **27 passed**.
- [x] 4. `Makefile`: `check-pr-authors` and `pr-authors-report` (PR_BASE/PR_HEAD bound the range),
      wired into `ci-unit` after `check-pr-hygiene`, declared in `.PHONY`, named in `make help`, and
      `tests/test_pr_authors.py` added to the `test-unit` file list.
- [x] 5. `AGENTS.md`: the durable section — the two allowed identities, the exact-name rule, the
      `Co-authored-by:` rule, the scope (merges and base commits out of scope), the remediation for a
      branch already authored off the allowlist, and the two make targets.
- [x] 6. `README.md`: document `check-pr-authors` / `pr-authors-report` — the command-list entry plus
      the rule and the scope it reads.
- [x] 7. `agent-wiki/2026-10-16-pr-commit-authors.md`: the work record naming issue #345 and the
      deferred #346.
- [x] 8. Put the repository's own producers on the allowlist: `fix-bot.yml`, `issue-bot.yml`,
      `rebase-bot.yml`, `engine-bump.yml`, `engine-bump-rebase.yml` and `registry-sync.yml` author as
      `Asimov Agent <support@docondee.com>`. The bump/sync pair keeps `BUMP_TOKEN` for the push and
      the PR, so #136 still holds — only the git AUTHOR is pinned, because `gh api user --jq .login`
      stamped the token owner's login. `test_engine_bump.py`'s two workflow cases assert the new
      property — **71 passed** in that file.
- [x] 9. Verify locally: `make check-pr-authors` exits 0 on this tree (its report shows all twelve
      producer identities `OK`); `tests/test_pr_authors.py` 27 passed; `tests/test_engine_bump.py` 71
      passed; `tests/test_pr_hygiene.py` + `tests/test_workflows_valid.py` + `tests/test_dispatch_forms.py`
      57 passed; and `make lint`, `make check-wiring`, `make check-docs`, `make check-pr-hygiene`,
      `make check-workflows`, `make check-dispatch-forms`, `make check-secret-output` and
      `make openspec-validate NAME=pr-commit-authors` all exit 0.
- [x] 10. Run `make test-unit` (the containerized suite `ci-unit` runs) and report its real result.
