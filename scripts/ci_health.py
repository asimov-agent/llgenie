#!/usr/bin/env python3
"""Standalone CI health check (issue #84/#89).

Launches a *specific* llama-server binary (a freshly-built variant binary,
NOT the installed wrapper), loads the lightweight 0.5B Qwen test model,
polls /health, POSTs "hi", and asserts a non-empty text reply. The same script
runs on ubuntu-latest (inside the CUDA variant image) and on macos-14 (host
toolchain) so the verification code path is identical everywhere.

Usage:
  python3 scripts/ci_health.py --server-bin /path/to/llama-server
  python3 scripts/ci_health.py --server-bin /path/to/llama-server --model /path/to/model.gguf

Downloads the 0.5B Qwen health model into ~/models/Qwen/8GB if not present.
No skips — a missing prerequisite is a loud failure (per AGENTS.md).
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

MODELS_ROOT = Path.home() / "models"
HEALTH_TIER = MODELS_ROOT / "Qwen" / "8GB"
MODEL_FILE = HEALTH_TIER / "qwen2.5-0.5b-instruct-q4_0.gguf"


def _pick_port() -> int:
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _download_5b_model(hf_bin: str) -> None:
    """Download the 0.5B health model if not already present (idempotent)."""
    if MODEL_FILE.is_file() and MODEL_FILE.stat().st_size > 100_000_000:
        print(f"[ci-health] model already present: {MODEL_FILE}")
        return
    print(f"[ci-health] downloading {MODEL_FILE.parent.name}/{MODEL_FILE.name} (via {hf_bin})")
    dl = Path(__file__).parent / "hf_download.py"
    r = subprocess.run([sys.executable, str(dl),
                        "Qwen/Qwen2.5-0.5B-Instruct-GGUF",
                        MODEL_FILE.name, str(HEALTH_TIER), "qwen05b-cih"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        raise SystemExit(f"model download failed (exit {r.returncode})")
    if not MODEL_FILE.is_file():
        raise SystemExit(f"model file not created: {MODEL_FILE}")
    print(f"[ci-health] model ready: {MODEL_FILE.stat().st_size / 1e6:.0f} MB")


def _find_hf() -> str:
    """Locate the hf CLI (huggingface_hub), on PATH or in the repo venv."""
    import shutil
    hf = shutil.which("hf")
    if hf:
        return hf
    venv_hf = (Path.home() / "llama-gguf-tools" / ".venv" / "bin" / "hf")
    if venv_hf.is_file():
        return str(venv_hf)
    raise SystemExit("ERROR: 'hf' CLI not found on PATH and no repo venv hf. Set HF_BIN or install huggingface_hub[cli].")


def _wait_healthy(url: str, timeout: float = 180.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url + "/health", timeout=2) as r:
                if r.status == 200:
                    body = r.read()
                    try:
                        if json.loads(body).get("status") == "ok":
                            return True
                    except Exception:
                        pass
        except Exception:
            pass
        time.sleep(2)
    return False


def _chat(url: str, prompt: str = "hi") -> str | None:
    body = json.dumps({
        "model": "llm-local",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 32,
        "temperature": 0.0,
    }).encode()
    req = urllib.request.Request(url + "/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read())
    return data.get("choices", [{}])[0].get("message", {}).get("content")


def main() -> int:
    ap = argparse.ArgumentParser(description="CI health check for a llama-server binary")
    ap.add_argument("--server-bin", required=True, help="Path to a llama-server binary")
    ap.add_argument("--model", default=None, help="Path to a .gguf model (else downloads the 0.5B health model)")
    args = ap.parse_args()

    srv = Path(args.server_bin)
    if not srv.is_file() or not os.access(str(srv), os.X_OK):
        raise SystemExit(f"ERROR: server binary not found/not executable: {srv}")
    # Verify --version + --help (exit 0) before launching (the binary sanity
    # check that the issue requires for every variant).
    vproc = subprocess.run([str(srv), "--version"], capture_output=True, text=True)
    if vproc.returncode != 0:
        print(f"[ci-health] --version failed: {vproc.stderr}", file=sys.stderr)
        raise SystemExit("ERROR: binary --version exited non-zero")
    print("[ci-health] --version:", vproc.stdout.strip().splitlines()[0].splitlines()[-1] if vproc.stdout else "")
    hproc = subprocess.run([str(srv), "--help"], capture_output=True, text=True)
    if hproc.returncode != 0:
        raise SystemExit("ERROR: binary --help exited non-zero")
    print("[ci-health] --help OK")

    # Resolve the model: explicit, or the default 0.5B health model (download if absent).
    if args.model:
        model = Path(args.model)
        if not model.is_file():
            raise SystemExit(f"ERROR: model not found: {model}")
    else:
        hf_bin = os.environ.get("HF_BIN") or _find_hf()
        _download_5b_model(hf_bin)
        model = MODEL_FILE

    port = _pick_port()
    url = f"http://127.0.0.1:{port}"
    proc = subprocess.Popen(
        [str(srv), "--alias", "llm-local", "-m", str(model), "--port", str(port),
         "--ctx-size", "2048"],
        cwd="/tmp", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        if not _wait_healthy(url):
            out = proc.stdout.read()[-2000:] if proc.stdout else ""
            raise SystemExit(f"ERROR: server never healthy on :{port}\nlast output:\n{out}")
        print(f"[ci-health] /health OK on :{port}")
        reply = _chat(url, "hi")
        if not reply or not reply.strip():
            raise SystemExit("ERROR: /v1/chat/completions returned empty reply for 'hi'")
        print(f"[ci-health] model replied to 'hi': {reply.strip()[:120]}")
        print("[ci-health] ASSERT OK: non-empty text returned")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
            proc.wait(timeout=5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
