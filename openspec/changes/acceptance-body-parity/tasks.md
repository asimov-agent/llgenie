# Tasks: acceptance-body-parity

- [x] 1. Add the `acceptance-body-lag` finding to `acceptance_verdict` in `scripts/check_pr_acceptance.py` (canonical-section scope, `## Not covered` exemption).
- [x] 2. Tests: five new states in `tests/test_check_pr_acceptance.py` (lag RED, mirror GREEN, exemption GREEN, out-of-section GREEN, no-section GREEN) — targeted pytest 58 passed rc=0; sibling suites `test_acceptance_writeback.py` + `test_pr_body_acceptance_gate.py` + `test_pr_hygiene_acceptance_form.py` 24 passed rc=0.
- [x] 3. Retro-fix the four measured merged bodies (#2507 #2498 #2496 #2490) with `gh pr edit`; re-audit: live bodies carry 0 `- [ ]` acceptance boxes each (regex recount 2026-11-11); `make check-pr-acceptance PR_BODY=<live body> PR_NUMBER=<n>` rc=0 for all four.
- [x] 4. Live replay before the retro-fix: `make check-pr-acceptance PR_BODY=/tmp/prbody2507.md PR_NUMBER=2507` → 2 blocking `acceptance-body-lag` findings, gate Error 1; same command after the fix → `[check-pr-acceptance] OK` rc=0.
- [x] 5. Companion issue #2512 filed (AGENTS.md section drafted, needs consented protected-file approval); issue #2511's body re-rendered via `scripts/issue_body.render` naming #2512 under `Not covered`.
- [ ] 6. Docs trio (agent-wiki + changes.d fragment) + `make changes-index` + `make check-docs` rc=0; `make openspec-validate NAME=acceptance-body-parity` rc=0.
- [ ] 7. Full gates at the final head: `make test-unit`, `make check-wiring`, `make check-workflows`, `make lint` rc=0; `make lane-preflight` OK.
- [ ] 8. Push `feat/acceptance-body-parity`, open the PR with its body fully ticked (proven lines at the head sha), drive CI green.
