# Tasks: merge-checkbox-parity

- [x] 1. `scripts/check_pr_hygiene.py`: add `commit_text_findings(messages, body)` (pure: flags
      `commit-unchecked-acceptance` for `- [ ]` under an acceptance heading, and
      `commit-acceptance-unmirrored` when the body's `acceptance_items` count exceeds the `- [x]`
      boxes in the joined text), a git-range wrapper `commit_checkboxes_findings(root, head, base,
      body)` gated on `is_bot_pr`, and the `commit-checkboxes` subcommand with optional
      `--body-file` (empty body = commit-side rule only).
- [x] 2. `scripts/auto_merge.py`: gate `_merge()` — fetch the PR's live commit messages
      (`gh api pulls/<n>/commits --paginate`) + live body, run `commit_text_findings`; on findings
      defer with the reason (`defer(...)`, exit 0), never merge, never red.
- [x] 3. Wiring: `mk/gates.mk` target `check-pr-commit-checkboxes`, classification in
      `scripts/issue_bot_gates.py::DEFERRED` with a reason (FAST_GATES is the fixed #475 list), and
      the live-body guard step in `.github/workflows/ci.yml` beside `check-pr-agents-line`.
- [x] 4. `tests/test_pr_hygiene_commit_checkboxes.py`: real-git fixtures covering the spec
      scenarios (unticked acceptance text RED; ticked mirror GREEN; missing mirror RED;
      human-only range skipped; merge-lane deferral via the pure seam).
- [x] 5. AGENTS.md: durable mandate section (three mirrors, one tick, closing is the single
      automatic act, commits end with a ticked `Acceptance:` block) + add the new gate to the
      lane-preflight FAST-gate roster text.
- [ ] 6. Docs trio: `agent-wiki/2026-11-12-merge-checkbox-parity-2519.md` +
      `docs/changes.d/2026-11-12-merge-checkbox-parity-2519.md` + `CHANGES.md` row.
- [ ] 7. Gates green: `make openspec-validate NAME=merge-checkbox-parity`, `make test-unit`,
      `make lane-preflight`; replay the measured #2509 commit text through the new subcommand and
      show it RED; replay the current #2516/#2517 heads and show what they must carry.
- [ ] 8. Push, open PR against upstream `main` referencing #2519, drive CI green, verify
      mergeStateStatus CLEAN, checkboxes ticked in issue + PR + commits before arming.
