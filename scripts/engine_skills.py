#!/usr/bin/env python3
"""Engine skills: one SKILL.md per inference server under skills/engines/<id>/.

Each skill's YAML front matter is the single source of truth for how to
detect, install and launch that engine on each hardware backend. This module
is the generic runner: it parses the skills, detects the hardware parameters a
build needs (CUDA arch, ROCm gfx target, CUDA major, cores, ...), renders a
skill's per-backend steps for this machine, checks prerequisites, validates
the skills against the trending-local-llms engine registry, and runs installs.
It contains no engine-specific install logic: that lives in the skills.

Stdlib only (no PyYAML): it runs under the bare `python3` that
scripts/build_llama_server.sh uses before the venv exists. The front matter is
a strict YAML subset (see parse_front_matter); tests check every skill parses
identically with yaml.safe_load.

Usage:
  python3 scripts/engine_skills.py list
  python3 scripts/engine_skills.py hardware [--json]
  python3 scripts/engine_skills.py validate [--registry FILE|URL]
  python3 scripts/engine_skills.py plan <id> [--backend B] [--json]
  python3 scripts/engine_skills.py check <id> [--backend B]
  python3 scripts/engine_skills.py install <id> [--backend B] [--dry]   # metal only; other backends: make build-engine
  python3 scripts/engine_skills.py detect <id> [--backend B]
  python3 scripts/engine_skills.py build-env <id> <backend>   # shell vars for build_llama_server.sh
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

try:  # imported as scripts.engine_skills (tests) or run as a script
    from . import detect_server  # type: ignore
except ImportError:  # pragma: no cover - script mode
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import detect_server  # type: ignore

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills" / "engines"
REGISTRY_URL = ("https://raw.githubusercontent.com/andyholst/trending-local-llms/"
                "master/data/models.json")

BACKENDS = ("cuda", "rocm", "vulkan", "metal", "cpu")
SERVABLE = (True, False, "via")
REQUIRED_KEYS = ("name", "description", "engine", "id", "repo", "ref", "ref_kind",
                 "pinned", "verified", "license", "servable", "backends", "os",
                 "formats", "upstream_watch")
SERVABLE_KEYS = ("install", "binary", "detect", "launch", "health", "alias_mode", "prereqs")
ALIAS_MODES = ("flag", "create", "config", "symlink", "any-name")


# ---------------------------------------------------------------------------
# Front matter: strict YAML subset parser
# ---------------------------------------------------------------------------
_INT = re.compile(r"^[-+]?\d+$")
_FLOAT = re.compile(r"^[-+]?(\d+\.\d*|\.\d+)([eE][-+]?\d+)?$")


def _strip_comment(s: str) -> str:
    """Drop a trailing ' # comment' that is outside quotes."""
    q = None
    for i, ch in enumerate(s):
        if q:
            if ch == q:
                q = None
        elif ch in "\"'":
            q = ch
        elif ch == "#" and (i == 0 or s[i - 1] in " \t"):
            return s[:i].rstrip()
    return s.rstrip()


def _split_inline(s: str) -> list[str]:
    out, cur, q = [], "", None
    for ch in s:
        if q:
            cur += ch
            if ch == q:
                q = None
        elif ch in "\"'":
            q = ch
            cur += ch
        elif ch == ",":
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def _scalar(s: str):
    s = s.strip()
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        return [_scalar(x) for x in _split_inline(inner)] if inner else []
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return json.loads(s)
    if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
        return s[1:-1].replace("''", "'")
    if s in ("true", "True"):
        return True
    if s in ("false", "False"):
        return False
    if s in ("null", "~", ""):
        return None
    if _INT.match(s):
        return int(s)
    if _FLOAT.match(s):
        return float(s)
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        raise ValueError(f"unquoted date {s!r}: quote it (YAML would parse a date)")
    if s[0] in "{&*!|>%@`":
        raise ValueError(f"unsupported YAML construct: {s!r}")
    return s


def _parse_block(lines: list[tuple[int, str]], i: int, indent: int):
    """Parse lines[i:] at exactly `indent`; return (value, next_index)."""
    if i >= len(lines):
        return None, i
    if lines[i][1].startswith("- "):
        items = []
        while i < len(lines) and lines[i][0] == indent and lines[i][1].startswith("- "):
            items.append(_scalar(lines[i][1][2:]))
            i += 1
        return items, i
    mapping: dict = {}
    while i < len(lines) and lines[i][0] == indent:
        text = lines[i][1]
        if text.startswith("- "):
            raise ValueError(f"mixed list/map at indent {indent}: {text!r}")
        m = re.match(r'^("[^"]+"|[A-Za-z0-9_.\-]+):(?:\s+(.*))?$', text)
        if not m:
            raise ValueError(f"cannot parse line: {text!r}")
        key = m.group(1).strip('"')
        rest = m.group(2)
        i += 1
        if rest is None or rest == "":
            if i < len(lines) and lines[i][0] > indent:
                mapping[key], i = _parse_block(lines, i, lines[i][0])
            else:
                mapping[key] = None
        else:
            mapping[key] = _scalar(rest)
    return mapping, i


def parse_front_matter(text: str) -> tuple[dict, str]:
    """Split `---\\n<yaml>\\n---\\n<body>` and parse the YAML subset."""
    if not text.startswith("---\n"):
        raise ValueError("SKILL.md must start with '---' front matter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError("unterminated front matter")
    raw, body = text[4:end], text[end + 5:]
    lines = []
    for ln in raw.splitlines():
        if "\t" in ln[: len(ln) - len(ln.lstrip())]:
            raise ValueError("tabs are not allowed for indentation")
        stripped = _strip_comment(ln)
        if not stripped.strip():
            continue
        lines.append((len(stripped) - len(stripped.lstrip(" ")), stripped.strip()))
    data, i = _parse_block(lines, 0, 0)
    if i != len(lines):
        raise ValueError(f"unexpected indentation at: {lines[i][1]!r}")
    if data is not None and not isinstance(data, dict):
        raise ValueError("front matter must be a mapping")
    return data or {}, body


def load_skill(path: Path) -> dict:
    meta, body = parse_front_matter(path.read_text())
    meta["_path"] = str(path)
    meta["_body"] = body
    return meta


def load_skills(skills_dir: Path = SKILLS_DIR) -> dict[str, dict]:
    skills = {}
    for p in sorted(skills_dir.glob("*/SKILL.md")):
        s = load_skill(p)
        skills[s.get("id") or p.parent.name] = s
    return skills


def get_skill(skill_id: str, skills: dict | None = None) -> dict:
    skills = skills if skills is not None else load_skills()
    if skill_id in skills:
        return skills[skill_id]
    for s in skills.values():  # accept the registry engine name too
        if s.get("engine") == skill_id:
            return s
    raise SystemExit(f"[engine-skills] no skill for engine {skill_id!r} "
                     f"(known: {', '.join(sorted(skills))})")


# ---------------------------------------------------------------------------
# Hardware detection (the parameters a build depends on)
# ---------------------------------------------------------------------------
def _run(cmd: list[str], timeout: int = 10) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def cuda_arch_from_compute_cap(cap: str) -> str:
    """'8.9' -> '89', '12.0' -> '120' (CMAKE_CUDA_ARCHITECTURES form)."""
    m = re.match(r"^\s*(\d+)\.(\d+)\s*$", cap or "")
    return f"{m.group(1)}{m.group(2)}" if m else ""


def nvidia_compute_caps() -> list[str]:
    if not shutil.which("nvidia-smi"):
        return []
    out = _run(["nvidia-smi", "--query-gpu=compute_cap", "--format=csv,noheader"])
    return [ln.strip() for ln in out.splitlines() if re.match(r"^\d+\.\d+$", ln.strip())]


def nvcc_cuda_version() -> str:
    nvcc = detect_server._find_nvcc()
    if not nvcc:
        return ""
    m = re.search(r"release (\d+\.\d+)", _run([nvcc, "--version"]))
    return m.group(1) if m else ""


def rocm_gfx_targets() -> list[str]:
    """gfx names of AMD GPU agents from rocminfo (CPU agents excluded)."""
    if not shutil.which("rocminfo"):
        return []
    names = re.findall(r"Name:\s+(gfx[0-9a-f]+)\b", _run(["rocminfo"], timeout=20))
    return sorted(set(names))


def detect_hardware() -> dict:
    """Probe the machine. Env seams (tests/CI): LLAMA_BACKEND, LLAMA_RAM_BYTES,
    LLGENIE_CUDA_ARCH, LLGENIE_GPU_TARGETS, LLGENIE_CUDA_VERSION, BUILD_JOBS."""
    system = {"darwin": "darwin", "linux": "linux"}.get(sys.platform, sys.platform)
    machine = platform.machine().lower()
    arch = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(machine, machine)
    caps = nvidia_compute_caps()
    env_arch = (os.environ.get("LLGENIE_CUDA_ARCH") or "").strip()
    cuda_arch = env_arch or ";".join(sorted({cuda_arch_from_compute_cap(c) for c in caps if c}))
    compute_cap = caps[0] if caps else ""
    if env_arch and not compute_cap:
        first = env_arch.split(";")[0]
        compute_cap = f"{first[:-1]}.{first[-1]}" if first.isdigit() and len(first) >= 2 else ""
    env_gfx = (os.environ.get("LLGENIE_GPU_TARGETS") or "").strip()
    gfx = env_gfx.split(";") if env_gfx else rocm_gfx_targets()
    cuda_version = (os.environ.get("LLGENIE_CUDA_VERSION") or "").strip() or nvcc_cuda_version()
    backend = (os.environ.get("LLAMA_BACKEND") or "").strip()
    if backend not in BACKENDS:
        backend = detect_server.detect_backend()
        if backend == "cpu" and gfx and shutil.which("hipconfig"):
            backend = "rocm"
    torch_backend = (os.environ.get("LLGENIE_TORCH_BACKEND") or "").strip() or "auto"
    jobs = (os.environ.get("BUILD_JOBS") or "").strip()
    if not jobs.isdigit() or int(jobs) < 1:
        jobs = str(os.cpu_count() or 4)
    return {
        "os": system,
        "arch": arch,
        "machine": machine,
        "backend": backend,
        "card_ram_bytes": detect_server.detect_card_ram_bytes(),
        "compute_cap": compute_cap,
        "cuda_arch": cuda_arch,
        "cuda_version": cuda_version,
        "cuda_major": cuda_version.split(".")[0] if cuda_version else "",
        "gpu_targets": ";".join(gfx),
        "torch_backend": torch_backend,
        "jobs": jobs,
    }


def _version_tuple(v) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", str(v)))


# ---------------------------------------------------------------------------
# Rendering a skill for this machine
# ---------------------------------------------------------------------------
class _Ctx(dict):
    def __missing__(self, key):
        raise KeyError(f"unresolved placeholder {{{key}}}")


def _render(template: str, ctx: dict) -> str:
    return template.format_map(_Ctx(ctx))


def engines_root() -> Path:
    return Path(os.environ.get("LLGENIE_ENGINES")
                or Path.home() / ".local" / "share" / "llgenie" / "engines")


def context(skill: dict, backend: str, hw: dict, extra: dict | None = None) -> dict:
    prefix = engines_root() / skill["id"]
    server_root = os.environ.get("SERVER_ROOT") or str(Path.home() / "repository" / "git")
    ctx = {
        **{k: str(v) for k, v in hw.items()},
        "id": skill["id"], "repo": skill["repo"], "ref": skill["ref"],
        "pinned": skill["pinned"], "pinned_short": str(skill["pinned"])[:12],
        "version": str(skill.get("version", skill["ref"])).lstrip("v"),
        "backend": backend, "prefix": str(prefix),
        "server_root": server_root, "repo_root": str(REPO_ROOT),
        "host": "127.0.0.1", "port": "11434", "alias": "llm-local",
        "model": "{model}", "drafter": "{drafter}",
    }
    # native builds follow the branch tip (as make install always has); image
    # builds check out exactly `pinned`, so the image tag never lies.
    ctx["checkout"] = ctx["pinned"] if os.environ.get("LLGENIE_IMAGE_BUILD") == "1" else f"origin/{skill['ref']}"
    ctx["src"] = _render(str(skill.get("src_dir", "{prefix}/src")), ctx)
    ctx["build"] = _render(str(skill.get("build_dir", "{src}/build-{backend}")), ctx)
    if extra:
        ctx.update({k: str(v) for k, v in extra.items()})
    if skill.get("binary"):
        ctx["binary"] = _render(str(skill["binary"]), ctx)
    return ctx


def _per_backend(value, backend: str):
    """`{common: ..., cuda: ...}` -> common + backend entries (lists or strings)."""
    if value is None:
        return None
    if not isinstance(value, dict):
        return value
    common, specific = value.get("common"), value.get(backend)
    if isinstance(common, list) or isinstance(specific, list):
        return list(common or []) + list(specific or [])
    parts = [p for p in (common, specific) if p]
    return " ".join(str(p) for p in parts) if parts else None


def hw_flags(skill: dict, backend: str, hw: dict) -> list[str]:
    """Hardware-derived flags, emitted only when the parameter was detected."""
    out = []
    spec = (skill.get("hw_flags") or {}).get(backend) or {}
    for param, template in spec.items():
        if str(hw.get(param) or "").strip():
            out.append(_render(str(template), {**hw}))
    return out


def cmake_flags(skill: dict, backend: str, hw: dict) -> str:
    base = _per_backend(skill.get("cmake_flags"), backend) or ""
    if isinstance(base, list):
        base = " ".join(str(x) for x in base)
    return " ".join([str(base), *hw_flags(skill, backend, hw)]).strip()


def build_env(skill: dict, backend: str, hw: dict, extra: dict | None = None) -> dict:
    spec = skill.get("env") or {}
    merged = {**(spec.get("common") or {}), **(spec.get(backend) or {})}
    ctx = context(skill, backend, hw, extra)  # extra: the run's host/port (ollama's OLLAMA_HOST)
    return {k: _render(str(v), ctx) for k, v in merged.items() if v not in (None, "")}


def env_prelude(env: dict) -> str:
    """`export K="V"; ...` so bash expands $VAR / $(cmd) in skill env values
    (e.g. HIP_PATH="$(hipconfig -R)", CUDA_HOME="$(dirname $(dirname $(command -v nvcc)))")."""
    out = []
    for k, v in env.items():
        esc = str(v).replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`")
        out.append(f'export {k}="{esc}"; ')
    return "".join(out)


def pick_backend(skill: dict, hw: dict, backend: str | None = None) -> str:
    backend = backend or hw["backend"]
    if backend not in (skill.get("backends") or []):
        raise SystemExit(f"[engine-skills] {skill['id']} does not support backend "
                         f"{backend!r} (supports: {', '.join(skill.get('backends') or []) or 'none'})")
    return backend


HW_PROBE_TOOLS = {"nvidia-smi", "rocminfo", "vulkaninfo"}


def check(skill: dict, backend: str, hw: dict, mode: str = "native") -> list[str]:
    """Return blockers for `skill` on `backend` (empty = OK).

    mode="native": install + run on this machine (tools AND hardware floors).
    mode="build":  container image build: build tools only; no GPU is visible,
                   so hardware probes and floors are skipped (enforced at run).
    mode="run":    run a prebuilt image here: hardware floors only, no build tools.
    """
    blockers = []
    floors = mode in ("native", "run")
    tools = mode in ("native", "build")
    if backend not in (skill.get("backends") or []):
        blockers.append(f"backend {backend} not supported by {skill['id']}")
    if skill.get("servable") is False:
        blockers.append(f"{skill['id']} is not an HTTP server (servable: false)")
    if mode != "build" and hw["os"] not in (skill.get("os") or []):
        blockers.append(f"OS {hw['os']} not supported (needs {', '.join(skill.get('os') or [])})")
    req = skill.get("requires") or {}
    min_cc = (req.get("min_compute_cap") or {}).get(backend)
    if floors and min_cc is not None and backend == "cuda":
        if not hw.get("compute_cap"):
            blockers.append(f"no NVIDIA GPU detected (needs compute capability >= {min_cc})")
        elif _version_tuple(hw["compute_cap"]) < _version_tuple(min_cc):
            blockers.append(f"GPU compute capability {hw['compute_cap']} < required {min_cc}")
    min_cuda = (req.get("min_cuda") or {}).get(backend)
    if mode != "run" and min_cuda is not None and _version_tuple(hw.get("cuda_version") or "0") < _version_tuple(min_cuda):
        blockers.append(f"CUDA toolkit {hw.get('cuda_version') or 'missing'} < required {min_cuda}")
    allowed = (req.get("gpu_targets") or {}).get(backend)
    if floors and allowed and backend == "rocm":
        have = [g for g in (hw.get("gpu_targets") or "").split(";") if g]
        if not any(g in allowed for g in have):
            blockers.append(f"AMD GPU {','.join(have) or 'none'} not in supported targets {','.join(allowed)}")
    for tool in (_per_backend(skill.get("prereqs"), backend) or []) if tools else []:
        if mode == "build" and tool in HW_PROBE_TOOLS:
            continue
        found = detect_server._find_nvcc() if tool == "nvcc" else shutil.which(tool)
        if not found:
            blockers.append(f"missing prerequisite: {tool}")
    return blockers


def plan(skill: dict, backend: str, hw: dict, extra: dict | None = None,
         mode: str = "native") -> dict:
    ctx = context(skill, backend, hw, extra)
    ctx["cmake_flags"] = cmake_flags(skill, backend, hw)
    steps = [_render(str(s), ctx) for s in (_per_backend(skill.get("install"), backend) or [])]

    def r(key):
        v = _per_backend(skill.get(key), backend)
        if v is None:
            return None
        return [_render(str(x), ctx) for x in v] if isinstance(v, list) else _render(str(v), ctx)

    return {
        "id": skill["id"], "engine": skill["engine"], "backend": backend,
        "servable": skill.get("servable"), "via": skill.get("via"),
        "pinned": skill["pinned"], "env": build_env(skill, backend, hw, extra),
        "steps": steps, "binary": ctx.get("binary"), "detect": r("detect"),
        "pre_launch": r("pre_launch"), "launch": r("launch"), "post_launch": r("post_launch"),
        "health": skill.get("health"), "alias_mode": skill.get("alias_mode"),
        "env_prelude": env_prelude(build_env(skill, backend, hw, extra)),
        "blockers": check(skill, backend, hw, mode),
    }


def native_allowed(skill: dict, backend: str) -> bool:
    """Engines are installed in their container image. Only Metal (which cannot
    run in a container) is installed natively on the host."""
    return backend == "metal"


def install(skill: dict, backend: str, hw: dict, dry: bool = False,
            skills: dict | None = None, mode: str = "native") -> int:
    if mode == "native" and not native_allowed(skill, backend) and os.environ.get("LLGENIE_IMAGE_BUILD") != "1":
        print(f"[engine-skills] {skill['id']}/{backend} is installed in its container image, not on the host:\n"
              f"  make build-engine ENGINE={skill['id']}   then   make run-engine ENGINE={skill['id']} MODEL=<model>",
              file=sys.stderr)
        return 3
    p = plan(skill, backend, hw, mode=mode)
    if p["blockers"]:
        for b in p["blockers"]:
            print(f"[engine-skills] BLOCKED {skill['id']}/{backend}: {b}", file=sys.stderr)
        return 2
    prelude = env_prelude(p["env"])
    Path(context(skill, backend, hw)["prefix"]).mkdir(parents=True, exist_ok=True)
    for step in p["steps"]:
        if step.startswith("use:"):  # delegate to another skill (e.g. dflash2 -> sglang)
            dep = get_skill(step[4:].strip(), skills)
            print(f"[engine-skills] {skill['id']}: installing dependency {dep['id']}")
            rc = install(dep, backend, hw, dry, skills, mode)
            if rc:
                return rc
            continue
        print(f"[engine-skills] {skill['id']}/{backend}$ {step}", flush=True)
        if dry:
            continue
        rc = subprocess.run(["bash", "-euo", "pipefail", "-c", prelude + step]).returncode
        if rc:
            print(f"[engine-skills] FAIL {skill['id']}/{backend}: step exited {rc}", file=sys.stderr)
            return rc
    if not dry and p["detect"]:
        return detect(skill, backend, hw)
    return 0


def detect(skill: dict, backend: str, hw: dict) -> int:
    p = plan(skill, backend, hw)
    if not p["detect"]:
        print(f"[engine-skills] {skill['id']}: no detect command")
        return 1
    r = subprocess.run(["bash", "-euo", "pipefail", "-c", env_prelude(p["env"]) + p["detect"]],
                       capture_output=True, text=True)
    first = (r.stdout or r.stderr).strip().splitlines()[:1]
    status = "installed" if r.returncode == 0 else "missing"
    print(f"[engine-skills] {skill['id']}/{backend}: {status} {first[0] if first else ''}".rstrip())
    return 0 if r.returncode == 0 else 1


def serve(skill: dict, backend: str, hw: dict, model: str, host: str = "127.0.0.1",
          port: int = 11434, drafter: str = "", ready_timeout: float = 1800) -> int:
    if not native_allowed(skill, backend):
        print(f"[engine-skills] {skill['id']}/{backend} runs from its container image: "
              f"make run-engine ENGINE={skill['id']} MODEL={model} PORT={port}", file=sys.stderr)
        return 3
    """Native launch (#96): render the skill for this machine and hand it to the
    same runner the container entrypoint uses (scripts/engine_runner.py)."""
    try:
        from . import engine_runner  # type: ignore
    except ImportError:
        import engine_runner  # type: ignore
    p = plan(skill, backend, hw, mode="run")
    frozen = {"id": skill["id"], "backend": backend, "env": p["env"], "detect": p["detect"],
              "pre_launch": p["pre_launch"], "launch": p["launch"], "post_launch": p["post_launch"],
              "health": p["health"]}
    for k in ("pre_launch", "launch", "post_launch"):
        if frozen[k]:
            frozen[k] = frozen[k].replace("127.0.0.1", "{host}").replace("11434", "{port}")
    return engine_runner.serve_plan(frozen, model, host, port, drafter, ready_timeout)


# ---------------------------------------------------------------------------
# Frozen image parameters (containers/engines/params/<id>.json).
#
# `make engine-params` renders each skill into FIXED per-variant parameters
# (backend x GPU arch: base image, apt, build args, install steps, env, launch,
# health, run args) and commits them. `make engine-image` reads ONLY that file,
# never the skill, so an image is always built with exactly the parameters that
# were generated from the skill. When a skill changes, regenerating rewrites the
# file only where the rendered parameters differ; `make engine-params-check`
# (CI) fails if the committed file is stale.
# ---------------------------------------------------------------------------
CONTAINER_DIR = REPO_ROOT / "containers" / "engines"
PARAMS_DIR = CONTAINER_DIR / "params"
CONTAINER_BACKENDS = ("cuda", "rocm", "vulkan", "cpu")  # metal cannot run in a container
DEFAULT_BASE = {
    "cuda": "nvidia/cuda:13.0.2-devel-ubuntu24.04",   # devel: nvcc for builds AND runtime JITs (FlashInfer, triton)
    "rocm": "rocm/dev-ubuntu-24.04:7.0-complete",     # -complete: hipBLAS/rocBLAS dev libs llama.cpp's HIP build needs
    "vulkan": "ubuntu:24.04",
    "cpu": "ubuntu:24.04",
}
DEFAULT_APT = {"vulkan": ["glslc", "glslang-tools", "libvulkan-dev", "spirv-headers", "mesa-vulkan-drivers"]}
# Slim run-stage bases for engines that compile a self-contained binary
# (container.<backend>.runtime: true). The build stage keeps the devel base.
RUNTIME_BASE = {
    "cuda": "nvidia/cuda:13.0.2-runtime-ubuntu24.04",
    "rocm": "rocm/dev-ubuntu-24.04:7.0-complete",     # runtime needs the same HIP/rocBLAS libs
    "vulkan": "ubuntu:24.04",
    "cpu": "ubuntu:24.04",
}
RUNTIME_APT = {"vulkan": ["libvulkan1", "mesa-vulkan-drivers", "libgomp1"], "cpu": ["libgomp1"],
               "cuda": ["libgomp1"], "rocm": ["libgomp1"]}
# ONE image per backend: compiled engines are built as fat binaries for every
# common consumer/workstation GPU arch at once, so a single cuda image runs on
# Turing..Blackwell and a single rocm image on RDNA2..RDNA4 + MI300. A skill may
# override the list (container.<backend>.cuda_archs / gpu_targets).
FAT_CUDA_ARCHS = "75;80;86;89;90;120"
FAT_GPU_TARGETS = "gfx1030;gfx1100;gfx1101;gfx1102;gfx1151;gfx1200;gfx1201;gfx942"
CONTAINER_PORT = 11434
IMG_SRC = "/opt/llgenie/src"
# GPU passthrough at `docker run`. CUDA uses the CDI device that
# nvidia-container-toolkit generates (`nvidia-ctk cdi generate`): it mounts the
# HOST driver (libcuda.so.1, nvidia-smi) into the container, so the image never
# ships a driver and always matches the host's. (`--gpus all` breaks on Docker
# 28+ when an AMD CDI spec is probed first.)
# docker's default /dev/shm is 64 MiB; vLLM/sglang need more for their
# shared-memory buffers ("Insufficient space in /dev/shm", CI #98)
SHM = ["--shm-size", "2g"]
RUN_ARGS = {"cuda": ["--device", "nvidia.com/gpu=all", *SHM],
            "rocm": ["--device", "/dev/kfd", "--device", "/dev/dri", "--group-add", "video",
                     "--group-add", "render", "--ipc", "host"],
            "vulkan": ["--device", "/dev/dri", *SHM],
            "cpu": [*SHM]}


def container_spec(skill: dict, backend: str):
    """Per-backend container settings, or None when the skill opts out."""
    if skill.get("servable") is not True or backend not in CONTAINER_BACKENDS:
        return None
    if backend not in (skill.get("backends") or []) or "linux" not in (skill.get("os") or []):
        return None
    cont = skill.get("container")
    if cont is False:
        return None
    spec = (cont or {}).get(backend, {}) if isinstance(cont, dict) else {}
    return None if spec is False else (spec or {})


def _arch_variants(skill: dict, backend: str, spec: dict) -> list[tuple[str, str]]:
    """One variant per backend; compiled engines get the fat arch list."""
    hwf = (skill.get("hw_flags") or {}).get(backend) or {}
    if backend == "cuda" and "cuda_arch" in hwf:
        return [(backend, str(spec.get("cuda_archs", FAT_CUDA_ARCHS)))]
    if backend == "rocm" and ("gpu_targets" in hwf or any("{gpu_targets}" in str(x) for x in
                                                         _flatten(skill.get("install")))):
        return [(backend, str(spec.get("gpu_targets", FAT_GPU_TARGETS)))]
    return [(backend, "")]


def render_variant(skill: dict, backend: str, arch: str) -> dict:
    """Render one image variant with fixed, in-image paths (no host state)."""
    spec = container_spec(skill, backend) or {}
    version = str(skill.get("version", skill["ref"])).lstrip("v")
    base = str(spec.get("base") or DEFAULT_BASE[backend]).replace("{version}", version)
    prebuilt = bool(spec.get("prebuilt"))
    m = re.search(r"cuda:(\d+)\.(\d+)", base)
    cuda_ver = f"{m.group(1)}.{m.group(2)}" if (backend == "cuda" and m) else ("13.0" if backend == "cuda" else "")
    torch_backend = {"cuda": f"cu{cuda_ver.replace('.', '')}" if cuda_ver else "auto",
                     "rocm": "auto"}.get(backend, "cpu")
    hw = {"os": "linux", "arch": "amd64", "machine": "x86_64", "backend": backend,
          "card_ram_bytes": 0, "compute_cap": "",
          "cuda_arch": arch if backend == "cuda" else "",
          "cuda_version": cuda_ver, "cuda_major": cuda_ver.split(".")[0] if cuda_ver else "",
          "gpu_targets": arch if backend == "rocm" else "", "torch_backend": torch_backend,
          "jobs": "$(nproc)"}
    old = {k: os.environ.get(k) for k in ("LLGENIE_ENGINES", "SERVER_ROOT", "LLGENIE_IMAGE_BUILD")}
    os.environ.update({"LLGENIE_ENGINES": "/opt/llgenie/engines", "SERVER_ROOT": IMG_SRC,
                       "LLGENIE_IMAGE_BUILD": "1"})
    try:
        p = plan(skill, backend, hw, mode="build")
        ictx = context(skill, backend, hw)
        ictx["build"] = p.get("binary", "").rsplit("/bin/", 1)[0] if p.get("binary") else ictx["build"]
        runtime_copy = [_render(str(x), ictx) for x in (spec.get("runtime_copy") or [])] if spec.get("runtime") else []
        steps = []
        for st in p["steps"]:
            if st.startswith("use:"):  # inline the dependency's steps (frozen too)
                dep = get_skill(st[4:].strip())
                steps += plan(dep, backend, hw, mode="build")["steps"]
            else:
                steps.append(st)
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    if prebuilt:  # the official image already contains the engine: no install steps
        steps = []
        if spec.get("binary"):
            sk_bin = p.get("binary") or ""
            for k in ("detect", "pre_launch", "launch", "post_launch"):
                if p.get(k) and sk_bin:
                    p[k] = p[k].replace(sk_bin, str(spec["binary"]))
    # host/port/model stay placeholders: bound at `docker run` time.
    unbind = lambda c: c.replace("--host 127.0.0.1", "--host {host}").replace("-host 127.0.0.1", "-host {host}") \
        .replace("127.0.0.1:11434", "{host}:{port}").replace("11434", "{port}") if c else c  # noqa: E731
    return {
        "id": skill["id"], "engine": skill["engine"], "backend": backend, "arch": arch,
        "base": base, "prebuilt": prebuilt,
        "runtime_base": (str(spec.get("runtime_base") or RUNTIME_BASE[backend]) if spec.get("runtime") else ""),
        "runtime_copy": runtime_copy,
        "apt": DEFAULT_APT.get(backend, []) + list(spec.get("apt") or []),
        "build_args": {"CUDA_ARCH": hw["cuda_arch"], "GPU_TARGETS": hw["gpu_targets"],
                       "TORCH_BACKEND": torch_backend},
        "install": steps, "env": {k: unbind(v) for k, v in p["env"].items()},
        "detect": p["detect"], "pre_launch": unbind(p["pre_launch"]), "launch": unbind(p["launch"]),
        "post_launch": unbind(p["post_launch"]), "health": p["health"], "alias_mode": p["alias_mode"],
        "run_args": RUN_ARGS[backend], "port": CONTAINER_PORT,
    }


def generate_params(skill: dict) -> dict | None:
    variants = {}
    for b in CONTAINER_BACKENDS:
        spec = container_spec(skill, b)
        if spec is None:
            continue
        for key, arch in _arch_variants(skill, b, spec):
            variants[key] = render_variant(skill, b, arch)
    if not variants:
        return None
    return {"_generated_by": "make generate-engine-params (scripts/engine_skills.py) - do not edit; edit the skill",
            "engine": skill["engine"], "id": skill["id"], "repo": skill["repo"], "ref": skill["ref"],
            "pinned": skill["pinned"], "native": native_params(skill), "variants": variants}


def native_params(skill: dict) -> dict:
    """Frozen native (host) build parameters per backend for compiled engines:
    used by make install / build-variant via scripts/native_build_env.py, so
    native builds never read a skill either. Hardware-derived flags stay
    templates ({cuda_arch}, {gpu_targets}) filled from the detected hardware."""
    if "cmake_flags" not in skill:
        return {}
    out = {}
    for b in skill.get("backends") or []:
        out[b] = {"cmake_flags": cmake_flags(skill, b, {}),
                  "hw_flags": dict((skill.get("hw_flags") or {}).get(b) or {}),
                  "env": dict(((skill.get("env") or {}).get(b) or {})),
                  "src_dir": str(skill.get("src_dir", "")).replace("{server_root}/", ""),
                  "build_dir": f"build-{b}"}
    return out


def params_path(skill_id: str) -> Path:
    return PARAMS_DIR / f"{skill_id}.json"


def write_params(skills: dict, check_only: bool = False) -> list[str]:
    """Regenerate params JSON + one Dockerfile per engine x arch; write only
    files that differ, delete files for variants that no longer exist.
    Returns the changed paths (relative to the repo)."""
    want: dict[Path, str] = {}
    for sid, skill in skills.items():
        data = generate_params(skill)
        if data is None:
            continue
        want[params_path(sid)] = json.dumps(data, indent=2, sort_keys=False) + "\n"
        for variant in data["variants"]:
            want[dockerfile_path(sid, variant)] = render_dockerfile(data, variant)
    for b in CONTAINER_BACKENDS:
        want[BASE_DIR / f"Dockerfile.{b}"] = render_base_dockerfile(b)
    have = set(PARAMS_DIR.glob("*.json")) | set(DOCKERFILES_DIR.glob("*/Dockerfile.*")) | \
        set(BASE_DIR.glob("Dockerfile.*"))
    changed = []
    for path, text in want.items():
        if not path.exists() or path.read_text() != text:
            changed.append(str(path.relative_to(REPO_ROOT)))
            if not check_only:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
    for path in sorted(have - set(want)):
        changed.append(str(path.relative_to(REPO_ROOT)))
        if not check_only:
            path.unlink()
            if path.parent not in (PARAMS_DIR, BASE_DIR) and not any(path.parent.iterdir()):
                path.parent.rmdir()
    return sorted(changed)


DOCKERFILES_DIR = CONTAINER_DIR / "dockerfiles"


# Shared toolchain base per backend (built once, cached + published, reused by
# every compiled engine image): containers/engines/base/Dockerfile.<backend>.
BASE_DIR = CONTAINER_DIR / "base"
BUILD_TOOLS = ["ca-certificates", "curl", "git", "build-essential", "cmake", "ninja-build", "zstd",
               "python3", "tar"]


def base_image_name(backend: str) -> str:
    return f"llgenie/base-{backend}"


def render_base_dockerfile(backend: str) -> str:
    tools = BUILD_TOOLS + DEFAULT_APT.get(backend, [])
    return "\n".join([
        "# GENERATED by `make generate-engine-params`. Shared build toolchain for every",
        f"# compiled llgenie engine image on {backend}; built once by `make build-engine-base",
        f"# BACKEND={backend}` (CI: engine-base job), cached and published, never per engine.",
        f"FROM {DEFAULT_BASE[backend]}",
        "ENV DEBIAN_FRONTEND=noninteractive PATH=/opt/llgenie/bin:/usr/local/cuda/bin:${PATH}",
        "RUN apt-get update && apt-get install -y --no-install-recommends \\",
        f"        {' '.join(tools)} \\",
        "    && rm -rf /var/lib/apt/lists/*",
        "COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /uvx /opt/llgenie/bin/",
        f'LABEL llgenie.base="{backend}" llgenie.from="{DEFAULT_BASE[backend]}"',
        "",
    ])


def base_tag(backend: str) -> str:
    import hashlib
    return f"{base_image_name(backend)}:{hashlib.sha256(render_base_dockerfile(backend).encode()).hexdigest()[:10]}"


def render_dockerfile(params: dict, variant: str) -> str:
    """One self-contained Dockerfile per engine x arch. No ARGs to fill in:
    every value is fixed, from the frozen params."""
    v = params["variants"][variant]
    tag = f"{params['id']}:{variant}"
    lines = [
        f"# GENERATED by `make generate-engine-params` from skills/engines/{params['id']}/SKILL.md",
        f"# (pinned {params['pinned']}). Do not edit; edit the skill and regenerate.",
        f"# Build: make build-engine ENGINE={params['id']} ARCH={variant}",
        f"# Run:   make run-engine ENGINE={params['id']} ARCH={variant} MODEL=<model> PORT=11434",
        f"#        -> OpenAI API at http://127.0.0.1:<PORT>/v1, model llm-local",
        f"FROM {v['base']}",
        "",
        "ENV DEBIAN_FRONTEND=noninteractive HF_HOME=/models/hf \\",
        "    PATH=/opt/llgenie/bin:/usr/local/cuda/bin:${PATH}",
    ]
    if v.get("build_args", {}).get("CUDA_ARCH"):
        lines.append(f"ENV LLGENIE_CUDA_ARCH={v['build_args']['CUDA_ARCH']}")
    if v.get("build_args", {}).get("GPU_TARGETS"):
        lines.append(f"ENV LLGENIE_GPU_TARGETS={v['build_args']['GPU_TARGETS']}")
    lines.append("")
    if v.get("prebuilt"):
        tools = ["ca-certificates", "curl", "python3"] + list(v.get("apt") or [])
        lines += [
            "# Official upstream image already contains the engine; add only what the",
            "# llgenie entrypoint needs (python3 + curl) when the base lacks it.",
            "RUN if ! command -v python3 >/dev/null || ! command -v curl >/dev/null; then \\",
            f"      apt-get update && apt-get install -y --no-install-recommends {' '.join(tools)} \\",
            "      && rm -rf /var/lib/apt/lists/*; fi",
        ]
    elif v["base"] == DEFAULT_BASE[v["backend"]]:
        # shared, published toolchain base: no per-engine apt layer for the common tools
        lines[5] = f"FROM {base_tag(v['backend'])}" + (" AS build" if v.get("runtime_base") else "")
        extra = [a for a in (v.get("apt") or []) if a not in BUILD_TOOLS + DEFAULT_APT.get(v["backend"], [])]
        if extra:
            lines += ["RUN apt-get update && apt-get install -y --no-install-recommends \\",
                      f"        {' '.join(extra)} \\",
                      "    && rm -rf /var/lib/apt/lists/*"]
    else:
        tools = BUILD_TOOLS + list(v.get("apt") or [])
        lines += [
            "RUN apt-get update && apt-get install -y --no-install-recommends \\",
            f"        {' '.join(tools)} \\",
            "    && rm -rf /var/lib/apt/lists/*",
        ]
        if any("uv " in st for st in v["install"]):
            lines.append("COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /uvx /opt/llgenie/bin/")
    lines += [
        "",
        "WORKDIR /opt/llgenie/app",
        "COPY engine_runner.py entrypoint.sh params.json ./",
    ]
    lines.append("RUN chmod +x entrypoint.sh" + ("" if v.get("prebuilt") else
                                             " && python3 engine_runner.py install params.json && rm -rf /root/.cache"))
    if v.get("runtime_base"):  # multi-stage: compiled binary onto the slim runtime base
        if not lines[5].endswith(" AS build"):
            lines[5] = lines[5] + " AS build"
        rt_tools = ["ca-certificates", "curl", "python3"] + RUNTIME_APT.get(v["backend"], [])
        lines += ["", f"FROM {v['runtime_base']}",
                  "ENV DEBIAN_FRONTEND=noninteractive HF_HOME=/models/hf",
                  "RUN apt-get update && apt-get install -y --no-install-recommends \\",
                  f"        {' '.join(rt_tools)} \\",
                  "    && rm -rf /var/lib/apt/lists/*"]
        for path in v.get("runtime_copy") or []:
            lines.append(f"COPY --from=build {path} {path}")
        lines += ["COPY --from=build /opt/llgenie/app /opt/llgenie/app",
                  "WORKDIR /opt/llgenie/app"]
    lines += [
        "",
        f"ENV LLGENIE_ENGINE={params['id']} LLGENIE_BACKEND={v['backend']} LLGENIE_VARIANT={variant} \\",
        "    LLGENIE_HOST=0.0.0.0 LLGENIE_PORT=11434"
        + (' \\\n    LD_LIBRARY_PATH=/app' if 'ggml-org/llama.cpp' in str(v.get('base', '') or '') else ''),
        f'LABEL org.opencontainers.image.title="llgenie-{tag}" llgenie.engine="{params["id"]}" \\',
        f'      llgenie.variant="{variant}" llgenie.pinned="{params["pinned"]}" \\',
        '      llgenie.api="openai" llgenie.model="llm-local" llgenie.port="11434"',
        "EXPOSE 11434",
        'VOLUME ["/models"]',
        "HEALTHCHECK --interval=15s --timeout=5s --start-period=600s --retries=3 \\",
        "    CMD /opt/llgenie/app/entrypoint.sh health",
        'ENTRYPOINT ["/opt/llgenie/app/entrypoint.sh"]',
        'CMD ["serve"]',
        "",
    ]
    return "\n".join(lines)


def dockerfile_path(skill_id: str, variant: str) -> Path:
    return DOCKERFILES_DIR / skill_id / f"Dockerfile.{variant}"


def pick_variant(params: dict, backend: str, hw: dict) -> str:
    """One image per backend. Warn when this GPU is not in the fat arch list."""
    if backend not in params["variants"]:
        raise SystemExit(f"[engine-skills] {params['id']}: no image for {backend} "
                         f"(have {', '.join(params['variants'])})")
    v = params["variants"][backend]
    have = (v.get("build_args", {}).get("CUDA_ARCH") if backend == "cuda" else
            v.get("build_args", {}).get("GPU_TARGETS") if backend == "rocm" else "")
    mine = (hw.get("cuda_arch") if backend == "cuda" else hw.get("gpu_targets") if backend == "rocm" else "")
    if have and mine and not set(mine.split(";")) & set(have.split(";")):
        print(f"[engine-skills] note: {params['id']}/{backend} image targets {have}; this GPU is {mine}",
              file=sys.stderr)
    return backend


def _image_hash(params: dict, variant: str) -> str:
    import hashlib
    h = hashlib.sha256(json.dumps(params["variants"][variant], sort_keys=True).encode())
    h.update(render_dockerfile(params, variant).encode())
    for f in (CONTAINER_DIR / "entrypoint.sh", REPO_ROOT / "scripts" / "engine_runner.py"):
        h.update(f.read_bytes())
    return h.hexdigest()[:8]


def image_spec(params: dict, variant: str) -> dict:
    v = params["variants"][variant]
    tag = f"llgenie/{params['id'].replace('.', '-')}:{str(params['pinned'])[:8]}-{_image_hash(params, variant)}-{variant}"
    return {"id": params["id"], "engine": params["engine"], "backend": v["backend"], "variant": variant,
            "tag": tag, "params_file": str(params_path(params["id"]).relative_to(REPO_ROOT)),
            "dockerfile": str(dockerfile_path(params["id"], variant).relative_to(REPO_ROOT)),
            "build_args": {"BASE_IMAGE": v["base"], "ENGINE": params["id"], "BACKEND": v["backend"],
                           "VARIANT": variant, "APT_EXTRA": " ".join(v["apt"]), **v["build_args"]},
            "run_args": v["run_args"], "port": v["port"]}


# ---------------------------------------------------------------------------
# Validation against the trending-local-llms registry
# ---------------------------------------------------------------------------
def load_registry(src: str) -> dict:
    if re.match(r"^https?://", src):
        with urllib.request.urlopen(src, timeout=30) as resp:  # noqa: S310 (fixed https URL)
            data = json.load(resp)
    else:
        data = json.loads(Path(src).read_text())
    return data.get("engines", data)


def validate(skills: dict, registry: dict | None = None) -> list[str]:
    errors = []
    for sid, s in skills.items():
        where = f"{sid} ({s.get('_path')})"
        for k in REQUIRED_KEYS:
            if s.get(k) in (None, "", []) and k != "backends":
                errors.append(f"{where}: missing {k}")
        if Path(s["_path"]).parent.name != s.get("id"):
            errors.append(f"{where}: id must equal its directory name")
        if s.get("name") != f"engine-{s.get('id')}".replace(".", "-"):
            errors.append(f"{where}: name must be engine-<id with dots as dashes>")
        if not re.match(r"^[0-9a-f]{40}$", str(s.get("pinned", ""))):
            errors.append(f"{where}: pinned must be a full 40-hex commit sha")
        if s.get("ref_kind") not in ("branch", "tag"):
            errors.append(f"{where}: ref_kind must be branch or tag")
        if s.get("servable") not in SERVABLE:
            errors.append(f"{where}: servable must be true, false or via")
        bad = [b for b in s.get("backends") or [] if b not in BACKENDS]
        if bad:
            errors.append(f"{where}: unknown backends {bad}")
        if s.get("servable") is True:
            for k in SERVABLE_KEYS:
                if not s.get(k):
                    errors.append(f"{where}: servable engine needs {k}")
            if s.get("alias_mode") not in ALIAS_MODES:
                errors.append(f"{where}: alias_mode must be one of {ALIAS_MODES}")
            launch = " ".join(str(x) for x in (_flatten(s.get("launch")) + _flatten(s.get("post_launch"))
                                                 + _flatten(s.get("pre_launch")) + _flatten(s.get("env"))))
            if s.get("alias_mode") != "any-name" and "{alias}" not in launch:
                errors.append(f"{where}: launch must expose the model as {{alias}}")
            if "{port}" not in launch:
                errors.append(f"{where}: launch must bind {{port}}")
            for b in s.get("backends") or []:
                if not _per_backend(s.get("install"), b):
                    errors.append(f"{where}: no install steps for backend {b}")
        if s.get("servable") == "via":
            if not s.get("via"):
                errors.append(f"{where}: servable: via needs a via: [host engine ids] list")
            for v in s.get("via") or []:
                if v not in skills:
                    errors.append(f"{where}: via engine {v!r} has no skill")
        for b, params in (s.get("hw_flags") or {}).items():
            for param in params or {}:
                if param not in ("cuda_arch", "gpu_targets", "cuda_major", "jobs", "compute_cap", "torch_backend"):
                    errors.append(f"{where}: hw_flags.{b}.{param} is not a detected hardware parameter")
        for b in s.get("backends") or []:
            steps = " ".join(str(x) for x in _flatten(_per_backend(s.get("install"), b)))
            if "venv" in steps:
                errors.append(f"{where}: install.{b} creates a venv; engines run from container images")
            if "--system" in steps and b == "metal":
                errors.append(f"{where}: install.metal must not use --system (host); use `uv tool install`")
        cont = s.get("container")
        if cont is not None and cont is not False and not isinstance(cont, dict):
            errors.append(f"{where}: container must be false or a per-backend mapping")
        if isinstance(cont, dict):
            for b, spec in cont.items():
                if b not in (s.get("backends") or []) or b == "metal":
                    errors.append(f"{where}: container.{b} is not a containerizable backend of this skill")
                elif spec is not False and not isinstance(spec, dict):
                    errors.append(f"{where}: container.{b} must be false or a mapping")
        try:
            for b in s.get("backends") or []:
                if s.get("servable") is False:
                    continue
                plan(s, b, _fake_hw(b))
        except KeyError as exc:
            errors.append(f"{where}: {exc}")
    if registry is not None:
        engines = {s.get("engine") for s in skills.values()}
        for name in registry:
            if name not in engines:
                errors.append(f"registry engine {name!r} has no skill (add skills/engines/<id>/SKILL.md)")
        for sid, s in skills.items():
            if s.get("engine") not in registry:
                errors.append(f"{sid}: engine {s.get('engine')!r} is not a key in the registry engines{{}}")
    return errors


def _flatten(v) -> list:
    if v is None:
        return []
    if isinstance(v, dict):
        return [x for val in v.values() for x in _flatten(val)]
    return list(v) if isinstance(v, list) else [v]


def _fake_hw(backend: str) -> dict:
    return {"os": "linux", "arch": "amd64", "machine": "x86_64", "backend": backend,
            "card_ram_bytes": 16 * 1024 ** 3, "compute_cap": "8.9", "cuda_arch": "89",
            "cuda_version": "13.0", "cuda_major": "13", "gpu_targets": "gfx1100",
            "torch_backend": "auto", "jobs": "8"}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="llgenie engine skills runner")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    h = sub.add_parser("hardware")
    h.add_argument("--json", action="store_true")
    v = sub.add_parser("validate")
    v.add_argument("--registry", default=None, help="models.json path or URL (default: none)")
    for name in ("plan", "check", "install", "detect"):
        p = sub.add_parser(name)
        p.add_argument("id")
        p.add_argument("--backend", choices=BACKENDS, default=None)
        if name == "plan":
            p.add_argument("--json", action="store_true")
        if name == "install":
            p.add_argument("--dry", action="store_true")
            p.add_argument("--image-build", action="store_true",
                           help="container build: skip GPU probes/floors (enforced at run)")
    pp = sub.add_parser("params", help="regenerate containers/engines/params/*.json from the skills")
    pp.add_argument("--check", action="store_true", help="exit 1 if any committed params file is stale")
    sv = sub.add_parser("serve")
    sv.add_argument("id")
    sv.add_argument("--backend", choices=BACKENDS, default=None)
    sv.add_argument("--model", required=True)
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=11434)
    sv.add_argument("--drafter", default="")
    be = sub.add_parser("build-env")
    be.add_argument("id")
    be.add_argument("backend", choices=BACKENDS)
    a = ap.parse_args(argv)

    skills = load_skills()
    if a.cmd == "list":
        hw = detect_hardware()
        for sid, s in skills.items():
            ok = hw["backend"] in (s.get("backends") or [])
            print(f"{sid:28} {str(s.get('servable')):5} {','.join(s.get('backends') or []) or '-':30} "
                  f"{'fits ' + hw['backend'] if ok else ''}")
        return 0
    if a.cmd == "hardware":
        hw = detect_hardware()
        print(json.dumps(hw, indent=2) if a.json else "\n".join(f"{k:15} {v}" for k, v in hw.items()))
        return 0
    if a.cmd == "validate":
        reg = load_registry(a.registry) if a.registry else None
        errors = validate(skills, reg)
        for e in errors:
            print(f"[skills-validate] {e}", file=sys.stderr)
        print(f"[skills-validate] {len(skills)} skills, "
              f"{'registry ' + str(len(reg)) + ' engines, ' if reg is not None else ''}"
              f"{len(errors)} error(s)")
        return 1 if errors else 0
    if a.cmd == "params":
        changed = write_params(skills, check_only=a.check)
        for rel in changed:
            print(f"[engine-params] {'STALE' if a.check else 'updated'} {rel}")
        print(f"[engine-params] {len(changed)} file(s) {'stale' if a.check else 'changed'}")
        return 1 if (a.check and changed) else 0
    hw = detect_hardware()
    skill = get_skill(a.id, skills)
    if a.cmd == "build-env":
        ctx = context(skill, a.backend, hw)
        out = {"REPO_URL": skill["repo"].rstrip("/") + ".git", "BRANCH": skill["ref"],
               "TREE_DIR": ctx["src"], "BUILD_DIR": ctx["build"],
               "CMAKE_FLAGS": cmake_flags(skill, a.backend, hw)}
        for k, val in out.items():
            print(f"{k}={shlex.quote(val)}")
        # double quotes on purpose: skill env may use $(hipconfig -R) and is
        # expanded by the caller's eval. Values come from repo skills.
        for line in env_prelude(build_env(skill, a.backend, hw)).split("; "):
            if line.strip():
                print(line.strip())
        return 0
    backend = pick_backend(skill, hw, a.backend) if a.cmd != "check" else (a.backend or hw["backend"])
    if a.cmd == "serve":
        return serve(skill, backend, {**hw, "backend": backend}, a.model, a.host, a.port, a.drafter)
    if a.cmd == "plan":
        p = plan(skill, backend, hw)
        if a.json:
            print(json.dumps(p, indent=2))
        else:
            for k, val in p.items():
                print(f"{k:12} {val}")
        return 0
    if a.cmd == "check":
        blockers = check(skill, backend, hw)
        for b in blockers:
            print(f"[engine-skills] {skill['id']}/{backend}: {b}")
        if not blockers:
            print(f"[engine-skills] {skill['id']}/{backend}: OK")
        return 1 if blockers else 0
    if a.cmd == "install":
        if a.image_build:
            os.environ["LLGENIE_IMAGE_BUILD"] = "1"
        return install(skill, backend, {**hw, "backend": backend}, dry=a.dry, skills=skills,
                       mode="build" if a.image_build else "native")
    if a.cmd == "detect":
        return detect(skill, backend, hw)
    return 1


if __name__ == "__main__":
    sys.exit(main())
