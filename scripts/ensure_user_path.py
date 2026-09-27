#!/usr/bin/env python3
"""Add ~/bin to the default shell's rc file when it is not already there.

The default shell is $SHELL, which login uses. bash -> ~/.bashrc, zsh -> ~/.zshrc.
The export is inserted at the top so it runs before any interactive-only return.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PATH_LINE = 'export PATH="$HOME/bin:$PATH"'


def default_shell() -> str:
    shell = (os.environ.get("SHELL") or "").strip()
    if shell:
        return shell
    import pwd
    return pwd.getpwuid(os.getuid()).pw_shell


def rc_file_for_shell(shell: str, home: Path) -> Path:
    name = Path(shell).name
    if "zsh" in name:
        return home / ".zshrc"
    return home / ".bashrc"


def already_has_home_bin(text: str) -> bool:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "PATH" in stripped and ("$HOME/bin" in stripped or "~/bin" in stripped):
            return True
    return False


def ensure_bin_on_path(home: Path, shell: str) -> str:
    """Insert PATH_LINE into the rc file. Returns 'already' or 'added'."""
    rc = rc_file_for_shell(shell, home)
    text = rc.read_text() if rc.is_file() else ""
    if already_has_home_bin(text):
        return "already"
    body = PATH_LINE + "\n" + text
    if body and not body.endswith("\n"):
        body += "\n"
    rc.parent.mkdir(parents=True, exist_ok=True)
    rc.write_text(body)
    return "added"


def main() -> int:
    home = Path.home()
    shell = default_shell()
    rc = rc_file_for_shell(shell, home)
    result = ensure_bin_on_path(home, shell)
    if result == "already":
        print(f"==> {rc} already puts $HOME/bin on PATH")
    else:
        print(f"==> added $HOME/bin to PATH in {rc} ({Path(shell).name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
