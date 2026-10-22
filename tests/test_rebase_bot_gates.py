#!/usr/bin/env python3
"""The rebase bot's structural gate mounts the checkout, not the repo slug.

A bot job exports `REPO=asimov-agent/llgenie` so the sweep and the push know which repository they
are talking to. Make treats an environment variable as an override of `REPO := $(shell pwd)`, so a
gate that mounts `$(REPO)` hands docker the slug. Docker refuses it (`includes invalid characters
for a local volume name`, run 39727049030) and the rebase is aborted after the conflict was already
resolved. The mount must be a path whatever `REPO` is set to.

The mount only exists on a host that runs the gate in a container: Linux expands `TEST_RUN` to
`llgenie/test`, while macOS runs the SAME command natively in the 3.11 venv (the `HOST_OS` branch in
the `Makefile`), so its lint recipe carries no volume at all. The invariant is therefore asserted
where both hosts resolve it — `TEST_OPTS` — and the recipe is asserted against the shape its own
host expands. Run 39728790390 failed because the container shape was asserted on macOS.
"""
from __future__ import annotations

import platform
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SLUG = "asimov-agent/llgenie"
TEST_IMAGE = "llgenie/test:latest"
# The same host branch the Makefile takes: Linux runs the gate in llgenie/test, macOS in the venv.
CONTAINER_HOST = platform.system() != "Darwin"


def _make(*args: str) -> str:
    return subprocess.run(
        ["make", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout


def _expanded(target: str) -> str:
    """The recipe make would run for `target` with REPO set to the slug."""
    return _make("-n", target, f"REPO={SLUG}")


def _variable(name: str) -> str:
    """The value make resolved for `name` — the mount every recipe above expands to."""
    for line in _make("-p", "-n", "lint", f"REPO={SLUG}").splitlines():
        if line.startswith(f"{name} ") and "=" in line:
            return line.split("=", 1)[1].strip()
    raise AssertionError(f"make -p did not report {name}")


def test_the_lint_gate_mounts_the_checkout_when_repo_is_the_slug():
    """A slug in the environment must not become the volume source."""

    # Given the Makefile and REPO set to the slug the bot job exports

    # When  the mount and the lint recipe are expanded
    opts = _variable("TEST_OPTS")
    recipe = _expanded("lint")

    # Then  the volume source is this checkout, and the slug is not a mount
    assert f'-v "{REPO}":/repo:rw' in opts, opts
    assert f'-v "{SLUG}"' not in opts, opts
    assert f'-v "{SLUG}"' not in recipe, recipe

    # And   the recipe carries the shape this host actually runs
    if CONTAINER_HOST:
        assert f'-v "{REPO}":/repo:rw' in recipe, recipe
        assert TEST_IMAGE in recipe, "the image name must survive the mount change"
    else:
        assert "-v " not in recipe, recipe
        assert TEST_IMAGE not in recipe, recipe
        assert "scripts/lint_linefeeds.py" in recipe, recipe


def test_the_sweep_still_receives_the_slug():
    """The path fix must not steal the slug from the target that needs it."""

    # Given the same slug

    # When  the sweep recipe is expanded
    out = _expanded("rebase-bot-sweep")

    # Then  the sweep is told the slug, not the path
    assert f"--repo {SLUG}" in out, out
