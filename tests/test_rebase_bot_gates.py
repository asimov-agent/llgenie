#!/usr/bin/env python3
"""The rebase bot's structural gate mounts the checkout, not the repo slug.

A bot job exports `REPO=asimov-agent/llgenie` so the sweep and the push know which repository they
are talking to. Make treats an environment variable as an override of `REPO := $(shell pwd)`, so a
gate that mounts `$(REPO)` hands docker the slug. Docker refuses it (`includes invalid characters
for a local volume name`, run 39727049030) and the rebase is aborted after the conflict was already
resolved. The mount must be a path whatever `REPO` is set to.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_the_lint_gate_mounts_the_checkout_when_repo_is_the_slug():
    """A slug in the environment must not become the volume source."""

    # Given the Makefile and REPO set to the slug the bot job exports
    # When  the lint recipe is expanded
    out = subprocess.run(
        ["make", "-n", "lint", "REPO=asimov-agent/llgenie"],
        cwd=REPO, capture_output=True, text=True, check=True).stdout

    # Then  the volume source is this checkout, and the slug is not a mount
    assert f'-v "{REPO}":/repo:rw' in out, out
    assert '-v "asimov-agent/llgenie"' not in out, out


def test_the_sweep_still_receives_the_slug():
    """The path fix must not steal the slug from the target that needs it."""

    # Given the same slug
    # When  the sweep recipe is expanded
    out = subprocess.run(
        ["make", "-n", "rebase-bot-sweep", "REPO=asimov-agent/llgenie"],
        cwd=REPO, capture_output=True, text=True, check=True).stdout

    # Then  the sweep is told the slug, not the path
    assert "--repo asimov-agent/llgenie" in out, out
