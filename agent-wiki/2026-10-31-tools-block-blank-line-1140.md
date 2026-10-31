# The host tools block keeps a blank line before its heading; stamp through ONE skill map (issue #1140)

## Why
`scripts/host_bot_capabilities.py::tools_block()` rendered `MARKER_BEGIN` immediately followed by
`## Tools` — no blank line before the heading. `scripts/lint_linefeeds.py` (the `make ci-lint` gate)
fails exactly that shape, while every committed block in the tree carries the blank line
(`.hermes/skills/llgenie-engine-improver/SKILL.md`, `agents/llgenie-tester/skills/llgenie-pr-testing/SKILL.md`,
etc.). Because `insert_tools_block()` replaces the whole marker span, a lane regenerating its block
did not merely emit a wrong shape — it **stripped** the blank line a green file already had and
redded `make ci-lint` (the rebase lane hit this on 2026-10-30 and hand-repaired both sides).

Separately, `apply_repo_skills()` maintained an inline two-entry profile→path map while the tree's
marker-carrying skills grew to twelve, so a block could be stamped for one lane even as the tests
checked another — there was no single source of truth from a tree `SKILL.md` to its lane.

## What changed
1. **`tools_block()`** emits a blank line after `MARKER_BEGIN` (option (a) of #1119), matching every
   committed block byte-for-byte with no file migration.
2. **`REPO_SKILL_PROFILES` + `profile_for_skill()`** become the module's ONE map from a tree
   `SKILL.md` (repo-relative) to its host lane. `apply_repo_skills()` now reads the same map the
   block-identity test walks — so stamp and test cannot disagree, and there is no second hand-kept list.
3. **Two named tests** replace the earlier untracked assertion lines:
   - `test_the_rendered_block_is_byte_identical_to_every_committed_one` walks EVERY marker-carrying
     `SKILL.md` in the tree, derives its lane via `profile_for_skill()`, and asserts the rendered
     block equals the committed span byte-for-byte and that re-stamping is a no-op.
   - `test_every_profile_renders_a_lint_clean_block` asserts, for all ten fixture profiles, that the
     real `lint_linefeeds._check_markdown_sections` reports no bad heading in the block or in a file
     it is stamped into (rooted `from scripts import lint_linefeeds`).

## Verified
Bug-plant proof: removing the blank line makes both new tests RED (byte-identity mismatch + lint
names the heading), restoring it makes them GREEN — they catch exactly this defect. `make ci-lint`
reports `LINT OK … markdown sections are blank-line separated` on the full tracked set.
`tests/test_host_bot_capabilities.py` (8) and `+ tests/test_bot_pipeline_isolation.py` (16) pass in
the container. `check_pr_authors` green; the import-roots ratchet stays at 52.
