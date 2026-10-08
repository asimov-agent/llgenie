"""The lightest TensorFold model on this Apple-Silicon host's Metal (issue #114).

The lightest checkpoint TensorFold 0.6.5 serves correctly is `LIGHT_REPO`
(Qwen3.5-9B, MLX 4-bit, 5.5 GiB: smaller Qwen3.5 sizes tie their embeddings, which
the packed decoder refuses; Nemotron-4B and gemma-E2B fail to load; a 2-bit 9B loads
but answers garbage). It is installed and served exactly as llgenie does on a pick:
TensorFold is ensured at the skill's pin (`--ensure tensorfold --arch metal`) and the
model is served by the native start script `llgenie-engine-tensorfold <dir> <port>`.

TensorFold itself decides whether this host can serve it: `tensorfold plan` with the
same budget env the start script uses (TENSORFOLD_MEMORY_LIMIT_GB = RAM).
  fits     (any Mac with >= ~12 GB, the local host) -> serve on Metal, answer "hi";
  too big  (GitHub's 7 GB macos-15 runner)          -> the plan's refusal names the
           budget, the start script refuses it the same way (no crash, no hang), and the
           dry launch is the one a bigger Mac serves (--context, budget env).

Runs through `make test-native-engine-light` (local host + CI job
`native-engine-macos-arm64`). A non-Apple-Silicon host FAILS loudly: there is no skip.
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

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import engine_skills as es  # noqa: E402

LIGHT_REPO = "mlx-community/Qwen3.5-9B-MLX-4bit"
INST = REPO / "scripts" / "install_engine_launchers.py"
PORT = 18194
CONTEXT = "4096"  # LLGENIE_CONTEXT: a small window, so only the weights decide the fit


def _env(tmp: Path) -> dict:
    env = {**os.environ, "LLAMA_BACKEND": "metal", "LLGENIE_CONTEXT": CONTEXT}
    env["PATH"] = f"{Path.home() / '.local' / 'bin'}{os.pathsep}{env['PATH']}"
    for k in ("PYTHONPATH", "VIRTUAL_ENV"):
        env.pop(k, None)
    return env


def _hf() -> str:
    hf = shutil.which("hf") or str(Path(sys.executable).parent / "hf")
    assert Path(hf).exists(), "the hf CLI is required (huggingface_hub[cli], in the gguf venv)"
    return hf


def test_lightest_tensorfold_model_serves_on_metal_or_is_refused_by_its_budget(tmp_path):
    """Given the lightest TensorFold model, llgenie's TensorFold start script serves it on
    Metal when TensorFold's plan says it fits this host, else refuses it with the budget."""

    # Given an Apple-Silicon host, TensorFold ensured at the pin (the llgenie pick's step)
    assert platform.system() == "Darwin" and platform.machine() == "arm64", (
        f"native TensorFold needs an Apple-Silicon Mac (this is {platform.system()} {platform.machine()})")
    env, bindir = _env(tmp_path), tmp_path / "bin"
    r = subprocess.run([sys.executable, str(INST), "--bin", str(bindir), "--ensure", "tensorfold",
                        "--arch", "metal"], env=env, capture_output=True, text=True, timeout=1800)
    assert r.returncode == 0, r.stdout + r.stderr
    start = bindir / "llgenie-engine-tensorfold"
    pinned = es.pinned_version(es.get_skill("tensorfold"))
    assert f"tensorfold v{pinned}" in subprocess.run([start, "--version"], env=env, capture_output=True,
                                                     text=True).stdout

    # And the lightest TensorFold model downloaded with the hf CLI
    model = Path(os.environ.get("LLGENIE_LIGHT_DIR") or tmp_path / LIGHT_REPO.replace("/", "__"))
    d = subprocess.run([_hf(), "download", LIGHT_REPO, "--local-dir", str(model)], env=env,
                       capture_output=True, text=True, timeout=3600)
    assert d.returncode == 0 and (model / "config.json").exists(), d.stderr[-2000:]

    # When TensorFold plans it with the budget env llgenie's Metal launch sets
    os.environ["LLGENIE_CONTEXT"] = CONTEXT  # es.plan reads it in this process, like the start script
    hw = {**es.detect_hardware(), "backend": "metal"}
    launch = es.plan(es.get_skill("tensorfold"), "metal", hw, mode="run")
    assert launch["launch"].endswith(f"--context {CONTEXT}"), launch["launch"]
    # LLAMA_RAM_BYTES (the repo's card-RAM seam) gives llgenie, and so TensorFold's budget, the RAM
    # of a smaller Mac, e.g. 7 GiB for GitHub's macos-15 runner: the refusal branch on a big Mac too
    budget = launch["env"]["TENSORFOLD_MEMORY_LIMIT_GB"]
    plan = subprocess.run(["tensorfold", "plan", str(model)], env={**env, **launch["env"]},
                          capture_output=True, text=True, timeout=300)
    plan_out = plan.stdout + plan.stderr
    print(f"\n[light] host RAM budget {budget} GB; tensorfold plan exit {plan.returncode}:\n{plan_out}")

    if plan.returncode != 0:
        # Then (a host too small, e.g. the 7 GB CI runner) the plan names the budget, and the
        #      start script refuses the model the same way: exits, never serves, never hangs
        assert "weights exceed the allowance" in plan_out, plan_out
        s = subprocess.run([start, str(model), str(PORT)], env=env, capture_output=True, text=True,
                           timeout=600)
        assert s.returncode != 0, s.stdout + s.stderr
        assert "do not fit" in s.stdout + s.stderr, (s.stdout + s.stderr)[-2000:]
        print(f"[light] this host cannot hold {LIGHT_REPO} (TensorFold's own budget check); "
              f"launch on a bigger Mac: {launch['launch']}  env={launch['env']}")
        return

    # Then (it fits) the start script serves it on Metal as llm-local and it answers "hi"
    log = open(tmp_path / "serve.log", "w")
    proc = subprocess.Popen([start, str(model), str(PORT)], env=env, stdout=log, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, start_new_session=True)
    try:
        deadline, ready = time.time() + 900, False
        while time.time() < deadline and proc.poll() is None and not ready:
            try:
                ready = "llm-local" in [m["id"] for m in json.load(urllib.request.urlopen(
                    f"http://127.0.0.1:{PORT}/v1/models", timeout=5))["data"]]
            except OSError:
                time.sleep(3)
        text = (tmp_path / "serve.log").read_text()
        assert ready, f"TensorFold never served {LIGHT_REPO}:\n{text[-3000:]}"
        req = urllib.request.Request(
            f"http://127.0.0.1:{PORT}/v1/chat/completions", headers={"Content-Type": "application/json"},
            data=json.dumps({"model": "llm-local", "messages": [{"role": "user", "content": "hi"}],
                             "max_tokens": 24, "chat_template_kwargs": {"enable_thinking": False}}).encode())
        reply = json.load(urllib.request.urlopen(req, timeout=300))["choices"][0]["message"]["content"]
        assert reply.strip() and "<|" not in reply, repr(reply)
        assert f"--context {CONTEXT}" in text and f"context: {CONTEXT}" in text, text[-3000:]
        print(f"[light] TensorFold {pinned} served {LIGHT_REPO} on Metal: {reply!r}")
    finally:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(60)
