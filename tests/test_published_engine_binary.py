"""Real (no-mock) published-engine binary test (issue #204).

The push gate refuses to publish an image whose engine binary file is not
inside it / does not answer the version or help flag the engine documents.
This test runs that SAME check against the ALREADY-PUBLISHED image: it pulls
the engine's latest tag for this arch from GHCR (never any locally built tag;
`pull_published` also asserts the digest equals the moving `:<variant>` alias)
and then exercises the engine binary file inside the real image against the
flags the engine documents.

No mocks - this needs both a container runtime and registry access, so it runs
in the `engine-published-test` CI matrix (one job per engine x arch, on push)
and via

    make test-published-engine ENGINE=<id> ARCH=<variant>
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


def test_latest_published_image_binary_file_answers_its_documented_flags():
    engine = os.environ.get("LLGENIE_TEST_ENGINE", "")
    arch = os.environ.get("LLGENIE_TEST_ARCH", "")
    if not (engine and arch):
        pytest.fail("LLGENIE_TEST_ENGINE/LLGENIE_TEST_ARCH are not set: run through "
                    "`make test-published-engine ENGINE=<id> ARCH=<arch>`")

    spec = ei.resolve(engine, None, arch)
    # A variant CI does not publish (DISABLED, or not on the CI matrix) is skipped,
    # not failed - there is no published image to be its binary's truth.
    if (engine, arch) in ei.DISABLED:
        print(f"[published-binary] {engine}/{arch} is DISABLED on CI; nothing published to check")
        return

    if not ei.REGISTRY:
        pytest.fail("LLGENIE_REGISTRY not set: no registry to pull the published image from")

    # `make test-published-engine` calls `pull_published` (a REAL pull of the latest
    # published image, digest-checked against the moving :<arch> alias) just before
    # this test, so the enforced image is already the latest on this host. Honouring
    # that flag avoids pulling multi-GB images twice in the CI matrix. When it is not
    # set, the test pulls the latest published image itself.
    if not os.environ.get("LLGENIE_PUBLISHED_PULLED"):
        pulled = ei.pull_published(spec)
        assert pulled, f"{engine}/{arch}: could not pull the latest published image from {ei.REGISTRY}"

    # The same gate the push path enforces, against the actual published image.
    rc = ei.binary_file_works(spec)
    assert rc == 0, (
        f"{engine}/{arch}: the published image's engine binary did not answer its "
        f"documented flags (probe rc {rc})"
    )
    print(f"[published-binary] {engine}/{arch}: binary in the latest published image answers its flags")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
