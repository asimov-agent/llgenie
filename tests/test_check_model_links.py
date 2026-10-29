#!/usr/bin/env python3
"""The committed model/GGUF links a test depends on must resolve (issue #1000).

Static half (this file's focus): parse the vendored data, require every catalog amount to be a real
`/resolve/<rev>/<file>` URL, and exit 0 when all are well-formed. The LIVE half — probing the real
Hub — runs only on demand (`LIVE=1`) and uses `tests/hub_probe.probe` as the ONE authority, never a
second implementation; that single-authority property is what the tester pins in the unit gate.

No network here: the static path only parses committed data.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import scripts.check_model_links_liveness as ml  # noqa: E402  (the real gate, never a copy)


def test_the_static_gate_collects_the_vendored_links():
    """The gate parses every committed model/GGUF link and finds none malformed."""

    # When  the vendored data is parsed
    links, defects = ml._collect()

    # Then  it finds a real set of links and no malformed one (the fixture data is current)
    assert len(links) >= 100, f"expected the vendored registry to carry hundreds of links, got {len(links)}"
    assert defects == [], f"malformed committed links: {defects}"


def test_the_static_check_exits_zero_on_current_data():
    """`make check-model-links` (default) is hermetic and passes on this tree."""

    # Given the gate as the CLI runs it
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "check_model_links_liveness.py"), "check"],
                       capture_output=True, text=True, cwd=REPO)

    # Then  it exits 0 and reports the count, with no network
    assert r.returncode == 0, r.stderr
    assert "static pass:" in r.stdout


def test_report_names_every_link_with_its_caller():
    """`make model-links-report` prints caller:url pairs from the vendored data."""

    # Given a parse of the committed data
    links, defects = ml._collect()

    # Then  report surfaces them as caller:url lines (fixture data, no network)
    out = ml._report(links, defects)
    assert out == 0


def test_a_live_limit_bounds_the_probe(monkeypatch):
    """`--limit N` runs at most N real probes, never the whole committed set.

    The network-scan pipeline gates on `LIVE=1 LIMIT=25`; an unbounded live run would probe all
    1321 committed links every day — a Hub rate-limit storm. The bound must be real, not a
    suggestion, so the workflow's first step is fast and decides this hermetically.
    """

    import types

    calls = {"n": 0}

    def _fake(url):
        calls["n"] += 1
        return types.SimpleNamespace(exists=True, detail="HTTP 200")

    monkeypatch.setattr(ml.hub_probe, "probe", _fake)
    links, defects = ml._collect()

    # When the live check is bounded to 3
    rc = ml._check(links, defects, live=True, limit=3)

    # Then it probes exactly 3 links (not all 1321) and passes
    assert rc == 0
    assert calls["n"] == 3

