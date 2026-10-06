#!/usr/bin/env python3
"""
llama_serve.py - GGUF model launcher + auto-tuner for llama.cpp llama-server (Metal).

Serves an OpenAI-compatible endpoint via llama.cpp's llama-server. GGUF metadata
is read by the `gguf` package from the 3.10 venv set up by ~/llama-gguf-tools
(make venv-install). Run with that venv's python:

    ~/llama-gguf-tools/.venv/bin/python ~/scripts/llama_serve.py --list

- Scans ~/models/**/*.gguf
- Lets you pick a model from a numbered list (or pass substring/alias as argv)
- Auto-tunes llama-server flags to fit the card's memory:
    * KV cache sized to target context (q4_0 K+V). Flash attention and -ngl
      only on a GPU backend; -ngl is every layer when the weights fit, else
      the fraction that fits. Batch size follows the card.
    * context = min(the selected GGUF's context_length, KV tokens that fit the card)
    * -np slots: 2 for small models / 1 for big, pinned to 1 when MTP is engaged
    * MTP (multi-token-prediction): engage when the GGUF has nextn layers, with
      --spec-draft-n-max derived from the card's VRAM (<=16GB->1, <=24GB->2,
      >24GB->3) and --spec-draft-p-min only when set via LLAMA_SPEC_DRAFT_P_MIN
- Writes the exact command to <dest>/.run.log and launches llama-server

Usage:
    python3 ~/scripts/llama_serve.py            # interactive picker
    python3 ~/scripts/llama_serve.py --list     # list models, no run
    python3 ~/scripts/llama_serve.py <name>     # run by substring of filename
"""
import argparse
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error
import urllib.parse

# ---------------------------------------------------------------------------
# Interpreter bootstrap: the `gguf`/`numpy` deps live in the 3.10 venv built by
# `make install` (~/llama-gguf-tools/.venv). This file is symlinked into ~/bin
# as `llgenie.py` and its shebang (#!/usr/bin/env python3) often resolves to the
# SYSTEM python, which lacks gguf -> "No module named 'gguf'". If the imports
# below are missing in the current interpreter, re-exec this same file with the
# venv python so it works however it is launched (directly or via `llgenie`).
# ---------------------------------------------------------------------------
try:
    import gguf  # noqa: F401
    import numpy  # noqa: F401
except ImportError:
    _venv_py = os.path.expanduser("~/llama-gguf-tools/.venv/bin/python")
    if os.path.isfile(_venv_py):
        if sys.executable != _venv_py:
            args = [_venv_py, __file__] + sys.argv[1:]
            os.execv(_venv_py, args)  # replaces this process in place
    print(
        "[ERROR] gguf/numpy not importable in current python and the gguf venv was not "
        "found.\n"
        "        Install it first:  cd ~/repository/git/llama-ai && make install\n"
        "        Then run:          ~/llama-gguf-tools/.venv/bin/python ~/scripts/llama_serve.py\n"
        "        (or use the 'llgenie' launcher on your PATH)",
        file=sys.stderr,
    )
    raise SystemExit(1)
from gguf import GGUFReader
import numpy as np

# scripts/detect_server provides the canonical, GPU-VRAM-aware "card RAM"
# (VRAM when an NVIDIA card is present, else system RAM) plus its env seam.
# Tried two ways so it works both when the launcher runs the file directly
# (scripts/ is on sys.path) and when tests import it as the `scripts` package.
try:
    import detect_server  # noqa: F401  (module import, scripts/ on sys.path)
except ImportError:  # type: ignore[unreachable]
    from . import detect_server  # noqa: F401  (imported as scripts.detect_server)

HOME = os.path.expanduser("~")
# MODELS_ROOT overridable for hermetic tests (and for custom model dirs).
# Falls back to ~/models so local host behaviour is unchanged.
MODELS_ROOT = os.environ.get("LLAMA_MODELS_ROOT") or os.path.join(HOME, "models")
TOTAL_RAM_BYTES = 48 * 1024 * 1024 * 1024  # M5 Pro unified 48 GB
OS_OVERHEAD = 3 * 1024 * 1024 * 1024       # keep headroom for macOS/Metal
KV_QUANT = "q4_0"                           # K and V cache quant type
# ---------------------------------------------------------------------------
# Top-tier trending download (`--download-top-tier`)
# ---------------------------------------------------------------------------
# Flagship / large popular families considered "top tier". A trending GGUF whose
# repo id matches any of these (case-insensitive substring) is eligible; toy/
# tiny quantizations are then excluded by MIN_TOP_TIER_GB.
TOP_TIER_FAMILIES = (
    "qwen3", "qwen", "deepseek", "mistral", "llama-3", "llama3",
    "gemma", "gpt-oss", "phi-4", "phi-3", "qwq", "glm", "olmo",
    # additional trending LLM families observed in the live gguf trending query but
    # wrongly dropped (they're real LLMs, not TTS/image/audio):
    "ornith",          # ornith-ai/Ornith-1.5-{9B,35B-A3B}-GGUF (3.5M downloads, trend ~40)
    "qwopus",          # Jackrong/Qwopus3.8-27B-Flash-GGUF (trend ~121)
    "qwythos",         # empero-ai/Qwythos-9B (trend ~39)
    "tiel-coder",      # peculiar-ragdoll/Tiel-Coder-35B-A3B-GGUF (trend ~87)
    "minimax",         # unsloth/MiniMax-H3-GGUF (trend ~27)
    "k2-", "mova",     # IFM/K2-Horizon-MoVA-36B-A4B-GGUF (trend ~74)
)
MIN_TOP_TIER_GB = 4.0          # below this the quant file is treated as a toy/small
# Growing tier ladder for the `TierGB` placement folder. Extends DOWN to 1/2/4 GB so
# tiny CPU cards and small models get truthful folders too, and UP past 48 GB so big
# cards (256/512 GB+) get truthful tiers instead of everything-capped-at-48GB.
# Availability is bounded by the detected/overridden card in pick_tier_folder().
TIER_LADDER_GB = (1, 2, 4, 8, 16, 24, 48, 96, 128, 192, 256, 384, 512, 768, 1024, 1536, 2048, 3072)
HF_API = "https://huggingface.co/api/models"
HF_UA = "llgenie/1.0 (top-tier-download)"
# Transient HF API failures that _hf_get retries with backoff. 429 = rate-limited,
# 500/502/503/504 = server-side blips, and a plain URLError (DNS/reset/timeout) is
# also transient. Permanent errors (401/403/404, etc.) are NOT retried — they fail
# fast with a clear reason. Env-overridable so hermetic tests can drive it without
# sleeping (see test_hf_get_retries_transient_and_fails_permanent).
HF_TRANSIENT_HTTP = (429, 500, 502, 503, 504)
HF_GET_MAX_ATTEMPTS = int(os.environ.get("HF_GET_MAX_ATTEMPTS", "4"))   # total tries
HF_GET_BASE_PAUSE = float(os.environ.get("HF_GET_BASE_PAUSE", "1.0"))  # seconds, exponential
LLAMA_RAM_ENV = "LLAMA_RAM_BYTES"
LLAMA_HEADROOM_ENV = "LLAMA_HEADROOM_BYTES"
LLAMA_HEADROOM_MAX_FRAC = 0.45   # max OS reserve as a fraction of total RAM
LLAMA_SPEC_DRAFT_P_MIN_ENV = "LLAMA_SPEC_DRAFT_P_MIN"  # optional MTP confidence gate (rule 2)

# Card-VRAM -> --spec-draft-n-max (MTP depth), grounded in the qwen38-mtp
# community rules (https://github.com/sudoingX/qwen38-mtp): the depth sweet
# spot depends on the card and its bandwidth. Small/bandwidth-starved cards
# favour shallow drafts (depth 1 never hurts and pays at every context depth);
# 24 GB-class cards generally hold depth 2; big (>24 GB, e.g. 32/48/64 GB)
# cards can run depth 3 where the extra draft tokens amortise. This is a
# deterministic card-class heuristic — it re-derives the knob per card at serve
# time rather than hard-coding it — and is the value the spec calls for.
#
# Bins are (max_gb_inclusive, n_max) checked in order (first match wins).
MTP_DEPTH_BINS = (
    (16, 1),   # 8/12/16 GB: shallow — depth 1 pays everywhere, no starved depth-2 risk
    (24, 2),   # 24 GB (inclusive boundary, matches PRISM_THRESHOLD_GB)
    (999, 3),  # >24 GB: 32/48/64/128/... — depth 3
)
# sampling defaults from user's usual invocation (fallback preset when a model
# supplies no author-recommended defaults). Kept as the fallback default.
SAMPLING = ["--temp", "0.6", "--top-p", "0.9", "--top-k", "40", "--min-p", "0.05",
            "--repeat-penalty", "1.05"]
# Prism low-bit packings (Ternary Bonsai 2). Stock llama.cpp cannot run them.
# When the GGUF has no author sampling block, use the Bonsai server defaults.
PRISM_LOWBIT_QUANTS = ("PTQ1_0", "PQ2_0", "TQ1_0", "TQ2_0")
PRISM_SAMPLING = ["--temp", "0.5", "--top-p", "0.85", "--top-k", "20", "--min-p", "0"]


def prism_quant_name(meta):
    """PTQ1_0 / PQ2_0 / TQ1_0 / TQ2_0 from the file name or an explicit quant field."""
    blob = " ".join([
        str(meta.get("file") or ""),
        str(meta.get("name") or ""),
        str(meta.get("quant") or ""),
    ]).upper()
    for name in PRISM_LOWBIT_QUANTS:
        if name in blob:
            return name
    return ""
# Map short sampling dict keys to llama-server flags (see build_command).
SAMPLING_FLAG_MAP = {
    "temperature": "--temp",
    "top_p": "--top-p",
    "top_k": "--top-k",
    "min_p": "--min-p",
    "repeat_penalty": "--repeat-penalty",
}
# Short name -> GGUF metadata key for author-recommended sampling defaults.
SAMPLING_KEYS = {
    "temperature": "general.sampling.temperature",
    "top_p": "general.sampling.top_p",
    "top_k": "general.sampling.top_k",
    "min_p": "general.sampling.min_p",
    "repeat_penalty": "general.sampling.repeat_penalty",
}


def _extract_sampling_from_kv(kv):
    """Author-recommended sampling defaults from a parsed header kv dict."""
    out = {}
    for short, full in SAMPLING_KEYS.items():
        if full in kv:
            s = str(kv[full]).strip()
            if s != "":
                out[short] = s
    return out


def _extract_sampling_from_fields(fields):
    """Author-recommended sampling defaults from a GGUFReader fields mapping."""
    out = {}
    for short, full in SAMPLING_KEYS.items():
        if full in fields:
            s = str(_gget(fields[full])).strip()
            if s != "":
                out[short] = s
    return out

from gguf import GGUFReader
import numpy as np


# ----------------------------------------------------------------------------
# GGUF metadata reader — uses the `gguf` package from the 3.10 venv
# (~/llama-gguf-tools/.venv, see `make venv-install`). No stdlib fallback.
# ----------------------------------------------------------------------------
def _gget(f):
    """Return the scalar/string value of a GGUFReader field."""
    raw = f.parts[f.data[0]]  # uniform: data[0] indexes the value part
    a = np.asarray(raw)
    if a.dtype == np.uint8 and a.ndim == 1:
        try:
            return bytes(a).decode("utf-8", "replace")
        except Exception:
            return a
    flat = a.reshape(-1)
    items = [x.item() for x in flat]
    return items[0] if len(items) == 1 else items


def read_model_meta_fast(path):
    """Read ONLY the GGUF metadata header (no full-file mmap).

    Returns the same dict as read_model_meta but ~1000x faster for large
    models (reads the header K/V section rather than mapping all weights).
    Returns None if the header can't be decoded (caller falls back).
    """
    import struct
    try:
        with open(path, "rb") as fh:
            if fh.read(4) != b"GGUF":
                return None
            fh.read(4)  # version
            fh.read(8)  # tensor_count
            kv_count = struct.unpack("<Q", fh.read(8))[0]
            kv = {}

            def rkey():
                n = struct.unpack("<Q", fh.read(8))[0]
                return fh.read(n).decode("utf-8", "replace")

            for _ in range(kv_count):
                k = rkey()
                vt = struct.unpack("<I", fh.read(4))[0]
                if vt == 8:  # string
                    n = struct.unpack("<Q", fh.read(8))[0]
                    kv[k] = fh.read(n).decode("utf-8", "replace")
                elif vt == 9:  # array
                    evt = struct.unpack("<I", fh.read(4))[0]
                    n = struct.unpack("<Q", fh.read(8))[0]
                    if evt == 8:  # array of length-prefixed strings (e.g. tokenizer vocab)
                        for _ in range(n):
                            slen = struct.unpack("<Q", fh.read(8))[0]
                            fh.read(slen)
                    else:
                        fmts = {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i",
                                6: "f", 7: "?", 10: "Q", 11: "q", 12: "d"}
                        if evt in fmts:
                            sz = struct.calcsize("<" + fmts[evt])
                            fh.read(sz * n)
                else:
                    fmts = {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i",
                            6: "f", 7: "?", 10: "Q", 11: "q", 12: "d"}
                    if vt in fmts:
                        kv[k] = struct.unpack("<" + fmts[vt],
                                              fh.read(struct.calcsize("<" + fmts[vt])))[0]
    except Exception:
        return None

    arch = str(kv.get("general.architecture", "").lower())
    if not arch:
        return None
    name = str(kv.get("general.name", os.path.basename(path)))
    n_head = int(kv.get(f"{arch}.attention.head_count", 0) or 0)
    n_head_kv = int(kv.get(f"{arch}.attention.head_count_kv", 0) or 0)
    if n_head_kv <= 0:
        n_head_kv = n_head
    return {
        "file": path, "name": name, "arch": arch,
        "n_layer": int(kv.get(f"{arch}.block_count", 0) or 0),
        "n_embd": int(kv.get(f"{arch}.embedding_length", 0) or 0),
        "n_head": n_head,
        "n_head_kv": n_head_kv,
        "ctx_train": int(kv.get(f"{arch}.context_length", 0) or 0),
        "key_length": int(kv.get(f"{arch}.attention.key_length", 0) or 0),
        "value_length": int(kv.get(f"{arch}.attention.value_length", 0) or 0),
        "full_attention_interval": int(kv.get(f"{arch}.full_attention_interval", 0) or 0),
        "nextn_layers": int(kv.get(f"{arch}.nextn_predict_layers", 0) or 0),
        "chat_template": str(kv.get("tokenizer.chat_template", "") or ""),
        "sampling": _extract_sampling_from_kv(kv),
        "size_gb": os.path.getsize(path) / (1024 ** 3),
    }


def read_model_meta(path):
    """Return dict of arch facts for a GGUF. Tolerant of missing fields."""
    r = GGUFReader(path)
    f = r.fields
    arch = str(_gget(f["general.architecture"])).lower()
    name = str(_gget(f.get("general.name"))) if "general.name" in f else os.path.basename(path)
    n_head = 0
    n_head_kv = 0
    for hk in ("attention.head_count", "attention.head_count_kv"):
        key = f"{arch}.{hk}"
        if key in f:
            v = _gget(f[key])
            v = int(v) if v != "" else 0
            if hk == "attention.head_count":
                n_head = v
            else:
                n_head_kv = v
    if n_head_kv <= 0:
        n_head_kv = n_head
    return {
        "file": path, "name": name, "arch": arch,
        "n_layer": int(_gget(f.get(f"{arch}.block_count", "0")) or 0),
        "n_embd": int(_gget(f.get(f"{arch}.embedding_length", "0")) or 0),
        "n_head": n_head,
        "n_head_kv": n_head_kv,
        "ctx_train": int(_gget(f.get(f"{arch}.context_length", "0")) or 0),
        "key_length": int(_gget(f.get(f"{arch}.attention.key_length", "0")) or 0),
        "value_length": int(_gget(f.get(f"{arch}.attention.value_length", "0")) or 0),
        "full_attention_interval": int(_gget(f.get(f"{arch}.full_attention_interval", "0")) or 0),
        "nextn_layers": int(_gget(f.get(f"{arch}.nextn_predict_layers", "0")) or 0),
        "chat_template": str(_gget(f.get("tokenizer.chat_template", "0")) or ""),
        "sampling": _extract_sampling_from_fields(f),
        "size_gb": os.path.getsize(path) / (1024 ** 3),
    }


def is_reasoning_model(meta):
    """Detect a reasoning/thinking-capable model from its chat template.

    A template that routes user prompts through a hidden chain-of-thought block
    (e.g. DeepSeek/Ornith <|start_of_fim|>-style fim or 'cot' / 'reasoning'
    tokens) is treated as a reasoning model. Non-reasoning chat templates return
    False.
    """
    tpl = (meta.get("chat_template") or "").lower()
    reasoning_markers = (
        "fim", "reasoning", "cot", "chain-of-thought", "think",
        "<|start_of_fim|>", "r1", "slash_thinking",
    )
    return any(m in tpl for m in reasoning_markers)


# ----------------------------------------------------------------------------
# Scan + pick
# ----------------------------------------------------------------------------
def models_root():
    """Directory scanned for GGUFs. LLAMA_MODELS_ROOT overrides it per run."""
    return os.environ.get("LLAMA_MODELS_ROOT") or MODELS_ROOT


def scan_models():
    out = []
    for root, _, files in os.walk(models_root()):
        for fn in files:
            if fn.endswith(".gguf") and not fn.endswith(".incomplete"):
                p = os.path.join(root, fn)
                try:
                    # fast path: read only GGUF header (no 27GB mmap)
                    meta = read_model_meta_fast(p)
                    if meta is None:
                        # a file whose header is not GGUF is not a model (a test stub, a
                        # partial download); skip it quietly instead of raising on it
                        with open(p, "rb") as fh:
                            if fh.read(4) != b"GGUF":
                                continue
                        meta = read_model_meta(p)  # fallback to full reader
                    out.append(meta)
                except Exception as e:
                    print(f"  (skip {fn}: {e})")
    out.sort(key=lambda m: -m["size_gb"])
    return out


# ----------------------------------------------------------------------------
# Auto-tuning
# ----------------------------------------------------------------------------
# Floor for the KV budget when the weights already fill the card. 512 MiB still
# yields a small but usable context instead of a zero or negative window.
MIN_KV_BUDGET = 512 * 1024 * 1024


def _kv_cache_layers(meta):
    """Layers that store a per-token KV cache.

    Hybrid models (Qwen3.5 / Ternary Bonsai) set ``full_attention_interval``:
    only every Nth language layer is full attention. Linear/SSM layers keep a
    fixed state and do not grow with context. The MTP ``nextn`` block is a
    full attention layer and is counted when present. Dense models (no
    interval) count every block.
    """
    n_layer = int(meta.get("n_layer") or 0)
    nextn = max(0, int(meta.get("nextn_layers") or 0))
    interval = int(meta.get("full_attention_interval") or 0)
    if interval > 1 and n_layer > 0:
        language = max(0, n_layer - nextn)
        full = language // interval
        return max(1, full + nextn)
    return max(1, n_layer)


def _head_dim_pair(meta):
    """(key_dim, value_dim) from GGUF, else n_embd // n_head."""
    key = int(meta.get("key_length") or 0)
    val = int(meta.get("value_length") or 0)
    if key <= 0:
        n_embd = int(meta.get("n_embd") or 0)
        n_head = int(meta.get("n_head") or 0)
        key = (n_embd // n_head) if n_head else 128
    if val <= 0:
        val = key
    return key, val


def kv_bytes_per_token(meta, quant=KV_QUANT):
    """Approx K+V cache bytes/token for the layers that actually grow with context."""
    key_len, val_len = _head_dim_pair(meta)
    n_kv = int(meta.get("n_head_kv") or 0) or int(meta.get("n_head") or 0) or 1
    layers = _kv_cache_layers(meta)
    # fp16 is 2 bytes per element; K and V are separate.
    f16_bytes = 2.0 * layers * n_kv * (key_len + val_len)
    # q4_0 KV is ~0.5 byte per element vs 2 for fp16 => ~4x smaller
    if quant in ("q4_0", "q4_1", "q5_0", "q5_1"):
        return f16_bytes / 4.0
    return f16_bytes


def tuned_context(meta, target_bytes):
    """Context that fits in `target_bytes` of KV, capped by the model's train ctx.

    The ceiling is the selected GGUF's ``context_length``. A missing field
    falls back to 32768. The result is never above that ceiling, is rounded
    down to a multiple of 1024, and is never below 2048.
    """
    if meta.get("ctx_train"):
        hard = int(meta["ctx_train"])
    else:
        hard = 32768
    per_tok = kv_bytes_per_token(meta)
    if per_tok > 0:
        by_budget = int(target_bytes / per_tok)
    else:
        by_budget = hard
    ctx = min(hard, by_budget)
    ctx = max(2048, (ctx // 1024) * 1024)
    return ctx


def gpu_offload_layers(meta, ctx, card_bytes, backend):
    """Layers to place on the GPU, or None when the backend has no GPU.

    cuda and metal get 99 when the weights and the q4_0 KV cache for `ctx`
    fit in the card after the 3 GB reserve (every layer). Otherwise they get
    the fraction of `n_layer` those leftover bytes can hold. cpu omits `-ngl`.
    """
    if backend not in ("cuda", "metal"):
        return None
    n_layer = int(meta.get("n_layer") or 0)
    weights = int(float(meta.get("size_gb") or 0) * (1024 ** 3))
    kv = int(kv_bytes_per_token(meta) * int(ctx))
    room = int(card_bytes) - OS_OVERHEAD - kv
    if n_layer <= 0 or weights <= 0 or room >= weights:
        return 99
    return max(0, min(n_layer, int(n_layer * room / weights)))


def batch_for_card(card_bytes):
    """(batch, ubatch) sized to the card. Larger cards take a bigger batch."""
    gb = int(card_bytes) / (1024 ** 3)
    if gb <= 8:
        return 512, 256
    if gb <= 24:
        return 2048, 512
    return 4096, 1024


def context_kv_budget_bytes(meta, card_bytes):
    """Bytes left for the KV cache on `card_bytes` after weights and OS reserve."""
    weights = int(float(meta.get("size_gb") or 0) * (1024 ** 3))
    budget = int(card_bytes) - OS_OVERHEAD - weights
    if budget < MIN_KV_BUDGET:
        return MIN_KV_BUDGET
    return budget


def serve_context(meta, card_bytes):
    """`-c` for this model on this card: min(trained context, what the KV cache fits)."""
    return tuned_context(meta, context_kv_budget_bytes(meta, card_bytes))


def mtp_depth_for_card(card_bytes, env=None):
    """Card-VRAM -> --spec-draft-n-max (MTP depth).

    Deterministic card-class heuristic (first matching bin wins). `card_bytes`
    is the card's real RAM in bytes (GPU VRAM when an NVIDIA card is present,
    else system RAM — i.e. `read_total_ram_bytes()`) or any positive byte count.
    The env (opt-in `LLAMA_SPEC_DRAFT_P_MIN` knob) is NOT used here: the depth
    is purely a function of the card. Returns an int >= 1.
    """
    if card_bytes is None:
        card_bytes = read_total_ram_bytes()
    card_gb = card_bytes / (1024 ** 3)
    for max_gb, n_max in MTP_DEPTH_BINS:
        if card_gb <= max_gb:
            return int(n_max)
    return int(MTP_DEPTH_BINS[-1][1])


def mtp_spec_flags(meta, card_bytes, env=None):
    """MTP flags for `meta` on a card of `card_bytes` bytes.

    Returns a list of argv elements (flag, value) or [] when the model has no
    MTP head. Engaged iff `meta["nextn_layers"] > 0` (the GGUF carries draft
    layers, e.g. Qwen3.8-27B MTP / Ternary-Bonsai MTP). Depth is derived from
    the card (`mtp_depth_for_card`). The optional `LLAMA_SPEC_DRAFT_P_MIN`
    gate is emitted only when set (rule 2: helps starved cards, hurts fast ones —
    a knob, never a default). `env` is the env dict (os.environ by default).
    """
    if not meta.get("nextn_layers", 0):
        return []
    env = env or os.environ
    out = ["--spec-type", "draft-mtp",
           "--spec-draft-n-max", str(mtp_depth_for_card(card_bytes, env))]
    pmin_env = (env.get(LLAMA_SPEC_DRAFT_P_MIN_ENV) or "").strip()
    if pmin_env:
        out += ["--spec-draft-p-min", pmin_env]
    return out


# ---------------------------------------------------------------------------
# Dynamic memory detection (from the actual GPU/CPU card)
# ---------------------------------------------------------------------------
def read_total_ram_bytes():
    """Read TOTAL physical/unified memory from the real card (not hardcoded).

    Resolution order:
      1. $LLAMA_RAM_BYTES env override (explicit, e.g. for CI/container)
      2. macOS `sysctl -n hw.memsize`
      3. Linux /proc/meminfo MemTotal
      4. fallback: TOTAL_RAM_BYTES (48 GB) with a warning
    """
    env = (os.environ.get(LLAMA_RAM_ENV) or "").strip()
    if env.isdigit() and int(env) > 0:
        return int(env)
    if sys.platform == "darwin":
        try:
            out = subprocess.run(["sysctl", "-n", "hw.memsize"],
                                 capture_output=True, text=True, timeout=5).stdout.strip()
            if out.isdigit() and int(out) > 0:
                return int(out)
        except Exception:
            pass
    else:
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        return kb * 1024
        except Exception:
            pass
    print(f"[warn] could not detect total RAM; using {TOTAL_RAM_BYTES//(1024**3)} GB (set "
          f"{LLAMA_RAM_ENV} to override).", file=sys.stderr)
    return TOTAL_RAM_BYTES


def read_current_headroom_bytes(total_bytes=None):
    """Current-pressure OS/safety reserve for the fit gate.

    We must leave room for the OS + app runtime (on macOS unified memory this is
    the wired/unswappable portion plus a safety margin). Wired memory is measured
    from `vm_stat`, but it fluctuates heavily moment to moment, so a stable,
    meaningful reserve is `max(current_wired + 1GB, HEADROOM_MIN)` CAPPED at
    `LLAMA_HEADROOM_MAX_FRAC` of total (default 45%). HEADROOM_MIN (default
    OS_OVERHEAD = 3 GB) ensures a card never gets an absurdly tiny reserve just
    because wired is momentarily low, while the cap prevents over-reserving a big
    card. `$LLAMA_HEADROOM_BYTES` overrides for CI/containers.
    """
    env = (os.environ.get(LLAMA_HEADROOM_ENV) or "").strip()
    if env.isdigit() and int(env) > 0:
        return int(env)
    total = total_bytes or TOTAL_RAM_BYTES
    cap = int(total * LLAMA_HEADROOM_MAX_FRAC) if total else OS_OVERHEAD
    measured = None
    if sys.platform == "darwin":
        try:
            out = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=5).stdout
            wired = None
            page_size = None
            for line in out.splitlines():
                line = line.strip()
                if line.startswith("Pages wired down:"):
                    wired = int(line.split(":")[1].strip().rstrip("."))
                if "page size of" in line and "(" in line:
                    page_size = int(line.split("page size of")[1].split()[0])
            if wired is not None and page_size:
                measured = wired * page_size + (1024 * 1024 * 1024)  # wired + 1 GB safety
        except Exception:
            pass
    if measured is None:
        measured = OS_OVERHEAD
    # floor + cap so the reserve is stable yet bounded by the real card.
    return min(max(measured, OS_OVERHEAD), cap)


# ---------------------------------------------------------------------------
# llama-server resolution
# ---------------------------------------------------------------------------
def server_name() -> str:
    """The make-install shim for this card's llama.cpp tree (issue #98):
    `prism-server` (Prism image) on cards <= 24 GB, `llama-server` (stock
    llama.cpp image) above; LLAMA_SERVER_TREE forces the tree."""
    try:
        tree = detect_server.detect_all().get("tree", "upstream")
    except Exception:  # noqa: BLE001
        tree = "upstream"
    return "prism-server" if tree == "prism" else "llama-server"


def resolve_llama_server():
    """Locate the llama-server binary.

    Resolution order:
      1. $LLAMA_SERVER env var (explicit override; must be an executable file)
      2. the tree's shim name (`prism-server` or `llama-server`) on PATH,
         then ~/bin/<name> (make install writes it; covers non-interactive
         shells where ~/bin is not on PATH)
      3. `llama-server` on PATH / ~/bin (a native build, or the stock shim when
         only that one is installed)

    If none yields a usable binary, raise SystemExit with a clear, actionable
    error so the launcher terminates instead of silently failing.
    """
    env = (os.environ.get("LLAMA_SERVER") or "").strip()
    if env:
        if os.path.isfile(env) and os.access(env, os.X_OK):
            return env
        raise SystemExit(
            f"[ERROR] LLAMA_SERVER='{env}' is not an executable llama-server.\n"
            "        Fix LLAMA_SERVER, or make 'llama-server' available on your PATH."
        )
    names = list(dict.fromkeys([server_name(), "llama-server"]))
    for name in names:
        found = shutil.which(name)
        if found:
            return found
        home_bin = os.path.join(os.path.expanduser("~"), "bin", name)
        if os.path.isfile(home_bin) and os.access(home_bin, os.X_OK):
            return home_bin
    raise SystemExit(
        f"[ERROR] llama-server binary not found ({' / '.join(names)} on PATH or in ~/bin).\n"
        "        Run `make install` (writes ~/bin/llama-server for the stock llama.cpp image\n"
        "        and ~/bin/prism-server for the Prism image), or set\n"
        "        LLAMA_SERVER=/full/path/to/llama-server for a native build."
    )


# ----------------------------------------------------------------------------
# HF top-tier trending discovery + download placement
# ----------------------------------------------------------------------------
def _hf_get(url, timeout=30):
    """GET a HF API url and return parsed JSON (list or dict).

    Transient HF failures are retried with backoff (429 rate-limits, 5xx server
    blips, and plain network errors / socket timeouts). The top-tier discovery
    fan-out issues one API call per repo tree (hundreds in family mode), so an
    unretried 429 on a single call previously dropped that repo from the family
    list — which could turn a valid "this family has a fitting model" into a false
    "no model fits", and a 429 on the search call itself hard-exited the CLI
    (issue #61 CI flake: same commit RED on push, GREEN on pull_request).

    Permanent HTTP errors (401/403/404, ...) are NOT retried — they fail fast so a
    genuinely gated/dead repo is still reported loudly (the F3/#53 skip path and
    the F8 "no repos" path rely on that).

    Raises SystemExit immediately on a permanent error, or once the transient
    retry budget is exhausted.
    """
    max_attempts = max(1, HF_GET_MAX_ATTEMPTS)
    for attempt in range(1, max_attempts + 1):
        req = urllib.request.Request(url, headers={"User-Agent": HF_UA,
                                                   "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code not in HF_TRANSIENT_HTTP:
                # Permanent (401/403/404/...): fail fast, never retry.
                raise SystemExit(f"[ERROR] HF API {e.code} for {url}")
            # Transient (429/5xx): back off + retry, honoring Retry-After if sent.
            retry_after = (e.headers or {}).get("Retry-After")
        except urllib.error.URLError:
            # Plain URLError (DNS, connection reset, socket timeout) = transient.
            retry_after = None
        if attempt < max_attempts:
            pause = HF_GET_BASE_PAUSE * (2 ** (attempt - 1))
            if retry_after:
                try:
                    pause = max(pause, float(retry_after))
                except (TypeError, ValueError):
                    pass  # non-numeric Retry-After -> keep the exponential backoff
            print(f"[top-tier] HF API transient error ({url.split('?')[0]}, "
                  f"attempt {attempt}/{max_attempts}); retrying in {pause:.1f}s",
                  file=sys.stderr, flush=True)
            time.sleep(pause)
    # Exhausted the retry budget on a transient error.
    raise SystemExit(f"[ERROR] HF API still failing after {max_attempts} attempts for {url}")


def _trending_gguf_repos(limit=25):
    """Top trending GGUF repos from HF (time-weighted trendingScore), no auth.

    Returns a list of dicts with id, downloads, likes, trendingScore.
    """
    url = (f"{HF_API}?sort=trendingScore&direction=-1&filter=gguf"
           f"&limit={limit}")
    data = _hf_get(url)
    out = []
    for m in data:
        rid = m.get("id", "")
        if not _is_top_tier_repo(rid):
            continue
        out.append({
            "repo": rid,
            "downloads": m.get("downloads", 0),
            "likes": m.get("likes", 0),
            "trendingScore": m.get("trendingScore", 0),
        })
    # Guard against API order drift: ALWAYS rank trendingScore desc, top first.
    # (We request sort=trendingScore&direction=-1 but never trust the wire order.)
    return sorted(out, key=lambda r: r["trendingScore"], reverse=True)


def _is_top_tier_repo(repo):
    rl = repo.lower()
    return any(f in rl for f in TOP_TIER_FAMILIES)


def _family_keyword_matches(repo, keyword):
    """Word-boundary family match on the repo id (NOT a plain substring).

    `--family qwen` must match `Qwen/Qwen2.5-0.5B-Instruct-GGUF` and
    `unsloth/Qwen3.8-27B-GGUF` (the keyword may be followed by a version
    DIGIT, e.g. `qwen2`/`qwen3`) but NOT a *different* family that starts
    with the same letters — `Jackrong/Qwopus...`, `empero-ai/Qwythos...`.
    The keyword must therefore NOT be followed by a letter (that would make
    it the prefix of another family's name); a trailing digit is a version
    number and is allowed. Case-insensitive, whole-word prefix:
    `(?<![a-z0-9])<kw>(?![a-z])`.
    """
    kw = (keyword or "").lower()
    if not kw:
        return False
    return re.search(
        r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z])", repo.lower()) is not None


def _family_gguf_repos(keyword, limit=300):
    """All GGUF repos for ONE model family keyword, ranked for family mode.

    Unlike `_trending_gguf_repos` (the global trending WINDOW), family mode
    needs the COMPLETE family — a niche family has 0-2 repos in the trending
    slice. So this queries the full model set for the keyword with
    `filter=gguf&sort=downloads&direction=-1` and NO `sort=trendingScore`,
    then keeps only word-boundary keyword matches that are top-tier families,
    ranked trendingScore desc with downloads desc tie-break (trendingScore is
    sparse — many family repos report 0, so downloads breaks ties honestly).
    Returns the same dict shape as `_trending_gguf_repos`.
    """
    url = (f"{HF_API}?search={urllib.parse.quote(keyword)}&filter=gguf"
           f"&sort=downloads&direction=-1&limit={limit}")
    data = _hf_get(url)
    out = []
    for m in data:
        rid = m.get("id", "")
        if not _family_keyword_matches(rid, keyword):
            continue
        if not _is_top_tier_repo(rid):
            continue
        out.append({
            "repo": rid,
            "downloads": m.get("downloads", 0),
            "likes": m.get("likes", 0),
            "trendingScore": m.get("trendingScore", 0),
        })
    # NEVER trust the wire order: trendingScore desc, downloads desc tie-break.
    return sorted(out, key=lambda r: (-r["trendingScore"], -r["downloads"]))


def _repo_gguf_files(repo):
    """List .gguf files in a repo with real byte sizes (tree API)."""
    url = f"{HF_API}/{repo}/tree/main?recursive=true"
    data = _hf_get(url)
    files = []
    for f in data:
        path = f.get("path", "")
        size = f.get("size", 0) or 0
        if path.lower().endswith(".gguf") and size > 0:
            files.append({"path": path, "size": size, "size_bytes": size,
                          "size_gb": size / (1024 ** 3)})
    return files


def _probe_file_downloadable(repo, filename, timeout=15, probe_bytes=64 * 1024):
    """Pre-flight check that a repo file is genuinely DOWNLOADABLE by fetching a
    real chunk of bytes (not just a status code).

    Downloads the first `probe_bytes` (a ranged request — cheap, no full download)
    and verifies the bytes are real GGUF model data, not an HTML/error page that a
    gated or broken server might serve with HTTP 200. Returns one of:
      "ok"                  -> fetched a real chunk that looks like GGUF binary
      "access-denied"       -> 401/403 (gated/private: 'requires approval')
      "dead"                -> 404 (file/repo gone)
      None                  -> transient/other failure (caller decides: retry, not skip)
    """
    url = f"https://huggingface.co/{repo}/resolve/main/{filename}"
    req = urllib.request.Request(url, method="GET")
    req.add_header("User-Agent", HF_UA)
    req.add_header("Range", f"bytes=0-{probe_bytes - 1}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read(probe_bytes)
            if data[:4] == b"GGUF":
                return "ok"
            if data.startswith(b"<") or b"<html" in data[:512] or b"error" in data[:512].lower():
                return None  # HTML/error body served as 200 -> not a real model
            return "ok" if len(data) >= 256 else None
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return "access-denied"
        if e.code == 404:
            return "dead"
        return None
    except Exception:
        return None


def pick_tier_folder(size_bytes, total_ram_bytes=None):
    """Smallest GPU tier folder that holds this model, bounded by the card that runs it.

    The tier ladder (TIER_LADDER_GB) is a growing superset of the old 8/16/24/48
    buckets. Only ladder entries <= the card's total (detected or overridden) are
    "available"; a model's tier is the smallest AVAILABLE bucket >= its size, else
    the largest available bucket. So a 48 GB card keeps 8/16/24/48 exactly, while a
    512 GB card also has 96/128/.../512 and can label a 400 GB model truthfully.
    """
    total = total_ram_bytes if total_ram_bytes is not None else read_total_ram_bytes()
    card_gb = total / (1024 ** 3)
    available = [b for b in TIER_LADDER_GB if b <= card_gb]
    if not available:
        # degenerate tiny card: fall back to the smallest bucket
        return f"{TIER_LADDER_GB[0]}GB"
    gb = size_bytes / (1024 ** 3)
    for bucket in available:
        if gb <= bucket:
            return f"{bucket}GB"
    return f"{available[-1]}GB"  # bigger than any available bucket -> largest


def provider_dest_path(repo, filename, size_bytes, models_root=None, total_ram_bytes=None):
    """Provider-aware destination: ~/{MODELS_ROOT}/<owner>/<family>/<TierGB>/<file>."""
    root = models_root or MODELS_ROOT
    owner, family = _split_repo(repo)
    tier = pick_tier_folder(size_bytes, total_ram_bytes)
    return os.path.join(root, owner, family, tier, filename)


def _split_repo(repo):
    """'unsloth/Qwen3.8-27B-GGUF' -> ('unsloth', 'Qwen3.8-27B-GGUF')."""
    if "/" in repo:
        a, b = repo.split("/", 1)
        return a, b
    return repo, repo


def discover_top_tier(limit=10, total_ram_bytes=None, headroom_bytes=None,
                      min_trending_score=0, per_provider=2, skip_summary=None,
                      family=None, family_repos=None, models_root=None):
    """Ranked top-tier GGUF candidates that FIT the card, with real file sizes.

    Combines the three signals (trending + top-tier family + fit gate) using the
    dynamic total/headroom read from the card. For each trending provider (owner)
    it offers `per_provider` candidates at DIFFERENT quant sizes: the best
    (highest-fidelity that still fits comfortably) plus a lighter quant — so you
    get variety of BOTH provider and quantization quality, and the lower quants
    fit with comfortable margin instead of "barely fits". Returns a list of dicts:
      {repo, filename, size_gb, size_bytes, downloads, likes,
       trendingScore, tier_folder, dest_path}
    ranked best-quality first, then trending. `limit` = total candidates to return;
    `min_trending_score` = rating floor.

    `family` (optional keyword): scope discovery to ONE model family. When set,
    the repo list comes from `_family_gguf_repos(family)` (the COMPLETE family,
    word-boundary matched) instead of the global trending window, and
    `min_trending_score` is IGNORED (forced to 0 — a score floor would filter a
    niche family out entirely). `family_repos` may pre-supply that repo list (so
    the CLI can print its readout without a second API pass). Everything
    downstream (fit gate, high+lower per provider, pre-flight probe + refill,
    placement) is the SAME code. `family=None` is byte-identical to the
    pre-existing trending path.
    """
    total = total_ram_bytes if total_ram_bytes is not None else read_total_ram_bytes()
    head = headroom_bytes if headroom_bytes is not None else read_current_headroom_bytes(total)
    kv_reserve = 1 * 1024 ** 3  # conservative KV headroom for the fit gate
    # Family mode: a score floor would filter a niche family out entirely —
    # force it to 0 (the repo list is already the complete, ranked family).
    if family is not None:
        min_trending_score = 0

    def candidate_files(repo):
        try:
            files = _repo_gguf_files(repo)
        except SystemExit:
            return []
        return sorted(
            [f for f in files
             # top-tier: real model file, big enough to be non-trivial
             if f["size_gb"] >= MIN_TOP_TIER_GB
             and not os.path.basename(f["path"]).startswith(("mmproj", "Qwen_VL"))
             and "-multi-of-" not in os.path.basename(f["path"])
             and "-00001-of-" not in os.path.basename(f["path"])
             and "0000" not in os.path.basename(f["path"])
             # MTP/mtp-* files are multi-token-prediction COMPANION heads, not the
             # main serviceable model — never offer them as a "top-tier" pick.
             and "mtp-" not in os.path.basename(f["path"]).lower()
             # "no lower models": skip low-fidelity IQ1/IQ2/IQ3 quants even when a
             # trending provider only offers those (a 27B at ~8-11 GB is poor quality).
             and not re.search(r"(?:-|_)(IQ[123]_|IQ[12]XS|IQ[123][0-9])", os.path.basename(f["path"]), re.I)
             ],
            key=lambda f: f["size_gb"], reverse=True,
        )

    # Per provider: take the best-fit (largest = highest quant) and then a clearly
    # LOWER quant (Q4/Q5/Q6 class, ~30%+ smaller) so you get high + lower quality
    # variety from each provider, and the lower quants fit with comfortable margin.
    # Both must fit comfortably.
    cands = []
    skipped = []  # (repo, filename, reason) for gated/dead repos
    seen_repos = set()
    window = max(limit, 10) * 3
    while len(cands) < limit:
        if family is not None:
            # The complete family list (pre-supplied by the CLI or fetched here),
            # widened window = prefix of the ranked list for refill passes.
            if family_repos is not None:
                repos = family_repos[:window]
            else:
                repos = _family_gguf_repos(family, limit=window)
        else:
            repos = _trending_gguf_repos(limit=window)
        new_repos = [r for r in repos if r["repo"] not in seen_repos]
        if not new_repos:
            break  # source list exhausted (all seen) — nothing more to refill with
        for repo_info in new_repos:
            seen_repos.add(repo_info["repo"])
            if repo_info["trendingScore"] < min_trending_score:
                continue
            repo = repo_info["repo"]
            files = candidate_files(repo)
            owner_picks = []
            best = None
            for f in files:
                if f["size_bytes"] + head + kv_reserve > total:
                    continue  # doesn't fit comfortably -> skip
                if best is None:
                    best = f["size_bytes"]
                    owner_picks.append(f)
                    continue
                # 2nd+ pick: must be a clearly-different (lower) quant tier (~25% smaller)
                if best - f["size_bytes"] >= 0.25 * best:
                    owner_picks.append(f)
                    best = f["size_bytes"]  # allow a further-lower quant after this one
                if len(owner_picks) >= per_provider:
                    break
            for chosen in owner_picks:
                filename = os.path.basename(chosen["path"])
                # PRE-FLIGHT: verify the object is actually downloadable (skip gated/dead fast).
                probe = _probe_file_downloadable(repo, filename)
                if probe == "access-denied":
                    skipped.append((repo, filename, "access-denied"))
                    print(f"[top-tier] skipping {repo}::{filename}: access-denied (403)", flush=True)
                    continue
                if probe == "dead":
                    skipped.append((repo, filename, "dead"))
                    print(f"[top-tier] skipping {repo}::{filename}: dead (404)", flush=True)
                    continue
                if probe is None:
                    # transient or a 200-HTML shell served without the right body;
                    # do NOT hard-skip (could be a blip), but do not count it either here.
                    print(f"[top-tier] probe inconclusive for {repo}::{filename}", flush=True)
                cands.append({
                    "repo": repo,
                    "filename": filename,
                    "size_bytes": chosen["size_bytes"],
                    "size_gb": chosen["size_gb"],
                    "downloads": repo_info["downloads"],
                    "likes": repo_info["likes"],
                    "trendingScore": repo_info["trendingScore"],
                    "tier_folder": pick_tier_folder(chosen["size_bytes"], total),
                    "dest_path": provider_dest_path(repo, filename,
                                                    chosen["size_bytes"], models_root=models_root,
                                                    total_ram_bytes=total),
                })
            if len(cands) >= limit:
                break
        window = max(window * 2, limit * 3)  # widen the search window for the next pass
    # populate the skip summary (repo, reason) for the caller's completion report
    if skip_summary is not None:
        skip_summary.extend(skipped)
    # Rank so a provider's high + lower quants stay together (group by provider).
    # Order PROVIDERS by what's TRENDING now (highest trendingScore first,
    # downloads desc tie-break — trendingScore is sparse, so downloads breaks
    # ties honestly), each with its high + lower quant. (NOT by file size, which
    # would surface the biggest file of a niche provider over a genuinely
    # trending one.)
    cands.sort(key=lambda c: (c["repo"], -c["size_gb"]))              # group by provider, high first
    providers = {}
    for c in cands:
        providers.setdefault(c["repo"], []).append(c)
    ordered = []
    for repo in sorted(providers,
                       key=lambda r: (-providers[r][0]["trendingScore"],
                                      -providers[r][0]["downloads"])):
        ordered.extend(providers[repo])
    return ordered[:limit]


def download_top_tier_candidate(cand, models_root=None):
    """Download a top-tier candidate via the real hf CLI (etag-aware, idempotent).

    ALWAYS delegates to scripts/hf_download.py in REFRESH mode, which runs
    `hf download`. That command etag/content-hashes the file against the Hub:
      - unchanged local file  -> hf no-ops fast, returns existing path
      - file UPDATED upstream (even SAME filename + SAME size, new bytes)
        -> the etag differs, hf re-fetches that one file
    We deliberately do NOT skip on mere existence/size, because a size-only
    guard would mask a same-name content update.
    """
    dest_dir = os.path.dirname(cand["dest_path"])
    final = cand["dest_path"]
    hf = (os.environ.get("HF_BIN") or "").strip() or shutil.which("hf")
    if not hf or not os.path.isfile(hf):
        # hf-env fallback used on the host (downloader also reads HF_BIN), then the
        # launcher's own venv (make install now bundles huggingface_hub[cli]).
        for _hf_cand in (os.path.expanduser("~/models/hf-env/bin/hf"),
                         os.path.join(os.path.dirname(sys.executable), "hf")):
            if os.path.isfile(_hf_cand):
                hf = _hf_cand
                break
        if not hf:
            raise SystemExit("[ERROR] 'hf' CLI not found. Install huggingface_hub "
                             "(or set HF_BIN) — top-tier download aborts (no fallback).")
    os.makedirs(dest_dir, exist_ok=True)
    os.environ["HF_BIN"] = hf   # downloader (hf_download.py) resolves HF_BIN to find hf
    dl = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hf_download.py")
    label = f"top-tier-{os.path.basename(final)}".replace(".gguf", "")[:40]
    cmd = [sys.executable, dl, cand["repo"], cand["filename"], dest_dir, label, "1",
       str(cand.get("size_bytes", ""))]
    print(f"[top-tier] downloading {cand['repo']}::{cand['filename']} -> {dest_dir} "
          f"({cand['size_gb']:.2f} GB, tier {cand['tier_folder']})")
    rc = subprocess.call(cmd)
    if rc != 0 or not os.path.isfile(final) or os.path.getsize(final) < 100_000_000:
        raise SystemExit(f"[ERROR] top-tier download failed (rc={rc}); file missing/incomplete: {final}")
    # VERIFY the downloaded file by its GGUF metadata header (not just size/existence):
    # the file must actually be a readable GGUF model, not an HTML error page or a
    # truncated/corrupt stub that happens to have the right filename+size.
    meta = read_model_meta_fast(final)
    if meta is None:
        try:
            meta = read_model_meta(final)   # full reader fallback (handles unusual GGUFs)
        except Exception:
            meta = None                     # corrupt/non-GGUF -> reject, never raise
    if meta is None:
        raise SystemExit(f"[ERROR] downloaded file is not a valid GGUF model "
                         f"(metadata unreadable): {final}")
    print(f"[top-tier] verified downloaded model via GGUF metadata: "
          f"arch={meta.get('arch')}, name={meta.get('name')}, "
          f"layers={meta.get('n_layer')}, ctx_train={meta.get('ctx_train')}", flush=True)
    return final


def build_command(meta, ctx, port, card_bytes=None, backend=None):
    """Build the llama-server argv for `meta`.

    `card_bytes` is the card's real RAM in bytes (GPU VRAM when an NVIDIA card
    is present, else system RAM — the #84 "card RAM", via
    `detect_server.detect_card_ram_bytes()` and its LLAMA_RAM_BYTES seam). If
    omitted it is resolved at call time. MTP depth, GPU-layer count, and the
    batch size are derived from this value and from what the GGUF supports.
    `backend` is cuda, metal, or cpu (`detect_server.detect_backend()` when
    omitted).
    """
    global LLAMA_SERVER
    if card_bytes is None:
        card_bytes = detect_server.detect_card_ram_bytes()
    if backend is None:
        backend = detect_server.detect_backend()
    cmd = [LLAMA_SERVER,
           "-m", meta["file"],
           "--host", "0.0.0.0",
           "--port", str(port),
           "-c", str(ctx)]
    ngl = gpu_offload_layers(meta, ctx, card_bytes, backend)
    if ngl is not None:
        cmd += ["-ngl", str(ngl)]
    if backend in ("cuda", "metal"):
        cmd += ["-fa", "on"]
    if meta.get("chat_template"):
        cmd += ["--jinja"]
    batch, ubatch = batch_for_card(card_bytes)
    cmd += ["-ctk", KV_QUANT, "-ctv", KV_QUANT,
            "-b", str(batch), "-ub", str(ubatch),
            "--cont-batching",
            "--metrics"]
    # Sampling flags: use the model's author-recommended defaults
    # (general.sampling.*) when present, else fall back to the global preset.
    # Each flag and value is a SEPARATE argv element (llama.cpp treats one
    # "--temp 0.7" string as a single invalid argument). Emit EITHER model
    # defaults OR the preset, never both, never a flag twice.
    sampling = meta.get("sampling") or {}
    if sampling:
        for key, value in sampling.items():
            flag = SAMPLING_FLAG_MAP.get(key)
            if flag is None:
                continue  # unknown key: ignore, never raise
            cmd += [flag, value]
    elif prism_quant_name(meta):
        cmd += list(PRISM_SAMPLING)
    else:
        cmd += list(SAMPLING)
    # reasoning-capable model: enable reasoning + return thoughts in
    # `message.reasoning_content` (deepseek format) so thinking is preserved.
    if is_reasoning_model(meta):
        cmd += ["--reasoning", "on", "--reasoning-format", "deepseek"]
    # MTP (multi-token-prediction) head: engage when the GGUF carries nextn
    # layers (e.g. Qwen3.8-27B MTP / Ternary-Bonsai MTP). The depth
    # (--spec-draft-n-max) is derived from the card's VRAM, not hard-coded
    # (qwen38-mtp community rules: depth sweet-spot is card/bandwidth dependent).
    # The opt-in LLAMA_SPEC_DRAFT_P_MIN gate is emitted only when explicitly set.
    cmd += mtp_spec_flags(meta, card_bytes)

    # parallel slots: 2 for small models, 1 for big. MTP is a single-stream
    # optimisation, so when it is engaged the parallel slots are pinned to 1
    # (rule 5: --parallel > 1 kills the gain; a --parallel 2 baseline reads low
    # and inflates the claim).
    np_slots = 1 if meta.get("nextn_layers", 0) else (2 if meta["size_gb"] < 10 else 1)
    cmd += ["-np", str(np_slots)]
    # FIXED alias so the serving endpoint keeps the SAME name across model
    # switches. Clients (Hermes server, agent CLIs) pin one name and keep
    # working no matter which model is loaded. The real model id is still
    # served under the per-model filename alias as well.
    STABLE_ALIAS = "llm-local"
    cmd += ["--alias", STABLE_ALIAS]
    return cmd


def pretty(cmd):
    return " \\\n  ".join(cmd)


def stop_server_on_port(port):
    """Stop any llama-server already listening on `port` (one model at a time)."""
    try:
        out = subprocess.run(
            ["lsof", "-ti", f"tcp:{port}"], capture_output=True, text=True, timeout=5
        ).stdout.strip()
    except Exception:
        out = ""
    if not out:
        return 0
    pids = [p for p in out.split() if p]
    for p in pids:
        subprocess.run(["kill", "-9", p], capture_output=True)
    return len(pids)


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
def _main_download_top_tier(args):
    """Discover + download currently-trending top-tier GGUFs that fit the card.

    --family  -> scope discovery to ONE model family (top providers of that
                 family, word-boundary matched) instead of global trending.
    --list   -> print the ranked candidates that fit, then exit (no download).
    --dry    -> download nothing; just report what would be downloaded/served.
    default  -> download the top `--count` candidates that fit, then serve the
                highest-ranked one (unless --list). Honors --port/--dry.
    """
    limit = max(1, args.count)
    per_provider = max(1, args.per_provider or 2)   # high + lower quant per provider
    family = getattr(args, "family", None)
    print(f"[top-tier] detecting memory on the actual card ...")
    total = read_total_ram_bytes()
    head = read_current_headroom_bytes()
    print(f"[top-tier] total RAM = {total/(1024**3):.0f} GB, headroom (wired+safety) = "
          f"{head/(1024**3):.1f} GB")
    # Family mode: a word-boundary keyword scopes the SAME pipeline to ONE family.
    # Zero matching repos is a loud failure (typo / non-GGUF family), never a
    # silent success.
    family_readout = ""
    family_repos = []
    if family:
        family_repos = _family_gguf_repos(family, limit=300)
        n_files = 0
        for r in family_repos:
            try:
                n_files += len(_repo_gguf_files(r["repo"]))
            except SystemExit:
                pass  # an unlistable repo contributes 0 files; discovery will skip it
        family_readout = (f"[family] {family} → {len(family_repos)} providers "
                          f"({n_files} files) match")
        print(family_readout, flush=True)
        if not family_repos:
            print(f"[top-tier] no GGUF repos found for family '{family}'. "
                  "Nothing downloaded.", file=sys.stderr)
            sys.exit(1)
    # `--count` = number of PROVIDERS; each yields per_provider quants (high+lower).
    skip_summary = []  # (repo, reason) for gated/dead repos dropped pre-flight
    cands = discover_top_tier(limit=max(1, limit * per_provider),
                              total_ram_bytes=total, headroom_bytes=head,
                              min_trending_score=args.min_trending_score,
                              per_provider=per_provider, skip_summary=skip_summary,
                              family=family,
                              family_repos=(family_repos if family else None))
    if not cands:
        if family:
            print(f"[top-tier] no model from family '{family}' fits the available card "
                  "right now. Nothing downloaded.")
        else:
            print("[top-tier] no trending top-tier GGUF model fits the available card right now. "
                  "Nothing downloaded.")
        return
    if family:
        total_str = (f"top {limit} providers of family '{family}' "
                     f"that fit {total/(1024**3):.0f} GB:")
    else:
        total_str = f"top {limit} trending top-tier models that fit {total/(1024**3):.0f} GB:"
    if args.list:
        print(f"\n{total_str}\n")
        for i, c in enumerate(cands, 1):
            print(f"{i:2d}. [{c['trendingScore']:>4} trend] {c['size_gb']:7.2f} GB  "
                  f"{c['repo']}::{c['filename']}  -> {c['dest_path']}")
        print()
        return
    # --dry: print what would be downloaded, do NOT download or serve.
    if args.dry:
        print(f"\n[dry] would download top {len(cands)} top-tier provider(s):\n")
        for i, c in enumerate(cands, 1):
            print(f"{i:2d}. [{c['trendingScore']:>4} trend] {c['size_gb']:7.2f} GB  "
                  f"{c['repo']}::{c['filename']}  -> {c['dest_path']}")
        print("\n[dry] nothing was downloaded or served (--dry).")
        return
    # Download the top `limit` candidates (idempotent per provider). Any single
    # failure is retried (up to RETRIES); already-completed downloads are never
    # re-fetched (download_top_tier_candidate etag-checks the Hub), so a retry
    # only resumes/completes the failed one. A persistent failure doesn't abort
    # the batch — remaining providers are still attempted.
    RETRIES = 3
    completed = []
    for i, c in enumerate(cands, 1):
        print(f"\n[{i}/{len(cands)}] downloading top-tier candidate: {c['repo']}::{c['filename']}")
        ok = False
        for attempt in range(1, RETRIES + 1):
            try:
                download_top_tier_candidate(c)
                ok = True
                break
            except SystemExit as e:
                print(f"  attempt {attempt}/{RETRIES} failed for {c['repo']}: "
                      f"{str(e).splitlines()[0] if str(e) else 'download error'}",
                      file=sys.stderr)
                if attempt < RETRIES:
                    time.sleep(2)
        if ok:
            completed.append(c)
        else:
            print(f"  SKIPPED {c['repo']} after {RETRIES} failed attempts.", file=sys.stderr)
    if not completed:
        print("[top-tier] nothing could be downloaded.")
        sys.exit(1)
    print(f"\n[top-tier] completed {len(completed)}/{len(cands)} provider(s).")
    skip_line = _skip_summary_line(skip_summary)
    if skip_line:
        print(f"[top-tier]   (+{skip_line}).")
    print("[top-tier] downloaded models are available to serve. Use the normal "
          "launch path (e.g. `llgenie <model-name>`) to start llama-server — "
          "`--download-top-tier` only downloads; it never auto-starts the server.")
    for i, c in enumerate(completed, 1):
        print(f"  {i}. {c['repo']}::{c['filename']}  -> {c['dest_path']}")


def _skip_summary_line(skip_summary):
    """Format the pre-flight skip summary (per reason) or '' if empty.

    skip_summary is a list of (repo, filename, reason) tuples. Returns the
    'N skipped pre-flight: <reason-counts>' suffix (without the parens or trailing
    period), or '' when there are no skips. Does NOT crash on the real 3-tuple
    shape (regression: issue #56 — previously unpacked 2-tuples and raised
    'ValueError: not enough values to unpack (expected 2)' whenever a repo was
    pre-flight skipped).
    """
    if not skip_summary:
        return ""
    by_reason = {}
    for _repo, _filename, reason in skip_summary:
        by_reason[reason] = by_reason.get(reason, 0) + 1
    parts = ", ".join(f"{n} {r}" for r, n in sorted(by_reason.items()))
    return f"{len(skip_summary)} skipped pre-flight: {parts}"


def invoke_llama_server(cmd, model_path):
    """Record the argv, then start that llama-server binary.

    The command line is appended to ``.run.log`` beside the model before
    ``subprocess.run``. Tests replace ``subprocess.run`` and read the log to
    see the parameters that were about to be passed.
    """
    log_path = os.path.join(os.path.dirname(model_path) or ".", ".run.log")
    with open(log_path, "a") as lf:
        lf.write(f"\n[{time.ctime()}] launching {os.path.basename(model_path)}\n")
        lf.write(" ".join(cmd) + "\n")
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nStopped.")
    except FileNotFoundError:
        print(f"\n[ERROR] llama-server binary disappeared after resolution ({cmd[0]}).\n"
              "        Reinstall or put 'llama-server' on PATH and retry.")
        sys.exit(1)


def _serve_chosen(chosen, args):
    """Tune + print + optionally launch llama-server for a chosen local meta dict."""
    card_bytes = detect_server.detect_card_ram_bytes()
    ctx = serve_context(chosen, card_bytes)
    global LLAMA_SERVER
    LLAMA_SERVER = resolve_llama_server()
    cmd = build_command(chosen, ctx, args.port, card_bytes=card_bytes)

    print(f"\nModel : {chosen['name']} ({chosen['arch']})")
    print(f"File  : {chosen['file']}")
    print(f"Layers: {chosen['n_layer']}, dim={chosen['n_embd']}, heads={chosen['n_head']}, kv_heads={chosen['n_head_kv']}")
    print(f"Train ctx: {chosen['ctx_train']}, KV/tok ~= {kv_bytes_per_token(chosen)/1e6:.1f} MB")
    print(f'Serving at http://127.0.0.1:{args.port}, context = {ctx} tokens\n')
    print("Command:\n  " + pretty(cmd) + "\n")
    print("Log: " + os.path.join(os.path.dirname(chosen["file"]), ".run.log"))
    print("Stop with Ctrl-C.\n")

    if args.dry:
        return

    stopped = stop_server_on_port(args.port)
    if stopped:
        print(f"Stopped {stopped} existing listener(s) on port {args.port} (one model at a time).")
        time.sleep(1)

    invoke_llama_server(cmd, chosen["file"])


def _engine_script(engine_id):
    """~/bin/llgenie-engine-<id>, written by `make install`."""
    return os.path.join(HOME, "bin", "llgenie-engine-" + engine_id.replace(".", "-").replace("/", "-"))


def _ensure_and_exec(eng, path, args):
    """Print the plan, pull the engine image on first use, exec its start script."""
    script = _engine_script(eng["id"])
    cmd = [script, str(path), str(args.port)]
    print(f"Serving: http://127.0.0.1:{args.port}/v1  model=llm-local")
    print("Command: " + " ".join(cmd))
    if args.dry:
        return
    # first use of this engine: pull its published image for this backend and
    # write its start script (make install only installs the llama.cpp core)
    inst = os.path.join(os.path.dirname(os.path.abspath(__file__)), "install_engine_launchers.py")
    rc = subprocess.run([sys.executable, inst, "--bin", os.path.dirname(script),
                         "--ensure", eng["id"], "--arch", eng["variant"]]).returncode
    if rc or not os.access(script, os.X_OK):
        raise SystemExit(f"[llgenie] could not install the {eng['id']} image ({eng['variant']}); "
                         f"check LLGENIE_REGISTRY / docker, or run `make install ENGINES={eng['id']}`")
    stop_server_on_port(args.port)
    os.execv(script, cmd)


def _pick_mp():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import model_engine_pick as mp
    return mp


def _match_engine(engines, want):
    """`want` (substring of id/name) among `engines`, or exit naming them."""
    hit = [e for e in engines if want.lower() in (e["id"] + " " + e["engine"]).lower()]
    if not hit:
        names = ", ".join(e["id"] for e in engines) or "none"
        raise SystemExit(f"[llgenie] engine {want!r} is not compatible here; compatible engines: {names}")
    return hit[0]


def _local_files(sub):
    """Local GGUF files / HF model dirs under the models root whose name contains `sub`
    (filename match only: no metadata parse, so any readable file counts)."""
    root = Path(models_root())
    given = Path(os.path.expanduser(sub or ""))
    if sub and given.exists() and (given.suffix == ".gguf" or (given / "config.json").exists()):
        return [given.resolve()]  # an explicit path
    if not sub or not root.exists():
        return []
    hits = [p for p in root.rglob("*") if sub.lower() in p.name.lower()
            and (p.suffix == ".gguf" or (p.is_dir() and (p / "config.json").exists()))
            and not p.name.endswith((".incomplete", ".progress.log"))]
    return sorted(hits, key=lambda p: p.stat().st_size if p.is_file() else 0)


def _registry_match(rows, want):
    """Rows whose model id or name equals `want` (case-insensitive) when any does,
    else those containing it: `qwen3-8b` is Qwen3 8B, not RavenX-...-Qwen3-8B-MLX."""
    w = want.lower()
    exact = [r for r in rows if w in (r["model"]["id"].lower(), r["model"]["name"].lower())]
    return exact or [r for r in rows if w in (r["model"]["name"] + " " + r["model"]["id"]).lower()]


def _main_engines(args):
    """--engines [model]: engines with an image for this host (all, or compatible)."""
    mp = _pick_mp()
    if not args.model:
        rows = mp.host_engines()
        print(f"Engines with a published image for this host ({mp.host_arch()}):")
        for e in rows:
            print(f"  {e['id']:<28} {e['engine']:<34} [{e['variant']}]  formats: {', '.join(e['formats'])}")
        return
    local = _local_files(args.model)
    if local:
        f = str(local[0])
        print(f"Engines that can serve {os.path.basename(f)} ({mp.model_format(Path(f))}) here:")
        for e in mp.engines_for_file(Path(f)):
            print(f"  {e['id']:<28} {e['engine']:<34} [{e['variant']}]")
        return
    rows = _registry_match(mp.rank_models(mp.load_registry()), args.model)
    if not rows:
        raise SystemExit(f"[llgenie] no local or registry model matches {args.model!r}")
    print(f"Engines for {rows[0]['model']['name']} on this host, best reported t/s first:")
    for e in rows[0]["engines"]:
        print(f"  {e['id']:<28} {e['engine']:<34} [{e['variant']}] {e['tps']:>6.0f} t/s")


def _main_local_engine(args, path):
    """llgenie <local model> --engine <e>: serve that pair if compatible."""
    mp = _pick_mp()
    path = Path(path)
    eng = _match_engine(mp.engines_for_file(path), args.engine)
    print(f"\nModel  : {path.name}  ({path})")
    print(f"Engine : {eng['engine']} [{eng['variant']}]")
    _ensure_and_exec(eng, path, args)


def _tps_label(e):
    """'124 t/s' (this host's hardware), '96 t/s (ROCm)', or 'supported' (no figure)."""
    if not e.get("measured_on"):
        return "supported"
    return f"{e['tps']:.0f} t/s" + ("" if e["same_hw"] else f" ({e['measured_on']})")


def _ask(rows, prompt):
    """Ask for a number 1..len(rows) (list already printed); re-ask on bad input."""
    while True:
        try:
            sel = input(f"Pick {prompt} [1]: ").strip() or "1"
        except EOFError:
            raise SystemExit("cancel") from None
        if sel.isdigit() and 1 <= int(sel) <= len(rows):
            return rows[int(sel) - 1]
        print(f"  enter 1-{len(rows)}")


def _print_trend(mp, reg, rows, gb):
    """The README trend list that fits this card; numbers = what --select / the prompt take."""
    print(f"\ntrending-local-llms ({reg.get('generated_utc', '')}): every model whose VRAM fits "
          f"this card ({gb:.0f} GB, {mp.host_arch()}), in README order:")
    n = 0
    for r in rows:
        m, e = r["model"], (r["engines"] or [None])[0]
        head = (f"{m['name']:<30} {mp.BAND_LABEL[mp.band(m, mp.registry_today(reg))]:<8} "
                f"trend {mp.trend_score(m):>4.1f}  {m['vram_tier']:>5}  ")
        if r.get("why"):
            print(f"   --  {head}not here: {r['why']}")
            continue
        n += 1
        mark = "  [local]" if r.get("local") else ""
        print(f"  {n:2d}.  {head}{e['engine']} {_tps_label(e)}{mark}")


def _main_pick(args):
    """Trend pick (issue #105): recommended model -> its engines -> download -> serve."""
    mp = _pick_mp()
    reg = mp.load_registry()
    manual = bool(args.model or args.engine or args.model_file)
    gb = mp.card_gb()
    if args.model:  # a registry model by id / name (exact first, then substring)
        reg = {**reg, "models": [r["model"] for r in _registry_match(
            [{"model": m} for m in reg.get("models") or []], args.model)]}
    if args.model_file:  # the given file decides the format
        fmt = mp.model_format(Path(args.model_file).expanduser())
        rows = mp.recommend(reg, fmt=fmt)
        for r in rows:
            r["local"], r["plans"] = None, {}
            r["engines"] = [{**e, "use_format": fmt} for e in r["engines"]]
    else:
        rows = mp.offer(reg, gb=gb)
    if args.engine:  # only models the requested engine can run here
        want = args.engine.lower()
        rows = [r for r in rows if any(want in (e["id"] + " " + e["engine"]).lower() for e in r["engines"])]
    if manual:
        rows = [r for r in rows if not r.get("why")]
    if args.model and not rows:
        raise SystemExit(f"[llgenie] no registry model matches {args.model!r} with a compatible engine "
                         f"here; see `llgenie --engines {args.model}` or `llgenie --list`")
    local = {r["model"]["id"]: r["local"] for r in rows}
    pickable = [r for r in rows if not r.get("why")]
    if not pickable:
        raise SystemExit("[llgenie] no model of the trend list can be served on this card")
    interactive = not args.model and not args.auto and not args.select and sys.stdin.isatty()
    if interactive or args.trend or args.select:
        _print_trend(mp, reg, rows, gb)
    if args.trend:
        return
    if args.select:
        if not 1 <= args.select <= len(pickable):
            raise SystemExit(f"[llgenie] --select {args.select}: pick 1-{len(pickable)}")
        row = pickable[args.select - 1]
    elif interactive:
        row = _ask(pickable, "model")
    else:
        row = pickable[0]
    model, engines = row["model"], row["engines"]
    if args.engine:
        eng = _match_engine(engines, args.engine)
    else:
        if not args.auto and not args.select and sys.stdin.isatty():
            print(f"\nEngines for {model['name']} on this host, best t/s measured on {mp.host_arch()} hardware first:")
        eng = mp.choose(engines, lambda e: f"{e['engine']:<34} [{e['variant']}] {_tps_label(e):<16} "
                                           f"{e['use_format']:<16} {e['hardware']}",
                        "inference server", None, args.auto or bool(args.select))
    fmt = eng["use_format"]
    path = Path(args.model_file).expanduser().resolve() if args.model_file else local.get(model["id"])
    if args.model_file and not path.exists():
        raise SystemExit(f"[llgenie] --model-file {args.model_file} does not exist")
    if path is not None and not args.model_file and mp.model_format(path) != fmt:
        path = None  # the local copy is another format than this engine reads
    if path is None:
        print(f"[llgenie] {model['name']} ({fmt}) not under {mp.models_root()} -> downloading")
        plan = row.get("plans", {}).get(fmt) or mp.plan_download(model, gb, None, fmt)
        if not plan:
            raise SystemExit(f"[llgenie] {model['name']}: no {fmt} download fits this host")
        if args.dry:
            what = plan["path"] or f"(whole repo, {len(plan['files'])} files)"
            shards = f" ({len(plan['files'])} files)" if plan["path"] and len(plan["files"]) > 1 else ""
            print(f"[llgenie] (dry) would download {plan['repo']}/{what}{shards}, {plan['size'] / 2**30:.1f} GB")
            dest = mp.models_root() / plan["repo"].replace("/", "__")
            path = dest if plan.get("dir") else dest / plan["path"]
        else:
            path = mp.download(model, gb, fmt=fmt)
    print(f"\nModel  : {model['name']}  ({path})")
    print(f"Engine : {eng['engine']} [{eng['variant']}]  {_tps_label(eng)}")
    _ensure_and_exec(eng, path, args)


def main():
    ap = argparse.ArgumentParser(description="llgenie: pick a trending model + the fastest compatible engine for this card (default, interactive), or serve a local GGUF (llgenie <name> / --local)")
    ap.add_argument("model", nargs="?", help="substring of model filename to select")
    ap.add_argument("--list", action="store_true", help="just list models")
    ap.add_argument("--port", type=int, default=11434)
    ap.add_argument("--dry", action="store_true", help="print command without running")
    ap.add_argument("--download-top-tier", action="store_true",
                    help="discover + download the currently-trending top-tier GGUF model(s) "
                         "that fit the actual GPU/CPU card. DOWNLOAD ONLY — never auto-starts "
                         "llama-server; serve a downloaded model separately with `llgenie <name>`.")
    ap.add_argument("--count", type=int, default=5,
                    help="with --download-top-tier: number of distinct PROVIDERS to download "
                         "(each yields high + lower quants, default 5 = variety of what's popular)")
    ap.add_argument("--per-provider", type=int, default=2,
                    help="with --download-top-tier: quants per provider (default 2 = best + a "
                         "lower Q4/Q5/Q6 so each fits comfortably, not just Q8)")
    ap.add_argument("--min-trending-score", type=int, default=0,
                    help="with --download-top-tier: only consider repos whose HF trendingScore "
                         "is >= this (0 = any trending that fits). A rating floor so niche/"
                         "unrated models don't show.")
    ap.add_argument("--family", type=str, default=None,
                    help="with --download-top-tier: scope to ONE model family keyword "
                         "(e.g. 'qwen', 'ornith') — download the top --count providers of "
                         "THAT family (word-boundary match, so 'qwen' never matches "
                         "'qwopus'/'qwythos'), each with high + lower quants. "
                         "--min-trending-score is ignored in family mode.")
    ap.add_argument("--engine", type=str, default=None,
                    help="inference server to serve with (substring of the engine id/name, e.g. "
                         "'vllm', 'prism'). Without it llgenie ranks the engines that can run the "
                         "model on this host (highest reported t/s, then trending) and asks; "
                         "--auto takes the top one.")
    ap.add_argument("--pick", action="store_true",
                    help="pick from the trending registry instead of only local files: models "
                         "that fit this card, each with its fastest engine; the chosen model is "
                         "downloaded into ~/models if it is not there yet")
    ap.add_argument("--model-file", type=str, default=None,
                    help="with --pick/--engine: serve exactly this local model file (or dir) "
                         "instead of the one llgenie finds under ~/models")
    ap.add_argument("--engines", action="store_true",
                    help="list the engines with a published image for this host; with a model "
                         "(local file substring or registry name): only the compatible ones")
    ap.add_argument("--local", action="store_true",
                    help="pick from the local ~/models GGUF files and serve with llama.cpp "
                         "(prism-server / llama-server by card size) instead of the trend pick")
    ap.add_argument("--trend", action="store_true",
                    help="print the trend list (the trending-local-llms README list that fits this "
                         "card, numbered) and exit")
    ap.add_argument("--select", type=int, default=0, metavar="N",
                    help="take model N of the trend list without asking (same numbers as the "
                         "prompt); downloads it when missing, then serves it with its top engine "
                         "(or --engine)")
    ap.add_argument("--auto", action="store_true",
                    help="never ask: take the highest-t/s model (with --pick) and its "
                         "highest-ranked engine")
    args = ap.parse_args()

    if args.engines:
        _main_engines(args)
        return

    # llgenie <local model> --engine <e>: a manual, compatibility-checked pair
    if args.engine and args.model and not args.pick and not args.model_file:
        local = _local_files(args.model)
        if len(local) > 1:
            root = Path(models_root())
            rel = [str(p.relative_to(root)) if p.is_relative_to(root) else str(p) for p in local]
            raise SystemExit(f"[llgenie] {args.model!r} matches {len(local)} local models: "
                             + ", ".join(rel) + " (give the full path to pick one)")
        if local:
            _main_local_engine(args, local[0])
            return

    # trend pick (issues #102/#105): the default when no model is named, or
    # --pick / --engine: model + engine from the vendored registry, served
    # through the engine's container start script (make install).
    if args.pick or args.engine or args.trend or args.select or \
            not (args.model or args.list or args.local or args.download_top_tier):
        _main_pick(args)
        return

    # --download-top-tier path (trending + top-tier family + dynamic fit gate).
    if args.download_top_tier:
        _main_download_top_tier(args)
        return

    models = scan_models()
    if not models:
        print(f"No .gguf models found under {MODELS_ROOT}")
        sys.exit(1)

    if args.list:
        for i, m in enumerate(models, 1):
            print(f"{i:2d}. {m['size_gb']:7.2f} GB  {m['file']}  [ctx={m['ctx_train']}]")
        return

    # selection
    chosen = None
    if args.model:
        cands = [m for m in models if args.model.lower() in os.path.basename(m["file"]).lower()]
        if not cands:
            print(f"No model matches '{args.model}'. Use --list")
            sys.exit(1)
        if len(cands) > 1:
            print(f"'{args.model}' matches {len(cands)} models. Pick exactly one:\n")
            for i, m in enumerate(cands, 1):
                print(f"  {i}. {m['size_gb']:7.2f} GB  {os.path.basename(m['file'])}")
            print()
            try:
                sel = int(input("Pick number (or 0 to cancel): "))
            except (EOFError, ValueError):
                sel = -1
            if sel < 1 or sel > len(cands):
                print("cancel"); sys.exit(2)
            chosen = cands[sel - 1]
        else:
            chosen = cands[0]
        print(f"Selected: {chosen['file']}")
    else:
        print(f"\nModels under {MODELS_ROOT}:\n")
        for i, m in enumerate(models, 1):
            print(f"{i:2d}. {m['size_gb']:7.2f} GB  {os.path.basename(m['file'])}")
        try:
            sel = int(input("\nPick number: "))
        except (EOFError, ValueError):
            print("cancel"); sys.exit(2)
        chosen = models[sel - 1]

    # tune: the selected model's trained context is the ceiling; the card's RAM
    # (GPU VRAM when an NVIDIA card is present) is the budget.
    card_bytes = detect_server.detect_card_ram_bytes()
    ctx = serve_context(chosen, card_bytes)
    # resolve llama-server (LLAMA_SERVER override, then PATH) BEFORE building the
    # command — terminates with a clear error if the binary is missing.
    global LLAMA_SERVER
    LLAMA_SERVER = resolve_llama_server()
    cmd = build_command(chosen, ctx, args.port, card_bytes=card_bytes)

    print(f"\nModel : {chosen['name']} ({chosen['arch']})")
    print(f"File  : {chosen['file']}")
    print(f"Layers: {chosen['n_layer']}, dim={chosen['n_embd']}, heads={chosen['n_head']}, kv_heads={chosen['n_head_kv']}")
    print(f"Train ctx: {chosen['ctx_train']}, KV/tok ~= {kv_bytes_per_token(chosen)/1e6:.1f} MB")
    print(f"Serving at http://127.0.0.1:{args.port}, context = {ctx} tokens\n")
    print("Command:\n  " + pretty(cmd) + "\n")
    print("Log: " + os.path.join(os.path.dirname(chosen["file"]), ".run.log"))
    print("Stop with Ctrl-C.\n")

    if args.dry:
        return

    # one model at a time: stop anything already on the target port
    stopped = stop_server_on_port(args.port)
    if stopped:
        print(f"Stopped {stopped} existing listener(s) on port {args.port} (one model at a time).")
        time.sleep(1)

    invoke_llama_server(cmd, chosen["file"])


if __name__ == "__main__":
    main()
