# Tasks: bot-stamp-roster-2110

- [x] `architecture_bot.publish` stamps through `bot_preflight.stamp_body` with a `resolve_record(root)` record; `_hygiene_lines` deleted; the `--dry` preview body is stamped too
- [x] `publish` resolves the record before any issue/branch/commit/GitHub write and refuses naming the refs tried when no `main` ref resolves (test with a ref-less checkout and a call-recording fake gh)
- [x] `test_bot_stamp_body` derives the producer roster from the tree (python call-form scan + workflow non-comment scan) and proves a synthetic unstamped module is named (scratch-tree negative control)
- [x] `test_architecture_bot` measures the gate: stamped publish body → `pr_agents_line_findings` verdict `[]`; pair stripped → `agents-line`
- [x] `docs/BOTS.md` names the architecture bot beside the stamped producers, with its agent-wiki note + `docs/changes.d/` row
- [x] Replay the suite in the container (focused + full `make test-unit`) at the lane head, rc=0
- [x] `make openspec-validate NAME=bot-stamp-roster-2110` exits 0
- [x] The commit carries the ticked AC mirror + `closes #2110`; `make lane-preflight` prints preflight: OK
