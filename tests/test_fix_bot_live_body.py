"""Workflow-shape regression for #3123: fix-bot must check against the LIVE PR body."""
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WF = REPO / ".github" / "workflows" / "fix-bot.yml"


def _blocks():
    text = WF.read_text()
    fetch_start = text.index("- name: Fetch the LIVE PR body")
    loop_start = text.index("- name: Run the fix loop INSIDE", fetch_start)
    return text[fetch_start:loop_start], text[loop_start:loop_start + 1600]


def test_live_body_is_fetched_before_the_check_loop():
    """The body has to be fetched before fix-loop-image, not stamped after the verdict."""
    fetch, loop = _blocks()
    assert "gh pr view \"$NUM\"" in fetch
    assert "--json body" in fetch and "--json headRefOid" in fetch and "--json baseRefOid" in fetch
    assert "fix-loop-image" in loop
    assert "PR_BODY: /repo/fix-bot-pr-body.md" in loop
    assert "PR_HEAD: ${{ steps.livebody.outputs.head }}" in loop
    assert "PR_BASE: ${{ steps.livebody.outputs.base }}" in loop
    assert "PR_BODY=\"$PR_BODY\"" in loop


def test_body_dependent_check_refuses_an_empty_live_body():
    """An empty live body is a loud non-green, never a vacuous pass with a 'fixed' marker."""
    _, loop = _blocks()
    assert "body-dependent check" in loop
    assert "refusing a vacuous green (issue #3123)" in loop
    assert '[ ! -s "$PR_BODY" ]' in loop
    assert 'echo "exit=2" >> "$GITHUB_OUTPUT"' in loop
    assert "check-pr-commit-checkboxes" in loop and "check-pr-acceptance" in loop
