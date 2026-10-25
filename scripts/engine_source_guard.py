#!/usr/bin/env python3
"""A cell that claims to be built from source must actually compile.

`variants.<arch>.prebuilt: false` is a promise: this engine is cloned at its pinned
commit and built here, with this backend's parameters. A cell can break that promise in
one way only — its `install` steps download a ready-made artefact (a wheel, a release
tarball) and never run the engine's own build. Such a cell shows up as a source build in
every report and is really a pull.

This checks the committed params (`containers/engines/params/*.json`), i.e. exactly what
`generate-engine-params` writes into that engine's Dockerfile, so it can fail without
Docker available.

A cell that genuinely has no source build yet is recorded in `KNOWN_NOT_SOURCE` with the
reason and its issue (the `DISABLED` pattern): it is reported, and the gate fails only on
a NEW cell that claims a build it does not have.

    python3 scripts/engine_source_guard.py check     # exit 1 on a new finding
    python3 scripts/engine_source_guard.py report    # print the census, never fails
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARAMS = os.path.join(REPO_ROOT, "containers", "engines", "params")

# Something that compiles, or an install of the checked-out tree itself (a build).
BUILD_SIGNALS = (
    r"\bcmake\b", r"\bninja\b", r"\bmeson\b", r"\bbazel build\b", r"\bnvcc\b",
    r"\bcargo build\b", r"\bgo build\b", r"\bgo install\b", r"\bgradle\b", r"\bjavac\b",
    r"-m build\b", r"setup\.py", r"setup_[a-z_]+\.py", r"\bmake\b",
    # A python entrypoint that drives a native build (Strata compiles llama.cpp this way).
    r"get_llama_cpp\(", r"CMAKE_ARGS\s*=",
    # pip/uv installing the cloned tree (not a wheel by name): a lone `.` / `-e .`
    r"(?:pip|uv pip) install\b[^\n]*?(?:--no-build-isolation|--no-binary)[^\n]*",
    r"(?:pip|uv pip) install\b[^\n]*?\s(?:-e\s+)?\.(?:\s|\[|$)",
)

# Something that fetches another build's output instead of building.
DOWNLOAD_SIGNALS = (
    r"\bcurl\b", r"\bwget\b", r"\btar\s+-?[xz]", r"\bunzip\b", r"\bhf download\b",
    r"\baria2c\b", r"\bpip install\b[^\n]*?==\S*\.whl",
)

ARTEFACT_SUFFIXES = (".tar", ".tar.gz", ".tar.zst", ".tgz", ".zip", ".whl")

# Cells that say `prebuilt: false` today without a source build, and why. Each is tracked:
# removing the entry is what the issue does. Keep the reason concrete and dated.
KNOWN_NOT_SOURCE = {
    ("freetoken", "cuda"): "#615 install is a wheel (`freetoken[accel]==0.2.0`); needs the rocm-style clone+build",
    ("litert", "cpu"): "#615 install is a wheel (`litert-lm==0.18.1`); needs the LiteRT-LM source build",
    ("mlx", "cpu"): "#615 install is a wheel (`mlx[cpu] mlx-lm==0.32.2`); needs mlx's C++ core from source",
    ("mlx", "cuda"): "#615 install is a wheel (`mlx[cuda] mlx-lm==0.32.2`); needs mlx's C++ core from source",
    ("tensorfold", "cuda"): "#615 install downloads the `tensorfold-<ver>-linux-x86_64.tar.gz` release "
                             "and sha256-verifies it; upstream ships no buildable tree",
}


def cells() -> list[dict]:
    """Every committed cell, flattened, in a stable order."""
    rows = []
    for path in sorted(glob.glob(os.path.join(PARAMS, "*.json"))):
        doc = json.load(open(path))
        for arch, variant in (doc.get("variants") or {}).items():
            rows.append({"engine": doc["id"], "arch": arch,
                         "prebuilt": bool(variant.get("prebuilt")),
                         "install": list(variant.get("install") or [])})
    return rows


def _violation(row: dict) -> str | None:
    """Why this cell does not build, or None when it does."""
    text = "\n".join(row["install"])
    where = f"{row['engine']}/{row['arch']}"
    if not text.strip():
        return f"{where}: prebuilt=false but declares no install steps (nothing is built)"
    if not any(re.search(sig, text) for sig in BUILD_SIGNALS):
        return (f"{where}: prebuilt=false but its install steps run no build "
                f"(looked for cmake / make / cargo build / go build / pip install <tree> / setup.py)")
    for line in row["install"]:
        if (any(re.search(sig, line) for sig in DOWNLOAD_SIGNALS)
                and any(sfx in line for sfx in ARTEFACT_SUFFIXES)):
            return f"{where}: prebuilt=false but downloads a built artefact: {line.strip()[:140]}"
    return None


def findings(rows: list[dict] | None = None) -> list[tuple[str, str, str]]:
    """(engine/arch, message, tracked-issue-or-"") for every cell that claims a build it lacks."""
    out = []
    for row in rows if rows is not None else cells():
        if row["prebuilt"]:
            continue
        bad = _violation(row)
        if bad:
            out.append((f"{row['engine']}/{row['arch']}", bad, KNOWN_NOT_SOURCE.get((row["engine"], row["arch"]), "")))
    return out


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "check"
    rows = cells()
    source = [r for r in rows if not r["prebuilt"]]
    prebuilt = [r for r in rows if r["prebuilt"]]
    bad = findings(rows)
    known = [b for b in bad if b[2]]
    new = [b for b in bad if not b[2]]

    print(f"[engine-source] {len(rows)} cell(s): {len(source)} prebuilt=false, {len(prebuilt)} prebuilt=true")
    for _, msg, issue in known:
        print(f"[engine-source] tracked {issue}: {msg}")
    if cmd == "report":
        for _, msg, issue in new:
            print(f"[engine-source] UNTRACKED {msg}")
        return 0
    if cmd != "check":
        print(f"[engine-source] unknown command {cmd!r}; expected check|report", file=sys.stderr)
        return 2

    for _, msg, _issue in new:
        print(f"[engine-source] FAIL {msg}", file=sys.stderr)
    if new:
        print(f"[engine-source] {len(new)} cell(s) claim a source build and do not build, "
              f"with no tracked issue", file=sys.stderr)
        return 1
    print(f"[engine-source] OK: {len(source) - len(known)} of {len(source)} prebuilt=false cell(s) "
          f"run their own build; {len(known)} tracked in issue #615")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
