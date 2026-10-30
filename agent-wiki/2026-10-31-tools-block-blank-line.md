# The tools block keeps a blank line before its heading

Issue #1119, PR #1121, OpenSpec change `tools-block-blank-line`. Complements issue #1038, whose
tool pin this generator writes, and #1116, whose fix commit this branch carries.

## What was measured

`scripts/host_bot_capabilities.py::tools_block()` rendered

```python
f"{MARKER_BEGIN}\n"
"## Tools\n"
```

so its output was `<!-- host-bot-tools:begin -->\n## Tools\n` — a markdown heading with no blank line
before it. `scripts/lint_linefeeds.py::_check_markdown_sections` rejects exactly that shape, and it
is the gate `make ci-lint` runs. Every one of the four committed blocks in the tree carries the
blank line:

- `.hermes/skills/llgenie-engine-improver/SKILL.md:14-16`
- `.hermes/skills/llgenie-architecture-pass/SKILL.md:14-16`
- `agents/llgenie-pr-reviever/skills/software-development/llgenie-pr-review/SKILL.md:17-19`
- `agents/llgenie-tester/skills/llgenie-pr-testing/SKILL.md:8-10`

So the generator was the outlier, and it was not merely wrong: `insert_tools_block()` replaces the
whole marker span, so regenerating a lane's block STRIPPED the blank line a green file already had.
The rebase lane hit this on 2026-10-30 and repaired its own file by hand on both sides.

## What changed

- The blank line is emitted (option (a) of #1119: it matches every committed block, so no file
  migration).
- `REPO_SKILL_PROFILES` + `profile_for_skill()` are the module's ONE map from a tree SKILL.md to the
  lane it belongs to; `apply_repo_skills()` reads it, and so does the test. A hand-kept second list
  in the test is what this avoids.
- `tests/test_host_bot_capabilities.py` gains two tests, and neither is an assertion added to an
  existing pass:
  - `test_the_rendered_block_is_byte_identical_to_every_committed_one` walks every SKILL.md in the
    tree that carries the marker, derives its lane, and asserts the rendered block equals the
    committed span byte for byte, and that re-running the generator over that file is a no-op.
  - `test_every_profile_renders_a_lint_clean_block` asserts, for all ten profiles in the fixture,
    that the REAL `lint_linefeeds` gate reports no bad heading in the block or in a file it is
    stamped into.

## Negative control

Stashing the one-line fix and running the two new tests against the pre-fix generator:

```
$ docker run --rm -u root -v "$PWD":/repo:rw -w /repo -e HOME=/root llgenie/test:latest \
    python -m pytest tests/test_host_bot_capabilities.py -q -p no:cacheprovider
FAILED tests/test_host_bot_capabilities.py::test_the_rendered_block_is_byte_identical_to_every_committed_one
FAILED tests/test_host_bot_capabilities.py::test_every_profile_renders_a_lint_clean_block
2 failed, 6 passed
```

The byte comparison prints the unified diff with the missing `-` (blank line) after the marker; the
lint test reports `assert [2] == []` — line 2 of the block, `## Tools`, for the first lane checked.

With the fix restored, the same command is `8 passed in 0.04s`, and `make ci-lint` prints
`LINT OK — all tracked text files end with a newline; markdown sections are blank-line separated.`

## Why the pass count was never the proof

On `main` this file has 6 test defs with zero blank-line assertions; the earlier fix commit added 7
assertion lines INSIDE an existing test, so "6 passed" read identical before and after. That is why
five PR heads could report the fix present with the file in none of their diffs (#1119's own
evidence). Two named tests that fail without the fix and pass with it replace that count.

## Status

Landed by this branch's PR only. No SKILL.md, config, or workflow file changes; a regenerating lane
now produces a byte-identical, lint-clean block.
