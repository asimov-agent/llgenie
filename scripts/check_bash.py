#!/usr/bin/env python3
"""bash-5 parity gate for the llgenie Makefile (single source of truth).

The Makefile resolves ``SHELL`` at make-parse time to the first bash on PATH
(brew's bash on macOS, which is bash 5; /bin/bash on Linux, also bash 5). This
script is the gate the ``make bash-check`` target runs *before* any install /
CI / loop stage, so no recipe ever executes under macOS's system bash 3.2.

Behaviour:
  * Determines the effective recipe shell (``$SHELL`` in the make environment,
    falling back to ``command -v bash`` then ``/bin/bash``).
  * If it is already bash 5  -> prints OK, exits 0.
  * If it is bash 3.x on macOS and brew is available and brew bash is MISSING
    -> installs bash 5 via ``brew install bash``, then exits 3 (re-run make so
    the newly-selected SHELL takes effect). ``--force`` skips the "already bash
    5" shortcut so the check/install path is always exercised (tests).
  * Otherwise -> fails closed (exit 1) with an actionable message.

Exit codes:
  0  recipe shell is bash 5.
  3  bash 5 installed (macOS) - re-run make so the resolved SHELL updates.
  1  no bash 5 available — fail closed, no stage should run.

Used by ``make bash-check``. Tests: tests/test_macos_install.py.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys


def _run(path: str, args: list[str]) -> str:
    """Run ``path`` with ``args`` and return its stdout stripped (never raises)."""
    try:
        out = subprocess.run(
            [path, *args], capture_output=True, text=True, timeout=30
        ).stdout.strip()
    except Exception:
        return ""
    return out


def bash_version(path: str) -> str | None:
    """Return the BASH_VERSION of the bash at ``path``, or None if not bash."""
    v = _run(path, ["-c", "echo $BASH_VERSION"])
    return v or None


def version_at_least_5(version: str) -> bool:
    """True when the first integer of ``version`` is >= 5 (bash 5.x)."""
    m = re.match(r"^(\d+)\.", version)
    return bool(m) and int(m.group(1)) >= 5


def recipe_shells() -> list[str]:
    """Candidate bash paths in priority order for the effective recipe shell."""
    candidates: list[str] = []
    env_shell = os.environ.get("SHELL")
    if env_shell and os.path.basename(env_shell).startswith("bash"):
        candidates.append(env_shell)
    found = shutil.which("bash")
    if found:
        candidates.append(found)
    candidates.append("/bin/bash")
    seen: set[str] = set()
    out: list[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def brew_prefix() -> str:
    try:
        return subprocess.run(
            ["brew", "--prefix"], capture_output=True, text=True, timeout=30
        ).stdout.strip()
    except Exception:
        return ""


def brew_bash() -> str:
    """The brew-bash path (`brew --prefix`/bin/bash), installed or intended."""
    return os.path.join(brew_prefix() or "/opt/homebrew", "bin", "bash")


def resolve() -> str:
    """The recipe shell the Makefile sets SHELL to, at make-parse time (``--resolve``).

    macOS with brew: brew's bash 5, installed first (``brew install bash``) when it is
    missing, so the SAME make invocation already runs every recipe under bash 5 (a
    fresh CI runner never needs a second ``make``). Otherwise the first bash on PATH
    (Linux: /bin/bash, bash 5). Install output goes to stderr: stdout is the path."""
    if sys.platform == "darwin" and shutil.which("brew"):
        bb = brew_bash()
        if not os.path.isfile(bb):
            print("==> [bash-check] installing bash 5 via `brew install bash` so recipes run "
                  "under bash 5, not system bash 3.2", file=sys.stderr)
            subprocess.run(["brew", "install", "bash"], stdout=sys.stderr)
        if os.path.isfile(bb):
            return bb
    return shutil.which("bash") or "/bin/bash"


def real_main(argv: list[str]) -> int:
    if argv[:1] == ["--resolve"]:
        print(resolve())
        return 0
    force = "--force" in argv

    # The effective recipe shell is passed explicitly by the Makefile as argv[0]
    # (the resolved $(SHELL) variable, which GNU make runs recipes under but does
    # not export to the recipe env). Fall back to env $SHELL / `bash` on manual use.
    effective = (argv[0] if argv and not argv[0].startswith("-")
                 else os.environ.get("SHELL") or shutil.which("bash") or "/bin/bash")
    eff_ver = bash_version(effective)

    # 2. Already bash 5 and not forced: OK.
    if eff_ver and version_at_least_5(eff_ver) and not force:
        print(f"==> [bash-check] recipe shell {effective} is {eff_ver} (bash 5) OK")
        return 0

    # 3. There is a bash 5 somewhere else the Makefile should be using.
    other_bash5 = None
    for shell in recipe_shells():
        if shell == effective:
            continue
        v = bash_version(shell)
        if v and version_at_least_5(v):
            other_bash5 = shell
            break

    # 4. macOS: install brew bash 5 when it is missing (the Makefile SHELL
    #    resolution prefers brew's bash), then ask for a re-run.
    if sys.platform == "darwin" and shutil.which("brew"):
        bb = brew_bash()
        if not os.path.isfile(bb):
            print(
                "==> [bash-check] installing bash 5 via `brew install bash` so "
                "recipes run under bash 5, not system bash 3.2"
            )
            code = subprocess.run(["brew", "install", "bash"]).returncode
            if code != 0:
                print("FATAL: brew install bash failed", file=sys.stderr)
                return 1
            other_bash5 = bb
            print(
                "==> [bash-check] bash 5 installed. Re-run `make` so the "
                "resolved SHELL updates to brew's bash 5."
            )
            return 3

    # 5. A bash 5 exists but is not the effective SHELL: tell the user to point
    #    SHELL at it (or re-run after a fresh install) and fail closed.
    if other_bash5:
        print(
            f"==> [bash-check] bash 5 found at {other_bash5} but the recipe shell "
            f"is {effective} (bash {eff_ver or '?'}). Re-run `make` so SHELL "
            "resolves to bash 5.",
            file=sys.stderr,
        )
        return 3

    # 6. No bash 5 available anywhere.
    print(
        "FATAL: recipe shell must be bash 5; found none of "
        f"{', '.join(recipe_shells())}. Install bash 5 "
        "(macOS: brew install bash; Linux: /bin/bash already ships bash 5) "
        "and re-run make.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(real_main(sys.argv[1:]))
