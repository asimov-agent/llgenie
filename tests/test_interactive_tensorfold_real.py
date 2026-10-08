"""REAL interactive llgenie on an Apple-Silicon Mac (issue #114): the user's exact path.

Plain `llgenie` in a pseudo-terminal, no flags that bypass the prompts:

  1. the trend list (README order, filtered to what fits this Mac) is printed and
     `Pick model [1]:` asks;            -> the test finds Qwen3.8-27B's number IN the
                                           printed list and types it
  2. the engine list for that model is printed and `Pick inference server [1]:`
     asks;                              -> the test finds TensorFold's number IN the
                                           printed list and types it
  3. llgenie downloads the TensorFold checkpoint when missing, installs / updates /
     reuses TensorFold at the skill's pinned release, serves on Metal
                                        -> the test chats "hi" on /v1/chat/completions

TensorFold is removed first (isolated uv tool dir), so step 3 really installs it.
The model checkpoint uses the real ~/models (the 21 GB download is done once; then it
is `[local]`). Driven by `make test-interactive-tensorfold` on the Apple-Silicon host.
A non-Apple-Silicon host FAILS loudly: there is no skip."""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tests"))
import engine_skills as es  # noqa: E402
from ptydrive import Pty  # noqa: E402

SERVE = REPO / "scripts" / "llama_serve.py"
PINNED = es.pinned_version(es.get_skill("tensorfold"))
MODEL = "Qwen3.8-27B"
ENGINE = "TensorFold"
PORT = int(os.environ.get("LLGENIE_TEST_PORT", "18193"))
LAUNCHER = os.environ.get("LLGENIE_LAUNCHER") or str(SERVE)   # ~/bin/llgenie after make install
# LLGENIE_NO_SERVE=1 (the macOS CI runner: no 15-21 GB checkpoint, slow): the SAME two
# interactive picks with --dry, then llgenie's own ensure step installs TensorFold for
# real; only the Metal serve + "hi" is skipped by design of the run, never by a skip.
NO_SERVE = os.environ.get("LLGENIE_NO_SERVE") == "1"
ROW = re.compile(r"^\s+(\d+)\.\s{2}(.+?)\s+(?:trending|recent|stale)\s+trend", re.M)
ENGINE_ROW = re.compile(r"^\s+(\d+)\.\s+(.+?)\s+\[(\w+)\]", re.M)


def _number_of(rows: list[tuple[str, str]], name: str) -> str:
    hits = [n for n, label in rows if label.strip() == name or label.strip().startswith(name + " ")]
    assert hits, f"{name!r} is not pickable in the printed list: {rows}"
    return hits[0]


def _chat(port: int) -> str:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions", headers={"Content-Type": "application/json"},
        data=json.dumps({"model": "llm-local", "messages": [{"role": "user", "content": "hi"}],
                         "max_tokens": 24, "chat_template_kwargs": {"enable_thinking": False}}).encode())
    return json.load(urllib.request.urlopen(req, timeout=300))["choices"][0]["message"]["content"]


def _ready(port: int) -> bool:
    try:
        data = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/models", timeout=5))["data"]
        return any(m["id"] == "llm-local" for m in data)
    except OSError:
        return False


def test_interactive_llgenie_picks_qwen38_27b_then_tensorfold_and_serves_on_metal(tmp_path):
    """Plain `llgenie`: pick Qwen3.8-27B from the trend list, then TensorFold from its
    engine list; TensorFold is installed by the pick and answers "hi" on Metal."""

    # Given an Apple-Silicon Mac where TensorFold is NOT installed (isolated uv tool dir)
    assert platform.system() == "Darwin" and platform.machine() == "arm64", \
        f"needs an Apple-Silicon Mac (this is {platform.system()} {platform.machine()})"
    assert shutil.which("uv"), "uv is required"
    tools, tbin = tmp_path / "uv-tools", tmp_path / "uv-bin"
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "VIRTUAL_ENV"))}
    env.update({"UV_TOOL_DIR": str(tools), "UV_TOOL_BIN_DIR": str(tbin), "TERM": "xterm",
                "PATH": f"{tbin}{os.pathsep}{env['PATH']}"})
    env.pop("LLGENIE_REGISTRY_SRC", None)
    if NO_SERVE:  # a CI runner (7 GB) does not list a 16 GB-tier model: emulate the reporter's 48 GB Mac
        env.setdefault("LLAMA_RAM_BYTES", str(48 * 2**30))
        env.setdefault("LLGENIE_SYSTEM_RAM_BYTES", str(48 * 2**30))
    py = [] if LAUNCHER != str(SERVE) else [sys.executable]

    # When the user runs plain `llgenie` and answers the two prompts from the printed lists
    p = Pty([*py, LAUNCHER, "--port", str(PORT), *(["--dry"] if NO_SERVE else [])], env, cwd=str(Path.home()))
    try:
        p.expect(r"Pick model \[1\]: ", 600)
        header = re.search(r"this card \((\d+) GB, (\w+)\)", p.out)
        models = [(m.group(1), m.group(2)) for m in ROW.finditer(p.out)]
        n_model = _number_of(models, MODEL)
        p.send(n_model)

        p.expect(r"Pick inference server \[1\]: ", 600)
        menu = p.out.split(f"Engines for {MODEL}", 1)[1]
        engines = [(m.group(1), m.group(2), m.group(3)) for m in ENGINE_ROW.finditer(menu)]
        tf = [e for e in engines if e[1].strip() == ENGINE]
        assert tf, f"{ENGINE} is not in the engine list of {MODEL}: {engines}"
        n_engine, _, variant = tf[0]
        tf_line = next(ln for ln in menu.splitlines() if re.match(rf"\s+{n_engine}\.\s+{ENGINE}\b", ln))
        p.send(n_engine)

        if NO_SERVE:
            assert p.wait(600) == 0, p.out[-4000:]
            # the pick's own ensure step (what llgenie runs after the plan), for real
            inst = subprocess.run([sys.executable, str(REPO / "scripts" / "install_engine_launchers.py"),
                                   "--bin", str(tmp_path / "bin"), "--ensure", "tensorfold", "--arch", "metal"],
                                  env=env, capture_output=True, text=True, timeout=1800)
            p.out += inst.stdout + inst.stderr
            assert inst.returncode == 0, inst.stdout + inst.stderr
            ver = subprocess.run([str(tmp_path / "bin" / "llgenie-engine-tensorfold"), "--version"],
                                 env=env, capture_output=True, text=True, timeout=120)
            reply = ver.stdout.strip().splitlines()[-1] if ver.stdout.strip() else ""
            assert ver.returncode == 0, ver.stdout + ver.stderr
        else:
            deadline = time.time() + 3600
            while time.time() < deadline and not _ready(PORT):
                assert p.proc.poll() is None, f"llgenie exited {p.proc.returncode}:\n{p.out[-4000:]}"
                p._read(5)
            assert _ready(PORT), f"TensorFold never served llm-local:\n{p.out[-4000:]}"
            reply = _chat(PORT)
        steps = [ln for ln in p.out.splitlines() if "[install]" in ln or "[engine-skills]" in ln]
        print("\n[interactive] install steps seen:\n  " + "\n  ".join(steps))
    finally:
        p.close()

    # Then the trend list is this Mac's metal list and Qwen3.8-27B is pickable in it
    assert header and header.group(2) == "metal", p.out[:600]
    assert models and models[0][0] == "1"

    # And TensorFold is in Qwen3.8-27B's engine list as a native metal engine that installs on pick
    assert variant == "metal", tf_line
    assert tf_line.rstrip().endswith(f"(installs {PINNED} on pick)"), tf_line

    # And the pick installed the pinned TensorFold with the skill's install script
    flat = re.sub(r"\s+", "", p.out)   # the terminal wraps the long install command line
    assert "not installed -> installing" in p.out
    assert f"TensorFold.git@v{PINNED}" in flat
    assert (tbin / "tensorfold").exists()

    # And the model was served by TensorFold on Metal and answered "hi"
    #     (CI, LLGENIE_NO_SERVE=1: the dry plan names the TensorFold checkpoint and the start
    #      script prints the pinned TensorFold version instead of a Metal reply)
    assert f"Model  : {MODEL}" in p.out and f"Engine : {ENGINE} [metal]" in p.out
    if NO_SERVE:
        assert "TensorFold/Qwen3.8-27B-MLX-" in p.out or "TensorFold__Qwen3.8-27B-MLX-" in p.out
        assert f"tensorfold v{PINNED}" in reply, reply
    else:
        assert f"[tensorfold] serving llm-local at http://127.0.0.1:{PORT}/v1" in p.out
        # with the 64K window Hermes Agent needs, not TensorFold's 29,696 default on 48 GB
        assert "context: 65536" in p.out, p.out[-3000:]
    assert reply.strip(), "empty reply"
    print(f"\n[interactive] picked model {n_model} ({MODEL}) -> engine {n_engine} ({ENGINE}); "
          + (f"start script --version: {reply!r}" if NO_SERVE else
             f"TensorFold {PINNED} on Metal answered: {reply!r}"))
