#!/usr/bin/env python3
"""The vendored registry is additive only (trending-local-llms issue #114).

`data/models.json` is replaced wholesale by the weekly `make sync-registry` PR.
`check-registry` validates the NEW file's shape but cannot see what the sync
LOST, so a sync that dropped a key, a measurement, a t/s or an engagement
counter would land silently and surface later as a thin trend list.
`scripts/registry_keys.py` fails on exactly that loss, and `make
check-registry` runs it (these tests are wired into `make test-unit`).
"""
from __future__ import annotations

import copy
import io
import json
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import registry_keys as RK  # noqa: E402


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
                 "date": "2026-10-10", "source_post": "https://lightbrd.com/u/status/1",
                 "likes": 120, "comments": 8, "views": 4000},
                {"engine": "MLX", "tps": "80", "hardware": "M4 Max", "quant": "4-bit",
                 "date": "2026-10-09", "source_post": "https://lightbrd.com/u/status/2",
                 "likes": 40, "views": 900},
            ],
            "why": "w",
            "engagement": {"likes": 160, "comments": 8, "views": 4900, "last_7d_likes": 160,
                           "seen_posts": [{"url": "https://lightbrd.com/u/status/1", "date": "2026-10-10"}],
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


def test_compare_reports_every_kind_of_loss():
    """RED on the pre-change tree: registry_keys.compare does not exist there."""
    prev = registry()

    # Given the committed registry and a copy that only GREW
    grown = copy.deepcopy(prev)
    grown["models"][0]["engines"].append(
        {"engine": "vLLM", "tps": "120", "hardware": "RTX 4070", "date": "2026-10-11",
         "source_post": "https://lightbrd.com/u/status/9"})
    grown["models"][0]["system_ram_min"] = "32GB"          # a new key
    grown["models"][0]["engines"][0]["likes"] = 200        # a risen counter

    # When  we compare them
    findings = RK.compare(prev, grown)

    # Then  nothing is reported — additive only
    assert findings == []

    cases = {}

    # Given a sync that dropped a whole model
    no_model = copy.deepcopy(prev)
    no_model["models"] = []
    cases["model gone"] = (no_model, "model 'm1' is gone")

    # Given a sync that dropped an OPTIONAL engagement key
    no_key = copy.deepcopy(prev)
    no_key["models"][0]["engagement"].pop("seen_posts")
    cases["optional key gone"] = (no_key, "key 'engagement.seen_posts' is gone")

    # Given a sync that dropped a key from EVERY measurement of the model (a key
    # that survives on one row is not a loss — the list is compared as a union)
    no_meas_key = copy.deepcopy(prev)
    for e in no_meas_key["models"][0]["engines"]:
        e.pop("quant")
    cases["measurement key gone"] = (no_meas_key, "key 'engines.quant' is gone")

    # And a key dropped from ONE row of several is NOT reported
    one_row = copy.deepcopy(prev)
    one_row["models"][0]["engines"][0].pop("quant")
    assert RK.compare(prev, one_row) == []

    # Given a sync that dropped a whole (engine, hardware) measurement group
    no_meas = copy.deepcopy(prev)
    no_meas["models"][0]["engines"] = [e for e in no_meas["models"][0]["engines"]
                                       if e["engine"] != "MLX"]
    cases["measurement group gone"] = (no_meas, "measurement MLX on M4 Max is gone")

    # Given a sync that LOWERED a t/s figure
    lowered = copy.deepcopy(prev)
    lowered["models"][0]["engines"][0]["tps"] = "40"
    cases["t/s lowered"] = (lowered, "t/s lowered 91 -> 40")

    # Given a sync that lowered an engagement counter
    counter = copy.deepcopy(prev)
    counter["models"][0]["engines"][0]["likes"] = 3
    cases["counter lowered"] = (counter, "likes lowered 120 -> 3")

    # Given a sync that dropped a backend / a supported engine / a format
    backend = copy.deepcopy(prev)
    backend["models"][0]["backends"] = ["CUDA"]
    cases["backend dropped"] = (backend, "backends lost ['Metal']")

    engine_list = copy.deepcopy(prev)
    engine_list["models"][0]["supported_engines"] = ["llama.cpp"]
    cases["supported engine dropped"] = (engine_list, "supported_engines lost ['MLX']")

    fmt = copy.deepcopy(prev)
    fmt["models"][0]["formats"] = [{"name": "GGUF", "hf": "a/m1-gguf"}]
    cases["format dropped"] = (fmt, "formats lost ['MLX']")

    # Given a sync whose engine registry lost an entry
    no_engine = copy.deepcopy(prev)
    no_engine["engines"].pop("MLX")
    cases["engine registry entry dropped"] = (no_engine, "engine registry entries gone: ['MLX']")

    # When  each lossy sync is compared
    for name, (cur, expected) in cases.items():
        findings = RK.compare(prev, cur)

        # Then  the loss is reported with the model/field named
        assert any(expected in f for f in findings), f"{name}: {findings}"


def test_real_vendored_registry_is_additive_against_itself():
    """The committed registry must report no loss against its own copy — the
    guard cannot be red on a clean tree."""

    # Given the real vendored registry
    reg = json.loads((ROOT / "data" / "models.json").read_text())

    # When  it is compared with itself
    findings = RK.compare(reg, copy.deepcopy(reg))

    # Then  nothing is lost
    assert findings == []


def test_cli_fails_a_lossy_sync_and_passes_an_additive_one(tmp_path):
    """The CLI is what `make check-registry` runs: exit 1 on loss, 0 when additive."""

    # Given a previous registry on disk and a lossy current copy
    prev_file = tmp_path / "prev.json"
    cur_file = tmp_path / "cur.json"
    prev_file.write_text(json.dumps(registry()))
    cur = registry()
    cur["models"][0]["engagement"].pop("seen_posts")
    cur_file.write_text(json.dumps(cur))

    # When  the guard runs against them
    code, _out, err = run_cli(["--prev", str(prev_file), "--cur", str(cur_file)])

    # Then  it exits non-zero and names the loss
    assert code == 1
    assert "engagement.seen_posts" in err
    assert "additive only" in err

    # And  an additive copy passes
    cur_file.write_text(json.dumps(registry()))
    code, out, _err = run_cli(["--prev", str(prev_file), "--cur", str(cur_file)])
    assert code == 0
    assert "OK: additive only" in out


def test_rules_and_wiring_are_documented():
    """The rule lives in AGENTS.md and both makes drive the guard."""

    # Given the repo rulebook and Makefile
    agents = (ROOT / "AGENTS.md").read_text()
    makefile = (ROOT / "Makefile").read_text()

    # When  the additive-only rule is looked up
    # Then  AGENTS.md states it and points at the guard
    assert "additive" in agents.lower()
    assert "registry_keys.py" in agents
    assert "check-registry-keys" in makefile
    assert "registry_keys.py" in makefile


def test_default_prev_is_a_git_revision_of_the_vendored_file():
    """The default comparison target is the committed copy, not a live fetch."""

    # Given the guard's default previous-registry spec
    # When  it is read from git
    prev = RK.read_prev(RK.DEFAULT_PREV)

    # Then  it is the committed registry and it parses
    assert prev["models"], RK.DEFAULT_PREV
    assert RK.DEFAULT_PREV == "HEAD:data/models.json"


def test_read_prev_accepts_a_file_path_too(tmp_path):
    """A plain file path is accepted (so the guard can be used against fixtures)."""

    # Given a registry file on disk
    p = tmp_path / "prev.json"
    p.write_text(json.dumps(registry()))

    # When  it is read as the previous registry
    prev = RK.read_prev(str(p))

    # Then  the parsed registry is returned
    assert prev["models"][0]["id"] == "m1"


def test_unreadable_previous_revision_fails_loudly():
    """A missing git revision is an error, never a silent pass."""

    # Given a revision that does not exist
    # When  the guard reads it
    with pytest.raises(SystemExit) as e:
        RK.read_prev("HEAD:no/such/file.json")

    # Then  it aborts with a message naming the cause
    assert "cannot read previous registry" in str(e.value)
