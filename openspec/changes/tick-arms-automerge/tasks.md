# Tasks — tick arms auto-merge (issue #2182)

- [x] `tick_board.sh` section B requests `autoMergeRequest`,`reviewDecision` in the `gh pr list --json` field list and classifies the four arm states
- [x] Section B prints the `ARM armed=N unarmed=N armed-but-DIRTY(inert)=N` summary and the rule that an inert arm is impossible, never handled
- [x] Version `arm_pr.sh` — one mechanical arm: classify, arm only green+approved+unarmed, refuse a live-run/mid-rebase head, read `autoMergeRequest` back after `gh pr merge --auto` (#964: exit code is never proof), route inert arms to `llgenie-pr-merge-conflict`
- [x] Keep the versioned prompt step 4d/4e/4f byte-identical to the live jobs.json (the arming step already landed via #2159)
- [x] Hermetic tests: `tests/test_tick_board_arm.py` (four states + known-armed regression) and `tests/test_arm_pr.py` (#964 read-back, #2069 live-run refusal, dry-run)
- [x] Docs trio (`agent-wiki/`, `docs/changes.d/`, CHANGES.md) naming #2182
