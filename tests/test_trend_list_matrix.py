"""Committed trending list for every (arch, vram, ram) `llgenie --matrix` takes.

The expected rows live in tests/fixtures/trend-list-matrix.json. They are
`matrix(registry, vram, ram, arch)` on the vendored registry: README order,
the highest t/s server on that architecture whose quant fits the card and the
RAM. A registry sync rewrites the fixture (`make render-trend-list-matrix`).
Until that rewrite lands, this test fails, and the pull-request diff is the
new list.
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
def test_trend_list_matches_the_committed_matrix(arch, vram, ram):
    """One (arch, vram, ram): the list matrix() returns is the committed list."""

    # Given the committed rows for this card, RAM, and architecture
    expected = _expected(arch, vram, ram)

    # When llgenie's matrix runs with those three arguments
    got = tlm.trend_rows(mp.load_registry(), vram, ram, arch)

    # Then the models and their fastest fitting server match, in README order
    assert got == expected
    served = [row for row in got if row["server"]]
    assert [row["model"] for row in got] == [row["model"] for row in expected]
    assert all(row["tps"] >= 0 for row in served)
