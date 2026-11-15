# Recipe extraction: the five longest recipes move behind scripts/ entry points (issue #2675, branch feat/2675-recipe-extraction)

## What was verified

#800 criterion 5 — the five longest recipes become ≤ 3-line wrappers calling tested
`scripts/` entry points. All five extracted at `origin/main@dcfb96b7df`:

- **`help`** (60 lines) → `scripts/make_help.py`: the 59-line help text is a committed
  tuple emitted byte-identically; `cmp` against the pre-change capture
  (`tests/fixtures/make-help-base.txt`, sha256 `1eb759c19f…`) proves parity, and the
  output is now one string the #681 generator can own.
- **`ci-unit`** (51 lines) → `scripts/ci_unit.py`: the 51-entry gate sequence is a
  `MAKE_SEQUENCE` tuple byte-equal to the base invocation list
  (`tests/fixtures/ci-unit-sequence-base.txt`), fail-fast, honoring `$(MAKE)` via
  `os.environ.get("MAKE", "make")`; `--dry-run` prints the plan without running it.
- **`test-clean`** (15 lines) → `scripts/test_clean.py`: runtime-agnostic orphan
  container sweep (no `--filter ancestor`, skips running containers by inspect).
- **`build-server`** (15 lines) → `scripts/build_server.py`: detect → tee'd build →
  stamp, keeping the base recipe's pipefail-without-`set -e` semantics (the gate is
  the final log-line check, not `check=True`).
- **`test-published-engine`** (12 lines) → `scripts/published_engine.py` plus two
  internal seam targets (`published-engine-pull`, `published-engine-binary`): the
  three-step sequence is machine-readable through the entry-point seam.

Gate seams follow: `scripts/check_wiring.py` and `scripts/issue_bot_gates.py` read the
sequence out of the entry-point scripts (not recipe text), so the wiring closure and
the fast/deferred classification stay byte-stable; `scripts/package-layers.json` places
all five modules in **CI entrypoints**. `scripts/build_server.py` is NOT a host-only
wiring exception: its stage test runs inside `ci-unit`, and a host-only entry whose
script is CI-covered must be deleted.

## Parity measured at head

`make -qp` sorted-unique target inventory identical before/after (the sole record delta
belongs to #2700's `mk/agents.mk`); `make help` byte-identical (59 lines);
`make check-wiring`, `make check-workflows`, `make check-docs`, `make issue-bot-gates`,
`make issue-bot-gates-check` green; hermetic stage tests `tests/test_{ci_unit,make_help,
test_clean,build_server,published_engine}_stage.py` plus the four consumer tests
(`test_wiring`, `test_issue_bot_gates`, `test_network_marker`, `test_published_gate`)
green — 91 passed, no network marker, no docker.

## Key decisions

- Recipes became ONE-line wrappers (stricter than the ≤ 3 the criterion asks).
- The `host-only-wiring.json` entry first added for `build_server.py` was REMOVED once
  its stage test landed: a CI-covered script may not declare itself host-only.
- Help text stays hard-coded (byte-parity first); generation is #681's job.

## Current status

OpenSpec change `recipe-extraction-scripts` validated; full `make test-unit` green at
head; PR pending on branch `feat/2675-recipe-extraction` (closes #2675, carries #800's
criterion-5 row).
