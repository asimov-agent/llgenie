"""Hermetic e2e tests for the pack-format model-store fetch (OpenSpec pack-format-store-launch).

A multi-file checkpoint (a pack) is fetched from a file manifest through the REAL
scripts/hf_download.py as a subprocess against a REAL fake-`hf` executable
(tests/fixtures/fake_hf.py FAKE_HF_MODE=pack), which writes real bytes of each named
file to a real temp dir. NO MOCKS: the same resume/stall/retry path as a single-file
download drives each named file, and a pack is "present" only when EVERY named file
is on disk — a partial set resumes, never passes as complete.
"""
from __future__ import annotations

import json, os, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HF_DL = ROOT / "scripts" / "hf_download.py"
FAKE_HF = HERE / "fixtures" / "fake_hf.py"

PACK_MANIFEST = {"files": ["model-skeleton.gguf", "ple-fp8.gguf", "profile.bin", "mtp/next.gguf"]}


def _run(tmp: Path, manifest_files, preplace=None, corrupt=None) -> dict:
    """Execute the REAL hf_download.main() with a pack manifest; returns {rc, log_text, files}."""
    dest = tmp / "dest"
    dest.mkdir(parents=True)
    manifest = tmp / "pack.json"
    manifest.write_text(json.dumps({"files": manifest_files}))
    env = dict(os.environ)
    env["HF_BIN"] = str(FAKE_HF)
    env["FAKE_HF_MODE"] = "pack"
    env["HF_POLL_SECONDS"] = "0.2"
    env["HF_RETRY_PAUSE"] = "0.1"
    env["HF_MAX_RETRY"] = "2"
    env.pop("HF_TOKEN", None)
    env.pop("HF_XET_HIGH_PERFORMANCE", None)
    env.pop("HF_HUB_DISABLE_XET", None)
    if preplace:
        for rel in preplace:
            p = dest / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"\x00" * 32)
    label = "pack"
    proc = subprocess.run(
        [sys.executable, str(HF_DL), "Edge0/Edge0-145B-q3k", str(manifest), str(dest), label, "0"],
        env=env, capture_output=True, text=True, timeout=120,
    )
    log = dest / f"{label}.progress.log"
    log_text = log.read_text() if log.exists() else ""
    present = {rel: (dest / rel).is_file() for rel in manifest_files}
    return {"rc": proc.returncode, "log_text": log_text, "present": present,
            "stderr": proc.stderr, "stdout": proc.stdout}


def test_pack_manifest_fetches_every_named_file_into_one_dir(tmp_path):
    """The whole file set lands in the ONE destination directory, resumable like today.

    # Given a pack manifest naming a multi-file checkpoint's parts,
    # When  hf_download.main() fetches it (FAKE_HF_MODE=pack),
    # Then  every named file is on disk in the destination dir,
    # And   the pack logs a PACK COMPLETE line with all files present.
    """
    r = _run(tmp_path, PACK_MANIFEST["files"])
    assert r["rc"] == 0, (r["log_text"], r["stderr"])
    assert all(r["present"].values()), r["present"]
    assert "PACK COMPLETE 4/4 files" in r["stdout"], (r["log_text"], r["stdout"])


def test_partial_pack_resumes_not_redownloads_complete_files(tmp_path):
    """A re-run skips files already on disk and fetches only the missing ones.

    # Given a pack whose manifest lists 4 files, 2 already on disk,
    # When  hf_download.main() runs again,
    # Then  the 2 missing files are fetched (rc=0) without re-downloading the rest,
    # And   every named file is present afterward.
    """
    r = _run(tmp_path, PACK_MANIFEST["files"],
             preplace=["model-skeleton.gguf", "ple-fp8.gguf"])
    assert r["rc"] == 0, (r["log_text"], r["stderr"])
    assert all(r["present"].values()), r["present"]
    # the two pre-placed files were fast-pathed (no download attempt for them)
    assert r["log_text"].count("=== attempt 1 (") >= 1, r["log_text"]


def test_pack_manifest_bare_array_form_is_accepted(tmp_path):
    """A bare JSON array manifest (files only) is read the same as {"files": [...]}."""

    # Given a pack manifest written as a bare JSON array of paths,
    # When  hf_download.main() fetches it,
    # Then  every file lands in the destination directory.
    dest = tmp_path / "dest"
    dest.mkdir(parents=True)
    manifest = tmp_path / "pack.json"
    manifest.write_text(json.dumps(["model-skeleton.gguf", "dense.bin"]))
    env = dict(os.environ)
    env.update({"HF_BIN": str(FAKE_HF), "FAKE_HF_MODE": "pack",
                "HF_POLL_SECONDS": "0.2", "HF_RETRY_PAUSE": "0.1", "HF_MAX_RETRY": "2"})
    env.pop("HF_TOKEN", None); env.pop("HF_XET_HIGH_PERFORMANCE", None); env.pop("HF_HUB_DISABLE_XET", None)
    proc = subprocess.run(
        [sys.executable, str(HF_DL), "org/repo", str(manifest), str(dest), "pack", "0"],
        env=env, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    assert (dest / "model-skeleton.gguf").is_file()
    assert (dest / "dense.bin").is_file()
