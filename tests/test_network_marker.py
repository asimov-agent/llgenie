#!/usr/bin/env python3
"""The pin for issue #1000: the unit gate must never execute a network-marked test.

`pytest.ini` registers the `network` marker and `scripts/unit_tests.py` builds the unit gate as
`-m "not network"` (the `ci-network` pipeline uses `-m network` on the SAME seam). These tests fail
closed: if the marker is renamed, if the gate drops the exclusion, or if a network-marked test
appears without the marker, something here goes red rather than the real call sneaking into the
default runtime path.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import unit_tests as ut  # noqa: E402


def test_the_network_marker_is_registered_in_pytest_ini():
    cfg = (REPO / "pytest.ini").read_text()
    markers = cfg.split("markers =", 1)[1]
    assert "network:" in markers, "the `network` marker must be registered in pytest.ini"


def test_the_unit_gate_runs_not_network():
    args = ut.argv(REPO)
    assert "-m" in args, args
    assert "not network" in args, args


def test_the_network_pipeline_runs_on_the_same_seam():
    args = ut.argv(REPO, marker="network")
    assert "-m" in args and "network" in args and "not network" not in args, args


def test_network_marked_tests_exist_and_are_inside_the_gate():
    """`-m "not network"` only excludes something if the marker is actually on real tests in the
    selection — an exclusion that excludes nothing is that marker name rusting away."""
    marked = []
    for doc in ut.select(REPO):
        hits = re.findall(r"@pytest\.mark\.network", (REPO / doc).read_text())
        if hits:
            marked.append((doc, len(hits)))
    assert marked, "no selected test carries @pytest.mark.network — the marker excludes nothing"
