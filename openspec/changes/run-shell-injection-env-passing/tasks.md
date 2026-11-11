# Tasks — run-shell-injection-env-passing (#2505)

- [x] 1. Create this OpenSpec change (`make openspec-new NAME=run-shell-injection-env-passing`)
- [x] 2. Rewrite all 4 flagged `run:` sites to env-passing values
- [x] 3. `make check-workflows` exits 0 (re-verified at final head `6ce4513cb`: rc=0, log /tmp/cw2505e.log)
- [x] 4. `make security-scan TOOL=semgrep` reports zero `run-shell-injection` findings in the four files at this head (negative control: the same image+ruleset reports exactly 4 on the pre-fix copies; head re-scan at `6ce4513cb` rc=0: 502 rules on 5294 files, 44 findings, 0 run-shell-injection, log semgrep2505e.log)
- [x] 5. `make test-unit` is green (rc=0 at head `6ce4513cb`: 3624 passed, 0 failed, 13201 deselected in 1150s, log testunit2505d.log)
- [x] 6. Docs trio: `docs/changes.d/` fragment + `CHANGES.md` + `agent-wiki/` entry (`make changes-index` rc=0 and `make check-docs` rc=0 at head `6ce4513cb`)
- [x] 7. Final verification: `make openspec-validate NAME=run-shell-injection-env-passing` rc=0 (log /tmp/ov2505e.log) and `python3 scripts/check_pr_acceptance.py check --body-file <PR body>` replays rc=0 against the body carrying `closes #2505` (replayed at head `1e79d040f`, code-identical to the pushed head except this checklist)
