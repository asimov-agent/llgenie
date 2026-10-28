#!/usr/bin/env python3
"""The vendored registry is additive only (trending-local-llms issue #114, llgenie #668).

`data/models.json` is replaced wholesale by the weekly `make sync-registry` PR.
`check-registry` validates the NEW file's shape but cannot see what the sync
LOST, so a sync that dropped a model, key, engine or post would land silently
and surface later as a thin trend list. `scripts/registry_keys.py` fails on
exactly that loss, while the numbers the store RE-READS (a hardware label it
refined, a post re-attributed to a split model row, a counter re-scraped from
live X, a corrected t/s) are reported and do not freeze the sync (#534/#668).
These tests are wired into `make test-unit`.
"""
from __future__ import annotations

import copy
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

from scripts import registry_keys as RK

POST_1 = "https://lightbrd.com/u/status/1"
POST_2 = "https://lightbrd.com/u/status/2"
POST_3 = "https://lightbrd.com/u/status/3"


def registry() -> dict:
    """A registry shaped like the real one: a model with two measurements, the
    optional engagement keys, a per-measurement counter and a format list."""
    return {
        "generated_utc": "2026-10-13T22:37:08Z",
        "engines": {
            "llama.cpp": {"backend": "CUDA / CPU / Metal", "note": "x", "url": "https://github.com/ggml-org/llama.cpp"},
            "MLX": {"backend": "Metal", "note": "x", "url": "https://github.com/ml-explore/mlx"},
        },
        "models": [{
            "id": "m1", "name": "Model One", "full_name": "Model-One", "type": "LLM",
            "license": "Apache 2.0", "params": "27B", "hf": "a/m1",
            "formats": [{"name": "GGUF", "hf": "a/m1-gguf"}, {"name": "MLX", "hf": "a/m1-mlx"}],
            "vram_tier": "16GB", "vram_min": "12GB",
            "backends": ["CUDA", "Metal"],
            "supported_engines": ["llama.cpp", "MLX"],
            "engines": [
                {"engine": "llama.cpp", "tps": "91", "hardware": "RTX 4070", "quant": "Q4_K_M",
                 "date": "2026-10-10", "source_post": POST_1,
                 "likes": 120, "comments": 8, "views": 4000},
                {"engine": "MLX", "tps": "80", "hardware": "M4 Max", "quant": "4-bit",
                 "date": "2026-10-09", "source_post": POST_2,
                 "likes": 40, "views": 900},
            ],
            "why": "w",
            "engagement": {"likes": 160, "comments": 8, "views": 4900, "last_7d_likes": 160,
                           "seen_posts": [{"url": POST_1, "date": "2026-10-10"}],
                           "posts_7d": 2, "buzz_7d": 4.2, "score_7d": 4.2, "speed_bonus": 3.0,
                           "trend_score": 7.2},
            "last_seen": "2026-10-10",
        }],
    }


def run_cli(args: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = RK.main(args)
    return code, out.getvalue(), err.getvalue()


def test_a_dropped_non_format_name_is_not_a_loss():
    """A `formats[].name` that is not a format is upstream display text: the normaliser
    drops it and states the real format, and that is not the store losing data (#698)."""
    # Given a committed row that called its format after the model
    prev = registry()
    prev["models"][0]["formats"] = [{"name": "Model One", "hf": "a/m1"}]

    # When the sync normalises that row to GGUF
    cur = copy.deepcopy(prev)
    cur["models"][0]["formats"] = [{"name": "GGUF", "hf": "a/m1"}]

    # Then no finding calls the dropped display name a loss
    assert RK.compare(prev, cur) == []


def test_a_dropped_real_format_is_still_a_loss():
    """A format the pick can act on going away is what the guard exists for."""
    # Given a committed row offering GGUF and MLX
    prev = registry()

    # When the sync keeps only MLX
    cur = copy.deepcopy(prev)
    cur["models"][0]["formats"] = [{"name": "MLX", "hf": "a/m1-mlx"}]

    # Then the finding names the format that went away
    assert "m1: formats lost ['GGUF']" in RK.compare(prev, cur)


def test_compare_reports_every_kind_of_loss():
    """A model, key, engine, list entry, stated footprint or tracked post that goes
    away is a loss — the set llgenie ranks really got thinner."""
    prev = registry()

    # Given  the committed registry and a copy that only GREW
    grown = copy.deepcopy(prev)
    grown["models"][0]["engines"].append(
        {"engine": "vLLM", "tps": "120", "hardware": "RTX 4070", "date": "2026-10-11",
         "source_post": "https://lightbrd.com/u/status/9"})
    grown["models"][0]["system_ram_min"] = "32GB"          # a new key
    grown["models"][0]["engines"][0]["likes"] = 200        # a risen counter

    # When   we compare them
    findings = RK.compare(prev, grown)

    # Then   nothing is reported — additive only
    assert findings == []

    cases = {}

    # Given  a sync that dropped a whole model
    no_model = copy.deepcopy(prev)
    no_model["models"] = []
    cases["model gone"] = (no_model, "model 'm1' is gone")

    # Given  a sync that dropped an OPTIONAL engagement key
    no_key = copy.deepcopy(prev)
    no_key["models"][0]["engagement"].pop("seen_posts")
    cases["optional key gone"] = (no_key, "key 'engagement.seen_posts' is gone")

    # Given  a sync that dropped a key from EVERY measurement of the model (a key
    #        that survives on one row is not a loss — the list is compared as a union)
    no_meas_key = copy.deepcopy(prev)
    for e in no_meas_key["models"][0]["engines"]:
        e.pop("quant")
    cases["measurement key gone"] = (no_meas_key, "key 'engines.quant' is gone")

    # And    a key dropped from ONE row of several is NOT reported
    one_row = copy.deepcopy(prev)
    one_row["models"][0]["engines"][0].pop("quant")
    assert RK.compare(prev, one_row) == []

    # Given  a sync where an ENGINE keeps no measurement at all for the model — the unit
    #        `rank_engines` groups by, so losing it really does thin the trend list
    no_engine_rows = copy.deepcopy(prev)
    no_engine_rows["models"][0]["engines"] = [e for e in no_engine_rows["models"][0]["engines"]
                                              if e["engine"] != "MLX"]
    cases["engine measurement gone"] = (no_engine_rows, "no measurement left for engine 'MLX'")

    # Given  a sync that dropped a backend / a supported engine / a format
    backend = copy.deepcopy(prev)
    backend["models"][0]["backends"] = ["CUDA"]
    cases["backend dropped"] = (backend, "backends lost ['Metal']")

    engine_list = copy.deepcopy(prev)
    engine_list["models"][0]["supported_engines"] = ["llama.cpp"]
    cases["supported engine dropped"] = (engine_list, "supported_engines lost ['MLX']")

    fmt = copy.deepcopy(prev)
    fmt["models"][0]["formats"] = [{"name": "GGUF", "hf": "a/m1-gguf"}]
    cases["format dropped"] = (fmt, "formats lost ['MLX']")

    # Given  a sync whose engine registry lost an entry
    no_engine = copy.deepcopy(prev)
    no_engine["engines"].pop("MLX")
    cases["engine registry entry dropped"] = (no_engine, "engine registry entries gone: ['MLX']")

    # Given  a sync that lowered the MODEL-level stated footprint
    with_foot = registry()
    with_foot["models"][0]["weight_gb"] = "13GB (UD-Q3_K_XL)"
    lower_foot = copy.deepcopy(with_foot)
    lower_foot["models"][0]["weight_gb"] = "9GB (UD-Q3_K_XL)"
    cases["model footprint lowered"] = (lower_foot, "weight_gb lowered")
    prev = with_foot

    # Given  a sync that lowered a MEASUREMENT's stated footprint for the same post
    with_run_foot = copy.deepcopy(with_foot)
    with_run_foot["models"][0]["engines"][0]["weight_gb"] = "10GB Q4_K_M"
    lower_run_foot = copy.deepcopy(with_run_foot)
    lower_run_foot["models"][0]["engines"][0]["weight_gb"] = "4GB Q4_K_M"
    cases["measured run footprint lowered"] = (lower_run_foot, "post /status/1 weight_gb lowered")
    prev = with_run_foot

    # When   each lossy sync is compared
    for name, (cur, expected) in cases.items():
        findings = RK.compare(prev, cur)

        # Then   the loss is reported with the model/field named
        assert any(expected in f for f in findings), f"{name}: {findings}"


def test_compare_ignores_what_upstream_rewrites_in_place():
    """The rewrites that froze the weekly sync for 13 days (#534/#668) must pass."""

    prev = registry()

    # Given  a sync that REFINES the hardware label of a measurement (RTX 6000 -> RTX 6000 24GB)
    relabel = copy.deepcopy(prev)
    relabel["models"][0]["engines"][0]["hardware"] = "RTX 4070 12GB"

    # Given  a sync that UPGRADES a profile link to the real status URL of the same run
    profile_prev = registry()
    profile_prev["models"][0]["engines"][1]["source_post"] = "https://lightbrd.com/u"
    profile_cur = copy.deepcopy(profile_prev)
    profile_cur["models"][0]["engines"][1]["source_post"] = POST_2

    # Given  a sync that re-scrapes a counter LOWER (X engagement moves both ways)
    counter = copy.deepcopy(prev)
    counter["models"][0]["engines"][0]["likes"] = 3

    # Given  a sync that corrects a t/s figure for the same post
    restated = copy.deepcopy(prev)
    restated["models"][0]["engines"][0]["tps"] = "40"

    # Given  a sync whose model has no post in the window, so upstream rebuilt the
    #        `seen_posts` placeholder to an empty list
    emptied = copy.deepcopy(prev)
    emptied["models"][0]["engagement"]["seen_posts"] = []

    # When   each of them is compared
    for name, was, cur in (("hardware relabel", prev, relabel),
                           ("profile -> status URL", profile_prev, profile_cur),
                           ("counter re-scraped lower", prev, counter),
                           ("t/s re-stated", prev, restated),
                           ("seen_posts placeholder emptied", prev, emptied)):
        findings = RK.compare(was, cur)

        # Then   nothing is reported as lost
        assert findings == [], f"{name}: {findings}"


def test_a_tracked_post_is_one_identity_across_the_whole_store():
    """Upstream splits a model into per-run rows, so a post can move to another model
    id without the store losing the measurement."""

    # Given  the committed registry and a copy where the MLX measurement — and its
    #        seen_post — now live on a more specific model row
    prev = registry()
    moved = copy.deepcopy(prev)
    row = [e for e in moved["models"][0]["engines"] if e["engine"] == "MLX"][0]
    moved["models"][0]["engines"] = [e for e in moved["models"][0]["engines"] if e["engine"] != "MLX"]
    moved["models"][0]["engagement"]["seen_posts"] = []
    moved["models"].append({
        "id": "m1-mlx", "name": "Model One (MLX)", "vram_tier": "16GB", "vram_min": "12GB",
        "formats": [{"name": "MLX", "hf": "a/m1-mlx"}], "backends": ["Metal"],
        "supported_engines": ["MLX"], "engines": [row], "why": "w", "last_seen": "2026-10-10",
        "engagement": {"seen_posts": [{"url": POST_2, "date": "2026-10-09", "engine": "MLX"}]},
    })

    # When   it is compared
    findings = RK.compare(prev, moved)

    # Then   the post is still tracked store-wide, so it is not reported as gone (the old
    #        row losing its MLX measurement IS reported, and that is the real finding)
    assert not any("is gone from the store" in f for f in findings), findings
    assert any("no measurement left for engine 'MLX'" in f for f in findings), findings


def test_a_post_moved_to_the_seen_posts_placeholder_is_not_lost():
    """`engagement.seen_posts` records a post too: a measurement demoted to seen-only,
    or promoted back, is the same post in the same store."""

    # Given  a model with two llama.cpp runs, one of them demoted to a seen post
    prev = registry()
    prev["models"][0]["engines"].append(
        {"engine": "llama.cpp", "tps": "55", "hardware": "RTX 3060 12GB", "quant": "Q4_K_M",
         "date": "2026-10-05", "source_post": POST_3})
    cur = copy.deepcopy(prev)
    cur["models"][0]["engines"] = [e for e in cur["models"][0]["engines"]
                                   if e["source_post"] != POST_3]
    cur["models"][0]["engagement"]["seen_posts"].append(
        {"url": POST_3, "date": "2026-10-05", "engine": "llama.cpp", "tps": "55",
         "hardware": "RTX 3060 12GB"})

    # When   it is compared
    findings = RK.compare(prev, cur)

    # Then   nothing is lost — the post is still in the store, under an engine that still
    #        has a ranked measurement
    assert findings == []


def test_a_post_deleted_from_the_store_is_a_loss():
    """A tracked post that is nowhere in the new store is a measurement the store
    dropped — whatever model it was re-attributed to."""

    # Given  a sync where one post is gone from every model row and every placeholder
    prev = registry()
    gone = copy.deepcopy(prev)
    gone["models"][0]["engines"] = [e for e in gone["models"][0]["engines"] if e["source_post"] != POST_2]
    gone["models"][0]["engagement"]["seen_posts"] = [
        p for p in gone["models"][0]["engagement"]["seen_posts"] if p["url"] != POST_2]

    # When   it is compared
    findings = RK.compare(prev, gone)

    # Then   the post is reported as gone from the store
    assert any("post /status/2 is gone from the store" in f for f in findings), findings


def test_drift_reports_the_moved_numbers_that_are_not_a_loss():
    """The numbers that moved are still printed — a reviewer sees the store's new
    reading without having to diff the file by hand."""

    # Given  a sync that re-scraped a counter lower, re-stated a t/s, and whose
    #        seen_posts placeholder shrank
    prev = registry()
    cur = copy.deepcopy(prev)
    cur["models"][0]["engines"][0]["likes"] = 3
    cur["models"][0]["engines"][0]["tps"] = "40"
    cur["models"][0]["engagement"]["seen_posts"] = []

    # When   the guard reports the movement
    notes = RK.drift(prev, cur)

    # Then   each movement is named with both numbers, and none of them is a loss
    assert any("likes 120 -> 3 (live re-scrape)" in n for n in notes), notes
    assert any("t/s 91 -> 40 (same post, re-stated)" in n for n in notes), notes
    assert any("seen_posts 1 -> 0 (derived placeholder, rebuilt)" in n for n in notes), notes
    assert RK.compare(prev, cur) == []


def test_real_vendored_registry_is_additive_against_itself():
    """The committed registry must report no loss against its own copy — the
    guard cannot be red on a clean tree."""

    # Given  the real vendored registry
    reg = json.loads((ROOT / "data" / "models.json").read_text())

    # When   it is compared with itself
    findings = RK.compare(reg, copy.deepcopy(reg))

    # Then   nothing is lost
    assert findings == []


def test_cli_fails_a_lossy_sync_and_passes_an_additive_one(tmp_path):
    """The CLI is what `make check-registry-keys` runs: exit 1 on a loss, 0 when the
    sync only added rows or re-read a figure."""

    # Given  a previous registry on disk and a copy that dropped a model
    prev_file = tmp_path / "prev.json"
    cur_file = tmp_path / "cur.json"
    prev_file.write_text(json.dumps(registry()))
    cur = registry()
    cur["models"] = []
    cur_file.write_text(json.dumps(cur))

    # When   the guard runs against them
    code, _out, err = run_cli(["--prev", str(prev_file), "--cur", str(cur_file)])

    # Then   it exits non-zero and names the loss
    assert code == 1
    assert "model 'm1' is gone" in err
    assert "additive only" in err

    # And    an additive copy passes
    cur_file.write_text(json.dumps(registry()))
    code, out, _err = run_cli(["--prev", str(prev_file), "--cur", str(cur_file)])
    assert code == 0
    assert "OK: additive only" in out

    # And    a copy that only re-read a figure (counter down, t/s re-stated) also passes,
    #        with the movement printed as a NOTE instead of a LOSS
    drifted = registry()
    drifted["models"][0]["engines"][0]["likes"] = 3
    drifted["models"][0]["engines"][0]["tps"] = "40"
    cur_file.write_text(json.dumps(drifted))
    code, out, err = run_cli(["--prev", str(prev_file), "--cur", str(cur_file)])
    assert code == 0, err
    assert "NOTE: post /status/1 likes 120 -> 3 (live re-scrape)" in out
    assert "LOSS" not in err


def test_rules_and_wiring_are_documented():
    """The rule lives in AGENTS.md and both makes drive the guard."""

    # Given  the repo rulebook and Makefile
    agents = (ROOT / "AGENTS.md").read_text()
    makefile = (ROOT / "Makefile").read_text()

    # When   the additive-only rule is looked up
    # Then   AGENTS.md states it and points at the guard
    assert "additive" in agents.lower()
    assert "registry_keys.py" in agents
    assert "check-registry-keys" in makefile
    assert "registry_keys.py" in makefile


def test_default_prev_is_a_git_revision_of_the_vendored_file():
    """The default comparison target is the committed copy, not a live fetch."""

    # Given  the guard's default previous-registry spec
    # When   it is read from git
    prev = RK.read_prev(RK.DEFAULT_PREV)

    # Then   it is the committed registry and it parses
    assert prev["models"], RK.DEFAULT_PREV
    assert RK.DEFAULT_PREV == "HEAD:data/models.json"


def test_read_prev_accepts_a_file_path_too(tmp_path):
    """A plain file path is accepted (so the guard can be used against fixtures)."""

    # Given  a registry file on disk
    p = tmp_path / "prev.json"
    p.write_text(json.dumps(registry()))

    # When   it is read as the previous registry
    prev = RK.read_prev(str(p))

    # Then   the parsed registry is returned
    assert prev["models"][0]["id"] == "m1"


def test_unreadable_previous_revision_fails_loudly():
    """A missing git revision is an error, never a silent pass."""

    # Given  a revision that does not exist
    # When   the guard reads it
    with pytest.raises(SystemExit) as e:
        RK.read_prev("HEAD:no/such/file.json")

    # Then   it aborts with a message naming the cause
    assert "cannot read previous registry" in str(e.value)
