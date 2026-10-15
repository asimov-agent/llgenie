"""The install job waits for the images it pulls (issue #169).

A bump PR builds and publishes its engine images in the parallel `engine-image-*`
jobs, but `pipeline.yml`'s `install` job needs only `ci-images` and used to pull
the brand-new tag before any job had pushed it:

    [install] FAIL llama.cpp/cpu: not published in ghcr.io/asimov-agent

`make ci-wait-engine-images` is the gate: it resolves exactly the tags `install`
pulls and polls the registry manifest until each one exists, failing loudly on a
tag that never appears. Hermetic tests drive the gate with a stubbed manifest
lookup; the last test hits the real registry with no mock.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
PIPELINE = REPO / ".github" / "workflows" / "pipeline.yml"
sys.path.insert(0, str(REPO))

import scripts.install_engine_launchers as iel  # noqa: E402

# `install_engine_launchers` imports its sibling as the top-level `engine_image`;
# patch THAT module object, or the gate keeps calling the unpatched one.
ei = iel.ei

REGISTRY = "ghcr.io/asimov-agent"


def _install_steps() -> list[str]:
    """The `run:` commands of the reusable pipeline's install job, in step order."""
    wf = yaml.safe_load(PIPELINE.read_text())
    steps = wf["jobs"]["install"]["steps"]
    return [s.get("run", "") for s in steps]


def _gate(monkeypatch, log: list[str], published: bool = True):
    """Point the gate's manifest lookup at a fake registry and log every ref it looked up."""
    monkeypatch.setattr(ei, "REGISTRY", REGISTRY)

    def fake(ref: str) -> tuple[str, str]:
        log.append(ref)
        return ("sha256:" + "0" * 64, "") if published else ("", "404 Not Found")

    monkeypatch.setattr(ei, "_digest_http", fake)


def _recipe(target: str) -> str:
    """One Makefile target's recipe, exactly as `make <target>` runs it."""
    return (REPO / "Makefile").read_text().split(f"\n{target}:", 1)[1].split("\n\n", 1)[0]


def _install_ci_targets() -> list[str]:
    """The `make ci-<job>` targets the install job runs, in step order.

    `ci-free-disk` is a disk helper, not a job target (same exclusion as
    `tests/test_ci_images.py::_make_targets`).
    """
    found: list[str] = []
    for run in _install_steps():
        found += re.findall(r"make (ci-[a-z0-9-]+)", run)
    return [t for t in found if t != "ci-free-disk"]


def test_install_job_waits_before_it_installs():
    """ci-install waits for the images it pulls before it runs make install."""

    # Given the ci-install recipe the install job runs
    recipe = _recipe("ci-install")

    # When the wait and the install are located in recipe order
    wait = recipe.find("$(MAKE) ci-wait-engine-images")
    run = recipe.find("$(MAKE) ci-install-run")

    # Then the gate is in the recipe and strictly before make install
    assert wait != -1, "ci-install has no make ci-wait-engine-images"
    assert run != -1, "ci-install has no make ci-install-run"
    assert wait < run, f"wait at {wait} must precede ci-install-run at {run}"


def test_the_install_job_runs_one_make_target():
    """The gate is a make prerequisite, so the job still runs exactly one ci-<job> target."""

    # Given the install job's run: steps
    targets = _install_ci_targets()

    # Then ci-install is the only ci target, and no ci-wait step sits beside it
    assert targets == ["ci-install"], targets
    assert "ci-wait-engine-images" not in targets


def test_macos_install_is_not_gated():
    """macOS pulls no engine image, so the gate target skips the lookup (issue #120)."""

    # Given ci-install's recipe and the gate target's recipe
    install, gate = _recipe("ci-install"), _recipe("ci-wait-engine-images")

    # Then ci-install is OS-neutral: the same targets on both OSes, no Darwin branch
    assert "Darwin" not in install
    assert "$(MAKE) ci-wait-engine-images ARCH=cpu" in install

    # And only the gate target branches on the OS, with the registry lookup on Linux
    assert "ifeq ($(HOST_OS),Darwin)" in gate
    darwin, linux = gate.split("\nelse\n", 1)
    assert "--wait-published" not in darwin
    assert "--wait-published" in linux

    # And the gate is defined AFTER `HOST_OS := $(shell uname -s)`: make evaluates ifeq
    # while it parses the file, so a conditional placed earlier sees an empty HOST_OS and
    # would take the Linux branch on macOS too
    mk = (REPO / "Makefile").read_text()
    assert mk.find("HOST_OS := $(shell uname -s)") < mk.find("\nci-wait-engine-images:")


def test_the_gate_waits_for_exactly_what_install_pulls(monkeypatch, tmp_path):
    """The gate cannot wait for an image install would not pull, nor skip one it would."""

    # Given a registry that answers every lookup as published
    refs: list[str] = []
    pulled: list[tuple[str, str]] = []
    _gate(monkeypatch, refs)
    monkeypatch.setattr(ei, "image_platform", lambda tag: "linux/amd64")

    def fake_ensure(engine: str, variant: str, build: bool) -> str:
        pulled.append((engine, variant))
        return ei.resolve(engine, None, variant)["tag"]

    monkeypatch.setattr(iel, "ensure_image", fake_ensure)

    # When the gate waits, and install resolves its images
    assert iel.wait_published("cpu", timeout_s=5, poll_s=0) == 0
    assert iel.install(tmp_path / "bin", "cpu", build=False) == 0

    # Then the gate looked up exactly the refs install pulled
    want = [f"{REGISTRY}/{ei.resolve(e, None, v)['tag']}" for e, v in pulled]
    assert refs == want, f"gate waited for {refs}, install pulled {want}"


def test_a_never_published_tag_fails_loudly(monkeypatch, capsys):
    """A tag that never appears is a named failure, never a silent skip."""

    # Given a registry that answers every lookup with a 404
    _gate(monkeypatch, [], published=False)

    # When the gate waits and its deadline passes
    rc = iel.wait_published("cpu", timeout_s=0, poll_s=0)
    out = capsys.readouterr().out

    # Then it fails and names every tag that is still missing
    assert rc == 1
    for engine in iel.CORE_ENGINES:
        tag = ei.resolve(engine, None, "cpu")["tag"]
        assert f"{REGISTRY}/{tag}" in out
        assert f"FAIL {engine}/cpu" in out


def test_published_images_need_no_wait(monkeypatch):
    """An already published image is one lookup, not a retry budget."""

    # Given a registry that answers every lookup with a digest
    refs: list[str] = []
    monkeypatch.setattr(ei, "REGISTRY", REGISTRY)

    def published(ref: str) -> tuple[str, str]:
        refs.append(ref)
        return "sha256:" + "0" * 64, ""

    monkeypatch.setattr(ei, "_digest_http", published)

    # When the gate waits
    rc = iel.wait_published("cpu", timeout_s=60, poll_s=20)

    # Then it passes after a single pass over the tags
    assert rc == 0
    assert len(refs) == len(iel.CORE_ENGINES)


def test_every_image_install_pulls_is_published():
    """Real registry, no mock: every image `make install` pulls is on GHCR."""

    # Given the committed engine params and the cpu backend
    plan = [e for e in iel.install_plan("cpu") if e["variant"]]
    assert plan, "install resolves no engine image for cpu"

    # When the gate waits against the real registry with a short deadline
    rc = iel.wait_published("cpu", timeout_s=120, poll_s=10)

    # Then every tag install pulls is published
    assert rc == 0, "an image make install pulls is not published on GHCR (issue #169)"
