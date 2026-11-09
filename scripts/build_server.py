#!/usr/bin/env python3
"""Build the llama.cpp server variant (issue #800 extraction of the build-server/build-variant recipes).

The 15-line `build-server` and 13-line `build-variant` recipes were shell orchestration wrapped
around `scripts/build_llama_server.sh`: resolve tree/backend (explicit or auto-detected), run the
build with the env seams the make recipes set, tee to a log, read the binary path from the log's
last line, verify the binary is executable, stamp `SERVER_BIN_STAMP`, and clean the log. This module
names that orchestration as a tested entry point; the recipes became one-line calls that pass the
same seams:

  build-server   -> python3 scripts/build_server.py build --detect --repo P --server-root R --stamp S
  build-variant  -> python3 scripts/build_server.py build --tree T --backend B --repo P --server-root R --stamp S

Behaviour is unchanged: the same build script runs with the same environment, the same exit-code
contract holds (a missing or non-executable binary is a loud failure, never a skip), and the same
stamp file is written to.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

#: The RAM byte cap make's build-variant passed as LLAMA_RAM_BYTES (16 GiB) — the tree decision's
#: cap for a native variant. Kept identical to the recipe it replaces.
VARIANT_RAM_BYTES = "17179869184"


def _detect(detect_server_path: Path) -> tuple[str, str]:
    """`(tree, backend)` by importing the same detect_server module the old recipe shelled out to."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("ds", detect_server_path)
    if spec is None or spec.loader is None:
        return "", ""
    ds = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ds)
    return ds.detect_all()["tree"], ds.detect_all()["backend"]


def _resolve_linebuf() -> list[str]:
    """`LINEFBUF` = `stdbuf -oL -eL` when stdbuf exists (the old `command -v stdbuf` branch)."""
    if shutil.which("stdbuf"):
        return ["stdbuf", "-oL", "-eL"]
    return []


def build(*, repo: Path, server_root: Path, stamp: Path,
          tree: str | None = None, backend: str | None = None) -> int:
    """Run the server build exactly like the recipe did.

    `tree`/`backend` given -> explicit variant (build-variant); both None -> detect from the card
    (build-server). Returns 0 on a verified binary, 1 on failure — a missing or non-executable
    binary is a loud error, never a skip. Without `tree`/`backend` the card must yield both, else
    the old recipe's "detect_server produced no tree/backend" failure.
    """
    os.environ.setdefault("SERVER_ROOT", str(server_root))
    if tree is not None and backend is not None:
        # build-variant: explicit tree/backend, with the env seams the recipe set.
        env = dict(os.environ)
        env.update({
            "TREE": tree,
            "BACKEND": backend,
            "LLAMA_SERVER_TREE": tree,
            "LLAMA_BACKEND": backend,
            "LLAMA_RAM_BYTES": VARIANT_RAM_BYTES,
            "SERVER_ROOT": str(server_root),
        })
    else:
        # build-server: auto-detect tree/backend from the card.
        env = dict(os.environ)
        env["SERVER_ROOT"] = str(server_root)
        tree, backend = _detect(repo / "scripts" / "detect_server.py")
        if not tree or not backend:
            print("ERROR: detect_server produced no tree/backend", file=sys.stderr)
            return 1
        print("==> detect_server: tree/backend for this card")

    print(f"==> building server: tree={tree} backend={backend} (clone-or-pull + build)")
    # the recipe ran the shared build script directly, tee'd to a log
    cmd = _resolve_linebuf() + [str(repo / "scripts" / "build_llama_server.sh"), tree, backend]
    with tempfile.NamedTemporaryFile("w+", suffix=".log", delete=False) as logf:
        log_path = Path(logf.name)
        try:
            proc = subprocess.run(cmd, stdout=logf, stderr=subprocess.STDOUT,
                                  env=env, text=True)  # proc-allow: the build's stream IS the log
        except FileNotFoundError:
            print(f"ERROR: {cmd[0]} was not found on PATH", file=sys.stderr)
            log_path.unlink(missing_ok=True)
            return 1
        if proc.returncode != 0:
            logf.flush()
            tail = "".join(log_path.read_text().splitlines()[-5:]) if log_path.exists() else ""
            log_path.unlink(missing_ok=True)
            print(f"ERROR: build script exited {proc.returncode}\n{tail[-800:]}", file=sys.stderr)
            return proc.returncode
        logf.flush()
        try:
            lines = log_path.read_text().splitlines()
            srv = lines[-1].strip() if lines else ""
        finally:
            log_path.unlink(missing_ok=True)
    if not srv or not os.access(srv, os.X_OK):
        print(f"ERROR: {'build-variant' if tree and backend else 'build-server'} did not produce a "
              f"binary ({srv or 'empty log'})", file=sys.stderr)
        return 1

    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text(f"{srv}\n")
    print(f"==> server binary: {srv} (stamped to {stamp})")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build the llama.cpp server variant (issue #800)")
    ap.add_argument("cmd", choices=("build",))
    ap.add_argument("--tree", default=None, help="explicit TREE (prism|upstream); else detect")
    ap.add_argument("--backend", default=None, help="explicit BACKEND (metal|cuda|cpu); else detect")
    ap.add_argument("--repo", default=str(Path(__file__).resolve().parent.parent),
                    help="the repo root (the Makefile's REPO)")
    ap.add_argument("--server-root", default=os.environ.get("SERVER_ROOT", "~/repository/git"),
                    help="SERVER_ROOT (where llama.cpp trees are cloned)")
    ap.add_argument("--stamp", default="~/.llgenie/server.bin.path",
                    help="the SERVER_BIN_STAMP file to write the binary path into")
    a = ap.parse_args(argv)
    server_root = Path(a.server_root).expanduser()
    if a.tree is None and a.backend is not None or a.tree is not None and a.backend is None:
        ap.error("--tree and --backend must be given together (or both omitted to detect)")
    if a.tree is not None and a.backend is not None:
        return build(repo=Path(a.repo), server_root=server_root,
                     stamp=Path(a.stamp).expanduser(), tree=a.tree, backend=a.backend)
    return build(repo=Path(a.repo), server_root=server_root,
                 stamp=Path(a.stamp).expanduser())


if __name__ == "__main__":
    raise SystemExit(main())
