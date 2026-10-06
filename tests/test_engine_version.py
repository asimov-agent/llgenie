"""Engine image binary version check (host-side; docker is required).

Run after `make install` / `make build-engine` for every built engine image,
skipping the Metal/Apple-Silicon-only variant. Requires docker: it launches the
image and asserts the entrypoint `version` (alias of detect) reports text. This
is the "at least --version works" guarantee for engines that cannot serve on the
current host (e.g. GPU images on a GPU-less runner).

    LLGENIE_TEST_ENGINE=llama.cpp LLGENIE_TEST_ARCH=cpu \
        python3 -m pytest tests/test_engine_version.py -q
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import engine_image as ei  # noqa: E402


def test_engine_binary_reports_a_version():
    engine = os.environ.get("LLGENIE_TEST_ENGINE", "")
    arch = os.environ.get("LLGENIE_TEST_ARCH", "")
    if not (engine and arch):
        pytest.fail("LLGENIE_TEST_ENGINE/LLGENIE_TEST_ARCH are not set: run through "
                    "`make test-engine-image ENGINE=<id> ARCH=<arch>`")

    spec = ei.resolve(engine, None, arch)
    r = subprocess.run([ei.RUNTIME, "run", "--rm", spec["tag"], "version"],
                       capture_output=True, text=True, timeout=300)
    out = (r.stdout + r.stderr).strip()
    assert r.returncode == 0, f"{engine}/{arch} `version` exited {r.returncode}: {out}"
    assert out, f"{engine}/{arch} `version` printed nothing"
    print(f"[version] {engine}/{arch}: {out.splitlines()[-1]}")



if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
