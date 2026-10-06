"""llgenie trend pick by default, vendored registry, manual mode (issue #105,
OpenSpec feat-trend-pick-default).

Runs against the REAL vendored data/models.json; the Hub tests call the live
Hugging Face API (no mocks)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tests"))
import model_engine_pick as mp  # noqa: E402
import sync_registry as sr  # noqa: E402
from ptydrive import Pty  # noqa: E402

VENDORED = REPO / "data" / "models.json"
SERVE = REPO / "scripts" / "llama_serve.py"


# One Hub answer cache for the whole session (llgenie caches Hub lookups on disk):
# every llgenie subprocess below gets its own HOME but shares this cache, so the
# suite asks the Hub once per repo instead of once per run (avoids HTTP 429).
HUB_CACHE = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")


def _env(tmp_path: Path, backend: str, gb: int, **extra) -> dict:
    env = {**os.environ, "LLAMA_MODELS_ROOT": str(tmp_path), "LLAMA_BACKEND": backend,
           "LLAMA_RAM_BYTES": str(gb * 2**30), "HOME": str(tmp_path / "home"),
           "XDG_CACHE_HOME": str(HUB_CACHE), **extra}
    env.pop("LLGENIE_REGISTRY_SRC", None)
    return env


def test_default_registry_is_the_vendored_file(monkeypatch):
    # Given no LLGENIE_REGISTRY_SRC
    monkeypatch.delenv("LLGENIE_REGISTRY_SRC", raising=False)
    # When the registry is loaded
    reg = mp.load_registry()
    # Then it is data/models.json and it validates
    assert reg == json.loads(VENDORED.read_text())
    assert sr.validate(VENDORED.read_bytes())["models"]
    assert sr.check(VENDORED) == 0


README = REPO / "data" / "trending-README.md"


def _readme_rows() -> list[tuple[str, int]]:
    """(name, VRAM GB) of the vendored upstream README "Most loved" table, parsed
    straight from the markdown: the list a user reads on GitHub."""
    import re
    section = README.read_text().split(sr.MOST_LOVED, 1)[1].split("\n## ", 1)[0]
    rows = []
    for line in section.splitlines():
        m = re.match(r"^\| \[\*\*(.+?)\*\*\]", line)
        if m:
            cells = [c.strip() for c in line.split(" | ")]
            vram = next(c for c in cells if re.fullmatch(r"\d+GB", c))
            rows.append((m.group(1), int(vram[:-2])))
    return rows


def _offer(tmp_path: Path, backend: str, gb: int) -> list[dict]:
    os.environ.pop("LLGENIE_REGISTRY_SRC", None)
    return mp.offer(mp.load_registry(), backend, gb, root=tmp_path)


def test_sync_writes_valid_registry_and_rejects_invalid(tmp_path, capsys):
    # Given a valid source (the vendored file + its README) and an invalid one
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"engines": {"x": {}}, "models": [{"id": "m"}]}))
    dest = tmp_path / "out" / "models.json"
    # When each is synced into a temp target
    assert sr.sync(str(VENDORED), dest, str(README)) == 0
    # Then both are copied byte for byte and a second sync is a no-op
    assert dest.read_bytes() == VENDORED.read_bytes()
    assert (dest.parent / "trending-README.md").read_text() == README.read_text()
    assert sr.sync(str(VENDORED), dest, str(README)) == 0
    assert "unchanged" in capsys.readouterr().out
    # and the invalid one is rejected without touching the target
    assert sr.sync(str(bad), dest, str(README)) == 1
    assert dest.read_bytes() == VENDORED.read_bytes()
    assert sr.check(bad) == 1


def test_sync_rejects_a_registry_whose_order_is_not_the_readme(tmp_path):
    # Given the vendored registry with its first two models swapped
    data = json.loads(VENDORED.read_text())
    data["models"][0], data["models"][1] = data["models"][1], data["models"][0]
    swapped = tmp_path / "swapped.json"
    swapped.write_text(json.dumps(data))
    # When it is synced against the README
    # Then it is rejected: llgenie's list must be the README's list in the README's order
    assert sr.sync(str(swapped), tmp_path / "out" / "models.json", str(README)) == 1
    assert not (tmp_path / "out" / "models.json").exists()


def test_readme_copy_passes_and_a_modified_copy_is_rejected(tmp_path):
    """The business rule, both ways, against copies of the README (the vendored file
    is never touched). A byte-for-byte copy matches the registry and is accepted. A
    copy with the rows reordered, a copy with a row removed, and a copy whose top
    engine was renamed are each rejected, and the rejection names the change."""
    data = json.loads(VENDORED.read_text())
    good = tmp_path / "good.md"
    good.write_text(README.read_text())

    # the good copy: same models, same order, and every best engine the README names
    sr.check_readme_matches(data, good.read_text())
    assert sr.sync(str(VENDORED), tmp_path / "out" / "models.json", str(good)) == 0
    best = sr.readme_best(good.read_text(), "CUDA t/s (best)")
    assert best["Qwen3.8-Flash-Next 125B"] == "Strata"
    assert best["Qwen3.8-27B"] == "DFlash2"

    # a reordered copy: the first two rows swapped
    lines = good.read_text().splitlines(keepends=True)
    rows = [i for i, l in enumerate(lines) if l.startswith("| [**")]
    lines[rows[0]], lines[rows[1]] = lines[rows[1]], lines[rows[0]]
    reordered = tmp_path / "reordered.md"
    reordered.write_text("".join(lines))
    with pytest.raises(ValueError, match="!= README 'Most loved' order"):
        sr.check_readme_matches(data, reordered.read_text())
    assert sr.sync(str(VENDORED), tmp_path / "out2" / "models.json", str(reordered)) == 1
    assert not (tmp_path / "out2" / "models.json").exists()

    # a copy with a model removed
    dropped = tmp_path / "dropped.md"
    dropped.write_text("".join(l for i, l in enumerate(lines) if i != rows[0]))
    with pytest.raises(ValueError, match="!= README 'Most loved' order"):
        sr.check_readme_matches(data, dropped.read_text())

    # a copy whose best CUDA engine was renamed to one the registry does not list
    renamed = tmp_path / "renamed.md"
    renamed.write_text(good.read_text().replace("[Strata](https://github.com/Niko1221/Strata)",
                                                "[NotAnEngine](https://github.com/Niko1221/Strata)", 1))
    with pytest.raises(ValueError, match="README CUDA t/s \\(best\\) names 'NotAnEngine'"):
        sr.check_readme_matches(data, renamed.read_text())
    assert sr.sync(str(VENDORED), tmp_path / "out3" / "models.json", str(renamed)) == 1


def test_readme_links_answer_and_a_broken_copy_is_caught():
    """Every link in the README "Most loved" table answers: the Hugging Face model
    pages and the GitHub engine repos. A copy of the README with one link pointed at
    a repo that does not exist is rejected, and the rejection names that link."""
    links = sr.readme_links(README.read_text())
    assert links and all(l.startswith(("https://huggingface.co/", "https://github.com/")) for l in links)
    assert sr.check_links(links) == []
    broken = README.read_text().replace("https://github.com/Niko1221/Strata",
                                        "https://github.com/Niko1221/this-repo-does-not-exist-404", 1)
    dead = sr.check_links(sr.readme_links(broken))
    assert len(dead) == 1 and "this-repo-does-not-exist-404" in dead[0]


def test_live_upstream_registry_is_the_live_readme_list():
    """Live GitHub: upstream data/models.json is exactly the README "Most loved" list."""
    data = sr.validate(sr.fetch(sr.UPSTREAM))
    sr.check_readme_matches(data, sr.fetch(sr.UPSTREAM_README).decode())


def test_vendored_registry_is_the_vendored_readme_list():
    # Given the vendored registry and the README it was synced with
    data = json.loads(VENDORED.read_text())
    # Then the models are the README "Most loved" rows, same names, same order, same VRAM
    assert [(m["name"], int(mp._num(m["vram_tier"]))) for m in data["models"]] == _readme_rows()


@pytest.mark.parametrize("backend,gb", [("cuda", 16), ("cuda", 24), ("cpu", 16), ("rocm", 8),
                                        ("vulkan", 48), ("cpu", 2)])
def test_llgenie_list_is_the_readme_list_that_fits_the_card(tmp_path, backend, gb):
    """Every README model whose VRAM fits the card is listed, in README order;
    nothing else is listed. A row that cannot run here stays and says why."""
    # Given the README "Most loved" list
    want = [name for name, vram in _readme_rows() if vram <= gb]
    # When llgenie builds its list for the host
    rows = _offer(tmp_path, backend, gb)
    # Then it is exactly the README models that fit, in README order
    assert [r["model"]["name"] for r in rows] == want
    import engine_image as ei
    for r in rows:
        if r["why"]:
            assert not r["engines"] or r["local"] is None, r
            continue
        # a servable row: every engine has an enabled image for this host and a format
        # it reads that llgenie can get (local copy or a fitting download plan);
        # order = same hardware, other hardware, supported-only, then t/s
        assert r["engines"]
        for e in r["engines"]:
            assert e["use_format"] in e["formats"]
            assert mp.engine_plan(r, e) or mp.engine_local(r, e), (r["model"]["name"], e)
        assert all(e["variant"] in (backend, "cpu") and not ei.disabled(e["id"], e["variant"]) for e in r["engines"])
        keys = [(e["rank"], -e["tps"]) for e in r["engines"]]
        assert keys == sorted(keys)


RAM64 = str(64 * 2**30)


def test_card_16gb_list_on_this_readme(tmp_path, monkeypatch):
    """The concrete 16 GB cuda list for the vendored README (2026-10-05), 64 GB RAM:
    all 11 README models with VRAM <= 16 GB, in README order, every one selectable
    (nvidia-smi's 15.99 GiB counts as 16 GB); 18/24/48 GB models are absent."""
    monkeypatch.setenv("LLGENIE_SYSTEM_RAM_BYTES", RAM64)
    rows = _offer(tmp_path, "cuda", 15.9921875)
    names = [r["model"]["name"] for r in rows]
    assert names == [n for n, v in _readme_rows() if v <= 16]
    assert names == ["Qwen3.8-Flash-Next 125B", "Qwen3.8-27B", "Bonsai 2 27B", "RavenX-Conjecture-Qwen3-8B-MLX",
                     "Qwen3.6-35B-A3B", "Qwen3 8B", "Gemma 4 12B", "Qwen3 14B", "Gemma 4 E2B", "Llama 3.1 8B",
                     "DeepSeek R1 1.5B"]
    assert not {"Qwen 3.6 27B", "Muse Glimmer 30B", "Ornith 1.5"} & set(names)
    assert all(r["why"] == "" for r in rows), [(r["model"]["name"], r["why"]) for r in rows]
    # each row's first engine + the format llgenie fetches for it
    first = {r["model"]["name"]: (r["engines"][0]["id"], r["engines"][0]["use_format"]) for r in rows}
    assert first["Qwen3.8-Flash-Next 125B"] == ("strata", "gguf")        # 124 t/s on an RTX 4090, its own engine
    assert first["RavenX-Conjecture-Qwen3-8B-MLX"] == ("mlx", "mlx-safetensors")
    assert first["Gemma 4 E2B"] == ("litert", "litertlm")
    assert first["Llama 3.1 8B"] == ("vllm", "safetensors") or first["Llama 3.1 8B"][1] == "gguf"


# The full README permutation for this card: every model -> its best engine here.
# Derived from the vendored README (data/trending-README.md, 2026-10-05) and pinned,
# so an engine that loses its image (and drops out of the list) fails the unit job.
README_BEST_ON_16GB_CUDA = {
    "Qwen3.8-Flash-Next 125B": ("Strata", "gguf"),
    "Qwen3.8-27B": ("SGLang", "gguf"),
    "Bonsai 2 27B": ("llama.cpp (PrismML fork)", "gguf"),
    "RavenX-Conjecture-Qwen3-8B-MLX": ("MLX", "mlx-safetensors"),
    "Qwen3.6-35B-A3B": ("FreeToken", "safetensors"),
    "Qwen3 8B": ("Ollama", "gguf"),
    "Gemma 4 12B": ("llama.cpp", "gguf"),
    "Qwen3 14B": ("Ollama", "gguf"),
    "Gemma 4 E2B": ("LiteRT", "litertlm"),
    "Llama 3.1 8B": ("vLLM", "gguf"),
    "DeepSeek R1 1.5B": ("Ollama", "gguf"),
}


def test_every_readme_model_maps_to_its_best_engine(tmp_path, monkeypatch):
    """The whole README list that fits a 16 GB cuda card, each row mapped to the engine
    with the best figure measured on this hardware and the format llgenie fetches for it.
    This is the permutation the interactive list and `llgenie --trend` print."""
    monkeypatch.setenv("LLGENIE_SYSTEM_RAM_BYTES", RAM64)
    rows = _offer(tmp_path, "cuda", 15.9921875)
    got = {r["model"]["name"]: (r["engines"][0]["engine"], r["engines"][0]["use_format"])
           for r in rows if not r["why"]}
    assert got == README_BEST_ON_16GB_CUDA
    # and the printed list names that engine on every row
    out = _cli(tmp_path, "--trend").stdout
    for name, (engine, _fmt) in README_BEST_ON_16GB_CUDA.items():
        line = next(l for l in out.splitlines() if name in l)
        assert engine in line, line


# ---------------------------------------------------------------------------
# mapping: registry engine name -> engine id -> image variant -> format -> download
# ---------------------------------------------------------------------------
def test_every_registry_engine_name_maps_to_its_skill_or_has_no_image():
    """Every engine name the registry uses maps to exactly the engine skill with
    that `engine:` name; names without a container image map to nothing."""
    import engine_skills as es
    d = mp.load_registry()
    names = ({e["engine"] for m in d["models"] for e in m["engines"]}
             | {n for m in d["models"] for n in m.get("supported_engines") or []} | set(d["engines"]))
    ids = mp.engine_ids()
    skills = {s["engine"]: sid for sid, s in es.load_skills().items()}
    for n in names:
        if n in ids:
            assert skills[n] == ids[n]["id"], n
        else:  # no params = no container image: Metal-only, browser-only, or no skill yet
            assert n not in skills or not (mp.PARAMS / f"{skills[n]}.json").exists(), n
    assert ids["llama.cpp (PrismML fork)"]["id"] == "llama.cpp-prism"
    assert ids["vLLM"]["id"] == "vllm" and ids["LiteRT"]["id"] == "litert" and ids["MLX"]["id"] == "mlx"
    # Strata is a real OpenAI server, so it gets its own image and maps like the others
    assert ids["Strata"]["id"] == "strata" and {"cuda", "rocm"} <= set(ids["Strata"]["variants"])
    # not servers: a drafter, a benchmark harness, and a browser library
    assert {"DFlash2", "MLX-fast (Bonsai 2)", "WebLLM"}.isdisjoint(ids)


@pytest.mark.parametrize("arch,engine,variant", [
    ("cuda", "llama.cpp", "cuda"), ("cuda", "llama.cpp-prism", "cpu"),      # prism/cuda disabled (#103)
    ("cuda", "strata", "cuda"), ("rocm", "strata", "rocm"),
    ("cuda", "litert", "cpu"), ("cuda", "mlx", "cuda"), ("rocm", "mlx", "cpu"),
    ("vulkan", "vllm", "cpu"), ("rocm", "freetoken", "rocm"), ("cpu", "ollama", "cpu")])
def test_engine_maps_to_the_host_variant_with_cpu_fallback(arch, engine, variant):
    rows = {e["id"]: e for e in mp.host_engines(arch)}
    assert rows[engine]["variant"] == variant


def test_cpu_has_no_cuda_only_engine():
    ids = {e["id"] for e in mp.host_engines("cpu")}
    assert {"sglang", "freetoken", "tensorfold", "tensorrt-llm", "strata"}.isdisjoint(ids)


@pytest.mark.parametrize("hardware,want", [
    ("RTX 4090 24GB", "CUDA"), ("RTX 4090 Laptop", "CUDA"), ("DGX Spark", "CUDA"),
    ("8GB GPU (est, vendor-claimed MoE weight offload)", "CUDA"),
    ("RX 7900 XTX", "ROCm"), ("Strix Halo (AMD Ryzen AI Max APU)", "ROCm"),
    ("Radeon AI PRO R9700 32GB", "ROCm"), ("Ryzen 5 7600 + RX 7800 XT", "ROCm"),
    ("Raspberry Pi 5 (CPU)", "CPU"), ("Ryzen AI Max+ 395, CPU only", "CPU"),
    ("M5 Max (Apple Silicon)", "Metal"), ("Apple Silicon 16GB Mac", "Metal"), ("M3 (Apple Silicon)", "Metal")])
def test_measurement_hardware_maps_to_a_backend(hardware, want):
    assert mp.measurement_backend({"hardware": hardware}) == want


def test_engine_order_same_hw_then_other_hw_then_supported_only():
    # Given a model measured on CUDA (A), ROCm (B), Apple (C) and listed-only (D)
    m = {"id": "t", "name": "t", "engines": [
        {"engine": "Ollama", "tps": "50", "hardware": "RX 7900 XTX"},
        {"engine": "llama.cpp", "tps": "20", "hardware": "RTX 3060"},
        {"engine": "MLX", "tps": "90", "hardware": "M4 Max (Apple Silicon)"}],
        "supported_engines": ["vLLM"]}
    rows = mp.rank_engines(m, "cuda")
    # Then CUDA figure first, then other hardware by t/s (ROCm 50 > Metal... no: by rank then t/s),
    # supported-without-figure last
    assert [r["id"] for r in rows] == ["llama.cpp", "mlx", "ollama", "vllm"]
    assert [r["rank"] for r in rows] == [0, 1, 1, 2]
    assert rows[1]["measured_on"] == "Metal" and rows[2]["measured_on"] == "ROCm"
    assert rows[3]["tps"] == 0 and rows[3]["measured_on"] == ""


@pytest.mark.parametrize("name,fmt", [("m.gguf", "gguf"), ("m.litertlm", "litertlm")])
def test_model_format_of_files(tmp_path, name, fmt):
    f = tmp_path / name
    f.write_bytes(b"x")
    assert mp.model_format(f) == fmt


def test_model_format_of_dirs(tmp_path):
    for d, fmt in (("Some-Model-MLX", "mlx-safetensors"), ("Some-Model", "safetensors")):
        (tmp_path / d).mkdir()
        (tmp_path / d / "config.json").write_text("{}")
        assert mp.model_format(tmp_path / d) == fmt


def test_weight_budget_rules():
    assert abs(mp.weight_budget_gb(16) - 11.8) < 1e-9
    assert abs(mp.weight_budget_gb(16, moe=True, ram_gb=64) - (11.8 + 60)) < 1e-9
    assert abs(mp.weight_budget_gb(16, moe=True, ram_gb=64, arch="cpu") - 11.8) < 1e-9  # card is RAM
    assert abs(mp.weight_budget_gb(2) - 1.0) < 1e-9   # floor: half the card
    assert mp.weight_budget_gb(0) == float("inf")


@pytest.mark.parametrize("model_id,fmt,repo_part,file_part", [
    ("qwen3.8-27b", "gguf", "Qwen3.8-27B-GGUF", "Qwen3.8-27B-"),
    ("bonsai-2-27b", "gguf", "prism-ml/Ternary-Bonsai-2-27B-gguf", "Ternary-Bonsai-2-27B-"),
    ("gemma-4-e2b", "litertlm", "litert-community/gemma-4-E2B-it-litert-lm", "gemma-4-E2B-it.litertlm"),
    ("ravenx-conjecture-qwen3-8b-mlx", "mlx-safetensors", "deadbydawn101/RavenX-Conjecture-Qwen3-8B-MLX", ""),
    ("qwen3-8b", "gguf", "Qwen/Qwen3-8B-GGUF", "Qwen3-8B-"),
])
def test_plan_download_per_format_live_hub(model_id, fmt, repo_part, file_part):
    """Live Hub: the download plan for each format a 16 GB card would fetch."""
    m = next(x for x in mp.load_registry()["models"] if x["id"] == model_id)
    plan = mp.plan_download(m, 16, 64, fmt, "cuda")
    assert plan and repo_part in plan["repo"] and plan["path"].endswith(file_part) or file_part in plan["path"]
    assert plan["size"] <= mp.weight_budget_gb(16, mp.is_moe(m), 64) * 2**30
    if fmt == "mlx-safetensors":
        assert plan.get("dir") and "config.json" in plan["files"] and any(f.endswith(".safetensors") for f in plan["files"])
        assert not any(f.lower().endswith((".md", ".gitattributes")) for f in plan["files"])
    if fmt == "litertlm":
        assert not mp._LITERT_VARIANT.search(plan["path"])  # the generic build, not gpu/web/vendor


def test_moe_model_on_16gb_is_planned_with_system_ram():
    m = next(x for x in mp.load_registry()["models"] if x["id"] == "qwen3.8-flash-next-125b")
    assert mp.plan_download(m, 16, 8, "gguf", "cuda") is None           # 8 GB RAM: nothing fits
    plan = mp.plan_download(m, 16, 64, "gguf", "cuda")                    # 64 GB RAM: smallest set fits
    assert plan and len(plan["files"]) > 1 and plan["path"] == plan["files"][0]
    assert plan["size"] <= mp.weight_budget_gb(16, True, 64) * 2**30


def test_unservable_row_says_why(tmp_path, monkeypatch):
    # Given an 8 GB RAM host: llama.cpp has no GGUF of the 125B that fits, but Strata
    # installs its own choice whatever the RAM (setup.py recommends, never forces), so
    # the row stays servable on Strata, with Strata's own first size (Q2_0)
    monkeypatch.setenv("LLGENIE_SYSTEM_RAM_BYTES", str(8 * 2**30))
    rows = {r["model"]["name"]: r for r in _offer(tmp_path, "cuda", 16)}
    row = rows["Qwen3.8-Flash-Next 125B"]
    assert row["why"] == "" and [e["id"] for e in row["engines"]] == ["strata"]
    assert row["engine_plans"]["strata"]["path"] == "Q2_0/Qwen3.8-Flash-Next-GSQ-RCO-Q2_0-00001-of-00002.gguf"
    # and on a cpu host the MLX-only model has no image... mlx has a cpu image, so it stays
    rows = {r["model"]["name"]: r for r in _offer(tmp_path, "cpu", 16)}
    assert rows["RavenX-Conjecture-Qwen3-8B-MLX"]["why"] == ""


# ---------------------------------------------------------------------------
# non-interactive CLI: --trend (print the list), --select N (pick row N)
# ---------------------------------------------------------------------------
def _cli(tmp_path, *args, backend="cuda", gb=15.9921875, ram=RAM64, timeout=300):
    env = _env(tmp_path, backend, 16, LLAMA_RAM_BYTES=str(int(gb * 2**30)), LLGENIE_SYSTEM_RAM_BYTES=ram)
    return subprocess.run([sys.executable, str(SERVE), *args], env=env, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, timeout=timeout)


def test_trend_flag_prints_the_numbered_readme_list(tmp_path):
    r = _cli(tmp_path, "--trend")
    assert r.returncode == 0, r.stderr
    lines = [line for line in r.stdout.splitlines() if " trend " in line]
    names = [n for n, v in _readme_rows() if v <= 16]
    assert len(lines) == len(names)
    for i, (line, name) in enumerate(zip(lines, names), 1):
        assert line.strip().startswith(f"{i}.") and name in line, line


def test_select_every_row_plans_a_download_and_the_right_engine(tmp_path, monkeypatch):
    """--select N for EVERY row of the 16 GB list on an empty models dir: each model
    is planned for download (repo + file/dir that fit) and served by that row's top
    engine's start script. No terminal, no prompts."""
    monkeypatch.setenv("LLGENIE_SYSTEM_RAM_BYTES", RAM64)
    rows = [r for r in _offer(tmp_path, "cuda", 15.9921875) if not r["why"]]
    for i, row in enumerate(rows, 1):
        r = _cli(tmp_path, "--select", str(i), "--dry")
        assert r.returncode == 0, (i, row["model"]["name"], r.stderr)
        e = row["engines"][0]
        assert f"Model  : {row['model']['name']}" in r.stdout, (i, r.stdout)
        assert f"Engine : {e['engine']} [{e['variant']}]" in r.stdout, (i, r.stdout)
        plan = mp.engine_plan(row, e)
        assert f"would download {plan['repo']}/{plan['path']}" in r.stdout, (i, r.stdout)
        assert "llgenie-engine-" + e["id"].replace(".", "-") in r.stdout, (i, r.stdout)
    assert _cli(tmp_path, "--select", str(len(rows) + 1), "--dry").returncode != 0


def test_select_with_engine_overrides_the_top_engine(tmp_path):
    # Qwen3.8-27B (row 2): llama.cpp instead of the top SGLang
    r = _cli(tmp_path, "--select", "2", "--engine", "llama.cpp", "--dry")
    assert r.returncode == 0, r.stderr
    assert "Engine : llama.cpp [cuda]" in r.stdout and "Qwen3.8-27B-GGUF" in r.stdout


def test_every_model_in_the_list_downloads_the_first_bytes_of_its_planned_file(tmp_path, monkeypatch):
    """The download path is the same for every row, and it is real: for each model in
    the 16 GB list llgenie fetches the first bytes of the exact file plan_download
    chose, from the repo it chose. A GGUF starts with its magic, a repo snapshot with
    the file the plan names. LLGENIE_DOWNLOAD_MAX_BYTES is the CI seam."""
    monkeypatch.setenv("LLGENIE_SYSTEM_RAM_BYTES", RAM64)
    monkeypatch.setenv("LLGENIE_DOWNLOAD_MAX_BYTES", "4096")
    monkeypatch.setenv("LLAMA_MODELS_ROOT", str(tmp_path))   # empty: every row is a download
    rows = [r for r in _offer(tmp_path, "cuda", 15.9921875) if not r["why"]]
    assert [r["model"]["name"] for r in rows] == list(README_BEST_ON_16GB_CUDA)
    for row in rows:
        fmt = row["engines"][0]["use_format"]
        plan = mp.engine_plan(row, row["engines"][0])
        assert plan, row["model"]["name"]
        out = mp.download(row["model"], 15.9921875, tmp_path, fmt=fmt, arch="cuda",
                          ram_gb=64, engine=row["engines"][0]["id"], plan=plan)
        assert out.exists() and 0 < out.stat().st_size <= 4096, (row["model"]["name"], out)
        assert plan["repo"].replace("/", "__") in str(out)
        assert out.name == Path(plan["path"] or plan["files"][0]).name, (row["model"]["name"], out.name)
        if fmt == "gguf":
            assert out.read_bytes()[:4] == b"GGUF", row["model"]["name"]


def test_select_downloads_a_missing_model_for_real(tmp_path):
    """Real download, no --dry, no terminal: on a 2 GB cpu card the list is Gemma 4 E2B
    (LiteRT, too big for 1 GB) and DeepSeek R1 1.5B; --select picks DeepSeek, which is
    not under the models dir, so llgenie downloads the full GGUF from the Hub before
    serving (the serve step itself needs the engine image: covered by make
    test-install-trend). The start script is absent here, so llgenie stops right after."""
    rows = [x for x in _offer(tmp_path, "cpu", 2) if not x["why"]]
    target = rows[0]
    plan = mp.engine_plan(target, target["engines"][0])
    r = _cli(tmp_path, "--select", "1", backend="cpu", gb=2, timeout=1800)
    f = tmp_path / plan["repo"].replace("/", "__") / plan["path"]
    assert f.exists() and f.stat().st_size == plan["size"], (r.stdout[-2000:], r.stderr[-2000:])
    assert f.read_bytes()[:4] == b"GGUF"
    assert "-> downloading" in r.stdout
    # a second run finds it locally: no download
    r2 = _cli(tmp_path, "--select", "1", "--dry", backend="cpu", gb=2)
    assert "would download" not in r2.stdout and str(f) in r2.stdout, r2.stdout


def test_download_mlx_repo_snapshot_for_real(tmp_path):
    """Real download of a whole safetensors repo (the MLX/safetensors path), tiny repo."""
    m = {"id": "tiny-st", "name": "tiny-random-LlamaForCausalLM",
         "hf": "hf-internal-testing/tiny-random-LlamaForCausalLM",
         "formats": [{"name": "safetensors", "hf": "hf-internal-testing/tiny-random-LlamaForCausalLM"}]}
    plan = mp.plan_download(m, 2, 8, "safetensors", "cpu")
    assert plan and plan.get("dir") and "config.json" in plan["files"]
    out = mp.download(m, 2, tmp_path, fmt="safetensors", arch="cpu")
    assert out.is_dir() and (out / "config.json").exists() and (out / "model.safetensors").stat().st_size > 0
    assert mp.model_format(out) == "safetensors"


def test_engine_tps_comes_from_the_hosts_hardware_first():
    # Given Qwen3.8-27B: llama.cpp measured on an RTX 5090 Laptop (43.7) and on AMD (51.8)
    m = next(x for x in mp.load_registry()["models"] if x["id"] == "qwen3.8-27b")
    # When its engines are ranked for a cuda host
    rows = {r["id"]: r for r in mp.rank_engines(m, "cuda")}
    # Then llama.cpp uses the CUDA figure, and the AMD-only LaurentZuijdwijk fork ranks last
    assert rows["llama.cpp"]["tps"] == 43.7 and rows["llama.cpp"]["same_hw"]
    assert not rows["llama.cpp-laurentzuijdwijk"]["same_hw"] and rows["llama.cpp-laurentzuijdwijk"]["rank"] == 1
    order = [r["id"] for r in mp.rank_engines(m, "cuda")]
    assert order.index("llama.cpp-laurentzuijdwijk") > order.index("llama.cpp")
    # and for a rocm host the AMD figures come first
    rrows = mp.rank_engines(m, "rocm")
    assert rrows[0]["same_hw"] and rrows[0]["measured_on"] == "ROCm"
    # and the classifier matches upstream on the hardware strings in the registry
    assert mp.measurement_backend({"hardware": "RTX 4090 24GB"}) == "CUDA"
    assert mp.measurement_backend({"hardware": "Strix Halo (AMD Ryzen AI Max APU)"}) == "ROCm"
    assert mp.measurement_backend({"hardware": "Raspberry Pi 5 (CPU)"}) == "CPU"
    assert mp.measurement_backend({"hardware": "M5 Max (Apple Silicon)"}) == "Metal"
    assert mp.measurement_backend({"hardware": "DGX Spark"}) == "CUDA"


def test_bands_match_the_readme_status_column():
    import re
    reg = mp.load_registry()
    today = mp.registry_today(reg)
    section = README.read_text().split(sr.MOST_LOVED, 1)[1].split("\n## ", 1)[0]
    status = dict(re.findall(r"^\| \[\*\*(.+?)\*\*\].*? \| \S+ (trending|recent|stale)<br>", section, re.M))
    assert len(status) == len(reg["models"])
    for m in reg["models"]:
        assert mp.BAND_LABEL[mp.band(m, today)] == status[m["name"]], m["name"]


def test_llgenie_no_args_is_the_interactive_trend_pick(tmp_path):
    # Given the vendored registry, an empty models dir and a 16 GB cpu host
    env = _env(tmp_path, "cpu", 16)
    rows = _offer(tmp_path, "cpu", 16)
    pickable = [r for r in rows if not r["why"]]
    top = pickable[0]
    # When `llgenie --dry` runs in a terminal and the user answers 1, then 1
    p = Pty([sys.executable, str(SERVE), "--dry"], env, cwd=str(REPO))
    try:
        p.expect(r"every model whose VRAM fits this card", 300)
        p.expect(r"Pick model \[1\]: ", 300)
        listing = p.out
        p.send("1")
        p.expect(r"Engines for " + top["model"]["name"], 120)
        p.expect(r"Pick inference server \[1\]: ")
        p.send("1")
        assert p.wait(300) == 0, p.out
    finally:
        p.close()
    # Then the README list that fits is printed in README order, numbered only where servable
    printed = [line for line in listing.splitlines() if " trend " in line]
    assert len(printed) == len(rows)
    for line, r in zip(printed, rows):
        assert r["model"]["name"] in line
        assert ("not here:" in line) == bool(r["why"])
    # and pick 1 = the first servable README model, its top engine, downloaded from a Hub GGUF repo
    out = p.out
    assert f"Engine : {top['engines'][0]['engine']}" in out
    assert "would download " in out and ".gguf" in out.split("would download ")[1].splitlines()[0]
    assert "llgenie-engine-" + top["engines"][0]["id"].replace(".", "-") in out


def test_auto_and_no_tty_take_the_top_pick(tmp_path):
    # Given no terminal (stdin closed)
    env = _env(tmp_path, "cuda", 24)
    top = [r for r in _offer(tmp_path, "cuda", 24) if not r["why"]][0]
    # When llgenie --dry runs
    r = subprocess.run([sys.executable, str(SERVE), "--dry"], env=env, stdin=subprocess.DEVNULL,
                       capture_output=True, text=True, timeout=300)
    # Then it never asks and takes the first servable README model + its top engine
    assert r.returncode == 0, r.stderr
    assert "Pick model" not in r.stdout
    assert f"Model  : {top['model']['name']}" in r.stdout
    assert f"Engine : {top['engines'][0]['engine']}" in r.stdout


def test_engines_listing_and_manual_pair_compatibility(tmp_path):
    # Given a local GGUF on a cpu host
    f = tmp_path / "Qwen" / "8GB" / "tiny-test-q4_0.gguf"
    f.parent.mkdir(parents=True)
    f.write_bytes(b"GGUF")
    env = _env(tmp_path, "cpu", 16)
    run = lambda *a: subprocess.run([sys.executable, str(SERVE), *a], env=env, stdin=subprocess.DEVNULL,  # noqa: E731
                                    capture_output=True, text=True, timeout=120)
    # When the engines are listed
    r = run("--engines")
    assert r.returncode == 0, r.stderr
    assert "llama.cpp " in r.stdout and "ollama" in r.stdout and "litert" in r.stdout
    # Then a manual incompatible pair fails naming the compatible engines
    r = run("tiny-test", "--engine", "litert", "--dry")
    assert r.returncode != 0
    assert "not compatible" in r.stderr and "ollama" in r.stderr and "llama.cpp" in r.stderr
    # and a compatible pair serves that exact file with that engine's start script
    r = run("tiny-test", "--engine", "ollama", "--dry")
    assert r.returncode == 0, r.stderr
    assert "llgenie-engine-ollama" in r.stdout and str(f) in r.stdout
    # and --engines <file> lists only the GGUF readers
    r = run("--engines", "tiny-test")
    assert r.returncode == 0 and "ollama" in r.stdout and "litert" not in r.stdout


def test_local_flag_keeps_the_local_picker(tmp_path):
    # Given --local and an empty models dir
    env = _env(tmp_path, "cpu", 16)
    r = subprocess.run([sys.executable, str(SERVE), "--local", "--dry"], env=env, stdin=subprocess.DEVNULL,
                       capture_output=True, text=True, timeout=60)
    # Then the old local GGUF flow runs (no registry)
    assert "No .gguf models found" in r.stdout and "Recommended" not in r.stdout


# ---------------------------------------------------------------------------
# download / Hub logic (live Hugging Face, real files, no mocks)
# ---------------------------------------------------------------------------
TINY = {"id": "tiny", "name": "tiny-random-LlamaForCausalLM",
        "hf": "aladar/tiny-random-LlamaForCausalLM-GGUF",
        "formats": [{"name": "GGUF", "hf": "aladar/tiny-random-LlamaForCausalLM-GGUF"}]}


def test_full_download_through_hf_download_places_the_complete_gguf(tmp_path, monkeypatch):
    """The real download path (scripts/hf_download.py -> hf CLI), full file, no byte cap."""
    # Given a tiny real GGUF repo and no download cap
    monkeypatch.delenv("LLGENIE_DOWNLOAD_MAX_BYTES", raising=False)
    # When it is downloaded for a 2 GB card
    out = mp.download(TINY, gb=2, root=tmp_path)
    # Then the whole file is in ~/models/<org>__<repo>/, the Hub size matches, GGUF magic
    hub = dict(mp.gguf_files(TINY["hf"]))
    assert out.parent == tmp_path / "aladar__tiny-random-LlamaForCausalLM-GGUF"
    assert out.stat().st_size == hub[out.name] and out.read_bytes()[:4] == b"GGUF"
    # and the model is now found locally (no second download)
    assert mp.resolve_local(TINY, tmp_path) == out


def test_gguf_repo_prefers_registry_repo_then_named_gguf_repo():
    # Given a registry repo that holds GGUF, and one that holds only safetensors
    bonsai = next(m for m in mp.load_registry()["models"] if m["id"] == "bonsai-2-27b")
    qwen = next(m for m in mp.load_registry()["models"] if m["id"] == "qwen3-8b")
    # When the GGUF repo is resolved
    # Then the registry repo is kept when it has .gguf files
    assert mp.gguf_repo(bonsai) == mp.repo_for(bonsai) and mp.gguf_files(mp.repo_for(bonsai))
    # and a base (safetensors) repo resolves to a `<name>-GGUF` repo, same org first
    assert not mp.gguf_files(mp.repo_for(qwen))
    assert mp.gguf_repo(qwen) == "Qwen/Qwen3-8B-GGUF"
    # and a model with no GGUF anywhere resolves to None
    assert mp.gguf_repo({"id": "x", "name": "x", "hf": "llgenie-nonexistent/none-zzzq"}) is None


def test_pick_file_fits_the_card_and_skips_shards_and_mmproj():
    # Given a real GGUF repo with many quants
    files = mp.gguf_files("Qwen/Qwen2.5-0.5B-Instruct-GGUF")
    assert files and not any("mmproj" in f or mp.SHARD.search(f) for f, _ in files)
    # When the file for a 2 GB card is picked
    name, size = mp.pick_file("Qwen/Qwen2.5-0.5B-Instruct-GGUF", 2)
    # Then it is the largest within the dense budget (80% of the card - 1 GiB = 0.6 GB)
    budget = mp.weight_budget_gb(2) * 2**30
    assert size <= budget and size == max(s for _, s in files if s <= budget)
    # and with no fitting file the smallest is returned (and plan_download says no fit)
    assert mp.pick_file("Qwen/Qwen2.5-0.5B-Instruct-GGUF", 0.01)[1] == min(s for _, s in files)


def test_unsloth_repo_skips_mtp_heads_and_imatrix():
    """Live Hub: unsloth repos ship MTP draft heads (MTP/mtp-*.gguf) and an imatrix
    next to the model; they are not loadable models and must never be picked."""
    ws = mp.gguf_weights("unsloth/Qwen3.8-27B-GGUF")
    assert ws and not any("mtp" in w["path"].lower() or "imatrix" in w["path"].lower() for w in ws)
    # the 16 GB pick is a real Qwen3.8-27B quant within 11.8 GB
    plan = mp.plan_download(next(m for m in mp.load_registry()["models"] if m["id"] == "qwen3.8-27b"), 16)
    assert plan["repo"] == "unsloth/Qwen3.8-27B-GGUF" and plan["path"].startswith("Qwen3.8-27B-")
    assert plan["size"] <= mp.weight_budget_gb(16) * 2**30


# ---------------------------------------------------------------------------
# compatibility logic
# ---------------------------------------------------------------------------
def test_model_format_and_engines_for_file(tmp_path):
    # Given a GGUF file and an HF safetensors dir
    g = tmp_path / "m.gguf"
    g.write_bytes(b"GGUF")
    d = tmp_path / "hfdir"
    d.mkdir()
    (d / "config.json").write_text("{}")
    # When their formats and engines are resolved for a cpu host
    # Then gguf -> GGUF readers only, safetensors -> safetensors readers only
    assert mp.model_format(g) == "gguf" and mp.model_format(d) == "safetensors"
    gi = {e["id"] for e in mp.engines_for_file(g, "cpu")}
    si = {e["id"] for e in mp.engines_for_file(d, "cpu")}
    assert {"llama.cpp", "ollama", "vllm"} <= gi and "litert" not in gi and "mlx" not in gi
    assert "vllm" in si and "llama.cpp" not in si


def test_host_engines_use_the_backend_variant_with_cpu_fallback():
    import engine_image as ei
    # Given a cuda host
    rows = {e["id"]: e for e in mp.host_engines("cuda")}
    # Then each engine uses its cuda image, else cpu; disabled (#103) images never appear
    for e in rows.values():
        assert not ei.disabled(e["id"], e["variant"])
    assert rows["llama.cpp"]["variant"] == "cuda"
    assert rows["llama.cpp-prism"]["variant"] == "cpu"  # prism/cuda disabled until #103
    assert "sglang" in rows and "sglang" not in {e["id"] for e in mp.host_engines("cpu")}


def test_choose_reprompts_on_invalid_input(tmp_path):
    # Given a terminal session answering "9", "x", then "2" to a 3-item prompt
    code = ("import sys; sys.path.insert(0, %r); import model_engine_pick as mp; "
            "print('PICKED', mp.choose(['a','b','c'], str, 'thing', None, False))") % str(REPO / "scripts")
    p = Pty([sys.executable, "-c", code], dict(os.environ))
    try:
        for answer in ("9", "x", "2"):
            p.expect(r"Pick thing \[1\]: ", 30)
            p.out = p.out.replace("Pick thing [1]: ", "", 1)
            p.send(answer)
        assert p.wait(30) == 0
    finally:
        p.close()
    # Then out-of-range and non-numeric answers are rejected and "2" picks b
    assert p.out.count("enter 1-3") == 2 and "PICKED b" in p.out


def test_manual_registry_pick_errors_and_engines_for_registry_model(tmp_path):
    env = _env(tmp_path, "cuda", 24)
    run = lambda *a: subprocess.run([sys.executable, str(SERVE), *a], env=env, stdin=subprocess.DEVNULL,  # noqa: E731
                                    capture_output=True, text=True, timeout=300)
    # When a registry model is named that does not exist
    r = run("--pick", "no-such-model-zz", "--dry")
    assert r.returncode != 0 and "no registry model matches" in r.stderr
    # When a registry model is paired with an engine that cannot run it
    r = run("--pick", "bonsai", "--engine", "vllm", "--dry")
    assert r.returncode != 0
    # When --engines names a registry model
    r = run("--engines", "qwen3-8b")
    # Then exactly that model (not RavenX-...-Qwen3-8B-MLX, which contains the id) is listed
    assert r.returncode == 0 and "Engines for Qwen3 8B " in r.stdout and "t/s" in r.stdout, r.stdout
    assert "RavenX" not in r.stdout
    # When a registry model + compatible engine are given
    r = run("--pick", "qwen3-8b", "--engine", "ollama", "--dry")
    # Then that pair is planned, downloading the resolved GGUF repo
    assert r.returncode == 0, r.stderr
    assert "Engine : Ollama [cuda]" in r.stdout and "would download Qwen/Qwen3-8B-GGUF/" in r.stdout


def test_ambiguous_local_model_with_engine_is_rejected(tmp_path):
    # Given the same file name in two dirs (seen on a real host: Qwen/8GB + smoke/)
    for d in ("a", "b"):
        (tmp_path / d).mkdir()
        (tmp_path / d / "dup.gguf").write_bytes(b"GGUF")
    env = _env(tmp_path, "cpu", 16)
    run = lambda *a: subprocess.run([sys.executable, str(SERVE), *a], env=env, stdin=subprocess.DEVNULL,  # noqa: E731
                                    capture_output=True, text=True, timeout=60)
    # When it is named ambiguously with an engine
    r = run("dup", "--engine", "ollama", "--dry")
    # Then llgenie refuses and lists both by their path under the models dir
    assert r.returncode != 0 and "matches 2 local models" in r.stderr
    assert "a/dup.gguf" in r.stderr and "b/dup.gguf" in r.stderr
    # and the full path selects exactly that file
    f = tmp_path / "b" / "dup.gguf"
    r = run(str(f), "--engine", "ollama", "--dry")
    assert r.returncode == 0, r.stderr
    assert "llgenie-engine-ollama" in r.stdout and str(f) in r.stdout


def test_local_marker_and_reuse_in_the_trend_list(tmp_path):
    # Given the first servable cpu/16 GB README model already downloaded (a file named like it)
    top = [r for r in _offer(tmp_path, "cpu", 16) if not r["why"]][0]
    f = tmp_path / "x" / (top["model"]["name"].replace(" ", "-") + "-Q4_0.gguf")
    f.parent.mkdir()
    f.write_bytes(b"GGUF")
    env = _env(tmp_path, "cpu", 16)
    # When llgenie --dry runs in a terminal and the user takes the defaults (Enter, Enter)
    p = Pty([sys.executable, str(SERVE), "--dry"], env, cwd=str(REPO))
    try:
        p.expect(r"Pick model \[1\]: ", 300)
        p.send("")
        p.expect(r"Pick inference server \[1\]: ")
        p.send("")
        assert p.wait(120) == 0, p.out
    finally:
        p.close()
    # Then the row is marked [local] and that file is served without a download
    assert "[local]" in p.out.split("Pick model")[0]
    assert str(f) in p.out and "would download" not in p.out


def test_model_pick_reprompts_on_invalid_input(tmp_path):
    # Given the trend list in a terminal
    env = _env(tmp_path, "cpu", 16)
    n = len([r for r in _offer(tmp_path, "cpu", 16) if not r["why"]])
    p = Pty([sys.executable, str(SERVE), "--dry"], env, cwd=str(REPO))
    try:
        # When the user types an out-of-range number, then text, then 1
        for answer in (str(n + 1), "x", "1"):
            p.expect(r"Pick model \[1\]: ", 300)
            p.out = p.out.replace("Pick model [1]: ", "", 1)
            p.send(answer)
        p.expect(r"Pick inference server \[1\]: ")
        p.send("1")
        assert p.wait(120) == 0, p.out
    finally:
        p.close()
    # Then both bad answers are re-asked (rows marked "--" are not pickable numbers)
    assert p.out.count(f"enter 1-{n}") == 2


def test_hub_json_caches_and_survives_a_missing_repo(tmp_path, monkeypatch):
    """Live Hub: a tree lookup is cached on disk (second call does not hit the
    network), and a repo that does not exist gives no files instead of crashing."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    url = f"{mp.HF}/api/models/aladar/tiny-random-LlamaForCausalLM-GGUF/tree/main?recursive=true"
    first = mp._hub_json(url)
    cached = list((tmp_path / "llgenie" / "hub").glob("*.json"))
    assert first and len(cached) == 1
    cached[0].write_text(json.dumps([{"path": "sentinel.gguf", "type": "file", "size": 1}]))
    assert mp._hub_json(url) == [{"path": "sentinel.gguf", "type": "file", "size": 1}]
    mp._TREE_CACHE.clear()
    assert mp.gguf_weights("llgenie-nonexistent/none-zzzq") == []
