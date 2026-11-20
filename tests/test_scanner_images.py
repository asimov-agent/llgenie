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

import http.server
import json
import datetime as _dt
import os
import subprocess
import sys
import threading
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


def test_write_carries_the_image_digest_forward(tmp_path, monkeypatch):
    """`write` rebuilds the record from the Dockerfiles; it must not drop the pin `pin` recorded
    (issue #2609). Same Dockerfile → same tag → the digest of the image that tag serves survives."""

    # Given a written record whose tag has had its published digest pinned
    root = _tree(tmp_path)
    monkeypatch.setattr(si, "REPO", root)
    monkeypatch.setattr(si, "SCANNERS", {"trivy": si.SCANNERS["trivy"]})
    digest_path = root / "containers" / "scanners" / "digests.json"
    si.write()
    data = json.loads(digest_path.read_text())
    data["trivy"]["image_digest"] = "sha256:" + "ab" * 32
    digest_path.write_text(json.dumps(data), encoding="utf-8")

    # When  digests are re-written over the same Dockerfile (the tag has not moved)
    si.write()

    # Then  the entry carries its tag and keeps its image digest
    data = json.loads(digest_path.read_text())
    assert data["trivy"]["tag"] == si.content_hash("trivy")
    assert data["trivy"]["image_digest"] == "sha256:" + "ab" * 32


def test_a_moved_tag_drops_the_old_image_digest(tmp_path, monkeypatch):
    """The carry-forward is identity-checked: a changed Dockerfile is a new tag, and the old
    tag's digest must not be inherited by it (issue #2609)."""

    # Given a pinned record written for one Dockerfile
    root = _tree(tmp_path)
    monkeypatch.setattr(si, "REPO", root)
    monkeypatch.setattr(si, "SCANNERS", {"trivy": si.SCANNERS["trivy"]})
    digest_path = root / "containers" / "scanners" / "digests.json"
    si.write()
    data = json.loads(digest_path.read_text())
    data["trivy"]["image_digest"] = "sha256:" + "ab" * 32
    digest_path.write_text(json.dumps(data), encoding="utf-8")

    # When  the Dockerfile is bumped (a different tag) and digests are re-written
    (root / "containers" / "scanners" / "trivy" / "Dockerfile").write_text(
        DOCKERFILE_OK.replace("0.70.0-r5", "0.71.0-r0"), encoding="utf-8")
    si.write()

    # Then  the new tag's entry carries no digest until it is pinned
    data = json.loads(digest_path.read_text())
    assert data["trivy"]["tag"] == si.content_hash("trivy")
    assert "image_digest" not in data["trivy"]


def _semgrep_tree(tmp_path: Path) -> Path:
    """A repository-shaped fixture carrying the semgrep scanner AND its rules pack (issue #2713)."""
    root = _tree(tmp_path)
    d = root / "containers" / "scanners" / "semgrep"
    (d / "rules").mkdir(parents=True)
    (d / "Dockerfile").write_text(
        "# syntax=docker/dockerfile:1\n"
        f"FROM cgr.dev/chainguard/wolfi-base@{BASE_DIGEST}\n\n"
        "ARG SEMGREP_VERSION=1.165.0-r0\n"
        'RUN apk add --no-cache "semgrep=${SEMGREP_VERSION}"\n\n'
        'ENTRYPOINT ["semgrep"]\n'
        'CMD ["--version"]\n',
        encoding="utf-8")
    (d / "rules" / "default.yml").write_text("- id: rule-one\n", encoding="utf-8")
    return root


def test_rewriting_an_unchanged_rules_pack_keeps_the_capture_date(tmp_path, monkeypatch):
    """`rules_captured_at` tracks the PACK, not the write (issue #2713): a `make scanner-digests`
    run that changes no rule keeps the committed capture date — a silent advance would make a
    stale pack look freshly captured to the recency-floor gate (issue #1284)."""

    # Given a written record whose rules pack was captured on an earlier date
    root = _semgrep_tree(tmp_path)
    monkeypatch.setattr(si, "REPO", root)
    monkeypatch.setattr(si, "SCANNERS", {"semgrep": si.SCANNERS["semgrep"]})
    digest_path = root / "containers" / "scanners" / "digests.json"
    si.write()
    data = json.loads(digest_path.read_text())
    assert data["semgrep"]["rules_captured_at"] == _dt.date.today().isoformat()  # first capture stamps today
    data["semgrep"]["rules_captured_at"] = "2026-11-08"
    digest_path.write_text(json.dumps(data), encoding="utf-8")

    # When  digests are re-written over the SAME rules pack (rules_sha unchanged)
    si.write()

    # Then  the capture date survives and the pack identity is unchanged
    data = json.loads(digest_path.read_text())
    assert data["semgrep"]["rules_captured_at"] == "2026-11-08"
    assert data["semgrep"]["rules_sha"] == si.hashlib.sha256(
        (root / "containers" / "scanners" / "semgrep" / "rules" / "default.yml").read_bytes()
    ).hexdigest()


def test_a_changed_rules_pack_advances_the_capture_date(tmp_path, monkeypatch):
    """The keep is identity-checked on `rules_sha`: a pack that actually moved is a new capture
    and MUST be stamped with today (issue #2713)."""

    # Given a written record captured on an earlier date
    root = _semgrep_tree(tmp_path)
    monkeypatch.setattr(si, "REPO", root)
    monkeypatch.setattr(si, "SCANNERS", {"semgrep": si.SCANNERS["semgrep"]})
    digest_path = root / "containers" / "scanners" / "digests.json"
    si.write()
    data = json.loads(digest_path.read_text())
    old_sha = data["semgrep"]["rules_sha"]
    data["semgrep"]["rules_captured_at"] = "2026-11-08"
    digest_path.write_text(json.dumps(data), encoding="utf-8")

    # When  a rule is added to the pack and digests are re-written
    (root / "containers" / "scanners" / "semgrep" / "rules" / "default.yml").write_text(
        "- id: rule-one\n- id: rule-two\n", encoding="utf-8")
    si.write()

    # Then  the new pack is stamped with today
    data = json.loads(digest_path.read_text())
    assert data["semgrep"]["rules_sha"] != old_sha
    assert data["semgrep"]["rules_captured_at"] == _dt.date.today().isoformat()


def test_an_entry_without_an_image_digest_fails(tmp_path, monkeypatch, capsys):
    """`check` is the gate a scan workflow trusts: a record that pins only the Dockerfile, not
    the published image, fails it (issue #2609)."""

    # Given a fixture tree whose record was written but never pinned
    root = _tree(tmp_path)
    monkeypatch.setattr(si, "REPO", root)
    monkeypatch.setattr(si, "SCANNERS", {"trivy": si.SCANNERS["trivy"]})
    si.write()

    # When  the gate reads the record
    rc = si.check("trivy")

    # Then  it fails, naming the missing image pin
    assert rc == 1
    assert "image_digest" in capsys.readouterr().out


def test_the_real_digests_record_pins_every_published_scanner_image():
    """The real tree: every scanner entry names the manifest digest of the image its content-hash
    tag serves — measured live with `make pin-scanner-image-digests` (issue #2609)."""

    # Given this repository's scan record
    data = json.loads((REPO / "containers" / "scanners" / "digests.json").read_text())

    # When  each scanner entry is read
    for sid in si.SCANNERS:
        # Then  it carries a manifest digest in sha256:<64 hex> form
        assert si.DIGEST_PIN.fullmatch(str(data[sid].get("image_digest") or "")), (sid, data[sid])


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


def test_a_grype_edit_never_moves_the_syft_tag(tmp_path, monkeypatch):
    """Issue #746 AC: a grype bump cannot change the SBOM generator.

    While Syft rode the grype image, any grype Dockerfile change silently changed what
    `make sbom` ran. The tag each scanner publishes is the content hash of THAT scanner's
    own Dockerfile, so the isolation between the two is assertable, not a promise.
    """
    grype = (
        "# syntax=docker/dockerfile:1\n"
        f"FROM cgr.dev/chainguard/wolfi-base@{BASE_DIGEST}\n\n"
        "ARG GRYPE_VERSION=6.140.2-r0\n"
        'RUN apk add --no-cache "grype=${GRYPE_VERSION}"\n\n'
        'ENTRYPOINT ["grype"]\n'
        'CMD ["version"]\n'
    )
    syft = (
        "# syntax=docker/dockerfile:1\n"
        f"FROM cgr.dev/chainguard/wolfi-base@{BASE_DIGEST}\n\n"
        "ARG SYFT_VERSION=1.57.2-r0\n"
        'RUN apk add --no-cache "syft=${SYFT_VERSION}"\n\n'
        'ENTRYPOINT ["syft"]\n'
        'CMD ["version"]\n'
    )
    for name, text in (("grype", grype), ("syft", syft)):
        d = tmp_path / "containers" / "scanners" / name
        d.mkdir(parents=True)
        (d / "Dockerfile").write_text(text, encoding="utf-8")
    monkeypatch.setattr(si, "REPO", tmp_path)
    g0, s0 = si.content_hash("grype"), si.content_hash("syft")

    # When  the grype pin moves
    (tmp_path / "containers" / "scanners" / "grype" / "Dockerfile").write_text(
        grype.replace("6.140.2-r0", "6.141.0-r0"), encoding="utf-8"
    )

    # Then  grype's tag moves and syft's does not
    assert si.content_hash("grype") != g0
    assert si.content_hash("syft") == s0


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
                 op_stdout="load done", op_stderr="", pushcheck_rc=0):
    """Fake the leg's one policy seam (`si.run_ok`): an `imagetools inspect` answers
    with the given platforms (or probe_rc when the registry lacks the tag), every
    other command answers with op_rc and these streams. No real Docker runs — unit
    CI has none, and the behaviour under test is the leg's decision, not buildkit's.

    The push-check (issue #2960, the #335 seam) is answered as a recorded call with
    `pushcheck_rc`, so tests can SEE its position relative to the build; its real HTTP
    shape is proven hermetically in test_ci_images.py and the stub-registry tests below.
    """

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

    def fake_pushcheck(name):
        calls.append(["pushcheck", str(name)])
        return pushcheck_rc

    monkeypatch.setattr(si, "run_ok", fake)
    monkeypatch.setattr(si._ci_images, "pushcheck", fake_pushcheck)
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

    # And the write was PROVEN before the build: the push-check call precedes the --push (issue #2960)
    assert ["pushcheck", "trivy"] in calls
    assert calls.index(["pushcheck", "trivy"]) < calls.index(pushes[0])


def test_ensure_force_republishes_a_present_ref(tmp_path, monkeypatch, capsys):
    """force (the dispatch input, passed as an env value) re-pushes even a present tag."""

    # Given the registry already carries the tag on both platforms
    monkeypatch.setattr(si, "REPO", _tree(tmp_path))
    calls = _fake_docker(monkeypatch, platforms=("linux/amd64", "linux/arm64"))

    # When  ensure runs with FORCE set in the environment
    monkeypatch.setenv("FORCE", "1")
    rc = si.ensure("trivy", force=True)
    out = capsys.readouterr().out

    # Then  it published anyway (a --push ran, named the ref) — push-checked first (issue #2960)
    assert rc == 0 and "publishing" in out
    assert any("--push" in c for c in calls)
    assert ["pushcheck", "trivy"] in calls
    assert calls.index(["pushcheck", "trivy"]) < next(i for i, c in enumerate(calls) if "--push" in c)


def test_ensure_skips_the_publish_when_the_push_check_refuses(tmp_path, monkeypatch, capsys):
    """A package the credential cannot write must never reach the buildx build: ensure fails
    right after the refusal, naming the scanner, with NO --push command ever issued (issue #2960)."""

    # Given an absent tag AND a push-check that refuses
    monkeypatch.setattr(si, "REPO", _tree(tmp_path))
    calls = _fake_docker(monkeypatch, probe_rc=1, pushcheck_rc=1)

    # When  ensure runs
    rc = si.ensure("trivy")
    err = capsys.readouterr().err

    # Then  the leg fails with the refusal named...
    assert rc == 1
    assert "trivy: the credential cannot push" in err
    assert "the build is skipped" in err

    # ...and the build was never issued — only the tag probe and the push-check reached the seams
    assert not any("--push" in c for c in calls)
    assert ["pushcheck", "trivy"] in calls


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

    # Then  it delegates to the ONE builder scanner_image.build (a scan deferral builds locally
    #       and NEVER pushes, so it is not `ensure`) and hand-rolls no second `docker build`
    assert "_scanner_image.build(tool" in src
    # the old inline builder arguments (docker build -t <ref> <context>) must not be present
    assert '"build"' not in src or "subprocess.run([RUNTIME, \"build\"" not in src
    assert "cannot build" not in src  # the old failure message naming the inline build is gone


# ---------------------------------------------------------------------------
# push-check before buildx (issue #2960: ensure IS the ci-security-images publish seam)
# ---------------------------------------------------------------------------
_DENIED_BODY = ('{"errors":[{"code":"DENIED","message":"denied: permission_denied: read_package"}]}')


def _stub_registry_and_probe(tmp_path, upload_status: int = 202):
    """A stand-in GHCR + the RUNTIME stub the lane would call, wired through a probe file.

    Every request the registry answers bumps `probe.txt`; the fake runtime records that count when
    a `buildx build` is issued — so a test can SEE whether the write was proven before the build.
    """
    seen: list[tuple[str, str, str]] = []
    probe = tmp_path / "probe.txt"
    probe.write_text("0")

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:
            pass

        def _answer(self, status: int, payload) -> None:
            raw = (payload if isinstance(payload, str) else json.dumps(payload)).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _bump(self):
            probe.write_text(str(len(seen)))

        def do_GET(self):
            seen.append((self.command, self.path, self.headers.get("Authorization", "")))
            self._bump()
            self._answer(200 if self.path.startswith("/token?") else 404,
                         {"token": "stub-token"} if self.path.startswith("/token?") else _DENIED_BODY)

        def do_POST(self):
            seen.append((self.command, self.path, self.headers.get("Authorization", "")))
            self._bump()
            self._answer(upload_status, "" if upload_status < 300 else _DENIED_BODY)

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    runtime = tmp_path / "fake-runtime.sh"
    runtime.write_text(
        "#!/bin/sh\n"
        'echo "$*" >> "$RUNTIME_LOG"\n'
        'if [ "$2" = "build" ]; then\n'
        '  echo "BUILD_SEEN=$(cat "$PROBE_FILE" 2>/dev/null || echo 0)" >> "$RUNTIME_LOG"\n'
        '  exit 0\n'
        "fi\n"
        "exit 1\n")
    runtime.chmod(0o755)
    env = {**os.environ, "LLGENIE_REGISTRY": f"http://127.0.0.1:{srv.server_address[1]}",
           "GHCR_TOKEN": "s3cret", "GHCR_USER": "asimov-agent", "RUNTIME": str(runtime),
           "RUNTIME_LOG": str(tmp_path / "runtime.log"), "PROBE_FILE": str(probe), "FORCE": ""}
    return srv, seen, env, tmp_path / "runtime.log"


def _run_ensure(env) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(REPO / "scripts" / "scanner_image.py"), "ensure", "syft"],
                          env=env, capture_output=True, text=True, timeout=120)


def test_a_missing_scanner_is_push_checked_before_it_is_built(tmp_path):
    """`ensure` proves the credential may write the package BEFORE it issues a buildx push:
    the registry saw the token exchange AND the empty upload before the build ran."""

    # Given a registry that grants the push token and accepts the empty upload
    srv, seen, env, log = _stub_registry_and_probe(tmp_path)
    try:
        # When the lane's publish seam runs for the missing syft image
        r = _run_ensure(env)
        assert r.returncode == 0, r.stdout + r.stderr

        # Then the pre-flight hit the package the publish writes: push-scoped token, empty upload
        assert seen[0][0] == "GET" and seen[0][1].startswith("/token?")
        assert "scope=repository:llgenie/syft:push" in seen[0][1]
        assert seen[1][:2] == ("POST", "/v2/llgenie/syft/blobs/uploads/")
        assert seen[1][2] == "Bearer stub-token"

        # And the build was issued only AFTER both write-proof requests had happened
        log_text = log.read_text()
        assert "buildx build" in log_text and "--push" in log_text
        seen_at_build = int([ln for ln in log_text.splitlines() if ln.startswith("BUILD_SEEN=")][0]
                            .split("=", 1)[1])
        assert seen_at_build >= 2
    finally:
        srv.shutdown()


def test_a_denied_push_skips_the_build_and_names_the_refusal(tmp_path):
    """The whole point (issue #2960): a package the credential cannot write must fail the leg
    BEFORE any multi-arch build burns — with the registry's own denial in the output."""

    # Given a registry that grants the token but denies the empty upload (GHCR's read_package shape)
    srv, seen, env, log = _stub_registry_and_probe(tmp_path, upload_status=403)
    try:
        # When the publish seam runs
        r = _run_ensure(env)

        # Then it fails, and the refusal is loud and named
        assert r.returncode != 0
        out = r.stdout + r.stderr
        assert "push-check llgenie/syft" in out and "CANNOT push" in out
        assert "permission_denied: read_package" in out          # the registry's own words
        assert "syft: the credential cannot push" in out         # ensure names the scanner
        assert "the build is skipped" in out

        # And no build was ever issued — only the tag-lookup probe reached the runtime seam
        log_text = log.read_text()
        assert "buildx build" not in log_text
        assert "buildx imagetools inspect" in log_text
    finally:
        srv.shutdown()


def test_the_publish_step_is_handed_the_login_credential():
    """The lane must prove the SAME identity it publishes with (the #335 pattern)."""

    # Given the security-images workflow
    wf = (REPO / ".github" / "workflows" / "security-images.yml").read_text()

    # Then the step running the publish seam is handed the credential the login step logs in with
    assert "GHCR_TOKEN: ${{ secrets.GITHUB_TOKEN }}" in wf
    step_start = wf.index("- name: make ci-security-images")
    step_env = wf[step_start:wf.index("run: |", step_start)]
    assert "GHCR_TOKEN: ${{ secrets.GITHUB_TOKEN }}" in step_env
    # and the job keeps the write permission the credential needs
    job_start = wf.index("  build:\n")
    assert "packages: write" in wf[job_start:step_start]


