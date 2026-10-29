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


# The HF/trend data-path files this lane routes (issue #1000). Ownership of the real-Hub tests is
# pinned HERE, deterministically, so the network pipeline's membership set cannot drift: a hermetic
# test marked `.network` silently loses coverage, and an unmarked real-Hub test escapes the gate.
DATA_PATH_FILES = (
    "test_native_engine_real.py",
    "test_interactive_tensorfold_real.py",
    "test_top_tier_serve.py",
    "test_strata_download.py",
    "test_strata_missing_hf.py",
    "test_model_engine_pick.py",
    "test_engine_bump.py",
    "test_pick_matrix.py",
    "test_pick_matrix_arch_perms.py",
    "test_trend_pick.py",
    "test_install_trend.py",
)

# The complete real-Hub ownership set across those files, from the routing census (issue #1000):
# ONLY test_trend_pick genuinely opens the Hub (each of these does real i/o, is named "for real" or
# "live", and carries no `urlopen` monkeypatch in its body). Everything else is hermetic by
# construction (0 open primitives) or reaches only a localhost serve / non-Hub, so nothing else may
# be marked. test_plan_download_per_format_live_hub is deliberately ABSENT: it only plans, no i/o.
EXPECTED_NETWORK_TESTS = {
    "test_trend_pick.py": {
        "test_live_upstream_registry_is_the_live_readme_list",
        "test_every_model_in_the_list_downloads_the_first_bytes_of_its_planned_file",
        "test_select_downloads_a_missing_model_for_real",
        "test_download_mlx_repo_snapshot_for_real",
    },
}


def test_the_network_membership_of_the_hf_data_path_files_is_exact():
    """The @pytest.mark.network set over the data-path files matches the routing census exactly.

    This is the "routing decision is pinned by a test" half the owner asked for in #1000: marked ==
    EXPECTED_NETWORK_TESTS, every file accounted for, and no file in the ownership set is absent. A
    future edit that marks a hermetic test `.network` (dropping unit coverage) or leaves a new
    real-Hub test unmarked (escaping the gate) changes this and the test reds with the file + test.
    """

    actual: dict[str, set[str]] = {f: set() for f in DATA_PATH_FILES}
    for filename in DATA_PATH_FILES:
        path = REPO / "tests" / filename
        lines = path.read_text().splitlines()
        for i, line in enumerate(lines):
            if "@pytest.mark.network" in line:
                # the decorated test is the NEXT `def test_...` line
                for nxt in lines[i + 1:]:
                    if nxt.startswith("def test_"):
                        name = nxt.split("(")[0][len("def "):].strip()
                        actual[filename].add(name)
                        break
                else:
                    raise AssertionError(f"{filename}:{i+1}: @pytest.mark.network marks nothing")

    # Only the files that carry marks are asserted; every OTHER data-path file must therefore be
    # mark-free (an added mark there adds a key and reds here), and every expected mark must exist.
    marked = {k: set(v) for k, v in actual.items() if v}
    assert marked == EXPECTED_NETWORK_TESTS, (
        f"network-membership drift:\n  actual-marks: {marked}\n  expected: {EXPECTED_NETWORK_TESTS}"
    )
    assert all(v == set() for f, v in actual.items() if f not in EXPECTED_NETWORK_TESTS), (
        "a data-path file NOT in the ownership set carries a @pytest.mark.network mark"
    )


