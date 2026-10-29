#!/usr/bin/env python3
"""Container start scripts for every llgenie engine image (issue #98).

`make install` builds nothing natively. It detects this host's backend (cuda,
rocm, vulkan or cpu; LLAMA_BACKEND / ARCH= mock it) and PULLS the matching
published, CI-tested image of each engine from LLGENIE_REGISTRY (GHCR,
default ghcr.io/asimov-agent). Only images for this backend are pulled (an engine
without one falls back to its cpu image). It builds an image only with --build
(BUILD=1). By default it installs the CORE set: both llama.cpp trees (the two
shims below). ENGINES=all installs every engine; any other engine is pulled the
first time `llgenie --pick/--engine` selects it (`--ensure <id>`). Then it
writes a start script into ~/bin:

  ~/bin/llgenie-engine-<id>   docker-runs the engine image:
                                llgenie-engine-<id> --version       engine version
                                llgenie-engine-<id> <model> [port]  serve <model> as
                                  llm-local on 127.0.0.1:${PORT:-11434}/v1
  ~/bin/llama-server          shim: the stock llama.cpp image (ggml-org)
  ~/bin/prism-server          shim: the Prism llama.cpp image
                              Both take the llama-server CLI and run it in the
                              container; llgenie.py picks one by the card's tree
                              (Prism on cards <= 24 GB, like detect_server).

  python3 scripts/install_engine_launchers.py [--bin DIR] [--arch A] [--engines all|id,id] [--build]
  python3 scripts/install_engine_launchers.py --bin DIR --ensure <engine-id>
  python3 scripts/install_engine_launchers.py --bin DIR --test

--test runs every start script with --version (each is a docker run of its
image) and fails unless every one prints a version. Metal-only engines have no
container image, so no script is written for them. Stdlib only.
"""
from __future__ import annotations

import argparse
import re
import shutil
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import engine_image as ei  # noqa: E402


def _macos_silicon() -> bool:
    """True only on an Apple-Silicon Mac (detect_server probes the hardware)."""
    import detect_server as d
    return d._macos_silicon()


PARAMS = REPO / "containers" / "engines" / "params"
PREFIX = "llgenie-engine-"
# same GPU passthrough as `make run-engine` (engine_skills.RUN_ARGS): the host
# driver is mounted into the container at run time
import engine_skills as es  # noqa: E402
GPU_FLAGS = {k: " ".join(v) for k, v in es.RUN_ARGS.items()}


def nvidia_modeset_guard() -> str:
    """Bash that creates /dev/nvidia-modeset before CDI injection (issue #157).

    The nvidia_modeset module can be loaded while the device node (195, 254)
    was never created. nvidia-container-toolkit's CDI spec stats that path and
    `docker run --device nvidia.com/gpu=all` then fails before the container
    starts. nvidia-modprobe is setuid and creates the node. The guard runs only
    after LLGENIE_NO_GPU has rewritten `gpu`, so a CPU fallback never calls it.
    """
    return """if [[ " ${gpu[*]} " == *" nvidia.com/gpu=all "* && ! -e /dev/nvidia-modeset ]]; then
  command -v nvidia-modprobe >/dev/null && nvidia-modprobe -c 0 -m -u || true
  if [[ ! -e /dev/nvidia-modeset ]]; then
    echo "[llgenie] /dev/nvidia-modeset is missing, so NVIDIA CDI cannot inject the GPU." >&2
    echo "[llgenie] create it with: nvidia-modprobe -m" >&2
    exit 1
  fi
fi
"""


CORE_ENGINES = ["llama.cpp", "llama.cpp-prism"]  # the two llama.cpp shims; others on demand
RUNTIME_DOWN = ("container runtime '{rt}' does not answer (`{rt} info` failed): start its engine "
                "or point RUNTIME at a docker CLI. Colima is never started (issue #120)")


def detected_arch() -> str:
    """cuda | rocm | vulkan | metal | cpu for this host (LLAMA_BACKEND mocks it).

    Apple Silicon is metal (issue #120). Mapping it to cpu made macOS pull a cpu image.
    """
    try:
        import detect_server as d
        b = d.detect_all().get("backend")
        if b == "cpu" and shutil.which("rocminfo") and es.rocm_gfx_targets():
            b = "rocm"
        return {"cuda": "cuda", "rocm": "rocm", "vulkan": "vulkan", "metal": "metal"}.get(b, "cpu")
    except Exception:  # noqa: BLE001
        return "cpu"


def variant_for(engine: str, arch: str) -> str | None:
    """The engine's image variant for this backend.

    A metal host never falls back to a cpu image (issue #120). Linux does.
    """
    variants = [v for v in json.loads((PARAMS / f"{engine}.json").read_text()).get("variants") or {}
                if not ei.disabled(engine, v)]  # disabled images are never pulled (ei.DISABLED)
    if arch in variants:
        return arch
    if arch == "metal":
        return None
    return "cpu" if "cpu" in variants else None


def script_name(engine: str) -> str:
    return PREFIX + engine.replace(".", "-").replace("/", "-")


def ensure_image(engine: str, variant: str, build: bool) -> str | None:
    """Local tag of the engine image: present, pulled from the registry, or built."""
    spec = ei.resolve(engine, None, variant)
    if ei._available(spec["tag"]):
        return spec["tag"]
    if build and ei.build(spec) == 0:
        return spec["tag"]
    return None


# Load HF_TOKEN from the login rc when the job did not export it, then `docker -e HF_TOKEN`
# forwards it. The value is never echoed.
HF_TOKEN_SHELL = "\n".join([
    'if [ -z "${HF_TOKEN:-}" ]; then',
    '  _ll_rc=""; _ll_line=""',
    '  for _ll_rc in "$HOME/.zshrc" "$HOME/.bashrc"; do',
    '    [ -r "$_ll_rc" ] || continue',
    '    _ll_line="$(grep -E \'^[[:space:]]*(export[[:space:]]+)?HF_TOKEN=\' "$_ll_rc" | tail -n 1 || true)"',
    '    [ -n "$_ll_line" ] || continue',
    '    HF_TOKEN=${_ll_line#*=}',
    '    HF_TOKEN=${HF_TOKEN#\\"}',
    '    HF_TOKEN=${HF_TOKEN%\\"}',
    "    HF_TOKEN=${HF_TOKEN#\\'}",
    "    HF_TOKEN=${HF_TOKEN%\\'}",
    '    export HF_TOKEN',
    '    break',
    '  done',
    '  unset _ll_rc _ll_line',
    'fi',
    '',
])


def launcher(engine: str, variant: str, tag: str, models: str, platform: str = "") -> str:
    name = script_name(engine)
    plat = f" --platform {platform}" if platform else ""
    modeset = nvidia_modeset_guard() if variant == "cuda" else ""
    return f"""#!/usr/bin/env bash
# Generated by `make install` (scripts/install_engine_launchers.py). Do not edit.
# {engine} ({variant}) runs ONLY through its container image {tag}.
#   {name} --version          engine version (docker run ... version)
#   {name} <model> [port]     serve <model> as llm-local on 127.0.0.1:${{PORT:-11434}}/v1
set -euo pipefail
IMAGE="${{LLGENIE_IMAGE:-{tag}}}"
case "${{1:-}}" in
  --version|-v|version) exec {ei.RUNTIME} run --rm{plat} "$IMAGE" version ;;
  ""|-h|--help) sed -n '3,5p' "$0"; exit 0 ;;
esac
MODEL="$1"; PORT="${{2:-${{PORT:-11434}}}}"
MODELS="${{LLGENIE_MODELS_DIR:-{models}}}"
case "$MODEL" in "$MODELS"/*) MODEL="/models/${{MODEL#"$MODELS"/}}" ;; esac
name="llgenie-{engine.replace('.', '-')}-$PORT"
{ei.RUNTIME} rm -f "$name" >/dev/null 2>&1 || true
trap '{ei.RUNTIME} rm -f "$name" >/dev/null 2>&1' EXIT INT TERM
gpu=({GPU_FLAGS.get(variant, '')}); [ -n "${{LLGENIE_NO_GPU:-}}" ] && gpu=({GPU_FLAGS['cpu']})  # LLGENIE_NO_GPU=1: GPU image on CPU
{HF_TOKEN_SHELL}{modeset}{ei.RUNTIME} run --rm{plat} --name "$name" "${{gpu[@]}}" \\
  -p "127.0.0.1:$PORT:11434" -v "$MODELS:/models" -e HF_TOKEN \\
  -e "LLGENIE_MODEL=$MODEL" "$IMAGE" serve &
wait $!
"""


def server_binary(engine: str, variant: str) -> str:
    """llama-server's path inside the image: the first word of the frozen launch
    line (/app/llama-server in ggml-org images, a build-<arch>/bin path in the
    Prism/LaurentZuijdwijk source builds)."""
    params = json.loads((es.PARAMS_DIR / f"{engine}.json").read_text())
    return params["variants"][variant]["launch"].split()[0]


SERVER_SHIMS = {"llama.cpp": "llama-server", "llama.cpp-prism": "prism-server"}


def llama_server_shim(tag: str, variant: str, binary: str = "/app/llama-server",
                      name: str = "llama-server", platform: str = "") -> str:
    bindir = binary.rsplit("/", 1)[0]
    plat = f" --platform {platform}" if platform else ""
    modeset = nvidia_modeset_guard() if variant == "cuda" else ""
    return f"""#!/usr/bin/env bash
# Generated by `make install`: {name} (llama.cpp llama-server) through its container image
# ({tag}). llgenie.py calls it like the native binary; model files are mounted
# read-only at the same path and the port is published on the same host:port.
set -euo pipefail
IMAGE="${{LLGENIE_IMAGE:-{tag}}}"
case "${{1:-}}" in --version|version) exec {ei.RUNTIME} run --rm{plat} "$IMAGE" version ;; esac
args=(); mounts=(); port=8080; host=127.0.0.1
while [[ $# -gt 0 ]]; do
  case "$1" in
    -m|--model|-md|--model-draft|--mmproj)
      f="$(readlink -f "$2")"; mounts+=(-v "$(dirname "$f"):$(dirname "$f"):ro"); args+=("$1" "$f"); shift 2 ;;
    --port) port="$2"; args+=(--port "$2"); shift 2 ;;
    --host) host="$2"; args+=(--host 0.0.0.0); shift 2 ;;
    *) args+=("$1"); shift ;;
  esac
done
# one container per port, named so it can always be found and removed: a
# killed shim (SIGTERM/SIGKILL from a caller) must not leave the server running.
name="llgenie-{name}-$port"
{ei.RUNTIME} rm -f "$name" >/dev/null 2>&1 || true
trap '{ei.RUNTIME} rm -f "$name" >/dev/null 2>&1' EXIT INT TERM
gpu=({GPU_FLAGS.get(variant, '')}); [ -n "${{LLGENIE_NO_GPU:-}}" ] && gpu=({GPU_FLAGS['cpu']})  # LLGENIE_NO_GPU=1: GPU image on CPU
{HF_TOKEN_SHELL}{modeset}{ei.RUNTIME} run --rm{plat} --name "$name" "${{gpu[@]}}" -p "$host:$port:$port" "${{mounts[@]}}" \\
  -e HF_TOKEN -e LD_LIBRARY_PATH={bindir} --entrypoint {binary} "$IMAGE" "${{args[@]}}" &
wait $!
"""


def cuda_cdi_ready() -> bool:
    """nvidia-container-toolkit generated the CDI spec that mounts the host driver."""
    r = subprocess.run(["nvidia-ctk", "cdi", "list"], capture_output=True, text=True) \
        if shutil.which("nvidia-ctk") else None
    return bool(r and r.returncode == 0 and "nvidia.com/gpu=all" in r.stdout)


def install_plan(arch: str, only: list[str] | None = None) -> list[dict]:
    """The images `install` resolves for this backend — the ONE place that list is built.

    One entry per engine: `variant` + the exact published `tag` install pulls, or
    `variant=None` with a `why` when the engine is unknown or has no image for this
    backend (install reports it and skips it). `wait_published` waits for exactly these
    tags, so the gate can never wait for something install would not pull (issue #169).
    """
    every = sorted(json.loads(pf.read_text())["id"] for pf in PARAMS.glob("*.json"))
    wanted = every if only == ["all"] else (only or CORE_ENGINES)
    plan = []
    for engine in wanted:
        if engine not in every:
            plan.append({"engine": engine, "variant": None, "tag": "",
                         "why": f"unknown engine (have {', '.join(every)})"})
            continue
        p = json.loads((PARAMS / f"{engine}.json").read_text())
        variant = variant_for(engine, arch)
        if not variant:
            plan.append({"engine": engine, "variant": None, "tag": "",
                         "why": f"no {arch}/cpu image (has {', '.join(p.get('variants') or {})})"})
            continue
        plan.append({"engine": p["id"], "variant": variant,
                     "tag": ei.resolve(p["id"], None, variant)["tag"], "why": ""})
    return plan


# The engine-image jobs of the same CI run build and push these images in parallel
# with the install job, so a first run of a new pin used to fail `not published`
# (issue #169). The gate polls the registry manifest until each tag shows up.
#
# A tag that is absent has TWO very different causes, and the wait used to report
# both as "not published" (issue #893): the image was never produced (a bad pin, a
# failed publish step), or the producer cell was still QUEUED in the runner queue the
# install job is itself running in — the queue outlasted the wait, which is capacity,
# not a defect. So the wait reads its producers' OWN job state: `ci.yml` names each
# engine-image cell `engine-image-<engine>-<variant>`, and that job name is the join.
#
#   queued / in_progress  -> keep waiting, up to PUBLISH_WAIT_QUEUE_MAX_S
#   completed / failure   -> NOT FOUND, naming the producer and its conclusion
#   completed / success   -> NOT FOUND, the tag really is missing
#   no state to read      -> the old budget, and the message says capacity is not ruled out
#
# Both bounds are wall-clock and finite. PUBLISH_WAIT_QUEUE_MAX_S plus the reserve the
# rest of the install job needs must stay BELOW that job's `timeout-minutes`, or a hung
# producer inherits GitHub's six-hour default: tests/test_ci_publish_order.py pins the
# relation against the workflow file itself.
PUBLISH_WAIT_TIMEOUT_S = 30 * 60
PUBLISH_WAIT_QUEUE_MAX_S = 75 * 60
PUBLISH_WAIT_RESERVE_S = 20 * 60   # pull + make install + the dry run + uninstall
PUBLISH_WAIT_POLL_S = 20
#: A producer that has CONCLUDED ends the wait, because its tag is final — but not at
#: once: a registry manifest can lag its own push by a moment, or answer 404 while the
#: token is being minted, and a timed-out verdict there would be a flake dressed as a
#: defect. So a concluded producer shortens the budget to this, never to zero.
PUBLISH_WAIT_CONCLUDED_GRACE_S = 2 * 60

#: A producer status that means "the builder has not finished" — the runner queue.
PRODUCER_QUEUED_STATES = ("queued", "in_progress", "waiting", "pending", "requested")


def producer_job_name(engine: str, variant: str) -> str:
    """The `ci.yml` job name of the cell that builds and pushes ONE image."""
    return f"engine-image-{engine}-{variant}"


def _github_get(url: str, token: str) -> tuple[dict, str]:
    """(body, next-page link) for one Actions API page. Raises on a non-200."""
    import urllib.request
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "llgenie-ci-wait-engine-images",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        body, link = json.loads(r.read()), r.headers.get("Link") or ""
    nxt = ""
    for part in link.split(","):
        if 'rel="next"' in part:
            nxt = part.split(";")[0].strip().strip("<>")
    return body, nxt


def producer_job_states() -> dict[str, tuple[str, str]]:
    """{job name: (status, conclusion)} for this run's jobs, from the Actions API.

    Empty when this is not a GitHub Actions run (a host `make ci-wait-engine-images`)
    or when the token cannot read the run's jobs: the wait then keeps its queue-unaware
    budget and still fails loudly. It never raises and never hangs — a lookup that
    cannot answer must not become a stall.
    """
    run_id = os.environ.get("GITHUB_RUN_ID", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    token = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    if not (run_id and repo and token):
        return {}
    url = (f"https://api.github.com/repos/{repo}/actions/runs/{run_id}"
           f"/jobs?filter=latest&per_page=100")
    states: dict[str, tuple[str, str]] = {}
    try:
        for _ in range(20):                      # paginated; 20 pages is 2000 jobs
            body, nxt = _github_get(url, token)
            for job in body.get("jobs") or []:
                name = job.get("name") or ""
                if name:
                    states[name] = (job.get("status") or "", job.get("conclusion") or "")
            if not nxt:
                break
            url = nxt
    except Exception as e:  # noqa: BLE001 - "cannot read" is `unknown`, not a failure
        print(f"[install] could not read the producer jobs' state ({str(e)[-120:]}): "
              f"the runner queue cannot be ruled out", flush=True)
        return {}
    return states


def producer_state(states: dict[str, tuple[str, str]] | None,
                   engine: str, variant: str) -> tuple[str, str, str]:
    """('queued'|'failed'|'done'|'unknown', job name, conclusion) for one producer cell."""
    job = producer_job_name(engine, variant)
    status, conclusion = (states or {}).get(job, ("", ""))
    if status in PRODUCER_QUEUED_STATES:
        return "queued", job, conclusion
    if status == "completed":
        return ("done" if conclusion in ("", "success", "skipped") else "failed"), job, conclusion
    return "unknown", job, conclusion


def _missing_verdict(engine: str, variant: str, ref: str, state: str, job: str,
                     conclusion: str, reason: str, elapsed_s: float) -> str:
    """The one line that says WHICH failure this is (issue #893), and its remedy."""
    waited = int(elapsed_s) // 60
    if state == "queued":
        return (f"[install] FAIL {engine}/{variant}: BLOCKED — the producer cell {job} is still queued "
                f"after {waited} minutes with no runner: this is the runner queue, not a bad tag. "
                f"{ref} has not been published yet; re-run this job once the engine-image cells have "
                f"started, and do not change the pin.")
    if state == "failed":
        return (f"[install] FAIL {engine}/{variant}: NOT FOUND — the producer cell {job} concluded "
                f"{conclusion or 'unsuccessfully'}, so {ref} was never published "
                f"(last registry error: {reason}). Fix the producer cell, not the wait.")
    if state == "done":
        return (f"[install] FAIL {engine}/{variant}: NOT FOUND — the producer cell {job} concluded "
                f"{conclusion or 'success'} and {ref} was never published "
                f"(last registry error: {reason}). The pin or the publish step needs a look.")
    return (f"[install] FAIL {engine}/{variant}: NOT FOUND — {ref} was never published within "
            f"{waited} minutes and no producer cell state could be read (a host run, or the "
            f"job lacks `actions: read`), so the runner queue cannot be ruled out "
            f"(last registry error: {reason}).")


def wait_published(arch: str, only: list[str] | None = None,
                   timeout_s: int = PUBLISH_WAIT_TIMEOUT_S,
                   poll_s: int = PUBLISH_WAIT_POLL_S,
                   max_queue_s: int = PUBLISH_WAIT_QUEUE_MAX_S,
                   states: dict[str, tuple[str, str]] | None = None,
                   concluded_grace_s: int = PUBLISH_WAIT_CONCLUDED_GRACE_S) -> int:
    """Wait until every image `install` pulls for this backend is published (issue #169).

    No pull, no build, no fallback: a manifest lookup per tag, retried until the tag
    appears or the deadline passes. A tag that never appears fails loudly and is named,
    and the failure says WHICH failure it is (issue #893): `BLOCKED` when the producer
    cell is still queued in the runner queue, `NOT FOUND` when the producer concluded
    and the tag itself is absent.
    """
    if not ei.REGISTRY:
        print("[install] FAIL LLGENIE_REGISTRY is not set: there is nothing to wait for")
        return 1
    want = [(e["engine"], e["variant"], f"{ei.REGISTRY}/{e['tag']}")
            for e in install_plan(arch, only) if e["variant"]]
    if not want:
        print(f"[install] backend {arch}: no engine image to wait for")
        return 0
    print(f"[install] waiting for {len(want)} published image(s) for backend {arch}: "
          + ", ".join(f"{e}/{v}" for e, v, _ in want), flush=True)
    started = time.monotonic()
    deadline = started + timeout_s
    ceiling = started + max_queue_s
    missing, reason, verdict = list(want), {}, {}
    extended = False
    while missing:
        still = []
        for engine, variant, ref in missing:
            digest, err = ei._digest_http(ref)
            if digest:
                print(f"[install] published {ref}", flush=True)
            else:
                reason[ref] = err
                still.append((engine, variant, ref))
        missing = still
        if not missing:
            print(f"[install] every image install pulls is published", flush=True)
            return 0
        # The producer's OWN state decides what an absent tag means (issue #893). A
        # producer that has CONCLUDED has published its tag or never will, so waiting
        # on it further cannot change the answer — but it shortens the budget to a grace
        # period instead of to zero, because a manifest can lag its own push; one that is
        # still queued/in_progress is the runner queue, which is capacity, not a tag.
        current = states if states is not None else producer_job_states()
        verdict = {(e, v): producer_state(current, e, v) for e, v, _ in missing}
        if any(s in ("done", "failed") for s, _, _ in verdict.values()):
            if time.monotonic() >= min(deadline, started + concluded_grace_s):
                break
            time.sleep(poll_s)
            continue
        if any(s == "queued" for s, _, _ in verdict.values()):
            now = time.monotonic()
            if now >= ceiling:
                break
            if not extended:
                extended = True
                print("[install] producer still queued: "
                      + ", ".join(j for _, j, _ in verdict.values())
                      + f" — the runner queue, not the tag, is the delay; keeping the wait "
                        f"alive up to {max_queue_s // 60} minutes (issue #893)", flush=True)
            time.sleep(poll_s)
            continue
        if time.monotonic() >= deadline:
            break
        print(f"[install] not published yet: {', '.join(ref for _, _, ref in missing)}; "
              f"waiting {poll_s}s", flush=True)
        time.sleep(poll_s)
    elapsed = time.monotonic() - started
    for engine, variant, ref in missing:
        state, job, conclusion = verdict.get((engine, variant)) or producer_state(
            states if states is not None else {}, engine, variant)
        print(_missing_verdict(engine, variant, ref, state, job, conclusion,
                               reason.get(ref, ""), elapsed))
    return 1


def install(bindir: Path, arch: str, build: bool, only: list[str] | None = None) -> int:
    if arch == "cuda" and not os.environ.get("LLGENIE_NO_GPU") and not cuda_cdi_ready():
        print("[install] FAIL cuda host without the NVIDIA CDI spec: the engine containers could not "
              "use the host driver. Install nvidia-container-toolkit and run\n"
              "          sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml")
        return 1
    bindir.mkdir(parents=True, exist_ok=True)
    models = os.environ.get("LLGENIE_MODELS_DIR", str(Path.home() / "models"))
    written, failed = {}, []
    plan = install_plan(arch, only)
    print(f"[install] backend {arch}: {', '.join(e['engine'] for e in plan)}"
          f"{'' if build else ' (pull published images only)'}")
    for entry in plan:
        engine = entry["engine"]
        if not entry["variant"]:
            if entry["why"].startswith("unknown"):
                failed.append(engine)
                print(f"[install] FAIL {engine}: {entry['why']}")
            else:
                print(f"[install] {engine}: {entry['why']} - skipped")
            continue
        variant, tag = entry["variant"], entry["tag"]
        tag = ensure_image(engine, variant, build)
        if not tag:
            failed.append(engine)
            why = "the build failed" if build else f"not published in {ei.REGISTRY or '(no LLGENIE_REGISTRY)'}"
            if not ei.runtime_answers(ei.RUNTIME):
                # a CLI with no engine behind it (docker CLI next to Colima's containerd,
                # a stopped VM) is not an unpublished image (issue #112)
                why = RUNTIME_DOWN.format(rt=ei.RUNTIME)
            print(f"[install] FAIL {engine}/{variant}: {why}")
            continue
        out = bindir / script_name(engine)
        plat = ei.image_platform(tag)  # run the image as what it is (no amd64-on-arm64 warning)
        out.write_text(launcher(engine, variant, tag, models, plat))
        out.chmod(0o755)
        written[engine] = (variant, tag, plat)
        print(f"[install] {out} -> {tag}")
    # one shim per llama.cpp tree, named after its server (issue #98):
    #   ~/bin/llama-server  -> stock llama.cpp image (ggml-org, /app/llama-server)
    #   ~/bin/prism-server  -> Prism llama.cpp image (its build-<arch>/bin/llama-server)
    # llgenie_serve.resolve_llama_server picks one by the card's tree.
    for engine, name in SERVER_SHIMS.items():
        hit = written.get(engine)
        if not hit:
            continue
        shim = bindir / name
        if shim.is_symlink() or shim.exists():
            shim.unlink()
        shim.write_text(llama_server_shim(hit[1], hit[0], server_binary(engine, hit[0]), name, hit[2]))
        shim.chmod(0o755)
        print(f"[install] {shim} -> {hit[1]} ({name} in its container)")
    return 1 if failed else 0


def native_launcher(engine: str, python: str | None = None) -> str:
    """Start script for a Metal engine (issue #114). Metal cannot run in a container,
    so the engine runs natively on the host, installed and launched by its skill
    (scripts/engine_skills.py: `install` = the skill's metal steps, `serve` = its
    frozen launch through scripts/engine_runner.py). Same CLI as the image scripts."""
    name = script_name(engine)
    py = python or sys.executable
    es_py = REPO / "scripts" / "engine_skills.py"
    return f"""#!/usr/bin/env bash
# Generated by `make install` (scripts/install_engine_launchers.py). Do not edit.
# {engine} (metal) runs NATIVELY on this Mac: Metal cannot run in a container.
#   {name} --version          engine version (the skill's detect)
#   {name} <model> [port]     serve <model> as llm-local on 127.0.0.1:${{PORT:-11434}}/v1
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"   # uv tool installs (tensorfold, mlx_lm.server, litert-lm)
case "${{1:-}}" in
  --version|-v|version) exec "{py}" "{es_py}" detect {engine} --backend metal ;;
  ""|-h|--help) sed -n '3,5p' "$0"; exit 0 ;;
esac
MODEL="$1"; PORT="${{2:-${{PORT:-11434}}}}"
exec "{py}" "{es_py}" serve {engine} --backend metal --model "$MODEL" --port "$PORT"
"""


def native_state(engine: str) -> dict:
    """Install state of a native Metal engine (missing / outdated / current), as the
    engine picker shows it and ensure_native acts on it."""
    _uv_tool_path()
    return es.native_status(es.get_skill(engine), "metal", {**es.detect_hardware(), "backend": "metal"})


def _uv_tool_path() -> None:
    """`uv tool install` puts executables in ~/.local/bin, often not on a fresh shell's
    PATH: put it there so the skill's detect finds a just-installed engine."""
    local = str(Path.home() / ".local" / "bin")
    if local not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = local + os.pathsep + os.environ.get("PATH", "")


def ensure_native(bindir: Path, engine: str, dry: bool = False) -> int:
    """Metal (issue #114): make the picked engine ready with its skill, whatever is on
    the host: install it when missing, update it when its version is not the skill's
    pinned release (the skill's install steps are idempotent: `uv tool install --force`
    of the pinned tag), keep it when current. Then write its native start script."""
    skill = es.get_skill(engine)
    hw = {**es.detect_hardware(), "backend": "metal"}
    script = bindir / script_name(engine)
    _uv_tool_path()
    st = es.native_status(skill, "metal", hw)
    if st["state"] == "missing":
        print(f"[install] {engine}: not installed -> installing {st['wanted'] or 'it'} natively for metal",
              flush=True)
    elif st["state"] == "outdated":
        print(f"[install] {engine}: installed {st['installed']} != pinned {st['wanted']} -> updating",
              flush=True)
    else:
        print(f"[install] {engine}: installed {st['installed'] or ''} (current)".replace("  ", " "), flush=True)
    if st["state"] != "current":
        rc = es.install(skill, "metal", hw, dry=dry)
        if rc:
            print(f"[install] FAIL {engine}/metal: native install exited {rc}")
            return rc
        if not dry and es.native_status(skill, "metal", hw)["state"] != "current":
            print(f"[install] FAIL {engine}/metal: still not at the pinned {st['wanted']} after installing")
            return 1
    bindir.mkdir(parents=True, exist_ok=True)
    script.write_text(native_launcher(engine))
    script.chmod(0o755)
    print(f"[install] {script} -> {engine} (metal, native)")
    return 0


def ensure(bindir: Path, engine: str, arch: str, build: bool) -> int:
    """`llgenie --pick/--engine`: pull ONE engine's image for this backend (if not
    yet local) and write its start script. Idempotent and fast when present.
    arch=metal: the engine is installed natively instead (ensure_native)."""
    if arch == "metal":
        return ensure_native(bindir, engine)
    script = bindir / script_name(engine)
    variant = variant_for(engine, arch) if (PARAMS / f"{engine}.json").exists() else None
    if not variant:
        print(f"[install] FAIL {engine}: no {arch}/cpu image")
        return 1
    tag = ei.resolve(engine, None, variant)["tag"]
    if script.exists() and tag in script.read_text() and ei.image_exists(tag):
        return 0
    print(f"[install] {engine}: pulling the {variant} image (first use)", flush=True)
    return install(bindir, arch, build, [engine])


VERSION_RE = re.compile(r"\d+\.\d+")
# Lines the container runtime itself prints (never the engine's version), e.g.
#   WARNING: The requested image's platform (linux/amd64) does not match ... (docker)
#   time="..." level=warning msg="force cleanup timed out for container ..." (nerdctl)
RUNTIME_NOISE_RE = re.compile(r'^\s*(WARNING:|time="[^"]*" level=)')


def version_ok(returncode: int, stdout: str, stderr: str) -> tuple[bool, str]:
    """`<script> --version` passed: exit 0 and the engine printed a version number on
    ANY line of stdout or stderr that is not runtime noise (issue #112: the runtime may
    print a warning after the engine's version line, so the last line is not the
    version). Returns (ok, the line to report: the version line, else the last line)."""
    lines = [ln for ln in (stdout + "\n" + stderr).splitlines() if ln.strip()]
    hits = [ln for ln in lines if VERSION_RE.search(ln) and not RUNTIME_NOISE_RE.match(ln)]
    line = hits[-1] if hits else (lines[-1] if lines else "")
    return returncode == 0 and bool(hits), line


def test(bindir: Path) -> int:
    scripts = sorted(bindir.glob(PREFIX + "*"))
    scripts += [bindir / n for n in SERVER_SHIMS.values() if (bindir / n).exists()]
    if not scripts:
        print(f"[test-built-engine] no {PREFIX}* scripts in {bindir}; run make install")
        return 1
    fails = 0
    for s in scripts:
        r = subprocess.run([str(s), "--version"], capture_output=True, text=True, timeout=600)
        ok, line = version_ok(r.returncode, r.stdout, r.stderr)
        fails += not ok
        print(f"[test-built-engine] {'OK  ' if ok else 'FAIL'} {s.name} --version: {line[:150]}")
    print(f"[test-built-engine] {len(scripts) - fails} ok, {fails} failed")
    return 1 if fails else 0


MARKER = "Generated by `make install`"


def uninstall(bindir: Path, purge_images: bool = False) -> int:
    """Undo `make install`: stop running engine containers, remove the start
    scripts and the llama-server shim (only files this script wrote, or a stale
    symlink from the old native install). Engine images are kept as a cache
    unless purge_images; no source tree or model is ever touched."""
    removed = []
    for s in sorted(bindir.glob(PREFIX + "*")):
        if s.is_symlink() or MARKER in s.read_text(errors="ignore"):
            s.unlink()
            removed.append(s.name)
    for n in SERVER_SHIMS.values():
        shim = bindir / n
        if shim.is_symlink() or (shim.is_file() and MARKER in shim.read_text(errors="ignore")):
            shim.unlink()
            removed.append(shim.name)
    r = subprocess.run([ei.RUNTIME, "ps", "-q", "--filter", "name=^llgenie-"], capture_output=True, text=True)
    running = r.stdout.split()
    if running:
        subprocess.run([ei.RUNTIME, "rm", "-f", *running], capture_output=True)
    print(f"[uninstall] removed {len(removed)} file(s) from {bindir}: {' '.join(removed) or '-'}")
    print(f"[uninstall] stopped {len(running)} running llgenie engine container(s)")
    if purge_images:
        r = subprocess.run([ei.RUNTIME, "images", "--format", "{{.Repository}}:{{.Tag}}"],
                           capture_output=True, text=True)
        imgs = [i for i in r.stdout.split() if i.split("/")[-2:-1] == ["llgenie"] or i.startswith("llgenie/")]
        imgs = [i for i in imgs if not i.startswith(("llgenie/test:", "llgenie/openspec:"))]
        if imgs:
            subprocess.run([ei.RUNTIME, "rmi", "-f", *imgs], capture_output=True)
        print(f"[uninstall] removed {len(imgs)} engine image(s)")
    else:
        print("[uninstall] engine images kept as a cache (make uninstall PURGE_IMAGES=1 removes them)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bin", default=str(Path.home() / "bin"))
    ap.add_argument("--arch", default=None, help="cpu|cuda|rocm|vulkan (default: detected)")
    ap.add_argument("--no-build", action="store_true", help="only pull published images (default)")
    ap.add_argument("--build", action="store_true", help="build an image that is not published")
    ap.add_argument("--ensure", default="", help="pull one engine's image for this backend + its start script")
    ap.add_argument("--test", action="store_true", help="run every start script with --version")
    ap.add_argument("--engines", default="", help="comma-separated engine ids, or 'all' (default: llama.cpp + Prism)")
    ap.add_argument("--uninstall", action="store_true", help="remove what install wrote, stop engine containers")
    ap.add_argument("--purge-images", action="store_true", help="with --uninstall: also remove the engine images")
    ap.add_argument("--wait-published", action="store_true",
                    help="wait until every image install pulls for this backend is published (issue #169)")
    a = ap.parse_args(argv)
    bindir = Path(a.bin).expanduser()
    if a.wait_published:
        # no container, no pull: a registry manifest lookup per tag (issue #169)
        return wait_published(a.arch or detected_arch(),
                              [e for e in a.engines.split(",") if e] or None)
    # Intel macOS (macos-15-intel) has no native Metal engines and no container
    # image is pulled for it. The default install (no --ensure) writes nothing,
    # test-built-engine has nothing to version-test, and uninstall has nothing
    # to remove: all three are a no-op that exits 0. An explicit non-metal
    # --arch is still REFUSED (the health / top-tier job asserts `--arch cpu`
    # fails, issue #120). An explicit `--ensure <engine>` still installs that
    # engine natively for metal (the llgenie pick path; the hermetic TensorFold
    # tests drive it on the Intel runner via LLAMA_BACKEND=metal). Apple Silicon
    # still installs and tests every native-Metal engine; Linux still pulls.
    intel_mac = sys.platform == "darwin" and not _macos_silicon()
    if intel_mac and not a.ensure and (a.uninstall or a.test or not a.arch):
        if a.uninstall:
            print("[install] macOS x86_64: nothing was installed; nothing to uninstall", flush=True)
        if a.test:
            print("[test-built-engine] macOS x86_64: no start scripts were written; nothing to test",
                  flush=True)
        return 0
    if a.uninstall:
        return uninstall(bindir, a.purge_images)
    if a.test:
        return test(bindir)
    # Nothing starts Colima, and macOS never starts or pulls an engine image
    # (issue #120), even when --arch is passed. Only Apple Silicon writes native
    # Metal start scripts. An Intel Mac has no Metal engines and must not pull a
    # cpu image either. Linux still checks the runtime and pulls this host's images.
    arch = a.arch or detected_arch()
    if sys.platform == "darwin":
        if not _macos_silicon():
            if a.arch and a.arch != "metal":
                print(f"[install] refusing --arch {a.arch}: Intel macOS has no Metal engines and "
                      f"never pulls an engine image (issue #120)", flush=True)
                return 1
            if not a.ensure:
                print("[install] macOS x86_64: no native Metal engines and no engine image is pulled",
                      flush=True)
                return 0
            print("[install] macOS x86_64: ensuring natively for metal (explicit --ensure)",
                  flush=True)
        else:
            print("[install] macOS: native Metal only; no engine image is pulled and Colima is not started",
                  flush=True)
        if a.arch and a.arch != "metal":
            print(f"[install] refusing --arch {a.arch}: macOS never starts an engine image (issue #120)",
                  flush=True)
            return 1
        if a.ensure:
            return ensure_native(bindir, a.ensure)
        import model_engine_pick as mp
        failed = 0
        for engine in sorted(mp.metal_engines()):
            failed = ensure_native(bindir, engine) or failed
        return 1 if failed else 0
    if not (a.ensure and arch == "metal"):
        ei.ensure_container_env()
    if a.ensure:
        return ensure(bindir, a.ensure, arch, a.build)
    only = [e for e in a.engines.split(",") if e]
    return install(bindir, arch, a.build and not a.no_build, only or None)


if __name__ == "__main__":
    sys.exit(main())
