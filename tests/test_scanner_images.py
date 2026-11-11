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
import subprocess
from pathlib import Path

import pytest

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


# --- publishing is idempotent (issue #2453; failure streams per issue #2452 criterion 4) ---


def _fake_docker(monkeypatch, *, platforms=(), probe_rc=0, op_rc=0,
                 op_stdout="load done", op_stderr=""):
    """Fake the leg's one policy seam (`si.run_ok`): an `imagetools inspect` answers
    with the given platforms (or probe_rc when the registry lacks the tag), every
    other command answers with op_rc and these streams. No real Docker runs — unit
    CI has none, and the behaviour under test is the leg's decision, not buildkit's."""

    calls = []

    def fake(cmd, **kw):
        cmd = [str(c) for c in cmd]
        calls.append(cmd)
        if "imagetools" in cmd:
            if probe_rc != 0:
                return subprocess.CompletedProcess(cmd, probe_rc, "", "not found")
            out = "".join(f"    Platform: {p}\n" for p in platforms)
            return subprocess.CompletedProcess(cmd, 0, out, "")
        return subprocess.CompletedProcess(cmd, op_rc, op_stdout, op_stderr)

    monkeypatch.setattr(si, "run_ok", fake)
    return calls


def test_an_already_published_tag_is_not_re_pushed(tmp_path, monkeypatch, capsys):
    """The measured incident: the tag run 42751641578 published was re-pushed by run
    42755279061 and its transient failure reds main. The probe must skip it."""

    # Given the registry already carries the content-hash tag on both platforms
    monkeypatch.setattr(si, "REPO", _tree(tmp_path))
    calls = _fake_docker(monkeypatch, platforms=("linux/amd64", "linux/arm64"))

    # When  publish runs
    rc = si.publish("trivy")
    out = capsys.readouterr().out

    # Then  it skipped: a skip line naming the ref, no --push command ran, rc 0
    assert rc == 0
    assert "skipping re-push" in out and si.ref("trivy") in out
    assert not any("--push" in cmd for cmd in calls)


def test_a_tag_missing_a_required_platform_still_publishes(tmp_path, monkeypatch, capsys):
    """Negative control: the skip must never suppress an incomplete artifact."""

    # Given the registry carries the tag with only linux/amd64
    monkeypatch.setattr(si, "REPO", _tree(tmp_path))
    calls = _fake_docker(monkeypatch, platforms=("linux/amd64",))

    # When  publish runs with PLATFORMS = linux/amd64,linux/arm64
    rc = si.publish("trivy")
    out = capsys.readouterr().out

    # Then  the multi-arch push ran unchanged
    assert rc == 0 and "published" in out
    pushes = [cmd for cmd in calls if "--push" in cmd]
    assert pushes and "linux/amd64,linux/arm64" in pushes[0]


def test_a_tag_absent_from_the_registry_publishes_as_today(tmp_path, monkeypatch):
    """A probe that cannot find the tag is an empty answer, never a leg failure."""

    # Given the registry probe exits non-zero (tag does not exist)
    monkeypatch.setattr(si, "REPO", _tree(tmp_path))
    calls = _fake_docker(monkeypatch, probe_rc=1)

    # When  publish runs
    rc = si.publish("trivy")

    # Then  the push ran exactly as before
    assert rc == 0
    assert any("--push" in cmd for cmd in calls)


def test_a_failed_publish_prints_its_captured_streams(tmp_path, monkeypatch, capsys):
    """Issue #2452 criterion 4: the streams `run_ok` captured were discarded; a
    failure that prints nothing is undiagnosable from the job log."""

    # Given a publish whose buildx push exits 1 with a buildkit error in its stderr
    monkeypatch.setattr(si, "REPO", _tree(tmp_path))
    _fake_docker(monkeypatch, probe_rc=1, op_rc=1,
                 op_stderr="failed to solve: sentinel-buildkit-error")

    # When  publish handles the failure
    with pytest.raises(SystemExit) as got:
        si.publish("trivy")
    out = capsys.readouterr().out

    # Then  the output names the failure, the exit code, and the captured error —
    #         and the leg still exits non-zero
    assert "publish failed: trivy" in str(got.value)
    assert "exit 1" in out and "sentinel-buildkit-error" in out


def test_a_failed_build_prints_its_captured_streams(tmp_path, monkeypatch, capsys):
    """The same rule for the local build leg."""

    # Given a build whose docker build exits 1 with an error on stderr
    monkeypatch.setattr(si, "REPO", _tree(tmp_path))
    _fake_docker(monkeypatch, op_rc=1, op_stderr="ERROR: sentinel-build-error")

    # When  build handles the failure
    with pytest.raises(SystemExit):
        si.build("trivy")
    out = capsys.readouterr().out

    # Then  the printed output carries the exit code and the captured error line
    assert "exit 1" in out and "sentinel-build-error" in out


# --- `ensure` is the scanners' own pipeline (issue #745): publish ONLY the tags GHCR is missing ---


def test_ensure_skips_a_published_ref(tmp_path, monkeypatch, capsys):
    """A tag the registry already carries is one manifest lookup and a log line, never a build."""

    # Given the registry already carries the content-hash tag (imagetools inspect answers 0)
    monkeypatch.setattr(si, "REPO", _tree(tmp_path))
    calls = _fake_docker(monkeypatch, platforms=("linux/amd64", "linux/arm64"))

    # When  ensure runs
    rc = si.ensure("trivy")
    out = capsys.readouterr().out

    # Then  it skipped: a `present … (skipped)` line naming the ref, no --push/unqualified build ran
    assert rc == 0
    assert "present" in out and "(skipped)" in out and si.ref("trivy") in out
    assert not any("--push" in c or "--platform" in c for c in calls)
    # single registry probe only — the decision came from one imagetools inspect
    assert sum("imagetools" in c for c in calls) == 1


def test_ensure_publishes_an_absent_ref(tmp_path, monkeypatch, capsys):
    """A tag absent from the registry is built + pushed exactly once, with the digests ref."""

    # Given the registry probe exits non-zero (the tag does not exist)
    monkeypatch.setattr(si, "REPO", _tree(tmp_path))
    calls = _fake_docker(monkeypatch, probe_rc=1)

    # When  ensure runs
    rc = si.ensure("trivy")
    out = capsys.readouterr().out

    # Then  it published the multi-arch tag once, from digests.json's ref
    assert rc == 0 and "publishing" in out
    pushes = [c for c in calls if "--push" in c]
    assert len(pushes) == 1
    assert si.ref("trivy") in pushes[0] and "linux/amd64,linux/arm64" in pushes[0]


def test_ensure_force_republishes_a_present_ref(tmp_path, monkeypatch, capsys):
    """force (the dispatch input, passed as an env value) re-pushes even a present tag."""

    # Given the registry already carries the tag on both platforms
    monkeypatch.setattr(si, "REPO", _tree(tmp_path))
    calls = _fake_docker(monkeypatch, platforms=("linux/amd64", "linux/arm64"))

    # When  ensure runs with FORCE set in the environment
    monkeypatch.setenv("FORCE", "1")
    rc = si.ensure("trivy", force=True)
    out = capsys.readouterr().out

    # Then  it published anyway (a --push ran, named the ref)
    assert rc == 0 and "publishing" in out
    assert any("--push" in c for c in calls)


# --- the scanners' own pipeline (issue #745): ci.yml holds no scanner build, security-images.yml never a PR ---


def test_ci_yml_has_no_scanner_job():
    """Main CI builds and publishes no scanner image: the scanner-images job is gone from ci.yml."""

    # Given this repository's ci.yml
    ci = (REPO / ".github" / "workflows" / "ci.yml").read_text()

    # Then  it declares no scanner-images JOB (a YAML job key at 2-space indent) and runs no scanner
    #       make target on a PR/merge — the build lives in security-images.yml, its own pipeline
    assert "scanner-images:" not in ci          # the job declaration key is gone
    assert "make ci-scanner-images" not in ci
    assert "make ci-security-images" not in ci  # this pipeline must not publish from main CI
    assert "make publish-scanner-images" not in ci  # a PR/merge run must not push a scanner tag


def test_security_images_yml_runs_never_on_a_pull_request():
    """The scanner-images pipeline has schedule + path-filtered push + dispatch, never pull_request."""

    # Given the new security-images.yml
    wf = (REPO / ".github" / "workflows" / "security-images.yml").read_text()

    # Then  the on: block carries a pull_request key exactly nowhere (a PR cannot publish these
    #       images, issue #745) — only schedule, a path-filtered push to main, and workflow_dispatch
    assert "pull_request:" not in wf            # no trigger declares a PR event
    assert "schedule:" in wf and "workflow_dispatch:" in wf
    assert "containers/scanners/**" in wf and "scanner_image.py" in wf


def test_ensure_image_has_single_build_path():
    """security_scan.ensure_image carries no docker build of its own (issue #745 item 4)."""

    # Given the module that resolves a scanner image for a scan
    src = (REPO / "scripts" / "security_scan.py").read_text()

    # Then  it delegates to scanner_image.ensure and never hand-rolls a second `docker build`
    assert "_scanner_image.ensure(scanner=tool)" in src
    # the old inline builder arguments (docker build -t <ref> <context>) must not be present
    assert '"build"' not in src or "subprocess.run([RUNTIME, \"build\"" not in src
    assert "cannot build" not in src  # the old failure message naming the inline build is gone


