"""Every shipped engine is built by CI, or says why it is not an image (issue #771).

`skills-validate` proves a servable engine declares a container; `check-engine-params`
proves the committed cell matches the skill. Neither proves the matrix will BUILD the
cell — `engine_image.DISABLED` drops a cell, a variant outside `CI_VARIANTS` is never a
CI cell, and an engine whose `os` omits `linux` has no image. These tests lock the
verdict rule and the exception lifecycle (a new gap fails, a stale exception fails).
"""

from __future__ import annotations


from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

from scripts import engine_coverage as cov


def _skill(sid: str = "engine-a", servable=True, os_=("linux",)) -> dict:
    return {"id": sid, "engine": sid, "servable": servable, "os": list(os_)}


def test_a_cell_the_matrix_drops_leaves_the_engine_unbuilt():
    """A servable linux engine whose only variant is behind DISABLED is invisible."""

    # Given a servable linux engine with one params cell the build table drops
    skill = _skill()
    variants = {"rocm": {"backend": "rocm"}}
    dropped = lambda engine, variant: "#103 the cell cannot build yet"  # noqa: E731

    # When  the coverage verdict runs over it
    verdict, reason = cov.verdict(skill, variants, disabled=dropped)

    # Then  the engine is unbuilt and the reason names the cell and why it is dropped
    assert verdict == "unbuilt"
    assert "rocm (#103 the cell cannot build yet)" in reason


def test_a_variant_outside_the_ci_variants_is_not_a_cell():
    """A params variant that is not a CI variant is never built by the matrix."""

    # Given an engine whose only variant is not one the CI matrix builds
    skill = _skill()

    # When  the verdict runs with an empty build table
    verdict, reason = cov.verdict(skill, {"metal": {}}, disabled=lambda e, v: "")

    # Then  it is unbuilt and the reason says the variant is not a CI variant
    assert verdict == "unbuilt"
    assert "metal (not a CI variant)" in reason


def test_one_buildable_cell_covers_the_engine():
    """CPU is a CI variant, so a cpu image is enough coverage."""

    # Given a servable linux engine with a cpu cell
    skill = _skill()

    # When  the verdict runs with nothing dropped
    verdict, reason = cov.verdict(skill, {"cpu": {}}, disabled=lambda e, v: "")

    # Then  the engine counts as built
    assert (verdict, reason) == ("built", "cpu")


def test_deliberately_imageless_engines_pass():
    """`servable: via`, `servable: false` and a non-linux engine are not image engines."""

    # Given three skills that are not container servers
    cases = [
        (_skill(servable="via"), "rides another engine"),
        (_skill(servable=False), "servable: False"),
        (_skill(os_=["darwin"]), "no linux image"),
    ]

    # When  each one is classified
    verdicts = [cov.verdict(s, {"cpu": {}}, disabled=lambda e, v: "") for s, _ in cases]

    # Then  all are deliberately not images, with the matching reason
    assert [v for v, _ in verdicts] == ["not-an-image"] * 3
    assert all(needle in reason for (_, reason), (_, needle) in zip(verdicts, cases))


def test_a_new_unbuilt_engine_fails_the_gate_naming_it():
    """An unbuilt engine with no recorded exception is the finding the gate exists for."""

    # Given an unbuilt engine and an empty exception table
    rows = [{"id": "new-engine", "engine": "New Engine", "verdict": "unbuilt",
             "reason": "no params cell (run `make generate-engine-params`)"}]

    # When  the gate looks for findings
    errors = cov.findings(rows, known={})

    # Then  it names the engine and the reason
    assert len(errors) == 1
    assert "new-engine (New Engine) is shipped but never built" in errors[0]
    assert "no params cell" in errors[0]


def test_a_stale_exception_fails_the_gate():
    """Once an engine builds, its recorded exception must be removed."""

    # Given an engine that is now built and an exception that still records it
    rows = [{"id": "old-gap", "engine": "Old Gap", "verdict": "built", "reason": "cpu"}]

    # When  the gate runs with that exception still recorded
    errors = cov.findings(rows, known={"old-gap": "#103 used to be disabled"})

    # Then  it fails as stale and says so
    assert len(errors) == 1
    assert "is built now — the exception is stale" in errors[0]


def test_the_real_tree_is_green():
    """The committed skills satisfy the gate, so a red run means a real new gap."""

    # Given the real skills tree and the committed params
    rows = cov.census()

    # When  the gate runs over them
    errors = cov.findings(rows)

    # Then  nothing is unbuilt without an exception and no exception is stale
    assert errors == []
    assert {r["verdict"] for r in rows} <= {"built", "not-an-image", "unbuilt"}
    assert cov.KNOWN_UNBUILT.keys() <= {r["id"] for r in rows}
