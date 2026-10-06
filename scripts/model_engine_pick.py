#!/usr/bin/env python3
"""Pick the model and the inference server for `llgenie` (issue #102 / OpenSpec
feat-model-engine-pick).

Data: the trending-local-llms registry (data/models.json): per model, measured
t/s per engine (`engines[].tps`) plus post engagement (likes/reshares/views).

  rank_engines(model)  engines that can run `model` ON THIS HOST (an image
                       variant for the host backend, cpu fallback), best first:
                       highest reported t/s, then trending engagement.
  rank_models()        registry models that fit the card (vram_tier <= card),
                       each with its best engine, best first by t/s.
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
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PARAMS = REPO / "containers" / "engines" / "params"
REGISTRY_URL = ("https://raw.githubusercontent.com/andyholst/trending-local-llms/"
                "master/data/models.json")
HF = "https://huggingface.co"
APPLE = re.compile(r"apple|\bM[1-9]\b|\bM[1-9] (pro|max|ultra)|mac", re.I)


def models_root() -> Path:
    return Path(os.environ.get("LLAMA_MODELS_ROOT") or Path.home() / "models")


def load_registry(src: str | None = None) -> dict:
    """LLGENIE_REGISTRY_SRC (file or URL) overrides the live registry."""
    src = src or os.environ.get("LLGENIE_REGISTRY_SRC") or REGISTRY_URL
    if src.startswith("http"):
        with urllib.request.urlopen(src, timeout=30) as r:  # noqa: S310
            return json.load(r)
    return json.loads(Path(src).read_text())


def engine_ids() -> dict[str, dict]:
    """Registry engine name -> {id, variants} from the generated params."""
    out = {}
    for pf in PARAMS.glob("*.json"):
        p = json.loads(pf.read_text())
        sys.path.insert(0, str(REPO / "scripts"))
        import engine_image as ei
        out[p["engine"]] = {"id": p["id"], "variants": [v for v in (p.get("variants") or {})
                                                       if not ei.disabled(p["id"], v)]}
    return out


def host_arch() -> str:
    try:
        sys.path.insert(0, str(REPO / "scripts"))
        import detect_server as d
        return {"cuda": "cuda", "rocm": "rocm", "vulkan": "vulkan"}.get(d.detect_all().get("backend"), "cpu")
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


def _engagement(e: dict) -> int:
    return int(e.get("likes") or 0) * 3 + int(e.get("reshares") or 0) * 5 + int(e.get("views") or 0) // 100


def rank_engines(model: dict, arch: str | None = None, ids: dict | None = None) -> list[dict]:
    """Engines that can run `model` here, best first: max t/s, then engagement."""
    arch = arch or host_arch()
    ids = ids if ids is not None else engine_ids()
    best: dict[str, dict] = {}
    for e in model.get("engines") or []:
        if APPLE.search(e.get("hardware") or ""):
            continue  # Apple-Silicon t/s does not describe a container (Linux/PC) host
        info = ids.get(e["engine"])
        if not info:
            continue  # no container image (Metal-only / browser-only engines)
        variant = arch if arch in info["variants"] else ("cpu" if "cpu" in info["variants"] else None)
        if not variant:
            continue
        row = {"engine": e["engine"], "id": info["id"], "variant": variant,
               "tps": _num(e.get("tps")), "engagement": _engagement(e),
               "hardware": e.get("hardware", "")}
        cur = best.get(info["id"])
        if not cur or (row["tps"], row["engagement"]) > (cur["tps"], cur["engagement"]):
            best[info["id"]] = row
    return sorted(best.values(), key=lambda r: (-r["tps"], -r["engagement"], r["id"]))


def fits(model: dict, gb: float) -> bool:
    return gb <= 0 or _num(model.get("vram_tier")) <= gb


def rank_models(registry: dict, arch: str | None = None, gb: float | None = None) -> list[dict]:
    """Models that fit the card AND have a runnable engine here, best t/s first."""
    gb = card_gb() if gb is None else gb
    ids = engine_ids()
    rows = []
    for m in registry.get("models") or []:
        engines = rank_engines(m, arch, ids)
        if engines and fits(m, gb):
            rows.append({"model": m, "engines": engines, "tps": engines[0]["tps"]})
    return sorted(rows, key=lambda r: (-r["tps"], -r["engines"][0]["engagement"], r["model"]["id"]))


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
        if all(t in name for t in want) and (p.suffix == ".gguf" or (p.is_dir() and (p / "config.json").exists())):
            hits.append(p)
    return max(hits, key=lambda p: p.stat().st_size if p.is_file() else 0) if hits else None


def repo_for(model: dict) -> str:
    fmts = model.get("formats") or []
    gguf = next((f["hf"] for f in fmts if "gguf" in (f.get("name", "") + f.get("hf", "")).lower()), None)
    return gguf or (fmts[0]["hf"] if fmts else model["hf"])


def pick_file(repo: str, gb: float) -> tuple[str, int] | None:
    """Largest .gguf in `repo` that leaves ~15% of the card free (smallest if none fit)."""
    with urllib.request.urlopen(f"{HF}/api/models/{repo}/tree/main?recursive=true", timeout=30) as r:  # noqa: S310
        files = [(f["path"], int(f.get("size") or 0)) for f in json.load(r)
                 if f.get("type") == "file" and f["path"].endswith(".gguf") and "mmproj" not in f["path"]]
    if not files:
        return None
    budget = gb * 0.85 * 2**30 if gb > 0 else float("inf")
    ok = [f for f in files if f[1] <= budget]
    return max(ok, key=lambda f: f[1]) if ok else min(files, key=lambda f: f[1])


def download_chunk(repo: str, filename: str, dest: Path, max_bytes: int) -> Path:
    """Fetch only the first `max_bytes` of a Hub file (HTTP Range) — CI's download test."""
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / Path(filename).name
    req = urllib.request.Request(f"{HF}/{repo}/resolve/main/{filename}",
                                 headers={"Range": f"bytes=0-{max_bytes - 1}", "User-Agent": "llgenie"})
    if os.environ.get("HF_TOKEN"):
        req.add_header("Authorization", f"Bearer {os.environ['HF_TOKEN']}")
    with urllib.request.urlopen(req, timeout=120) as r, open(out, "wb") as f:  # noqa: S310
        f.write(r.read(max_bytes))
    return out


def download(model: dict, gb: float | None = None, root: Path | None = None) -> Path:
    """Download the model into ~/models/<repo> through the existing hf path."""
    gb = card_gb() if gb is None else gb
    root = root or models_root()
    repo = repo_for(model)
    dest = root / repo.replace("/", "__")
    chosen = pick_file(repo, gb)
    if not chosen:
        raise SystemExit(f"[pick] {repo}: no .gguf file on the Hub")
    filename, size = chosen
    max_bytes = int(os.environ.get("LLGENIE_DOWNLOAD_MAX_BYTES") or 0)
    if max_bytes:
        return download_chunk(repo, filename, dest, max_bytes)
    rc = subprocess.run([sys.executable, str(REPO / "scripts" / "hf_download.py"),
                         repo, filename, str(dest), model["id"], "0", str(size)]).returncode
    if rc:
        raise SystemExit(f"[pick] download of {repo}/{filename} failed (exit {rc})")
    return dest / filename


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
    sel = input(f"Pick {prompt} [1]: ").strip() or "1"
    return rows[int(sel) - 1]
