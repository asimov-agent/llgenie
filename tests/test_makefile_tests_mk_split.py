"""Structural pins for the #800 residual split: the test-suite domain lives in mk/tests.mk (#2677).

The split must stay a split: the 18 issue-named targets are declared in `mk/tests.mk` (each with
its `##` help line), the top `Makefile` includes that file, no target name is declared in both
files (the #2674 duplicate detector enforces this as a gate; pinned here as a unit), and the
`ci-*` job domain plus the image domain stay on their side of the boundary.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

#: The 18 targets issue #2677 names, verbatim.
MOVED = [
    "test-env",
    "test-clean",
    "test-unit-network",
    "test-unit",
    "test-hub-live",
    "test-strata-live",
    "agents-read-venv",
    "test-agents-read",
    "test-agent-skills-live",
    "test-board-ownership-host",
    "test-recall-step",
    "test-top-tier",
    "test-top-tier-ci",
    "test-top-tier-serve",
    "test-top-tier-serve-ci",
    "test-top-tier-cli-ci",
    "test",
    "download-test-model",
]

#: `name:` at line start — a target declaration, never a `name:=` assignment.
STRICT = re.compile(r"^([A-Za-z_][A-Za-z0-9_./-]*)\s*:(?!=)", re.M)


def _declared(path: Path) -> dict[str, str]:
    """target name -> its declaration line (for `##` presence)."""
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        m = STRICT.match(line)
        if m:
            out.setdefault(m.group(1), line)
    return out


def test_tests_mk_exists_and_is_included_from_the_top_file():
    assert (REPO / "mk" / "tests.mk").is_file(), "mk/tests.mk must exist (#2677)"
    top = (REPO / "Makefile").read_text()
    assert re.search(r"^include mk/tests\.mk\b", top, re.M), (
        "the top Makefile must include mk/tests.mk in its include block"
    )


def test_every_issue_named_target_is_declared_in_tests_mk():
    declared = _declared(REPO / "mk" / "tests.mk")
    missing = [t for t in MOVED if t not in declared]
    assert not missing, f"#2677 targets not declared in mk/tests.mk: {missing}"


#: `test-unit-network` is an internal CI seam with NO `##` help line ON PURPOSE
#: (declared that way on main since issue #1000 — "not user-facing and no `##`
#: help line on purpose (engine-matrix-pushed precedent)"). The move must not
#: promote it into the help surface.
NO_HELP_ON_PURPOSE = {"test-unit-network"}


def test_moved_targets_keep_their_help_lines():
    declared = _declared(REPO / "mk" / "tests.mk")
    no_help = [
        t for t in MOVED
        if "##" not in declared[t] and t not in NO_HELP_ON_PURPOSE
    ]
    assert not no_help, f"moved targets lost their `##` help line: {no_help}"
    seam_note = (REPO / "mk" / "tests.mk").read_text()
    assert "no `##` help line on purpose" in seam_note, (
        "the #1000 seam comment must travel with test-unit-network"
    )


def test_no_target_is_declared_in_both_files():
    both = set(_declared(REPO / "Makefile")) & set(_declared(REPO / "mk" / "tests.mk"))
    assert not both, (
        f"targets declared in Makefile AND mk/tests.mk: {sorted(both)} "
        "(make keeps one recipe and silently drops the other — #2674's guard is the gate)"
    )


def test_the_ci_job_domain_stays_out_of_tests_mk():
    """`ci-*` job targets belong to mk/ci.mk (one ci-<job> target per pipeline job, #117)."""
    declared = set(_declared(REPO / "mk" / "tests.mk"))
    leaked = sorted(t for t in declared if t.startswith("ci-"))
    assert not leaked, f"ci-* job targets leaked into mk/tests.mk: {leaked}"
