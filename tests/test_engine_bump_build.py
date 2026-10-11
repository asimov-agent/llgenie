"""Real llama.cpp cpu image build. Not in make test-unit: that runner has no
docker socket, so this fails closed there. Run it where the runtime answers
(make test-engine ENGINE=llama.cpp ARCH=cpu is the CI path).
"""
from __future__ import annotations

import shutil
import subprocess

import pytest

import scripts.engine_image as ei


def test_real_docker_build_llama_cpp_cpu():
    """Real happy path: `make build-engine ENGINE=llama.cpp ARCH=cpu` builds the
    image from the generated Dockerfile + params (docker required). The image
    must build and its entrypoint must report a version."""

    # Given docker answers and the generated llama.cpp cpu spec
    if not shutil.which("docker"):
        pytest.fail("docker is required for the real build test")
    spec = ei.resolve("llama.cpp", None, "cpu")

    # When the image is built (force, so a stale tag still rebuilds)
    rc = ei.build(spec, force=True)

    # Then it builds and its entrypoint reports a version
    assert rc == 0, f"make build-engine llama.cpp cpu failed (exit {rc})"
    r = subprocess.run([ei.RUNTIME, "run", "--rm", spec["tag"], "version"],
                       capture_output=True, text=True, timeout=300)
    out = (r.stdout + r.stderr).strip()
    assert r.returncode == 0, f"llama.cpp cpu `version` exited {r.returncode}: {out}"
    assert out, "llama.cpp cpu `version` printed nothing"
    print(f"[build] llama.cpp cpu built and answered: {out.splitlines()[-1]}")
