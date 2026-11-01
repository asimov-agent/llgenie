# 2026-11-02 report-hygiene guard — evidence-or-silence (issue #1292)

A reporting leg can guess *whose* work an overlap is and be wrong, turning a legitimate cross-lane
collision into a misdirected issue. `agent_profile_sync.py` already states the corrected principle in
prose ("the tree has no ownership information, so never say whose work it is"), and `orchestrator_tick.py`
frames the same failure as an order-of-operations — but neither was a tree-enforced structural guard, so a
future lane could reintroduce the guess in a new reporting leg and nothing would red. This change makes
evidence-or-silence a checked `ci-unit` gate:

- `scripts/check_report_hygiene.py`: scans the tree's **reporting legs** — the strings `scripts/*.py`
  actually emit (string constants and f-string literal fragments, docstrings excluded) plus workflow step
  `name:`/`run:` lines in `.github/workflows/*.yml`. A reporting string that pairs an **ownership pronoun**
  (another lane, someone else, a sibling lane, this lane, ...) with an **adverse shared-state change verb**
  (advanced, rewrote, moved, overwrote, deleted, ...) is a blame sentence, and it is a **violation** unless
  a `@<sha>` / `$<sha>` (or bare-sha) evidence anchor sits on the same line. Comments and docstrings that
  *quote* a forbidden phrase to explain the rule are not reporting output and never red.
- `tests/test_check_report_hygiene.py`: 9 tests pinning the contract — active and passive blame red without
  a sha and pass with a `@<sha>`; the workflow `run:` leg is a first-class surface; the corrected
  `agent_profile_sync.py` message (mtime fact, never an owner) passes unchanged; a comment/docstring quoting
  the phrase is not a violation; the whole repo stays green; `main(["check"])` exit-code contract.
- `docs/BOTS.md`: the make targets in the guard list + a new subsection (after the bind-proof section, issue
  #1293) stating the ownership rule — report a collision as an order-of-operations with the two side shas,
  never "another lane's fault".
- Makefile: `check-report-hygiene` / `report-hygiene-report` targets (both `.PHONY`), `check-report-hygiene`
  added to the `ci-unit` job, classified in `scripts/issue_bot_gates.py` (DEFERRED — a static read a
  reporting-leg change is re-checked by ci-unit on the bot's own PR).

Not covered (per the issue): arbitrating a real live collision between two lanes — the guard demands
evidence-or-silence, the lanes still resolve the overlap; and rewriting existing prose that already anchors
to a sha — those pass as written.

Verified: `python3 scripts/check_report_hygiene.py check` green on the tree; `make check-wiring`
`make issue-bot-gates-check` green; the 9 tests pass; `make check-report-hygiene` runs the guard. Baseline
`origin/main@1a775497`.

References: implements issue #1292.
