#!/usr/bin/env python3
"""build-server's detect → build → stamp flow as an entry point (issue #2675).

The `build-server` make target is a thin wrapper that calls this module. It reproduces
the replaced recipe's exact order and failure semantics:

1. announce detect_server, then resolve tree/backend for this card (base ran
   `scripts/detect_server.py`, then asked it twice via `$(shell ...)`; one in-process
   `detect_all()` call is the same probe), error out if either is empty;
2. announce the build, then run `<repo>/scripts/build_llama_server.sh <tree> <backend>`
   with SERVER_ROOT exported, streaming stdout+stderr line-buffered to the console and
   teed to the build log (the base's `stdbuf -oL -eL ... | tee` behaviour — python's
   line loop is inherently line-buffered, so the stdbuf branch is moot);
3. like the base under `set -o pipefail` WITHOUT `set -e`: the build's own exit status
   is not checked — the gate is the stamped binary: `SRV = last log line`, and a failing
   build fails at `test -x "$SRV"`;
4. stamp the binary path, remove the log, report the binary.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

BUILD_LOG = "/tmp/llgenie_srv_build.log"


def build(server_root: str, repo: str, stamp: str, log: str = BUILD_LOG) -> int:
    print("==> detect_server: tree/backend for this card")
    sys.path.insert(0, repo)
    from scripts.detect_server import detect_all
    detected = detect_all()
    tree, backend = detected.get("tree", ""), detected.get("backend", "")
    if not tree or not backend:
        print("ERROR: detect_server produced no tree/backend", file=sys.stderr)
        return 1
    print(f"==> building server: tree={tree} backend={backend} (clone-or-pull + build)")
    env = dict(os.environ, SERVER_ROOT=server_root)
    with open(log, "w") as logfile:
        proc = subprocess.Popen(
            [os.path.join(repo, "scripts", "build_llama_server.sh"), tree, backend],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            logfile.write(line)
        proc.wait()
    with open(log) as logfile:
        lines = logfile.read().splitlines()
    srv = lines[-1].strip() if lines else ""
    if not srv or not os.access(srv, os.X_OK):
        print(f"ERROR: build-server did not produce a binary ({srv})", file=sys.stderr)
        return 1
    os.makedirs(os.path.dirname(stamp), exist_ok=True)
    with open(stamp, "w") as stampfile:
        stampfile.write(f"{srv}\n")
    os.remove(log)
    print(f"==> server binary: {srv} (stamped to {stamp})")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Detect the card's tree/backend, build the llama "
                                             "server, stamp the binary path.")
    ap.add_argument("--server-root", required=True, help="SERVER_ROOT export for the build script")
    ap.add_argument("--repo", required=True, help="llgenie repo root (make REPO)")
    ap.add_argument("--stamp", required=True, help="file the built binary path is stamped to")
    args = ap.parse_args(argv)
    return build(args.server_root, args.repo, args.stamp)


if __name__ == "__main__":
    sys.exit(main())
