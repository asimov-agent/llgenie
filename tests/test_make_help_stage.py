"""`make help` prints from scripts/make_help.py now (issue #2675, #800 criterion 5).

The 60-line `help:` recipe of the Makefile (at origin/main@dcfb96b7df) moved into the entry
point as `HELP_LINES`; the target recipe became the thin wrapper `@python3 scripts/make_help.py`.
`scripts/check_docs.py` (#257/#678/#934) reads the `##` target declarations, not the recipe, so
the docs guard is untouched; what this file pins is the OUTPUT contract:

- the recipe is exactly the wrapper line;
- the entry point's stdout is byte-identical to the base capture committed as
  `tests/fixtures/make-help-base.txt` (`make help | cmp -` was proven on the host);
- the line count of `HELP_LINES` matches the fixture, so a later help edit must go through
  the fixture AND the entry point together.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
from conftest import makefiles_text  # noqa: E402  (include-resolving reader, #2459)
from scripts import make_help

BASE_FIXTURE = REPO / "tests" / "fixtures" / "make-help-base.txt"


def _help_recipe() -> str:
    mk = makefiles_text(REPO)
    m = re.search(r"^help:[^\n]*\n((?:[ \t].*\n)*)", mk, re.M)
    assert m, "help target not found in the flattened Makefile"
    return m.group(1)


def test_the_help_recipe_is_the_thin_wrapper_of_the_entry_point():
    # Given the flattened Makefile at this head
    tab_lines = [l for l in _help_recipe().splitlines() if l.startswith("\t")]
    # Then help is one line: the entry-point call, and no inline @echo block survived
    assert len(tab_lines) == 1, tab_lines
    assert tab_lines[0].strip() == "@python3 scripts/make_help.py"
    assert "@echo" not in _help_recipe()


def test_the_entry_point_output_is_the_base_capture_byte_for_byte(capsys):
    # Given the base `make help` capture (59 lines, taken at dcfb96b7df before the move)
    base_text = BASE_FIXTURE.read_text()
    # When the entry point renders help
    rc = make_help.main([])
    out = capsys.readouterr().out
    # Then byte parity with the capture: help output is what it was
    assert rc == 0
    assert out == base_text


def test_help_lines_and_fixture_stay_the_same_length():
    # Given the committed capture and the entry point's data
    base_lines = BASE_FIXTURE.read_text().splitlines()
    # Then they agree (the fixture is the contract; HELP_LINES is its copy inside the script)
    assert len(make_help.HELP_LINES) == len(base_lines) == 59
    assert list(make_help.HELP_LINES) == base_lines
