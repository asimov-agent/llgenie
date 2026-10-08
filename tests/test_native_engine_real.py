"""REAL native TensorFold on an Apple-Silicon Mac (issue #114) — no stand-ins.

Real `uv`, real network, the real skills/engines/tensorfold/SKILL.md install script.
uv's tool dirs are isolated (UV_TOOL_DIR / UV_TOOL_BIN_DIR under tmp), so the user's
own `uv tool` installs are never touched, yet every step is the one llgenie runs:

  install  : missing  -> `llgenie` pick installs the pinned TensorFold with the skill
  update   : older    -> the pick updates it to the pinned release
  reuse    : current  -> the pick reuses it (no reinstall)
  version  : ~/bin/llgenie-engine-tensorfold --version prints the pinned version
  serve    : (LLGENIE_NATIVE_SERVE=1, local only) `llgenie --select 1 --engine tensorfold`
             downloads the TensorFold checkpoint if missing, serves it on Metal and
             answers "hi" on /v1/chat/completions

Runs on the host through `make test-native-engine` (install/update/reuse/version, also
the macOS arm64 CI job) and `make test-native-engine-serve` (+ the real Metal serve).
A non-Apple-Silicon host FAILS loudly: there is no skip."""
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

SERVE = REPO / "scripts" / "llama_serve.py"
INST = REPO / "scripts" / "install_engine_launchers.py"
SKILL = es.get_skill("tensorfold")
PINNED = es.pinned_version(SKILL)
OLDER = "0.6.4"
SPEC = "tensorfold @ git+{repo}.git@v{ver}"


def _require_apple_silicon():
    assert platform.system() == "Darwin" and platform.machine() == "arm64", (
        f"native TensorFold needs an Apple-Silicon Mac (this is {platform.system()} {platform.machine()}); "
        "run `make test-native-engine` there (CI: the macos arm64 job)")
    assert shutil.which("uv"), "uv is required (brew install uv / https://docs.astral.sh/uv/)"


@pytest.fixture(scope="module")
def mac(tmp_path_factory):
    """Isolated uv tool dirs + ~/bin for llgenie's start scripts; a 48 GB metal host."""
    _require_apple_silicon()
    root = tmp_path_factory.mktemp("native")
    tools, tbin, bindir = root / "uv-tools", root / "uv-bin", root / "bin"
    for d in (tools, tbin, bindir):
        d.mkdir()
    env = {**os.environ, "UV_TOOL_DIR": str(tools), "UV_TOOL_BIN_DIR": str(tbin),
           "PATH": f"{tbin}{os.pathsep}{os.environ['PATH']}", "LLAMA_BACKEND": "metal"}
    for k in ("PYTHONPATH", "LLGENIE_REGISTRY_SRC"):
        env.pop(k, None)
    return {"env": env, "bindir": bindir, "tbin": tbin}


def _run(mac, *cmd, timeout=900):
    return subprocess.run([str(c) for c in cmd], env=mac["env"], capture_output=True, text=True,
                          timeout=timeout, stdin=subprocess.DEVNULL)


def _state(mac) -> dict:
    code = ("import sys,json; sys.path.insert(0,'scripts'); import install_engine_launchers as i; "
            "print(json.dumps(i.native_state('tensorfold')))")
    r = _run(mac, sys.executable, "-c", code)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def _uv_install(mac, ver):
    r = _run(mac, "uv", "tool", "install", "--force", SPEC.format(repo=SKILL["repo"], ver=ver))
    assert r.returncode == 0, r.stderr


def _ensure(mac):
    """What llgenie runs on the pick (llama_serve._ensure_and_exec)."""
    return _run(mac, sys.executable, INST, "--bin", mac["bindir"], "--ensure", "tensorfold", "--arch", "metal")


DRY_MAC = {"LLAMA_RAM_BYTES": str(48 * 2**30), "LLGENIE_SYSTEM_RAM_BYTES": str(48 * 2**30)}


def _engine_line(mac) -> str:
    # the dry pick shows what llgenie offers the reporter's 48 GB Mac: a 7 GB CI runner lists
    # no trend model of its own (the install/update/reuse below is real on any Mac)
    r = subprocess.run([sys.executable, str(SERVE), "--select", "1", "--engine", "tensorfold", "--dry"],
                       env={**mac["env"], **DRY_MAC}, capture_output=True, text=True, timeout=900,
                       stdin=subprocess.DEVNULL)
    assert r.returncode == 0, r.stdout + r.stderr
    return next(ln for ln in r.stdout.splitlines() if ln.startswith("Engine :"))


def test_1_missing_tensorfold_is_installed_by_the_pick(mac):
    # Given a Mac where TensorFold is not installed (isolated uv tool dir)
    assert _state(mac)["state"] == "missing"

    # When the user picks TensorFold (llgenie shows the plan, then ensures it)
    line = _engine_line(mac)
    r = _ensure(mac)

    # Then the picker said it installs, and the skill's install script installed the pin
    assert line.endswith(f"(installs {PINNED} on pick)"), line
    assert r.returncode == 0, r.stdout + r.stderr
    assert "not installed -> installing" in r.stdout
    assert _state(mac) == {"state": "current", "installed": PINNED, "wanted": PINNED}
    assert (mac["tbin"] / "tensorfold").exists()


def test_2_start_script_prints_the_pinned_version(mac):
    # Given TensorFold installed by the pick

    # When its llgenie start script is asked for the version
    r = _run(mac, mac["bindir"] / "llgenie-engine-tensorfold", "--version")

    # Then it answers with the pinned TensorFold release
    assert r.returncode == 0, r.stdout + r.stderr
    assert f"tensorfold v{PINNED}" in r.stdout


def test_3_older_tensorfold_is_updated_by_the_pick(mac):
    # Given TensorFold at an older release
    _uv_install(mac, OLDER)
    assert _state(mac)["state"] == "outdated"

    # When the user picks TensorFold
    line = _engine_line(mac)
    r = _ensure(mac)

    # Then the picker said it updates, and the pick updated it to the pinned release
    assert line.endswith(f"(installed {OLDER} -> updates to {PINNED} on pick)"), line
    assert r.returncode == 0, r.stdout + r.stderr
    assert f"installed {OLDER} != pinned {PINNED} -> updating" in r.stdout
    assert _state(mac)["installed"] == PINNED


def test_4_current_tensorfold_is_reused_by_the_pick(mac):
    # Given TensorFold at the pinned release
    assert _state(mac)["state"] == "current"
    before = (mac["tbin"] / "tensorfold").stat().st_mtime_ns

    # When the user picks TensorFold again
    line = _engine_line(mac)
    r = _ensure(mac)

    # Then nothing is reinstalled: same executable, "(current)"
    assert line.endswith(f"(installed {PINNED})"), line
    assert r.returncode == 0 and "(current)" in r.stdout, r.stdout + r.stderr
    assert "uv tool install" not in r.stdout
    assert (mac["tbin"] / "tensorfold").stat().st_mtime_ns == before


def test_5_llgenie_pick_downloads_installs_and_serves_on_metal(mac):
    """`make test-native-engine-serve` only (LLGENIE_NATIVE_SERVE=1): the full user path."""
    if os.environ.get("LLGENIE_NATIVE_SERVE") != "1":
        # the CI/arm64 target checks install/update/reuse only; prove the serve path is
        # wired (a dry pick resolves a TensorFold checkpoint + the native start script)
        r = subprocess.run([sys.executable, str(SERVE), "--select", "1", "--engine", "tensorfold", "--dry"],
                           env={**mac["env"], **DRY_MAC}, capture_output=True, text=True, timeout=900,
                           stdin=subprocess.DEVNULL)
        assert r.returncode == 0 and "llgenie-engine-tensorfold" in r.stdout, r.stdout + r.stderr
        return

    # Given TensorFold removed again, so the pick must install it as well as serve
    _run(mac, "uv", "tool", "uninstall", "tensorfold")
    assert _state(mac)["state"] == "missing"
    port = 18197

    # When the user picks model 1 with TensorFold (download if missing, install, serve)
    env = {**mac["env"], "HOME": os.environ["HOME"]}
    log = open(mac["bindir"].parent / "serve.log", "w")
    proc = subprocess.Popen([sys.executable, str(SERVE), "--select", "1", "--engine", "tensorfold",
                             "--port", str(port)], env=env, stdout=log, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, start_new_session=True)
    try:
        deadline, ready = time.time() + 3600, False
        while time.time() < deadline and proc.poll() is None:
            try:
                ids = [m["id"] for m in json.load(urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/v1/models", timeout=5))["data"]]
                ready = "llm-local" in ids
                if ready:
                    break
            except OSError:
                pass
            time.sleep(5)
        text = (mac["bindir"].parent / "serve.log").read_text()
        assert ready, f"TensorFold never served llm-local:\n{text[-3000:]}"

        # Then it answers "hi" on Metal, and the pick installed the pinned TensorFold
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/chat/completions", headers={"Content-Type": "application/json"},
            data=json.dumps({"model": "llm-local", "messages": [{"role": "user", "content": "hi"}],
                             "max_tokens": 24, "chat_template_kwargs": {"enable_thinking": False}}).encode())
        reply = json.load(urllib.request.urlopen(req, timeout=300))["choices"][0]["message"]["content"]
        assert reply.strip(), "empty reply"
        assert "not installed -> installing" in text and "READY tensorfold/metal" in text, text[-3000:]
        assert _state(mac)["installed"] == PINNED

        # And it is the README's Mac pick, Qwen3.8-27B, from its TensorFold checkpoint, served with
        #     the 65,536 window Hermes Agent needs (the full Mac budget, not TensorFold's 70%)
        assert "Model  : Qwen3.8-27B  (" in text and "TensorFold__Qwen3.8-27B-MLX-" in text, text[:2000]
        assert "--context 65536" in text and "context: 65536" in text, text[-3000:]
        print(f"\n[native-serve] TensorFold {PINNED} served Qwen3.8-27B on Metal (context 65536): {reply!r}")
    finally:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(60)
