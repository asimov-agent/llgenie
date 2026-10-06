#!/usr/bin/env python3
"""Shell variables for a native llama.cpp-family build, from the GENERATED params.

  python3 scripts/native_build_env.py <engine-id> <backend>

Reads containers/engines/params/<engine-id>.json (written by
`make generate-engine-params` from the skill; never the skill itself) and the
detected hardware (scripts/detect_server.py) to print REPO_URL, BRANCH,
TREE_DIR, BUILD_DIR, CMAKE_FLAGS and exports, for scripts/build_llama_server.sh
to eval. Stdlib only. No LLM, no skills.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def detected(param: str) -> str:
    env = {"cuda_arch": "LLGENIE_CUDA_ARCH", "gpu_targets": "LLGENIE_GPU_TARGETS"}[param]
    if os.environ.get(env, "").strip():
        return os.environ[env].strip()
    if param == "cuda_arch" and shutil.which("nvidia-smi"):
        out = subprocess.run(["nvidia-smi", "--query-gpu=compute_cap", "--format=csv,noheader"],
                             capture_output=True, text=True).stdout
        caps = sorted({c.strip().replace(".", "") for c in out.splitlines() if re.match(r"^\d+\.\d+$", c.strip())})
        return ";".join(caps)
    if param == "gpu_targets" and shutil.which("rocminfo"):
        out = subprocess.run(["rocminfo"], capture_output=True, text=True).stdout
        return ";".join(sorted(set(re.findall(r"Name:\s+(gfx[0-9a-f]+)\b", out))))
    return ""


def main(argv: list[str]) -> int:
    engine, backend = argv[1], argv[2]
    params = json.loads((ROOT / "containers" / "engines" / "params" / f"{engine}.json").read_text())
    nat = params.get("native", {}).get(backend)
    if not nat:
        print(f"[native-build-env] {engine} has no native {backend} build in its params", file=sys.stderr)
        return 1
    server_root = os.environ.get("SERVER_ROOT") or str(Path.home() / "repository" / "git")
    tree = f"{server_root}/{nat['src_dir']}"
    flags = [nat["cmake_flags"]]
    for param, template in nat["hw_flags"].items():
        val = detected(param)
        if val:  # build_llama_server.sh word-splits $CMAKE_FLAGS: no shell quotes here
            flags.append(template.replace("{" + param + "}", val).strip("'"))
    out = {"REPO_URL": params["repo"] + ".git", "BRANCH": params["ref"], "TREE_DIR": tree,
           "BUILD_DIR": f"{tree}/{nat['build_dir']}", "CMAKE_FLAGS": " ".join(f for f in flags if f)}
    for k, v in out.items():
        print(f"{k}={shlex.quote(v)}")
    for k, v in nat["env"].items():  # may contain $(hipconfig -R): expanded by the caller's eval
        esc = str(v).replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`")
        print(f'export {k}="{esc}"')
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
