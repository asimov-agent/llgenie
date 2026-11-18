"""Issue #178: PR-scoped producer runs publish and measure the UNIQUE PINNED TAG ONLY
(OpenSpec change engine-tag-publish-178).

A `push=true` engine-build dispatch fired by a PR repin used to publish every ref
`publish_refs` returns — including the moving `:<arch>` (and `:latest`) aliases. A PR whose
pin is not merged yet therefore repointed the alias out from under the published main pin,
and the very next published-leg step demanded `digest(pin) == digest(:arch)` — comparing
this PR's pin against a tag main no longer owns (or another PR's pin already moved). These
tests pin the scoping hermetically — no docker, no network: the runtime seam is stubbed.
"""
from __future__ import annotations

import re

import scripts.engine_image as ei


def _point(monkeypatch):
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    monkeypatch.setattr(ei, "RUNTIME", "docker")


def _spec() -> dict:
    # No params_file: engine_latest_variant() falls back to spec["variant"], so refs are
    # [pinned, :cuda, :latest] — the full moving-ref set a main-scope run would move.
    return {"id": "vllm", "engine": "vllm-project/vllm", "backend": "cuda",
            "variant": "cuda", "tag": "vllm:abc12345-cuda"}


def _stub_runtime(monkeypatch) -> list[list[str]]:
    calls: list[list[str]] = []

    def fake_sh(cmd, **kw):
        calls.append(list(cmd))

        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        return R()

    monkeypatch.setattr(ei, "_sh", fake_sh)
    return calls


def _pushed_refs(calls: list[list[str]]) -> list[str]:
    return [c[-1] for c in calls if c[0] == ei.RUNTIME and c[1] == "push"]


def test_pr_scoped_push_publishes_the_pinned_tag_only(monkeypatch, capsys):
    """AC: PR-scoped engine build publishes only unique pin — the moving refs are never
    touched, and the note names issue #178."""
    _point(monkeypatch)
    calls = _stub_runtime(monkeypatch)
    monkeypatch.setattr(ei, "image_exists", lambda tag: True)
    monkeypatch.setattr(ei, "test_image", lambda spec: 0)
    spec = _spec()
    pin, *moving = ei.publish_refs(spec)
    assert ei.push(spec, moving=False) == 0
    assert _pushed_refs(calls) == [pin]  # exactly the pinned tag, nothing else
    tagged = [c for c in calls if c[0] == ei.RUNTIME and c[1] == "tag"]
    assert all(m not in c for m in moving for c in tagged)
    out = capsys.readouterr().out
    assert "PR-scoped publish (issue #178)" in out
    for m in moving:
        assert m in out  # every skipped ref is named


def test_main_scope_push_still_publishes_every_ref(monkeypatch):
    """Regression: the default `push()` (main-scope) is unchanged — all publish_refs move."""
    _point(monkeypatch)
    calls = _stub_runtime(monkeypatch)
    monkeypatch.setattr(ei, "image_exists", lambda tag: True)
    monkeypatch.setattr(ei, "test_image", lambda spec: 0)
    spec = _spec()
    assert ei.push(spec) == 0
    assert _pushed_refs(calls) == ei.publish_refs(spec)


def test_pr_scoped_pull_measures_the_pin_alone(monkeypatch, capsys):
    """AC: PR-scoped published pull passes mid-wave even though :cuda carries another
    pin's digest — only the pinned tag is measured."""
    _point(monkeypatch)
    _stub_runtime(monkeypatch)
    spec = _spec()
    pin, arch, latest = ei.publish_refs(spec)
    digests = {pin: "sha256:AAA", arch: "sha256:BBB", latest: "sha256:CCC"}
    monkeypatch.setattr(ei, "_digest", lambda ref: digests.get(ref, ""))
    assert ei.pull_published(spec, moving_check=False) == spec["tag"]
    out = capsys.readouterr().out
    assert "PR-scoped published pull (issue #178)" in out
    assert "moving refs skipped" in out


def test_main_scope_pull_still_fails_on_alias_mismatch(monkeypatch, capsys):
    """Regression: the main-scope published pull keeps demanding digest(pin) == digest(:arch)."""
    _point(monkeypatch)
    _stub_runtime(monkeypatch)
    spec = _spec()
    pin, arch, latest = ei.publish_refs(spec)
    digests = {pin: "sha256:AAA", arch: "sha256:BBB", latest: "sha256:AAA"}
    monkeypatch.setattr(ei, "_digest", lambda ref: digests.get(ref, ""))
    assert ei.pull_published(spec) == ""
    assert "FAIL digest mismatch" in capsys.readouterr().out


def test_cli_wires_no_moving_into_both_legs(monkeypatch):
    """AC wiring: `--no-moving` on `push` / `pull-published` reaches the gated functions;
    without it the main-scope defaults stand."""
    _point(monkeypatch)
    seen: dict = {}

    def fake_push(spec, moving=True):
        seen["push"] = moving
        return 0

    def fake_pull(spec, moving_check=True):
        seen["pull"] = moving_check
        return spec["tag"]

    monkeypatch.setattr(ei, "push", fake_push)
    monkeypatch.setattr(ei, "pull_published", fake_pull)
    assert ei.main(["push", "vllm", "--variant", "cuda", "--no-moving"]) == 0
    assert seen["push"] is False
    assert ei.main(["pull-published", "vllm", "--variant", "cuda"]) == 0
    assert seen["pull"] is True
    assert ei.main(["pull-published", "vllm", "--variant", "cuda", "--no-moving"]) == 0
    assert seen["pull"] is False


def test_make_seam_and_workflow_dispatch_carry_the_scope():
    """AC wiring (file-level): the Makefile translates MOVING=0 to --no-moving, both engine
    legs pass the flag, the workflow exposes `moving_tags` (default true), and the PR repin
    trigger dispatches moving_tags=false on every cell."""
    from pathlib import Path

    make = (Path(__file__).resolve().parents[1] / "Makefile").read_text()
    assert "MOVING_FLAG = $(if $(filter 0 false,$(MOVING)),--no-moving,)" in make
    engines = (Path(__file__).resolve().parents[1] / "mk" / "engines.mk").read_text()
    pull_line = next(line for line in engines.splitlines()
                     if "pull-published" in line and "engine_image.py" in line)
    push_line = next(line for line in engines.splitlines()
                     if re.search(r"engine_image\.py push", line))
    assert "$(MOVING_FLAG)" in pull_line and "$(MOVING_FLAG)" in push_line
    wf = (Path(__file__).resolve().parents[1] / ".github" / "workflows"
          / "engine-build.yml").read_text()
    assert "moving_tags:" in wf
    assert 'default: "true"' in wf.split("moving_tags:")[1].split("producer_run:")[0]
    assert wf.count("MOVING: ${{ inputs.moving_tags == 'false' && '0' || '1' }}") == 2
    trig = (Path(__file__).resolve().parents[1] / "scripts"
            / "engine_build_trigger.py").read_text()
    assert '"engine={engine}", "push=true", "moving_tags=false"' in trig
