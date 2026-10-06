#!/usr/bin/env python3
"""Engine smoke test: install an engine through its skill, serve a tiny model
with the skill's own launch line, and assert the llm-local contract.

This is what the CI `engine-smoke` matrix runs (one job per engine x backend
a hosted runner can execute). Nothing here is engine-specific: install steps,
env, pre/post-launch, launch and health all come from the SKILL.md. Only the
tiny test model per model format is chosen here.

  python3 scripts/engine_smoke.py <engine-id> [--backend cpu|metal|...] [--port N]

Exit 0 = installed, /v1/models lists llm-local, and a chat completion with
model=llm-local returned text. Any failure exits non-zero (never a skip).
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine_skills as es  # noqa: E402

# Tiny, ungated test models per format (pulled with the hf CLI).
TEST_MODELS = {
    "gguf": ("Qwen/Qwen2.5-0.5B-Instruct-GGUF", "qwen2.5-0.5b-instruct-q4_0.gguf"),
    "safetensors": ("Qwen/Qwen2.5-0.5B-Instruct", None),
    "mlx-safetensors": ("mlx-community/Qwen2.5-0.5B-Instruct-4bit", None),
    # MLX's CPU backend takes minutes per token on 4-bit quantized matmul, but
    # bf16 answers in seconds: the cpu image smoke uses the bf16 build (#98)
    "mlx-safetensors-cpu": ("mlx-community/Qwen2.5-0.5B-Instruct-bf16", None),
    "litertlm": ("litert-community/Qwen3-0.6B", "Qwen3-0.6B.litertlm"),
}
MODELS_DIR = Path(os.environ.get("LLGENIE_SMOKE_MODELS", Path.home() / "models" / "smoke"))


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def fetch_model(fmt: str) -> str:
    """Download the tiny model for `fmt` with the hf CLI; return file or dir."""
    repo, filename = TEST_MODELS[fmt]
    dest = MODELS_DIR / repo.replace("/", "__")
    hf = os.environ.get("HF_BIN") or "hf"
    cmd = [hf, "download", repo, "--local-dir", str(dest)]
    if filename:
        cmd.insert(3, filename)
    print("[smoke] $", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)
    return str(dest / filename) if filename else str(dest)


def pick_format(skill: dict) -> str:
    for fmt in skill.get("formats") or []:
        if fmt in TEST_MODELS:
            return fmt
    raise SystemExit(f"[smoke] FAIL {skill['id']}: no tiny test model for formats {skill.get('formats')}")


def bash(cmd: str, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", "-euo", "pipefail", "-c", cmd], **kw)


def http(url: str, body: dict | None = None, timeout: float = 5) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (loopback)
        return json.load(r)


def wait_ready(port: int, health: str, proc: subprocess.Popen, timeout: float) -> bool:
    path = str(health or "GET /v1/models").split()[-1]
    end = time.time() + timeout
    while time.time() < end:
        if proc.poll() is not None:
            return False
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=3)  # noqa: S310
            return True
        except Exception:
            time.sleep(2)
    return False
def harness_sdk_check(port: int, engine: str = "", arch: str = "cpu", container: bool = True) -> int:
    """Run tests/test_engine_runs.py (OpenAI SDK: GET /v1/models lists llm-local,
    a chat completion answers) against the served endpoint.

    container=True (Linux images): pytest runs in llgenie/test:latest with
    --network host, so the test tools come from the test image.
    container=False (native macOS Metal, no docker): the same pytest file runs
    with uv and the openai version pinned in tools/requirements-dev.txt."""
    root = Path(__file__).resolve().parent.parent
    alias_mode = (es.get_skill(engine).get("alias_mode") or "") if engine else ""
    env_vars = {"LLGENIE_TEST_ENGINE": engine, "LLGENIE_TEST_ARCH": arch,
                "LLGENIE_TEST_ALIAS_MODE": alias_mode,
                "OPENAI_BASE_URL": f"http://127.0.0.1:{port}/v1"}
    if container:
        import engine_image as ei
        cmd = [ei.RUNTIME, "run", "--rm", "--network", "host", "-v", f"{root}:/repo:rw", "-w", "/repo"]
        for k, v in env_vars.items():
            cmd += ["-e", f"{k}={v}"]
        cmd += ["llgenie/test:latest", "python3", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                "tests/test_engine_runs.py"]
        env = None
    else:
        # same locked deps as the test image (tests/conftest.py needs gguf/numpy too)
        cmd = ["uv", "run", "--no-project", "--quiet", "--python", "3.10",
               "--with-requirements", str(root / "tools" / "requirements.txt"),
               "--with-requirements", str(root / "tools" / "requirements-dev.txt"),
               "python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_engine_runs.py"]
        env = {**os.environ, **env_vars}
    r = subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True)
    print(r.stdout, end="")
    if r.returncode:
        print(r.stderr[-2000:])
    return r.returncode

def image_smoke(skill_id: str, backend: str | None, port: int, timeout: float,
                variant: str | None = None, no_gpu: bool = False) -> int:
    """Build the engine image (no-op if tagged), run it, assert the contract on
    the PUBLISHED host port (what an external AI harness sees)."""
    import engine_image as ei
    skill = es.get_skill(skill_id)
    spec = ei.resolve(skill_id, backend, variant)
    if no_gpu:
        # GPU image on a GPU-less runner: started without GPU devices, the
        # engine must fall back to CPU and still answer on its OpenAI endpoint
        spec = {**spec, "run_args": list(es.SHM)}
    rc = ei.build(spec)
    if rc:
        return rc
    fmt = pick_format(skill)
    if f"{fmt}-{spec['backend']}" in TEST_MODELS:
        fmt = f"{fmt}-{spec['backend']}"
    model = fetch_model(fmt)
    models_dir = MODELS_DIR.parent if MODELS_DIR.name == "smoke" else MODELS_DIR
    name = f"llgenie-smoke-{spec['id'].replace('.', '-')}-{spec['backend']}"
    try:
        rc = ei.run(spec, model, port, name, models_dir, timeout)
        if rc:
            return rc
        rc = harness_sdk_check(port, engine=spec["id"], arch=spec["variant"])
        if rc == 0:
            print(f"[smoke] OK image {spec['tag']}: http://127.0.0.1:{port}/v1 model=llm-local (OpenAI SDK)")
        else:
            print(f"[smoke] FAIL image {spec['tag']}: OpenAI-SDK conformance exited {rc}")
        return rc
    finally:
        subprocess.run([ei.RUNTIME, "logs", "--tail", "20", name])
        subprocess.run([ei.RUNTIME, "rm", "-f", name], capture_output=True)


def smoke(skill_id: str, backend: str | None, port: int, timeout: float) -> int:
    skill = es.get_skill(skill_id)
    hw = es.detect_hardware()
    backend = es.pick_backend(skill, hw, backend)
    hw = {**hw, "backend": backend}

    rc = es.install(skill, backend, hw)
    if rc:
        print(f"[smoke] FAIL {skill_id}/{backend}: install exited {rc}")
        return rc

    model = fetch_model(pick_format(skill))
    p = es.plan(skill, backend, hw, extra={"port": port})
    prelude = p["env_prelude"]

    def render(cmd):
        return cmd.replace("{model}", model) if cmd else cmd

    if p["pre_launch"]:
        bash(prelude + render(p["pre_launch"]), check=True)
    launch = prelude + render(p["launch"])
    print(f"[smoke] launch: {launch}", flush=True)
    log = open(f"/tmp/llgenie-smoke-{skill_id}.log", "w")
    proc = subprocess.Popen(["bash", "-c", launch], stdout=log, stderr=subprocess.STDOUT,
                            start_new_session=True)
    try:
        if not wait_ready(port, p["health"], proc, timeout):
            print(f"[smoke] FAIL {skill_id}/{backend}: server not ready in {timeout:.0f}s")
            print(Path(log.name).read_text()[-4000:])
            return 1
        if p["post_launch"]:
            bash(prelude + render(p["post_launch"]), check=True)
        rc = harness_sdk_check(port, engine=skill_id, arch=backend, container=False)
        if rc == 0:
            print(f"[smoke] OK {skill_id}/{backend}: installed via skill, served llm-local, answered (OpenAI SDK)")
        else:
            print(f"[smoke] FAIL {skill_id}/{backend}: OpenAI-SDK conformance exited {rc}")
        return rc
    finally:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(30)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("engine")
    ap.add_argument("--backend", choices=es.BACKENDS, default=None)
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--timeout", type=float, default=600)
    ap.add_argument("--image", action="store_true", help="build + run the engine container image")
    ap.add_argument("--variant", default=None, help="image variant from the frozen params (with --image)")
    ap.add_argument("--no-gpu", action="store_true", help="run the image without GPU devices (with --image)")
    a = ap.parse_args(argv)
    if a.image:
        return image_smoke(a.engine, a.backend, a.port or free_port(), a.timeout, a.variant, a.no_gpu)
    return smoke(a.engine, a.backend, a.port or free_port(), a.timeout)


if __name__ == "__main__":
    sys.exit(main())
