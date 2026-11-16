# Tasks

- [x] `scripts/pr_body_write.py`: `body_preserve_findings(live, proposed)` names live headings/ticked `(proven:` lines the proposal drops.
- [x] `scripts/pr_body_write.py`: `write_body(repo, pr, new_file)` reads the live body through `gh`, skips a dropping write (log + PR comment naming the section), writes nothing when equal, and reaches `gh pr edit` only for a preserving rewrite.
- [x] `make bot-body-write PR= REPO= NEW=` with its `## help` line, usage guard and `.PHONY:` entry.
- [x] `.github/workflows/fix-bot.yml`: the re-stamp step hands the stamped body to `make bot-body-write` instead of calling `gh pr edit --body-file`.
- [x] `tests/test_pr_body_write.py`: refusal + skip-comment, preserving rewrite writes, identical body writes nothing, fix-bot wiring — with `gh` stubbed on PATH.
- [x] `docs/BOTS.md` documents `make bot-body-write` and records the #2131 finding.
- [x] `agent-wiki/2026-11-16-fix-bot-body-write-guard-2131.md` naming #2131 + a `docs/changes.d` row.
- [x] `make test-unit` exits 0 at the branch head.
- [x] `make lane-preflight` exits 0 and `make openspec-validate NAME=fix-bot-body-write-guard` exits 0.
