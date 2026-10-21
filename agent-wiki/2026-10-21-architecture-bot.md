# 2026-10-21 — architecture bot keeps docs/ARCHITECTURE.md current (issue #449)

## What was built

`architecture-bot` (`.github/workflows/architecture-bot.yml`, `scripts/architecture_bot.py`,
`docs/ARCHITECTURE.md`) re-reads the real tree every 6 hours (`47 */6 * * *`) and on manual
dispatch, rewrites the architecture document, and leaves the refresh as ONE linked issue + ONE
reviewable PR. It never merges and never pushes to `main`.

- `make architecture-bot-brief` — deterministic: the tree surface (tracked layout, `scripts/`
  modules, public targets, workflows/crons, data/skills/containers/tests) plus the drift since
  the commit that last wrote the doc (`git log --diff-filter=AM`, `git diff ..HEAD`). No model.
- `make architecture-bot-doc` — one Hermes leg inside the agent image; the doc is the only
  writable file. Credentials travel through `AGENT_SHELL_FORWARD`; the transcript is redacted by
  the existing `scrubbed_run` seam.
- `make architecture-bot-publish` — checks the working tree (`git diff HEAD`), refuses a doc
  under 200 characters, refuses from any branch but `main`, refuses when a tracked file other
  than the doc changed (the agent's write boundary is enforced), defers when an
  `agent/architecture-*` PR is open, and otherwise files
  one issue (Issue/Fix/Benefit/Technical), commits only the doc as `Asimov Agent`, pushes
  `agent/architecture-<UTC stamp>`, and opens one PR ending `closes #<issue>`.
- `make architecture-bot` chains the three for a local run (`DRY=1` previews).

## Verified

- `tests/test_architecture_bot.py` (new, discovered by `scripts/unit_tests.py`): real git repos
  for the brief and for publish (real branch, real commit, real bare remote); `gh` is a recorded
  fake because the test must not file issues. Scenarios map 1:1 onto
  `openspec/changes/feat-architecture-bot/specs/architecture-bot/spec.md`.
- The cron slot `:47 */6` is free of every reserved minute (`:07`, `:17`, `:29`, `:37`, `:43`),
  and the workflow has its own concurrency group (`architecture-bot`), so
  `tests/test_bot_pipeline_isolation.py` stays green.
- README section + regenerated dispatch table; `make check-dispatch-forms`, `make check-docs`,
  `make check-wiring` pass with the new files.

## Status

OpenSpec change `feat-architecture-bot`; branch `feat/architecture-bot`; issue #449; PR #451
against `asimov-agent/llgenie:main`. Waiting for review — the agent never merges.

## Related

- #269 (code-review bot, the analysis-only sibling)
- #248 (issue-bot, the issue -> PR lifecycle this bot follows)
- #231 (analysis ships issues, never implementation)
