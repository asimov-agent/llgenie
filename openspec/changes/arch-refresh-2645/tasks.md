# Tasks — arch-refresh-2645

- [x] `scripts/architecture_bot.py` issues the issue-body PATCH as `gh api --method PATCH` (no positional verb), with the why recorded at the call site
- [x] `tests/test_architecture_bot.py` fake-gh + call-order assertion lock the flag-form call shape
- [x] new test `test_no_gh_api_call_carries_a_positional_verb` scans the bot module and fails any positional verb in a `gh api` call
- [x] focused replay of `tests/test_architecture_bot.py` is green in the test container at the lane head (20 passed rc=0; new test 1 passed rc=0)
- [x] measured against real gh 2.103.3: positional `gh api PATCH <endpoint>` fails (`accepts 1 arg(s), received 2`); `gh api --method PATCH` parses and dispatches
- [x] `docs/ARCHITECTURE.md` regenerated through the sanctioned legs (`make architecture-bot-brief`, then `make architecture-bot-doc` — Hermes inside the agent image, only the doc writable)
- [x] the refresh pair is paid: `agent-wiki/` note, `docs/changes.d/` row, rebuilt `CHANGES.md`, and `make check-docs` green
- [x] `make openspec-validate NAME=arch-refresh-2645` exits 0
- [x] issue #2645 body, PR body, and commit text carry the identical ticked acceptance block (issue body read back at 21:23Z with 4 ticked items; PR #2648 body posted from the same file)
- [x] `make lane-preflight` prints `preflight: OK` on the pushed tree
- [x] full unit battery (`make test-unit`) exits 0 at the final squashed lane head (rc=0, 3766 passed, 13201 deselected, 19:46)
