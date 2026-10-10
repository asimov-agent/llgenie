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

WANT = (3, 11)


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


def find_python311() -> str | None:
    if tuple(sys.version_info[:2]) == WANT:
        return sys.executable
    for cand in (shutil.which("python3.11"), brew_python()):
        if cand and os.path.isfile(cand) and version_of(cand) == WANT:
            return cand
    return None


def resolve() -> str | None:
    """The python3.11 path; on macOS installs python@3.11 via brew when missing."""
    found = find_python311()
    if found:
        return found
    if sys.platform == "darwin" and shutil.which("brew"):
        print("==> [python-check] installing Python 3.11 via `brew install python@3.11`",
              file=sys.stderr)
        if subprocess.run(["brew", "install", "python@3.11"]).returncode != 0:
            print("FATAL: brew install python@3.11 failed", file=sys.stderr)
            return None
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
              "Linux: install python3.11) and none was found.", file=sys.stderr)
        return 1
    print(found)
    return 0


if __name__ == "__main__":
    sys.exit(real_main(sys.argv[1:]))
