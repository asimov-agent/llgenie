#!/usr/bin/env python3
"""Start an already-built llama-server variant on its own port.

Does not rebuild, relink ~/bin/llama-server, or signal any other server.
A live server on another port (the usual one is 11434) is left running.

  make serve-variant TREE=prism BACKEND=cuda
  make serve-variant TREE=prism BACKEND=cuda PORT=18080

PORT omitted picks a free 127.0.0.1 port and never binds a port that is
already taken. --n-gpu-layers is never passed. llama-server keeps its
default and takes GPU or CPU, whichever it can.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

TREE_DIRS = {"prism": "prism-llama.cpp", "upstream": "llama.cpp"}
DEFAULT_MODEL = Path.home() / "models" / "Qwen" / "8GB" / "qwen2.5-0.5b-instruct-q4_0.gguf"


def variant_binary(server_root: Path, tree: str, backend: str) -> Path:
    if tree not in TREE_DIRS:
        raise SystemExit(f"ERROR: tree must be prism or upstream, got {tree!r}")
    if backend not in ("cpu", "cuda", "metal"):
        raise SystemExit(f"ERROR: backend must be cpu, cuda, or metal, got {backend!r}")
    return server_root / TREE_DIRS[tree] / f"build-{backend}" / "bin" / "llama-server"


def free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def port_is_free(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def serve_argv(binary: str, model: str, port: int) -> list[str]:
    return [
        binary, "--host", "127.0.0.1", "--port", str(port),
        "-m", model, "--alias", "llm-local",
        "--ctx-size", "2048",
    ]


def state_path(tree: str, backend: str) -> Path:
    return Path.home() / ".llgenie" / f"serve-{tree}-{backend}.json"


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def stop_recorded(state: Path, kill=os.kill) -> dict:
    """Stop only the pid this target recorded. Never scans for other servers."""
    if not state.is_file():
        raise SystemExit(f"ERROR: no serve-variant state at {state}")
    prev = json.loads(state.read_text())
    pid = int(prev.get("pid") or 0)
    port = prev.get("port")
    if not pid or not _alive(pid):
        state.unlink(missing_ok=True)
        return {"stopped": False, "pid": pid, "port": port, "reason": "not running"}
    kill(pid, signal.SIGTERM)
    for _ in range(50):
        if not _alive(pid):
            break
        time.sleep(0.1)
    else:
        kill(pid, signal.SIGKILL)
        time.sleep(0.2)
    state.unlink(missing_ok=True)
    return {"stopped": True, "pid": pid, "port": port}


def ensure_model(path: Path) -> Path:
    """Use the cached 0.5B file, or download it once when it is missing."""
    if path.is_file() and path.stat().st_size > 100_000_000:
        print(f"[serve-variant] using cached model: {path}")
        return path
    if path != DEFAULT_MODEL:
        raise SystemExit(f"ERROR: model not found: {path}")
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    import scripts.ci_health as ci_health
    hf = os.environ.get("HF_BIN") or ci_health._find_hf()
    ci_health._download_5b_model(hf)
    if not ci_health.MODEL_FILE.is_file():
        raise SystemExit("ERROR: model download failed")
    print(f"[serve-variant] model ready: {ci_health.MODEL_FILE}")
    return ci_health.MODEL_FILE


def chat_hi(port: int) -> str:
    body = json.dumps({
        "model": "llm-local",
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 16,
        "temperature": 0.0,
    }).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions",
        data=body, headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    reply = data.get("choices", [{}])[0].get("message", {}).get("content")
    if not reply or not reply.strip():
        raise SystemExit(f"ERROR: empty reply for 'hi' on {port}")
    return reply.strip()


def _wait_healthy(port: int, timeout: float = 90.0) -> bool:
    url = f"http://127.0.0.1:{port}/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200 and json.loads(resp.read()).get("status") == "ok":
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Serve one built variant on its own port")
    ap.add_argument("--tree", required=True)
    ap.add_argument("--backend", required=True)
    ap.add_argument("--port", type=int, default=0, help="0 picks a free port")
    ap.add_argument("--model", default=str(DEFAULT_MODEL))
    ap.add_argument("--server-root", default=str(Path.home() / "repository" / "git"))
    ap.add_argument("--stop", action="store_true", help="Stop the server this target started")
    ap.add_argument("--test", action="store_true",
                    help="POST hi, then stop the server this target started")
    args = ap.parse_args(argv)

    state = state_path(args.tree, args.backend)
    if args.stop:
        result = stop_recorded(state)
        print(f"stopped {args.tree}+{args.backend} pid={result['pid']} port={result['port']} "
              f"({result.get('reason') or 'stopped'})")
        return 0

    if state.is_file():
        prev = json.loads(state.read_text())
        pid = int(prev.get("pid") or 0)
        if pid and _alive(pid) and not args.test:
            print(f"already serving {args.tree}+{args.backend} pid={pid} "
                  f"http://127.0.0.1:{prev['port']}/health")
            return 0
        if pid and _alive(pid) and args.test:
            reply = chat_hi(int(prev["port"]))
            print(f"[hi] {reply[:120]}")
            result = stop_recorded(state)
            print(f"stopped {args.tree}+{args.backend} pid={result['pid']} port={result['port']}")
            return 0

    binary = variant_binary(Path(args.server_root), args.tree, args.backend)
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise SystemExit(f"ERROR: built binary missing: {binary}. "
                         f"Run make build-variant TREE={args.tree} BACKEND={args.backend} first.")
    model = ensure_model(Path(args.model))

    port = args.port if args.port else free_port()
    if not port_is_free(port):
        raise SystemExit(f"ERROR: port {port} is already taken. "
                         "Pass another PORT= or omit it to pick a free one. "
                         "This target does not stop the server already on that port.")

    log = Path(f"/tmp/llgenie-serve-{args.tree}-{args.backend}.log")
    cmd = serve_argv(str(binary), str(model), port)
    log_fh = log.open("w")
    proc = subprocess.Popen(
        cmd, stdout=log_fh, stderr=subprocess.STDOUT, start_new_session=True,
    )
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps({
        "pid": proc.pid, "port": port, "tree": args.tree, "backend": args.backend,
        "model": str(model), "log": str(log),
    }))
    if not _wait_healthy(port):
        raise SystemExit(f"ERROR: {args.tree}+{args.backend} did not become healthy on {port}. See {log}")
    print(f"serving {args.tree}+{args.backend} pid={proc.pid} "
          f"http://127.0.0.1:{port}/health ngl=default")
    print(f"log: {log}")
    if args.test:
        reply = chat_hi(port)
        print(f"[hi] {reply[:120]}")
        result = stop_recorded(state)
        print(f"stopped {args.tree}+{args.backend} pid={result['pid']} port={result['port']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
