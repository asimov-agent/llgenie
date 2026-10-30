# host-bot-capabilities

## ADDED Requirements

### Requirement: The tools block matches the committed form and the lint gate

`tools_block(spec, profile)` SHALL be byte-identical to the `host-bot-tools` block every committed
SKILL.md in this tree carries for that profile, for every profile the tree carries a block for, and
it SHALL carry no markdown heading that `scripts/lint_linefeeds.py` rejects for every profile named
by `tests/fixtures/host-bot-capabilities.json`.

`insert_tools_block(text, tools_block(spec, profile))` SHALL be a no-op on a file whose block was
rendered by that same function: the marker span is replaced whole, so any shape difference strips a
line the file needs.

WHEN a lane regenerates its tools block
THEN the file it writes is unchanged when it was already in the generated form, and `make ci-lint`
stays green.

#### Scenario: the rendered block is the committed block

Given every SKILL.md in this tree that carries the `host-bot-tools` marker
When `tools_block()` renders that profile's block from the fixture
Then the rendered text equals the committed span byte for byte.
And re-running `insert_tools_block()` over the file returns the file unchanged.

- **Test:** `tests/test_host_bot_capabilities.py::test_the_rendered_block_is_byte_identical_to_every_committed_one`

#### Scenario: a regenerated block is lint-clean for every lane

Given the ten profiles in `tests/fixtures/host-bot-capabilities.json`
When each lane's block is rendered and stamped into a skill
Then `lint_linefeeds._check_markdown_sections` reports no heading for the block itself
And it reports no heading for the stamped file.

- **Test:** `tests/test_host_bot_capabilities.py::test_every_profile_renders_a_lint_clean_block`

#### Scenario: the pre-fix generator fails this requirement

Given the generator from before this change, which rendered the marker directly above `## Tools`
When the two tests above run
Then both fail — the byte comparison names the missing blank line
And the lint check names line 2 of the generated block.

- **Test:** `tests/test_host_bot_capabilities.py::test_the_rendered_block_is_byte_identical_to_every_committed_one` and `tests/test_host_bot_capabilities.py::test_every_profile_renders_a_lint_clean_block` (measured red on the pre-fix generator: `2 failed, 6 passed`)
