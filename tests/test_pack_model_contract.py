"""The pack contract: one code path for multi-file model packs (issue #2909).

edge0-145b's checkpoint (Edge0/Edge0-145B-q3k) is a multi-file tree served as a DIRECTORY —
the registry's single pseudo-quant formats entry cannot fetch or gate it. This suite drives
the real functions end to end on hermetic fixtures (a fake `hf` downloader for the download
legs; no network, no engine, no Hub):

  manifest  the `formats[].pack` manifest is the fetch plan, malformed ones are refused;
  size      the pack is gated by the SUM of its manifest bytes;
  fetch     `scripts/hf_download.py`'s manifest mode fetches the whole file set in ONE
            resumable call: a partial is continued, a wrong size is re-fetched, a completed
            pack is not re-fetched at all;
  launch    `scripts/pack_contract.launch_env` binds every declared part and refuses a pack
            that is missing one, naming it; frozen params carry the contract.
"""
from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts import engine_skills as es
from scripts import hf_download as hd
from scripts import model_engine_pick as mp
from scripts import pack_contract as pc
from scripts import sync_registry as sr

# A hermetic pack record in the shape the trending-local-llms registry carries:
# one pseudo-quant formats entry PLUS the additive `pack` manifest (issue #2909).
PACK_MODEL = {
    "id": "edge0-145b",
    "name": "Edge0 145B",
    "hf": "Edge0-AI/Edge0",
    "formats": [{
        "name": "GGUF",
        "hf": "Edge0/Edge0-145B-q3k",
        "quant": "q3k",
        "pack": {
            "revision": "deadbeef",
            "files": [
                {"path": "model.json", "bytes": 100},
                {"path": "model-skeleton.gguf", "bytes": 100},
                {"path": "experts.bin", "bytes": 100},
                {"path": "tokenizer/tok.json", "bytes": 100},
            ],
        },
    }],
}


def _fake_hf(tmp_path: Path, body: str) -> str:
    """A stand-in `hf` CLI (HF_BIN) that materializes the requested files locally."""
    script = tmp_path / "fake-hf"
    script.write_text("#!/usr/bin/env python3\n" + body)
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return str(script)


CRASH_FIRST_HF = r"""
import pathlib, sys
argv = sys.argv[1:]
assert argv[0] == "download"
d = argv[argv.index("--local-dir") + 1]
names = argv[2:argv.index("--local-dir")]  # the manifest's file set, exactly
mark = pathlib.Path(d) / ".attempts"
n = 1 + (int(mark.read_text()) if mark.exists() else 0)
mark.write_text(str(n))
if n == 1:  # crash mid-download: only the first part lands
    f = pathlib.Path(d) / names[0]
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(b"x" * 100)
    sys.exit(1)
for name in names:  # complete: rewrite any wrong-size part, never a completed one
    f = pathlib.Path(d) / name
    if not f.exists() or f.stat().st_size != 100:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"x" * 100)
sys.exit(0)
"""

ALL_OK_HF = r"""
import pathlib, sys
argv = sys.argv[1:]
assert argv[0] == "download"
d = argv[argv.index("--local-dir") + 1]
names = argv[2:argv.index("--local-dir")]
mark = pathlib.Path(d) / ".attempts"
mark.write_text(str(1 + (int(mark.read_text()) if mark.exists() else 0)))
for name in names:
    f = pathlib.Path(d) / name
    if not f.exists() or f.stat().st_size != 100:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"x" * 100)
sys.exit(0)
"""


@pytest.fixture(autouse=True)
def _offline_retry(monkeypatch, tmp_path):
    """Hermetic: the fake downloader and no retry sleeps; the loop still runs MAX times."""
    monkeypatch.setenv("HF_RETRY_PAUSE", "0")
    monkeypatch.setenv("HF_POLL_SECONDS", "0.05")
    monkeypatch.setenv("HF_STALL_SECONDS", "5")
    monkeypatch.setenv("HF_MAX_RETRY", "4")


# --------------------------------------------------------------------------- manifest

def test_pack_manifest_shape_and_rejections():
    man = pc.manifest(PACK_MODEL)
    assert man is not None
    assert man["repo"] == "Edge0/Edge0-145B-q3k" and man["revision"] == "deadbeef"
    assert [f["path"] for f in man["files"]] == ["model.json", "model-skeleton.gguf",
                                                 "experts.bin", "tokenizer/tok.json"]
    assert pc.manifest_bytes(man) == 400
    # A non-pack record is no manifest at all.
    assert pc.manifest({"id": "x", "formats": [{"name": "GGUF", "hf": "a/b"}]}) is None
    # Malformed manifests never resolve into a half-fetch plan.
    for bad in ([], [{"path": "/absolute/x"}], [{"nope": 1}], [{"path": ""}], "not-a-list"):
        assert pc.manifest({"id": "x", "formats": [{"name": "GGUF", "hf": "a/b",
                                                    "pack": {"files": bad}}]}) is None
    assert pc.valid_files([{"path": "a", "bytes": 5}]) == [{"path": "a", "bytes": 5}]
    assert pc.valid_files(None) is None


def test_pack_gb_sizes_the_whole_file_set():
    assert pc.pack_gb(PACK_MODEL) == 400 / 1e9
    assert pc.pack_gb({"id": "x", "formats": [{"name": "GGUF", "hf": "a/b"}]}) is None
    # stated_budget_gb: a measurement's own footprint first (stated values are strings like
    # "640GB"), then the pack sum, then the model's stated weight_gb.
    assert mp.stated_budget_gb(PACK_MODEL) == 400 / 1e9
    assert mp.stated_budget_gb(PACK_MODEL, {"weight_gb": "7GB"}) == 7.0
    plain = {"id": "y", "weight_gb": "5GB", "formats": [{"name": "GGUF", "hf": "a/b"}]}
    assert mp.stated_budget_gb(plain) == 5.0


# --------------------------------------------------------------------------- plan + fetch

def test_plan_download_pack_fetches_the_manifest(tmp_path, monkeypatch):
    # Hermetic Hub replay substitute (issue #1080; the #1000 hub-pin guard): the pack plan is
    # computed from the declared manifest bytes, never from a live Hub listing — the snapshot
    # override answers any Hub read from a local recording.
    snapshot = tmp_path / "hub-snapshot.json"
    snapshot.write_text("{}")
    monkeypatch.setenv(mp.HUB_SNAPSHOT_ENV, str(snapshot))
    monkeypatch.setattr(mp, "_tree", lambda repo, rev="main": [])
    plan = mp.plan_download(PACK_MODEL, gb=500)
    assert plan is not None
    assert plan["pack"] is True and plan["dir"] is True and plan["path"] == ""
    assert plan["repo"] == "Edge0/Edge0-145B-q3k" and plan["revision"] == "deadbeef"
    assert plan["files"] == ["model.json", "model-skeleton.gguf", "experts.bin",
                             "tokenizer/tok.json"]
    assert plan["size"] == 400
    # The WHOLE pack must fit: no partial-pack plan (the manifest is atomic).
    monkeypatch.setattr(mp, "weight_budget_gb", lambda *a, **k: 1e-7)
    assert mp.plan_download(PACK_MODEL, gb=1) is None


def test_pack_manifest_download_is_resumable(tmp_path, monkeypatch):
    """A crash leaves a partial pack; the next run continues it and re-verifies sizes."""
    dest = tmp_path / "Edge0__Edge0-145B-q3k"
    dest.mkdir()
    monkeypatch.setenv("HF_BIN", _fake_hf(tmp_path, CRASH_FIRST_HF))
    man = pc.manifest(PACK_MODEL)
    assert man is not None
    man_path = pc.write_manifest(man, tmp_path / "pack.json")

    rc = hd.main([man["repo"], f"@{man_path}", str(dest), "edge0-145b (pack)"])
    attempts_first = (dest / ".attempts").read_text()  # attempt 1 crashed, loop retried
    assert rc == 0
    for f in man["files"]:
        assert (dest / f["path"]).read_bytes() == b"x" * 100

    # Resume proof: a completed pack is NOT fetched again (no new downloader attempt).
    (dest / ".attempts").write_text("9")
    assert hd.main([man["repo"], f"@{man_path}", str(dest), "edge0-145b (pack)"]) == 0
    assert (dest / ".attempts").read_text() == "9"

    # A part with the WRONG size is treated as not-present: the manifest re-fetches, whole.
    (dest / "experts.bin").write_bytes(b"short")
    monkeypatch.setenv("HF_BIN", _fake_hf(tmp_path, ALL_OK_HF))
    assert hd.main([man["repo"], f"@{man_path}", str(dest), "edge0-145b (pack)"]) == 0
    assert (dest / "experts.bin").read_bytes() == b"x" * 100


def test_pack_download_routes_through_the_manifest(tmp_path, monkeypatch):
    """scripts/model_engine_pick.download() fetches a pack plan through the manifest leg."""
    monkeypatch.setenv("HF_BIN", _fake_hf(tmp_path, ALL_OK_HF))
    root = tmp_path / "models"
    dest = mp.download(PACK_MODEL, gb=500, root=root)
    assert dest == root / "Edge0__Edge0-145B-q3k"
    assert (dest / "model.json").read_bytes() == b"x" * 100
    assert (dest / "tokenizer" / "tok.json").read_bytes() == b"x" * 100
    # The manifest is kept beside the pack: the sidecar the resume reads its contract from.
    sidecar = root / f"{PACK_MODEL['id']}.pack.json"
    assert json.loads(sidecar.read_text())["repo"] == "Edge0/Edge0-145B-q3k"


def test_malformed_pack_manifest_is_refused_before_any_byte(tmp_path, monkeypatch):
    calls = tmp_path / "calls"
    monkeypatch.setenv("HF_BIN", _fake_hf(tmp_path, "import sys; open(r'%s','w').write('ran'); sys.exit(0)" % str(calls)))
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"repo": "a/b", "files": []}))
    assert hd.main(["a/b", f"@{bad}", str(tmp_path / "d"), "x"]) == 2
    assert not calls.exists()  # the downloader was never invoked on a half manifest
    bad.write_text(json.dumps({"repo": "a/b", "files": [{"path": "/escape"}]}))
    assert hd.main(["a/b", f"@{bad}", str(tmp_path / "d"), "x"]) == 2


def test_pack_passes_the_registry_normaliser():
    """ADDITIVE only: a well-formed pack survives sync untouched; a malformed one is dropped loudly."""
    kept, note = sr.normalise_formats({"id": "m", "hf": "a/b",
                                       "formats": [{"name": "GGUF", "hf": "r/q",
                                                    "pack": {"files": [{"path": "a.bin", "bytes": 1}]}}]})
    assert kept[0]["pack"]["files"] == [{"path": "a.bin", "bytes": 1}] and note == ""
    kept, note = sr.normalise_formats({"id": "m", "hf": "a/b",
                                       "formats": [{"name": "GGUF", "hf": "r/q",
                                                    "pack": {"files": [{"path": "/bad"}]}}]})
    assert "pack" not in kept[0]
    assert "malformed pack manifest" in note


# --------------------------------------------------------------------------- launch

def _pack_dir(models_dir: Path) -> Path:
    d = models_dir / "Edge0__Edge0-145B-q3k"
    d.mkdir(parents=True, exist_ok=True)
    for part in PACK_SPEC["pack"]["parts"]:
        p = d / part
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"p")
    return d


PACK_SPEC = {
    "id": "edge0", "engine": "edge0", "backend": "cuda", "variant": "cuda",
    "model_contract": "pack",
    "pack": {"parts": ["model.json", "model-skeleton.gguf", "experts.bin", "tokenizer"],
             "config_env": {"MODEL_DIR": ".", "SKELETON": "model-skeleton.gguf",
                            "EXPERTS": "experts.bin"}},
}


def test_launch_env_binds_every_declared_part(tmp_path):
    d = _pack_dir(tmp_path)
    env = pc.launch_env(PACK_SPEC, str(d), tmp_path)
    assert all(x == "-e" for x in env[0::2])  # the wiring is ONLY docker -e pairs
    pairs = dict(kv.split("=", 1) for kv in env[1::2])
    assert pairs["MODEL_DIR"] == "/models/Edge0__Edge0-145B-q3k"
    assert pairs["SKELETON"] == "/models/Edge0__Edge0-145B-q3k/model-skeleton.gguf"
    assert pairs["EXPERTS"] == "/models/Edge0__Edge0-145B-q3k/experts.bin"
    # Every -e names a real part: nothing half-wired is ever served.
    assert len(pairs) == len(PACK_SPEC["pack"]["config_env"])


def test_launch_env_refuses_a_pack_missing_a_part_naming_it(tmp_path):
    d = _pack_dir(tmp_path)
    (d / "experts.bin").unlink()
    with pytest.raises(SystemExit) as e:
        pc.launch_env(PACK_SPEC, str(d), tmp_path)
    assert "experts.bin" in str(e.value)
    with pytest.raises(SystemExit) as e:  # a pack must be a local directory under models
        pc.launch_env(PACK_SPEC, str(tmp_path / "not-a-dir.gguf"), tmp_path)
    assert "pack directory" in str(e.value) or "pack model" in str(e.value)
    with pytest.raises(SystemExit):  # model_contract without parts is a params bug
        pc.launch_env({"id": "z", "model_contract": "pack"}, str(d), tmp_path)


def test_params_carry_the_pack_contract_only_for_declaring_variants(monkeypatch):
    monkeypatch.setattr(es, "_image_hash", lambda params, variant: "0deadbee")  # no Dockerfile needed
    params = {"id": "packeng", "engine": "packeng", "ref": "1", "pinned": "deadbeef",
              "variants": {
                  "cpu": {"backend": "cpu", "base": "b", "apt": [], "build_args": {},
                          "run_args": [], "port": 8080},
                  "cuda": {"backend": "cuda", "base": "b", "apt": [], "build_args": {},
                           "run_args": [], "port": 8080, "model_contract": "pack",
                           "pack": {"parts": ["a"], "config_env": {"A": "a"}}}}}
    plain = es.image_spec(params, "cpu")
    assert "model_contract" not in plain  # no current engine's spec or tag moves
    pack = es.image_spec(params, "cuda")
    assert pack["model_contract"] == "pack"
    assert pack["pack"]["parts"] == ["a"]


def test_resolve_local_hits_a_pack_directory(tmp_path):
    """A pack checkpoint under ~/models resolves as a directory (model.json manifest)."""
    d = tmp_path / "Edge0-AI__Edge0-145B-q3k"
    d.mkdir()
    (d / "model.json").write_text("{}")
    hit = mp.resolve_local({"id": "edge0-145b", "name": "Edge0 145B"}, root=tmp_path)
    assert hit == d
