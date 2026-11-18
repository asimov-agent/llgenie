#!/usr/bin/env python3
"""The pack contract: one code path for llgenie's multi-file model packs (issue #2909).

A PACK is a model whose checkpoint is a multi-file tree consumed as a DIRECTORY (edge0-145b's
`Edge0/Edge0-145B-q3k`: skeleton + latent MoE shards + tokenizer + config, served by edge0's
v5 launch contract), as opposed to the single-file contract every current engine speaks. The
contract has three legs, all spelled here so no consumer re-derives any of them:

1. MANIFEST  — `formats[].pack` (`{"revision", "files": [{"path", "bytes"?}]}`) on a registry
   record is the pack's file manifest; `manifest()` resolves it (or None for a non-pack record).
   ADDITIVE only: records without `pack` keep their single-quant shape.
2. SIZE      — a pack model is gated by the SUM of its declared bytes across the whole file set
   (`pack_gb()`), never by one pseudo-quant entry.
3. LAUNCH    — an engine's params may declare `model_contract: "pack"` with `pack.parts` +
   `pack.config_env` (env var -> part path); `launch_env()` validates every part is on disk and
   returns the docker `-e` wiring (`VAR=/models/<pack-dir>/<part>`). A missing part is a
   refusal naming the part, never a half-wired serve.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

PACK_FIELD = "pack"
_SAFE_PART = re.compile(r"^[^/\x00][^/]*$")  # a relative name segment; no absolute paths


def _valid_files(files) -> list[dict] | None:
    """The manifest's file list when it is well-formed, else None (never a partial manifest)."""
    if not isinstance(files, list) or not files:
        return None
    out = []
    for f in files:
        if not isinstance(f, dict) or not isinstance(f.get("path"), str):
            return None
        # paths may nest (models/latent.gguf); each segment must be a plain relative name
        segs = f["path"].split("/")
        if any(not _SAFE_PART.match(s) for s in segs):
            return None
        entry = {"path": f["path"]}
        if f.get("bytes"):
            entry["bytes"] = int(f["bytes"])
        out.append(entry)
    return out


def valid_files(files) -> list[dict] | None:
    """Public form: the manifest's file list when it is well-formed, else None
    (`scripts/sync_registry.py` uses this to refuse a malformed pack at the door)."""
    return _valid_files(files)


def pack_of(model: dict) -> dict | None:
    """The registry record's pack manifest payload (formats[].pack), or None.

    A record whose `pack` field is malformed is reported as no pack here so the pick treats the
    row as before-sync; the sync normaliser is the place a malformed pack is REJECTED
    (issue #2909: the registry stays the referee).
    """
    for f in model.get("formats") or []:
        raw = f.get(PACK_FIELD)
        if isinstance(raw, dict) and _valid_files(raw.get("files")):
            return raw
    return None


def manifest(model: dict) -> dict | None:
    """{repo, revision, files:[{path, bytes?}]} when the record declares a pack, else None."""
    for f in model.get("formats") or []:
        raw = f.get(PACK_FIELD)
        if isinstance(raw, dict):
            files = _valid_files(raw.get("files"))
            if files:
                return {"repo": f.get("hf") or model.get("hf") or "",
                        "revision": str(raw.get("revision") or "main"),
                        "files": files}
    return None


def manifest_bytes(man: dict) -> int:
    """Declared total bytes of a manifest (0 when the manifest declares no sizes)."""
    return sum(int(f.get("bytes") or 0) for f in man["files"])


def pack_gb(model: dict) -> float | None:
    """The pack's whole-file-set size in GB — the gating figure for a pack record, else None."""
    man = manifest(model)
    if not man:
        return None
    total = manifest_bytes(man)
    return total / 1e9 if total else None


def write_manifest(man: dict, path: Path) -> Path:
    """Write a resolved manifest where `scripts/hf_download.py`'s manifest mode reads it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(man, indent=2) + "\n")
    return path


def missing_parts(pack_dir: Path, parts: list[str]) -> list[str]:
    """Declared parts absent from the pack directory (in declared order), naming each one."""
    return [p for p in parts if not (pack_dir / p).exists()]


def launch_env(spec: dict, model: str, models_dir: Path) -> list[str]:
    """The docker `-e` wiring for a pack model (engine params `model_contract: "pack"`).

    Refuses when the model is not a local pack directory, or when a declared part is missing
    (naming it); otherwise returns `-e VAR=<container path>` pairs for every `config_env` entry
    on top of the base `LLGENIE_MODEL` the caller already passed. The container path mirrors
    `container_model()`: the host directory lives under `models_dir`, mounted at `/models`.
    """
    pack = spec.get(PACK_FIELD) or {}
    parts = [p for p in (pack.get("parts") or []) if isinstance(p, str)]
    config_env = pack.get("config_env") or {}
    if not parts or not isinstance(config_env, dict) or not config_env:
        raise SystemExit(
            f"[pack] {spec.get('id', '?')}: model_contract=pack but params declare no "
            f"pack.parts/pack.config_env (issue #2909)")
    dir_ = Path(model).expanduser()
    if not dir_.is_dir():
        raise SystemExit(f"[pack] {spec.get('id', '?')}: a pack model must be a local pack "
                         f"directory under {models_dir}: {model}")
    try:
        cont_dir = "/models/" + str(dir_.resolve().relative_to(models_dir.resolve()))
    except ValueError:
        raise SystemExit(f"[pack] {spec.get('id', '?')}: pack directory must live under "
                         f"{models_dir} (mounted at /models): {dir_}")
    missing = missing_parts(dir_, parts)
    if missing:
        raise SystemExit(f"[pack] {spec.get('id', '?')}: pack {dir_.name} is missing "
                         f"declared part(s): {', '.join(missing)} "
                         f"(fetch the pack: scripts/model_engine_pick.py download <model-id>)")
    env: list[str] = []
    for var, part in config_env.items():
        if part == ".":  # the pack directory itself
            env += ["-e", f"{var}={cont_dir}"]
        else:
            env += ["-e", f"{var}={cont_dir}/{part}"]
    return env
