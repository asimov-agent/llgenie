#!/usr/bin/env python3
"""A stale launcher must not silently run an older pinned engine (issue #842).

`~/bin/llgenie-engine-<engine>` embeds a content-addressed image tag
`<pin[:8]>-<params_hash8>-<variant>`. The launcher is written once and never re-derived, so
an engine pin can move underneath it: the host keeps running the older image and
`--version` reports it happily, or a fresh install fails on a tag nobody pushed with an
error that blames the registry.

The check's whole point is that the expected tag comes from the SAME function that writes
the launcher (`install_engine_launchers.install_plan`), so these tests build their fixtures
with that writer and never re-implement the formula.

Runnable without Docker: the registry case stubs the `docker` binary on PATH.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts import check_engine_launchers as cel  # noqa: E402  (the real check)
from scripts import engine_image as ei  # noqa: E402
from scripts import install_engine_launchers as iel  # noqa: E402  (the real WRITER: one formula)

#: A backend every engine ships, so the fixtures do not depend on the test host's GPU.
ARCH = "cpu"


def _an_engine() -> dict:
    """One (engine, variant, tag) the writer would emit for ARCH — the fixture's truth."""
    rows = [e for e in iel.install_plan(ARCH, ["all"]) if e.get("variant")]
    assert rows, "the committed params declare no engine for cpu"
    return rows[0]


def _write_launcher(bindir: Path, engine: str, tag: str) -> Path:
    """Write the launcher exactly as `install` does, then override the image tag."""
    bindir.mkdir(parents=True, exist_ok=True)
    path = bindir / iel.script_name(engine)
    path.write_text(iel.launcher(engine, "cpu", tag, "/tmp/models"))
    path.chmod(0o755)
    return path


def test_a_current_launcher_passes(tmp_path):
    """The launcher the writer would produce today is the one the check expects."""

    # Given a launcher carrying the tag computed from the committed params
    row = _an_engine()
    _write_launcher(tmp_path, row["engine"], row["tag"])

    # When  the check runs
    code = cel.check(tmp_path, ARCH)

    # Then  it passes
    assert code == 0


def test_a_stale_launcher_fails_naming_both_tags_and_both_pins(tmp_path, capsys):
    """A launcher on an older pin is the silent version-skew this gate exists to stop."""

    # Given a launcher naming a different pin than the committed params compute
    row = _an_engine()
    stale = f"llgenie/{row['engine']}:{'0ldp1n00'}-{'deadbeef'}-cpu"
    _write_launcher(tmp_path, row["engine"], stale)

    # When  the check runs
    code = cel.check(tmp_path, ARCH)
    out = capsys.readouterr()

    # Then  it fails, naming the engine, both tags and both pins
    assert code == 1, "a launcher that names another image must fail"
    combined = out.out + out.err
    assert row["engine"] in combined
    assert stale in combined and row["tag"] in combined
    assert "0ldp1n00" in combined and cel.tag_pin(row["tag"]) in combined
    assert "STALE" in combined


def test_no_launcher_is_informational(tmp_path, capsys):
    """CI has no ~/bin launchers at all: that is not a failure."""

    # Given an empty bin dir
    empty = tmp_path / "bin"
    empty.mkdir()

    # When  the check runs
    code = cel.check(empty, ARCH)
    out = capsys.readouterr().out

    # Then  it exits 0 and says so once per engine, as information
    assert code == 0
    assert "informational" in out
    assert "0 ok" in out


def _stub_docker(bindir: Path, marker: Path, exit_code: int) -> str:
    """A fake `docker` on PATH: records that it ran, exits `exit_code`."""
    bindir.mkdir(parents=True, exist_ok=True)
    exe = bindir / "docker"
    exe.write_text(f"#!/bin/sh\ntouch {marker}\nexit {exit_code}\n")
    exe.chmod(0o755)
    return str(bindir)


def test_check_registry_reports_an_unpublished_tag(tmp_path, monkeypatch, capsys):
    """`CHECK_REGISTRY=1` turns a tag no manifest resolves into a failure."""

    # Given a current launcher, a registry, and a docker whose manifest lookup misses
    row = _an_engine()
    _write_launcher(tmp_path / "bin", row["engine"], row["tag"])
    marker = tmp_path / "docker-ran"
    monkeypatch.setenv("PATH", _stub_docker(tmp_path / "fakebin", marker, 1) + ":" + os.environ["PATH"])
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/example/llgenie", raising=False)
    monkeypatch.setattr(ei, "RUNTIME", "docker", raising=False)

    # When  the check runs with the registry check on
    code = cel.check(tmp_path / "bin", ARCH, check_registry=True)
    out = capsys.readouterr().out

    # Then  it fails, naming the tag as not published, and it did consult the registry
    assert code == 1
    assert "NOT PUBLISHED" in out and row["tag"] in out
    assert marker.exists(), "the registry check never ran a manifest lookup"


def test_the_default_run_touches_no_registry(tmp_path, monkeypatch, capsys):
    """No network by default: the gate must be safe on a runner with no GHCR reach."""

    # Given a current launcher and a docker that records any use
    row = _an_engine()
    _write_launcher(tmp_path / "bin", row["engine"], row["tag"])
    marker = tmp_path / "docker-ran"
    monkeypatch.setenv("PATH", _stub_docker(tmp_path / "fakebin", marker, 0) + ":" + os.environ["PATH"])
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/example/llgenie", raising=False)
    monkeypatch.setattr(ei, "RUNTIME", "docker", raising=False)

    # When  the check runs WITHOUT --check-registry
    code = cel.check(tmp_path / "bin", ARCH)

    # Then  it passes and never invoked the registry
    assert code == 0
    assert not marker.exists(), "the default run must not talk to a registry"


def test_the_expected_tag_comes_from_the_launcher_writer():
    """A second copy of the tag formula would agree today and disagree later."""

    # Given the check's expected() and the writer's install_plan
    rows = {r["engine"]: r for r in cel.expected(ARCH)}
    written = {e["engine"]: e for e in iel.install_plan(ARCH, ["all"]) if e.get("variant")}

    # Then  they are the same list, tag for tag (the check imports the writer, not the formula)
    assert rows.keys() == written.keys()
    assert all(rows[k]["tag"] == written[k]["tag"] for k in rows)


# ------------------------------- the tag hashes FOUR inputs, so the check must too
# `engine_skills._image_inputs` hashes the variant's params, its committed Dockerfile,
# `containers/engines/entrypoint.sh` and `scripts/engine_runner.py`. A check that hashed only the
# params would call a correct launcher stale on a branch that legitimately edits the runner — the
# worst audience for a false red.
def _tag_with(params: dict, variant: str, **overrides) -> str:
    """The tag the published scheme computes for `variant`, with any of the four inputs replaced."""
    import hashlib

    from scripts import engine_skills as es

    digest = hashlib.sha256(es._image_inputs(params, variant, **overrides)).hexdigest()[:8]
    return f"llgenie/{params['id']}:{str(params['pinned'])[:8]}-{digest}-{variant}"


def test_expected_is_the_full_four_input_digest():
    """`expected()` must not be a shortcut formula over the params alone."""

    # Given the committed params for one engine
    row = _an_engine()
    params = ei.load_params(row["engine"])

    # When  the tag is recomputed from all four inputs, read from disk exactly as the build does
    full = _tag_with(params, row["variant"])

    # Then  the check's expectation is that same tag (params + Dockerfile + entrypoint + runner)
    assert cel.expected(ARCH) and row["tag"] == full


def test_a_changed_engine_runner_makes_a_current_launcher_stale(tmp_path, capsys):
    """Editing `scripts/engine_runner.py` moves every tag: a launcher from before it IS stale."""

    # Given a launcher whose tag was computed with DIFFERENT runner bytes
    row = _an_engine()
    params = ei.load_params(row["engine"])
    shifted = _tag_with(params, row["variant"], runner=b"# a runner that changed\n")
    assert shifted != row["tag"], "the runner bytes must move the tag"
    _write_launcher(tmp_path, row["engine"], shifted)

    # When  the check runs against this tree (whose runner is the committed one)
    code = cel.check(tmp_path, ARCH)
    out = capsys.readouterr()

    # Then  it is STALE and names both tags — correctly, and for the right reason
    assert code == 1
    combined = out.out + out.err
    assert "STALE" in combined and shifted in combined and row["tag"] in combined
