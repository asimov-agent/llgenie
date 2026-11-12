#!/usr/bin/env python3
"""Engine smoke test: install an engine through its skill, serve a tiny model
with the skill's own launch line, and assert the llm-local contract.

This is what the CI `engine-smoke` matrix runs (one job per engine x backend
a hosted runner can execute). Nothing here is engine-specific: install steps,
env, pre/post-launch, launch and health all come from the SKILL.md. Only the
tiny test model per model format is chosen here.

  python3 scripts/engine_smoke.py <engine-id> [--backend cpu|metal|...] [--port N]
                                       [--image] [--serve]

The DEFAULT contract (no `--serve`, which is what CI `test-engine-stage` runs)
is the ENGINE BINARY smoke: after the image is built (or the skill installed),
the engine binary is invoked with `-h` and `--version` inside the image (or on
the host for the skill path) and must answer BOTH with exit 0 and non-empty
output. This is deterministic and near-instant, and is the gate for an engine
BUILD (issue #1717): a broken binary fails fast instead of burning a 1200 s
serving-readiness wait that redden on a slow/flaky endpoint or runner.

Serving conformance is the explicit `--serve` tier: with `--serve`, after the
binary smoke the engine image is run (or the skill launch line served) and the
llm-local OpenAI contract is asserted (/v1/models lists llm-local and a chat
completion returns text). No coverage is lost — it is just not the default
build gate.

Exit 0 = built/installed and the binary answered `-h`/`--version` (and, with
`--serve`, served llm-local). Any failure exits non-zero (never a skip).
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
    """Fetch the tiny model for `fmt` through the ONE downloader; return file or dir.

    `scripts/hf_download.py` is the repository's single model-download path (the `hf`
    CLI plus the resume/retry loop and the throttle wait). The smoke calls it exactly
    like `scripts/download_test_model.py` does, so a Hub 429 during the CI matrix waits
    its window out instead of reddening the engine job (issue #385). `-` in place of a
    filename asks for the whole repo (the safetensors/MLX snapshot).
    """
    repo, filename = TEST_MODELS[fmt]
    dest = MODELS_DIR / repo.replace("/", "__")
    downloader = Path(__file__).resolve().parent / "hf_download.py"
    cmd = [sys.executable, str(downloader), repo, filename or "-", str(dest), fmt]
    print("[smoke] $", " ".join(cmd), flush=True)
    rc = subprocess.call(cmd)
    if rc:
        raise SystemExit(f"[smoke] FAIL {fmt}: the model download exited {rc}")
    return str(dest / filename) if filename else str(dest)


def pick_format(skill: dict) -> str:
    for fmt in skill.get("formats") or []:
        if fmt in TEST_MODELS:
            return fmt
    raise SystemExit(f"[smoke] FAIL {skill['id']}: no tiny test model for formats {skill.get('formats')}")


def bash(cmd: str, **kw) -> subprocess.CompletedProcess:
    # LLGENIE_BASH is the bash make selected (bash 5). A bare `bash` on the macOS
    # CI runner is /bin/bash 3.2 invoked as a login shell, which drops the venv.
    return subprocess.run([os.environ.get("LLGENIE_BASH") or "bash", "-euo", "pipefail", "-c", cmd], **kw)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)


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
        cmd = ["uv", "run", "--no-project", "--quiet", "--python", "3.11",
               "--with-requirements", str(root / "tools" / "requirements.txt"),
               "--with-requirements", str(root / "tools" / "requirements-dev.txt"),
               "python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_engine_runs.py"]
        env = {**os.environ, **env_vars}
    r = subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
    print(r.stdout, end="")
    if r.returncode:
        print(r.stderr[-2000:])
    return r.returncode


def _print_verdict(tag: str, flag: str, ret: subprocess.CompletedProcess) -> bool:
    """One flag's binary-smoke verdict (issue #1717): exit 0 AND non-empty output.

    A dead flag is named instead of masked by a working one — this is the same
    per-flag discipline the push gate uses (issue #580). Returns True = OK.
    """
    out = ((ret.stdout or "") + (ret.stderr or "")).strip()
    head = out.splitlines()[0][:140] if out else ""
    if ret.returncode != 0:
        print(f"[smoke] FAIL {tag} {flag}: binary exited {ret.returncode}"
              + (f" ({head})" if head else ""))
        return False
    if not out:
        print(f"[smoke] FAIL {tag} {flag}: exit 0 with EMPTY output")
        return False
    print(f"[smoke] OK {tag} {flag}: answered ({head})")
    return True


# The version/help vocabulary the binary gate may probe (issue #2319's ceiling,
# re-read per issue #2573): what a manifest/skill is allowed to DOCUMENT, and
# the pinned probe set when an engine documents nothing. The gate probes exactly
# the documented set ("the binary answering the flags it documents", issue #1717)
# — never more than this vocabulary, never a flag the engine does not have.
DOCUMENTED_FLAG_VOCAB = frozenset({"-h", "--help", "--version"})
DEFAULT_BINARY_FLAGS = ["-h", "--version"]


def _documented_probe_set(flags, who: str) -> list[str] | None:
    """Validate a documented probe set (issue #2573). Returns the deduped set,
    the pinned default when nothing is documented, or None when a documented
    flag sits outside the version/help vocabulary — the caller fails closed."""
    flags = [str(f) for f in (flags or [])]
    bad = [f for f in flags if f not in DOCUMENTED_FLAG_VOCAB]
    if bad:
        print(f"[smoke] FAIL {who}: documents flag(s) {' '.join(bad)} outside the "
              f"version/help vocabulary [{' '.join(sorted(DOCUMENTED_FLAG_VOCAB))}] (issue #2573)")
        return None
    return list(dict.fromkeys(flags)) or list(DEFAULT_BINARY_FLAGS)


def binary_smoke(spec: dict | None = None, skill: dict | None = None,
                 p: dict | None = None, host_prelude: str = "") -> int:
    """The ENGINE BINARY smoke (issue #1717): the engine binary must answer
    BOTH `-h`/`--help` AND `--version` with exit 0 and non-empty output, BEFORE
    any serving wait. This is the DEFAULT engine-build gate (`test-engine-stage`);
    serving conformance is the opt-in `--serve` tier.

    * image path (spec): the binary is run INSIDE the built image — `docker run
      --rm <tag> <binary> <flag>` for each flag the committed manifest documents
      (the same `variant_binary` the image was built to contain). A `probe:
      device` variant (vllm cuda/rocm) is skipped here: its CLI probes the device
      at startup and cannot answer on a GPU-less runner (#106); its version is
      proven by the image's own `detect` in the serve tier.
    * skill path (p): the installed engine binary is probed on the host with the
      launch prelude so it can render a version/help line.

    Exit 0 only when every applicable flag answered. `--serve` is not needed.
    """
    import engine_image as ei
    if spec is not None:
        tag = spec["tag"]
        policy = (ei.binary_manifest(spec["id"], spec["variant"]).get("probe") or "flags")
        if policy == "device":
            print(f"[smoke] binary {spec['id']}/{spec['variant']}: probe=device (device needed at "
                  f"startup); answering in the serve tier via detect (#106)")
            return 0
        binary = ei.variant_binary(spec) or ""
        if not binary:
            print(f"[smoke] FAIL {tag}: binaries.json has no binary for {spec['id']}/{spec['variant']}")
            return 1
        # Probe what THIS engine's own generated manifest documents (issue #2573):
        # binaries.json is generated from each skill's binary_flags and the push
        # gate has read it since issue #204. #2319's pinned pair survives as the
        # default when nothing is documented, and as the vocabulary bound.
        probe = _documented_probe_set(ei.variant_flags(spec), f"{spec['id']}/{spec['variant']}")
        if probe is None:
            return 1
        flags = probe
        print(f"[smoke] binary {binary}  image {tag}  flags: {' '.join(flags)}", flush=True)
        ok = True
        for flag in flags:
            r = subprocess.run(  # proc-allow: binary smoke inside the built image (issue #1717)
                [ei.RUNTIME, "run", "--rm", "--entrypoint", "bash", tag, "-c",
                 f"{binary} {flag} 2>&1; ec=$?; exit $ec"],
                capture_output=True, text=True, timeout=120)
            ok = _print_verdict(tag, flag, r) and ok
        return 0 if ok else 1
    # skill path: installed engine binary on the host
    assert skill is not None  # the skill path is only entered without a spec
    binary = (p or {}).get("binary")
    if not binary:
        print(f"[smoke] FAIL {skill.get('id')}: no binary in the skill plan; cannot binary-smoke")
        return 1
    # Probe what THIS skill documents for the backend being smoked (issue #2573):
    # binary_flags is a list or a per-backend map; documented_flags resolves it.
    # Nothing documented -> the pinned #2319 pair as default, same as the image path.
    probe = _documented_probe_set(
        es.documented_flags(skill, (p or {}).get("backend")),
        f"{skill.get('id')}/{(p or {}).get('backend') or 'all-backends'}")
    if probe is None:
        return 1
    flags = probe
    print(f"[smoke] binary {binary}  flags: {' '.join(flags)}", flush=True)
    ok = True
    for flag in flags:
        r = subprocess.run(  # proc-allow: binary smoke of the installed engine (issue #1717)
            [os.environ.get("LLGENIE_BASH") or "bash", "-euo", "pipefail", "-c",
             host_prelude + f'{binary} "{flag}" 2>&1; ec=$?; exit $ec'],
            capture_output=True, text=True, timeout=120)
        ok = _print_verdict(binary, flag, r) and ok
    return 0 if ok else 1


def image_smoke(skill_id: str, backend: str | None, port: int, timeout: float,
                variant: str | None = None, no_gpu: bool = False, serve: bool = False) -> int:
    """Build the engine image (no-op if tagged), run the engine BINARY smoke
    first, and — only with `--serve` — run the image and assert the contract on
    the PUBLISHED host port (what an external AI harness sees). Without
    `--serve` the binary smoke is the whole gate: deterministic, near-instant,
    and it never waits a serving readiness budget (issue #1717)."""
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
    rc = binary_smoke(spec=spec)
    if rc:
        return rc
    if not serve:
        print(f"[smoke] OK image {spec['tag']}: engine binary answered its documented flags "
              f"(binary smoke; serving is the --serve tier, issue #1717)")
        return 0
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
        subprocess.run([ei.RUNTIME, "logs", "--tail", "20", name])  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
        subprocess.run([ei.RUNTIME, "rm", "-f", name], capture_output=True)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)


def smoke(skill_id: str, backend: str | None, port: int, timeout: float, serve: bool = False) -> int:
    skill = es.get_skill(skill_id)
    hw = es.detect_hardware()
    backend = es.pick_backend(skill, hw, backend)
    hw = {**hw, "backend": backend}

    rc = es.install(skill, backend, hw)
    if rc:
        print(f"[smoke] FAIL {skill_id}/{backend}: install exited {rc}")
        return rc

    p = es.plan(skill, backend, hw, extra={"port": port})
    rc = binary_smoke(skill=skill, p=p, host_prelude=p["env_prelude"])
    if rc:
        return rc
    if not serve:
        print(f"[smoke] OK {skill_id}/{backend}: installed engine binary answered its documented "
              f"flags (binary smoke; serving is the --serve tier, issue #1717)")
        return 0

    model = fetch_model(pick_format(skill))
    prelude = p["env_prelude"]

    def render(cmd):
        return cmd.replace("{model}", model) if cmd else cmd

    if p["pre_launch"]:
        bash(prelude + render(p["pre_launch"]), check=True)
    launch = prelude + render(p["launch"])
    print(f"[smoke] launch: {launch}", flush=True)
    log = open(f"/tmp/llgenie-smoke-{skill_id}.log", "w")
    proc = subprocess.Popen([os.environ.get("LLGENIE_BASH") or "bash", "-c", launch], stdout=log, stderr=subprocess.STDOUT,  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
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
    ap.add_argument("--serve", action="store_true",
                    help="also run the serving-conformance tier (image run / OpenAI SDK contract); "
                         "the DEFAULT is the engine binary smoke only (issue #1717)")
    a = ap.parse_args(argv)
    if a.image:
        return image_smoke(a.engine, a.backend, a.port or free_port(), a.timeout,
                           a.variant, a.no_gpu, a.serve)
    return smoke(a.engine, a.backend, a.port or free_port(), a.timeout, a.serve)


if __name__ == "__main__":
    sys.exit(main())
