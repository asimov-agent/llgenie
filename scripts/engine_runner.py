#!/usr/bin/env python3
"""Standalone engine runner: install / detect / serve from a FROZEN params file.

This is the only llgenie code inside an engine container image. It never reads
skills: everything (install steps, env, launch, health) comes from one variant
of containers/engines/params/<engine>.json, generated from the skill by
`make engine-params` and committed. Stdlib only.

  engine_runner.py install <params.json>
  engine_runner.py detect  <params.json>
  engine_runner.py serve   <params.json> --model M [--host H] [--port P] [--drafter D]
"""
from __future__ import annotations

import argparse
import json
import re
import os
import signal
import subprocess
import sys
import time
import urllib.request


def env_prelude(env: dict) -> str:
    """`export K="V"; ...` so bash expands $VAR / $(cmd) in env values
    (e.g. HIP_PATH="$(hipconfig -R)", CUDA_HOME="$(dirname $(dirname $(command -v nvcc)))")."""
    out = []
    for k, v in env.items():
        esc = str(v).replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`")
        out.append(f'export {k}="{esc}"; ')
    return "".join(out)


def bash_exe() -> str:
    """The bash make already selected (``LLGENIE_BASH``, set by the Makefile).

    A bare ``bash`` is wrong on the macOS CI runner: GitHub invokes ``/bin/bash``
    (3.2) as a login shell, so it drops the venv from PATH and a launch of
    ``python3 -m http.server`` never binds. The Makefile's recipe shell is bash 5
    and keeps the PATH ``make test-env`` put the 3.11 venv on.
    """
    return os.environ.get("LLGENIE_BASH") or "bash"


def _bash(cmd: str, **kw) -> subprocess.CompletedProcess:
    return subprocess.run([bash_exe(), "-euo", "pipefail", "-c", cmd], **kw)


def install(p: dict) -> int:
    pre = env_prelude(p.get("env") or {})
    for step in p.get("install") or []:
        print(f"[engine-runner] {p['id']}/{p['backend']}$ {step}", flush=True)
        rc = _bash(pre + step).returncode
        if rc:
            print(f"[engine-runner] FAIL {p['id']}/{p['backend']}: step exited {rc}", file=sys.stderr)
            return rc
    return detect(p)


VERSION_RE = re.compile(r"\d+\.\d+(\.\d+)?")


def detect(p: dict) -> int:
    if not p.get("detect"):
        return 1
    r = _bash(env_prelude(p.get("env") or {}) + p["detect"], capture_output=True, text=True)
    lines = [l.strip() for l in (r.stdout + "\n" + r.stderr).splitlines() if l.strip()]
    # the version line, not a warning printed first (ollama: "could not connect ...")
    ver = next((l for l in lines if VERSION_RE.search(l)), lines[0] if lines else "")
    ver = re.sub(r"^(warning|info):\s*", "", ver, flags=re.I)
    if r.returncode == 0:
        print(f"[engine-runner] {p['id']}/{p['backend']}: installed {ver}".rstrip())
        return 0
    print(f"[engine-runner] {p['id']}/{p['backend']}: missing (detect exited {r.returncode})\n"
          f"{(r.stdout + r.stderr)[-3000:]}", file=sys.stderr)
    return 1


def probe(port: int, health, host: str = "127.0.0.1") -> bool:
    path = str(health or "GET /v1/models").split()[-1]
    try:
        urllib.request.urlopen(f"http://{host}:{port}{path}", timeout=3)  # noqa: S310 (loopback)
        return True
    except Exception:
        return False


def serve_plan(p: dict, model: str, host: str, port: int, drafter: str = "",
               ready_timeout: float = 1800, on_ready=None) -> int:
    """pre_launch -> launch -> wait ready -> post_launch; stay in the foreground
    until the server exits. SIGTERM/SIGINT are forwarded to the server."""
    vals = {"{model}": model, "{drafter}": drafter, "{host}": host, "{port}": str(port)}

    def bind(v):
        for k, val in vals.items():
            v = str(v).replace(k, val)
        return v
    pre = env_prelude({k: bind(v) for k, v in (p.get("env") or {}).items()})

    def r(cmd):
        if not cmd:
            return cmd
        for k, v in vals.items():
            cmd = cmd.replace(k, v)
        return cmd

    os.makedirs(os.environ.get("HF_HOME", "/tmp/hf") + "/hub", exist_ok=True)  # HF libs expect it
    if p.get("pre_launch"):
        _bash(pre + r(p["pre_launch"]), check=True)
    launch = r(p["launch"])
    print(f"[engine-runner] serve {p['id']}/{p['backend']}: {launch}", flush=True)
    serve_log = os.path.join(os.environ.get("TMPDIR", "/tmp"), "engine-runner-serve.log")
    out = open(serve_log, "w")
    proc = subprocess.Popen([bash_exe(), "-c", pre + launch], start_new_session=True,
                            stdout=out, stderr=subprocess.STDOUT)

    def stop(signum, _frame):
        try:
            os.killpg(proc.pid, signum)
        except ProcessLookupError:
            pass
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    end = time.time() + ready_timeout
    while proc.poll() is None and not probe(port, p.get("health"), host):
        if time.time() > end:
            print(f"[engine-runner] {p['id']}: not ready after {ready_timeout:.0f}s (server exited {proc.poll()})", file=sys.stderr)
            stop(signal.SIGTERM, None)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            log = os.path.join(os.environ.get("TMPDIR", "/tmp"), "engine-runner-serve.log")
            if os.path.exists(log):
                print(open(log, errors="replace").read()[-3000:], file=sys.stderr)
            return 1
        time.sleep(1)
    if proc.poll() is None:
        if p.get("post_launch"):
            _bash(pre + r(p["post_launch"]), check=True)
        print(f"[engine-runner] READY {p['id']}/{p['backend']} on {host}:{port} model=llm-local", flush=True)
        if on_ready is not None:
            on_ready()
            stop(signal.SIGTERM, None)
    return proc.wait()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=("install", "detect", "serve"))
    ap.add_argument("params")
    ap.add_argument("--model", default="")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=11434)
    ap.add_argument("--drafter", default="")
    a = ap.parse_args(argv)
    with open(a.params) as f:
        p = json.load(f)
    if a.cmd == "install":
        return install(p)
    if a.cmd == "detect":
        return detect(p)
    if not a.model:
        ap.error("serve needs --model")
    return serve_plan(p, a.model, a.host, a.port, a.drafter)


if __name__ == "__main__":
    sys.exit(main())
