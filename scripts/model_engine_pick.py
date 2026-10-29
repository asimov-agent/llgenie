#!/usr/bin/env python3
"""Pick the model and the inference server for `llgenie` (issue #102 / OpenSpec
feat-model-engine-pick).

Data: the trending-local-llms registry, vendored as data/models.json (issue #105;
`make sync-registry` refreshes it, LLGENIE_REGISTRY_SRC=<file|url> overrides it):
per model, measured t/s per engine (`engines[].tps`) plus post engagement.

  rank_engines(model)  engines that can run `model` ON THIS HOST (an image
                       variant for the host backend, cpu fallback), best first:
                       a figure measured on this host's kind of hardware AND on
                       a card of this host's class (issue #225), then a
                       same-backend figure from a bigger/unknown card, then
                       another backend, then a datacenter figure, then
                       supported-only; by t/s, then trending engagement.
  rank_models()        registry models that fit the card (measured evidence: a run
                       on a card <= this one, else vram_min, else weight_gb —
                       issue #669), each with its best engine, best first by t/s.
  recommend()          what plain `llgenie` offers (issue #105): the models this
                       card fits, in the card's own order — the vendored README's
                       tier-local `Up to N GB` ranking, then the rows it does not
                       rank in the store's trend order (the file's position is
                       never read); rows that cannot be served here say why.
                       Engine t/s comes from this host's kind of hardware first.
  gguf_repo(model)     a Hub repo with .gguf files for the model: the registry
                       repo, else the most-downloaded `<name>-GGUF` repo.
  engines_for_file(p)  engines with an image for this host that read p's format.
  resolve_local(model) a GGUF/model dir under ~/models matching the model.
  download(model)      fetch it with the existing hf path (scripts/hf_download.py);
                       LLGENIE_DOWNLOAD_MAX_BYTES=N fetches only the first N bytes
                       (HTTP Range) — what CI uses to test the download logic.

Defaults never prompt: `--auto` (or a non-interactive stdin) picks the top
model and its top engine. Stdlib only.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

try:
    from .hf_auth import TRANSIENT_HTTP, authorize, hub_open, rate_limit_wait
except ImportError:  # run as a script
    from hf_auth import TRANSIENT_HTTP, authorize, hub_open, rate_limit_wait  # type: ignore

REPO = Path(__file__).resolve().parent.parent
PARAMS = REPO / "containers" / "engines" / "params"
REGISTRY_FILE = REPO / "data" / "models.json"  # vendored; make sync-registry refreshes it
RECOMMEND_LIMIT = None  # the whole README trend list that fits the card
SHARD = re.compile(r"-\d{5}-of-\d{5}\.gguf$")
HF = "https://huggingface.co"
APPLE = re.compile(r"apple|\bM[1-9]\b|\bM[1-9] (pro|max|ultra)|mac", re.I)
#: Outer ceiling, in seconds, on ONE `scripts/hf_download.py` child (a file or a whole
#: repo). The child bounds its own attempts (hf_download.py: MAX_RETRY=20 on a 90 s
#: stall-watch and a 5 s pause, i.e. a ~1900 s retry ladder before transfer time), but
#: nothing bounded the hop as a whole: `subprocess.run` with no `timeout=` let one stalled
#: transfer hold a CI job until GitHub's 6-hour default, with `pytest`'s 300 s faulthandler
#: only printing a traceback (issue #872). 3600 s is ~2x that ladder, so a healthy download
#: that retries still finishes while a dead one fails in an hour NAMING its command.
#: Override with LLGENIE_DOWNLOAD_TIMEOUT=<seconds> for an unusually slow link.
DOWNLOAD_TIMEOUT = float(os.environ.get("LLGENIE_DOWNLOAD_TIMEOUT", "3600"))


def models_root() -> Path:
    return Path(os.environ.get("LLAMA_MODELS_ROOT") or Path.home() / "models")


def load_registry(src: str | None = None) -> dict:
    """The vendored data/models.json; LLGENIE_REGISTRY_SRC (file or URL) overrides it."""
    src = src or os.environ.get("LLGENIE_REGISTRY_SRC") or str(REGISTRY_FILE)
    if src.startswith("http"):
        with urllib.request.urlopen(authorize(urllib.request.Request(src)), timeout=30) as r:  # noqa: S310
            return json.load(r)
    return json.loads(Path(src).read_text())


def engine_formats() -> dict[str, list[str]]:
    """Engine id -> model formats it reads (the skill's `formats`)."""
    sys.path.insert(0, str(REPO / "scripts"))
    import engine_skills as es
    return {sid: [str(f).lower() for f in (s.get("formats") or [])] for sid, s in es.load_skills().items()}


def metal_engines() -> set[str]:
    """Engine ids that run natively on Apple-Silicon Metal (issue #114): a servable
    skill (servable: true, not a `via` harness) with `metal` in its backends and an
    install for it. Metal cannot run in a container, so these are the only engines
    installed on the host (engine_skills.native_allowed); their `metal` variant is
    native (scripts/install_engine_launchers.py writes a native start script)."""
    sys.path.insert(0, str(REPO / "scripts"))
    import engine_skills as es
    out = set()
    for sid, s in es.load_skills().items():
        if s.get("servable") is True and "metal" in (s.get("backends") or []) \
                and es._per_backend(s.get("install"), "metal"):
            out.add(sid)
    return out


def engine_ids() -> dict[str, dict]:
    """Registry engine name -> {id, variants, formats} from the generated params,
    plus the native `metal` variant of every Metal engine (metal_engines)."""
    out = {}
    fmts = engine_formats()
    metal = metal_engines()
    sys.path.insert(0, str(REPO / "scripts"))
    import engine_image as ei
    for pf in PARAMS.glob("*.json"):
        p = json.loads(pf.read_text())
        variants = [v for v in (p.get("variants") or {}) if not ei.disabled(p["id"], v)]
        if p["id"] in metal:
            variants.append("metal")
        out[p["engine"]] = {"id": p["id"], "formats": fmts.get(p["id"], []), "variants": variants}
    return out


def host_engines(arch: str | None = None, ids: dict | None = None) -> list[dict]:
    """Every engine with an enabled image variant for this host (cpu fallback).

    A metal host never falls back to a cpu image (issue #120): macOS runs natively
    and must not start an engine image. Linux keeps the cpu fallback.
    """
    arch = arch or host_arch()
    ids = ids if ids is not None else engine_ids()
    out = []
    for name, info in ids.items():
        variant = arch if arch in info["variants"] else (
            None if arch == "metal" else ("cpu" if "cpu" in info["variants"] else None))
        if variant:
            out.append({"engine": name, "id": info["id"], "variant": variant, "formats": info["formats"]})
    return sorted(out, key=lambda r: r["id"])


def model_format(path: Path) -> str:
    """Format of a local model: gguf (.gguf), litertlm (.litertlm), mlx-safetensors
    (an HF model dir whose name says MLX), safetensors (any other HF model dir)."""
    path = Path(path)
    if path.suffix == ".gguf":
        return "gguf"
    if path.suffix == ".litertlm":
        return "litertlm"
    if path.is_dir() and (path / "config.json").exists():
        return "mlx-safetensors" if "mlx" in path.name.lower() else "safetensors"
    return path.suffix.lstrip(".").lower()


#: ggml tensor types that exist ONLY in the Prism fork (skills/engines/llama.cpp-prism:
#: `GGML_TYPE_PQ2_0 = 142`, `GGML_TYPE_PTQ1_0 = 143`). Stock llama.cpp refuses such a file
#: with `tensor 'output.weight' has invalid ggml type 142`, so a GGUF carrying one must be
#: served by the Prism engine and nothing else — the picker used to offer stock llama.cpp
#: for Ternary Bonsai 2's PQ2_0 file, which cannot load it at all.
PRISM_GGML_TYPES = frozenset({142, 143})
PRISM_ENGINES = frozenset({"llama.cpp-prism"})


def gguf_tensor_types(path: Path) -> set[int]:
    """The ggml tensor types a .gguf actually stores (empty when the header is unreadable).

    A local model decided the engine by its file FORMAT alone, so every GGUF looked alike.
    The tensor types are what tell a fork-specific quantisation apart: parsed straight from
    the header (magic -> version -> counts -> KV block -> tensor infos), no dependency.
    """
    import struct

    path = Path(path)
    try:
        with path.open("rb") as f:
            if f.read(4) != b"GGUF":
                return set()
            ver = struct.unpack("<I", f.read(4))[0]
            if ver < 2:
                return set()
            _n_tensors = struct.unpack("<Q", f.read(8))[0]
            n_kv = struct.unpack("<Q", f.read(8))[0]

            def rd_str() -> None:
                n = struct.unpack("<Q", f.read(8))[0]
                f.seek(n, 1)

            # scalar/array sizes of the GGUF value types (skip them, we only need the infos)
            fixed = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}
            for _ in range(n_kv):
                rd_str()
                vt = struct.unpack("<I", f.read(4))[0]
                if vt == 8:  # string
                    rd_str()
                elif vt == 9:  # array
                    at = struct.unpack("<I", f.read(4))[0]
                    n = struct.unpack("<Q", f.read(8))[0]
                    if at == 8:
                        for _ in range(n):
                            rd_str()
                    else:
                        f.seek(fixed.get(at, 0) * n, 1)
                else:
                    f.seek(fixed.get(vt, 0), 1)
            types: set[int] = set()
            for _ in range(_n_tensors):
                rd_str()
                n_dims = struct.unpack("<I", f.read(4))[0]
                f.seek(8 * n_dims, 1)
                types.add(struct.unpack("<I", f.read(4))[0])
                f.seek(8, 1)  # offset
            return types
    except (OSError, struct.error):
        return set()


def gguf_needs_prism(path: Path) -> bool:
    """True when the file stores a tensor type only the Prism build defines."""
    return bool(gguf_tensor_types(path) & PRISM_GGML_TYPES)


def engines_for_file(path: Path, arch: str | None = None) -> list[dict]:
    """Engines with an image for this host that read the model file's format.

    A GGUF carrying a Prism-only tensor type is narrowed to the engines that can load it,
    so the file's own bytes decide, not the extension.
    """
    fmt = model_format(path)
    out = [e for e in host_engines(arch) if fmt in e["formats"]]
    if fmt == "gguf" and gguf_needs_prism(path):
        out = [e for e in out if e["id"] in PRISM_ENGINES]
    return out


def host_arch() -> str:
    """cuda | rocm | vulkan | metal | cpu. An Apple-Silicon Mac is `metal` (issue #114):
    its native Metal engines come first. A metal host never falls back to a cpu
    image (issue #120): macOS runs natively and must not start an engine image."""
    try:
        sys.path.insert(0, str(REPO / "scripts"))
        import detect_server as d
        return {"cuda": "cuda", "rocm": "rocm", "vulkan": "vulkan",
                "metal": "metal"}.get(d.detect_all().get("backend"), "cpu")
    except Exception:  # noqa: BLE001
        return "cpu"


def card_gb() -> float:
    if os.environ.get("LLAMA_RAM_BYTES", "").isdigit():
        return int(os.environ["LLAMA_RAM_BYTES"]) / 2**30
    try:
        import detect_server as d
        return d.detect_card_ram_bytes() / 2**30
    except Exception:  # noqa: BLE001
        return 0.0


def _num(s) -> float:
    m = re.search(r"\d+(\.\d+)?", str(s or ""))
    return float(m.group(0)) if m else 0.0


# ---- measurement backend (mirrors trending-local-llms update_trending.py) ----
# A t/s figure only describes this host when it was measured on the same kind of
# hardware: an RTX number for a cuda host, a Radeon/Strix Halo number for rocm or
# vulkan, a CPU number for cpu. Apple numbers never describe a container host.
_CUDA_HW = ("rtx", "nvidia", "cuda", "geforce", "tesla", "a100", "h100", "l40", "aic", "dgx", "gb10", "jetson")
_CPU_HW = ("cpu", "intel", "amd ryzen", "ryzen", "epyc", "xeon", "threadripper", "no gpu", "raspberry",
           "arm64", "snapdragon")
_CPU_ONLY = re.compile(r"\bcpu[\s-]only\b|\bno[\s-]gpu\b|\bwithout (?:a )?gpu\b", re.I)
_AMD_GPU = re.compile(
    r"\bradeon\b|\brx\s?-?\d{3,4}\b|\b(?:9070|9060|7900|7800|7700|7600|6950|6900|6800|6750|6700|6650|6600|5700)"
    r"\s?(?:xtx|xt|gre)\b|\brocm\b|\bhip\b|\bstrix[\s-]?halo\b|\bryzen\s+ai\s+max\b"
    r"|\b(?:8065s|8060s|8050s|890m|880m|780m|760m|680m|660m)\b|\bgfx\d{3,4}\b|\binstinct\b|\bmi\d{3}x?\b"
    r"|\br9700\b|\bw7[89]00\b|\brdna\s?\d|\bnavi\s?\d|\bamd\s+(?:gpu|graphics)\b", re.I)
HOST_TO_MEASURED = {"cuda": "CUDA", "rocm": "ROCm", "vulkan": "ROCm", "metal": "Metal", "cpu": "CPU"}
# A host whose hardware IS a card: only here can a figure be compared to THIS
# host's card. Apple Silicon (unified memory) and a CPU host have no card class.
CARD_ARCHES = ("cuda", "rocm", "vulkan")

# ---- card class (mirrors trending-local-llms update_trending.py) --------------
# A backend (CUDA vs ROCm) is not a card class: a 2x RTX 4090 (48 GB) box and a
# 6 GB laptop card are both "CUDA", and a figure from the bigger one does not
# predict throughput on the smaller one — what it needed there is unknown. So a
# figure is comparable only when the card it ran on is no bigger than this
# host's. The strings and the VRAM numbers are upstream's (_CARD_VRAM,
# hardware_vram_gb, _DATACENTER_HW), so llgenie and the README agree on what a
# hardware string means.
# Consumer/workstation cards -> total VRAM (GB). Laptop variants first (more
# specific), then bare model numbers; a bare AMD number needs the 'rx ' prefix so
# a host CPU such as 'Ryzen 5 7600' is never read as an RX 7600 (8 GB).
_CARD_VRAM = (
    ("5090 laptop", 24), ("4090 laptop", 16), ("5080 laptop", 16), ("4080 laptop", 12),
    ("5090", 32), ("5080", 16), ("5070 ti", 16), ("5070", 12), ("5060 ti", 16), ("5060", 8),
    ("4090", 24), ("4080", 16), ("4070 ti super", 16), ("4070 ti", 12), ("4070", 12),
    ("4060 ti", 16), ("4060", 8), ("3090", 24), ("3080 ti", 12), ("3080", 10),
    ("3070", 8), ("3060 ti", 8), ("3060", 12), ("a6000", 48), ("l40", 48),
    ("7900 xtx", 24), ("7900 xt", 20), ("7900 gre", 16), ("7800 xt", 16), ("7700 xt", 12),
    ("7600 xt", 16), ("rx 7600", 8), ("9070 xt", 16), ("rx 9070", 16), ("9060 xt", 16),
    ("rx 9060", 8), ("6950 xt", 16), ("6900 xt", 16), ("6800 xt", 16), ("rx 6800", 16),
    ("6750 xt", 12), ("6700 xt", 12), ("6650 xt", 8), ("6600 xt", 8), ("rx 6600", 8),
    ("5700 xt", 8), ("vega 64", 8), ("vega 56", 8), ("r9700", 32), ("w7900", 48), ("w7800", 32),
)
# Datacenter parts never count (upstream: "datacenter parts never count"). Every
# SKU family, so one spelling cannot slip through.
_DATACENTER_HW = ("h100", "h200", "h800", "a100", "a800", "b100", "b200", "b300", "gb200", "gb300",
                  "mi210", "mi250", "mi300", "mi308", "mi325", "mi355", "tpu", "gaudi")
_GB_IN_TEXT = re.compile(r"(\d+(?:\.\d+)?)\s*gb", re.I)
_CARD_MULT = re.compile(r"(?<![\w.])(\d{1,2})\s*[x\u00d7]\s*(?=[a-z0-9])")


def measurement_card_gb(hardware: str) -> float | None:
    """The card the measurement ran on: an explicit 'NN GB' wins, else a known
    card model, else None (a host that is not a card, a cluster, a bare 'GPU').
    '2x RTX 3090' multiplies. Mirrors upstream's hardware_vram_gb()."""
    h = re.sub(r"\brx\s*-?(?=\d)", "rx ", (hardware or "").lower())  # 'RX7900' -> 'rx 7900'
    # '2x RTX 3090' multiplies; a 1-2 digit count only, so the 'x' of an AMD
    # suffix ('7900 xtx', '9070 xt') is never read as a count.
    mult_m = _CARD_MULT.search(h)
    mult = int(mult_m.group(1)) if mult_m else 1
    m = _GB_IN_TEXT.search(h)
    if m:
        return float(m.group(1)) * mult
    for card, gb in _CARD_VRAM:
        if card in h:
            return float(gb * mult)
    return None


def datacenter_hardware(hardware: str) -> bool:
    """True when the hardware names a datacenter part (H100/A100/B300/MI300...):
    a figure measured on one never describes a card a reader owns."""
    h = (hardware or "").lower()
    return any(k in h for k in _DATACENTER_HW) or re.search(r"\binstinct\b", h) is not None


def tps_label(e: dict) -> str:
    """The one place a ranked row's t/s becomes text, so the list the user reads
    and the tests that lock it can never disagree:
      '124 t/s'                          a figure from this host's card class
      '96 t/s (ROCm)'                    another backend
      '300 t/s (CUDA, 48 GB card)'       this backend, a bigger card
      '67 t/s (CUDA, card unknown)'      this backend, the hardware names no card
      '21000 t/s (CUDA, datacenter)'     a datacenter part: never a fit for a card
      'supported'                        no figure (engines[].tps absent)
    """
    if not e.get("measured_on"):
        return "supported"
    lbl = f"{e['tps']:.0f} t/s"
    if e.get("same_hw"):
        return lbl
    why = {"bigger": f"{e['card_gb']:.0f} GB card" if e.get("card_gb") else "bigger card",
           "unknown": "card unknown", "datacenter": "datacenter"}.get(e.get("card_class") or "")
    return f"{lbl} ({e['measured_on']}{', ' + why if why else ''})"


def measurement_backend(e: dict) -> str:
    """CUDA, ROCm, CPU or Metal: which hardware a measurement was taken on."""
    hw = " " + (e.get("hardware") or "").lower() + " "
    if APPLE.search(hw):
        return "Metal"
    if _CPU_ONLY.search(hw):
        return "CPU"
    if _AMD_GPU.search(hw) and not any(k in hw for k in _CUDA_HW):
        return "ROCm"
    if any(k in hw for k in _CPU_HW) and not any(k in hw for k in _CUDA_HW):
        return "CPU"
    text = hw + (e.get("quant") or "").lower()
    if _AMD_GPU.search(text) and not any(k in text for k in _CUDA_HW):
        return "ROCm"
    return "CUDA"


# ---- trend (the upstream index's ranking: band -> trend score -> posts) ------
TRENDING_DAYS, RECENT_DAYS = 7, 30
BAND_LABEL = ("trending", "recent", "stale")


def band(model: dict, today=None) -> int:
    """0 trending (seen <= 7 days ago), 1 recent (<= 30), 2 stale; as upstream."""
    from datetime import datetime, timezone
    today = today or datetime.now(timezone.utc)
    try:
        last = datetime.strptime(model.get("last_seen", ""), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return 0
    days = (today - last).days
    return 0 if days <= TRENDING_DAYS else 1 if days <= RECENT_DAYS else 2


def trend_score(model: dict) -> float:
    return float((model.get("engagement") or {}).get("trend_score") or 0)


def peak_tps(model: dict) -> float:
    """The model's fastest measured t/s, whatever the hardware (the store's tie-break)."""
    return max([_num(e.get("tps")) for e in model.get("engines") or []] or [0.0])


def trend_key(model: dict, today=None) -> tuple:
    """The key the store is sorted with, computed from its own fields — never its position:
    band (trending -> recent -> stale) -> trend score -> posts in the window -> peak t/s.

    `data/models.json` is replaced wholesale by the weekly sync and arrives sorted this way;
    reading that order back would make a line number decide the card's list, so `trend_list`
    sorts by this key instead. Measured on the vendored 2026-10-27 store: the key reproduces
    the committed order exactly (112 of 112 rows)."""
    eng = model.get("engagement") or {}
    return (band(model, today), -trend_score(model), -int(eng.get("posts_7d") or 0),
            -peak_tps(model), str(model.get("id") or ""))



def _engagement(e: dict) -> int:
    return int(e.get("likes") or 0) * 3 + int(e.get("reshares") or 0) * 5 + int(e.get("views") or 0) // 100


def rank_engines(model: dict, arch: str | None = None, ids: dict | None = None,
                 gb: float | None = None) -> list[dict]:
    """Engines that have an image for this host and are known to run `model` (a
    measurement in the registry, or `supported_engines`), best first:
      1. a figure measured on this host's kind of hardware AND on a card of this
         host's class or smaller — the only figure PROVEN to describe this card
         (`same_hw`, issue #225);
      2. a figure from this host's kind of hardware measured on a BIGGER card, or
         on hardware that names no card at all: it does not describe this card
         (`card_class` says which, the t/s label says so too);
      3. a figure from other hardware (ROCm / CPU / Metal), labelled by measured_on;
      4. a datacenter figure (H100/A100/B300/MI300 ...): never a fit for a card;
      5. listed as supported without a figure (tps 0, measured_on "").
    Within a rank: highest t/s, then trending engagement.

    `gb` is this host's card size. `None`/0 = unknown or not a card host (Apple
    Silicon, CPU, or no card detected): no card class applies and only the
    backend rule separates the ranks. Mapping: registry engine name ->
    engine id (containers/engines/params) -> image variant (host backend, else
    cpu, never a disabled #103 variant)."""
    arch = arch or host_arch()
    ids = ids if ids is not None else engine_ids()
    want = HOST_TO_MEASURED.get(arch, "CPU")
    # The card class is applied only where the host hardware IS a card: an Apple
    # Silicon or CPU host is judged by unified memory / RAM, never by a card tier.
    host_card = card_class_gb(gb) if (gb and gb > 0 and arch in CARD_ARCHES) else 0.0
    best: dict[str, dict] = {}

    def card_rank(mb, card, datacenter):
        """0 proven on this card class, 1 bigger card, 2 no card known,
        3 another backend, 4 datacenter, 5 no figure — see the docstring."""
        if datacenter:
            return 4      # a datacenter part never counts, whatever backend ran it
        if mb and mb != want:
            return 3
        if not mb:
            return 5
        if not host_card:
            return 0  # no card class on this host: the backend match is all we know
        if card is None:
            return 2
        return 0 if card <= host_card else 1

    def add(name, tps, engagement, mb, hardware, measurement=None):
        info = ids.get(name)
        if not info:
            return  # no container image (Metal-only / browser-only / no-skill engines)
        variant = arch if arch in info["variants"] else (
            None if arch == "metal" else ("cpu" if "cpu" in info["variants"] else None))
        if not variant:
            return
        card = measurement_card_gb(hardware)
        datacenter = datacenter_hardware(hardware)
        rank = card_rank(mb, card, datacenter)
        kind = "" if not mb else "datacenter" if datacenter else \
            {0: "proven", 1: "bigger", 2: "unknown"}.get(rank, "")
        row = {"engine": name, "id": info["id"], "variant": variant, "tps": tps, "engagement": engagement,
               "same_hw": rank == 0, "measured_on": mb, "rank": rank, "hardware": hardware,
               "card_gb": card, "card_class": kind, "formats": info.get("formats", []),
               "footprint": footprint(model, measurement)}
        cur = best.get(info["id"])
        if not cur or (-row["rank"], row["tps"], row["engagement"]) > (-cur["rank"], cur["tps"], cur["engagement"]):
            best[info["id"]] = row

    for e in model.get("engines") or []:
        add(e["engine"], _num(e.get("tps")), _engagement(e), measurement_backend(e),
            e.get("hardware", ""), e)
    for name in model.get("supported_engines") or []:
        add(name, 0.0, 0, "", "")
    return [r for r in sorted(best.values(),
                              key=lambda r: (r["rank"], -r["tps"], -r["engagement"], r["id"]))
            if engine_has_a_plan(model, r)]


def engine_has_a_plan(model: dict, eng: dict) -> bool:
    """True when the pick can actually DOWNLOAD `eng` for `model` — never on a measurement alone.

    A t/s figure is evidence that somebody ran the model; it is not evidence that this host can
    fetch it. The committed HF class table is generated WITH the store (`make sync-quant-catalog`
    derives its cell from the same model row), so for a model the table covers it is the authority:
    an engine with no cell for that model has no plan, and offering it makes `llgenie` fail minutes
    later at download time instead of at pick time.

    Two cases keep the previous behaviour on purpose:

    - **A model the table does not cover yet** (a store synced a step before its catalog): nothing
      is refused, and the pick falls back to live resolution — a refreshed registry never has to
      wait for the generator to be served.
    - **An own-checkpoint engine** (Strata, TensorFold) is covered by the same rule: its cell exists
      only for the family it really publishes, which is why the previous TensorFold-only gate and
      this one agree (issue #122, measured on the 2026-10-27 store: `MLX` on the ternary Bonsai
      rows, `Strata` on rows it does not serve, `vLLM` on an MLX-only repo, `llama.cpp` on a repo
      with no quantized file — 12 cells, all of them undownloadable).
    """
    mid = str(model.get("id") or "")
    cells = (quant_catalog().get("files") or {}).get(mid)
    if cells is None:
        return True  # the table is not rendered for this model: live resolution decides
    return str(eng.get("engine") or eng.get("id") or "") in cells


def card_class_gb(gb: float) -> float:
    """The card's nominal size: nvidia-smi reports a "16 GB" card as 16376 MiB
    (15.99 GiB), which must still count as 16 GB against the README VRAM column."""
    return float(round(gb)) if gb > 0 else gb


TIER_SECTION = "## 🔥 Trending for your card"
_TIER_HEADING = re.compile(r"^### Up to (\d+) GB$", re.M)


def registry_readme() -> Path | None:
    """The README vendored beside the store (`make sync-registry` writes both), when it is there."""
    src = os.environ.get("LLGENIE_REGISTRY_SRC") or str(REGISTRY_FILE)
    if src.startswith("http"):
        return None
    path = Path(src).with_name("trending-README.md")
    return path if path.is_file() else None


_TIER_CACHE: dict[tuple, dict[int, list[str]]] = {}


def tier_tables() -> dict[int, list[str]]:
    """Card tier (GB) -> the model names the vendored README's `### Up to N GB` table ranks, in
    its order.

    Those tables are upstream's TIER-LOCAL ranking: the speed bonus is earned only by a
    measurement that ran on a card of that size or smaller, so a 32 GB figure never tops the
    8 GB table (issue #669). Cached by path + mtime, so a synced README is read on the next
    call. No README beside the store (a bare `LLGENIE_REGISTRY_SRC` fixture) -> `{}`, and the
    card's list is then the computed store order alone.
    """
    path = registry_readme()
    if path is None:
        return {}
    stat = path.stat()
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    if key not in _TIER_CACHE:
        text = path.read_text()
        section = text.split(TIER_SECTION, 1)[1].split("\n## ", 1)[0] if TIER_SECTION in text else ""
        parts = _TIER_HEADING.split(section)
        _TIER_CACHE.clear()  # one store, one README: a previous run's tables never leak in
        _TIER_CACHE[key] = {int(parts[i]): re.findall(r"^\| \[\*\*(.+?)\*\*\]", parts[i + 1], re.M)
                            for i in range(1, len(parts), 2)}
    return _TIER_CACHE[key]


def card_tier(gb: float) -> int | None:
    """The published tier a card reads: the smallest tier at or above the card's nominal size,
    and the largest published tier for a bigger card (the tables stop at 48 GB)."""
    tiers = sorted(tier_tables())
    if not tiers or not gb:
        return None
    want = card_class_gb(gb)
    return next((t for t in tiers if want <= t), tiers[-1])


def tier_rank(gb: float) -> dict[str, int]:
    """Model name -> its published position in this card's tier-local ranking ({} when the
    store has no README beside it)."""
    tier = card_tier(gb)
    return {name: i for i, name in enumerate(tier_tables().get(tier or 0) or [])}


def ran_on_gb(model: dict) -> float | None:
    """The smallest card one of this model's MEASURED runs actually ran on, or None.

    A measurement is a run: `engines[].tps` above zero, on hardware that names a card size
    (`measurement_card_gb`). A datacenter part (H100/A100/MI300 ...) is not a card a reader
    owns, so it is never evidence of what this card does — the rule `rank_engines` applies to a
    figure (issue #669).
    """
    cards = [measurement_card_gb(e.get("hardware", ""))
             for e in model.get("engines") or []
             if _num(e.get("tps")) and not datacenter_hardware(e.get("hardware", ""))]
    cards = [c for c in cards if c is not None]
    return min(cards) if cards else None


def vram_min_gb(model: dict) -> float | None:
    """The model's stated minimum card size (`vram_min`) in GB, or None when it states none.

    `vram_min` is the contract's measured minimum; `vram_tier` is the README's display
    bucket. Measured on the 2026-10-27 store at a 16 GB card, in all 8 rows where the two
    disagree the README's VRAM column agrees with `vram_min` and never with `vram_tier`
    (issue #669) — so the label is not the gate, the measurement is.
    """
    return stated_gb(model.get("vram_min")) or None


def vram_label(model: dict) -> str:
    """The VRAM figure the gate reads, as the printed list shows it: the store's measured
    minimum (`vram_min`) when it states one, else the README's display `vram_tier`.

    The list is gated by `fits()`, so this is the same field the gate used: a row admitted at
    its 12 GB measured minimum never prints "48GB" next to itself, which is exactly the
    contradiction #669 is about (issue #669).
    """
    need = vram_min_gb(model)
    if need is None:
        return str(model.get("vram_tier") or "")
    return f"{need:g}GB"


GATE_EVIDENCE = ("run", "min", "weights", "label", "unknown", "")

#: The system RAM a measurement's hardware string names: `4GB VRAM + 32GB system RAM`,
#: `RTX 3060 12GB + 16GB DDR4`. A unified-memory box says `unified`, which is its card's pool,
#: so it is not read here (the host's own RAM is what `ram_gb` states).
_RAM_IN_HW = re.compile(r"(\d+(?:\.\d+)?)\s*GB\s*(?:of\s+)?(?:system\s+ram|ram|ddr\d?)\b", re.I)
# Apple / Metal "unified memory" boxes: a measurement on one is never a cuda/vulkan/rocm/cpu
# card a container host can reproduce, so it must not admit a model there (issue #669).
_APPLE_RUN = ("apple", "mac", "macbook", "imac", "m1 ", "m2 ", "m3 ", "m4 ", "m5 ",
              "unified memory", "metal", " mlx")


def _is_apple_run(hardware: str) -> bool:
    return any(k in (hardware or "").lower() for k in _APPLE_RUN)


def admitting_measurement(model: dict, gb: float, arch: str | None = None) -> dict | None:
    """The measurement that proves this model runs on a card of `gb`: the smallest `ran on`
    card at or below the card, or None when no run is at that size.

    A run is evidence only on hardware this host can reproduce: a datacenter part is never a
    card a reader owns, and — for a container/GPU host (`arch` not a Metal/Apple one) — an
    Apple/Metal "unified memory" run is never a cuda/vulkan/rocm/cpu card at all, so it cannot
    admit the model there (issue #669: an MLX "M1 Pro 16GB" row beside a "M4 Max 128GB" must not
    gate a 16 GB cuda host). `arch=None` (a bare gate call) counts every card-sized run.
    """
    card = card_class_gb(gb)
    apple_excluded = arch is not None and arch not in ("metal", "mlx", "apple")
    best, best_card = None, None
    for e in model.get("engines") or []:
        if not _num(e.get("tps")):
            continue
        hw = e.get("hardware", "")
        if datacenter_hardware(hw):
            continue
        if apple_excluded and _is_apple_run(hw):
            continue
        run_card = measurement_card_gb(hw)
        if run_card is None or run_card > card:
            continue
        if best_card is None or run_card < best_card:
            best, best_card = e, run_card
    return best


def card_evidence(model: dict, gb: float, arch: str | None = None) -> str:
    """WHICH evidence admits `model` on a card of `gb`: `"run"`, `"min"`, `"weights"`,
    `"label"`, `"unknown"` (no card on this host) or `""` (nothing admits it).

    The order is upstream's own (`data/MODEL_CONTRACT.md`, the README's `VRAM` column): a model
    is placed on a card only with evidence — a proved `ran on` figure, the declared minimum, or
    the labelled `weights-only` fit. `vram_tier` is the README's *display bucket* and decides
    only for a row that states no measured figure at all, so the label can never keep out a
    model the store proves runs here (issue #669).
    """
    if gb <= 0:
        return "unknown"  # no card on this host: the gate has nothing to compare against
    if admitting_measurement(model, gb, arch) is not None:
        return "run"
    card = card_class_gb(gb)
    need = vram_min_gb(model)
    if need is not None and need <= card:
        return "min"
    weight = stated_budget_gb(model)
    if weight is not None and weight <= card:
        return "weights"  # the labelled weights-only fit: no run at this size, the file does fit
    if need is not None:
        return ""  # the store states its requirement and this card is below it
    return "label" if _num(model.get("vram_tier")) <= card else ""


def ram_floor_gb(model: dict, evidence: str, gb: float) -> float | None:
    """The system RAM the ADMITTING evidence states, or None when it states none.

    A run is judged by its own footprint — the measurement's `system_ram_min` when it states
    one, else the RAM its hardware names (`4GB VRAM + 32GB system RAM`), else the model's
    figure — because that is the run this card is being told about (`footprint()`: "the
    measurement's own value wins for that engine"). A declared minimum or a weights-only fit is
    judged by the model's own `system_ram_min`.
    """
    if evidence == "run":
        run = admitting_measurement(model, gb) or {}
        stated = stated_gb(run.get("system_ram_min"))
        if stated:
            return stated
        named = _RAM_IN_HW.search(str(run.get("hardware") or ""))
        if named:
            return float(named.group(1))
    return stated_gb(model.get("system_ram_min"))


def fits(model: dict, gb: float, ram_gb: float | None = None, arch: str | None = None) -> bool:
    """True when the store's measured evidence places this model on a card of `gb` — a run on a
    card that size or smaller, else `vram_min`, else the stated `weight_gb` (issue #669) — and,
    when the admitting evidence states one, this host's RAM is at least its `system_ram_min`.

    `system_ram_min` is the contract's optional system-RAM requirement (`MODEL_CONTRACT.md`:
    "the CPU and Metal tables are RAM-bound … partial offload keeps the un-offloaded layers +
    KV cache in system RAM"). It is a hard floor, never derived from `vram_min`, so a host
    below it cannot run the model at the stated quality however much VRAM it has.
    `arch` threads the host's compute kind into the run evidence (Apple runs never gate a
    container/GPU host). `None` counts every card-sized run.
    """
    evidence = card_evidence(model, gb, arch)
    if not evidence:
        return False
    floor = ram_floor_gb(model, evidence, gb)
    return not (floor and ram_gb and ram_gb < floor)


# ---- the contract's stated footprint (MODEL_CONTRACT.md, issue #414) ----------------------
# `data/models.json` states what a run needs: `weight_gb` (weight bytes before any context),
# `context_tokens` (the window the KV cache is sized for), `system_ram_min`, `storage_offload`
# and `engine_min_version`. They may sit on the model OR on one `engines[]` measurement ("the
# footprint of that run"), and the measurement's own value wins for that engine.
FOOTPRINT_FIELDS = ("weight_gb", "context_tokens", "system_ram_min", "storage_offload",
                    "engine_min_version")
_GB = re.compile(r"(\d+(?:\.\d+)?)\s*(gb|gib|mb|mib)?", re.IGNORECASE)
_TOKENS = re.compile(r"(\d+(?:\.\d+)?)\s*([kKmM])?\b")


def stated_gb(value) -> float | None:
    """A stated size as GB: '5.95GB Q4_K_M' -> 5.95, '640GB NVMe, experts on SSD' -> 640,
    '16GB' -> 16, '800MB' -> 0.78. None when no number is stated (never invented)."""
    if value is None or isinstance(value, bool):
        return None
    m = _GB.search(str(value))
    if not m:
        return None
    n = float(m.group(1))
    unit = (m.group(2) or "gb").lower()
    return round(n / 1024, 2) if unit.startswith("m") else n


def stated_context(value) -> int | None:
    """A stated context window in tokens: '131072' -> 131072, '128K' -> 131072,
    '1M' -> 1048576, '32 768' -> 32768. None when the value states no number."""
    if value is None or isinstance(value, bool):
        return None
    m = _TOKENS.search(str(value).replace(",", " "))
    if not m:
        return None
    n = float(m.group(1))
    unit = (m.group(2) or "").lower()
    if unit == "k":
        n *= 1024
    elif unit == "m":
        n *= 1024 * 1024
    return int(n)


def footprint(model: dict, measurement: dict | None = None) -> dict:
    """The stated footprint for `model`, or for one engine `measurement` of it.

    The measurement's own value wins (the store states it for THAT run); the model's covers
    the rest. Only stated fields appear — an absent field is a reported data gap, never a
    fabricated default.
    """
    out: dict = {}
    for field in FOOTPRINT_FIELDS:
        value = (measurement or {}).get(field)
        if value in (None, "", [], {}):
            value = model.get(field)
        if value not in (None, "", [], {}):
            out[field] = value
    return out


def stated_budget_gb(model: dict, measurement: dict | None = None) -> float | None:
    """The stated weight footprint of a run, as GB (None when the store states none)."""
    return stated_gb(footprint(model, measurement).get("weight_gb"))


def registry_today(registry: dict):
    """The date the upstream README ranking was computed for (its generated_utc), so
    bands (trending/recent/stale) match the README exactly, not the local clock."""
    from datetime import datetime, timezone
    try:
        return datetime.strptime(registry.get("generated_utc", "")[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def card_order(rows: list[dict], gb: float | None, registry: dict) -> list[dict]:
    """`rows` in the order the card's list shows them.

    The vendored README's tier-local ranking for that card comes first (issue #669), then every
    row it does not rank — a model with no post in the window keeps no trend rank, but it still
    fits, so it stays selectable — in the store's own trend order. Both halves are COMPUTED:
    the tier table is read from the vendored README, the remainder from `trend_key` on the
    store's fields. `data/models.json`'s file position is never read.
    """
    rank = tier_rank(gb) if gb is not None else {}
    today = registry_today(registry)
    return sorted(rows, key=lambda m: (rank.get(str(m.get("name")), len(rank)), *trend_key(m, today)))


def trend_list(registry: dict, gb: float | None = None, ram_gb: float | None = None,
               arch: str | None = None) -> list[dict]:
    """The models this card fits, in the card's own order.

    Membership is the gate (`fits`: measured evidence, plus the stated `system_ram_min` floor);
    order is the vendored README's `### Up to N GB` tier-local ranking for this card, then the
    rows it does not rank in the store's trend order (`card_order`). Measured on the vendored
    2026-10-27 store, 8 GB: the published top is `Qwen3.6-35B-A3B`, `Bonsai 2 9B`, … while the
    global order (which this used to return) is `Bonsai 2 9B`, `Qwen3.6-35B-A3B`, …
    """
    gb = card_gb() if gb is None else gb
    return card_order([m for m in registry.get("models") or [] if fits(m, gb, ram_gb, arch)],
                      gb, registry)



def rank_models(registry: dict, arch: str | None = None, gb: float | None = None, today=None) -> list[dict]:
    """trend_list() models that have a runnable engine here, README order kept."""
    ids = engine_ids()
    rows = []
    for m in trend_list(registry, gb, arch=arch):
        engines = rank_engines(m, arch, ids, gb)
        if engines:
            rows.append({"model": m, "engines": engines, "tps": engines[0]["tps"]})
    return rows


DOWNLOADABLE = ("gguf", "litertlm", "mlx-safetensors", "safetensors")  # formats llgenie can fetch


def recommend(registry: dict, arch: str | None = None, gb: float | None = None,
              fmt: str | None = None, limit: int | None = None, today=None, all_rows: bool = False,
              ram_gb: float | None = None) -> list[dict]:
    """The README trend list that fits this card, in README order, with each model's
    engines here (no Hub lookups). fmt narrows the engines to readers of that
    format; `why` = "" when an engine is left, else the reason. all_rows=False
    keeps only rows with an engine."""
    ids = engine_ids()
    rows = []
    for m in trend_list(registry, gb, ram_gb, arch):
        everything = rank_engines(m, arch, ids, gb)
        engines = [e for e in everything if fmt is None or fmt in e.get("formats", [])]
        if engines:
            why = ""
        elif everything:
            why = f"its engines here ({', '.join(e['id'] for e in everything)}) do not read {fmt.upper()}"
        else:
            names = sorted({e["engine"] for e in m.get("engines") or []} | set(m.get("supported_engines") or []))
            why = f"no {arch or host_arch()} engine image ({', '.join(names)})"
        if why and not all_rows:
            continue
        rows.append({"model": m, "engines": engines, "tps": engines[0]["tps"] if engines else 0.0, "why": why,
                     "footprint": footprint(m)})
    return rows[:limit] if limit else rows


def offer(registry: dict, arch: str | None = None, gb: float | None = None,
          root: Path | None = None, ram_gb: float | None = None) -> list[dict]:
    """The rows plain `llgenie` prints: the README trend list that fits the card, in
    README order. For each model the engines here are matched to a format llgenie
    can get for it: the local copy's format, else a download plan that fits
    (plan_download per format). Each engine gets `use_format`; engines without a
    usable format are dropped; a row with none left gets `why`.
    Strata reads only the files its setup.py names, so it gets its own plan and local
    copy (`engine_plans` / `engine_local`), never the generic GGUF of the format.
    TensorFold likewise serves only its own MLX checkpoints (TensorFold/<base>-MLX-*,
    issue #114), so it gets its own plan / local copy too."""
    arch = arch or host_arch()
    gb = card_gb() if gb is None else gb
    rows = recommend(registry, arch, gb, all_rows=True, ram_gb=ram_gb)
    own = ("strata", "tensorfold")  # engines that read only their own checkpoints
    for r in rows:
        r["local"] = resolve_local(r["model"], root)
        r["plans"], r["engine_plans"], r["engine_local"] = {}, {}, {}
        if r["why"]:
            continue
        local_fmt = model_format(r["local"]) if r["local"] else None
        generic = [e for e in r["engines"] if e["id"] not in own]
        wanted = [f for f in DOWNLOADABLE if any(f in e["formats"] for e in generic)]
        for f in wanted:
            if f != local_fmt:
                r["plans"][f] = plan_download(r["model"], gb, ram_gb, f, arch)
        usable = {f for f, pl in r["plans"].items() if pl} | ({local_fmt} if local_fmt else set())
        kept, own_missed = [], []
        for e in r["engines"]:
            if e["id"] == "strata":
                here = strata_local(root, ram_gb) if strata_serves(r["model"]) else None
                plan = None if here else plan_download(r["model"], gb, ram_gb, "gguf", arch, engine="strata")
                if here or plan:
                    r["engine_local"]["strata"], r["engine_plans"]["strata"] = here, plan
                    kept.append({**e, "use_format": "gguf"})
                continue
            if e["id"] == "tensorfold":
                here = tensorfold_local(r["model"], root)
                plan = None if here else plan_download(r["model"], gb, ram_gb, "mlx-safetensors", arch,
                                                       engine="tensorfold")
                if here or plan:
                    r["engine_local"]["tensorfold"], r["engine_plans"]["tensorfold"] = here, plan
                    kept.append({**e, "use_format": "mlx-safetensors"})
                else:
                    own_missed.append("tensorfold")
                continue
            fmt = next((f for f in e["formats"] if f == local_fmt), None) or \
                next((f for f in e["formats"] if f in usable), None)
            if fmt:
                kept.append({**e, "use_format": fmt})
        r["engines"] = kept
        r["tps"] = kept[0]["tps"] if kept else 0.0
        if not kept:
            r["why"] = _no_fit_reason(r["model"], wanted, gb, arch, ram_gb, own_missed)
    return rows


def engine_plan(row: dict, eng: dict) -> dict | None:
    """The download for `eng` in an offer() row: its own plan, else its format's."""
    if eng["id"] in row.get("engine_plans", {}):
        return row["engine_plans"][eng["id"]]
    return row.get("plans", {}).get(eng["use_format"])


def engine_local(row: dict, eng: dict) -> Path | None:
    """The local copy `eng` loads in an offer() row (Strata: its own shard set)."""
    if eng["id"] in row.get("engine_local", {}):
        return row["engine_local"][eng["id"]]
    return row.get("local")


def _no_fit_reason(model: dict, fmts: list[str], gb: float, arch: str, ram_gb,
                   own_missed: list[str] | None = None) -> str:
    """Why no engine is left: the smallest download of each engine that could run it
    against what this host holds (TensorFold: its own smallest checkpoint).

    The store's own stated footprint comes first, because it is a measurement of a run rather
    than an estimate of a file: a `system_ram_min` above this host's RAM means no download can
    fix it, and a stated `weight_gb` above the budget says the run cannot be repeated here.
    """
    stated = footprint(model)
    needs_ram = stated_gb(stated.get("system_ram_min"))
    if needs_ram and ram_gb and ram_gb < needs_ram:
        return (f"needs {needs_ram:g} GB system RAM, this host has {ram_gb:.0f} GB "
                f"(stated in the registry)")
    budget = weight_budget_gb(gb, is_moe(model), ram_gb, arch)
    parts = []
    stated_weight = stated_gb(stated.get("weight_gb"))
    if stated_weight and stated_weight > budget:
        parts.append(f"stated weights are {stated_weight:g} GB")
    if "tensorfold" in (own_missed or []):
        s = tensorfold_smallest(model)
        parts.append(f"smallest TensorFold MLX is {s['size'] / 2**30:.0f} GB" if s
                     else "TensorFold publishes no MLX checkpoint of it")
    if "gguf" in fmts:
        ws = gguf_weights(gguf_repo(model) or "")
        if ws:
            parts.append(f"smallest GGUF is {ws[0]['size'] / 2**30:.0f} GB")
    if parts:
        reason = f"{', '.join(parts)} > {budget:.0f} GB this host can hold"
        if stated.get("storage_offload"):
            reason += f"; the registry states it runs off storage ({stated['storage_offload']})"
        return reason
    return f"no {'/'.join(fmts) or 'supported'} download of it fits this host"


def _tokens(s: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9.]+", s.lower()) if t and t not in {"gguf", "it", "instruct"}]


def resolve_local(model: dict, root: Path | None = None) -> Path | None:
    """A file/dir under ~/models whose name contains the model's name tokens."""
    root = root or models_root()
    want = _tokens(model.get("name") or model["id"])
    if not root.exists() or not want:
        return None
    hits = []
    for p in root.rglob("*"):
        if p.name.endswith((".incomplete", ".progress.log")):
            continue
        name = p.name.lower()
        if all(t in name for t in want) and (p.suffix in (".gguf", ".litertlm")
                                             or (p.is_dir() and (p / "config.json").exists())):
            hits.append(p)
    return max(hits, key=lambda p: p.stat().st_size if p.is_file() else 0) if hits else None


def repo_for(model: dict) -> str:
    fmts = model.get("formats") or []
    gguf = next((f["hf"] for f in fmts if "gguf" in (f.get("name", "") + f.get("hf", "")).lower()), None)
    return gguf or (fmts[0]["hf"] if fmts else model["hf"])


HUB_CACHE_TTL = int(os.environ.get("LLGENIE_HUB_CACHE_TTL", "3600"))  # seconds; 0 = off


def _hub_cache_dir() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "llgenie" / "hub"


def _hub_ipv4(host: str, port: int) -> list:
    """IPv4 addresses for a Hub host. Empty when the host has no A record."""
    import socket
    try:
        return socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
    except socket.gaierror:
        return []


def _ipv4_urlopen(req: urllib.request.Request, timeout: float):
    """urlopen over IPv4 where an A record exists (the transport, not the policy).

    macOS GitHub runners hang on huggingface.co's IPv6 address; the default lookup
    is used when there is no A record. The retry budget around this lives in
    `hf_auth.hub_open` (issue #339), which `_hub_open` passes this to.
    """
    import socket
    orig = socket.create_connection

    def create_connection(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT,
                          source_address=None, *, all_errors=False):
        host, port = address
        infos = _hub_ipv4(host, port)
        if not infos:
            return orig(address, timeout, source_address, all_errors=all_errors)
        err = None
        for af, socktype, proto, _canon, sa in infos:
            sock = socket.socket(af, socktype, proto)
            try:
                if timeout is not None and timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
                    sock.settimeout(timeout)
                if source_address:
                    sock.bind(source_address)
                sock.connect(sa)
                return sock
            except OSError as e:
                err = e
                sock.close()
        if err is not None:
            raise err
        return orig(address, timeout, source_address, all_errors=all_errors)

    socket.create_connection = create_connection
    try:
        return urllib.request.urlopen(req, timeout=timeout)  # noqa: S310
    finally:
        socket.create_connection = orig


def _hub_open(req: urllib.request.Request, timeout: float):
    """Open a Hub API URL: IPv4 transport, ONE shared transient budget (issue #339)."""
    return hub_open(req, timeout=timeout, opener=_ipv4_urlopen)


def _hub_json(url: str):
    """GET a Hub API URL as JSON. Answers are cached on disk for HUB_CACHE_TTL.

    The transient budget is the shared one (`hf_auth.hub_open`, issue #339): a 429
    waits the Hub's own window (twice at most), 5xx and transport errors retry on the
    doubling ladder, and a definitive status — a missing or gated repo — raises on the
    first answer. This used to be a second ladder of its own (3 tries), which is how
    the macos unit lane turned one exhausted 429 into "this repo has no files".
    """
    import hashlib
    import time
    cache = _hub_cache_dir() / (hashlib.sha256(url.encode()).hexdigest() + ".json")
    if HUB_CACHE_TTL and cache.exists() and time.time() - cache.stat().st_mtime < HUB_CACHE_TTL:
        try:
            return json.loads(cache.read_text())
        except ValueError:
            pass
    req = authorize(urllib.request.Request(url, headers={"User-Agent": "llgenie"}))
    with _hub_open(req, 30) as r:
        data = json.load(r)
    if HUB_CACHE_TTL and data is not None:
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(data))
        except OSError:
            pass
    return data


def _not_weights(path: str) -> bool:
    """Files in a GGUF repo that are not a loadable model: vision projectors, the
    imatrix, and MTP/draft heads shipped beside the model (unsloth `MTP/mtp-*.gguf`)."""
    low = path.lower()
    name = low.rsplit("/", 1)[-1]
    return "mmproj" in low or "imatrix" in name or name.startswith("mtp-") or low.startswith("mtp/")


def _tree(repo: str, revision: str = "main") -> list[dict]:
    key = f"{repo}@{revision}"
    if key not in _TREE_CACHE:
        try:
            files = _hub_json(f"{HF}/api/models/{repo}/tree/{revision}?recursive=true")
        except urllib.error.HTTPError as e:
            # A definitive answer (a missing or gated repo) is not a blip — but a
            # throttle or a 5xx is, and caching an empty tree for it would turn one
            # failed GET into "this repo has no files" for the whole process: the
            # macos unit lane failed exactly that way (issue #339). The shared budget
            # in `hf_auth.hub_open` has already waited the window out by now.
            if e.code in TRANSIENT_HTTP:
                return []
            _TREE_CACHE[key] = []
            return []
        except (urllib.error.URLError, TimeoutError, OSError):
            return []  # a blip is not an empty repo; the next call tries again
        if not isinstance(files, list):
            return []
        _TREE_CACHE[key] = files
    return _TREE_CACHE[key]


_TREE_CACHE: dict[str, list] = {}


def gguf_weights(repo: str) -> list[dict]:
    """Loadable GGUF models in `repo`: one entry per single file or per split set
    (`-00001-of-0000N.gguf` shards summed), as {path, size, files}. `path` is what
    the server loads (the first shard); `files` is everything to download."""
    sets: dict[str, dict] = {}
    for f in _tree(repo):
        path = f.get("path", "")
        if f.get("type") != "file" or not path.endswith(".gguf") or _not_weights(path):
            continue
        key = SHARD.sub("", path)
        w = sets.setdefault(key, {"path": path, "size": 0, "files": []})
        w["size"] += int(f.get("size") or 0)
        w["files"].append(path)
    for w in sets.values():
        w["files"].sort()
        w["path"] = w["files"][0]
    return sorted(sets.values(), key=lambda w: w["size"])


def gguf_files(repo: str) -> list[tuple[str, int]]:
    """Single-file .gguf models in `repo` as (path, size) (no shards, no mmproj,
    imatrix or MTP heads)."""
    return [(w["path"], w["size"]) for w in gguf_weights(repo) if len(w["files"]) == 1]


def gguf_repo(model: dict) -> str | None:
    """A Hub repo with GGUF models for `model`: the registry repo when it has them,
    else the most-downloaded repo named `<name>-GGUF` (same org first, then any
    org), else the most-downloaded GGUF repo whose id contains the name."""
    base = repo_for(model)
    if gguf_weights(base):
        return base
    org, name = base.split("/", 1) if "/" in base else ("", base)
    want = (name + "-gguf").lower()
    hits = _hub_json(f"{HF}/api/models?search={urllib.parse.quote(name)}&filter=gguf"
                     f"&sort=downloads&direction=-1&limit=50")
    ids = [h["id"] for h in hits]
    exact = [i for i in ids if i.split("/", 1)[-1].lower() == want]
    ranked = ([i for i in exact if i.split("/")[0].lower() == org.lower()] + exact
              + [i for i in ids if name.lower() in i.lower()])
    for repo in dict.fromkeys(ranked):
        if gguf_weights(repo):
            return repo
    return None


def system_ram_gb() -> float:
    """System RAM in GiB (LLGENIE_SYSTEM_RAM_BYTES overrides it: tests / CI seam)."""
    env = os.environ.get("LLGENIE_SYSTEM_RAM_BYTES", "")
    if env.isdigit():
        return int(env) / 2**30
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) / 2**20
    except OSError:
        pass
    return 0.0


def is_moe(model: dict) -> bool:
    return "moe" in (str(model.get("type", "")) + " " + str(model.get("params", ""))).lower()


def weight_budget_gb(gb: float, moe: bool = False, ram_gb: float | None = None, arch: str = "cuda") -> float:
    """Largest model download that still runs on this host.
    Dense: 80% of the card minus 1 GiB (KV cache + compute buffers stay on the GPU;
    16 GB -> 11.8 GB). MoE on a GPU host: plus system RAM minus 4 GiB for the OS,
    because llama.cpp keeps the experts in RAM (--fit / mmap). On a cpu host the
    "card" already is system RAM, so nothing is added. On a metal host (Apple
    Silicon, unified memory, issue #114) the GPU may wire about 70% of RAM (MLX's
    default process budget; Metal's recommended working set is close to it): 70%
    minus 3 GiB process reserve minus 4 GiB for KV cache (48 GB -> 26.6 GB), MoE or
    not, since there is no separate RAM to spill the experts into.
    (Strata is not sized by this rule: it installs what its own setup.py picks,
    strata_choice.)"""
    if gb <= 0:
        return float("inf")
    if arch == "metal":
        return max(gb * 0.7 - 7, gb * 0.4)
    card = max(gb * 0.8 - 1, gb * 0.5)
    if not moe or arch == "cpu":
        return card
    ram = system_ram_gb() if ram_gb is None else ram_gb
    return card + max(0.0, ram - 4)


def pick_weights(repo: str, gb: float, moe: bool = False, ram_gb: float | None = None,
                 arch: str = "cuda") -> dict | None:
    """The largest GGUF model in `repo` within weight_budget_gb (None when none fits)."""
    budget = weight_budget_gb(gb, moe, ram_gb, arch) * 2**30
    ok = [w for w in gguf_weights(repo) if w["size"] <= budget]
    return max(ok, key=lambda w: w["size"]) if ok else None


# ---------------------------------------------------------------------------
# Strata: the files its setup.py names, never a guess (OpenSpec fix-engine-model-download-map).
# data/strata_models.json is setup.py's MODELS / FAMILIES / HF_REVISIONS at the pinned
# engine commit (make sync-strata-models; make check-strata-models fails on drift).
# ---------------------------------------------------------------------------
STRATA_MODELS = REPO / "data" / "strata_models.json"


def strata_map() -> dict:
    return json.loads(STRATA_MODELS.read_text())


def strata_serves(model: dict) -> bool:
    """True when `model` is the one Strata runs: its Hub name is in Strata's default
    family's repo (Qwen/Qwen3.8-Flash-Next -> ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF).
    A family the store marks `hub: false` (no Hub URL, e.g. `nvfp4`) has no repo to match."""
    name = str(model.get("hf") or "").rsplit("/", 1)[-1].lower()
    fam = next(iter(strata_map()["families"].values()))
    return bool(name) and bool(fam.get("repo")) and name in fam["repo"].lower()


def strata_choice(ram_gb: float) -> tuple[str, str]:
    """(family, size) Strata's `setup.py --yes` installs on a PC with `ram_gb` GiB of RAM:
    the first family; its sizes in setup's order, an experimental one last; IQ3_XXS from
    60 GB of RAM, else the first size (setup.py main(), step 2)."""
    s = strata_map()
    family = next(iter(s["families"]))
    names = [m for m, d in s["models"].items() if family in d["families"]]
    names.sort(key=lambda m: bool(s["models"][m]["experimental"]))
    return family, ("IQ3_XXS" if ram_gb >= 60 and "IQ3_XXS" in names else names[0])


def strata_files(family: str, size: str) -> list[str]:
    """Repo paths of every shard of a Strata choice (setup.py model_file / model_shards).

    A family the store marks `hub: false` has no repo/subdir to build a path in, so a caller
    asking for its files is a caller that must be told, not given a URL built from None."""
    s = strata_map()
    fam, d = s["families"][family], s["models"][size]
    if not fam.get("repo"):
        raise ValueError(f"[strata] family {family!r} is not Hub-downloadable (no repo)")
    pattern, shards = d.get("file", fam["file"]), d.get("shards", fam["shards"])
    sub = fam["subdir"].format(q=size)
    return [sub + pattern.format(q=size, i=i) for i in range(1, shards + 1)]


def strata_first_shards() -> dict[str, tuple[str, str]]:
    """First-shard file name -> (family, size): what setup.py's gguf_choice maps."""
    s = strata_map()
    out = {}
    for f in s["families"]:
        if not s["families"][f].get("repo"):
            continue  # not Hub-downloadable: it has no first shard to map
        for m, d in s["models"].items():
            if f in d["families"]:
                out.setdefault(Path(strata_files(f, m)[0]).name, (f, m))
    return out


def strata_plan(ram_gb: float | None = None) -> dict | None:
    """The download for Strata on this host: its own choice's shards from its own repo at
    its pinned revision, sizes from the Hub. None when a shard is missing on the Hub."""
    ram = system_ram_gb() if ram_gb is None else ram_gb
    family, size = strata_choice(ram)
    fam = strata_map()["families"][family]
    files = strata_files(family, size)
    sizes = {f["path"]: int(f.get("size") or 0) for f in _tree(fam["repo"], fam["revision"])}
    if not all(sizes.get(f) for f in files):
        return None
    return {"repo": fam["repo"], "revision": fam["revision"], "path": files[0], "files": files,
            "size": sum(sizes[f] for f in files), "strata": {"family": family, "model": size}}


def strata_local(root: Path | None = None, ram_gb: float | None = None) -> Path | None:
    """A complete set of Strata shards under the models root (the first shard), this
    host's choice first; partial sets and files Strata cannot run are ignored."""
    root = root or models_root()
    if not root.exists():
        return None
    firsts = strata_first_shards()
    want = Path(strata_files(*strata_choice(system_ram_gb() if ram_gb is None else ram_gb))[0]).name
    hits = []
    for p in root.rglob("*.gguf"):
        if p.name in firsts:
            f, m = firsts[p.name]
            if all((p.parent / Path(x).name).is_file() for x in strata_files(f, m)):
                hits.append(p)
    return min(hits, key=lambda p: (p.name != want, str(p))) if hits else None


def pick_file(repo: str, gb: float, moe: bool = False, ram_gb: float | None = None) -> tuple[str, int] | None:
    """(path, total size) of pick_weights, else the smallest model in the repo."""
    w = pick_weights(repo, gb, moe, ram_gb)
    if w is None:
        allw = gguf_weights(repo)
        if not allw:
            return None
        w = allw[0]
    return w["path"], w["size"]


_SNAPSHOT_SKIP = re.compile(r"(^|/)(\.gitattributes|readme\.md)$|\.(png|jpe?g|gif|ipynb|md)$", re.I)
_LITERT_VARIANT = re.compile(r"[-_](gpu|web)\b|_(google|intel|qualcomm|mediatek|samsung)", re.I)


def _model_repos(model: dict) -> list[str]:
    """Every Hub repo the registry names for the model (formats[].hf, then hf)."""
    out = [f["hf"] for f in model.get("formats") or [] if f.get("hf")] + ([model["hf"]] if model.get("hf") else [])
    return list(dict.fromkeys(out))


def _snapshot(repo: str) -> dict | None:
    """A whole HF model repo (config.json + *.safetensors) as one download."""
    files = [f for f in _tree(repo) if f.get("type") == "file"]
    names = {f["path"] for f in files}
    if "config.json" not in names or not any(n.endswith(".safetensors") for n in names):
        return None
    keep = [f for f in files if not _SNAPSHOT_SKIP.search(f["path"])]
    return {"repo": repo, "path": "", "dir": True, "size": sum(int(f.get("size") or 0) for f in keep),
            "files": sorted(f["path"] for f in keep)}


def plan_download(model: dict, gb: float | None = None, ram_gb: float | None = None,
                  fmt: str = "gguf", arch: str | None = None, engine: str | None = None) -> dict | None:
    """What llgenie would download for `model` in `fmt` on this host, or None when
    nothing of it in that format fits. {repo, path, size, files[, dir]}:
      gguf             largest GGUF in the GGUF repo within the budget (shards summed)
      litertlm         the generic .litertlm (no gpu/web/vendor build) that fits
      mlx-safetensors  a registry repo named MLX with config.json + safetensors (whole repo),
                       else the most-downloaded `<name>-MLX*` Hub repo that fits
      safetensors      a non-MLX registry repo with config.json + safetensors (whole repo)
    engine="tensorfold": only TensorFold's own MLX checkpoints (tensorfold_plan)."""
    gb = card_gb() if gb is None else gb
    arch = arch or host_arch()
    budget = weight_budget_gb(gb, is_moe(model), ram_gb, arch) * 2**30
    if engine == "strata":  # only the files Strata's setup.py names
        return strata_plan(ram_gb) if fmt == "gguf" and strata_serves(model) else None
    if engine == "tensorfold":  # only the checkpoints TensorFold publishes for its families
        return tensorfold_plan(model, budget) if fmt == "mlx-safetensors" else None
    if fmt == "gguf":
        repo = gguf_repo(model)
        if not repo:
            return None
        w = pick_weights(repo, gb, is_moe(model), ram_gb, arch)
        return {"repo": repo, **w} if w else None
    if fmt == "litertlm":
        for repo in _model_repos(model):
            fs = [(f["path"], int(f.get("size") or 0)) for f in _tree(repo)
                  if f.get("type") == "file" and f["path"].endswith(".litertlm")]
            fit = [f for f in fs if f[1] <= budget]
            if fit:
                generic = [f for f in fit if not _LITERT_VARIANT.search(f[0])]
                path, size = max(generic or fit, key=lambda f: f[1])
                return {"repo": repo, "path": path, "size": size, "files": [path]}
        return None
    if fmt in ("mlx-safetensors", "safetensors"):
        repos = _model_repos(model)
        if fmt == "mlx-safetensors":  # the registry names the base repo: find its MLX conversions
            repos += mlx_repos(model)
        for repo in dict.fromkeys(repos):
            if ("mlx" in repo.lower()) != (fmt == "mlx-safetensors"):
                continue
            snap = _snapshot(repo)
            if snap and snap["size"] <= budget:
                return snap
        return None
    return None


# ---------------------------------------------------------------------------
# The HF class table (data/trending-quant-catalog.json) — the committed
# source of truth llgenie's pick logic resolves against. Generated by
# scripts/gen_trending_quant_catalog.py (make sync-quant-catalog), NOT llgenie
# runtime logic, no LLM calls. It lists, per trending model per engine, the archs
# that engine supports and every real quantized download plan with its resolvable
# https://huggingface.co/<repo>/resolve/<rev>/<file> link. llgenie never re-queries
# the live Hub to decide what a chosen engine can load on this hardware — it reads
# this table (the pick's comparison path is hermetic; the Hub is only touched when
# actually downloading). A model/engine not yet in the table falls back to live
# resolution (strata_plan / tensorfold_plan / gguf_weights & co.).
# ---------------------------------------------------------------------------
QUANT_CATALOG = REPO / "data" / "trending-quant-catalog.json"
_QUANT_CATALOG_CACHE: dict | None = None
_QUANT_CATALOG_HASH = ""


def quant_catalog_path() -> str | None:
    """The catalog file the pick reads: LLGENIE_QUANT_CATALOG (a path, or '' to
    disable the table and always resolve live), else the committed
    data/trending-quant-catalog.json."""
    v = os.environ.get("LLGENIE_QUANT_CATALOG", "")
    if v == "" or v == "0":
        return str(QUANT_CATALOG) if v == "" else None
    return v


def quant_catalog() -> dict:
    """The committed HF class table (cached across calls; reloaded when the file
    changes on disk). {} when it is missing or the env seam disables it (never a
    hard dependency)."""
    global _QUANT_CATALOG_CACHE, _QUANT_CATALOG_HASH
    src = quant_catalog_path()
    if src is None:
        _QUANT_CATALOG_CACHE, _QUANT_CATALOG_HASH = {}, ""
        return {}
    try:
        stamp = os.stat(src).st_mtime_ns
    except OSError:
        _QUANT_CATALOG_CACHE, _QUANT_CATALOG_HASH = {}, ""
        return {}
    if _QUANT_CATALOG_CACHE is None or stamp != _QUANT_CATALOG_HASH:
        try:
            _QUANT_CATALOG_CACHE = json.loads(Path(src).read_text())
        except (OSError, ValueError):
            _QUANT_CATALOG_CACHE = {}
        _QUANT_CATALOG_HASH = stamp
    return _QUANT_CATALOG_CACHE


def catalog_engine_cell(model_id: str, engine_name: str) -> dict | None:
    """The {arch, quants} table row for (model, engine), or None when not catalogued."""
    return (quant_catalog().get("files") or {}).get(model_id, {}).get(engine_name)


def catalog_supported_archs(model_id: str, engine_name: str) -> list[str]:
    """The archs the catalog says can run this engine for this model."""
    cell = catalog_engine_cell(model_id, engine_name)
    return (cell or {}).get("arch") or []


def catalog_supported_quants(model: dict, eng: dict) -> list[dict] | None:
    """The quantized download plans the committed table lists for `eng` on `model`,
    as real plan dicts ({repo, revision, path, files, size}), or None when that
    (model, engine) pair is not in the catalog (caller falls back to live). The
    catalog row's URL becomes plan_url()'s output — the pick never re-queries the
    Hub to learn what the engine can load."""
    cell = catalog_engine_cell(str(model.get("id") or ""), str(eng.get("engine") or eng.get("id") or ""))
    if cell is None:
        return None
    plans = []
    for it in (cell.get("quants") or []):
        plan = {"repo": it["repo"], "revision": it.get("revision", "main"),
                "path": it["path"], "files": it.get("files") or [it["path"]],
                "size": float(it.get("size_gb") or 0) * 2**30}
        if it.get("dir") and not it.get("path"):
            plan["path"] = ""
            plan["dir"] = True  # whole-repo snapshot (config.json + safetensors)
        plans.append(plan)
    return plans


def plan_url(plan: dict) -> list[str]:
    """The resolvable Hub URL of every planned file:
    `https://huggingface.co/<repo>/resolve/<revision>/<file>` (the pinned revision
    for Strata/TensorFold). The link a user can open / a downloader can fetch."""
    if not plan:
        return []
    rev = plan.get("revision", "main")
    return [f"{HF}/{plan['repo']}/resolve/{rev}/{f}" for f in (plan.get("files") or [])]


def _matrix_plan(model: dict, eng: dict, gb: float, ram_gb: float | None, arch: str) -> tuple[str | None, dict | None]:
    """The (use_format, plan) for one (model, engine) matrix cell — the HIGHEST quant
    of the model that `eng` supports and that fits the (vram, ram) budget
    (pick_quant). Own-checkpoint engines (Strata, TensorFold) get only their own plan.
    `use_format` is the format that plan resolves in."""
    own = {"strata": "gguf", "tensorfold": "mlx-safetensors"}
    plan = pick_quant(model, eng, gb, ram_gb, arch)
    if not plan:
        return None, None
    if eng["id"] in own:
        return own[eng["id"]], plan
    # derive the format from what the plan resolved to
    fmt = "gguf"
    if plan.get("files") and all(f.endswith(".litertlm") for f in plan["files"]):
        fmt = "litertlm"
    elif model_format_path_is_snapshot(plan):
        fmt = "mlx-safetensors" if any("mlx" in r.lower() for r in _model_repos(model)) else "safetensors"
    return fmt, plan


def model_format_path_is_snapshot(plan: dict) -> bool:
    """A whole-repo snapshot plan (config.json + safetensors, an MLX/safetensors repo)
    rather than a single file plan (gguf / litertlm)."""
    return bool(plan and plan.get("dir") and not plan.get("path"))


def engine_supported_quants(model: dict, eng: dict, gb: float, ram_gb: float | None = None,
                            arch: str | None = None) -> list[dict]:
    """The REAL range of quantized models `eng` supports for `model` on this host, in
    ascending size — the list the picker narrows to once the engine is chosen. Each
    entry is one real, resolvable download plan ({repo, revision, path, files, size})
    of a format the engine reads; own-checkpoint engines (Strata, TensorFold) return
    only their own files. Empty when the engine's format has nothing that exists within
    the budget. This is the business rule behind 'pick a model -> its supported engines
    -> the quants THAT engine supports -> take the highest that fits your spec'.

    Hermetic by default: the offered quants come from the committed HF class table
    (data/trending-quant-catalog.json), so deciding what a chosen engine can load never
    re-queries the live Hub. Only a (model, engine) not yet in the table falls back to
    live resolution, so a registry refreshed before its catalog still works."""
    arch = arch or host_arch()
    gb = card_gb() if gb is None else gb
    budget = weight_budget_gb(gb, is_moe(model), ram_gb, arch) * 2**30
    own = {"strata": "gguf", "tensorfold": "mlx-safetensors"}
    out: list[dict] = []

    def _add(plan):
        if plan and plan.get("size", 0) <= budget and not any(
                p["repo"] == plan["repo"] and p.get("path") == plan.get("path")
                and p.get("files") == plan.get("files") for p in out):
            out.append(plan)

    # First: the committed catalog row for this (model, engine) — the archs the engine
    # supports on this model AND every real quantitized plan it can load, budget-fit.
    catalog_plans = catalog_supported_quants(model, eng)
    if catalog_plans is not None:
        supported = catalog_supported_archs(str(model.get("id") or ""),
                                            str(eng.get("engine") or eng.get("id") or ""))
        # an engine whose table row does not list this arch is not runnable for the
        # model on this hardware: offer nothing (arch-driven engine support, #122)
        if supported and arch not in supported:
            return []
        for plan in catalog_plans:
            _add(plan)
        return sorted(out, key=lambda p: p["size"])

    # Fallback: live resolution for a model/engine the committed table does not cover.
    if eng["id"] in own:
        fmt = own[eng["id"]]
        plan = plan_download(model, gb, ram_gb, fmt, arch, engine=eng["id"])
        _add(plan)
        return sorted(out, key=lambda p: p["size"])

    for fmt in DOWNLOADABLE:
        if fmt not in (eng.get("formats") or []):
            continue
        if fmt == "gguf":
            repo = gguf_repo(model)
            if repo:
                for w in gguf_weights(repo):
                    if w["size"] <= budget:
                        _add({"repo": repo, "revision": "main", **w})
        elif fmt == "litertlm":
            for repo in _model_repos(model):
                for f in _tree(repo):
                    path = f.get("path", "")
                    if f.get("type") == "file" and path.endswith(".litertlm") \
                            and int(f.get("size") or 0) <= budget:
                        _add({"repo": repo, "revision": "main", "path": path,
                              "size": int(f.get("size") or 0), "files": [path]})
        elif fmt in ("mlx-safetensors", "safetensors"):
            repos = _model_repos(model)
            if fmt == "mlx-safetensors":
                repos += mlx_repos(model)
            for repo in dict.fromkeys(repos):
                if ("mlx" in repo.lower()) != (fmt == "mlx-safetensors"):
                    continue
                snap = _snapshot(repo)
                if snap and snap["size"] <= budget:
                    _add(snap)
    return sorted(out, key=lambda p: p["size"])


def pick_quant(model: dict, eng: dict, gb: float, ram_gb: float | None = None,
               arch: str | None = None) -> dict | None:
    """The HIGHEST quant of `model` that `eng` supports and that fits the (vram, ram)
    spec — the interactive pick's final step after the engine is chosen (unless the
    user names a specific file). The last (largest) element of engine_supported_quants,
    or None when the engine supports none within the budget."""
    qs = engine_supported_quants(model, eng, gb, ram_gb, arch)
    return qs[-1] if qs else None


def matrix(registry: dict, gb: float | None = None, ram_gb: float | None = None,
           arch: str | None = None) -> dict:
    """The exhaustive map an interactive `llgenie --matrix` pick proves: every
    README trend model that fits the VRAM `gb`, every engine that can run it on
    `arch`, and the exact quantized HF download it would use (the largest that
    fits `weight_budget_gb(gb, is_moe, ram_gb, arch)` — VRAM, + RAM for MoE).
    Returns {"permutations": [ {model, engines: [{engine, use_format, plan, url,
    size_gb}]} in README order / best-t/s engine order ], "skipped": [ {model,
    why} ] for models within VRAM that no engine here can run or whose smallest
    download still exceeds the budget. `url` holds a resolvable HF link per file;
    the full matrix is what the picker's choices reduce to."""
    arch = arch or host_arch()
    gb = card_gb() if gb is None else gb
    # the host's RAM is resolved the same way the card is: `matrix()` given no ram means
    # THIS host's ram, so the store's `system_ram_min` floor applies here exactly as it does
    # in `offer()` (issue #669/#414). Without it `llgenie --matrix` without `--ram` listed
    # models this host cannot run.
    ram_gb = (system_ram_gb() or 0.0) if ram_gb is None else ram_gb
    permutations, skipped = [], []
    for m in trend_list(registry, gb, ram_gb):
        engines = rank_engines(m, arch, gb=gb)
        if not engines:
            names = sorted({e["engine"] for e in m.get("engines") or []} | set(m.get("supported_engines") or []))
            skipped.append({"model": m["id"], "why": f"no {arch} engine image ({', '.join(names)})"})
            continue
        cells = []
        for eng in engines:
            fmt, plan = _matrix_plan(m, eng, gb, ram_gb, arch)
            if not plan:
                continue
            cells.append({"engine": eng, "use_format": fmt, "plan": plan,
                          "url": plan_url(plan), "size_gb": plan["size"] / 2**30})
        if cells:
            permutations.append({"model": m, "engines": cells})
        else:
            skipped.append({"model": m["id"],
                            "why": _no_fit_reason(m, list(DOWNLOADABLE), gb, arch, ram_gb)})
    return {"permutations": permutations, "skipped": skipped}


def _base_name(model: dict) -> str:
    return str(model.get("hf") or "").rsplit("/", 1)[-1]


def mlx_repos(model: dict) -> list[str]:
    """Hub repos named `<base>-MLX...` (the model's own org first, then by downloads):
    the MLX conversions of a model the registry lists only by its base repo
    (ornith-ai/Ornith-1.5-9B -> ornith-ai/Ornith-1.5-9B-MLX-4bit)."""
    name = _base_name(model)
    if not name:
        return []
    org = str(model.get("hf") or "").split("/", 1)[0].lower()
    try:
        hits = _hub_json(f"{HF}/api/models?search={urllib.parse.quote(name)}&filter=mlx"
                         f"&sort=downloads&direction=-1&limit=50")
    except Exception:  # noqa: BLE001  (Hub down: no conversions)
        return []
    want = (name + "-mlx").lower()
    ids = [h["id"] for h in hits if h["id"].split("/", 1)[-1].lower().startswith(want)]
    return sorted(ids, key=lambda i: i.split("/")[0].lower() != org)


TENSORFOLD_ORG = "TensorFold"


def tensorfold_repos(model: dict) -> list[str]:
    """TensorFold's own MLX checkpoints of `model` (TensorFold/<base>-MLX-<quant>[-MTP]):
    TensorFold serves only the families it ships kernels for, and publishes their
    checkpoints under its org (README "Supported models"; NVFP4/oQ are CUDA/other)."""
    name = _base_name(model)
    if not name:
        return []
    try:
        hits = _hub_json(f"{HF}/api/models?author={TENSORFOLD_ORG}&search={urllib.parse.quote(name)}&limit=100")
    except Exception:  # noqa: BLE001
        return []
    want = f"{TENSORFOLD_ORG}/{name}-MLX-".lower()
    return sorted(h["id"] for h in hits if h["id"].lower().startswith(want))


def tensorfold_plan(model: dict, budget_bytes: float) -> dict | None:
    """The largest TensorFold MLX checkpoint of `model` within the budget (whole repo)."""
    snaps = [s for s in (_snapshot(r) for r in tensorfold_repos(model)) if s]
    fit = [s for s in snaps if s["size"] <= budget_bytes]
    return max(fit, key=lambda s: (s["size"], s["repo"])) if fit else None


def tensorfold_smallest(model: dict) -> dict | None:
    snaps = [s for s in (_snapshot(r) for r in tensorfold_repos(model)) if s]
    return min(snaps, key=lambda s: s["size"]) if snaps else None


def tensorfold_local(model: dict, root: Path | None = None) -> Path | None:
    """A downloaded TensorFold checkpoint of `model` under the models root
    (~/models/TensorFold__<base>-MLX-*/ with config.json), largest first."""
    root = root or models_root()
    name = _base_name(model)
    if not name or not root.exists():
        return None
    pre = f"{TENSORFOLD_ORG}__{name}-MLX-".lower()
    hits = [p for p in root.iterdir() if p.is_dir() and p.name.lower().startswith(pre)
            and (p / "config.json").exists()]
    return max(hits, key=lambda p: sum(f.stat().st_size for f in p.glob("*.safetensors"))) if hits else None


def download_chunk(repo: str, filename: str, dest: Path, max_bytes: int, revision: str = "main") -> Path:
    """Fetch only the first `max_bytes` of a Hub file (HTTP Range) — CI's download test."""
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / Path(filename).name
    req = authorize(urllib.request.Request(
        f"{HF}/{repo}/resolve/{revision}/{filename}",
        headers={"Range": f"bytes=0-{max_bytes - 1}", "User-Agent": "llgenie"}))
    with hub_open(req, timeout=120) as r, open(out, "wb") as f:  # noqa: S310
        f.write(r.read(max_bytes))
    return out


def download(model: dict, gb: float | None = None, root: Path | None = None, fmt: str = "gguf",
             arch: str | None = None, ram_gb: float | None = None, engine: str | None = None,
             plan: dict | None = None) -> Path:
    """Download plan_download(model, fmt) into ~/models/<org>__<repo>/ through the
    existing hf path (every shard / every file of a repo snapshot); returns what the
    engine loads (the GGUF / .litertlm file, or the repo dir)."""
    gb = card_gb() if gb is None else gb
    root = root or models_root()
    plan = plan or plan_download(model, gb, ram_gb, fmt, arch, engine=engine)
    if not plan:
        raise SystemExit(f"[pick] {model['name']}: no {fmt} download fits "
                         f"{weight_budget_gb(gb, is_moe(model), None, arch or host_arch()):.1f} GB on this host")
    repo, dest = plan["repo"], root / plan["repo"].replace("/", "__")
    max_bytes = int(os.environ.get("LLGENIE_DOWNLOAD_MAX_BYTES") or 0)
    if max_bytes:  # CI seam: the first bytes of every planned file, never the whole download
        rev = plan.get("revision", "main")
        if plan["path"]:
            for f in plan["files"]:
                download_chunk(repo, f, dest / Path(f).parent, max_bytes, rev)
            return dest / plan["path"]
        return download_chunk(repo, plan["files"][0], dest, max_bytes, rev)
    env = dict(os.environ)
    venv_hf = Path(sys.executable).parent / "hf"  # the launcher runs the gguf venv, which ships hf
    if not env.get("HF_BIN") and venv_hf.exists():
        env["HF_BIN"] = str(venv_hf)
    rev = plan.get("revision", "main")
    if rev != "main":
        env["HF_REVISION"] = rev  # hf_download.py: `hf download --revision` (Strata's pinned files)
    sizes = {f["path"]: int(f.get("size") or 0) for f in _tree(repo, rev)}
    for i, filename in enumerate(plan["files"], 1):
        label = model["id"] + (f"-{i}of{len(plan['files'])}" if len(plan["files"]) > 1 else "")
        cmd = [sys.executable, str(REPO / "scripts" / "hf_download.py"), repo, filename,
               str(dest), label, "0", str(sizes.get(filename, 0))]
        try:
            rc = subprocess.run(cmd, env=env, timeout=DOWNLOAD_TIMEOUT).returncode
        except subprocess.TimeoutExpired:
            # A timeout is a FAILURE that names itself: never an empty success, and never
            # the 6-hour silence of a child nobody killed (issues #797, #872).
            raise SystemExit(
                f"[pick] download of {repo}/{filename} exceeded {DOWNLOAD_TIMEOUT:.0f}s "
                f"(LLGENIE_DOWNLOAD_TIMEOUT) and was killed: {' '.join(cmd)}") from None
        if rc:
            raise SystemExit(f"[pick] download of {repo}/{filename} failed (exit {rc})")
    return dest if plan.get("dir") else dest / plan["path"]


def choose(rows: list, label, prompt: str, wanted: str | None, auto: bool):
    """Pick from `rows` (best first): by substring `wanted`, the top one when
    auto/non-interactive, else ask."""
    if wanted:
        hit = [r for r in rows if wanted.lower() in label(r).lower()]
        if not hit:
            raise SystemExit(f"[pick] no {prompt} matches {wanted!r}; have: {', '.join(label(r) for r in rows)}")
        return hit[0]
    if auto or not sys.stdin.isatty():
        return rows[0]
    for i, r in enumerate(rows, 1):
        print(f"  {i:2d}. {label(r)}")
    while True:
        try:
            sel = input(f"Pick {prompt} [1]: ").strip() or "1"
        except EOFError:
            raise SystemExit("cancel") from None
        if sel.isdigit() and 1 <= int(sel) <= len(rows):
            return rows[int(sel) - 1]
        print(f"  enter 1-{len(rows)}")
