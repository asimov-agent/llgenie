"""Committed trending list for every (arch, vram, ram) `llgenie --matrix` takes.

The expected rows live in tests/fixtures/trend-list-matrix.json. They are
`matrix(registry, vram, ram, arch)` on the vendored registry: README order,
the highest t/s server on that architecture whose quant fits the card and the
RAM. A registry sync rewrites the fixture (`make render-trend-list-matrix`).
Until that rewrite lands, this test fails, and the pull-request diff is the
new list.

ROUTING (issue #1020): `matrix()` is NOT a pure function of the vendored
registry. For a model no engine can run, `_no_fit_reason()` reads the smallest
download's size off the LIVE Hugging Face tree (`gguf_weights -> _tree`), and
`mlx_repos()` searches the live Hub, so the committed-matrix comparison can only
be made against the Hub's answer of the hour. That comparison therefore carries
the **network** marker (`pytest.ini`; the #1000/#1002 seam): `make test-unit`
runs `-m "not network"` and collects ZERO nodes from it, and the network
pipeline (`make test-unit-network`) owns it. The hermetic pins in this file —
the parameter grid and the stamp, and the RAM ladder — read only the committed
fixture and stay in the gate, and the same live comparison also runs in `ci-unit`
through `make check-trend-list-matrix` (`scripts/trend_list_matrix.py --check`),
which is the documented guard of that fixture (`docs/ARCHITECTURE.md`).

The marker is spelled only on the decorator below, never quoted in prose: the
#1000 routing census in `tests/test_check_model_links.py` attributes the marker
TEXT to the next `def test_`, so a quoted mention here would claim a mark this
file's hermetic tests do not carry.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
from scripts import model_engine_pick as mp
from scripts import trend_list_matrix as tlm

FIXTURE = REPO / "tests" / "fixtures" / "trend-list-matrix.json"
GOLDEN = json.loads(FIXTURE.read_text())
IDS = [tlm.case_key(arch, vram, ram) for arch, vram, ram in tlm.CASES]


def _expected(arch: str, vram: float, ram: float) -> list[dict]:
    key = (arch, vram, ram)
    for case in GOLDEN["cases"]:
        if (case["arch"], case["vram"], case["ram"]) == key:
            return case["rows"]
    raise AssertionError(f"no committed list for {tlm.case_key(arch, vram, ram)}")


def test_the_committed_matrix_is_the_vram_ram_arch_grid():
    """The fixture is one case per parameter, for this registry's generated_utc."""

    # Given the vendored registry and the parameter grid llgenie --matrix accepts

    # When the committed cases are read
    got = [(c["arch"], c["vram"], c["ram"]) for c in GOLDEN["cases"]]

    # Then they are that grid, and the stamp is the vendored registry
    assert got == tlm.CASES
    assert GOLDEN["generated_utc"] == mp.load_registry().get("generated_utc")
    assert len(IDS) == len(set(IDS))


def test_ram_changes_which_cuda_16gb_model_is_served():
    """Same card and architecture, two RAM sizes: more RAM only ever ADDS a served row.

    The committed fixture is the source of truth: the RAM-sensitive row is the one
    whose server changes between 8 GB and 64 GB of RAM (a MoE whose download budget
    grows with system RAM). It is served at 64 GB and left with a reason at 8 GB.
    A model the store's `system_ram_min` floor keeps out of the 8 GB list (issue #669)
    is simply absent from it, so the two lists need not be identical: growing the RAM
    never removes a row and never takes a server away.
    """

    # Given the committed CUDA 16 GB lists
    tight = _expected("cuda", 16, 8)
    roomy = _expected("cuda", 16, 64)

    # When the rows that differ between the two RAM sizes are read
    by_model = {r["model"]: r for r in roomy}
    tight_by = {r["model"]: r for r in tight}

    # Then exactly the RAM-sensitive model is served at 64 GB and not at 8 GB
    gained = [m for m, r in by_model.items() if r["server"] and not (tight_by.get(m) or {}).get("server")]
    assert gained, "a MoE model must be served only when the RAM budget grows"
    for m in gained:
        assert by_model[m]["server"] and by_model[m]["tps"] > 0
        # a row that IS listed at 8 GB and serves nothing must say why (never a blank reason)
        if m in tight_by:
            assert tight_by[m]["server"] == "" and tight_by[m]["why"]

    # And growing the RAM only ADDS rows: the tight list is a prefix-safe subset, in order
    roomy_names = [r["model"] for r in roomy]
    assert [r["model"] for r in tight] == [m for m in roomy_names if m in tight_by]
    assert all(r["server"] or r["why"] for r in tight), "a listed row must be served or say why"


@pytest.mark.parametrize("arch,vram,ram", tlm.CASES, ids=IDS)
@pytest.mark.network
def test_trend_list_matches_the_committed_matrix(arch, vram, ram):
    """One (arch, vram, ram): the list matrix() returns is the committed list.

    LIVE (the network marker, issue #1020): `matrix()` sizes a model no engine
    can run off the live Hub tree, so this comparison belongs to the network seam
    (`make test-unit-network`), never to the hermetic gate.
    """

    # Given the committed rows for this card, RAM, and architecture
    expected = _expected(arch, vram, ram)

    # When llgenie's matrix runs with those three arguments
    got = tlm.trend_rows(mp.load_registry(), vram, ram, arch)

    # Then the models and their fastest fitting server match, in README order
    assert got == expected
    served = [row for row in got if row["server"]]
    assert [row["model"] for row in got] == [row["model"] for row in expected]
    assert all(row["tps"] >= 0 for row in served)


def test_committed_matrix_records_the_engine_variant_fingerprint():
    """GUARD (#1232): the committed fixture names the engine->variant signature
    it was rendered against, and that recorded value matches the current tree.

    The add/params seam: nothing couples an engine params/arch change to a
    re-render of the trend-list matrix, so a params delta that leaves the rows
    byte-identical (only the engine->variant map shifted) could land green through
    `check-trend-list-matrix`. The recorded fingerprint closes it: `--check`
    recomputes the signature from `containers/engines/params/*.json` and fails
    when it differs from the committed value, even if no row changed."""
    import shutil, tempfile
    from pathlib import Path

    # the committed fixture records a fingerprint (and the recorded value is what
    # the current params tree produces)
    m = tlm.mp  # the EXACT model_engine_pick module trend_list_matrix reads (not the
    # test module's `scripts.model_engine_pick` alias -- two import systems, #796)
    with m.hub_snapshot_file(tlm.SNAPSHOT):
        fresh = json.loads(json.dumps(tlm.build(), indent=2))
    assert GOLDEN.get(tlm.FINGERPRINT_KEY), "fixture must record the engine-variant fingerprint"
    assert fresh[tlm.FINGERPRINT_KEY] == GOLDEN[tlm.FINGERPRINT_KEY]

    # A TRUE arch delta (an engine gains a variant it did not have) must change
    # the matrix-consuming engine->variant map, so the recorded fingerprint is
    # stale until `make render-trend-list-matrix` re-pins it.
    orig_dir = m.PARAMS
    files = sorted(orig_dir.glob("*.json"))
    assert files, "there must be engine params to fingerprint"
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        for f in files:
            shutil.copy(f, d / f.name)
        # pick an engine without a vulkan variant (vLLM: cpu/cuda/rocm)
        chosen = next(p for p in d.glob("*.json") if json.loads(p.read_text()).get("engine") == "vLLM")
        p = json.loads(chosen.read_text())
        assert "vulkan" not in p["variants"], "test assumption: vLLM starts without a vulkan variant"
        p["variants"]["vulkan"] = dict(p["variants"]["cpu"])
        p["variants"]["vulkan"]["backend"] = "vulkan"
        chosen.write_text(json.dumps(p, indent=2) + "\n")
        old = m.PARAMS
        m.PARAMS = d
        try:
            assert tlm.fingerprint() != fresh[tlm.FINGERPRINT_KEY], \
                "an engine that gained a variant must change the matrix fingerprint"
            # and the stale fingerprint is exactly what fails `--check`/the render
            with m.hub_snapshot_file(tlm.SNAPSHOT):
                alt = json.dumps(tlm.build(), indent=2) + "\n"
            assert alt != FIXTURE.read_text()  # the committed fixture is now stale
        finally:
            m.PARAMS = old




def test_staleness_cells_are_empty_when_the_two_matrices_agree():
    """The read's fresh case: diffing the fixture against ITSELF names no cell."""
    assert tlm.staleness_cells(GOLDEN, GOLDEN) == []


def test_staleness_names_the_disagreeing_cells_and_exits_nonzero():
    """#2901 AC1: a drifted cell is NAMED — added, dropped, and changed rows each
    appear with their case key, and the fingerprint delta is its own named cell.

    The fixture/live pair here is synthetic (hermetic: `staleness_cells` is a pure
    dict diff, no Hub is touched); the exit-code contract around it is the read."""
    fixture = {
        tlm.FINGERPRINT_KEY: "fp-old",
        "cases": [
            {"arch": "cpu", "vram": 16.0, "ram": 32.0, "rows": [
                {"model": "kept-model", "size_gb": 9.0, "tps": 40.0},
                {"model": "gone-model", "size_gb": 12.0, "tps": 30.0},
            ]},
        ],
    }
    live = {
        tlm.FINGERPRINT_KEY: "fp-new",
        "cases": [
            {"arch": "cpu", "vram": 16.0, "ram": 32.0, "rows": [
                {"model": "kept-model", "size_gb": 13.0, "tps": 40.0},
                {"model": "new-model", "size_gb": 8.0, "tps": 55.0},
            ]},
        ],
    }
    cells = tlm.staleness_cells(fixture, live)
    key = tlm.case_key("cpu", 16.0, 32.0)
    by_case = {c["case"]: c for c in cells}
    assert key in by_case, f"the drifted cell {key} was not named: {cells}"
    cell = by_case[key]
    assert cell["added"] == ["new-model"]
    assert cell["dropped"] == ["gone-model"]
    assert cell["changed"] == [{"model": "kept-model", "fields": {"size_gb": "9.0 -> 13.0"}}]
    assert tlm.FINGERPRINT_KEY in by_case, "a changed fingerprint must be its own named cell"

    # exit-code contract, bounded (no live Hub): both unreadable paths exit 2, never 0.
    orig_fixture, orig_build = tlm.FIXTURE, tlm.build
    try:
        tlm.FIXTURE = REPO / "tests" / "fixtures" / "definitely-not-a-fixture.json"
        rc, cells2 = tlm.staleness_read()
        assert (rc, cells2) == (2, []), "an unreadable fixture must exit 2, never look fresh"
    finally:
        tlm.FIXTURE = orig_fixture
    try:
        def _boom() -> dict:
            raise RuntimeError("live trending unreachable")
        tlm.build = _boom
        rc, cells3 = tlm.staleness_read()
        assert (rc, cells3) == (2, []), "a live build that fails must exit 2, never look fresh"
    finally:
        tlm.build = orig_build


def test_staleness_refresh_issue_is_rendered_through_the_one_renderer():
    """#2901: the producer's issue carries the six-section shape and the dedupe marker
    on its first line — the body a reviewer reads and the producer remembers."""
    from scripts import issue_body, trend_staleness_issue as tsi

    cells = [{
        "case": tlm.case_key("cuda", 16.0, 32.0),
        "added": ["new-model"], "dropped": ["gone-model"],
        "changed": [{"model": "kept-model", "fields": {"size_gb": "9.0 -> 13.0"}}],
    }]
    fingerprint = tsi.drift_fingerprint(cells)
    assert fingerprint == tsi.drift_fingerprint(list(reversed(cells))), \
        "the fingerprint must be stable across cell ordering, or the producer re-files every tick"
    body = tsi.render_issue(cells, fingerprint)
    assert body.splitlines()[0] == f"{tsi.MARKER_PREFIX} {fingerprint} -->", \
        "the dedupe marker must be the body's first line"
    missing = issue_body.missing(body) if hasattr(issue_body, "missing") else None
    if missing is not None:
        assert missing == [], f"the refresh body is missing sections: {missing}"
    for needle in ("## Problem", "## Why it matters", "## How we fix it", "## Benefit",
                   "## Acceptance criteria", "## Technical", "render-trend-list-matrix",
                   "cuda/16.0/32.0", "new-model", "gone-model", "#2901"):
        assert needle in body, f"refresh body lacks {needle!r}"
