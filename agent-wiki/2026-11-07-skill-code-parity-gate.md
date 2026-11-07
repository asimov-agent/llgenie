# Skill↔code parity gate (issue #1924)

## What was verified

- `scripts/check_skill_code_parity.py` (Layer B, CI): every `agents/*/skills/**/*.md` reference that
  cites a test id (`tests/test_x.py::test_y`) must resolve to a test in the **hermetic suite** (not
  merely on disk — `scripts/unit_tests.py` collection), and every repository-owned backticked code
  symbol must name a real file (and `::symbol` must be defined). Fenced code blocks (quoted logs,
  command samples) and the generic `tests/test_x.py::test_name` template are not claims and are
  ignored; a trailing `...` resolves by prefix (abbreviation).
- `scripts/skill_parity.py` (Layer A, host + read-only): diffs `agents/<profile>/skills/` against the
  live `~/.hermes/profiles/<profile>/skills/` per llgenie profile and reports live-only / tree-only
  counts and names. It is read-only: a run leaves the live profile and the tree byte-identical
  (mutation test asserts this).
- `agents/llgenie-planner/skills/llgenie-bot-orchestration/references/auto-merge-mechanism.md` §3
  restated: a stale-by-move deferral marker on a **green** head is swept by `recheck`
  (`has_any_deferral_marker`, #1914, `d45e659f`), anchored to
  `tests/test_auto_merge.py::test_a_stale_marker_green_head_is_retried_and_merged`. The pre-#1914
  sentence ("skipped by every cron run") described a fixed bug as current behaviour. This file was
  live-only (not on main); it is committed here.

## What is at stake

A skill reference exists so a lane does not re-derive a diagnosis. A reference that documents a fixed
bug as current behaviour, or cites a test that no longer runs, is worse than no reference: the next
lane reads it and acts on a false premise (e.g. hand-merge, forbidden #1088, or a #1910 duplicate).
Both directions were silent until this gate.

## Index

- Issue: #1924
