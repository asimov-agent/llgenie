from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts import engine_capability as ec  # noqa: E402  (conftest is the one root — issue #1101)

REPO = Path(__file__).resolve().parents[1]

def _serve(engine: str, arch: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(REPO / "scripts/engine_capability.py"),
                           "serve", engine, arch], capture_output=True, text=True)


def test_mlx_cpu_can_serve():
    """mlx declares cpu in its capability archs (issue #1214) — it MUST remain a serve test, not be de-scoped."""
    assert ec.can_serve("mlx", "cpu") is True
    assert _serve("mlx", "cpu").returncode == 0


def test_tensorrt_in_a_cycle_no_cpu():
    """A GPU-only engine's non-declared arch is binary-flags-only: never a serve assertion."""
    assert ec.can_serve("tensorrt-llm", "cpu") is False
    assert _serve("tensorrt-llm", "cpu").returncode == 1


def test_webllm_declares_zero_archs():
    """webllm.archs == [] (browser-only, no linux image) -> no arch may serve it."""
    assert ec.declared_archs("webllm") == set()
    assert ec.can_serve("webllm", "cpu") is False
    for a in ("cpu", "cuda", "rocm", "vulkan", "metal"):
        assert ec.can_serve("webllm", a) is False


def test_all_ci_cells_are_capability_consistent():
    """Every engine-build CI cell's arch is declared by its engine's capability row.

    Invariance guard (subset, not equality): a future params row must never be built-and-verified in a
    way that serves on an arch the engine does not declare.
    """
    import json
    import subprocess

    rows = json.loads(subprocess.run(
        [sys.executable, str(REPO / "scripts/engine_image.py"), "matrix", "--json", "--ci"],
        capture_output=True, text=True, cwd=REPO, check=True).stdout)["include"]
    for r in rows:
        if r["engine"] == "none":
            continue
        assert ec.can_serve(r["engine"], r["variant"]), (
            f"{r['engine']}/{r['variant']} is a CI cell whose arch is NOT in its capability archs")


def test_unknown_engine_defaults_to_flags_only():
    """An engine with no capability row defaults to False (flags-only) — the safe 'never over-serve' choice."""
    assert ec.can_serve("engine-that-does-not-exist", "cpu") is False
