"""Deterministic build-parameter derivation from an upstream tree (issue #107).

Reads the upstream repo at a sha via `git show <sha>:<path>` on a
`--filter=blob:none` clone, so nothing is checked out. Produces a stable
`findings` JSON. No LLM anywhere: git, regex and file parsing only.

Extractors (each a pure function `(repo_dir, skill) -> Findings`):
  E1 cmake options   option(NAME ...) / set(NAME ... CACHE ...) at the new sha
  E2 cmake renames   llama_option_depr(LEVEL OLD NEW) -> auto-replace -DOLD with -DNEW
  E3 cmake removed   a skill -DNAME that was an option at the old sha and is gone
                     at the new sha (no rename) -> hard fail
  E4 upstream recipe cmake -B/-S line(s) in each backend recipe Dockerfile;
                     mirror-listed flags auto-added, others report-only
  E5 toolchain       ARG CUDA_VERSION/ROCM_VERSION -> toolchain.<backend>
  E6 gpu targets var which of GPU_TARGETS/AMDGPU_TARGETS the HIP CMakeLists reads
  E7 python/torch    requires-python / torch== pin -> toolchain.python / torch_backend
  E8 launch flags    flags in skill launch absent from flags_from / --help -> hard fail
  E9 watch report    git diff --numstat old..new -- <upstream_watch> -> per-backend

Each skill declares which extractors apply in a `derive:` frontmatter key, so
the generic code has no per-engine `if`.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from . import engine_skills as es
except ImportError:  # pragma: no cover - script mode
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import engine_skills as es

REPO_ROOT = es.REPO_ROOT

_OPTION = re.compile(r"^\s*option\(\s*([A-Za-z0-9_]+)", re.MULTILINE)
_CACHE = re.compile(r"^\s*set\(\s*([A-Za-z0-9_]+)\s+[^\s]+\s+CACHE", re.MULTILINE)
_DEPR = re.compile(r"llama_option_depr\(\s*[A-Za-z0-9_]+\s+([A-Za-z0-9_]+)\s+([A-Za-z0-9_]+)")
_CMAKE_FLAG = re.compile(r"-D([A-Za-z0-9_]+)(?:=([^ \t]+))?")
_ARG = re.compile(r"^\s*ARG\s+([A-Za-z0-9_]+)=(.+)$", re.MULTILINE)
_TORCH = re.compile(r"torch==([0-9.]+)\+cu(\d+)")
_PYTHON = re.compile(r"requires-python\s*=\s*[\"']?([0-9.]+)")

# Default mapping of upstream_watch paths -> backends (overridable per skill).
_WATCH_BACKENDS = [
    (re.compile(r"ggml-cuda/"), "cuda"),
    (re.compile(r"ggml-hip/"), "rocm"),
    (re.compile(r"ggml-vulkan/"), "vulkan"),
    (re.compile(r"ggml-metal/"), "metal"),
    (re.compile(r"(^|/)(CMakeLists\.txt|docs/|README)"), "all"),
    (re.compile(r"(arg\.cpp|server/)"), "launch"),
]


class HardFail(Exception):
    """A build parameter cannot be derived deterministically. Nothing is guessed."""


def _git(repo_dir: Path, *args: str) -> str:
    p = subprocess.run(["git", "-C", str(repo_dir), *args], capture_output=True,
                       text=True, timeout=120)
    if p.returncode != 0:
        raise HardFail(f"git {' '.join(args)} failed: {p.stderr.strip()}")
    return p.stdout


def _show(repo_dir: Path, sha: str, path: str) -> str:
    """`git show <sha>:<path>`; raises HardFail when the file is absent."""
    p = subprocess.run(["git", "-C", str(repo_dir), "show", f"{sha}:{path}"],
                       capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        raise HardFail(f"no file {path!r} at {sha[:8]}")
    return p.stdout


def _cmake_flags(skill: dict, backend: str) -> list[str]:
    """The -D flags the skill uses for a backend (cmake_flags + hw_flags)."""
    out = []
    for key in ("cmake_flags", "hw_flags"):
        block = (skill.get(key) or {}).get(backend) or {}
        if isinstance(block, str):
            block = {"": block}
        for v in block.values():
            for m in _CMAKE_FLAG.finditer(str(v)):
                out.append(m.group(1))
    return out


def _options_at(repo_dir: Path, sha: str, files: list[str]) -> set[str]:
    opts: set[str] = set()
    for f in files:
        try:
            text = _show(repo_dir, sha, f)
        except HardFail:
            continue
        for m in _OPTION.finditer(text):
            opts.add(m.group(1))
        for m in _CACHE.finditer(text):
            opts.add(m.group(1))
    return opts


def _renames_at(repo_dir: Path, sha: str, files: list[str]) -> dict[str, str]:
    renames: dict[str, str] = {}
    for f in files:
        try:
            text = _show(repo_dir, sha, f)
        except HardFail:
            continue
        for m in _DEPR.finditer(text):
            renames[m.group(1)] = m.group(2)
    return renames


def _recipe_cmake(repo_dir: Path, sha: str, recipe: str) -> str:
    """The joined `cmake -B/-S ...` line(s) from a recipe Dockerfile."""
    text = _show(repo_dir, sha, recipe)
    lines = []
    for ln in text.splitlines():
        if "cmake" in ln and ("-B" in ln or "-S" in ln):
            lines.append(ln.rstrip("\\").strip())
    if not lines:
        raise HardFail(f"recipe {recipe!r} has no cmake -B/-S line at {sha[:8]}")
    return " ".join(lines)


def _toolchain_arg(repo_dir: Path, sha: str, file: str, arg: str) -> str:
    text = _show(repo_dir, sha, file)
    for m in _ARG.finditer(text):
        if m.group(1) == arg:
            return m.group(2).strip()
    raise HardFail(f"ARG {arg} not found in {file!r} at {sha[:8]}")


def _watch_backends(skill: dict, changed: list[str]) -> list[str]:
    override = skill.get("upstream_watch_backends") or {}
    out: set[str] = set()
    for path in changed:
        if path in override:
            out.update(override[path] if isinstance(override[path], list) else [override[path]])
            continue
        # specific backend patterns first; 'all'/'launch' only when nothing specific matched
        specific = [b for pat, b in _WATCH_BACKENDS if b not in ("all", "launch") and pat.search(path)]
        if specific:
            out.update(specific)
            continue
        for pat, backend in _WATCH_BACKENDS:
            if pat.search(path):
                out.add(backend)
    return sorted(out)


def derive(skill: dict, sha: str, repo_dir: Path | None = None,
           old_sha: str | None = None) -> dict:
    """Run the extractors the skill declares. Returns a stable findings dict.

    `repo_dir` is a `--filter=blob:none` clone of the skill's repo (created here
    when not given). `old_sha` enables the E9 watch diff; without it E9 is empty.
    """
    derive_cfg = skill.get("derive") or {}
    findings: dict = {"sha": sha, "auto": {}, "report": {}, "hard_fail": None}

    own_dir = repo_dir is None
    if own_dir:
        repo_dir = Path(tempfile.mkdtemp(prefix="llgenie-derive-"))
        repo_url = skill["repo"].rstrip("/")
        if "://" in repo_url or repo_url.startswith("git@"):
            repo_url += ".git"
        subprocess.run(["git", "clone", "--filter=blob:none", "--no-checkout",
                        repo_url, str(repo_dir)],
                       capture_output=True, text=True, timeout=300, check=True)

    try:
        # E1/E2/E3: cmake options + renames + removed
        cmake = derive_cfg.get("cmake") or {}
        opt_files = cmake.get("options_from") or []
        if opt_files:
            opts = _options_at(repo_dir, sha, opt_files)
            renames = _renames_at(repo_dir, sha, opt_files)
            findings["report"]["cmake_options"] = sorted(opts)
            findings["auto"]["renames"] = dict(sorted(renames.items()))
            # E3: only a flag that WAS an option at the old sha and is gone now
            # (with no rename) is a hard fail. Standard CMake built-ins like
            # CMAKE_CUDA_ARCHITECTURES are never options and are skipped.
            old_opts = _options_at(repo_dir, old_sha, opt_files) if old_sha else set()
            for backend in skill.get("backends") or []:
                for flag in _cmake_flags(skill, backend):
                    if flag in renames:
                        findings["auto"].setdefault("renamed_flags", {})[flag] = renames[flag]
                    elif flag in old_opts and flag not in opts:
                        raise HardFail(f"cmake option {flag} gone at {sha[:8]}")

        # E4: upstream recipe flags
        recipe = cmake.get("recipe") or {}
        mirror = cmake.get("mirror") or []
        for backend, rfile in recipe.items():
            line = _recipe_cmake(repo_dir, sha, rfile)
            recipe_flags = {m.group(1): m.group(2) for m in _CMAKE_FLAG.finditer(line)}
            findings["report"].setdefault("recipe_flags", {})[backend] = recipe_flags
            for flag, val in recipe_flags.items():
                if flag in mirror:
                    findings["auto"].setdefault("mirrored_flags", {})[flag] = val

        # E5: toolchain
        tc = derive_cfg.get("toolchain") or {}
        for backend, spec in tc.items():
            arg = spec.get("arg")
            if arg:
                val = _toolchain_arg(repo_dir, sha, spec["file"], arg)
                findings["auto"].setdefault("toolchain", {})[backend] = val

        # E6: gpu targets var
        gtv = derive_cfg.get("gpu_targets_var")
        if gtv:
            text = _show(repo_dir, sha, gtv["file"])
            used = [c for c in gtv["candidates"] if c in text]
            if used:
                findings["auto"]["gpu_targets_var"] = used[0]

        # E7: python/torch
        py = derive_cfg.get("python") or {}
        if py.get("pyproject"):
            text = _show(repo_dir, sha, py["pyproject"])
            m = _TORCH.search(text)
            if m:
                findings["auto"]["torch_backend"] = f"cu{m.group(2)}"
            m2 = _PYTHON.search(text)
            if m2:
                findings["auto"]["python"] = m2.group(1)

        # E8: launch flags
        launch = derive_cfg.get("launch") or {}
        if launch.get("flags_from"):
            text = _show(repo_dir, sha, launch["flags_from"])
            for flag in re.findall(r"--[a-z0-9-]+", str(skill.get("launch", ""))):
                if flag not in text:
                    raise HardFail(f"launch flag {flag} gone at {sha[:8]}")

        # E9: watch diff
        if old_sha and skill.get("upstream_watch"):
            numstat = _git(repo_dir, "diff", "--numstat", f"{old_sha}..{sha}",
                           "--", *skill["upstream_watch"])
            changed = [ln.split("\t")[2] for ln in numstat.splitlines() if "\t" in ln]
            findings["report"]["watch_changed"] = changed
            findings["report"]["watch_backends"] = _watch_backends(skill, changed)
    finally:
        if own_dir:
            subprocess.run(["rm", "-rf", str(repo_dir)], capture_output=True)

    return findings


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="derive engine build params from an upstream sha")
    ap.add_argument("engine")
    ap.add_argument("--sha", default="")
    ap.add_argument("--old-sha", default="")
    a = ap.parse_args(argv)
    skill = es.get_skill(a.engine)
    sha = a.sha or skill["pinned"]
    try:
        findings = derive(skill, sha, old_sha=a.old_sha or None)
    except HardFail as e:
        print(f"[engine-derive] HARD FAIL: {e}")
        return 1
    print(json.dumps(findings, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
