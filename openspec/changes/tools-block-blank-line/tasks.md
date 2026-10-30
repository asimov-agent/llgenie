# Tasks

- [x] 1. `tools_block()` emits a blank line after `MARKER_BEGIN`, matching every committed block in the tree (issue #1119, option (a)).
- [x] 2. `REPO_SKILL_PROFILES` + `profile_for_skill()` give the applier and its test one map from a tree skill to its lane; `apply_repo_skills()` reads it.
- [x] 3. `test_the_rendered_block_is_byte_identical_to_every_committed_one` compares the rendered block with every committed block in the tree and asserts a re-run is a no-op.
- [x] 4. `test_every_profile_renders_a_lint_clean_block` asserts the real `lint_linefeeds` gate accepts the block, and the stamped file, for every profile in the fixture.
- [x] 5. Negative control measured: against the pre-fix generator the two new tests fail (`2 failed, 6 passed`), naming the missing blank line and line 2 of the block; with the fix they pass (`8 passed`).
- [x] 6. `make ci-lint` green (`LINT OK — all tracked text files end with a newline; markdown sections are blank-line separated.`).
- [x] 7. The dated note in `agent-wiki/` and its `docs/changes.d/` row name issue #1119, and `make openspec-validate NAME=tools-block-blank-line` exits 0.
