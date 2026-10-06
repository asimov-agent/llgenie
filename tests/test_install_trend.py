"""After `make install`: the installed ~/bin/llgenie runs the trend pick (issue #105,
OpenSpec feat-trend-pick-default).

Run by `make test-install-trend` (part of `make test-install-ci`) after `make
install`, in the test container with the host docker socket. A real user path,
no mocks except the card size: LLAMA_RAM_BYTES=2 GiB on a cpu backend so the top
recommendation is a small GGUF.

  1. `llgenie` with no model, in a pty: the recommended list comes from the
     vendored data/models.json; the user picks model 1 and engine 1.
  2. The GGUF is downloaded from the Hub into ~/models.
  3. The engine image is pulled on first use and its container answers "hi"
     on /v1/chat/completions as llm-local.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tests"))
import engine_image as ei  # noqa: E402
import model_engine_pick as mp  # noqa: E402
from ptydrive import Pty  # noqa: E402

BIN = Path.home() / "bin"
CARD = 2 * 2**30


def _port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _chat(port: int, p: Pty, timeout: float = 1800) -> str:
    end = time.time() + timeout
    while time.time() < end:
        p._read(1)  # keep draining the pty so the engine never blocks on output
        if p.proc.poll() is not None:
            raise AssertionError(f"llgenie exited {p.proc.returncode}:\n{p.out[-4000:]}")
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/models", timeout=3) as r:  # noqa: S310
                if any(m["id"].split(":")[0] == "llm-local" for m in json.load(r).get("data") or []):
                    break
        except Exception:  # noqa: BLE001
            time.sleep(1)
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions",
        data=json.dumps({"model": "llm-local", "max_tokens": 32,
                         "messages": [{"role": "user", "content": "hi"}]}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:  # noqa: S310
        msg = json.load(r)["choices"][0]["message"]
    return (msg.get("content") or "") + (msg.get("reasoning_content") or "") + (msg.get("reasoning") or "")


def run_trend_pick(backend: str) -> tuple[dict, dict, Path, str, str]:
    """The installed ~/bin/llgenie with no model, in a pty, on a mocked 2 GB card of
    `backend` (GPU images run on CPU via LLGENIE_NO_GPU=1): pick 1, pick 1, then the
    real GGUF download and the engine container's answer to "hi"."""
    launcher = BIN / "llgenie"
    assert launcher.is_file() and os.access(launcher, os.X_OK), "~/bin/llgenie missing: run make install first"
    os.environ.pop("LLGENIE_REGISTRY_SRC", None)
    reg = mp.load_registry()
    assert reg == json.loads((REPO / "data" / "models.json").read_text())
    rows = mp.offer(reg, backend, CARD / 2**30)
    # the list is the README "Most loved" list that fits a 2 GB card, in README order
    assert [r["model"]["name"] for r in rows] == [m["name"] for m in reg["models"] if mp.fits(m, CARD / 2**30)]
    top = [r for r in rows if not r["why"]]
    assert top, f"no servable model for a 2 GB {backend} card in data/models.json"
    model, eng = top[0]["model"], top[0]["engines"][0]
    assert ei.chat_testable(eng["id"], eng["variant"]), (eng, "top 2 GB pick must run on a GPU-less runner")
    port = _port()
    env = {**os.environ, "LLAMA_BACKEND": backend, "LLAMA_RAM_BYTES": str(CARD), "LLGENIE_NO_GPU": "1"}
    env.pop("LLGENIE_REGISTRY_SRC", None)
    p = Pty([str(launcher), "--port", str(port)], env)
    try:
        p.expect(r"every model whose VRAM fits this card", 300)
        menu = p.expect(r"Pick model \[1\]: ", 300)
        listing = [line for line in p.out[: menu.end()].splitlines() if " trend " in line]
        assert [r["model"]["name"] for r in rows] == [next(r["model"]["name"] for r in rows
                                                          if r["model"]["name"] in line) for line in listing], p.out
        assert " 1.  " + model["name"] in p.out[: menu.end()], p.out
        p.send("1")
        p.expect(r"Engines for " + model["name"], 120)
        eng_menu = p.expect(r"Pick inference server \[1\]: ", 60)
        assert f"[{eng['variant']}]" in p.out[menu.end(): eng_menu.end()], p.out
        p.send("1")
        reply = _chat(port, p)
    finally:
        p.close()
        out = subprocess.run([ei.RUNTIME, "ps", "-a", "--format", "{{.Names}}"], capture_output=True, text=True).stdout
        for name in out.split():
            if name.startswith("llgenie-"):
                subprocess.run([ei.RUNTIME, "rm", "-f", name], capture_output=True)
    assert reply.strip(), p.out[-4000:]
    assert f"Engine : {eng['engine']} [{eng['variant']}]" in p.out, p.out
    local = mp.resolve_local(model)
    assert local and local.suffix == ".gguf", local
    plan = mp.plan_download(model, CARD / 2**30)
    assert local.name == plan["path"].rsplit("/", 1)[-1], (local, plan)
    assert local.stat().st_size == plan["size"], (local.stat().st_size, plan)  # complete download
    assert local.read_bytes()[:4] == b"GGUF"
    assert (BIN / ("llgenie-engine-" + eng["id"].replace(".", "-"))).exists()
    tag = ei.resolve(eng["id"], None, eng["variant"])["tag"]
    assert ei.image_exists(tag), tag
    return model, eng, local, reply, p.out


def test_installed_llgenie_trend_pick_downloads_and_answers():
    # Given make install has run on this backend (NO SKIP: missing artifacts are a failure)
    backend = os.environ.get("LLAMA_BACKEND") or "cpu"
    # When the installed llgenie runs with no model in a terminal and the user picks 1, 1
    model, eng, local, reply, _ = run_trend_pick(backend)
    # Then the full GGUF was downloaded from the Hub and the engine image answered "hi"
    print(f"[install-trend] {backend}: {model['name']} on {eng['engine']} [{eng['variant']}] "
          f"({local.name}, {local.stat().st_size / 2**30:.2f} GiB) answered {reply.strip()[:60]!r}")
