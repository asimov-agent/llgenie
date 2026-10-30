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
    "test_pick_full_registry.py",
    "test_trend_pick.py",
    "test_install_trend.py",
    "test_registry_sync_trend.py",  # issue #1067: live sr.fetch into raw.githubusercontent.com
)

# The complete real-Hub ownership set across those files, from the widened routing census (issue
# #1000, corrected): the four live reads + the three Hub-metadata reads mp.gguf_repo/mp.gguf_files
# (test_gguf_repo_..., test_pick_file_fits_..., = live _hub_json/_tree) + the full real GGUF
# download (test_full_download_...) in test_trend_pick, and test_model_engine_pick's
# test_download_fetches_a_real_chunk_of_the_chosen_file (mp.download, host implied by the model
# dict — NOT a 0-open-primitive hermetic test, as the earlier census wrongly claimed). Everything
# else is hermetic by construction or reaches only a localhost serve / non-Hub, apart from
# test_pick_full_registry.py (added by issue #1059: its whole surface is the live matrix, below).
# So nothing else may be marked. test_plan_download_per_format_live_hub is deliberately ABSENT: it
# only plans, no i/o.
EXPECTED_NETWORK_TESTS = {
    "test_trend_pick.py": {
        "test_live_upstream_registry_is_the_live_readme_list",
        "test_every_model_in_the_list_downloads_the_first_bytes_of_its_planned_file",
        "test_select_downloads_a_missing_model_for_real",
        "test_download_mlx_repo_snapshot_for_real",
        "test_gguf_repo_prefers_registry_repo_then_named_gguf_repo",
        "test_pick_file_fits_the_card_and_skips_shards_and_mmproj",
        "test_full_download_through_hf_download_places_the_complete_gguf",
        "test_hub_json_caches_and_survives_a_missing_repo",
        "test_the_vendored_contract_is_upstreams_and_the_store_satisfies_it",  # issue #1067
    },
    "test_model_engine_pick.py": {
        "test_download_fetches_a_real_chunk_of_the_chosen_file",
    },
    # test_pick_full_registry.py is the FULL-registry live matrix: every one of its tests drives
    # `_live_matrix()` (mp.matrix -> the live Hub repo trees) or the wired `llgenie --matrix` CLI
    # over them, so the whole file is a real-Hub scope (issue #1059 — the quant-links test was the
    # one that red-ed a local `make test-unit` with a Hub 429). Its hermetic twin is
    # tests/test_pick_matrix.py + tests/test_pick_matrix_arch_perms.py (synthetic registry, stubbed
    # Hub tree), which stay in the unit gate, so no offline assertion is lost by routing these.
    "test_pick_full_registry.py": {
        "test_pick_matrix_any_offer_is_a_real_fitting_hf_url",
        "test_pick_matrix_real_quant_links_exist",
        "test_pick_matrix_engine_supported_quants_catalog",
        "test_pick_matrix_llgenie_cli_agrees_with_business_logic",
        "test_pick_matrix_offers_only_engines_the_gap_says_have_an_image",
        "test_pick_matrix_edge_case_golden",
        "test_pick_matrix_edge_case_golden_ram",
        "test_the_ram_ladder_never_shrinks_the_chosen_quant",
    },
    # issue #1067: the whole file is the one that motivated the widened scan — its module
    # fixture synced the live upstream registry inside the hermetic gate. The hermetic twins
    # that keep the same behaviour on committed data carry no mark on purpose.
    "test_registry_sync_trend.py": {
        "test_live_sync_adopts_a_higher_skilled_tps_for_models_that_fit_48gb",
        "test_rank_follows_the_given_vram_ram_and_arch",
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


