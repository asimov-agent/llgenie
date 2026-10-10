"""`make install` for EACH native-Metal engine, in its own environment (issue #120).

On an Apple-Silicon Mac the servable engines with a `metal` backend and a metal install
(`model_engine_pick.metal_engines()`: litert, llama.cpp, llama.cpp-prism, mlx, ollama,
tensorfold; issue #114: Metal cannot run in a container) are the macOS engine matrix.
llama.cpp and llama.cpp-prism are BUILT natively (cmake -DGGML_METAL=ON) by their skill. For each one this test runs the same path `make install` / the llgenie pick runs:

  install : `install_engine_launchers.py --ensure <id> --arch metal` installs it with
            its skill at the pinned version and writes ~/bin/llgenie-engine-<id>
  version : `llgenie-engine-<id> --version` prints the pinned version
  serve   : the start script serves a tiny model of the engine's format on Metal as
            llm-local and it answers "hi" on /v1/chat/completions
            (tensorfold's smallest servable checkpoint is 5.5 GiB: its Metal serve, or
            its own budget refusal on a 7 GB runner, is `make test-native-engine-light`)

Runs through `make test-native-engines` (`make ci-engines BACKEND=metal`) on an
Apple-Silicon host (no CI job: the macOS runners have no Metal GPU). A non-Apple-Silicon host FAILS loudly: there is no skip.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import engine_skills as es  # noqa: E402
import model_engine_pick as mp  # noqa: E402

INST = REPO / "scripts" / "install_engine_launchers.py"
NATIVE = sorted(mp.metal_engines())
_GGUF = ("Qwen/Qwen2.5-0.5B-Instruct-GGUF", "qwen2.5-0.5b-instruct-q4_0.gguf")
# tiny model per engine format: (hf repo, file or None for the whole repo)
TINY = {
    "mlx": ("mlx-community/Qwen2.5-0.5B-Instruct-4bit", None),
    "ollama": _GGUF,
    "llama.cpp": _GGUF,
    "llama.cpp-prism": _GGUF,
    "litert": ("litert-community/Qwen3-0.6B", "Qwen3-0.6B.litertlm"),
}
SERVED_ELSEWHERE = {"tensorfold": "make test-native-engine-light"}
PORTS = {e: 18300 + i for i, e in enumerate(NATIVE)}


def _env() -> dict:
    env = {**os.environ, "LLAMA_BACKEND": "metal"}
    env["PATH"] = f"{Path.home() / '.local' / 'bin'}{os.pathsep}{env['PATH']}"
    for k in ("PYTHONPATH", "VIRTUAL_ENV"):
        env.pop(k, None)
    return env


def _hf() -> str:
    hf = shutil.which("hf") or str(Path(sys.executable).parent / "hf")
    assert Path(hf).exists(), "the hf CLI is required (huggingface_hub[cli], in the gguf venv)"
    return hf


def _download(tmp: Path, engine: str) -> Path:
    repo, fname = TINY[engine]
    dest = tmp / repo.replace("/", "__")
    cmd = [_hf(), "download", repo, *([fname] if fname else []), "--local-dir", str(dest)]
    d = subprocess.run(cmd, env=_env(), capture_output=True, text=True, timeout=3600)
    assert d.returncode == 0, d.stderr[-2000:]
    return dest / fname if fname else dest


def _chat(port: int) -> str:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions", headers={"Content-Type": "application/json"},
        data=json.dumps({"model": "llm-local", "messages": [{"role": "user", "content": "hi"}],
                         "max_tokens": 24}).encode())
    return json.load(urllib.request.urlopen(req, timeout=300))["choices"][0]["message"]["content"]


def test_the_native_engine_matrix_is_every_metal_skill():
    """The macOS engine matrix is every servable skill with a metal backend + install
    (llama.cpp and prism included), and each one is served here or by the named make
    target (none is left out)."""

    # Given the engine skills
    skills = es.load_skills()

    # When the native-Metal set is read
    native = sorted(k for k, v in skills.items() if v.get("servable") is True
                    and "metal" in (v.get("backends") or []) and es._per_backend(v.get("install"), "metal"))

    # Then it is non-empty, includes the llama.cpp builds, and every engine has a serve proof
    assert native and native == NATIVE and {"llama.cpp", "llama.cpp-prism"} <= set(native)
    assert set(native) == set(TINY) | set(SERVED_ELSEWHERE), native


@pytest.mark.parametrize("engine", NATIVE)
def test_each_native_engine_installs_and_answers_hi_on_metal(engine, tmp_path):
    """make install for this native engine in its own environment: installed at its pin,
    version printed, a tiny model served on Metal answers "hi"."""

    # Given an Apple-Silicon host
    assert platform.system() == "Darwin" and platform.machine() == "arm64", (
        f"native Metal engines need an Apple-Silicon Mac (this is {platform.system()} {platform.machine()}); "
        "run `make ci-engines BACKEND=metal` there")
    assert shutil.which("uv"), "uv is required (brew install uv)"
    env, bindir = _env(), tmp_path / "bin"

    # When the engine is installed the way make install / the llgenie pick installs it
    r = subprocess.run([sys.executable, str(INST), "--bin", str(bindir), "--ensure", engine, "--arch", "metal"],
                       env=env, capture_output=True, text=True, timeout=3600)

    # Then its start script exists and prints its version (the skill's pinned release;
    # a branch-tracking build such as llama.cpp prints its build number)
    assert r.returncode == 0, r.stdout + r.stderr
    start = bindir / f"llgenie-engine-{engine.replace('.', '-')}"
    v = subprocess.run([str(start), "--version"], env=env, capture_output=True, text=True, timeout=300)
    pinned = es.pinned_version(es.get_skill(engine))
    assert v.returncode == 0 and (v.stdout + v.stderr).strip(), (v.stdout, v.stderr)
    assert pinned is None or pinned in v.stdout + v.stderr, (pinned, v.stdout, v.stderr)
    pinned = pinned or (v.stdout + v.stderr).strip().splitlines()[-1]

    if engine in SERVED_ELSEWHERE:
        print(f"[native] {engine} {pinned} installed; Metal serve: {SERVED_ELSEWHERE[engine]}")
        return

    # And the start script serves a tiny model on Metal that answers "hi"
    model, port = _download(tmp_path, engine), PORTS[engine]
    log = open(tmp_path / "serve.log", "w")
    proc = subprocess.Popen([str(start), str(model), str(port)], env=env, stdout=log, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, start_new_session=True)
    try:
        deadline, reply = time.time() + 900, ""
        while time.time() < deadline and proc.poll() is None and not reply.strip():
            try:
                reply = _chat(port)
            except (OSError, KeyError, ValueError):
                time.sleep(3)
        text = (tmp_path / "serve.log").read_text()
        assert reply.strip(), f"{engine} never answered on :{port}:\n{text[-3000:]}"
        print(f"[native] {engine} {pinned} served {model.name} on Metal: {reply!r}")
    finally:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(60)
