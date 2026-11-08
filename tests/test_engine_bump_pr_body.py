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
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github/workflows/engine-bump.yml"

# The env the step receives (mirrors `env:` on the step).
_OS_ENV = {
    "ID": "ollama",
    "OLD": "02480ca2a47153e1f9c31cbe1e05536da97ce1ba",
    "NEW": "02480ca2a47153e1f9c31cbe1e05536da97ce1ba",
    "REF": "v0.40.15",
}

_REPO = "acme/llgenie"

#: The author line the seam puts first in the body (issue #840) — the identity the commit carries.
_AUTHOR = "Author: Asimov Agent <support@docondee.com>"

_EXPECTED_BASE = (
    _AUTHOR + "\n"
    "\n"
    "Automated engine pin bump (issue #107).\n"
    "\n"
    "- **Engine:** `ollama`\n"
    "- **Pin:** `02480ca2` -> `02480ca2` (`v0.40.15`)\n"
    "- **Compare:** https://github.com/acme/llgenie/compare/"
    "02480ca2a47153e1f9c31cbe1e05536da97ce1ba..."
    "02480ca2a47153e1f9c31cbe1e05536da97ce1ba\n"
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
    not affect body rendering and need network auth — and before the #2050 stamp
    step (`printf > /tmp/pr-body.md` + `make bot-stamp-body`), which consumes the
    assembled body rather than assembling it. That step is pinned by
    `tests/test_bot_stamp_body.py`; here the subject is the rendering.
    """
    block = _run_block()
    lines = block.splitlines()
    start = next(i for i, l in enumerate(lines) if "body=" in l)
    end = next(
        (i for i, l in enumerate(lines)
         if i > start and ("gh pr view" in l or "/tmp/pr-body.md" in l or "bot-stamp-body" in l)),
        None)
    assert end is not None, "the PR write/stamp step was not found after the body assembly"
    return lines[start:end]


def _bash(body_slice: list[str], hard_fail: str, deps: str = "",
          author: str = _AUTHOR) -> str:
    """Run the body-assembly slice in bash and print `$body` on stdout.

    `author` stands in for `$(make -s git-identity-line)`: the seam's own value is pinned by
    `tests/test_git_identity.py`, and this module pins what the body does with it.
    """
    script = "set -eu\n"
    script += f"author={_shell_quote(author)}\n"
    for key, val in _OS_ENV.items():
        script += f'{key}={_shell_quote(val)}\n'
    script += f"HARD_FAIL={_shell_quote(hard_fail)}\n"
    script += f"DEPS={_shell_quote(deps)}\n"
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


def test_dependency_line_is_appended():
    """A bump that found new packages names them on their own line."""

    # Given the new pin added a python package and an apt package
    deps = "python_added=newpkg apt_added=libnew1"
    body = _bash(_body_slice(), hard_fail="", deps=deps)

    # When the body is rendered
    # Then the dependency line follows the base body
    assert body == _EXPECTED_BASE + "\n- **Dependencies:** " + deps
    assert "\\n" not in body


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


def test_generated_commit_message_does_not_trip_the_closing_gate():
    """The engine-bump commit must not claim an issue the bump never closes.

    #1588 regression: the commit message once began with `Issue: #107 — ...`, which
    `check_pr_closing` reads as a claim (issue #1329/#1417) and demands an adjacent
    `closes #107` in the squash text and body that a rolling engine-bump PR never
    emits — red on every generated bump. #107 is a CLOSED meta-issue; a pin bump is
    a rolling chore that should claim and close nothing. This asserts the workflow's
    generated commit line carries no `Issue: #N` claim, so the gate stays green and
    the false-red cannot return.
    """
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import check_pr_closing as cpc  # noqa: E402

    block = _run_block()
    msg_line = next(l for l in block.splitlines() if l.lstrip().startswith("msg=$(printf"))
    # Rebuild the commit message as the workflow does (printf interpolates \n).
    script = "set -eu\n"
    for key, val in _OS_ENV.items():
        script += f"{key}={_shell_quote(val)}\n"
    script += msg_line + "\nprintf '%s' \"$msg\"\n"
    rendered = subprocess.run(
        ["bash", "-c", script], check=True, capture_output=True, text=True
    ).stdout
    # A rendered bump commit (subject + message) claims no issue.
    title = "chore(engine): bump ollama to v0.40.15@02480ca2"
    claims = cpc.claims_in([rendered], None, title)
    assert claims == set(), (
        "engine-bump commit must not claim an issue the rolling pin does not close. "
        f"claiming {cpc._fmt(claims)} re-opens #1588."
    )
    # And the full squash check passes (commit claims nothing, body closes nothing).
    items = cpc.check_squash([rendered], body=None, title=title)
    assert items == [], [i["key"] for i in items]


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
