# 2026-11-13 — architecture-bot now pays its own note+row pair (issue #2598, PR #pending)

- Problem: the architecture-bot's publish leg committed `docs/ARCHITECTURE.md` alone, so every
  refresh violated the `check-docs` change→note rule (issue #1123) and reddened its own ci-scope.
  Measured on PR #2595 / run 43301454421: `[check-docs] ERROR: change->note: ... adds no
  agent-wiki/<stem>.md note`; a human hand-paid the pair (commit `03f2878a3`) to land it.
- Fix: `scripts/architecture_bot.py` gained `pair_stem`/`pair_row`/`pair_note`/`emit_pair`:
  after the stray guard, publish writes the `agent-wiki/<date>-architecture-refresh-<issue>.md`
  note, the matching one-row `docs/changes.d/` fragment (rendered through `changes_index`),
  rebuilds `CHANGES.md`, and commits all four paths as the bot identity. A `parse_row` probe runs
  BEFORE any issue/branch exists, so a malformed row files and writes nothing.
- The model leg is unchanged: the doc remains its ONLY writable file; the pair is deterministic.
  The bot's rendered issue/PR bodies now state the four-path rule, and the workflow header
  comment names the exception.
- Tests (`tests/test_architecture_bot.py`): publish test asserts the four-path commit + fragment
  parses + note link matches; new dry-run test asserts previews write no pair; no-drift and
  pending tests assert no pair appears.

Current status: implementation + tests written in `feat/archbot-note-pair`; gates and CI pending.
