#!/usr/bin/env python3
"""Build / run llgenie engine images (one per engine x backend x GPU arch).

  python3 scripts/engine_image.py build-base <backend> [--push]       # shared toolchain base
  python3 scripts/engine_image.py build <engine> [--backend B] [--variant V] [--force] [--push]
  python3 scripts/engine_image.py run   <engine> [--backend B] [--variant V] --model M [--port 11434]
  python3 scripts/engine_image.py tag   <engine> [--backend B] [--variant V]
  python3 scripts/engine_image.py matrix [--json]     # every engine x variant in params/

Images are built ONLY from the committed, frozen parameters in
containers/engines/params/<engine>.json (generated from the skill by
`make engine-params`). The build does not read skills. The binary-file check
reads the same generated manifest (containers/engines/binaries.json: the file
each image must contain + the version/help flags it answers), never a skill.
The variant defaults to the
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
import hashlib
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
import hf_auth  # noqa: E402

# Generated with the params (make generate-engine-params): engine -> variant ->
# {binary, flags}. The binary-file check reads it instead of a skill, so the
# probe checks the same generated files the image was built from (issue #204).
BINARIES_FILE = es.BINARIES_PATH


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


def ensure_nvidia_modeset(run_args: list[str]) -> None:
    """Create /dev/nvidia-modeset before CDI injection (issue #157).

    nvidia-container-toolkit's CDI spec stats /dev/nvidia-modeset. The
    nvidia_modeset module can be loaded while that node (195, 254) was never
    created, and docker then refuses `--device nvidia.com/gpu=all`.
    nvidia-modprobe is setuid and creates the node.
    """
    if "nvidia.com/gpu=all" not in run_args or os.path.exists("/dev/nvidia-modeset"):
        return
    modprobe = shutil.which("nvidia-modprobe")
    if modprobe:
        subprocess.run([modprobe, "-c", "0", "-m", "-u"], check=False)
    if not os.path.exists("/dev/nvidia-modeset"):
        raise SystemExit(
            "[llgenie] /dev/nvidia-modeset is missing, so NVIDIA CDI cannot inject the GPU.\n"
            "[llgenie] create it with: nvidia-modprobe -m")


def run(spec: dict, model: str, port: int, name: str, models_dir: Path, wait: float) -> int:
    tag = spec["tag"]
    if not image_exists(tag):
        print(f"[engine-image] {tag} not built; run: make engine-image ENGINE={spec['id']} BACKEND={spec['backend']}")
        return 1
    ensure_nvidia_modeset(spec["run_args"])
    subprocess.run([RUNTIME, "rm", "-f", name], capture_output=True)
    tok = hf_auth.hf_token()
    if tok:
        os.environ["HF_TOKEN"] = tok  # docker -e HF_TOKEN reads it; the value stays off argv
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


# Proves one engine file: it exists, and it answers EVERY flag the engine's manifest documents, plus
# the standard trio (the flags a user actually types), tried one at a time (issue #580).
#
# WHY every flag and not the first: this probe used to `exit 0` on the first flag that answered, so a
# release that dropped `--help` — or a binary that answers `--version` and nothing else — passed the
# bump's CI and broke the first user who typed `-h`. The verdict is now the caller's, one line per
# flag, so a dead flag is visible instead of masked.
#
# A `.py` file is the server itself (exllamav3 server.py) and is run with python3.
# Exit codes: 0 = the file was found and every flag was tried (the verdict is in the LG-FLAG lines),
#             1 = the file is missing.
BINARY_PROBE = """
bin=$1
shift
path=
# Portable timeout: GNU `timeout` (Linux) or coreutils `gtimeout` (macOS), else none.
# Production runs inside a Linux container where `timeout` exists; the host-side
# hermetic test on macOS must still work without it.
TO=
if command -v timeout >/dev/null 2>&1; then TO="timeout 30"
elif command -v gtimeout >/dev/null 2>&1; then TO="gtimeout 30"
fi
if [ -f "$bin" ]; then
  path=$bin
else
  path=$(command -v "$bin" 2>/dev/null || true)
fi
if [ -z "$path" ] || [ ! -f "$path" ]; then
  echo "missing binary file: $bin" >&2
  exit 1
fi
echo "binary file: $path"
i=0
for flag in "$@"; do
  i=$((i+1))
  out="/tmp/llgenie-bin.$i.out"
  if [ "${path##*.}" = py ]; then
    $TO python3 "$path" "$flag" >"$out" 2>&1
  else
    $TO "$path" "$flag" >"$out" 2>&1
  fi
  rc=$?
  # BSD `wc -c` pads its count with spaces ("      12") while GNU does not, so strip them here: a
  # padded count broke the verdict parser on the macOS runner (issue #580, caught by macos / unit).
  bytes=$(wc -c <"$out" 2>/dev/null | tr -d ' ' || true)
  [ -n "$bytes" ] || bytes=0
  # One verdict per flag: the caller decides, this probe never short-circuits.
  echo "LG-FLAG $flag $rc $bytes"
  echo "LG-OUT-BEGIN $flag"
  tail -c 600 "$out" 2>/dev/null || true
  echo "LG-OUT-END $flag"
done
exit 0
"""

#: The flags a user types at an engine binary. Probed ALWAYS, whatever the manifest documents, so the
#: log shows a dead spelling instead of hiding it behind a working sibling (issue #580).
TYPED_FLAGS = ("--version", "-h", "--help", "-V")

#: The spellings that answer the "what version is this" and "show me the flags" questions. A release
#: that drops a whole family is the regression this asserts; an engine that spells one member is fine.
VERSION_FAMILY = ("--version", "-V")
HELP_FAMILY = ("-h", "--help")

# The standard trio a server binary is expected to answer, kept as the fallback for an engine whose
# manifest documents nothing (issue #580). See TYPED_FLAGS for the always-probed set.
FALLBACK_FLAGS = ("--version", "-h", "--help")

#: One verdict line per flag, as BINARY_PROBE prints it. `\s+` on purpose: a platform's own `wc` may
#: pad its count, and a probe whose parser only understands Linux spacing is a green Linux / red macOS.
_LG_FLAG = re.compile(r"^LG-FLAG (\S+)\s+(-?\d+)\s+(\d+)$")
_LG_OUT_BEGIN = re.compile(r"^LG-OUT-BEGIN (\S+)$")
_LG_OUT_END = re.compile(r"^LG-OUT-END (\S+)$")


def parse_probe(text: str) -> dict[str, dict]:
    """{flag: {rc, bytes, output}} from the probe's own per-flag verdict lines (issue #580).

    Pure: the probe's stdout in, a decision-ready mapping out. A flag with no verdict line is absent,
    so "the probe never ran it" can never be read as "it answered".
    """
    verdicts: dict[str, dict] = {}
    lines = (text or "").splitlines()
    i = 0
    while i < len(lines):
        m = _LG_FLAG.match(lines[i])
        if not m:
            i += 1
            continue
        flag, rc, size = m.group(1), int(m.group(2)), int(m.group(3))
        body: list[str] = []
        j = i + 1
        if j < len(lines):
            begin = _LG_OUT_BEGIN.match(lines[j])
            if begin and begin.group(1) == flag:
                j += 1
                while j < len(lines):
                    end = _LG_OUT_END.match(lines[j])
                    if end and end.group(1) == flag:
                        break
                    body.append(lines[j])
                    j += 1
        verdicts[flag] = {"rc": rc, "bytes": size, "output": "\n".join(body).strip()}
        i = j + 1
    return verdicts


def _answered(verdicts: dict[str, dict], flag: str) -> bool:
    """A flag answered when its own invocation exited 0 and printed something."""
    v = verdicts.get(flag)
    return bool(v) and v["rc"] == 0 and v["bytes"] > 0


def decide(documented: list[str], verdicts: dict[str, dict], policy: str = "flags") -> dict:
    """The verdict for one engine binary, from the per-flag results (issue #580).

    Pure, so it can be tested without docker. Rules, in order:

      * EVERY documented flag must answer on its own — one working flag never vouches for a dead one;
      * the help family and the version family must each be answered by one of their spellings, which
        is what survives engines that hyphenate help differently (six of them document `--help` only);
      * an engine that documents nothing falls back to the trio and needs one answer;
      * a `probe: device` variant whose flags ALL failed is contained: its CLI initialises the device
        at startup, and the version is proven by the image's own `detect`.

    Returns {"ok": bool, "failures": [lines], "note": str}.
    """
    failures: list[str] = []
    note = ""

    for flag in documented:
        v = verdicts.get(flag)
        if v is None:
            failures.append(f"{flag}: documented but never probed")
        elif not _answered(verdicts, flag):
            tail = v["output"].splitlines()[-6:]
            failures.append(f"{flag}: documented but did not answer (exit {v['rc']}, "
                            f"{v['bytes']} byte(s) of output)"
                            + ("\n" + "\n".join(tail) if tail else ""))

    probed = [f for f in dict.fromkeys([*documented, *TYPED_FLAGS]) if f in verdicts]
    if not any(_answered(verdicts, f) for f in probed):
        if policy == "device":
            return {"ok": True, "failures": [],
                    "note": "its CLI needs its device (probe: device) -> version comes from the "
                            "image's entrypoint detect"}
        if documented:
            failures.append(f"none of the documented flags answered: {' '.join(documented)}")
        else:
            failures.append(f"the manifest documents no flags and none of the probed flags answered: "
                            f"{' '.join(probed)}")
        return {"ok": False, "failures": failures, "note": note}

    # A family is judged only over the members that were PROBED: `binary_file_works` always probes all
    # of TYPED_FLAGS, so an absent member here is a caller that never ran it — not an engine failing.
    help_probed = [f for f in HELP_FAMILY if f in verdicts]
    if help_probed and not any(_answered(verdicts, f) for f in help_probed):
        failures.append(f"the help family answers to neither {' nor '.join(help_probed)}: a user "
                        "typing either gets nothing")
    # `probe: help` is for a CLI whose parser HAS no version flag at all (argparse-only, e.g.
    # mlx_lm.server): the help family is still required, and the version is proven by the image's
    # own `detect`. Any other policy must answer the version family (issue #580).
    version_probed = [f for f in VERSION_FAMILY if f in verdicts]
    if policy != "help" and version_probed and not any(_answered(verdicts, f) for f in version_probed):
        failures.append(f"the version family answers to neither {' nor '.join(version_probed)}")

    return {"ok": not failures, "failures": failures, "note": note}


def binary_manifest(engine: str, variant: str) -> dict:
    """{binary, flags} for one image, from the committed generated manifest.

    containers/engines/binaries.json is generated with the params and Dockerfiles
    (make generate-engine-params) and is NOT part of the image-tag hash, so the
    probe reads generated files only - never a skill.
    """
    if not BINARIES_FILE.exists():
        raise SystemExit(f"[engine-image] missing {BINARIES_FILE.relative_to(es.REPO_ROOT)}; "
                         f"run: make generate-engine-params")
    engines = json.loads(BINARIES_FILE.read_text()).get("engines") or {}
    entry = (engines.get(engine) or {}).get(variant)
    if not entry:
        raise SystemExit(f"[engine-image] {engine}/{variant} has no entry in "
                         f"containers/engines/binaries.json; run: make generate-engine-params")
    return entry


def variant_binary(spec: dict) -> str:
    """The engine file for this image. Same path the image was built to contain."""
    return str(binary_manifest(spec["id"], spec["variant"]).get("binary") or "")


def variant_flags(spec: dict) -> list[str]:
    """The version/help flags this engine's own binary documents (issue #204)."""
    return [str(f) for f in (binary_manifest(spec["id"], spec["variant"]).get("flags") or [])]


def binary_file_works(spec: dict) -> int:
    """The image contains the engine file, and that file answers the flags a user types.

    Runs inside the built image. A name on PATH is resolved to its file first, so a missing file is
    not hidden by a later Python import. EVERY flag the manifest documents must answer, and EACH of
    the flags a user types (`--version`, `-h`, `--help`, `-V`) is executed, so a dead spelling is
    named instead of masked by a working one (issue #580).

    A variant whose CLI initialises its device at startup (`probe: device`, e.g. vllm cuda/rocm,
    CI #106) must still CONTAIN the file; there the version proof is the image's own `detect`, which
    `test_image` runs next.
    """
    tag = spec["tag"]
    entry = binary_manifest(spec["id"], spec["variant"])
    binary = str(entry.get("binary") or "")
    if not binary:
        print(f"[engine-image] FAIL {tag}: binaries.json has no binary for "
              f"{spec['id']}/{spec['variant']}")
        return 1
    documented = [str(f) for f in (entry.get("flags") or [])]
    policy = str(entry.get("probe") or "flags")
    # The documented flags first, then whatever a user types that was not already covered.
    flags = [*documented, *[f for f in TYPED_FLAGS if f not in documented]]
    if not documented:
        flags = [*FALLBACK_FLAGS, *[f for f in TYPED_FLAGS if f not in FALLBACK_FLAGS]]
    r = subprocess.run(
        [RUNTIME, "run", "--rm", "--entrypoint", "bash", tag, "-c", BINARY_PROBE,
         "llgenie-binary", binary, *flags],
        capture_output=True, text=True)
    out = (r.stdout or "").strip()
    if r.returncode != 0:
        # The probe's only non-zero exit is "the binary file is missing" (issue #580 keeps the exit
        # contract); nothing to parse.
        print(f"[engine-image] FAIL {tag}: {binary} probed non-zero ({r.returncode})")
        print(((r.stdout or "") + (r.stderr or "")).strip()[-2000:])
        return 1
    verdicts = parse_probe(out)
    verdict = decide(documented, verdicts, policy)
    print(f"[engine-image] {spec['id']}/{spec['variant']} binary {binary} "
          f"(documented: {' '.join(documented) or 'none'}, policy: {policy}, "
          f"probed: {' '.join(flags)})")
    for flag in flags:
        v = verdicts.get(flag)
        if v is None:
            continue
        state = "answers" if _answered(verdicts, flag) else f"NO ANSWER (exit {v['rc']})"
        print(f"[engine-image]   {flag}: {state}"
              + (f" -> {v['output'].splitlines()[0][:120]}" if v["output"] else ""))
    if verdict["note"]:
        print(f"[engine-image] {spec['id']}/{spec['variant']}: {binary} IS in the image but "
              f"{verdict['note']}")
    if verdict["ok"]:
        return 0
    print(f"[engine-image] FAIL {spec['id']}/{spec['variant']} binary {binary}: "
          f"{len(verdict['failures'])} flag problem(s)")
    for line in verdict["failures"]:
        print(f"[engine-image]   - {line}")
    return 1


def test_image(spec: dict) -> int:
    """GPU images on GPU-less runners: the engine file exists and accepts
    --version or -h, `entrypoint.sh detect` prints a version, and
    `entrypoint.sh info` reports port 11434 and model llm-local."""
    tag = spec["tag"]
    if not _available(tag):
        print(f"[engine-image] {tag} not built")
        return 1
    rc = 0
    if binary_file_works(spec) != 0:
        rc = 1
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
    """Push a built image to GHCR only after its binary reports a version.

    The CI matrix tests the image first (`make test-engine-stage`). This runs
    that same version check again and does not tag or push when it fails, so a
    matrix row whose binary is missing is not published.
    """
    if not REGISTRY:
        print("[engine-image] LLGENIE_REGISTRY not set; nothing to push")
        return 1
    tag = spec["tag"]
    if not image_exists(tag):
        print(f"[engine-image] {tag} not built locally; build + test it first")
        return 1
    if test_image(spec) != 0:
        print(f"[engine-image] FAIL {tag}: engine binary file missing or did not accept --version or -h; not pushing")
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


def _bytes_at(ref: str, rel: str, root) -> bytes | None:
    p = subprocess.run(["git", "show", f"{ref}:{rel}"], capture_output=True, cwd=root)
    return None if p.returncode != 0 else p.stdout


def _tag_at(ref: str, engine: str, variant: str, root=None) -> str:
    """The image tag `<ref>` would publish for this engine x arch, or '' when the
    params file does not exist there or has no such variant.

    The bytes are the same ones `_current_tag` hashes, read from `<ref>` with
    `git show` instead of from the working tree (which holds the new pin).
    """
    root = root or es.REPO_ROOT
    raw = _bytes_at(ref, f"containers/engines/params/{engine}.json", root)
    if raw is None:
        return ""
    try:
        old = json.loads(raw)
    except json.JSONDecodeError:
        return ""
    if variant not in old.get("variants", {}):
        return ""
    dockerfile = _bytes_at(ref, f"containers/engines/dockerfiles/{engine}/Dockerfile.{variant}", root)
    entry = _bytes_at(ref, "containers/engines/entrypoint.sh", root)
    runner = _bytes_at(ref, "scripts/engine_runner.py", root)
    if None in (dockerfile, entry, runner):
        return ""
    inputs = es._image_inputs(old, variant, dockerfile=dockerfile, entrypoint=entry, runner=runner)
    digest = hashlib.sha256(inputs).hexdigest()[:8]
    return f"llgenie/{engine.replace('.', '-')}:{str(old['pinned'])[:8]}-{digest}-{variant}"


def _current_tag(params: dict, variant: str, root=None) -> str:
    """The tag HEAD publishes for this engine x arch — the very tag `make install`
    pulls. Same digest function as `engine_skills.image_spec`, so the matrix can
    never skip an image the install path then asks GHCR for."""
    digest = hashlib.sha256(es._image_inputs(params, variant, root)).hexdigest()[:8]
    return f"llgenie/{params['id'].replace('.', '-')}:{str(params['pinned'])[:8]}-{digest}-{variant}"


def matrix(ci: bool = False, changed: str = "", params_dir=None,
           engine: str = "", arch: str = "") -> list[dict]:
    out = []
    params_dir = params_dir or es.PARAMS_DIR
    # params live in <repo>/containers/engines/params: the repo root is two levels
    # above that dir, and every hashed path is relative to it.
    root = params_dir.parents[2]
    for path in sorted(params_dir.glob("*.json")):
        params = json.loads(path.read_text())
        if engine and params["id"] != engine:
            continue
        for key, v in params["variants"].items():
            if arch and key != arch:
                continue
            if ci and (key not in CI_VARIANTS or disabled(params["id"], key)):
                continue
            if changed and _tag_at(changed, params["id"], key, root) == _current_tag(params, key, root):
                continue  # the published tag already is this image
            serve = key == "cpu" and params["id"] not in SMOKE_SKIP
            out.append({"engine": params["id"], "backend": v["backend"], "variant": key,
                        "smoke": serve, "test": "serve" if serve else "detect",
                        "chat": "yes" if chat_testable(params["id"], key) else ""})
    if not out:
        # GitHub fails a workflow whose matrix include list is empty BEFORE the
        # job's if: is evaluated (run 38105450418). One placeholder row keeps the
        # matrix legal; ci.yml skips engine == none and builds nothing.
        out.append({"engine": "none", "backend": "cpu", "variant": "none",
                    "smoke": False, "test": "detect", "chat": ""})
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
    m.add_argument("--changed", default="", help="ref: only images whose tag differs from it")
    m.add_argument("--engine", default="", help="only this engine id (the dispatched sweep)")
    m.add_argument("--arch", default="", help="only this backend/variant")
    a = ap.parse_args(argv)

    if a.cmd == "build-base":
        return build_base(a.backend, a.force, a.push)
    if a.cmd == "ci-status":
        return ci_status(a.run, a.watch)
    if a.cmd == "ensure-env":
        return 0 if ensure_container_env() else 1
    if a.cmd == "matrix":
        rows = matrix(a.ci, a.changed, engine=a.engine, arch=a.arch)
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
