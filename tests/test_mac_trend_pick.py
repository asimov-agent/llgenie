"""llgenie on an Apple-Silicon Mac: the trend list is the README list that fits the
unified memory, Metal engines (TensorFold, MLX, llama.cpp, ...) run natively, and
TensorFold is offered with its own MLX checkpoints (issue #114, OpenSpec
fix-mac-trend-pick-tensorfold).

The list is tested WITHOUT the interactive prompt: `llgenie --trend` prints the exact
rows `llgenie` asks from (both are `_print_trend` over `model_engine_pick.offer`), and
one pty test proves the interactive listing is byte-identical. Runs against the REAL
vendored data/models.json and the live Hugging Face API (no mocks of the Hub)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tests"))
import engine_image as ei  # noqa: E402
import engine_skills as es  # noqa: E402
import install_engine_launchers as iel  # noqa: E402
import model_engine_pick as mp  # noqa: E402
from ptydrive import Pty  # noqa: E402

SERVE = REPO / "scripts" / "llama_serve.py"
HUB_CACHE = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
MAC_GB = 48          # the reporter's M5 Pro: 48 GiB unified memory
BIG_MAC_GB = 128     # a Mac that holds TensorFold's Flash Next 2-bit checkpoint
FLASH_NEXT = "Qwen3.8-Flash-Next 125B"


def _env(tmp_path: Path, gb: int, backend: str = "metal") -> dict:
    env = {**os.environ, "LLAMA_MODELS_ROOT": str(tmp_path), "LLAMA_BACKEND": backend,
           "LLAMA_RAM_BYTES": str(gb * 2**30), "LLGENIE_SYSTEM_RAM_BYTES": str(gb * 2**30),
           "HOME": str(tmp_path / "home"), "XDG_CACHE_HOME": str(HUB_CACHE)}
    env.pop("LLGENIE_REGISTRY_SRC", None)
    return env


def _llgenie(tmp_path: Path, gb: int, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SERVE), *args], env=_env(tmp_path, gb),
                          stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=600)


def _offer(tmp_path: Path, gb: int) -> list[dict]:
    os.environ.pop("LLGENIE_REGISTRY_SRC", None)
    return mp.offer(mp.load_registry(), "metal", gb, root=tmp_path, ram_gb=gb)


def _trend_lines(out: str) -> list[str]:
    return [ln for ln in out.splitlines() if " trend " in ln]


# ---------------------------------------------------------------------------
# the host is metal, and Metal engines are native
# ---------------------------------------------------------------------------
def test_apple_silicon_host_is_metal_not_cpu(monkeypatch):
    """The list header said `cpu` on an M5 Pro: detect_server said metal, host_arch
    dropped it."""

    # Given detect_server reports an Apple-Silicon (metal) backend
    monkeypatch.setenv("LLAMA_BACKEND", "metal")

    # When llgenie asks for the host arch
    arch = mp.host_arch()

    # Then it is metal and Metal measurements count as this host's hardware
    assert arch == "metal"
    assert mp.HOST_TO_MEASURED["metal"] == "Metal"


def test_metal_engines_are_the_servable_skills_with_a_metal_install():
    # Given every engine skill

    # When the Metal engines are derived from the skills
    metal = mp.metal_engines()

    # Then they are the servable skills that install on metal (no benchmark harness)
    assert metal == {"tensorfold", "mlx", "llama.cpp", "llama.cpp-prism", "ollama", "litert"}
    assert "mlx-fast-bonsai2" not in metal  # servable: via (a harness, not a server)
    for sid in metal:
        assert es.native_allowed(es.get_skill(sid), "metal")


def test_metal_host_offers_only_native_metal_engines():
    # Given a metal host

    # When its engines are listed
    rows = {e["id"]: e for e in mp.host_engines("metal")}

    # Then every offered engine is native Metal (macOS never starts an image)
    assert rows
    assert {e["variant"] for e in rows.values()} == {"metal"}
    for sid in ("tensorfold", "mlx", "llama.cpp", "llama.cpp-prism", "ollama", "litert"):
        assert rows[sid]["variant"] == "metal", sid

    # And a container-only engine and the cuda/rocm-only engines are absent
    assert "vllm" not in rows
    assert {"strata", "sglang", "freetoken", "tensorrt-llm", "exllamav3-rocm"}.isdisjoint(rows)


def test_linux_hosts_never_get_a_metal_variant():
    # Given cuda / cpu Linux hosts

    # When their engines are listed
    variants = {(e["id"], e["variant"]) for arch in ("cuda", "rocm", "vulkan", "cpu")
                for e in mp.host_engines(arch)}

    # Then no engine is offered as metal there
    assert not [v for v in variants if v[1] == "metal"]


def test_tensorfold_image_is_cuda_only_and_built_by_linux_ci():
    """Metal cannot run in a container: TensorFold's image is the CUDA one, built and
    published by the Linux CI matrix; on a Mac it runs natively (uv tool install)."""

    # Given the generated TensorFold params and the CI image matrix
    params = es.generate_params(es.get_skill("tensorfold"))

    # When the CI matrix is computed
    ci = {(r["engine"], r["variant"]) for r in ei.matrix(ci=True)}

    # Then the only image is cuda and CI builds it; metal is a native install
    assert set(params["variants"]) == {"cuda"}
    assert ("tensorfold", "cuda") in ci and ("tensorfold", "metal") not in ci
    assert es._per_backend(es.get_skill("tensorfold")["install"], "metal") == [
        "uv tool install --force 'tensorfold @ git+{repo}.git@v{version}'"]


# ---------------------------------------------------------------------------
# the memory budget of unified memory
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("gb,want", [(48, 26.6), (128, 82.6), (16, 6.4), (8, 3.2)])
def test_metal_budget_is_the_gpu_working_set_minus_reserves(gb, want):
    # Given a Mac with `gb` GiB of unified memory

    # When the weight budget is computed (dense and MoE)
    dense, moe = mp.weight_budget_gb(gb, False, gb, "metal"), mp.weight_budget_gb(gb, True, gb, "metal")

    # Then it is 70% minus 7 GiB (floor 40%), and MoE adds nothing (no separate RAM)
    assert round(dense, 1) == want and moe == dense


# ---------------------------------------------------------------------------
# the list itself, tested without the prompt
# ---------------------------------------------------------------------------
def test_trend_on_a_48gb_mac_is_the_readme_list_with_metal_engines(tmp_path):
    """The reporter's list, fixed: header says metal, TensorFold is #1 for
    Qwen3.8-27B, Metal t/s figures are this host's, and Flash Next says exactly why."""

    # Given the vendored README list and a 48 GB Apple-Silicon Mac
    rows = _offer(tmp_path, MAC_GB)

    # When `llgenie --trend` prints it (no prompt)
    r = _llgenie(tmp_path, MAC_GB, "--trend")

    # Then the header names the metal backend, not cpu
    assert r.returncode == 0, r.stderr
    assert f"this card ({MAC_GB} GB, metal)" in r.stdout

    # And every printed row is an offer() row, in README order, numbered only where servable
    lines = _trend_lines(r.stdout)
    assert [ln.split("trend")[0] for ln in lines] and len(lines) == len(rows)
    n = 0
    for ln, row in zip(lines, rows):
        assert row["model"]["name"] in ln
        if row["why"]:
            assert ln.lstrip().startswith("--") and f"not here: {row['why']}" in ln
        else:
            n += 1
            assert ln.lstrip().startswith(f"{n}.") and row["engines"][0]["engine"] in ln

    # And Qwen3.8-27B is the first pick, on TensorFold natively, with its M5 Max figure
    pick = [x for x in rows if not x["why"]]
    assert pick[0]["model"]["name"] == "Qwen3.8-27B"
    top = pick[0]["engines"][0]
    assert (top["id"], top["variant"], top["use_format"], top["same_hw"]) == \
        ("tensorfold", "metal", "mlx-safetensors", True)
    assert "TensorFold 189 t/s" in lines[1] and "(Metal)" not in lines[1]


def test_flash_next_on_48gb_says_tensorfold_needs_more_memory(tmp_path):
    """Qwen3.8-Flash-Next 125B is the README #1 but cannot be picked on 48 GB: every
    TensorFold checkpoint (63+ GB) and every GGUF (68+ GB) is larger than the 26.6 GB a
    48 GB Mac can wire for the GPU, and Strata has no Metal backend."""

    # Given a 48 GB Mac
    rows = {r["model"]["name"]: r for r in _offer(tmp_path, MAC_GB)}

    # When the Flash Next row is built
    row = rows[FLASH_NEXT]

    # Then it is listed, not pickable, and names the TensorFold and GGUF sizes it lacks
    assert row["engines"] == [] and row["why"]
    assert "smallest TensorFold MLX is" in row["why"] and "smallest GGUF is" in row["why"]
    assert row["why"].endswith("> 27 GB this host can hold")
    smallest = mp.tensorfold_smallest(row["model"])
    assert smallest and smallest["repo"].startswith("TensorFold/Qwen3.8-Flash-Next-MLX-")
    assert smallest["size"] > mp.weight_budget_gb(MAC_GB, True, MAC_GB, "metal") * 2**30


def test_flash_next_is_number_one_with_tensorfold_on_a_128gb_mac(tmp_path):
    # Given a Mac whose GPU working set holds TensorFold's smallest Flash Next checkpoint
    rows = _offer(tmp_path, BIG_MAC_GB)

    # When the list is built
    pick = [r for r in rows if not r["why"]]

    # Then Flash Next is pick 1, on TensorFold natively, with a TensorFold checkpoint plan
    assert pick[0]["model"]["name"] == FLASH_NEXT
    eng = pick[0]["engines"][0]
    assert (eng["id"], eng["variant"]) == ("tensorfold", "metal")
    plan = mp.engine_plan(pick[0], eng)
    assert plan["repo"].startswith("TensorFold/Qwen3.8-Flash-Next-MLX-") and plan.get("dir")
    assert plan["size"] <= mp.weight_budget_gb(BIG_MAC_GB, True, BIG_MAC_GB, "metal") * 2**30


def test_select_1_on_a_48gb_mac_serves_qwen38_27b_with_tensorfold(tmp_path):
    # Given a 48 GB Mac with no local models

    # When `llgenie --select 1 --dry` runs (no prompt)
    r = _llgenie(tmp_path, MAC_GB, "--select", "1", "--dry")

    # Then it plans TensorFold's own MLX checkpoint and its native start script
    assert r.returncode == 0, r.stderr
    assert "Model  : Qwen3.8-27B" in r.stdout
    assert "Engine : TensorFold [metal]" in r.stdout
    assert "would download TensorFold/Qwen3.8-27B-MLX-" in r.stdout
    assert "llgenie-engine-tensorfold " in r.stdout


def test_select_flash_next_with_tensorfold_on_a_128gb_mac(tmp_path):
    # Given a 128 GB Mac

    # When `llgenie --select 1 --engine tensorfold --dry` runs
    r = _llgenie(tmp_path, BIG_MAC_GB, "--select", "1", "--engine", "tensorfold", "--dry")

    # Then Flash Next is served by TensorFold from a TensorFold checkpoint
    assert r.returncode == 0, r.stderr
    assert f"Model  : {FLASH_NEXT}" in r.stdout and "Engine : TensorFold [metal]" in r.stdout
    assert "would download TensorFold/Qwen3.8-Flash-Next-MLX-" in r.stdout


def test_mlx_only_model_finds_its_mlx_conversion_on_a_mac(tmp_path):
    """Ornith 1.5 was "not here" on the Mac: the registry names only the base repo;
    its MLX conversions (ornith-ai/Ornith-1.5-9B-MLX-*) are on the Hub."""

    # Given a 48 GB Mac
    rows = {r["model"]["name"]: r for r in _offer(tmp_path, MAC_GB)}

    # When the Ornith row is built
    row = rows["Ornith 1.5"]

    # Then it is servable on MLX natively with an MLX repo snapshot
    assert row["why"] == "", row["why"]
    eng = row["engines"][0]
    assert (eng["id"], eng["variant"], eng["use_format"]) == ("mlx", "metal", "mlx-safetensors")
    plan = mp.engine_plan(row, eng)
    assert "-mlx" in plan["repo"].lower() and plan.get("dir")


def test_interactive_listing_is_the_trend_listing(tmp_path):
    """The prompt shows exactly what --trend prints, so the non-interactive tests above
    cover the interactive list."""

    # Given the --trend output for a 48 GB Mac
    trend = _trend_lines(_llgenie(tmp_path, MAC_GB, "--trend").stdout)

    # When plain `llgenie --dry` runs in a terminal and reaches the prompt
    p = Pty([sys.executable, str(SERVE), "--dry"], _env(tmp_path, MAC_GB), cwd=str(REPO))
    try:
        p.expect(r"Pick model \[1\]: ", 600)
        listing = _trend_lines(p.out)
        p.send("1")
        p.expect(r"Pick inference server \[1\]: ", 300)
        p.send("1")
        assert p.wait(300) == 0, p.out
    finally:
        p.close()

    # Then the listing is identical and pick 1 is TensorFold on metal
    assert listing == trend
    assert "Engine : TensorFold [metal]" in p.out


# ---------------------------------------------------------------------------
# the native start script
# ---------------------------------------------------------------------------
def test_native_start_script_runs_the_skill_not_a_container():
    # Given TensorFold on metal

    # When its start script is rendered
    text = iel.native_launcher("tensorfold", python="/venv/bin/python")

    # Then it serves through the skill natively, never docker
    assert "serve tensorfold --backend metal --model \"$MODEL\" --port \"$PORT\"" in text
    assert "detect tensorfold --backend metal" in text
    assert " run --rm" not in text and "docker" not in text
    assert iel.MARKER in text  # make uninstall removes it


def test_ensure_on_metal_installs_natively_once_and_writes_the_script(tmp_path, monkeypatch):
    # Given TensorFold is not installed yet, then installed
    calls = []
    state = {"installed": False}
    pinned = es.pinned_version(es.get_skill("tensorfold"))

    def status(skill, backend, hw):
        calls.append(("detect", skill["id"], backend))
        return ({"state": "current", "installed": pinned, "wanted": pinned} if state["installed"]
                else {"state": "missing", "installed": None, "wanted": pinned})

    def install(skill, backend, hw, dry=False):
        calls.append(("install", skill["id"], backend))
        state["installed"] = True
        return 0

    monkeypatch.setattr(iel.es, "native_status", status)
    monkeypatch.setattr(iel.es, "install", install)

    # When llgenie ensures it twice
    assert iel.ensure(tmp_path, "tensorfold", "metal", build=False) == 0
    assert iel.ensure(tmp_path, "tensorfold", "metal", build=False) == 0

    # Then it is installed natively once, and its native start script is written
    assert calls.count(("install", "tensorfold", "metal")) == 1
    script = tmp_path / "llgenie-engine-tensorfold"
    assert os.access(script, os.X_OK) and "--backend metal" in script.read_text()
