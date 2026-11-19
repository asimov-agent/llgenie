"""The chain's secret lands where Hermes profile mode actually reads it (issue #2929).

Measured against Hermes 0.23.2: `hermes -p <lane>` resolves `model.key_env` from the
PROFILE's own `.env` — a key that only sits in the leg's exported environment authenticates
nothing. `scripts/seed_profile_hermes_env.py` moves each key from the caller's environment
into every llgenie profile home's `.env` (and the agent image does the same at every leg
start through its /etc/profile.d hook). These tests run the REAL script over REAL homes and
prove it never invents, duplicates, prints, or leaks a value, and never touches foreign
profiles.
"""
from __future__ import annotations

import importlib.util
import os
import stat
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SPEC = REPO / "scripts" / "seed_profile_hermes_env.py"


def _load():
    spec = importlib.util.spec_from_file_location("seed_profile_hermes_env", SPEC)
    assert spec is not None and spec.loader is not None, f"cannot load {SPEC}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


seed = _load()


def _homes(tmp_path: Path) -> Path:
    home = tmp_path / "hermes-home"
    profiles = home / "profiles"
    for name in ("llgenie-planner", "llgenie-architect", "tll-other", "personal"):
        (profiles / name).mkdir(parents=True)
    return home


def _key(value: str = "probe-key-value"):
    return {"NOUS_API_KEY": value}


def test_seed_all_lands_the_key_in_global_and_llgenie_profiles_only(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "environ", {**os.environ, **_key()})
    home = _homes(tmp_path)
    profiles = home / "profiles"

    rc = seed.main(["--all", "--home", str(home), "--profiles-parent", str(profiles)])
    assert rc == 0

    for target in (home, profiles / "llgenie-planner", profiles / "llgenie-architect"):
        env = target / ".env"
        assert env.is_file(), f"{target} was not seeded"
        assert "NOUS_API_KEY=probe-key-value" in env.read_text()
        assert stat.S_IMODE(env.stat().st_mode) == 0o600, "a key file is not world-readable"
    assert not (profiles / "tll-other" / ".env").exists(), "a foreign profile is never touched"
    assert not (profiles / "personal" / ".env").exists()


def test_seed_merges_in_place_and_stays_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "environ", {**os.environ, **_key("first")})
    home = tmp_path / "hermes-home"
    (home / "profiles" / "llgenie-planner").mkdir(parents=True)
    (home / ".env").write_text("SOMETHING_ELSE=keep\nNOUS_API_KEY=stale\n")

    assert seed.main(["--all", "--home", str(home)]) == 0
    first = (home / ".env").read_text()
    assert "SOMETHING_ELSE=keep" in first, "foreign lines survive"
    assert first.count("NOUS_API_KEY=") == 1, "the key line is UPDATED in place, not duplicated"
    assert "stale" not in first

    monkeypatch.setattr(os, "environ", {**os.environ, **_key("second")})
    assert seed.main(["--all", "--home", str(home)]) == 0
    assert (home / ".env").read_text().count("NOUS_API_KEY=second") == 1


def test_a_keyless_leg_is_a_loud_noop_not_a_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "environ", {k: v for k, v in os.environ.items() if k != "NOUS_API_KEY"})
    home = _homes(tmp_path)
    rc = seed.main(["--all", "--home", str(home)])
    assert rc == 0, "an agent leg without the secret must not red the hook"
    assert not (home / ".env").exists(), "no key, no file — the script never invents a secret"


def test_check_names_every_home_missing_the_key_and_greens_after_seed(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "environ", {**os.environ, **_key()})
    home = _homes(tmp_path)
    profiles = home / "profiles"

    rc = seed.main(["--check", "--all", "--home", str(home), "--profiles-parent", str(profiles)])
    assert rc == 1
    assert seed.main(["--all", "--home", str(home), "--profiles-parent", str(profiles)]) == 0
    assert seed.main(["--check", "--all", "--home", str(home), "--profiles-parent", str(profiles)]) == 0


def test_lanes_scope_touches_profiles_not_the_global_home(tmp_path, monkeypatch):
    """The host seam: the interactive default home's .env is left completely alone."""
    monkeypatch.setattr(os, "environ", {**os.environ, **_key()})
    home = _homes(tmp_path)
    (home / ".env").write_text("HUMAN_LINE=untouched\n")
    profiles = home / "profiles"

    rc = seed.main(["--lanes", "--home", str(home), "--profiles-parent", str(profiles)])
    assert rc == 0
    assert (home / ".env").read_text() == "HUMAN_LINE=untouched\n"
    assert "NOUS_API_KEY" in (profiles / "llgenie-planner" / ".env").read_text()


def test_values_are_never_printed(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(os, "environ", {**os.environ, **_key("super-secret-value")})
    home = _homes(tmp_path)
    seed.main(["--all", "--home", str(home)])
    seed.main(["--check", "--all", "--home", str(home)])
    out = capsys.readouterr()
    assert "super-secret-value" not in out.out + out.err, \
        "the report names homes and key NAMES — never values (AGENTS.md: no secrets printed)"


def test_the_seed_script_is_wired_into_the_image_and_the_host_target():
    """The hook is the image half; `make seed-hermes-profile-env` is the host half. A build
    that stopped staging the script or a Makefile that lost the target is drift the gate names."""
    dockerfile = (REPO / "containers" / "agent" / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY seed_profile_hermes_env.py /usr/local/bin/seed_profile_hermes_env.py" in dockerfile
    assert "/etc/profile.d/llgenie-hermes-profile-env.sh" in dockerfile
    agents_mk = (REPO / "mk" / "agents.mk").read_text(encoding="utf-8")
    assert "seed-hermes-profile-env:" in agents_mk
    assert "scripts/seed_profile_hermes_env.py" in agents_mk
    # the agent build stages the script next to the seam it imports (the Dockerfile COPY
    # reads the build context scripts/ — ci_images.py assembles that staging list)
    staged = (REPO / "scripts" / "ci_images.py").read_text(encoding="utf-8")
    assert "seed_profile_hermes_env.py" in staged
