#!/usr/bin/env python3
"""Python 3.11 parity gate for the gguf venv (issue #120, single source of truth).

Every stage runs its Python scripts on Python 3.11: inside the ``llgenie/test``
image (``python:3.11-slim``) on Linux and for the shared CI steps, and in the
gguf venv (``~/llama-gguf-tools/.venv``) that ``make install`` builds on the host
(the native-Metal engines on macOS run from it). This script finds the 3.11
interpreter the venv is created with.

  python3 scripts/check_python.py            # print the python3.11 path, exit 0
  python3 scripts/check_python.py --venv V   # exit 0 when V/bin/python is 3.11, else 1

Resolution: the running interpreter when it is 3.11, else ``python3.11`` on PATH.
On macOS with brew and no python3.11, it runs ``brew install python@3.11`` first.
No 3.11 anywhere -> exit 1 with an actionable message (fails closed).

Used by ``make -C tools create-venv``. Tests: tests/test_macos_install.py.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

WANT = (3, 11)


def running_is_want() -> bool:
    """True when the current interpreter is already 3.11 (a seam the tests can
    override — the real check reads the live sys.version_info)."""
    return tuple(sys.version_info[:2]) == WANT


def version_of(python: str) -> tuple[int, int] | None:
    """(major, minor) of the interpreter at ``python``, or None when it does not run."""
    try:
        out = subprocess.run([python, "-c", "import sys; print(*sys.version_info[:2])"],
                             capture_output=True, text=True, timeout=30).stdout.split()
        return (int(out[0]), int(out[1])) if len(out) == 2 else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def brew_python() -> str:
    try:
        prefix = subprocess.run(["brew", "--prefix", "python@3.11"], capture_output=True,
                                text=True, timeout=60).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""
    return os.path.join(prefix, "bin", "python3.11") if prefix else ""


def uv_python_root() -> str:
    """The directory uv manages CPython installs under (env override, else the
    default ~/.local/share/uv/python)."""
    return os.environ.get("UV_PYTHON_INSTALL_DIR") or os.path.join(
        os.environ.get("HOME") or str(Path.home()), ".local", "share", "uv", "python")


def uv_python311() -> str:
    """A python3.11 uv already manages, even when it is not on PATH (uv installs into
    its own dir). Globs the managed CPython dirs for a 3.11 interpreter."""
    import glob
    root = uv_python_root()
    # uv's managed dirs are cpython-3.11.<patch>-<platform>-<arch> (a dot, not a hyphen)
    hits = glob.glob(os.path.join(root, "cpython-3.11*", "bin", "python3.11"))
    return hits[0] if hits else ""


def find_python311() -> str | None:
    if running_is_want():
        return sys.executable
    for cand in (shutil.which("python3.11"), uv_python311(), brew_python()):
        if cand and os.path.isfile(cand) and version_of(cand) == WANT:
            return cand
    return None


def uv_install_python311() -> bool:
    """Install Python 3.11 with uv into its managed dir (default `make -C tools
    create-venv` behaviour on a host that has uv but no 3.11 — the Linux analogue of
    the macOS brew path). Returns True on success."""
    print("==> [python-check] installing Python 3.11 via `uv python install 3.11`",
          file=sys.stderr)
    return subprocess.run(["uv", "python", "install", "3.11"]).returncode == 0


def resolve() -> str | None:
    """The python3.11 path. When missing, auto-provisions: macOS via brew (as
    before), any host with `uv` on PATH via `uv python install 3.11`. A host with
    neither still fails closed with an actionable message."""
    found = find_python311()
    if found:
        return found
    if sys.platform == "darwin" and shutil.which("brew"):
        print("==> [python-check] installing Python 3.11 via `brew install python@3.11`",
              file=sys.stderr)
        if subprocess.run(["brew", "install", "python@3.11"]).returncode == 0:
            return find_python311()
        print("FATAL: brew install python@3.11 failed", file=sys.stderr)
        return None
    if shutil.which("uv") and uv_install_python311():
        return find_python311()
    return None


def real_main(argv: list[str]) -> int:
    if argv[:1] == ["--venv"]:
        if len(argv) < 2:
            print("usage: check_python.py --venv <dir>", file=sys.stderr)
            return 2
        return 0 if version_of(os.path.join(argv[1], "bin", "python")) == WANT else 1
    found = resolve()
    if not found:
        print("FATAL: Python 3.11 is required (macOS: brew install python@3.11; "
              "Linux: `uv python install 3.11` — or install python3.11) and none was found.",
              file=sys.stderr)
        return 1
    print(found)
    return 0


if __name__ == "__main__":
    sys.exit(real_main(sys.argv[1:]))
