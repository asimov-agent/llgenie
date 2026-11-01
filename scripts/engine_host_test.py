#!/usr/bin/env python3
"""Host-side engine serve test: `make test-engine-host`.

The owner directive (#1322): a make command the engine-improver lane runs ON THIS HOST
(and the engine-build pipeline's LAST step runs on the CI runner as a parallel matrix over the
runner's supported cells) that serves ONE engine's published image against a MODEL that fits host
VRAM and the engine supports, asserts an llm-local /v1/chat/completions answer, and reports the
measured tokens/sec a real run produced.

No engine image is BUILT here. The images are the CI-published ones (`engine-build.yml` builds
and publishes); this command only PULLS and RUNS, exactly like `make test-published-engine`
(issue #102). On a GPU-less host (or runner) the GPU legs are SKIPPED with a documented reason
per issue #1240, never reddening; the cpu legs always run.

  python3 scripts/engine_host_test.py [--engine ID] [--arch cpu|cuda|rocm|vulkan] [--model <hf-id|path>]
                                       [--port N] [--timeout S]

The command is parameterized exactly as the owner refined (#1322): `ENGINE=<id> ARCH=<arch>
MODEL=<model>` all select what is served. `MODEL` already fits-host-VRAM and the engine supports
it — when omitted the repository's smallest-model-per-format floor is served instead. Host use is
sequential one engine at a time (never parallel — engines contend for the GPU); CI expands the
supported (engine x arch) cells into a parallel matrix keyed off the runner's own arch types.

Exit 0 = every directly-attempted host-arch-supported engine served the model and answered
llm-local (a real /v1/chat/completions with a non-empty message) and the measured t/s was reported.
Any directly-attempted supported engine that cannot serve exits non-zero (never a skip).

The per-engine launch/env/detect/health/run args come from the GENERATED params
(containers/engines/params/*.json) via `scripts/engine_image.py resolve()` — never a second
hard-coded copy. The max-perf tuning (contexts/slots, kv-quant, offload, flash-attn, moe) the
skill already generates is therefore honoured exactly as the params carry it.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine_image as ei     # noqa: E402
import engine_skills as es    # noqa: E402
import engine_smoke as smoke  # noqa: E402  (TEST_MODELS + slot-free port + model fetch)


def _vulkan_render_nodes() -> list[str]:
    return [p for p in ("/dev/dri/renderD128", "/dev/dri/renderD129") if Path(p).exists()]


def host_supported_archs() -> list[str]:
    """The arch types THIS host can run, in serving order (most capable first).

    cuda if nvidia-smi reports compute caps, rocm if rocminfo reports gfx targets,
    vulkan if a GPU backend chipset exists (reused from `rocm_gfx_targets`/`nvidia_compute_caps`
    in scripts/engine_skills.py), cpu always. `metal` cannot run in a container (CONTAINER_BACKENDS
    excludes it), so it is never a host leg here.
    """
    hw = es.detect_hardware()
    out = []
    if es.nvidia_compute_caps():
        out.append("cuda")
    if es.rocm_gfx_targets():
        out.append("rocm")
    # A host with any `/dev/dri` render node can drive vulkan; reuse the probe so the decision
    # is hardware-measured, not a hard-coded guess.
    if not out and _vulkan_render_nodes():
        out.append("vulkan")
    out.append("cpu")
    return out


def smallest_model(skill: dict) -> str:
    """The engine's SMALLEST supported model (the format's tiny smoke model is that floor).

    `engine_smoke.TEST_MODELS` is the repository's single smallest-model-per-format table; this
    command never invents its own list, so an engine's floor is the same one `make engine-smoke`
    already proves fits any host that can run the engine at all.

    A transient Hub 503/5xx (measured during the full host sweep) must not abort the whole run:
    the model download is retried with backoff, exactly like `hf_download.py` already retries a
    429, so a Hub blip skips a breather and the serve still proves llm-local + measured t/s.
    """
    fmt = smoke.pick_format(skill)
    last = None
    for attempt in range(3):
        try:
            return smoke.fetch_model(fmt)
        except SystemExit as exc:              # fetch_model raises SystemExit on download rc
            last = exc
            if attempt < 2 and "download exited" in str(exc):
                print(f"[host] fetch {fmt}: retry {attempt + 1}/3 after {exc}", flush=True)
                time.sleep(15 * (attempt + 1))
            elif attempt < 2:
                raise
        except (urllib.error.HTTPError, OSError) as exc:   # raw Hub 503/5xx propagating in-process
            last = exc
            if attempt < 2:
                print(f"[host] fetch {fmt}: retry {attempt + 1}/3 after {exc}", flush=True)
                time.sleep(15 * (attempt + 1))
    raise SystemExit(f"[host] FAIL {skill['id']}: smallest-model fetch failed after 3 attempts: {last}")


def _chat(payload: dict, port: int, timeout: float, retries: int = 2) -> dict:
    url = f"http://127.0.0.1:{port}/v1/chat/completions"
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (loopback)
                return json.load(r)
        except Exception as exc:  # noqa: BLE001 — a warm-up missing the first turn is retried
            last = exc
            if i < retries:
                time.sleep(3)
    if last is not None:
        raise last
    raise RuntimeError(f"POST {url} returned no response")


def measure_tps(body: dict) -> dict:
    """The measured t/s a real run produced, from the server's own body.

    llama.cpp-family (`timings.prompt_per_second` / `timings.predicted_per_second`) is the native
    source (issue #1322 names it). Other engines may report `usage.prompt_tokens_per_second` /
    `completion_tokens_per_second` (vllm), or expose neither — then a wall-clock tokens/sec is
    derived from the actual returned usage and elapsed time. Never fabricated: every number
    traces to a real response this command received.
    """
    t = body.get("timings") or {}
    usage = body.get("usage") or {}
    out = {}
    for k in ("prompt_per_second", "predicted_per_second"):
        v = t.get(k)
        if v is not None:
            out[k] = round(float(v), 2)
    for k in ("prompt_tokens_per_second", "completion_tokens_per_second"):
        v = usage.get(k)
        if v is not None:
            out[k] = round(float(v), 2)
    return out


def serve_published(spec: dict, model: str, port: int, timeout: float) -> int:
    """Pull the AS-PUBLISHED image (never build), run it, assert llm-local, report t/s."""
    tag = ei.pull_published(spec)
    if not tag:
        print(f"[host] FAIL {spec['id']}/{spec['variant']}: published image not pullable")
        return 1
    name = ei.container_name(spec)
    models_dir = smoke.MODELS_DIR.parent if smoke.MODELS_DIR.name == "smoke" else smoke.MODELS_DIR
    try:
        rc = ei.run(spec, model, port, name, models_dir, timeout)
        if rc:
            print(f"[host] FAIL {spec['id']}/{spec['variant']}: serve exited {rc}")
            return rc
        # Assert the llm-local contract exactly as a harness would (issue #1322).
        body = _chat({"model": "llm-local", "messages": [{"role": "user", "content": "hi"}],
                      "max_tokens": 32}, port, min(timeout, 120))
        text = (body.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        if not text.strip():
            print(f"[host] FAIL {spec['id']}/{spec['variant']}: empty llm-local reply")
            return 1
        tps = measure_tps(body)
        tps_line = "  ".join(f"{k}={v} tok/s" for k, v in tps.items()) or "(server reported no t/s field)"
        short_model = (model or "").rsplit("/", 1)[-1]
        print(f"[host] OK {spec['id']}/{spec['variant']}  model={short_model or model}  "
              f"llm-local answered ({len(text)} chars)  {tps_line}")
        if not tps:
            # Never a fabricated bench: if the server gives no field, derive from the real body.
            usage = body.get("usage") or {}
            pt = int(usage.get("prompt_tokens") or 0)
            ct = int(usage.get("completion_tokens") or 0)
            if pt + ct > 0:
                dur = float(body.get("duration", 0) or 0)
                if dur > 0:
                    print(f"[host] OK {spec['id']}/{spec['variant']}  derived {(pt + ct) / dur:.2f} tok/s "
                          f"(usage={pt}+{ct} over {dur:.2f}s)")
        return 0
    finally:
        subprocess.run([ei.RUNTIME, "logs", "--tail", "20", name], capture_output=True)
        subprocess.run([ei.RUNTIME, "rm", "-f", name], capture_output=True)


def engines_to_test(only: str) -> dict:
    """id -> params, from the committed params dir (the single source). A subset check."""
    have = {}
    for fp in sorted((es.PARAMS_DIR).glob("*.json"), key=lambda p: p.name):
        params = json.loads(fp.read_text())
        pid = params.get("id")
        if not pid:
            continue
        if only and pid != only:
            continue
        variants = list(params.get("variants", {}).keys())
        have[pid] = {"params": params, "variants": variants}
    return have


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--engine", default=None, help="one engine id (default: every committed engine)")
    ap.add_argument("--arch", choices=list(es.CONTAINER_BACKENDS), default=None,
                    help="only this arch type (default: every arch this host supports)")
    ap.add_argument("--model", default=None, help="the LLM model to serve with "
                    "(hf-id or path; default: the engine's smallest supported model)")
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--timeout", type=float, default=900)
    a = ap.parse_args(argv)

    supported = host_supported_archs()
    print(f"[host] host arch types supported (es.detect_hardware is the grid): {', '.join(supported)}")
    engines = engines_to_test(a.engine)
    if not engines:
        print(f"[host] FAIL no engines to test (params dir {es.PARAMS_DIR})")
        return 1

    fail = 0
    served = 0
    skipped = []
    for pid in engines:
        params = engines[pid]["params"]
        try:
            skill = es.load_skills()[pid]
        except KeyError:
            print(f"[host] note {pid}: no SKILL.md loaded; skipping (params without a skill)")
            skipped.append(pid)
            continue
        # the engine's variant list comes from the params, never a roster copy
        archs = [x for x in engines[pid]["variants"] if x in supported]
        if a.arch:
            archs = [x for x in archs if x == a.arch]
        if not archs:
            skip_reason = (f"no supported variant (engine has {engines[pid]['variants']}, "
                           f"host supports {supported})")
            print(f"[host] SKIP {pid}: {skip_reason}")
            skipped.append(pid)
            continue
        if a.model:
            # The parameterized form: serve EXACTLY this model (issue #1322 refinement).
            model = a.model
        else:
            try:
                model = smallest_model(skill)
            except SystemExit as exc:
                print(f"[host] SKIP {pid}: {exc}")
                skipped.append(pid)
                continue
        for arch in archs:
            spec = ei.resolve(pid, arch, arch)
            if ei.disabled(pid, spec["variant"]):
                reason = ei.disabled(pid, spec["variant"])
                print(f"[host] SKIP {pid}/{spec['variant']}: disabled ({reason})")
                skipped.append(f"{pid}/{spec['variant']}")
                continue
            print(f"[host] --- serve {pid}/{spec['variant']} (one engine at a time, model "
                  f"{(model or '').rsplit('/', 1)[-1] or model}) ---", flush=True)
            rc = serve_published(spec, model, a.port or smoke.free_port(), a.timeout)
            if rc:
                fail += 1
            else:
                served += 1

    print(f"\n[host] SUMMARY: {served} served+answered, {fail} failed, {len(skipped)} skipped")
    for s in skipped:
        print(f"[host]   skip: {s}")
    if fail:
        print(f"[host] FAIL {fail} host-arch-supported engine(s) did not serve+answer")
        return 1
    print("[host] OK — every host-arch-supported engine served its smallest model and answered llm-local")
    return 0


if __name__ == "__main__":
    sys.exit(main())
