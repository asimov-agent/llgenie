# Tasks — run-shell-injection-env-passing (#2505)

- [x] 1. Create this OpenSpec change (`make openspec-new NAME=run-shell-injection-env-passing`)
- [x] 2. Rewrite all 4 flagged `run:` sites to env-passing values
- [ ] 3. `make check-workflows` exits 0 (rc=0 measured at the edit; re-verify at the final head)
- [x] 4. `make security-scan TOOL=semgrep` reports zero `run-shell-injection` findings in the four files at this head (negative control: the same image+ruleset reports exactly 4 on the pre-fix copies)
- [ ] 5. `make test-unit` is green
- [ ] 6. Docs trio: `docs/changes.d/` fragment + `CHANGES.md` + `agent-wiki/` entry (`make changes-index`, `make check-docs` rc=0)
- [ ] 7. Final verification: `make openspec-validate NAME=run-shell-injection-env-passing` rc=0 and `python3 scripts/check_pr_acceptance.py check --body-file <PR body>` replays rc=0 against the body carrying `closes #2505`
