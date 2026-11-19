#!/usr/bin/env python3
"""The agent publish lane must RUN the image it published (issue #2934).

`make agent-image-profiles-check` is the post-publish seam: it boots the just-published
`llgenie/agent` image as a STANDARD agent leg (env guard, scrubbed stream, forwarded keys, bot
marker — the same seams every other leg passes) and runs
`scripts/agent_image_profiles_check.py` INSIDE it, testing the exact path Hermes resolves
`-p <lane>` from: `$HERMES_HOME/profiles/<lane>/config.yaml`. Before this seam,
`publish-agent-image.yml` only built + pushed, and the published `agent:latest` on main `81e6de6e8`
answered a real prompt attempt with `Profile 'llgenie-status-keeper' does not exist`.

These tests drive the REAL script (never a copy of its logic) over real tmp filesystems, plus
wiring tests proving the publish job runs the seam and the existing prompt proof
(`make hermes-smoke`) after the push, in that order.
"""
from __future__ import annotations

import json
from pathlib import Path

import scripts.agent_image_profiles_check as check  # noqa: E402  (the real seam, never a copy)

REPO = Path(__file__).resolve().parent.parent


def _manifest(tmp_path: Path, lanes: list[str]) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"profiles": [{"name": n} for n in lanes]}))
    return path


def _provision(home: Path, lanes: list[str]) -> None:
    for lane in lanes:
        p = home / "profiles" / lane
        p.mkdir(parents=True)
        (p / "config.yaml").write_text("model:\n  default: nous-longcat\n")


def test_manifest_lanes_are_read_from_the_manifest(tmp_path: Path) -> None:
    # Given a manifest declaring lanes
    path = _manifest(tmp_path, ["llgenie-architect", "llgenie-status-keeper"])
    # When the seam reads it
    # Then it names exactly those lanes
    assert check.manifest_lanes(path) == ["llgenie-architect", "llgenie-status-keeper"]


def test_manifest_without_profiles_is_unusable(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"nope": True}))
    try:
        check.manifest_lanes(path)
        raise AssertionError("empty manifest must be unusable, not vacuously passing")
    except SystemExit as exc:
        assert "no profiles list" in str(exc)


def test_every_lane_provisioned_exits_zero(tmp_path: Path, capsys) -> None:
    # Given an image-shaped profile home where every lane has its config.yaml
    home = tmp_path / "hermes-home"
    lanes = ["llgenie-architect", "llgenie-status-keeper"]
    _provision(home, lanes)
    # When the real CLI runs inside that home
    rc = check.main(["--manifest", str(_manifest(tmp_path, lanes)), "--home", str(home)])
    # Then it prints OK per lane and exits green
    assert rc == 0
    out = capsys.readouterr().out
    assert "OK llgenie-architect" in out and "OK llgenie-status-keeper" in out


def test_missing_lane_reds_the_check_naming_it(tmp_path: Path, capsys) -> None:
    # Given a profile home missing one lane (the measured ea98772a4319 shape)
    home = tmp_path / "hermes-home"
    _provision(home, ["llgenie-architect"])
    manifest = _manifest(tmp_path, ["llgenie-architect", "llgenie-status-keeper"])
    # When the real CLI runs against it
    rc = check.main(["--manifest", str(manifest), "--home", str(home)])
    # Then the check fails, printing MISSING for the absent lane and naming it in the verdict
    assert rc == 1
    out = capsys.readouterr().out
    assert "MISSING llgenie-status-keeper" in out
    assert "FAILED" in out and "llgenie-status-keeper" in out


def test_a_profile_dir_without_config_yaml_is_missing(tmp_path: Path) -> None:
    # Given a lane whose profile dir exists but carries no config.yaml
    # (Hermes resolves `-p <lane>` from profiles/<lane>/config.yaml — a bare dir is not a profile)
    home = tmp_path / "hermes-home"
    (home / "profiles" / "llgenie-architect").mkdir(parents=True)
    manifest = _manifest(tmp_path, ["llgenie-architect"])
    rc = check.main(["--manifest", str(manifest), "--home", str(home)])
    assert rc == 1


def test_profile_home_defaults_to_hermes_home_env(tmp_path: Path, monkeypatch) -> None:
    # Given HERMES_HOME set (the agent image bakes /home/agent/.hermes) and no --home flag
    home = tmp_path / "agent-hermes"
    _provision(home, ["llgenie-architect"])
    monkeypatch.setenv("HERMES_HOME", str(home))
    manifest = _manifest(tmp_path, ["llgenie-architect"])
    # When the seam runs the way the in-image leg calls it
    assert check.main(["--manifest", str(manifest)]) == 0


def test_the_leg_boots_the_image_through_the_standard_agent_leg_seams() -> None:
    # Given the Makefile
    mk = (REPO / "mk" / "agents.mk").read_text()
    leg_at = mk.index("\nagent-image-profiles-check:")
    leg = mk[leg_at + 1: mk.index("\n_agent-image-profiles-check:")]
    internal = mk[mk.index("\n_agent-image-profiles-check:"):]

    # Then the public target is an agent-image run guarded BEFORE the image is ensured,
    # redacted through the ONE scrub macro, carrying the forwarded keys and the bot marker
    assert "python3 scripts/require_env.py NOUS_API_KEY" in leg
    assert leg.index("python3 scripts/require_env.py") < leg.index("scripts/ci_images.py ensure agent")
    assert "$(call scrubbed_run," in leg
    assert "$(AGENT_IMAGE)" in leg
    assert "$(AGENT_SHELL_FORWARD)" in leg and "$(AGENT_BOT_MARKER)" in leg
    assert "bash -lc 'make _agent-image-profiles-check'" in leg
    # And the internal target runs the ONE real seam script inside the image
    assert "python3 scripts/agent_image_profiles_check.py --manifest agents/manifest.json" in internal


def test_the_publish_lane_runs_the_seam_and_the_prompt_proof_after_the_push() -> None:
    import yaml

    # Given the build-agent CI lane
    doc = yaml.safe_load((REPO / ".github" / "workflows" / "publish-agent-image.yml").read_text())
    steps = doc["jobs"]["publish"]["steps"]
    runs = [str(st.get("run", "")) for st in steps]
    # When its steps are ordered
    i_push = next(i for i, r in enumerate(runs) if "make publish-agent-image" in r)
    i_profiles = next(i for i, r in enumerate(runs) if "make agent-image-profiles-check" in r)
    i_smoke = next(i for i, r in enumerate(runs) if "make hermes-smoke" in r)
    # Then verification happens AFTER the push, before the lane can exit green
    assert i_push < i_profiles < i_smoke
    # And both verification steps pass the same lane credential every other agent lane passes
    for i in (i_profiles, i_smoke):
        assert steps[i].get("env", {}).get("NOUS_API_KEY") == "${{ secrets.NOUS_PORTAL_API_TOKEN }}"
