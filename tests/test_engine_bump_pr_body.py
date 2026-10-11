"""Unit tests for the engine-bump workflow's PR-body rendering.

The bug (issue #144): the `.yml` `run: |` block handed bash a double-quoted
string containing `\n` escape sequences; inside double quotes bash does NOT turn
`\n` into a newline, so every bump PR body rendered literal `\n` text. These
tests exercise the fixed step: the body is built with `printf` (whose format
string *does* interpret `\n`), and the hard-fail warning is appended with
`printf '%b'`.

They are hermetic: they parse `engine-bump.yml`, extract the exact `run` block
of the `Open / update the bump PR` step, validate it with `bash -n`, and run
the body-assembly slice in a real bash subprocess so the assertion matches what
CI actually executes (including the `if [ -n "$HARD_FAIL" ]` guard).

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github/workflows/engine-bump.yml"

# The env the step receives (mirrors `env:` on the step).
_OS_ENV = {
    "ID": "ollama",
    "OLD": "b0c1ca4f7549d7acdfa52a7dcffc934bc63a43ce",
    "NEW": "eab97e9f92b9a25c2d52d2cc6c1b1c99bd9fae21",
    "REF": "v0.40.3",
}

_REPO = "acme/llgenie"

_EXPECTED_BASE = (
    "Automated engine pin bump (issue #107).\n"
    "\n"
    "- **Engine:** `ollama`\n"
    "- **Pin:** `b0c1ca4f` -> `eab97e9f` (`v0.40.3`)\n"
    "- **Compare:** https://github.com/acme/llgenie/compare/"
    "b0c1ca4f7549d7acdfa52a7dcffc934bc63a43ce..."
    "eab97e9f92b9a25c2d52d2cc6c1b1c99bd9fae21\n"
    "- CI builds and tests ONLY this engine's images. A red PR means the new "
    "commit needs a manual skill fix."
)


def _run_block() -> str:
    """Return the literal `run` block of the Open / update the bump PR step."""
    with WORKFLOW.open() as fh:
        wf = yaml.safe_load(fh)
    for step in wf["jobs"]["bump"]["steps"]:
        if step.get("name") == "Open / update the bump PR":
            return step["run"]
    raise AssertionError("Open / update the bump PR step not found in engine-bump.yml")


def _body_slice() -> list[str]:
    """Return the source lines that assemble `body` (the printf + guarded append).

    Stops before the `gh pr view` / `gh pr edit|create` decision lines, which do
    not affect body rendering and need network auth.
    """
    block = _run_block()
    lines = block.splitlines()
    start = next(i for i, l in enumerate(lines) if "body=" in l)
    # the assembly is exactly: base body line, then the if/guard/fi append.
    end = next((i for i, l in enumerate(lines) if l.strip() == "fi" and i > start), None)
    assert end is not None, "hard-fail guard 'fi' not found in body assembly"
    return lines[start : end + 1]


def _bash(body_slice: list[str], hard_fail: str) -> str:
    """Run the body-assembly slice in bash and print `$body` on stdout."""
    script = "set -eu\n"
    for key, val in _OS_ENV.items():
        script += f'{key}={_shell_quote(val)}\n'
    script += f"HARD_FAIL={_shell_quote(hard_fail)}\n"
    body_source = "\n".join(body_slice)
    body_source = body_source.replace("${{ github.repository }}", _REPO)
    script += body_source + "\n"
    script += 'printf "%s" "$body"\n'
    return subprocess.run(
        ["bash", "-c", script], check=True, capture_output=True, text=True
    ).stdout


def _shell_quote(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


def test_pr_body_has_real_newlines():
    """REQ-1: base body ends each line with a real newline, not literal \\n."""

    # Given the workflow's body assembly runs in bash with no hard-fail
    body = _bash(_body_slice(), hard_fail="")

    # When  the body is rendered
    # Then  it matches the expected rendering with real line breaks
    assert body == _EXPECTED_BASE
    assert "\\n" not in body  # no literal backslash+n anywhere


def test_hard_fail_appended():
    """REQ-2: the manual-review warning is appended on its own paragraph."""

    # Given a derive hard-fail was recorded
    hard_fail = "the 'LLAMA_CUBLAS' flag was removed"
    body = _bash(_body_slice(), hard_fail=hard_fail)

    # When  the guarded append runs
    # Then  it lands after a blank line, with real newlines throughout
    assert body.startswith(_EXPECTED_BASE)
    expected_warn = (
        "\n\n> ⚠️ **Manual review required:** a build parameter could not be "
        f"auto-derived — {hard_fail}. The pin is bumped and the PR is open; CI "
        "will go red on the build until the skill is fixed by hand."
    )
    assert body.endswith(expected_warn)
    assert "\\n" not in body


def test_hard_fail_absent_does_not_append():
    """The guard must not append the warning when HARD_FAIL is empty."""

    # Given no hard-fail (HARD_FAIL="")
    body = _bash(_body_slice(), hard_fail="")

    # When  the guarded append runs
    # Then  the body is exactly the base (no warning)
    assert body == _EXPECTED_BASE
    assert "Manual review required" not in body


def test_run_block_is_valid_bash():
    """REQ-3: the extracted run block passes bash -n."""

    # Given the workflow's Open/update step source
    block = _run_block()

    # When  we syntax-check it as a bash script
    # Then  it parses without error
    subprocess.run(["bash", "-n", "-c", block], check=True, capture_output=True, text=True)
    for line in block.splitlines():
        if "body=" in line or "printf" in line:
            subprocess.run(
                ["bash", "-n", "-c", line], check=True, capture_output=True, text=True
            )


def test_printf_format_uses_single_backslash_n():
    """Guard the fix: printf format args carry \\n, never literal double-\\n."""

    # Given the body-assembly source
    src = "\n".join(_body_slice())
    # Extract every single-quoted printf argument.
    args = re.findall(r"'((?:[^'\\]|\\.)*)'", src)

    # When  we inspect the format strings
    # Then  the base format uses a single backslash-n (a printf escape) and
    #       never a double backslash (which would render literal backslash+n)
    assert any("\\n" in a for a in args)
    assert all("\\\\n" not in a for a in args)
