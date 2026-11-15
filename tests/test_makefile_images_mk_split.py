"""Structural pins for the #800 residual split: the image build/publish domain lives in mk/images.mk (#2678).

The split must stay a split: the 9 image-domain targets are declared in `mk/images.mk` (each with
its `##` help line), the top `Makefile` includes that file, no target name is declared in both
files (the #2674 duplicate detector enforces this as a gate; pinned here as a unit), and the
ci-domain `ci-image-refs`, the container-hygiene `test-clean`, and the shared variant variables
stay on their side of the boundary. Membership is decided by RECIPE, not name: `agent-image-ref`
runs `scripts/ci_images.py latest agent`, so it belongs here (the issue #2678 membership note
pre-authorizes the move out of the agents sibling).
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

#: The 9 targets issue #2678 moves (its 8 named targets + `agent-image-ref`, whose recipe is a
#: `scripts/ci_images.py` call — image-shaped by the issue's own membership rule).
MOVED = [
    "test-image",
    "test-image-pull",
    "test-variant-image",
    "publish-ci-images",
    "publish-agent-image",
    "agent-image-push-check",
    "agent-image",
    "agent-image-pull",
    "agent-image-ref",
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


def test_images_mk_exists_and_is_included_from_the_top_file():
    assert (REPO / "mk" / "images.mk").is_file(), "mk/images.mk must exist (#2678)"
    top = (REPO / "Makefile").read_text()
    assert re.search(r"^include mk/images\.mk\b", top, re.M), (
        "the top Makefile must include mk/images.mk in its include block"
    )


def test_every_moved_target_is_declared_in_images_mk():
    declared = _declared(REPO / "mk" / "images.mk")
    missing = [t for t in MOVED if t not in declared]
    assert not missing, f"#2678 targets not declared in mk/images.mk: {missing}"
    extra = sorted(set(declared) - set(MOVED))
    assert not extra, f"mk/images.mk declares targets beyond the #2678 roster: {extra}"


def test_moved_targets_keep_their_help_lines():
    declared = _declared(REPO / "mk" / "images.mk")
    no_help = [t for t in MOVED if "##" not in declared[t]]
    assert not no_help, f"moved targets lost their `##` help line: {no_help}"


def test_no_target_is_declared_in_both_files():
    both = set(_declared(REPO / "Makefile")) & set(_declared(REPO / "mk" / "images.mk"))
    assert not both, (
        f"targets declared in Makefile AND mk/images.mk: {sorted(both)} "
        "(make keeps one recipe and silently drops the other — #2674's guard is the gate)"
    )


def test_the_moved_targets_are_declared_in_no_other_domain_file():
    for mk in sorted((REPO / "mk").glob("*.mk")):
        if mk.name == "images.mk":
            continue
        overlap = sorted(set(MOVED) & set(_declared(mk)))
        assert not overlap, f"{mk} re-declares moved images targets: {overlap}"


def test_ci_image_refs_stays_in_the_ci_domain():
    """`ci-image-refs` is a `ci-*` job-domain target (mk/ci.mk) — never re-moved with the images cluster."""
    assert "ci-image-refs" in _declared(REPO / "mk" / "ci.mk"), "ci-image-refs must stay in mk/ci.mk"
    assert "ci-image-refs" not in _declared(REPO / "mk" / "images.mk")


def test_shared_variables_stay_in_the_top_makefile():
    """The domain files declare targets only (zero `VAR :=` in all six siblings); the variant
    variables the image recipes read stay at the top, exactly as #2456–#2460 left them."""
    top = (REPO / "Makefile").read_text()
    assert re.search(r"^VARIANT_IMG\s*:=", top, re.M), "VARIANT_IMG must stay in the top Makefile"
    assert re.search(r"^VARIANT_RUN\s*:=", top, re.M), "VARIANT_RUN must stay in the top Makefile"
    images = (REPO / "mk" / "images.mk").read_text()
    assert not re.search(r"^VARIANT_(IMG|RUN)\s*:=", images, re.M)


def test_phony_declarations_stay_in_the_top_makefile():
    """.PHONY names the image targets in the top file (the #2456–#2461 precedent): the split
    must not orphan them as non-phony names."""
    top = (REPO / "Makefile").read_text()
    for t in ("test-image", "agent-image", "test-variant-image"):
        assert re.search(rf"\.PHONY:.*\b{re.escape(t)}\b", top, re.S), (
            f".PHONY must still name {t} in the top Makefile"
        )
