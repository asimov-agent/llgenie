"""Issue #2852: every body-replacing bot lane writes through `make bot-body-write`, fleet-wide.

Issue #2131 landed the guarded seam (`scripts/pr_body_write.py`) and wired only `fix-bot.yml`. The defect
class is "any bot writes a body it derived from stale state": measured on `main` `fbf613d83`, three lanes
still hand-rolled a body REPLACEMENT of an OPEN PR with `gh pr edit … --body-file`
(`engine-bump.yml:266`, `registry-sync.yml:223`, `semgrep-rules-refresh.yml:167`), while `issue-bot.yml`
and `issue-refiner.yml` only post `gh issue comment` (append-only) and `rebase-bot.yml`,
`engine-bump-rebase.yml` and `auto-merge.yml` carry no body write at all. These tests scan every workflow
file so a new hand-rolled body replacement in ANY lane is a unit-test failure, and pin the measured
classification of the append-only / body-write-free lanes.

Run with `make test-unit`.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO / ".github" / "workflows"

#: A shell line that REPLACES a PR body without the seam: `gh pr edit` carrying a body payload, or a
#: `gh api PATCH … pulls/<n>` with a `body` field. `gh pr create --body-file` is NOT a replacement (it
#: opens the body once) and does not match; title-only `gh pr edit --title …` does not match either.
HAND_ROLLED = (
    re.compile(r"gh\s+pr\s+edit\b[^\n]*?(--body-file|-f\s+body)"),
    re.compile(r"gh\s+api\s+PATCH\b[^\n]*?pulls/[^\n]*?-f\s+body"),
)

#: The lanes the seam is wired into (measured after issue #2852 wired the three replacement lanes).
WIRED_LANES = {"fix-bot.yml", "engine-bump.yml", "registry-sync.yml", "semgrep-rules-refresh.yml"}

#: Append-only lanes: they reach a body state only by appending a comment (issue-bot/issue-refiner).
APPEND_ONLY_LANES = {"issue-bot.yml", "issue-refiner.yml"}

#: Lanes measured to carry no PR-body write at all (rebase lanes, the merge lane).
BODY_WRITE_FREE_LANES = {"rebase-bot.yml", "engine-bump-rebase.yml", "auto-merge.yml"}


def hand_rolled_body_writes(name: str, text: str) -> list[str]:
    """Lines of a workflow text that replace a PR body without `make bot-body-write` (empty = wired or clean)."""
    if "make bot-body-write" in text:
        return []
    out: list[str] = []
    for i, line in enumerate(text.splitlines(), 1):
        for pat in HAND_ROLLED:
            if pat.search(line):
                out.append(f"{name}:{i}: {line.strip()[:120]}")
    return out


def fleet_findings() -> list[str]:
    findings: list[str] = []
    for yml in sorted(WORKFLOWS.glob("*.yml")):
        findings.extend(hand_rolled_body_writes(yml.name, yml.read_text()))
    return findings


def test_replacement_lanes_route_through_the_seam() -> None:
    """No workflow in the fleet hand-rolls a PR-body replacement anywhere."""
    assert fleet_findings() == []
    wired = {
        yml.name
        for yml in WORKFLOWS.glob("*.yml")
        if "make bot-body-write" in yml.read_text()
    }
    assert wired == WIRED_LANES  # the seam's caller set is exactly the measured one
    # the replacement lanes keep a title-only edit; the body never rides on it
    for lane in ("engine-bump.yml", "registry-sync.yml", "semgrep-rules-refresh.yml"):
        text = (WORKFLOWS / lane).read_text()
        assert "make bot-body-write" in text
        assert not re.search(r"gh\s+pr\s+edit\b[^\n]*--body-file", text)


def test_append_only_lanes_stay_append_only() -> None:
    """issue-bot/issue-refiner reach body state only via `gh issue comment`; rebase/merge lanes write none."""
    for lane in APPEND_ONLY_LANES:
        text = (WORKFLOWS / lane).read_text()
        assert "gh issue comment" in text
        assert not re.search(r"gh\s+pr\s+edit\b", text)
        assert not re.search(r"gh\s+api\s+PATCH\b[^\n]*pulls/", text)
    for lane in BODY_WRITE_FREE_LANES:
        text = (WORKFLOWS / lane).read_text()
        assert not re.search(r"gh\s+pr\s+edit\b[^\n]*--body-file", text)
        assert not re.search(r"gh\s+api\s+PATCH\b[^\n]*pulls/[^\n]*-f\s+body", text)


def test_a_planted_hand_rolled_body_write_is_caught() -> None:
    planted = (
        "steps:\n"
        "  - run: |\n"
        "      gh pr edit chore/sneaky --body-file /tmp/body.md\n"
    )
    findings = hand_rolled_body_writes("planted.yml", planted)
    assert findings and "planted.yml:3" in findings[0]
    # and the seam presence clears the same text (the scan tests the call site, not the file name)
    assert hand_rolled_body_writes("planted.yml", planted.replace("gh pr edit", "make bot-body-write")) == []

