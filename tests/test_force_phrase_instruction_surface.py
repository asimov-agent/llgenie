"""Instruction-surface hygiene for the canonical force-push vehicle (issue #2502).

The rule (issues #2451/#2498, `agents/standing-rules.md`): a rebased, squashed, or otherwise
rewritten head does NOT contain the old remote tip, so `--force-if-includes` justifiably rejects
it — those pushes go through a plain `--force-with-lease` after a fresh fetch. The flag is only
for amend/integrate pushes whose remote tip IS an ancestor of the new head.

This test scans the agent instruction surface (`agents/**/SKILL.md`, `agents/**/references/**`,
`agents/**/prompts/**`, excluding the `llgenie-pr-merge-conflict` lane, which carries the
canonical #1960 wording) and requires every `--force-if-includes` occurrence to carry an
ancestor/amend/integrate/rejection qualification in-line or within +/-2 lines. A documented
allow-list (`tests/fixtures/force_phrase_allowlist.json`) names file-level exceptions.

The planted fixture under `tests/fixtures/force_phrase_instruction_surface/` must be caught, so
the check cannot pass vacuously.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SURFACE_GLOB_ROOT = REPO_ROOT / "agents"
EXCLUDED_LANE = "llgenie-pr-merge-conflict"
QUAL_RE = re.compile(
    r"ancestor|amend|integrat|fast-forward|refus|reject|only case|sanctioned", re.IGNORECASE
)
WINDOW = 2
ALLOWLIST_PATH = REPO_ROOT / "tests" / "fixtures" / "force_phrase_allowlist.json"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "force_phrase_instruction_surface"


def _load_allowlist() -> set[str]:
    entries = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    return {e["file"] for e in entries}


def scan_surface(root: Path, *, prefix: str = "agents/") -> list[str]:
    """Return 'file:line' findings for unqualified --force-if-includes occurrences."""
    findings: list[str] = []
    allow = _load_allowlist() if prefix == "agents/" else set()
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if not rel.startswith(prefix):
            continue
        if EXCLUDED_LANE in rel:
            continue
        is_skill = path.name == "SKILL.md"
        is_ref = "references" in path.relative_to(root).parts
        is_prompt = "prompts" in path.relative_to(root).parts
        if not (is_skill or is_ref or is_prompt):
            continue
        if rel in allow:
            continue
        lines = path.read_text(encoding="utf-8").split("\n")
        for i, line in enumerate(lines):
            if "--force-if-includes" not in line:
                continue
            window = " ".join(lines[max(0, i - WINDOW) : i + WINDOW + 1])
            if not QUAL_RE.search(window):
                findings.append(f"{rel}:{i + 1}")
    return findings


def test_live_instruction_surface_has_no_unqualified_force_if_includes() -> None:
    findings = scan_surface(SURFACE_GLOB_ROOT)
    assert findings == [], "stale --force-if-includes teaching (issue #2502): " + "; ".join(findings)


def test_planted_stale_tuple_fixture_reds_the_check() -> None:
    findings = scan_surface(FIXTURE_ROOT, prefix="tests/fixtures/force_phrase_instruction_surface/")
    stale = [f for f in findings if "stale-fixture-lane" in f]
    qualified = [f for f in findings if "qualified-fixture-lane" in f]
    assert len(stale) == 1, f"planted stale tuple must red: {findings}"
    assert qualified == [], f"qualified fixture must stay green: {findings}"


def test_allowlist_is_documented_json() -> None:
    entries = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    for entry in entries:
        assert entry["file"].startswith("agents/") and entry["reason"]
