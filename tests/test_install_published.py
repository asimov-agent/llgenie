"""After CI published the engine images: the real `make install` path on a clean
runner, per mocked backend (issue #98 / #102, OpenSpec feat-engine-skills).

Run by `make test-install-published BACKEND=<cpu|cuda|rocm|vulkan>` inside the test
image with the host docker socket. LLAMA_BACKEND mocks the hardware; the GPU
images run with LLGENIE_NO_GPU=1 (CPU fallback, hosted runners have no GPU).

  1. `make install` pulls ONLY this backend's published images (no build), for
     the llama.cpp core: llama-server + prism-server shims, version-tested.
  2. llgenie serves the 0.5B model through the shim of each tree (LLAMA_SERVER_TREE)
     and answers "hi" from the right container.
  3. `llgenie --pick --engine <e> --model-file <m>` pulls the picked engine's image
     for this backend on first use and its container answers "hi".
  4. `make uninstall` removes every installed file and container.
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

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import engine_image as ei  # noqa: E402
import install_engine_launchers as il  # noqa: E402

BACKEND = os.environ.get("LLAMA_BACKEND", "")
BIN = Path.home() / "bin"
GGUF = Path.home() / "models/Qwen/8GB/qwen2.5-0.5b-instruct-q4_0.gguf"  # scripts/download_test_model.py


def _port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _make(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["make", *args], cwd=REPO, env={**os.environ, **(env or {})},
                          capture_output=True, text=True, timeout=3600)


def _chat(port: int, timeout: float = 600) -> str:
    # ready = /v1/models lists llm-local (ollama answers /v1/models before
    # `ollama create llm-local` finished), exactly what a harness waits for
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/models", timeout=3) as r:  # noqa: S310
                if any(m["id"].split(":")[0] == "llm-local" for m in json.load(r).get("data") or []):
                    break
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions",
        data=json.dumps({"model": "llm-local", "max_tokens": 12,
                         "messages": [{"role": "user", "content": "hi"}]}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:  # noqa: S310
        return json.load(r)["choices"][0]["message"]["content"]


def _running(prefix: str) -> list[str]:
    out = subprocess.run([ei.RUNTIME, "ps", "--format", "{{.Names}} {{.Image}}"],
                         capture_output=True, text=True).stdout
    return [line for line in out.splitlines() if line.startswith(prefix)]


def _serve(argv: list[str], port: int, name_prefix: str, env: dict) -> tuple[str, list[str]]:
    proc = subprocess.Popen(argv, cwd=REPO, env={**os.environ, **env},
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        reply = _chat(port)
        return reply, _running(name_prefix)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
        for line in _running("llgenie-"):
            subprocess.run([ei.RUNTIME, "rm", "-f", line.split()[0]], capture_output=True)


def test_make_install_pulls_this_backends_published_images_and_they_answer():
    # NO SKIP: a missing prerequisite is a loud failure
    assert BACKEND in ("cpu", "cuda", "rocm", "vulkan"), \
        "LLAMA_BACKEND unset: run through `make test-install-published BACKEND=cpu|cuda|rocm|vulkan`"
    assert ei.REGISTRY, "LLGENIE_REGISTRY must point at the published images"
    assert GGUF.exists(), f"test model missing: {GGUF} (make test-install-published downloads it)"
    import shutil
    shutil.rmtree(BIN, ignore_errors=True)  # clean runner: nothing installed yet
    for engine in ("llama.cpp", "llama.cpp-prism", "ollama"):  # nothing local: install must pull
        v = il.variant_for(engine, BACKEND)
        subprocess.run([ei.RUNTIME, "rmi", "-f", ei.resolve(engine, None, v)["tag"]], capture_output=True)

    # 1. make install: only this backend's images, pulled, version-tested
    r = _make("install", f"ARCH={BACKEND}", env={"LLGENIE_NO_GPU": "1"})
    assert r.returncode == 0, r.stdout[-4000:] + r.stderr[-2000:]
    assert "(pull published images only)" in r.stdout
    assert "[engine-image] built" not in r.stdout
    for engine, shim in (("llama.cpp", "llama-server"), ("llama.cpp-prism", "prism-server")):
        v = il.variant_for(engine, BACKEND)  # cpu when this backend's image is disabled (#103)
        tag = ei.resolve(engine, None, v)["tag"]
        assert v in (BACKEND, "cpu") and tag.endswith(f"-{v}") and ei.image_exists(tag), tag
        assert tag in (BIN / shim).read_text()
        assert tag in (BIN / il.script_name(engine)).read_text()
    assert sorted(p.name for p in BIN.glob("llgenie-engine-*")) == [
        "llgenie-engine-llama-cpp", "llgenie-engine-llama-cpp-prism"]

    # 2. llgenie -> the tree's shim -> that image's container answers
    for tree, shim, engine in (("upstream", "llama-server", "llama.cpp"), ("prism", "prism-server", "llama.cpp-prism")):
        port = _port()
        reply, running = _serve([str(BIN / "llgenie"), "qwen2.5-0.5b", "--port", str(port)], port,
                                f"llgenie-{shim}-{port}",
                                {"LLAMA_SERVER_TREE": tree, "LLGENIE_NO_GPU": "1", "LLAMA_BACKEND": BACKEND})
        assert reply.strip(), (tree, reply)
        tag = ei.resolve(engine, None, il.variant_for(engine, BACKEND))["tag"]
        assert running and tag in running[0], (tree, running)
        print(f"[install-published] {BACKEND} {tree}: {shim} ({tag}) answered {reply.strip()!r}")

    # 3. llgenie --pick --engine: the picked engine is pulled for this backend on first use
    pick = {"cpu": "ollama", "cuda": "ollama", "rocm": "ollama", "vulkan": "ollama"}[BACKEND]
    port = _port()
    reg = REPO / "tests" / "fixtures" / "trending-models.json"
    reply, running = _serve([str(BIN / "llgenie"), "--pick", "--auto", "--engine", pick,
                             "--model-file", str(GGUF), "--port", str(port)], port, "llgenie-ollama-",
                            {"LLGENIE_NO_GPU": "1", "LLAMA_BACKEND": BACKEND, "LLGENIE_REGISTRY_SRC": str(reg),
                             "LLAMA_RAM_BYTES": str(64 * 2**30)})
    tag = ei.resolve(pick, None, il.variant_for(pick, BACKEND))["tag"]
    assert reply.strip() and running and tag in running[0], (reply, running)
    assert (BIN / il.script_name(pick)).exists()
    print(f"[install-published] {BACKEND} --pick --engine {pick}: {tag} answered {reply.strip()!r}")

    # 3b. issue #105: the installed llgenie with no model is the interactive trend pick
    #     from the vendored data/models.json for this backend: pty, pick 1/1, the
    #     full GGUF is downloaded and this backend's engine image answers "hi"
    sys.path.insert(0, str(REPO / "tests"))
    from test_install_trend import run_trend_pick
    model, eng, local, reply, _ = run_trend_pick(BACKEND)
    assert eng["variant"] in (BACKEND, "cpu")
    print(f"[install-published] {BACKEND} trend pick: {model['name']} -> {eng['engine']} [{eng['variant']}] "
          f"({local.name}) answered {reply.strip()[:60]!r}")

    # 4. make uninstall leaves nothing behind
    r = _make("uninstall")
    assert r.returncode == 0, r.stdout[-2000:]
    assert not list(BIN.glob("llgenie-engine-*"))
    assert not (BIN / "llama-server").exists() and not (BIN / "prism-server").exists()
    assert not _running("llgenie-")


def test_first_use_pull_works_without_llgenie_registry_live(tmp_path):
    """Live GHCR, no mocks: the first-use install llgenie runs for a picked engine
    (install_engine_launchers.py --ensure) with no LLGENIE_REGISTRY in the environment
    pulls the published llama.cpp cpu image and writes its start script."""
    tag = ei.resolve("llama.cpp", None, "cpu")["tag"]
    subprocess.run([ei.RUNTIME, "rmi", "-f", tag], capture_output=True)   # force a real pull
    env = {k: v for k, v in os.environ.items() if k != "LLGENIE_REGISTRY"}
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "install_engine_launchers.py"),
                        "--bin", str(tmp_path), "--ensure", "llama.cpp", "--arch", "cpu"],
                       env=env, capture_output=True, text=True, timeout=1800)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    assert "no LLGENIE_REGISTRY" not in r.stdout
    assert f"pull ghcr.io/asimov-agent/{tag}" in r.stdout
    assert tag in (tmp_path / "llgenie-engine-llama-cpp").read_text() and ei.image_exists(tag)
