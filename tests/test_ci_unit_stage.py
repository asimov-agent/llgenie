"""The `ci-unit` gate sequence lives in scripts/ci_unit.py now (issue #2675, #800 criterion 5).

The 51 `$(MAKE)` lines of the `ci-unit` recipe (mk/ci.mk at origin/main@dcfb96b7df) moved into
the entry point as `MAKE_SEQUENCE`; the target recipe became the thin wrapper
`@python3 scripts/ci_unit.py`. This file keeps the move honest:

- the target still exists and its recipe is exactly the wrapper (no stray `$(MAKE)` left);
- `MAKE_SEQUENCE` is byte-for-byte and in-order the base recipe's 51 commands
  (`tests/fixtures/ci-unit-sequence-base.txt`, captured from dcfb96b7df) plus the documented
  additions since that capture — currently `make check-ci-discipline` (issue #2701), inserted
  after `make check-wiring`;
- `run` fail-fasts at the first failing sub-target and returns that sub-target's exit code;
- `--dry-run` prints all planned commands and executes nothing;
- the sub-makes run through the make binary make itself sets (`MAKE` env, fallback `make`),
  i.e. the `$(MAKE)` semantics that carry `MAKEFLAGS` into the sub-targets.

Only the subprocess seam is stubbed, to capture the argv make would receive; no gate logic
is mocked.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
from conftest import makefiles_text  # noqa: E402  (the include-resolving Makefile reader, #2458)
from scripts import ci_unit

BASE_FIXTURE = REPO / "tests" / "fixtures" / "ci-unit-sequence-base.txt"


def _recipe() -> str:
    mk = makefiles_text(REPO)
    m = re.search(r"^ci-unit:[^\n]*\n((?:[ \t].*\n)*)", mk, re.M)
    assert m, "ci-unit target not found in the flattened Makefile"
    return m.group(1)


def test_the_ci_unit_recipe_is_the_thin_wrapper_of_the_entry_point():
    # Given the flattened Makefile at this head
    # When the ci-unit recipe is read
    tab_lines = [l for l in _recipe().splitlines() if l.startswith("\t")]
    # Then it is one line, the entry-point call, with no leftover $(MAKE) sequence
    assert len(tab_lines) == 1, tab_lines
    assert tab_lines[0].strip() == "@python3 scripts/ci_unit.py"
    assert "$(MAKE)" not in _recipe()


def test_the_sequence_is_the_base_recipes_51_commands_byte_for_byte():
    # Given the base capture of the 51 `$(MAKE)` recipe lines (origin/main@dcfb96b7df)
    base = [l for l in BASE_FIXTURE.read_text().splitlines() if l.strip()]
    # When the entry point's sequence is compared to it
    # Then same commands, same order, plus the documented additions since the capture:
    # `make check-ci-discipline` (issue #2701), inserted directly after `make check-wiring`.
    assert base[0] == "make test-unit" and len(base) == 51
    expected = list(base)
    expected.insert(expected.index("make check-wiring") + 1, "make check-ci-discipline")
    assert list(ci_unit.MAKE_SEQUENCE) == expected


def test_sequence_targets_are_the_gate_roster_the_consumers_read():
    # When the target names are derived from the sequence
    targets = ci_unit.sequence_targets()
    # Then they are the 51 base gates in execution order plus the #2701 addition,
    # gate-classification-usable
    assert len(targets) == 52
    assert targets[0] == "test-unit"
    for gate in ("check-wiring", "check-ci-discipline", "check-docs",
                 "issue-bot-gates", "issue-bot-gates-check"):
        assert gate in targets


def test_run_stops_at_the_first_failing_gate_and_returns_its_code(monkeypatch):
    # Given a make seam where check-wiring fails with rc 7
    calls: list[list[str]] = []

    def fake_run(argv, **kw):
        calls.append(list(argv))
        rc = 7 if "check-wiring" in argv else 0
        return type("Proc", (), {"returncode": rc})()

    monkeypatch.setattr(ci_unit.subprocess, "run", fake_run)
    # When the sequence runs
    rc = ci_unit.run(make_bin="make", cwd=str(REPO))
    # Then the entry point stops there and returns the failing step's own exit code
    assert rc == 7
    names = [argv[1] for argv in calls]
    assert names[-1] == "check-wiring"  # every later gate was never started


def test_dry_run_prints_all_planned_commands_and_executes_nothing(monkeypatch, capsys):
    # Given the sequence
    def no_execution(*a, **k):
        raise AssertionError("dry run must not execute anything")

    monkeypatch.setattr(ci_unit.subprocess, "run", no_execution)
    # When --dry-run is requested
    rc = ci_unit.main(["--dry-run"])
    out = capsys.readouterr().out.splitlines()
    # Then all 52 planned commands (51 base + the #2701 gate) are printed, none executed
    assert rc == 0
    assert len(out) == 52
    assert out[0].endswith("test-unit")


def test_the_sub_makes_run_through_the_make_binary_make_sets(monkeypatch):
    # Given MAKE points at another make binary (the $(MAKE) semantics the entry point keeps)
    monkeypatch.setenv("MAKE", "gmake")
    # Then every planned command starts with it
    assert all(argv[0] == "gmake" for argv in ci_unit.planned_commands())
    # And with MAKE unset it falls back to plain make
    monkeypatch.delenv("MAKE", raising=False)
    assert ci_unit.planned_commands()[0][0] == "make"
