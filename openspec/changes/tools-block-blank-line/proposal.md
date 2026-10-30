# The tools block keeps a blank line before its heading

## Why

`scripts/host_bot_capabilities.py::tools_block()` rendered the marker immediately followed by
`## Tools`:

```python
f"{MARKER_BEGIN}\n"
"## Tools\n"
```

`scripts/lint_linefeeds.py` (run by `make ci-lint`) fails a markdown heading with no blank line
before it, and every committed block in the tree already carries the blank line — the generator was
the outlier. Because `insert_tools_block()` REPLACES the whole marker span, running the generator
over a green SKILL.md did not just emit a wrong shape: it **stripped** the blank line the file
needed and turned a green tree red. The rebase lane hit exactly that on 2026-10-30 and repaired its
own file by hand on both sides.

The mismatch stayed invisible because the block is generated once and then copied by
`sync-agent-profile`, which compares files byte-for-byte and never re-renders. Nothing compared the
generated shape with the committed one, so the defect could only be found by a lane that actually
regenerated — and the pass count never moved (6 test defs before, 6 after), which is why five PR
heads could report "fix present" without the file in their diff.

## What Changes

- `tools_block()` emits a blank line after `MARKER_BEGIN` — option (a) of #1119, which matches every
  committed block today and needs no file migration.
- `REPO_SKILL_PROFILES` is the module's ONE map from a HOST skill's path to its lane, and
  `profile_for_skill()` names the lane a tree SKILL.md belongs to (`agents/<profile>/…` states it in
  the path). `apply_repo_skills()` and the test read the same map, so a block cannot be stamped for
  one lane while the test checks another.
- `tests/test_host_bot_capabilities.py` gains two tests: the rendered block is **byte-identical** to
  every committed block in the tree (and re-running the generator over that file is a no-op), and
  every profile in the fixture renders a block — and a stamped file — that the REAL
  `lint_linefeeds._check_markdown_sections` accepts.

## Impact

Regenerating a lane's tools block can no longer red `make ci-lint`, and the generator's output is
pinned to the committed form instead of to a hand-written assertion. No SKILL.md changes, no config
changes, no behaviour change for a running lane.
