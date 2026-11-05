# 2026-11-05 report-header guard — the full status header or nothing (issue #1615)

The fleet's report contract is the six-field status line every lane opens with:
`BOT <name> · working on #<id> · branch <ref> · since <hh:mmZ> · blocked on <x|none> · next <y>`.
The issue is the stale self-report: a lane asserts state ("working on #5", "branch hotfix") without
the same-pass evidence that ties it to a live measure — a report without an id, a branch or a run id
is not a report. The rule was prose in every SOUL and `agents/standing-rules.md`; nothing clashed the
*gate*. This change makes the header contract a structural `ci-unit` gate:

- `scripts/check_report_header.py`: scans the tree's **reporting legs** — the strings `scripts/*.py`
  actually emit (string constants and f-string literal fragments, docstrings excluded) plus workflow
  step `name:`/`run:` lines in `.github/workflows/*.yml` — the same surface `check_report_hygiene`
  (#1292) reads. An emitted line that carries a **header signal** — a `working on #<id>` fragment
  with a concrete id, or a `·`-separated status line pairing `BOT` with at least two field keywords —
  must carry the **full six-field grammar**. Missing any field (`BOT`, `working on #`, `branch `,
  `since `, `blocked on `, `next `) is a **violation**. A bare `BOT` (a config variable), a prose
  story `BOT <name> — run ...` (em-dash, not a `·` header), a plain echo, a docstring/comment that
  *quotes* the rule, and a full `<...>` placeholder template that only *teaches* the grammar, are
  never scanned — a rule retro is not a report.
- `tests/test_check_report_header.py`: 10 tests pinning the contract — a full header passes; a header
  missing `blocked on` reds; a header without an id reds; a `working on #<id>` template does NOT
  resolve (teaching the grammar, not asserting an id); a plain echo and a docstring quote never scan;
  the workflow `run:` leg is a first-class surface; bare keywords alone are not a signal; the whole
  repo stays green; `main(["check"])` exit-code contract.
- Makefile: `check-report-header` / `report-header-report` targets (both `.PHONY`), added to the
  `ci-unit` job, classified in `scripts/issue_bot_gates.py` (DEFERRED — a static read a reporting-leg
  change is re-checked by ci-unit on the bot's own PR).

The `CONTRACT` constant is interpolated (never split into scan-visible header literals) into every
emitted message, so the gate's own diagnostics teach the grammar without being misread as a report;
the `_is_full_template_quote` guard lets a surface state the rule as a placeholder template without
reddening.

Not covered (per the refined scope): renaming the fields or changing the dispatch flow — the header
itself is untouched; the gate only refuses a partial emission.

Verified: `python3 scripts/check_report_header.py check` green on the tree (was red on the tree
before the signal fix — the gate found its own `working on #` keyword constant and a `BOT` config
variable, both now correctly out-of-band); `make check-wiring`, `make issue-bot-gates-check`,
`make check-report-hygiene`, `make check-report-header` green; the 10 tests pass. Baseline
`origin/main@84e9684c`.

References: implements issue #1615.
