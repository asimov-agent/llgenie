#!/usr/bin/env python3
"""#2064: the lane profiles reference the lanes preload links the docs/BOTS.md Fleet
memory section (#2057 AC5). Hermetic: reads the tree only, no network.

The check scans every `agents/*/skills/*/references/agent-profiles*.md` (the preloaded
profile references), demands the Fleet memory anchor link in each, verifies the anchor
target still exists in docs/BOTS.md, and proves a planted removal is caught rather than
the current text being trusted.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANCHOR = "#fleet-memory-one-hindsight-daemon-per-host-shared-plugin-profile-issue-2057"
FLEET_HEADING = re.compile(
    r"(?m)^## Fleet memory: one Hindsight daemon per host, shared plugin profile \(issue #2057\)$"
)


def _profile_refs() -> list[Path]:
    return sorted(ROOT.glob("agents/*/skills/*/references/agent-profiles*.md"))


def _missing_anchor(text: str) -> bool:
    return ANCHOR not in text


def test_a_preloaded_profiles_references_exist_in_the_tree():
    assert _profile_refs(), "no agents/*/skills/*/references/agent-profiles*.md in the tree"


def test_b_every_profiles_reference_links_the_fleet_memory_section():
    for ref in _profile_refs():
        text = ref.read_text(encoding="utf-8")
        assert not _missing_anchor(text), (
            f"{ref.relative_to(ROOT)} does not link docs/BOTS.md's Fleet memory section"
        )


def test_c_the_linked_anchor_target_still_exists_in_bots_md():
    bots = (ROOT / "docs" / "BOTS.md").read_text(encoding="utf-8")
    assert FLEET_HEADING.search(bots), (
        "docs/BOTS.md lost the Fleet memory section the profile references link"
    )


def test_d_a_planted_removal_of_the_pointer_is_caught():
    ref = _profile_refs()[0]
    tampered = ref.read_text(encoding="utf-8").replace(ANCHOR, "#not-fleet-memory")
    assert _missing_anchor(tampered), "the check cannot see a deleted Fleet memory link"
