# leave-open-issue-on-open-pr — Tasks

Issue: [#2869](https://github.com/asimov-agent/llgenie/issues/2869)

- [x] 1. `scripts/issue_implementer.py`: add the `hold` verdict to `VERDICTS`, the machine-read
      decision block, `parse_verdict` (`PR:` block) and `apply_verdict` — a hold abandons the
      lane's own claim (`bot-done: … held`) and posts ONE hold comment naming the PR without
      closing the issue or labelling `agent:closed`; a hold with no `PR:` is refused. Verified:
      `tests/test_issue_implementer.py` hold tests green at `make test-unit`.
- [x] 2. `scripts/bot_claims.py`: add `held` to `DONE_RELEASES` so the claim protocol
      recognises the release a hold posts. Verified: `tests/test_bot_claims.py` green.
- [x] 3. Lane skill texts name the two close reasons and the leave-open rule, and teach the
      `hold` verdict: `agents/llgenie-planner/skills/github-issue-triage/SKILL.md` +
      `.hermes/skills/issue-triage/SKILL.md`. Verified: `make check-agent-skills` OK.
- [x] 4. `scripts/issue_close_backfill.py` + `make issue-close-backfill`: a read-only report of
      every bot-closed `not_planned` issue a MERGED PR closes, flagged `NEEDS-CORRECTION`, with
      an already-corrected issue (e.g. #2048) reported as corrected. Verified:
      `tests/test_issue_close_backfill.py` green; `make check-wiring` / `make check-docs` OK.
- [x] 5. `docs/BOTS.md`: document the `hold` verdict and the `issue-close-backfill` target.
      Verified: `make check-docs` OK.
- [x] 6. Final task — every gate green: `make openspec-validate NAME=leave-open-issue-on-open-pr`
      exits 0, all tasks ticked, `make test-unit` (hermetic) passes with the new lane coverage,
      `make lint` and `make check-wiring` and `make check-docs` green at the change head.
