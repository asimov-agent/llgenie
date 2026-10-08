"""Acceptance criteria of the llgenie trend list on Linux AND Mac hardware (issue #114,
OpenSpec fix-mac-trend-pick-tensorfold). One matrix, every backend llgenie supports:

  linux: cuda, rocm, vulkan, cpu        mac: metal (Apple-Silicon unified memory)

For every (backend, card size) the list must satisfy the same invariants, whatever
the README says this week:

  AC1  rows   = exactly the README "Most loved" models whose VRAM tier fits the card,
               in README order (nothing added, nothing dropped, nothing reordered);
  AC2  number = only servable rows are numbered, 1..N without gaps, and `--select N`
               / the prompt / `--auto` take exactly row N (1 for --auto);
  AC3  engine = every offered engine runs on this host: the host's own variant
               (metal = native) or a cpu image, never a disabled #103 image, never a
               variant of another backend (no metal on linux, no cuda on a mac);
  AC4  order  = engines ranked: measured on this host's hardware first, then other
               hardware, then supported-only, then by t/s within a rank;
  AC5  fit    = every engine has a local copy or a download plan that fits the
               host's weight budget (TensorFold: its own checkpoint, Strata: its
               setup.py files);
  AC6  why    = a row that cannot be served states a non-empty reason and has no engine;
  AC7  label  = the t/s label has no "(Backend)" suffix exactly when the figure was
               measured on this host's kind of hardware;
  AC8  header = the printed header names the detected backend and card size.

The list is checked without the prompt (`llgenie --trend` prints the same rows the
prompt asks from). Real vendored registry + live Hugging Face API, no Hub mocks."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tests"))
import engine_image as ei  # noqa: E402
import model_engine_pick as mp  # noqa: E402
import sync_registry as sr  # noqa: E402

SERVE = REPO / "scripts" / "llama_serve.py"
README = REPO / "data" / "trending-README.md"
HUB_CACHE = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
RAM = 64  # system RAM of the Linux hosts (GiB); a Mac's RAM is its card

# (platform, backend, card GiB): every backend, small and large cards
HOSTS = [
    ("linux", "cuda", 8), ("linux", "cuda", 16), ("linux", "cuda", 24),
    ("linux", "rocm", 16), ("linux", "rocm", 24),
    ("linux", "vulkan", 16), ("linux", "vulkan", 48),
    ("linux", "cpu", 16), ("linux", "cpu", 48),
    ("mac", "metal", 16), ("mac", "metal", 48), ("mac", "metal", 128),
]
IDS = [f"{p}-{b}-{g}gb" for p, b, g in HOSTS]
ROW = re.compile(r"^\s+(--|\d+\.)\s{2}(.+?)\s+(trending|recent|stale)\s+trend")


def _ram(backend: str, gb: int) -> int:
    return gb if backend == "metal" else RAM


def _env(tmp_path: Path, backend: str, gb: int) -> dict:
    env = {**os.environ, "LLAMA_MODELS_ROOT": str(tmp_path), "LLAMA_BACKEND": backend,
           "LLAMA_RAM_BYTES": str(gb * 2**30), "LLGENIE_SYSTEM_RAM_BYTES": str(_ram(backend, gb) * 2**30),
           "HOME": str(tmp_path / "home"), "XDG_CACHE_HOME": str(HUB_CACHE)}
    env.pop("LLGENIE_REGISTRY_SRC", None)
    return env


def _readme_rows() -> list[tuple[str, int]]:
    """(name, VRAM GB) parsed straight from the vendored README markdown (the list a
    user reads on GitHub), independent of data/models.json."""
    section = README.read_text().split(sr.MOST_LOVED, 1)[1].split("\n## ", 1)[0]
    rows = []
    for line in section.splitlines():
        m = re.match(r"^\| \[\*\*(.+?)\*\*\]", line)
        if m:
            cells = [c.strip() for c in line.split(" | ")]
            vram = next(c for c in cells if re.fullmatch(r"\d+GB", c))
            rows.append((m.group(1), int(vram[:-2])))
    return rows


_CACHE: dict = {}


def _offer(tmp_path: Path, backend: str, gb: int) -> list[dict]:
    key = (backend, gb)
    if key not in _CACHE:
        os.environ.pop("LLGENIE_REGISTRY_SRC", None)
        _CACHE[key] = mp.offer(mp.load_registry(), backend, gb, root=tmp_path, ram_gb=_ram(backend, gb))
    return _CACHE[key]


def _cli(tmp_path: Path, backend: str, gb: int, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SERVE), *args], env=_env(tmp_path, backend, gb),
                          stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=600)


def test_readme_parser_reads_the_vendored_list():
    # Given the vendored README

    # When its "Most loved" table is parsed
    rows = _readme_rows()

    # Then it is the registry's model list, same names and VRAM, same order
    reg = mp.load_registry()["models"]
    assert rows == [(m["name"], int(mp._num(m["vram_tier"]))) for m in reg]


@pytest.mark.parametrize("platform,backend,gb", HOSTS, ids=IDS)
def test_ac1_rows_are_the_readme_models_that_fit_in_readme_order(tmp_path, platform, backend, gb):
    # Given the README list and a host

    # When llgenie builds its list
    rows = _offer(tmp_path, backend, gb)

    # Then it is exactly the README models whose VRAM tier fits, in README order
    assert [r["model"]["name"] for r in rows] == [n for n, v in _readme_rows() if v <= gb]


@pytest.mark.parametrize("platform,backend,gb", HOSTS, ids=IDS)
def test_ac3_every_engine_runs_on_this_host(tmp_path, platform, backend, gb):
    # Given the list for a host
    rows = _offer(tmp_path, backend, gb)

    # When the engines of every servable row are checked
    engines = [e for r in rows for e in r["engines"]]

    # Then each is this host's variant or a cpu image, never disabled, never another backend's
    for e in engines:
        assert e["variant"] in (backend, "cpu"), e
        assert not ei.disabled(e["id"], e["variant"]), e
        if platform == "linux":
            assert e["variant"] != "metal", e
        else:
            assert e["variant"] in ("metal", "cpu"), e

    # And a Metal-native engine is only ever offered natively on a mac
    native = {e["id"] for e in engines if e["variant"] == "metal"}
    assert native <= mp.metal_engines()


@pytest.mark.parametrize("platform,backend,gb", HOSTS, ids=IDS)
def test_ac4_engines_are_ranked_same_hardware_then_other_then_supported(tmp_path, platform, backend, gb):
    # Given the list for a host
    rows = _offer(tmp_path, backend, gb)

    # When each row's engine order is read
    for r in rows:
        keys = [(e["rank"], -e["tps"]) for e in r["engines"]]

        # Then it is sorted by rank, then t/s descending; rank 0 == measured on this hardware
        assert keys == sorted(keys), r["model"]["name"]
        for e in r["engines"]:
            assert e["same_hw"] == (e["measured_on"] == mp.HOST_TO_MEASURED[backend])


@pytest.mark.parametrize("platform,backend,gb", HOSTS, ids=IDS)
def test_ac5_every_engine_has_a_fitting_download_or_local_copy(tmp_path, platform, backend, gb):
    # Given the list for a host and its weight budget
    rows = _offer(tmp_path, backend, gb)

    # When each offered engine's model source is resolved
    for r in rows:
        budget = mp.weight_budget_gb(gb, mp.is_moe(r["model"]), _ram(backend, gb), backend) * 2**30
        for e in r["engines"]:
            plan, local = mp.engine_plan(r, e), mp.engine_local(r, e)

            # Then there is a plan (or a local copy) in a format the engine reads
            assert plan or local, (r["model"]["name"], e["id"])
            assert e["use_format"] in e["formats"]

            # And the plan fits the budget (Strata sizes itself from its setup.py)
            if plan and e["id"] != "strata":
                assert plan["size"] <= budget, (r["model"]["name"], e["id"], plan["repo"])

            # And TensorFold only ever downloads TensorFold's own checkpoints
            if plan and e["id"] == "tensorfold":
                assert plan["repo"].startswith("TensorFold/") and "-MLX-" in plan["repo"]


@pytest.mark.parametrize("platform,backend,gb", HOSTS, ids=IDS)
def test_ac6_unservable_rows_say_why_and_offer_nothing(tmp_path, platform, backend, gb):
    # Given the list for a host
    rows = _offer(tmp_path, backend, gb)

    # When the rows are split into servable and not
    for r in rows:
        # Then a row is servable exactly when it has an engine, otherwise it says why
        assert bool(r["engines"]) != bool(r["why"]), (r["model"]["name"], r["why"])


@pytest.mark.parametrize("platform,backend,gb", HOSTS, ids=IDS)
def test_ac2_ac7_ac8_printed_list_numbering_labels_and_header(tmp_path, platform, backend, gb):
    # Given the rows llgenie computed for a host
    rows = _offer(tmp_path, backend, gb)

    # When `llgenie --trend` prints the list (no prompt)
    r = _cli(tmp_path, backend, gb, "--trend")

    # Then the header names the backend and the card (AC8)
    assert r.returncode == 0, r.stderr
    assert f"this card ({gb} GB, {backend})" in r.stdout

    # And one printed line per row, numbered 1..N only where servable (AC2)
    lines = [ln for ln in r.stdout.splitlines() if ROW.match(ln)]
    assert len(lines) == len(rows)
    n = 0
    for ln, row in zip(lines, rows):
        mark, name = ROW.match(ln).group(1), ROW.match(ln).group(2)
        assert name == row["model"]["name"]
        if row["why"]:
            assert mark == "--" and f"not here: {row['why']}" in ln
            continue
        n += 1
        assert mark == f"{n}."

        # And the t/s label carries "(Backend)" only for other hardware (AC7)
        e = row["engines"][0]
        assert e["engine"] in ln
        if e["same_hw"]:
            assert f"{e['tps']:.0f} t/s" in ln and f"t/s ({e['measured_on']})" not in ln
        elif e["measured_on"]:
            assert f"t/s ({e['measured_on']})" in ln
        else:
            assert "supported" in ln


@pytest.mark.parametrize("platform,backend,gb", [h for h in HOSTS if h[2] in (16, 48)],
                         ids=[i for i, h in zip(IDS, HOSTS) if h[2] in (16, 48)])
def test_ac2_select_n_and_auto_take_the_numbered_row(tmp_path, platform, backend, gb):
    # Given the servable rows of a host
    pick = [r for r in _offer(tmp_path, backend, gb) if not r["why"]]
    assert pick, "every host must have something to serve"

    # When `--select 1`, `--select N` (last) and `--auto` run dry
    runs = {1: _cli(tmp_path, backend, gb, "--select", "1", "--dry"),
            len(pick): _cli(tmp_path, backend, gb, "--select", str(len(pick)), "--dry")}
    auto = _cli(tmp_path, backend, gb, "--auto", "--dry")

    # Then each takes exactly that row and its top engine; --auto takes row 1
    for n, r in runs.items():
        assert r.returncode == 0, r.stderr
        row = pick[n - 1]
        assert f"Model  : {row['model']['name']}" in r.stdout
        assert f"Engine : {row['engines'][0]['engine']} [{row['engines'][0]['variant']}]" in r.stdout
    assert auto.returncode == 0, auto.stderr
    assert f"Model  : {pick[0]['model']['name']}" in auto.stdout

    # And --select past the end is refused with the valid range
    bad = _cli(tmp_path, backend, gb, "--select", str(len(pick) + 1), "--dry")
    assert bad.returncode != 0 and f"pick 1-{len(pick)}" in bad.stderr


def test_same_readme_different_hardware_gives_each_host_its_own_top_engine(tmp_path):
    """The same model is offered with the engine measured on each host's hardware:
    Qwen3.8-27B -> TensorFold on a Mac (189 t/s M5 Max), never TensorFold on a cpu host."""

    # Given Qwen3.8-27B on a 48 GB mac, a 24 GB cuda card and a 48 GB cpu host
    def top(backend, gb):
        row = next(r for r in _offer(tmp_path, backend, gb) if r["model"]["name"] == "Qwen3.8-27B")
        return row["engines"][0] if row["engines"] else None

    # When each host's top engine is read
    mac, cuda, cpu = top("metal", 48), top("cuda", 24), top("cpu", 48)

    # Then the Mac runs TensorFold natively on a Metal figure
    assert (mac["id"], mac["variant"], mac["measured_on"]) == ("tensorfold", "metal", "Metal")

    # And the cuda card's figure is a CUDA one (an engine with a cuda image or cpu fallback)
    assert cuda["measured_on"] == "CUDA" and cuda["variant"] in ("cuda", "cpu")

    # And the cpu host never gets TensorFold (no cpu image, no Metal)
    assert cpu is None or cpu["id"] != "tensorfold"
