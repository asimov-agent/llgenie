"""The card gate and the card's list read MEASURED evidence, never the display label
(issue #669, OpenSpec change card-gate-measured-vram).

Two claims are pinned here, against the vendored store and the vendored README:

  gate  a model is admitted on a card only from evidence — a measurement that RAN on a card
        that size or smaller, its declared `vram_min`, or its stated `weight_gb` (the
        `weights-only` fit) — and `vram_tier` decides only for a row that states none of them;
  order the card's list is the README's tier-local `Up to N GB` ranking, then the rows it does
        not rank in the store's own (computed) trend order. The store's FILE POSITION is never
        read, so the same store in any order gives the same list.

Every placement the README publishes passes the gate at that tier — measured on the vendored
2026-10-27 store: 8 GB 13/13, 12 GB 15/15, 16 GB 18/18, 24 GB 20/21 (the missing one is a run
whose own hardware states 110 GB of system RAM, which the RAM floor refuses on a 64 GB host),
32 GB 20/21, 48 GB 20/21.
"""
from __future__ import annotations

import copy
import random
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import model_engine_pick as mp  # noqa: E402

README = REPO / "data" / "trending-README.md"
RAM = 64.0


@pytest.fixture()
def reg():
    """The vendored store, as the picker loads it."""
    return mp.load_registry()


def _readme_tiers() -> dict[int, list[str]]:
    """The README's own `### Up to N GB` tables, parsed straight from the markdown — the
    independent oracle, so a parser bug in production cannot agree with itself."""
    section = README.read_text().split("## 🔥 Trending for your card", 1)[1].split("\n## ", 1)[0]
    parts = re.split(r"^### Up to (\d+) GB$", section, flags=re.M)
    return {int(parts[i]): re.findall(r"^\| \[\*\*(.+?)\*\*\]", parts[i + 1], re.M)
            for i in range(1, len(parts), 2)}


def _model(**fields) -> dict:
    """A minimal store row: the picker reads these fields and invents nothing else."""
    return {"id": "fixture-model", "name": "Fixture Model", "engines": [], **fields}


def _run(card_gb: int, tps: str = "20", ram_gb: int | None = None) -> dict:
    hardware = f"{card_gb}GB VRAM" + (f" + {ram_gb}GB system RAM" if ram_gb else "")
    return {"engine": "llama.cpp", "tps": tps, "hardware": hardware}


def test_the_gate_admits_a_model_with_a_measured_run_on_a_smaller_card(reg):
    """A run on a 4 GB card is evidence the model runs on an 8 GB one, whatever it declares."""
    # Given a store row whose declared minimum is above the card but which was MEASURED on a
    # smaller card
    model = _model(vram_min="12GB", vram_tier="16GB", engines=[_run(4, ram_gb=32)])

    # When the gate is asked about an 8 GB card
    evidence = mp.card_evidence(model, 8)

    # Then the run admits it, and the declared minimum does not have to
    assert mp.ran_on_gb(model) == 4
    assert mp.vram_min_gb(model) == 12
    assert evidence == "run"
    assert mp.fits(model, 8, RAM) is True


def test_the_gate_never_reads_the_display_label_when_the_store_states_a_measurement():
    """`vram_tier` is a label: it may neither admit a model nor refuse one that ran here."""
    # Given a model with no run and a declared minimum above the card, whose label claims the
    # card is big enough
    label_says_small = _model(vram_min="48GB", vram_tier="8GB", weight_gb="60GB")
    # And a model that ran on a 4 GB card whose label claims a 96 GB bucket
    label_says_big = _model(vram_min="12GB", vram_tier="96GB", engines=[_run(4, ram_gb=32)])

    # When the gate is asked about an 8 GB card
    # Then the label admits nothing and refuses nothing — the measurement decides
    assert mp.card_evidence(label_says_small, 8) == ""
    assert mp.fits(label_says_small, 8, RAM) is False
    assert mp.card_evidence(label_says_big, 8) == "run"
    assert mp.fits(label_says_big, 8, RAM) is True


def test_the_weights_only_fit_admits_a_model_above_its_declared_minimum():
    """A model whose file fits the card is placed on it, labelled `weights-only` — upstream's
    own second kind of evidence."""
    # Given a model declaring 48 GB, whose weights are 3.5 GB, with no run at this size
    model = _model(vram_min="48GB", vram_tier="48GB", weight_gb="3.5GB", engines=[_run(24)])

    # When the gate is asked about an 8 GB card
    evidence = mp.card_evidence(model, 8)

    # Then it is admitted as the weights-only fit, not kept out by the declaration
    assert evidence == "weights"
    assert mp.fits(model, 8, RAM) is True


def test_the_system_ram_floor_still_applies():
    """The RAM half of the run's footprint is a hard floor."""
    # Given a run on a 4 GB card that names 32 GB of system RAM
    model = _model(vram_min="40GB", vram_tier="40GB", system_ram_min="128GB",
                   engines=[_run(4, ram_gb=32)])

    # When the gate is asked about a card that fits but a host with 16 GB of RAM, then 64 GB
    # Then the run's own RAM statement decides, not the model-level one
    assert mp.ram_floor_gb(model, "run", 8) == 32
    assert mp.fits(model, 8, 16) is False
    assert mp.fits(model, 8, 64) is True


def test_every_model_the_published_tier_table_places_is_admitted(reg):
    """The README's per-tier placement is the gate's oracle: it never places a model the gate
    refuses."""
    # Given the vendored store and the tier tables the README publishes
    by_name = {m["name"]: m for m in reg["models"]}
    tiers = _readme_tiers()

    # When every placed model is asked about its own tier
    refused = {tier: [name for name in names
                      if name in by_name and not mp.card_evidence(by_name[name], tier)]
               for tier, names in tiers.items()}

    # Then no tier places a model the card evidence refuses (the RAM floor is the separate
    # half, measured in `test_the_system_ram_floor_still_applies`)
    assert tiers, "the vendored README publishes no card tier"
    assert {tier: names for tier, names in refused.items() if names} == {}


def test_the_card_list_follows_the_published_tier_ranking(reg):
    """The card's order is upstream's tier-local ranking, not the store's global order."""
    # Given the vendored store and the published 8 GB tier table
    tiers = _readme_tiers()
    gb = 8

    # When the card's list is built
    rows = mp.trend_list(reg, gb, RAM)
    ranked = [r["name"] for r in rows if r["name"] in set(tiers[gb])]

    # Then the ranked rows are in the table's order, and that order is NOT the store's order
    assert ranked == [n for n in tiers[gb] if n in set(ranked)]
    assert ranked != [m["name"] for m in reg["models"] if m["name"] in set(ranked)]
    global_order = [m["name"] for m in reg["models"] if mp.fits(m, gb, RAM)]
    assert [r["name"] for r in rows] != global_order


def test_the_card_list_does_not_depend_on_the_store_file_order(reg):
    """The store's line numbers are not the answer: a reordered store gives the same list."""
    # Given the vendored store and a shuffled copy of the same rows
    shuffled = copy.deepcopy(reg)
    random.Random(669).shuffle(shuffled["models"])

    # When each builds the card's list
    for gb in (8, 16, 48):
        straight = [m["id"] for m in mp.trend_list(reg, gb, RAM)]
        mixed = [m["id"] for m in mp.trend_list(shuffled, gb, RAM)]

        # Then the ids are identical: the order was computed, never read off the file
        assert mixed == straight


def test_the_derived_key_reproduces_the_published_store_order(reg):
    """The key the store is sorted with is computable from its own fields, so reading the file's
    position adds nothing."""
    # Given the vendored store and the date its ranking was computed for
    today = mp.registry_today(reg)

    # When the stated fields of each row are turned into the store's sort key
    keys = [mp.trend_key(m, today)[:-1] for m in reg["models"]]  # without the id tie-break

    # Then the committed order is already sorted by it — 112 of 112 rows, non-decreasing
    assert len(keys) == len(reg["models"]) > 100
    assert keys == sorted(keys)
