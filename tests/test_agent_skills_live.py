#!/usr/bin/env python3
"""Hermes really LOADS each bot's skill when its leg runs (issue #577).

`tests/test_agent_skills.py` proves the files and the wiring. This proves the loading, through
Hermes's OWN preload path: `agent.skill_commands.build_preloaded_skills_prompt` is the function
`hermes -z "…" -s <name>` calls before the model's first turn (see
`hermes_cli/oneshot.py::_build_preloaded_skills_prompt`). Each leg's `-s` list is fed to it against a
Hermes home registered by the SAME script the agent image runs
(`scripts/hermes_skills_register.py`), and the assertions are on what comes back: the skill RESOLVED
(not in `missing`) and its content is in the prompt the model receives.

It runs in the `agents-read` job's venv (`make agents-read-venv`, hermes-agent pinned), not in the
hermetic test image — so a missing hermes-agent is a LOUD failure here, never a skip.
"""
from __future__ import annotations

import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import check_agent_skills as guard  # noqa: E402  (the real leg/skill scanner)

REGISTER = REPO / "scripts" / "hermes_skills_register.py"
SKILLS_DIR = REPO / ".hermes" / "skills"


def _skills_module():
    """Hermes's preload seam, or a loud failure naming how to get it."""
    try:
        from agent.skill_commands import build_preloaded_skills_prompt
    except ModuleNotFoundError as exc:  # unprovisioned, never a skip
        raise AssertionError(
            "hermes-agent is not importable, so the real skill-loading path cannot be exercised "
            f"({exc}). This test runs in the `agents-read` venv (`make agents-read-venv`) or on a "
            "dev host with Hermes installed."
        ) from exc
    return build_preloaded_skills_prompt


@contextmanager
def hermes_home(tmp_path: Path, register: bool = True):
    """A throwaway HERMES_HOME, registered — or not — by the image's own script."""
    home = tmp_path / "hermes-home"
    home.mkdir(parents=True, exist_ok=True)
    if register:
        subprocess.run([sys.executable, str(REGISTER), "--home", str(home),
                        "--dir", str(SKILLS_DIR)], check=True, capture_output=True, text=True)
    saved = {k: os.environ.get(k) for k in ("HERMES_HOME", "TERMINAL_CWD")}
    os.environ["HERMES_HOME"] = str(home)
    os.environ.pop("TERMINAL_CWD", None)  # `external_dirs` needs no cwd and no project discovery
    cwd = os.getcwd()
    os.chdir(tmp_path)                    # and must not depend on where the process stands
    try:
        yield home
    finally:
        os.chdir(cwd)
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_the_image_registers_the_checkout_skills_dir():
    """The registration the container installs is the one this test drives."""

    # Given the agent image's install script
    script = (REPO / "scripts" / "install_hermes_ci.sh").read_text(encoding="utf-8")

    # When  its skill-registration section is read
    # Then  it runs the register script for the checkout's dir and reads the value back
    assert "hermes_skills_register.py" in script
    assert "/repo/.hermes/skills" in script
    assert "--check" in script


def test_every_leg_resolves_its_skills_through_hermes_own_preload(tmp_path):
    """Each leg's `-s` list, fed to Hermes's real preload, yields that bot's contract."""

    build_prompt = _skills_module()
    legs = guard.iter_legs(REPO)

    # Given every agent leg of this repository
    # When  its preload list goes through Hermes's preload path, against the image's registration
    with hermes_home(tmp_path):
        for leg in legs:
            text, loaded, missing = build_prompt(list(leg["skills"]))

            # Then  nothing is missing, every name loaded, and the preload preamble is present
            assert missing == [], f"{leg['where']}: unresolved {missing}"
            assert set(leg["skills"]) <= set(loaded), (leg["where"], loaded)
            assert "Treat its instructions as active guidance" in text, leg["where"]

            # And  each skill's own content reached the prompt the model receives
            for name in leg["skills"]:
                skill_md = SKILLS_DIR / name / "SKILL.md"
                description = guard.frontmatter(skill_md)["description"]
                assert description in text, f"{leg['where']}: {name} content did not load"
                assert f'"{name}" skill preloaded' in text, (leg["where"], name)
                assert "## Rules" in skill_md.read_text(encoding="utf-8")


def test_an_unregistered_home_loads_nothing(tmp_path):
    """The negative half: without the registration, the same preload resolves nothing.

    This is the failure the image's registration prevents — and the proof that a leg preloading
    nothing cannot be checked as having run under its contract.
    """

    build_prompt = _skills_module()

    # Given a Hermes home with no registration
    # When  a leg's preload list is fed to Hermes's real preload path
    with hermes_home(tmp_path, register=False):
        text, loaded, missing = build_prompt(["issue-triage", "bot-unattended"])

    # Then  both are reported missing and the prompt is empty: the contract did not load
    assert loaded == []
    assert set(missing) == {"issue-triage", "bot-unattended"}
    assert text.strip() == ""
