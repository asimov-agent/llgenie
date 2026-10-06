"""Strata gets exactly the GGUF files its own setup.py names (OpenSpec
fix-engine-model-download-map).

`llgenie` -> Qwen3.8-Flash-Next 125B -> Strata used to download Unsloth's UD-IQ1_M
(3 shards, 75 GB), a file Strata's setup refuses. These tests pin the fix against
Strata's REAL setup.py at the engine's pinned commit (fetched once per session),
the live Hugging Face Hub at Strata's pinned revisions, the real hf downloader
(scripts/hf_download.py -> `hf download --revision`) and the interactive llgenie in
a pseudo-terminal. No mocks.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tests"))
import model_engine_pick as mp  # noqa: E402
import strata_models as sm  # noqa: E402
from ptydrive import Pty  # noqa: E402

SERVE = REPO / "scripts" / "llama_serve.py"
PARAMS = REPO / "containers" / "engines" / "params" / "strata.json"
HUB_CACHE = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
GIB = 2**30
ISTA = "ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF"
# what setup.py --yes installs, by RAM (setup.py main(), step 2): IQ3_XXS from 60 GB
EXPECTED = {
    8: ("qwen", "Q2_0"), 32: ("qwen", "Q2_0"), 48: ("qwen", "Q2_0"), 59: ("qwen", "Q2_0"),
    60: ("qwen", "IQ3_XXS"), 64: ("qwen", "IQ3_XXS"), 128: ("qwen", "IQ3_XXS"),
}


@pytest.fixture(scope="session")
def strata_src(tmp_path_factory) -> Path:
    """Strata's source at the skill's pinned commit (the commit the image builds)."""
    return sm.checkout(tmp_path_factory.mktemp("strata") / "src")


@pytest.fixture(scope="session")
def setup_py(strata_src):
    """Strata's own setup.py, imported (its main() only runs as __main__)."""
    return sm.load_setup(strata_src)


def _model() -> dict:
    return next(m for m in mp.load_registry()["models"] if m["id"] == "qwen3.8-flash-next-125b")


def _env(tmp_path: Path, ram_gb: int, **extra) -> dict:
    env = {**os.environ, "LLAMA_MODELS_ROOT": str(tmp_path), "LLAMA_BACKEND": "cuda",
           "LLAMA_RAM_BYTES": str(16 * GIB), "LLGENIE_SYSTEM_RAM_BYTES": str(ram_gb * GIB),
           "HOME": str(tmp_path / "home"), "XDG_CACHE_HOME": str(HUB_CACHE), **extra}
    env.pop("LLGENIE_REGISTRY_SRC", None)
    return env


def _shard_set(root: Path, family: str, size: str, only: int | None = None) -> list[Path]:
    """Placeholder files named like a downloaded Strata choice (repo dir/subdir/name)."""
    fam = mp.strata_map()["families"][family]
    out = []
    for i, f in enumerate(mp.strata_files(family, size), 1):
        if only is not None and i != only:
            continue
        p = root / fam["repo"].replace("/", "__") / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"GGUF")
        out.append(p)
    return out


# ---------------------------------------------------------------------------
# the vendored map IS Strata's setup.py
# ---------------------------------------------------------------------------
def test_vendored_map_matches_strata_setup_py_at_the_pinned_commit(strata_src, tmp_path):
    # Given Strata at the pinned commit, When the map is checked, Then it is identical
    assert sm.main(["check", "--src", str(strata_src)]) == 0
    # and a drifted copy is caught
    bad = json.loads(sm.OUT.read_text())
    bad["models"]["IQ3_XXS"]["ram_gb"] = 1
    (tmp_path / "m.json").write_text(json.dumps(bad, indent=2) + "\n")
    assert sm.main(["check", "--src", str(strata_src), "--out", str(tmp_path / "m.json")]) == 1


def test_map_pinned_commit_is_the_image_commit():
    params = json.loads(PARAMS.read_text())
    s = mp.strata_map()
    assert s["pinned"] == params["pinned"] and s["ref"] == params["ref"]


def test_map_tables_equal_setup_py_tables(setup_py):
    s = mp.strata_map()
    assert list(s["families"]) == list(setup_py.FAMILIES)          # setup's order: its default first
    assert list(s["models"]) == list(setup_py.MODELS)
    assert s["hf_revisions"] == setup_py.HF_REVISIONS
    for fam, d in s["families"].items():
        assert setup_py.hf(d["repo"]) + d["subdir"] == setup_py.FAMILIES[fam]["hf"]


# ---------------------------------------------------------------------------
# model name -> Strata's choice -> exact files
# ---------------------------------------------------------------------------
def test_the_registry_model_is_the_one_strata_serves():
    assert mp.strata_serves(_model())
    others = [m for m in mp.load_registry()["models"] if m["id"] != "qwen3.8-flash-next-125b"]
    assert not any(mp.strata_serves(m) for m in others)


@pytest.mark.parametrize("ram,want", sorted(EXPECTED.items()))
def test_choice_is_setup_py_default_for_the_ram(ram, want):
    assert mp.strata_choice(ram) == want


def test_every_choice_file_name_is_what_setup_py_builds_and_maps_back(setup_py):
    """For every (family, size) setup.py offers: our shard names == setup.model_file(),
    our count == setup.model_shards(), and setup.gguf_choice(first shard) names the same
    choice: the --family/--model llgenie passes the engine."""
    for fam, d in setup_py.FAMILIES.items():
        for size, md in setup_py.MODELS.items():
            if fam not in md.get("families", ("qwen", "swift")):
                continue
            files = mp.strata_files(fam, size)
            assert [Path(f).name for f in files] == [setup_py.model_file(d, size, i)
                                                     for i in range(1, setup_py.model_shards(d, size) + 1)]
            assert setup_py.gguf_choice(Path(files[0]).name) == (fam, size)
            assert Path(files[0]).name in mp.strata_first_shards()


def test_downloaded_folder_is_accepted_by_setup_py_gguf_dir(setup_py, tmp_path):
    """setup.py --gguf-dir <folder> --family F --model M on the folder llgenie downloads
    into finds exactly the planned shards and reports no problem."""
    for ram in (48, 64):
        family, size = mp.strata_choice(ram)
        shards = _shard_set(tmp_path / str(ram), family, size)
        folder = shards[0].parent
        fam = setup_py.FAMILIES[family]
        got = setup_py.gguf_dir_shards(folder, fam, size)
        assert got == shards
        assert setup_py.gguf_dir_problem(folder, got[0], fam, size) is None


def test_the_old_unsloth_ud_iq1_m_is_refused_by_strata_and_never_planned(setup_py):
    old = "Qwen3.8-Flash-Next-UD-IQ1_M-00001-of-00003.gguf"
    assert setup_py.gguf_unsupported(old) == "UD-IQ1_M" and setup_py.gguf_choice(old) is None
    for ram in EXPECTED:
        plan = mp.plan_download(_model(), 16, ram, "gguf", "cuda", engine="strata")
        assert "UD-IQ1_M" not in json.dumps(plan)
        assert setup_py.gguf_choice(Path(plan["path"]).name) == mp.strata_choice(ram)


@pytest.mark.parametrize("ram", [48, 64])
def test_plan_is_every_shard_from_strata_repo_at_its_pinned_revision_live_hub(ram):
    family, size = mp.strata_choice(ram)
    plan = mp.plan_download(_model(), 16, ram, "gguf", "cuda", engine="strata")
    fam = mp.strata_map()["families"][family]
    assert plan["repo"] == fam["repo"] == ISTA
    assert plan["revision"] == fam["revision"] == mp.strata_map()["hf_revisions"][ISTA]
    assert plan["files"] == mp.strata_files(family, size) and len(plan["files"]) == 2
    assert plan["path"] == plan["files"][0] and plan["strata"] == {"family": family, "model": size}
    tree = {f["path"]: int(f["size"]) for f in mp._tree(ISTA, plan["revision"]) if f.get("type") == "file"}
    assert plan["size"] == sum(tree[f] for f in plan["files"])
    # the published size setup.py states (download_gb, decimal GB) within 3%
    assert abs(plan["size"] / 1e9 - mp.strata_map()["models"][size]["download_gb"]) < 0.03 * plan["size"] / 1e9


def test_strata_plan_ignores_other_engines_and_formats():
    m = _model()
    assert mp.plan_download(m, 16, 64, "mlx-safetensors", "cuda", engine="strata") is None
    other = next(x for x in mp.load_registry()["models"] if x["id"] == "qwen3-8b")
    assert mp.plan_download(other, 16, 64, "gguf", "cuda", engine="strata") is None
    # llama.cpp for the same model keeps its own (generic) plan, never Strata's
    generic = mp.plan_download(m, 16, 64, "gguf", "cuda", engine="llama.cpp")
    assert generic and generic["repo"] != ISTA and "revision" not in generic


# ---------------------------------------------------------------------------
# offer(): Strata's plan + local copy, separate from the format's generic plan
# ---------------------------------------------------------------------------
def test_offer_gives_strata_its_own_plan_and_llama_cpp_its_own(tmp_path):
    rows = {r["model"]["id"]: r for r in mp.offer(mp.load_registry(), "cuda", 16, root=tmp_path, ram_gb=64)}
    row = rows["qwen3.8-flash-next-125b"]
    strata, llama = row["engines"][0], row["engines"][1]
    assert (strata["id"], llama["id"]) == ("strata", "llama.cpp")
    assert mp.engine_plan(row, strata)["path"] == "IQ3_XXS/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.gguf"
    assert mp.engine_plan(row, llama)["repo"] == "unsloth/Qwen3.8-Flash-Next-GGUF"
    assert mp.engine_local(row, strata) is None


def test_complete_local_set_is_reused_partial_and_unsupported_are_not(tmp_path):
    # a partial set (shard 1 only) and Unsloth's UD-IQ1_M set: neither is a Strata model here
    _shard_set(tmp_path, "qwen", "IQ3_XXS", only=1)
    u = tmp_path / "unsloth__Qwen3.8-Flash-Next-GGUF" / "UD-IQ1_M"
    u.mkdir(parents=True)
    for i in (1, 2, 3):
        (u / f"Qwen3.8-Flash-Next-UD-IQ1_M-0000{i}-of-00003.gguf").write_bytes(b"GGUF")
    assert mp.strata_local(tmp_path, 64) is None
    # a complete Q2_0 set is reused even on a 64 GB host (no 71 GB download for IQ3_XXS) ...
    q2 = _shard_set(tmp_path, "qwen", "Q2_0")
    assert mp.strata_local(tmp_path, 64) == q2[0]
    # ... and this host's own choice wins once it is complete too
    full = _shard_set(tmp_path, "qwen", "IQ3_XXS")
    assert mp.strata_local(tmp_path, 64) == full[0]
    assert mp.strata_local(tmp_path, 48) == q2[0]
    row = next(r for r in mp.offer(mp.load_registry(), "cuda", 16, root=tmp_path, ram_gb=64)
               if r["model"]["id"] == "qwen3.8-flash-next-125b")
    assert mp.engine_local(row, row["engines"][0]) == full[0] and mp.engine_plan(row, row["engines"][0]) is None


# ---------------------------------------------------------------------------
# the download: real hf downloader at the pinned revision, every shard
# ---------------------------------------------------------------------------
def test_download_fetches_the_first_bytes_of_every_shard_at_the_pinned_revision(tmp_path, monkeypatch):
    monkeypatch.setenv("LLGENIE_DOWNLOAD_MAX_BYTES", "4096")
    plan = mp.plan_download(_model(), 16, 64, "gguf", "cuda", engine="strata")
    out = mp.download(_model(), 16, tmp_path, engine="strata", plan=plan)
    assert out == tmp_path / ISTA.replace("/", "__") / plan["path"]
    for f in plan["files"]:
        p = tmp_path / ISTA.replace("/", "__") / f
        assert p.stat().st_size == 4096 and p.read_bytes()[:4] == b"GGUF", f


def test_hf_downloader_uses_the_pinned_revision_for_real(tmp_path):
    """scripts/hf_download.py with HF_REVISION runs `hf download --revision <sha>` and
    places the file: a small file of Strata's repo at Strata's pinned revision."""
    rev = mp.strata_map()["hf_revisions"][ISTA]
    name = "tensor-allocation/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.rco-allocation.txt"
    size = next(int(f["size"]) for f in mp._tree(ISTA, rev) if f["path"] == name)
    env = {**os.environ, "HF_REVISION": rev, "HF_STALL_SECONDS": "120"}
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "hf_download.py"), ISTA, name, str(tmp_path),
                        "strata-rev", "0", str(size)], env=env, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    assert (tmp_path / name).stat().st_size == size
    log = (tmp_path / "strata-rev.progress.log").read_text()
    assert f"@ {rev}" in log


def test_download_passes_the_revision_to_the_hf_downloader(tmp_path):
    """mp.download() of a Strata plan hands HF_REVISION to scripts/hf_download.py: a
    tiny plan of one small file of Strata's repo, downloaded in full."""
    rev = mp.strata_map()["hf_revisions"][ISTA]
    name = "tensor-allocation/Qwen3.8-Flash-Next-GSQ-RCO-Q2_0-00001-of-00002.rco-allocation.txt"
    plan = {"repo": ISTA, "revision": rev, "path": name, "files": [name], "size": 0}
    out = mp.download(_model(), 16, tmp_path, engine="strata", plan=plan)
    assert out.is_file() and out.stat().st_size > 0
    assert f"@ {rev}" in (out.parent.parent / "qwen3.8-flash-next-125b.progress.log").read_text()


# ---------------------------------------------------------------------------
# the engine start: setup.py gets the choice the files are
# ---------------------------------------------------------------------------
def _pre_launch_args(strata_src: Path, model: Path) -> subprocess.CompletedProcess:
    """The image's pre_launch with Strata's real setup.py, the final setup run replaced
    by an echo of its arguments (the engine itself needs the image and a GPU)."""
    p = json.loads(PARAMS.read_text())["variants"]["cuda"]["pre_launch"]
    p = p.replace("/opt/llgenie/engines/strata/src", str(strata_src)).replace("{model}", str(model))
    p = p.replace("{port}", "11434").replace("{host}", "0.0.0.0")
    p = p.replace("py/bin/python setup.py", "echo ARGS").replace("py/bin/python", sys.executable)
    return subprocess.run(["bash", "-euo", "pipefail", "-c", p], capture_output=True, text=True, timeout=120)


@pytest.mark.parametrize("ram", [48, 64])
def test_pre_launch_names_the_downloaded_choice(strata_src, tmp_path, ram):
    family, size = mp.strata_choice(ram)
    first = _shard_set(tmp_path, family, size)[0]
    r = _pre_launch_args(strata_src, first)
    assert r.returncode == 0, r.stderr
    args = r.stdout.split("ARGS", 1)[1].split()
    assert args[args.index("--gguf-dir") + 1] == str(first.parent)
    assert args[args.index("--family") + 1] == family and args[args.index("--model") + 1] == size
    assert "--yes" in args and "--no-start" in args


def test_pre_launch_refuses_a_file_strata_cannot_run(strata_src, tmp_path):
    bad = tmp_path / "Qwen3.8-Flash-Next-UD-IQ1_M-00001-of-00003.gguf"
    bad.write_bytes(b"GGUF")
    r = _pre_launch_args(strata_src, bad)
    assert r.returncode != 0 and "ARGS" not in r.stdout
    assert "is not a Strata model file" in r.stderr


# ---------------------------------------------------------------------------
# the interactive llgenie: pick 1 (the 125B) -> 1 (Strata)
# ---------------------------------------------------------------------------
def _interactive(tmp_path: Path, ram: int, engine: str = "1") -> str:
    p = Pty([sys.executable, str(SERVE), "--dry"], _env(tmp_path, ram), cwd=str(REPO))
    try:
        p.expect(r"Pick model \[1\]: ", 300)
        p.send("1")
        p.expect(r"Engines for Qwen3.8-Flash-Next 125B", 120)
        p.expect(r"Pick inference server \[1\]: ", 120)
        p.send(engine)
        assert p.wait(300) == 0, p.out
    finally:
        p.close()
    return p.out


@pytest.mark.parametrize("ram", [48, 64])
def test_interactive_pick_strata_downloads_strata_files_and_starts_strata_on_them(tmp_path, ram):
    family, size = mp.strata_choice(ram)
    files = mp.strata_files(family, size)
    out = _interactive(tmp_path, ram)
    assert "Engine : Strata [cuda]" in out
    assert f"would download {ISTA}/{files[0]} (2 files)" in out
    for f in files:
        assert f"(dry)   {ISTA}/{f}" in out
    assert "unsloth" not in out.split("Engines for")[1] and "UD-IQ1_M" not in out
    first = tmp_path / ISTA.replace("/", "__") / files[0]
    assert re.search(r"Command: \S*llgenie-engine-strata " + re.escape(str(first)) + " 11434", out), out


def test_interactive_pick_llama_cpp_for_the_same_model_gets_its_own_files(tmp_path):
    out = _interactive(tmp_path, 64, engine="2")
    assert "Engine : llama.cpp [cuda]" in out
    assert "would download unsloth/Qwen3.8-Flash-Next-GGUF/" in out and ISTA not in out.split("Engines for")[1]


def test_interactive_reuses_a_complete_local_strata_set(tmp_path):
    first = _shard_set(tmp_path, "qwen", "IQ3_XXS")[0]
    out = _interactive(tmp_path, 64)
    listing = out.split("Pick model")[0]
    assert next(l for l in listing.splitlines() if "Qwen3.8-Flash-Next 125B" in l).endswith("[local]")
    assert "would download" not in out and f"llgenie-engine-strata {first} 11434" in out
