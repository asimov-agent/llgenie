"""The engine base Dockerfile renderer upgrades packages inherited from the base
image, and the generated files stay in sync with the renderer (issue #2839)."""

import sys
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import engine_skills as es  # noqa: E402

BACKENDS = ["cpu", "cuda", "rocm", "vulkan"]


def test_render_emits_upgrade_for_all_backends():
    """The base renderer emits `apt-get upgrade -y` between `apt-get update`
    and the toolchain install for every backend."""

    for backend in BACKENDS:
        # When  the base Dockerfile is rendered for this backend
        rendered = es.render_base_dockerfile(backend)
        # Then  its apt RUN layer upgrades inherited debs before installing.
        assert "apt-get update && apt-get upgrade -y" in rendered, (
            f"{backend} base does not upgrade inherited debs"
        )


def test_generated_files_in_sync():
    """All four generated base Dockerfiles carry the upgrade layer and the
    engine Dockerfile FROM lines pin the matching new base tag."""

    # Given the generated base Dockerfile for each backend must match the renderer.
    for backend in BACKENDS:
        generated = (
            REPO_ROOT / "containers" / "engines" / "base" / f"Dockerfile.{backend}"
        ).read_text()
        # When  rendered from the current source
        expected = es.render_base_dockerfile(backend)
        # Then  the on-disk file is byte-identical to the renderer output.
        assert generated == expected, (
            f"containers/engines/base/Dockerfile.{backend} is stale"
        )
        assert "apt-get update && apt-get upgrade -y" in generated

    # And each engine Dockerfile that builds from the shared base pins the new tag.
    for dockerfile in sorted(
        (REPO_ROOT / "containers" / "engines" / "dockerfiles").glob("**/Dockerfile.*")
    ):
        for ln in dockerfile.read_text().splitlines():
            if not ln.startswith("FROM llgenie/base-"):
                continue
            name = ln[len("FROM "):].split(":")[0]
            backend = name.rsplit("-", 1)[-1]
            expected_tag = es.base_tag(backend)
            assert f"FROM {expected_tag}" in ln, (
                f"{dockerfile} not pinned to the current {backend} base tag "
                f"(expected {expected_tag})"
            )


def test_check_engine_params_green():
    """The generated-file guard `make check-engine-params` is green."""

    # When  the on-disk generated files are checked against the renderer
    proc = subprocess.run(
        ["make", "check-engine-params"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    # Then  nothing is stale.
    assert proc.returncode == 0, proc.stderr + proc.stdout
