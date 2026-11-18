"""Hermetic tests for the pack-format model-store + launch contract path
(OpenSpec pack-format-store-launch, issue edge0-145b).

The model store's planning and gating are the unit under test: pack_manifest
reads a registry formats[] entry, pack_plan sizes the download by the WHOLE file
set (not one file), and pack_weight_gb feeds the card gate's stated budget so a
pack is admitted/refused as a set. `download()` routes a dir plan through the
existing per-file hf path and returns the pack directory. The manifest-driven
fetch itself is proven end-to-end against a real fake-`hf` in
tests/test_hf_download_pack.py.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

from scripts import model_engine_pick as mp  # noqa: E402
from scripts.model_engine_pick import pack_manifest, pack_plan, pack_weight_gb  # noqa: E402


def _pack_model(**fields) -> dict:
    """A model row whose formats[] carries the edge0-style multi-file pack."""
    entry = {"name": "Edge0-145B", "hf": "Edge0/Edge0-145B-q3k",
             "revision": "abc123",
             "files": ["model-skeleton.gguf", "ple-fp8.gguf", "profile.bin",
                       "labels.bin", "mtp/next.gguf"]}
    entry.update(fields)
    return {"id": "edge0-145b", "name": "Edge0 145B", "engines": [],
            "formats": [entry]}


def test_pack_manifest_reads_the_file_list_and_repo():
    """A formats[] entry naming a `files` list is a pack: repo, revision, the whole set."""

    # Given a model whose formats[] entry names a multi-file checkpoint
    model = _pack_model()

    # When the pack manifest is read
    pm = pack_manifest(model)

    # Then it names the repo, the pinned revision and EVERY file of the set
    assert pm is not None
    repo, rev, files, entry = pm
    assert repo == "Edge0/Edge0-145B-q3k"
    assert rev == "abc123"
    assert files == model["formats"][0]["files"]
    assert entry is model["formats"][0]


def test_pack_manifest_none_for_a_single_file_model():
    """A normal gguf row (no `files` list) is NOT a pack."""

    # Given a normal single-file store row
    model = {"id": "m", "name": "M", "formats": [{"name": "GGUF", "hf": "Org/M"}]}

    # When the pack manifest is read
    # Then there is no pack declaration
    assert pack_manifest(model) is None


def test_pack_plan_sizes_by_the_whole_file_set(monkeypatch):
    """The download plan's size is the SUM of every named file, never one file."""

    # Given a pack model and a Hub tree whose files sum to 20 GB (largest is 8 GB)
    model = _pack_model()
    tree = [{"path": "model-skeleton.gguf", "size": 8 * 2**30, "type": "file"},
            {"path": "ple-fp8.gguf", "size": 6 * 2**30, "type": "file"},
            {"path": "profile.bin", "size": 4 * 2**30, "type": "file"},
            {"path": "labels.bin", "size": 1 * 2**30, "type": "file"},
            {"path": "mtp/next.gguf", "size": 1 * 2**30, "type": "file"}]
    monkeypatch.setattr(mp, "_tree", lambda repo, rev="main": tree)

    # When the pack is planned within a 15 GB card budget
    plan = pack_plan(model, 15 * 2**30, pm=pack_manifest(model))

    # Then the whole 20 GB set exceeds the budget, so there is NO plan
    assert plan is None

    # And on a 24 GB budget the WHOLE set fits and its size is the sum of all files
    plan = pack_plan(model, 24 * 2**30, pm=pack_manifest(model))
    assert plan is not None
    assert plan["dir"] is True
    assert plan["path"] == ""
    assert plan["size"] == 20 * 2**30
    assert plan["files"] == model["formats"][0]["files"]


def test_pack_plan_refuses_when_a_named_file_is_missing(monkeypatch):
    """A pack is not servable unless EVERY named file exists on the Hub."""

    # Given a pack model whose Hub tree lacks one manifest file
    model = _pack_model()
    tree = [{"path": "model-skeleton.gguf", "size": 8 * 2**30, "type": "file"},
            {"path": "profile.bin", "size": 4 * 2**30, "type": "file"}]
    monkeypatch.setattr(mp, "_tree", lambda repo, rev="main": tree)

    # When the pack is planned on a budget that would fit the present files
    plan = pack_plan(model, 100 * 2**30, pm=pack_manifest(model))

    # Then there is no plan: a partial checkout is not a servable checkpoint
    assert plan is None


def test_pack_weight_gb_is_the_whole_file_set():
    """The card gate sizes a pack by the SUM of its files, not a single file."""

    # Given a pack whose entry states per-file weights summing to 9 GB
    model = _pack_model(files_weight_gb=["4.0", "3.0", "1.5", "0.5"])

    # When the pack weight is computed
    # Then it is the whole-file-set sum
    assert pack_weight_gb(model) == 9.0


def test_stated_budget_uses_the_pack_set_for_the_card_gate():
    """`stated_budget_gb` returns the pack's whole-file-set weight for the gate."""

    # Given a pack and a plain single-file model
    pack = _pack_model(files_weight_gb=["5", "5"])
    single = {"id": "m", "name": "M", "formats": [{"name": "GGUF"}], "weight_gb": "3GB"}

    # When the stated budget is read for each
    # Then the pack is sized by its whole set and the single file by its weight_gb
    assert mp.stated_budget_gb(pack) == 10.0
    assert mp.stated_budget_gb(single) == 3.0


def test_plan_download_returns_a_pack_plan_for_a_pack_model(monkeypatch):
    """plan_download routes a pack-format row through pack_plan, sized by the set."""

    # Given a pack model whose Hub files fit an 8 GB card budget (sum <= budget)
    model = _pack_model()
    tree = [{"path": "model-skeleton.gguf", "size": 3 * 2**30, "type": "file"},
            {"path": "ple-fp8.gguf", "size": 1 * 2**30, "type": "file"},
            {"path": "profile.bin", "size": 1 * 2**30, "type": "file"},
            {"path": "labels.bin", "size": 1 * 2**30, "type": "file"},
            {"path": "mtp/next.gguf", "size": 1 * 2**30, "type": "file"}]
    monkeypatch.setattr(mp, "_tree", lambda repo, rev="main": tree)

    # When plan_download resolves it for the gguf pack format on a 16 GB card (fits)
    plan = mp.plan_download(model, 16, 64, "gguf", "cuda")

    # Then it is the whole-set pack dir plan, never a single-file gguf pick
    assert plan is not None
    assert plan["dir"] is True
    assert plan["size"] == 7 * 2**30
    assert plan["files"] == model["formats"][0]["files"]
    assert plan["pack_layout"] == {}


def test_write_pack_config_wires_named_parts_into_one_engine_config(tmp_path):
    """The launch-contract seam writes the pack's named parts to an engine config file."""

    # Given a pack directory on disk (a downloaded multi-file checkpoint)
    pdir = tmp_path / "Edge0-145B-q3k"
    pdir.mkdir(parents=True)
    for rel in ("model-skeleton.gguf", "ple-fp8.gguf", "profile.bin", "labels.bin", "mtp"):
        (pdir / rel).parents[0].mkdir(parents=True, exist_ok=True)
        (pdir / rel).touch()
    layout = {"model": "model-skeleton.gguf", "ple": "ple-fp8.gguf",
              "profile": "profile.bin", "labels": "labels.bin", "mtp": "mtp/"}

    # When the engine config is written from the pack dir and the declared layout
    cfg_path = mp.write_pack_config(pdir, layout)
    import json as _json
    cfg = _json.loads(cfg_path.read_text())

    # Then every named part is wired to its absolute path under the pack dir, in ONE file
    assert cfg["model_dir"] == str(pdir.resolve())
    assert cfg["parts"]["model"] == str(pdir / "model-skeleton.gguf")
    assert cfg["parts"]["ple"] == str(pdir / "ple-fp8.gguf")
    assert cfg["parts"]["profile"] == str(pdir / "profile.bin")
    assert cfg["parts"]["labels"] == str(pdir / "labels.bin")
    assert cfg["parts"]["mtp"] == str(pdir / "mtp")
    assert cfg["layout"] == layout


def test_download_writes_the_pack_config_into_the_pack_dir(tmp_path, monkeypatch):
    """download() of a pack plan writes llgenie-pack-config.json into the pack directory.

    # Given a pack model and a plan for it (whole-directory, declared layout),
    # When  download() runs it through the REAL hf path (fake-`hf` writes the files),
    # Then  every named file lands in the pack dir,
    # And   the launch-contract config wiring the named parts is written there too.
    """
    import json as _json
    script_dir = Path(__file__).resolve().parent
    fake_hf = script_dir / "fixtures" / "fake_hf.py"
    layout = {"model": "model-skeleton.gguf", "ple": "ple-fp8.gguf", "profile": "profile.bin"}
    model = _pack_model(layout=layout)
    plan = {"repo": "Edge0/Edge0-145B-q3k", "revision": "abc123", "path": "", "dir": True,
            "files": ["model-skeleton.gguf", "ple-fp8.gguf"],
            "size": 7 * 2**30, "pack_layout": layout}
    monkeypatch.setattr(mp, "_tree", lambda repo, rev="main": [
        {"path": "model-skeleton.gguf", "size": 3 * 2**30, "type": "file"},
        {"path": "ple-fp8.gguf", "size": 4 * 2**30, "type": "file"}])

    # (the gguf venv ships `hf`, but we must point EVERY download at the fake so the
    #  run is hermetic; monkeypatch download()'s env to force HF_BIN on the child)
    mon_env = dict(__import__("os").environ)
    monkeypatch.setenv("HF_BIN", str(fake_hf))
    monkeypatch.setenv("FAKE_HF_MODE", "pack")
    monkeypatch.setenv("HF_POLL_SECONDS", "0.2")
    monkeypatch.setenv("HF_RETRY_PAUSE", "0.1")
    monkeypatch.setenv("HF_MAX_RETRY", "2")

    out = mp.download(model, 16, tmp_path, "gguf", "cuda", plan=plan)

    # Then the pack dir holds every named file AND the wiring config
    assert out == tmp_path / "Edge0__Edge0-145B-q3k"
    assert (out / "model-skeleton.gguf").is_file()
    assert (out / "ple-fp8.gguf").is_file()
    cfg = _json.loads((out / "llgenie-pack-config.json").read_text())
    assert cfg["parts"]["model"] == str(out / "model-skeleton.gguf")
    assert cfg["parts"]["ple"] == str(out / "ple-fp8.gguf")
