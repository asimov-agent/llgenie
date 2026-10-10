#!/usr/bin/env python3
"""Build / run llgenie engine images (one per engine x backend x GPU arch).

  python3 scripts/engine_image.py build-base <backend> [--push]       # shared toolchain base
  python3 scripts/engine_image.py build <engine> [--backend B] [--variant V] [--force] [--push]
  python3 scripts/engine_image.py run   <engine> [--backend B] [--variant V] --model M [--port 11434]
  python3 scripts/engine_image.py tag   <engine> [--backend B] [--variant V]
  python3 scripts/engine_image.py matrix [--json]     # every engine x variant in params/

Images are built ONLY from the committed, frozen parameters in
containers/engines/params/<engine>.json (generated from the skill by
`make engine-params`); skills are never read here. The variant defaults to the
one matching this machine's GPU arch (e.g. cuda-sm89), else <backend>-portable.

`build` is a no-op when the tag already exists locally (or can be pulled from
LLGENIE_REGISTRY): the tag encodes the pin, a hash of the frozen variant +
Dockerfile + entrypoint + runner, and the variant, so a rebuild happens only
when the generated parameters change.

`run` starts the image detached, publishes the OpenAI API on
127.0.0.1:<port> (host) -> 11434 (container), mounts ~/models at /models,
waits until /v1/models answers and prints the base_url for AI harnesses.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine_skills as es  # noqa: E402

def runtime_answers(rt: str) -> bool:
    """The container engine behind `rt` is reachable (`<rt> info` exits 0)."""
    if not shutil.which(rt):
        return False
    try:
        return subprocess.run([rt, "info"], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


# ---- macOS: Docker may run in a Colima VM (issue #112) -------------------------
# llgenie never starts, stops, or rewrites that VM (issue #120). A stopped VM or
# broken VM DNS is reported; the operator starts the engine. Linux is never touched.
COLIMA_DNS = ("1.1.1.1", "8.8.8.8")
DNS_PROBE_HOST = "ghcr.io"  # the registry every engine image comes from


def _colima(*args: str, timeout: int = 60) -> subprocess.CompletedProcess | None:
    """Colima is never invoked (issue #120). The args are ignored so no VM is started,
    stopped, or SSH'd into."""
    del args, timeout
    print("[llgenie] refusing to run colima (issue #120)", flush=True)
    return None


def vm_dns_ok(host: str = DNS_PROBE_HOST) -> bool:
    """Never probes the Colima VM. A live runtime is enough; Colima is not called."""
    del host
    return runtime_answers(RUNTIME)


def colima_health() -> str:
    """'' when the container runtime answers, else 'stopped'. Never calls Colima."""
    return "" if runtime_answers(RUNTIME) else "stopped"


def colima_repair_command() -> list[str]:
    """The command an operator would run. llgenie never executes it (issue #120)."""
    return ["colima", "start", *[a for ip in COLIMA_DNS for a in ("--dns", ip)]]


def vm_dns_fix_command() -> list[str]:
    """Point the running VM at COLIMA_DNS right away (its /etc/resolv.conf), and restart
    dockerd so the daemon's own resolver picks them up."""
    conf = "".join(f"nameserver {ip}\\n" for ip in COLIMA_DNS)
    return ["ssh", "--", "sudo", "sh", "-c",
            f"printf '{conf}' > /etc/resolv.conf && (systemctl restart docker 2>/dev/null || true)"]


def ensure_container_env(platform_name: str | None = None) -> bool:
    """Report whether the container runtime answers. Never starts Colima (issue #120):
    a stopped VM, a missing runtime, or broken VM DNS is the operator's job. True when
    the runtime answers, and always True off macOS (Linux brings its own engine)."""
    if (platform_name or sys.platform) != "darwin":
        return True
    if runtime_answers(RUNTIME):
        return True
    print(f"[llgenie] '{RUNTIME}' does not answer; Colima is not started (issue #120)", flush=True)
    return False


RUNTIME = os.environ.get("RUNTIME") or "docker"  # docker only (issue #112)
# The CI-published, CI-tested images. The default lives here, not only in the Makefile, so
# `llgenie` run straight from ~/bin pulls a picked engine on first use with no setup.
# LLGENIE_REGISTRY overrides it (a fork's GHCR); LLGENIE_REGISTRY= (empty) = local images only.
DEFAULT_REGISTRY = "ghcr.io/asimov-agent"
REGISTRY = os.environ.get("LLGENIE_REGISTRY", DEFAULT_REGISTRY).rstrip("/").lower()  # OCI refs must be lowercase


def _sh(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    print("[engine-image] $", " ".join(cmd), flush=True)
    return subprocess.run(cmd, **kw)


def image_exists(tag: str) -> bool:
    return subprocess.run([RUNTIME, "image", "inspect", tag], capture_output=True).returncode == 0


def image_platform(tag: str) -> str:
    """os/arch[/variant] the local image was built for (e.g. linux/amd64), or ""."""
    try:
        r = subprocess.run([RUNTIME, "image", "inspect", "-f",
                            "{{.Os}}/{{.Architecture}}{{if .Variant}}/{{.Variant}}{{end}}", tag],
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    out = r.stdout.strip()
    return out if r.returncode == 0 and re.fullmatch(r"[a-z0-9]+/[a-z0-9_]+(/[a-z0-9]+)?", out) else ""


def load_params(engine: str) -> dict:
    """Generated params only (never a skill). Accepts the id or the registry engine name."""
    path = es.params_path(engine)
    if not path.exists():
        for cand in es.PARAMS_DIR.glob("*.json"):
            if json.loads(cand.read_text()).get("engine") == engine:
                path = cand
                break
    if not path.exists():
        raise SystemExit(f"[engine-image] no frozen params for {engine} ({path}); the engine has no "
                         f"container image (metal-only, opt-out or not servable) or run: make engine-params")
    return json.loads(path.read_text())


def resolve(engine: str, backend: str | None, variant: str | None = None) -> dict:
    params = load_params(engine)
    if variant:
        if variant not in params["variants"]:
            raise SystemExit(f"[engine-image] {engine}: no variant {variant} (have {', '.join(params['variants'])})")
        return es.image_spec(params, variant)
    hw = es.detect_hardware()
    b = backend or hw["backend"]
    return es.image_spec(params, es.pick_variant(params, b, {**hw, "backend": b}))


def _buildx(tag: str, ctx: str, push: bool, cache_ref: str) -> int:
    """docker buildx with a registry layer cache: unchanged layers are reused
    across CI runs and machines (cache_ref = <registry>/<name>:buildcache)."""
    if push and REGISTRY:
        # push ONLY the registry-qualified tag (a bare llgenie/... tag would go to Docker Hub)
        cmd = [RUNTIME, "buildx", "build", "-t", f"{REGISTRY}/{tag}",
               "--cache-from", f"type=registry,ref={cache_ref}",
               "--cache-to", f"type=registry,ref={cache_ref},mode=max", "--push", ctx]
        rc = _sh(cmd).returncode
        if rc == 0:  # make the image available locally under its bare tag too
            _sh([RUNTIME, "pull", f"{REGISTRY}/{tag}"], capture_output=True)
            _sh([RUNTIME, "tag", f"{REGISTRY}/{tag}", tag], capture_output=True)
        return rc
    # Local build (PRs from forks have no push rights): the `default` (docker)
    # builder sees locally loaded base images; the published cache is read-only.
    # Only name it when it exists — a fresh Colima on the macOS runner has no
    # builder called "default" and buildx errors instead of falling back.
    cmd = [RUNTIME, "buildx", "build"]
    if _sh([RUNTIME, "buildx", "inspect", "default"], capture_output=True).returncode == 0:
        cmd += ["--builder", "default"]
    cmd += ["-t", tag, "--load"]
    if REGISTRY:
        cmd += ["--cache-from", f"type=registry,ref={cache_ref}"]
    return _sh(cmd + [ctx]).returncode


def _available(tag: str) -> bool:
    """Local image, or published one (pulled + retagged): no rebuild needed."""
    if image_exists(tag):
        return True
    if REGISTRY and _sh([RUNTIME, "pull", f"{REGISTRY}/{tag}"], capture_output=True).returncode == 0:
        _sh([RUNTIME, "tag", f"{REGISTRY}/{tag}", tag], check=True)
        return True
    return False


def build_base(backend: str, force: bool = False, push: bool = False) -> int:
    """Shared toolchain base for one backend (containers/engines/base/Dockerfile.<backend>)."""
    tag = es.base_tag(backend)
    if not force and _available(tag):
        print(f"[engine-image] base {tag} available -> no rebuild")
        return 0
    with tempfile.TemporaryDirectory(prefix="llgenie-base-") as ctx:
        shutil.copy2(es.BASE_DIR / f"Dockerfile.{backend}", Path(ctx) / "Dockerfile")
        rc = _buildx(tag, ctx, push, f"{REGISTRY}/{es.base_image_name(backend)}:buildcache")
    print(f"[engine-image] {'built' if rc == 0 else 'FAIL'} base {tag}")
    return rc


def build(spec: dict, force: bool = False, push: bool = False) -> int:
    tag = spec["tag"]
    if not force and _available(tag):
        print(f"[engine-image] {tag} available -> no rebuild")
        return 0
    dockerfile = es.REPO_ROOT / spec["dockerfile"]
    if not dockerfile.exists():
        raise SystemExit(f"[engine-image] missing {spec['dockerfile']}; run: make generate-engine-params")
    text = dockerfile.read_text()
    base = es.base_tag(spec["backend"])
    if f"FROM {base}" in text:  # compiled engine on the shared toolchain base
        rc = build_base(spec["backend"], push=push)
        if rc:
            return rc
        if REGISTRY and push:  # the published base must be addressable by the FROM line
            text = text.replace(f"FROM {base}", f"FROM {REGISTRY}/{base}")
    params = json.loads((es.REPO_ROOT / spec["params_file"]).read_text())
    variant = {**params["variants"][spec["variant"]], "pinned": params["pinned"], "repo": params["repo"]}
    with tempfile.TemporaryDirectory(prefix="llgenie-ctx-") as ctx:
        c = Path(ctx)
        (c / "Dockerfile").write_text(text)
        shutil.copy2(es.CONTAINER_DIR / "entrypoint.sh", c / "entrypoint.sh")
        shutil.copy2(es.REPO_ROOT / "scripts" / "engine_runner.py", c / "engine_runner.py")
        (c / "params.json").write_text(json.dumps(variant, indent=2) + "\n")
        rc = _buildx(tag, ctx, push, f"{REGISTRY}/{tag.split(':')[0]}:buildcache-{spec['variant']}")
    if rc:
        print(f"[engine-image] FAIL build {tag} (exit {rc})")
        return rc
    print(f"[engine-image] built {tag} from {spec['dockerfile']}" + (f" and pushed to {REGISTRY}" if push and REGISTRY else ""))
    return 0


def container_model(model: str, models_dir: Path) -> str:
    """Host path under ~/models -> /models/...; anything else (HF repo id) as is."""
    p = Path(model).expanduser()
    if p.exists():
        try:
            return "/models/" + str(p.resolve().relative_to(models_dir.resolve()))
        except ValueError:
            raise SystemExit(f"[engine-image] model must live under {models_dir} (mounted at /models): {p}")
    return model


def run(spec: dict, model: str, port: int, name: str, models_dir: Path, wait: float) -> int:
    tag = spec["tag"]
    if not image_exists(tag):
        print(f"[engine-image] {tag} not built; run: make engine-image ENGINE={spec['id']} BACKEND={spec['backend']}")
        return 1
    subprocess.run([RUNTIME, "rm", "-f", name], capture_output=True)
    env = ["-e", f"LLGENIE_MODEL={container_model(model, models_dir)}"]
    for k in ("HF_TOKEN", "LLGENIE_DRAFTER"):
        if os.environ.get(k):
            env += ["-e", k]  # value passed from the environment, never on the command line
    cmd = [RUNTIME, "run", "-d", "--name", name, "-p", f"127.0.0.1:{port}:{spec['port']}",
           "-v", f"{models_dir}:/models", *spec["run_args"], *env, tag]
    if _sh(cmd).returncode:
        return 1
    base = f"http://127.0.0.1:{port}/v1"
    end = time.time() + wait
    while time.time() < end:
        state = subprocess.run([RUNTIME, "inspect", "-f", "{{.State.Running}}", name],
                               capture_output=True, text=True).stdout.strip()
        if state != "true":
            _sh([RUNTIME, "logs", "--tail", "60", name])
            print(f"[engine-image] FAIL {name} exited")
            return 1
        try:
            ids = [m["id"] for m in json.load(urllib.request.urlopen(base + "/models", timeout=3))["data"]]  # noqa: S310
            print(f"[engine-image] READY {spec['id']}/{spec['backend']}  base_url={base}  model=llm-local  "
                  f"(served ids: {ids})  container={name}")
            return 0
        except Exception:
            time.sleep(2)
    print(f"[engine-image] FAIL {name} not ready after {wait:.0f}s; see: {RUNTIME} logs {name}")
    return 1


def test_image(spec: dict) -> int:
    """GPU images on GPU-less runners: start the image through its entrypoint and
    check the engine binary runs (`entrypoint.sh detect`) and the image metadata
    (`entrypoint.sh info`: port 11434, model llm-local). Serving needs the GPU."""
    tag = spec["tag"]
    if not _available(tag):
        print(f"[engine-image] {tag} not built")
        return 1
    rc = 0
    for cmd in (["info"], ["detect"]):
        r = subprocess.run([RUNTIME, "run", "--rm", tag, *cmd], capture_output=True, text=True)
        print(f"[engine-image] {spec['id']}/{spec['variant']} entrypoint {cmd[0]}: "
              f"{(r.stdout or r.stderr).strip().splitlines()[-1:] or ['']}")
        if cmd == ["info"] and ("port=11434" not in r.stdout or "model=llm-local" not in r.stdout):
            rc = 1
        if cmd == ["detect"] and (r.returncode != 0 or not re.search(r"\d+\.\d+", r.stdout + r.stderr)):
            # the binary's own --version/--help must exit 0 and print a version
            print(r.stdout[-2000:], r.stderr[-2000:])
            rc = 1
    print(f"[engine-image] {'OK' if rc == 0 else 'FAIL'} image test {tag}")
    return rc


def push(spec: dict) -> int:
    """Push an already built AND tested local image to the registry (GHCR).
    Called only after the post-build test stage passed (CI: main branch only)."""
    if not REGISTRY:
        print("[engine-image] LLGENIE_REGISTRY not set; nothing to push")
        return 1
    tag = spec["tag"]
    if not image_exists(tag):
        print(f"[engine-image] {tag} not built locally; build + test it first")
        return 1
    ref = f"{REGISTRY}/{tag}"
    latest = f"{REGISTRY}/{tag.split(':')[0]}:{spec['variant']}"  # moving per-arch tag
    for r in (ref, latest):
        if _sh([RUNTIME, "tag", tag, r]).returncode or _sh([RUNTIME, "push", r]).returncode:
            print(f"[engine-image] FAIL push {r}")
            return 1
        print(f"[engine-image] pushed {r}")
    return 0


def _have_runtime() -> bool:
    """True when the container runtime is installed. A function so tests can replace it."""
    import shutil
    return shutil.which(RUNTIME) is not None


def _digest(ref: str, attempts: int = 4) -> str:
    """Manifest digest of a registry ref, "" when it does not exist. GHCR manifest
    lookups intermittently time out (seen: freetoken:rocm empty after 60 s while the
    tag existed with the right digest), so a failed lookup is retried with backoff.
    Docker is used when it is installed; otherwise the registry HTTP API, so a host
    with no container engine (the macOS unit job) can still read a published digest."""
    import shutil
    for i in range(attempts):
        if _have_runtime():
            r = _sh([RUNTIME, "buildx", "imagetools", "inspect", ref, "--format", "{{json .Manifest.Digest}}"],
                    capture_output=True, text=True)
            d = r.stdout.strip().strip('"') if r.returncode == 0 else ""
            err = (getattr(r, "stderr", "") or "").strip()[-200:]
        else:
            d, err = _digest_http(ref)
        if d:
            return d
        if i + 1 < attempts:
            print(f"[engine-image] digest lookup for {ref} failed (attempt {i + 1}/{attempts}): "
                  f"{err}; retrying", flush=True)
            time.sleep(5 * (i + 1))
    return ""


def _digest_http(ref: str) -> tuple:
    """Digest of a registry ref via the registry HTTP API. ("", reason) on failure."""
    import urllib.request
    host, _, rest = ref.partition("/")
    name, _, tag = rest.rpartition(":")
    try:
        tok = urllib.request.urlopen(
            f"https://{host}/token?service={host}&scope=repository:{name}:pull", timeout=30).read()
        token = __import__("json").loads(tok)["token"]
    except Exception as e:  # noqa: BLE001 - no token means the registry is unreachable
        return "", str(e)[-200:]
    url = f"https://{host}/v2/{name}/manifests/{tag}"
    req = urllib.request.Request(url, method="HEAD", headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.oci.image.index.v1+json, "
                  "application/vnd.docker.distribution.manifest.list.v2+json, "
                  "application/vnd.oci.image.manifest.v1+json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.headers.get("Docker-Content-Digest", ""), ""
    except Exception as e:  # noqa: BLE001 - a missing or unreachable tag is "not published"
        return "", str(e)[-200:]


def pull_published(spec: dict) -> str:
    """Pull the image AS PUBLISHED (issue #102): drop any local copy first, pull the
    pinned tag from the registry, and check it has the same digest as the moving
    :<arch> tag. Returns the local tag, or "" on failure. Never builds."""
    if not REGISTRY:
        print("[engine-image] LLGENIE_REGISTRY not set; nothing published to test")
        return ""
    tag = spec["tag"]
    ref = f"{REGISTRY}/{tag}"
    latest = f"{REGISTRY}/{tag.split(':')[0]}:{spec['variant']}"
    _sh([RUNTIME, "rmi", "-f", tag, ref], capture_output=True)  # no local build may be used
    pulled = False
    for i in range(6):
        if _sh([RUNTIME, "pull", ref]).returncode == 0:
            pulled = True
            break
        # A push run publishes this tag from a parallel engine-image job. That job
        # can still be pushing when install starts, so a missing tag is retried.
        if i + 1 < 6:
            print(f"[engine-image] {ref} not published yet (attempt {i + 1}/6); retrying", flush=True)
            time.sleep(20 * (i + 1))
    if not pulled:
        print(f"[engine-image] FAIL {ref} is not published")
        return ""
    d_ref, d_latest = _digest(ref), _digest(latest)
    if not d_ref or d_ref != d_latest:
        print(f"[engine-image] FAIL digest mismatch: {ref}={d_ref or '?'} {latest}={d_latest or '?'}")
        return ""
    _sh([RUNTIME, "tag", ref, tag], check=True)
    print(f"[engine-image] pulled published {ref} ({d_ref}), same digest as {latest}")
    return tag


def container_name(spec: dict) -> str:
    return f"llgenie-{spec['id'].replace('.', '-')}-{spec['backend']}"


# CI builds these variants of every engine (in parallel, one job each). The
# full per-arch list stays buildable on demand with make build-engine ARCH=.
CI_VARIANTS = ("cpu", "cuda", "rocm", "vulkan")   # one image per backend (fat GPU arch lists)
# Engine x arch images that are NOT built, published, installed or tested until
# their tracking issue is fixed (CI run 37398159369 on PR #101). The single
# source of truth: `matrix(ci=True)` drops them, make install never pulls them
# (cpu fallback when the engine has one), llgenie never offers them.
DISABLED = {
    ("llama.cpp-laurentzuijdwijk", "cuda"): "#103 build-time --help needs libcuda.so.1",
    ("exllamav3-rocm", "rocm"): "#103 cuda_shim needs torch >= 2.13 ROCm headers",
    ("llama.cpp-prism", "cuda"): "#103 fat CUDA build runs > 50 min on hosted runners",
    ("llama.cpp-prism", "rocm"): "#103 fat ROCm build runs > 50 min on hosted runners",
}


# Engines whose GPU images (cuda/rocm/vulkan) fall back to CPU when started
# without GPU devices, so the published-image test can chat with them on a
# GPU-less hosted runner. The other GPU engines (vLLM, SGLang, TensorRT-LLM,
# FreeToken, mlx[cuda], TensorFold) refuse to start without a GPU (CI run
# 37407553595: "No HIP GPUs", "only 0 device(s) visible", libcuda.so.1): their
# published GPU images get the version test, their cpu images the chat test.
CPU_FALLBACK = {"llama.cpp", "llama.cpp-prism", "llama.cpp-laurentzuijdwijk", "ollama"}


def chat_testable(engine: str, variant: str) -> bool:
    """Can the published image answer "hi" on a GPU-less runner?"""
    return variant == "cpu" or engine in CPU_FALLBACK


def disabled(engine: str, variant: str) -> str:
    """The tracking reason when this engine x arch image is disabled, else ''."""
    return DISABLED.get((engine, variant), "")
SMOKE_SKIP = {"tensorrt-llm", "sglang", "tensorfold", "freetoken"}  # cuda-only servers, no cpu smoke


def matrix(ci: bool = False) -> list[dict]:
    out = []
    for path in sorted(es.PARAMS_DIR.glob("*.json")):
        params = json.loads(path.read_text())
        for key, v in params["variants"].items():
            if ci and (key not in CI_VARIANTS or disabled(params["id"], key)):
                continue
            serve = key == "cpu" and params["id"] not in SMOKE_SKIP
            out.append({"engine": params["id"], "backend": v["backend"], "variant": key,
                        "smoke": serve, "test": "serve" if serve else "detect",
                        "chat": "yes" if chat_testable(params["id"], key) else ""})
    return out


def ci_status(run: str = "", watch: bool = False, interval: int = 60) -> int:
    """Summarise the CI engine-image jobs (gh CLI) for the current branch."""
    branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True,
                            text=True, cwd=es.REPO_ROOT).stdout.strip()
    while True:
        rid = run or subprocess.run(
            ["gh", "run", "list", "--branch", branch, "--workflow", "CI", "--limit", "1",
             "--json", "databaseId", "-q", ".[0].databaseId"], capture_output=True, text=True).stdout.strip()
        if not rid:
            print(f"[ci-engine-images] no CI run for branch {branch}")
            return 1
        data = json.loads(subprocess.run(["gh", "run", "view", rid, "--json", "jobs,status,conclusion,url"],
                                         capture_output=True, text=True, check=True).stdout)
        jobs = [j for j in data["jobs"] if j["name"].startswith("engine-image-")]
        counts: dict = {}
        for j in jobs:
            state = j["conclusion"] or j["status"]
            counts[state] = counts.get(state, 0) + 1
        print(f"[ci-engine-images] run {rid} ({data['status']}) {data['url']}")
        print("  " + "  ".join(f"{k}={v}" for k, v in sorted(counts.items())) + f"  total={len(jobs)}")
        for j in sorted(jobs, key=lambda j: j["name"]):
            if (j["conclusion"] or "") not in ("success", "skipped"):
                print(f"  {j['conclusion'] or j['status']:12} {j['name']}")
        if not watch or data["status"] == "completed":
            return 0 if all((j["conclusion"] or "") in ("success", "skipped") for j in jobs) and jobs else 1
        time.sleep(interval)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="llgenie engine images")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("build", "run", "tag", "stop", "test-image", "push", "pull-published"):
        p = sub.add_parser(n)
        p.add_argument("engine")
        p.add_argument("--backend", choices=es.CONTAINER_BACKENDS, default=None)
        p.add_argument("--variant", default=None, help="cpu | cuda | rocm | vulkan (one image per backend)")
        if n == "build":
            p.add_argument("--force", action="store_true")
            p.add_argument("--push", action="store_true")
        if n == "run":
            p.add_argument("--model", required=True)
            p.add_argument("--port", type=int, default=11434)
            p.add_argument("--name", default="")
            p.add_argument("--models-dir", default=str(Path.home() / "models"))
            p.add_argument("--wait", type=float, default=900)
    cs = sub.add_parser("ci-status")
    cs.add_argument("--run", default="")
    cs.add_argument("--watch", action="store_true")
    bb = sub.add_parser("build-base")
    bb.add_argument("backend", choices=es.CONTAINER_BACKENDS)
    bb.add_argument("--force", action="store_true")
    bb.add_argument("--push", action="store_true")
    sub.add_parser("ensure-env", help="report whether the container runtime answers; never starts Colima")
    m = sub.add_parser("matrix")
    m.add_argument("--json", action="store_true")
    m.add_argument("--ci", action="store_true", help="only the variants CI builds")
    a = ap.parse_args(argv)

    if a.cmd == "build-base":
        return build_base(a.backend, a.force, a.push)
    if a.cmd == "ci-status":
        return ci_status(a.run, a.watch)
    if a.cmd == "ensure-env":
        return 0 if ensure_container_env() else 1
    if a.cmd == "matrix":
        rows = matrix(a.ci)
        print(json.dumps({"include": rows}) if a.json else
              "\n".join(f"{r['engine']:28} {r['variant']:18} {'smoke' if r['smoke'] else ''}" for r in rows))
        return 0
    spec = resolve(a.engine, a.backend, a.variant)
    if a.cmd == "tag":
        print(spec["tag"])
        return 0
    if a.cmd == "build":
        return build(spec, a.force, a.push)
    if a.cmd == "pull-published":
        return 0 if pull_published(spec) else 1
    if a.cmd == "push":
        return push(spec)
    if a.cmd == "test-image":
        return test_image(spec)
    if a.cmd == "stop":
        return subprocess.run([RUNTIME, "rm", "-f", container_name(spec)]).returncode
    name = a.name or container_name(spec)
    return run(spec, a.model, a.port, name, Path(a.models_dir).expanduser(), a.wait)


if __name__ == "__main__":
    sys.exit(main())
