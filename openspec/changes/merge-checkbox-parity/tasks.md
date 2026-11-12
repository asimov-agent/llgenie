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
- [x] 6. Docs trio: `agent-wiki/2026-11-12-merge-checkbox-parity-2519.md` +
      `docs/changes.d/2026-11-12-merge-checkbox-parity-2519.md` + `CHANGES.md` row.
- [x] 7. Gate evidence measured (2026-11-12, head `a59b9563c`):
      `make openspec-validate NAME=merge-checkbox-parity` rc=0; the #2509 commit text (`49f0cc3be`,
      3 unticked acceptance boxes, 0 ticked mirror) replayed through `check_pr_hygiene.py
      commit-checkboxes --head 49f0cc3be --base 49f0cc3be^` is RED rc=1 naming the squash-shape;
      the current main heads `d8700c60e` (#2516) and `aa700cf27` (#2517) replayed with their PR
      bodies are both rc=0 carrying the ticked mirror. Unit tally for this head: CI run
      43175752662 `linux / unit` = 1 failed, 3646 passed — the sole failure is the fleet-publish
      gate `test_every_image_install_pulls_is_published` (unpublished engine images, issue #169
      fleet state under the #2529 dispatch wave), not this change's files.
- [x] 8. PR staging verified: branch carries the implementation + the tasks-tick commit; the
      staged PR body (#2558, upstream base) references #2519 with ticked AC items carrying
      `proven:` evidence and the AGENTS/BASE stamp; `make lane-preflight` rc=0 on the final head
      before push. Driving CI fully green (after the fleet wave lands), mergeStateStatus CLEAN
      and the auto-merge arm are the CI follow-through recorded in the agent-wiki entry.
