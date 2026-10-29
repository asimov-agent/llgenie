# Tasks

- [x] 1. `scripts/bot_verdict.py`: the marker `<!-- bot-verdict: head=<sha> verdict=<approve|changes> reviewer=<login> -->`, its parser, the trusted-author + no-impersonation rule, `post` (full-40-hex only, unknown verdict refused, deduped per head+verdict) and `show`
- [x] 2. `scripts/auto_merge.py`: `pr_state` reads `comments` with the head in one snapshot; `decide()` clears `BLOCKED`+`REVIEW_REQUIRED` only on a verdict at the CURRENT `headRefOid`; a `changes` verdict at the head holds; `_merge_review_cleared` merges with `--admin` and turns a refusal into a deferral; `explain()` prints the verdict
- [x] 3. `Makefile`: `bot-verdict` and `bot-verdict-read` targets, both in `.PHONY`, one code path (the script)
- [x] 4. `docs/BOTS.md`: the rule — a bot review is a verdict comment, never an approval, and no second identity
- [x] 5. Tests: stale-sha refused, current-sha accepted and merged, untrusted/impersonating author refused, `changes` holds, marker round-trip/dedupe/refusals, and the allowlist cannot drift from `auto_merge`
- [x] 6. Falsified: with `verdict_for_head` ignoring the head, both the parser test and the stale-verdict merge test fail (a stale verdict would merge unreviewed code); with `on.workflow_run` replaced by `workflow_dispatch`, the issue-#874 automatic-trigger guard fails; both restored
- [x] 7. `agent-wiki/2026-10-29-bot-verdict-legible.md` + its `docs/changes.d/` fragment, `CHANGES.md` rendered by `make changes-index`
- [x] 8. Gates: `make test-unit`, `make openspec-validate NAME=bot-review-verdict`, `make check-docs`, `make check-wiring`, `make check-workflows`, `make lint` exit 0
