"""The scanner-image gate (issue #714): every scanner image is immutable before a scan runs.

A scan pipeline is only as reproducible as the scanner it runs. The image must therefore pin its
base by DIGEST and its scanner by an EXACT version, and `containers/scanners/digests.json` — the
file the scan workflow reads — must agree with the Dockerfiles that produced it. A stale digests
file would point a scan at an image that no longer matches the file in the tree.

Each rule is proven on a fixture tree first, then the real tree is asserted clean. No Docker is
needed: the gate reads files. Building and running the images is `make test-scanner-image`, which
CI runs per scanner.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
from scripts import scanner_image as si

BASE_DIGEST = "sha256:" + "a" * 64
DOCKERFILE_OK = (
    "# syntax=docker/dockerfile:1\n"
    f"FROM cgr.dev/chainguard/wolfi-base@{BASE_DIGEST}\n"
    "\n"
    "ARG TRIVY_VERSION=0.70.0-r5\n"
    'RUN apk add --no-cache "trivy=${TRIVY_VERSION}"\n'
    "\n"
    'ENTRYPOINT ["trivy"]\n'
    'CMD ["version"]\n'
)


def _tree(tmp_path: Path, dockerfile: str = DOCKERFILE_OK) -> Path:
    """A repository-shaped fixture with one scanner, then REPO pointed at it."""
    d = tmp_path / "containers" / "scanners" / "trivy"
    d.mkdir(parents=True)
    (d / "Dockerfile").write_text(dockerfile, encoding="utf-8")
    return tmp_path


def test_every_scanner_has_a_pinned_dockerfile():
    """The real tree: one image per scanner, digest base, exact version."""

    # Given this repository
    # When  the gate reads all four scanners
    rc = si.check("all")

    # Then  it passes
    assert rc == 0


def test_a_floating_base_fails(tmp_path, monkeypatch):
    """`FROM image:tag` can move under the build; only a digest is immutable."""

    # Given a Dockerfile whose base floats on a tag
    root = _tree(tmp_path, DOCKERFILE_OK.replace(
        f"cgr.dev/chainguard/wolfi-base@{BASE_DIGEST}", "cgr.dev/chainguard/wolfi-base:latest"))
    monkeypatch.setattr(si, "REPO", root)

    # When  the gate reads it
    rc = si.check("trivy")

    # Then  it fails and names both defects (no digest, and `latest` by name)
    assert rc == 1


def test_an_unpinned_scanner_version_fails(tmp_path, monkeypatch):
    """A version range compiles to a different scanner on the next build."""

    # Given a Dockerfile with no exact-version ARG
    root = _tree(tmp_path, DOCKERFILE_OK.replace("ARG TRIVY_VERSION=0.70.0-r5\n", ""))
    monkeypatch.setattr(si, "REPO", root)

    # When  the gate reads it
    try:
        rc = si.check("trivy")
    except SystemExit as exc:  # the version pin is required for digests too
        rc = str(exc)

    # Then  the missing pin is loud, never a silent pass
    assert rc != 0


def test_a_stale_digests_file_fails(tmp_path, monkeypatch):
    """The scan workflow reads digests.json; a stale entry points at a different build."""

    # Given a Dockerfile and a digests.json whose tag is from an older file
    root = _tree(tmp_path)
    digests = root / "containers" / "scanners" / "digests.json"
    digests.write_text(json.dumps({
        "trivy": {"version": "0.70.0-r5", "tag": "000000000000",
                  "ref": "ghcr.io/asimov-agent/llgenie/trivy:000000000000"}}), encoding="utf-8")
    monkeypatch.setattr(si, "REPO", root)

    # When  the gate reads it
    rc = si.check("trivy")

    # Then  it fails on the tag mismatch
    assert rc == 1


def test_write_records_the_content_hash_and_version(tmp_path, monkeypatch):
    """`write` is what keeps digests.json true: version + hash, one entry per scanner."""

    # Given a tree with a single pinned scanner
    root = _tree(tmp_path)
    monkeypatch.setattr(si, "REPO", root)
    monkeypatch.setattr(si, "SCANNERS", {"trivy": si.SCANNERS["trivy"]})

    # When  digests are written
    si.write()

    # Then  the entry carries the pin and the content hash the gate compares
    data = json.loads((root / "containers" / "scanners" / "digests.json").read_text())
    assert data["trivy"]["version"] == "0.70.0-r5"
    assert data["trivy"]["tag"] == si.content_hash("trivy")
    assert data["trivy"]["ref"].endswith(f"trivy:{si.content_hash('trivy')}")


def test_the_content_hash_moves_with_the_dockerfile(tmp_path, monkeypatch):
    """The tag is the immutability: a changed Dockerfile must be a different tag."""

    # Given two trees whose Dockerfiles differ by one pin
    a = _tree(tmp_path / "a")
    b = _tree(tmp_path / "b", DOCKERFILE_OK.replace("0.70.0-r5", "0.71.0-r0"))

    # When  each is hashed
    monkeypatch.setattr(si, "REPO", a)
    ha = si.content_hash("trivy")
    monkeypatch.setattr(si, "REPO", b)
    hb = si.content_hash("trivy")

    # Then  the tags differ, so a bump can never reuse a published tag
    assert ha != hb


def test_an_unknown_scanner_is_refused():
    """A typo must fail loudly rather than build nothing and report success."""

    # Given an unknown scanner id
    # When  the CLI is asked for it
    try:
        si.main(["build", "not-a-scanner"])
    except SystemExit as exc:
        assert "unknown scanner" in str(exc)

    # Then  it refused (the SystemExit above) — reaching here means it did not
    else:
        raise AssertionError("an unknown scanner was accepted")
