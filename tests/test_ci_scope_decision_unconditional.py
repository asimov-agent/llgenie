"""The scope decision is published unconditionally by ci.yml's guard job (issue #2156).

A guard that reds on a PR-body hygiene gate (check-pr-authors, check-pr-closing,
check-pr-agents-line, ...) must NEVER leave its run without the `ci-scope-decision`
artifact — otherwise `ci_scope.verify()` has no decision and ci-verdict prints
"NO DECISION: this run published no scope decision -- no skip is legitimate" for the
ENTIRE run (every selected-and-skipped job counts no_verdict), masking the gate that
actually failed. Measured on run 42480410251 (#2248) and 42479770472 (#2246): both CI
guard jobs died at `make check-pr-agents-line` BEFORE reaching the "Publish the scope
decision"/"Upload the decision" steps, published no artifact, and ci-verdict went
NO DECISION on 5 PRs.

The invariant pinned here: both decision steps carry `if: always()`. Removing those two
lines (the exact defect the tree shipped with) must red this test.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

#: The two guard-job steps that publish/upload the decision. Only in ci.yml's guard.
_PUBLISH = "- name: Publish the scope decision"
_UPLOAD = "- name: Upload the decision"


def _step_has_always(lines: list[str], start: int) -> bool:
    """True when the `if: always()` line sits in the step body that begins at line `start`.

    A step's body is every following line more indented than the `- name:` line itself;
    the body ends at the next same-or-less-indented non-empty line (a new step).
    """
    indent = len(lines[start]) - len(lines[start].lstrip())
    for raw in lines[start + 1:]:
        if not raw.strip():
            continue
        body_indent = len(raw) - len(raw.lstrip())
        if body_indent <= indent and raw.lstrip().startswith("- "):
            return False  # next step, `if: always()` never appeared
        if raw.strip() == "if: always()":
            return True
    return False


def _find_step(lines: list[str], prefix: str) -> int:
    for i, raw in enumerate(lines):
        if raw.lstrip().startswith(prefix):
            return i
    raise AssertionError(f"ci.yml has no step {prefix!r}")


def test_guard_decision_steps_are_unconditional():
    """Regression for issue #2156: a failing PR-hygiene gate must not suppress the scope
    decision. Both the publish and upload step of the guard job must carry `if: always()`.
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert _step_has_always(lines, _find_step(lines, _PUBLISH)), (
        "Publish the scope decision must carry `if: always()` (issue #2156): a red "
        "PR-hygiene gate earlier in the guard job otherwise erases the decision and "
        "ci-verdict reports NO DECISION for the whole run (measured run 42480410251, #2248)."
    )
    assert _step_has_always(lines, _find_step(lines, _UPLOAD)), (
        "Upload the decision must carry `if: always()` (issue #2156): the upload must not "
        "be skipped when a sibling gate failed after the decision was still written."
    )
