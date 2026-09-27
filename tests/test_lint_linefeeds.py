"""Linefeed lint tests: the lint MUST pick up extension-less config files.

Regression guard for the PR-review bug where `containers/test/Dockerfile`
(and bare `Makefile`/`LICENSE`/`.editorconfig`) never entered the lint's
tracked-file scan. Root cause: lint matched ONLY by path suffix, and an
extension-less ``Dockerfile`` has ``suffix == ''``, so the missing trailing
newline slipped through with "LINT OK" and the CI lint stage stayed green.

These tests assert the two things that must hold so a lint violation turns
the CI/lint stage RED (exit code != 0):

1. ``_tracked_text_files()`` includes extension-less config filenames
   (``containers/test/Dockerfile``, ``Makefile``, ``LICENSE``, ...), not just
   dotted-extension files.
2. ``check()`` returns a non-zero code (and names the file) when any picked-up
   tracked text file lacks a trailing newline — the fail-closed mechanism that
   drives the CI stage red.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Load scripts/lint_linefeeds.py by path so the test exercises the REAL script
# regardless of how pytest resolves sys.path inside the test container.
_LINT_SRC = str(REPO_ROOT / "scripts" / "lint_linefeeds.py")
_spec = importlib.util.spec_from_file_location("lint_linefeeds", _LINT_SRC)
assert _spec and _spec.loader, f"cannot load {_LINT_SRC}"
L = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(L)  # type: ignore[attr-defined]
sys.modules["lint_linefeeds_under_test"] = L


@pytest.mark.parametrize("path", [
    "containers/test/Dockerfile",
    "openspec/Dockerfile",
    "tools/Dockerfile",
    "Makefile",
    "tools/Makefile",
    "LICENSE",
    ".editorconfig",
    ".gitignore",
])
def test_extension_less_file_is_in_tracked_scan(path: str) -> None:
    """Every extension-less tracked config file we care about must be scanned."""
    files = L._tracked_text_files()
    assert path in files, (
        f"{path} must be in the lint scan list (got {len(files)} files). "
        "When extension-less files are skipped, a missing trailing newline "
        "silently stays green instead of turning the CI lint stage red."
    )


def test_check_returns_nonzero_on_missing_newline(repo_root: Path, tmp_path: Path) -> None:
    """Fail-closed: a scanned file without a final newline yields exit code 1.

    This is the exact exit-code contract the CI lint job relies on: when the
    lint flags a file, it must exit non-zero so the stage turns RED (GitHub
    marks a step failed on nonzero exit). We monkeypatch the file list to one
    tiny offender so the test stays hermetic (pytest runs in the container).
    """
    offender = tmp_path / "offender.py"
    offender.write_bytes(b"x = 1")  # no trailing newline

    origin_path = offender.resolve()
    orig = L._tracked_text_files

    def _one() -> list[str]:
        return [str(origin_path)]  # absolute path; check() joins onto _repo_root()

    L._tracked_text_files = _one  # type: ignore[assignment]
    try:
        rc = L.check(report=False)
        assert rc == 1, (
            "check() must return 1 (non-zero) when a scanned file lacks a "
            "trailing newline. A zero here is what let the Dockerfile slip "
            "through as a green lint."
        )
    finally:
        L._tracked_text_files = orig  # type: ignore[assignment]


def test_check_fix_appends_trailing_newline(tmp_path: Path) -> None:
    """--fix must actually append the final newline and return 0 afterwards.

    Regression guard for the dispatcher/new-OpenSpec CI failure where a
    freshly-created tracked text file (e.g. an OpenSpec change's .yaml/.md or a
    `scripts/` python file) was written WITHOUT a trailing newline, turning the
    CI `lint` job red even though everything else was green. The repair path
    `check(fix=True)` must add the newline so the next `check()` is green, and
    the recovery must be idempotent (a clean file stays clean).
    """
    target = tmp_path / "fresh_write.txt"
    target.write_bytes(b"skip_specs: true")  # written without final newline

    # --fix
    plugin = _tracked_offender_fn(target)

    orig = L._tracked_text_files
    L._tracked_text_files = plugin  # type: ignore[assignment]
    try:
        rc_fix = L.check(fix=True, report=False)
        # after fix the file ends with a newline and re-check returns 0
        assert target.read_bytes().endswith(b"\n"), "check(fix=True) must append a trailing \\n"
        rc_after = L.check(report=False)
        assert rc_fix == 0, f"fix pass should succeed, got rc={rc_fix}"
        assert rc_after == 0, "a newly-fixed file must lint green immediately after"
    finally:
        L._tracked_text_files = orig  # type: ignore[assignment]


def _tracked_offender_fn(offender: Path):
    """Return a tracked-files stub that reports just ONE offender (absolute)."""
    origin = offender.resolve()

    def _one() -> list[str]:
        return [str(origin)]

    return _one


def test_fix_returns_failfast_on_real_openspec_files_ending_newline(tmp_path: Path) -> None:
    """The exact repo class-of-bug: a tracked text file (like an OpenSpec
    change .yaml or a scripts/*.py) created without a final newline is caught
    and, after --fix, is clean. Uses a realistic extension ('.yaml') inside the
    TEXT_EXTS set so it is scanned by the real logic.
    """
    target = tmp_path / "change.yaml"
    target.write_bytes(b"schema: spec-driven\ncreated: 2026-08-24")  # no trailing newline
    one = _tracked_offender_fn(target)

    orig = L._tracked_text_files
    L._tracked_text_files = one  # type: ignore[assignment]
    try:
        assert L.check(report=False) == 1, "missing newline must be flagged"
        L.check(fix=True, report=False)  # repair
        assert target.read_bytes().endswith(b"\n")
        assert L.check(report=False) == 0, "after fix must be green"
    finally:
        L._tracked_text_files = orig  # type: ignore[assignment]


def test_markdown_heading_without_blank_line_is_flagged() -> None:
    """A markdown heading directly after content (no blank line) fails the lint.

    This is the exit-code contract the CI lint job relies on for the markdown
    section-separation rule: a `#### Scenario:` (or any heading) that is not
    preceded by a blank line must make `check()` return non-zero so the stage
    turns RED. Regression guard for the spec.md gap where a `- **Test:**` line
    was directly followed by the next scenario heading.
    """
    bad = [
        "- **Test:** tests/test_detect_server.py::test_x",
        "#### Scenario: unknown override falls back to RAM",
        "- **Given** x",
    ]
    assert L._check_markdown_sections("spec.md", bad) == [2], (
        "a heading not preceded by a blank line must be reported (line 2)"
    )


def test_markdown_heading_with_blank_line_is_clean() -> None:
    """A heading preceded by a blank line is not flagged."""
    good = [
        "- **Test:** tests/test_detect_server.py::test_x",
        "",
        "#### Scenario: unknown override falls back to RAM",
        "- **Given** x",
    ]
    assert L._check_markdown_sections("spec.md", good) == []


def test_markdown_code_fence_and_indented_prose_are_ignored() -> None:
    """`#` inside a fenced code block or indented prose is not a heading.

    A `# Given`/`# Then` comment marker in a test body (indented) and a `#`
    comment inside a ``` fence must NOT be treated as a heading, so they are
    never flagged for missing a preceding blank line.
    """
    lines = [
        "```bash",
        "# a comment inside a code block",
        "make install",
        "```",
        "",
        "## Real heading",
        "  # Then markers in the test body",
        "",
        "### Another real heading",
    ]
    # Only the two real column-0 headings (lines 6 and 9) are checked; both
    # are preceded by a blank line, so nothing is flagged. The `#` inside the
    # fence and the indented `# Then` prose are not headings.
    assert L._check_markdown_sections("x.md", lines) == []


def test_markdown_every_heading_level_needs_a_blank_line() -> None:
    """The blank-line rule applies to EVERY heading level (##, ###, ####, …).

    A `###`/`####`/`#####`/`######` heading directly after content (no blank
    line) must be flagged just like a `##` — the rule is not limited to one
    level. The first line of the file is exempt (nothing precedes it).
    """
    no_blank = [
        "## Section A",
        "body a",
        "### Sub A",
        "body a1",
        "#### Sub-sub A",
        "body a2",
        "##### Deep A",
        "body a3",
        "###### Deepest A",
        "body a4",
    ]
    # Line 1 (`##`) is the file's first line -> exempt. Lines 3,5,7,9 are the
    # ###/####/#####/###### headings, each directly after content -> flagged.
    assert L._check_markdown_sections("x.md", no_blank) == [3, 5, 7, 9]

    with_blank = [
        "## Section A",
        "",
        "### Sub A",
        "",
        "#### Sub-sub A",
        "",
        "##### Deep A",
        "",
        "###### Deepest A",
    ]
    assert L._check_markdown_sections("x.md", with_blank) == []
