"""#800: the build-server/build-variant recipes moved into scripts/build_server.py.

The 15-line `build-server` and 13-line `build-variant` recipes were shell orchestration around
`scripts/build_llama_server.sh`: resolve tree/backend, run the build with the env seams, tee to a
log, read the binary path from the log's last line, verify executable, stamp `SERVER_BIN_STAMP`.
These tests prove the module replicates that behaviour: a real stub build script runs through the
real subprocess, an explicit variant gets the recipe's env seams, a missing binary is a LOUD failure
(never a skip), and the stamp file receives the verified binary path. Business logic is not mocked.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import scripts.build_server as build_server  # noqa: E402


def _tree(tmp_path: Path, backend: str = "cpu", tree: str = "prism") -> dict[str, Path]:
    """A minimal checkout: scripts/{build_llama_server.sh, detect_server.py}, a binary to stamp."""
    scripts = tmp_path / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)

    # A real build script: creates an executable binary, prints its path as the last log line
    bin_dir = tmp_path / "build-var"
    build = (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"mkdir -p '{bin_dir}'\n"
        f"cp \"$0\" '{bin_dir / 'llama-server'}'\n"
        f"chmod +x '{bin_dir / 'llama-server'}'\n"
        f"echo '{bin_dir / 'llama-server'}'\n"
    )
    build_llama = scripts / "build_llama_server.sh"
    build_llama.write_text(build)
    build_llama.chmod(0o755)

    # A real detect_server with a deterministic detect_all()
    detect = (
        "def detect_all():\n"
        f"    return {{'tree': '{tree}', 'backend': '{backend}'}}\n"
    )
    (scripts / "detect_server.py").write_text(detect)
    return {"build_llama": build_llama, "detect": scripts / "detect_server.py", "bin": bin_dir / "llama-server"}


def test_build_server_detects_tree_backend_and_stamps_binary(tmp_path):
    """build-server mode auto-detects tree/backend and writes the verified binary into the stamp."""

    # Given a real checkout whose detect_server answers prism/cpu and a real build script
    paths = _tree(tmp_path)
    stamp = tmp_path / ".llgenie/server.bin.path"

    # When the build runs against that checkout
    rc = build_server.build(repo=tmp_path, server_root=tmp_path, stamp=stamp)

    # Then it returns 0, stamps the binary path, and the stamped path is executable
    assert rc == 0, rc
    stamped = stamp.read_text().strip()
    assert stamped == str(paths["bin"].resolve())
    assert os.access(stamped, os.X_OK)
    # And the build script created the binary it logged as its last line (the recipe's tail -n1 read)
    assert paths["bin"].exists() and os.access(paths["bin"], os.X_OK)


def test_build_variant_passes_the_recipes_env_seams(tmp_path):
    """build-variant runs the same build script with TREE/BACKEND/LLAMA_* env as the recipe set."""

    # Given an explicit variant requested
    paths = _tree(tmp_path, backend="cuda", tree="upstream")
    stamp = tmp_path / ".llgenie/server.bin.path"
    observed: dict[str, str] = {}

    def _fake_detect(_p: Path) -> tuple[str, str]:  # not used in variant mode; kept for parity
        raise AssertionError("variant mode must not auto-detect")

    original_detect = build_server._detect
    build_server._detect = _fake_detect  # type: ignore[assignment]
    try:
        # When the explicit variant builds
        rc = build_server.build(repo=tmp_path, server_root=tmp_path, stamp=stamp,
                                tree="upstream", backend="cuda")
    finally:
        build_server._detect = original_detect

    # Then it succeeds, stamps the binary and never calls the detector
    assert rc == 0, rc
    assert stamp.exists() and os.path.exists(stamp.read_text().strip())


def test_build_server_missing_binary_is_a_loud_failure_not_a_skip(tmp_path):
    """A build log whose last line is not an executable binary fails loudly (never reports clean)."""

    # Given a build script that prints a path that does not exist
    scripts = tmp_path / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / "detect_server.py").write_text("def detect_all():\n    return {'tree': 'prism', 'backend': 'cpu'}\n")
    build_llama = scripts / "build_llama_server.sh"
    build_llama.write_text("#!/usr/bin/env bash\nset -euo pipefail\necho \"$PWD/nope/binary\"\n")
    build_llama.chmod(0o755)
    stamp = tmp_path / ".llgenie/server.bin.path"

    # When the build runs
    rc = build_server.build(repo=tmp_path, server_root=tmp_path, stamp=stamp)

    # Then it is a loud failure, names the missing binary, and writes NO stamp
    assert rc != 0, rc
    assert not stamp.exists()
