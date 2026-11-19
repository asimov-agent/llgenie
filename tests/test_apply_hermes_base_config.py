"""The base-config seam lands ONE chain into many homes (issue #2929).

`agents/hermes-base-config.yaml` is the single home of the bots' model chain;
`scripts/apply_hermes_base_config.py` merges its OWNED keys (`model.default`,
`model.aliases`, `fallback_providers`) into the Hermes global home config.yaml and into every
llgenie lane profile's config.yaml — host (`make apply-hermes-base-config`) and image
(`install_hermes_ci.sh` + `provision_agent_profiles.py`) run this same code, which is the whole
point: a lane and the image resolve the identical chain.

OWNED-key semantics these tests prove: `model.default` and `fallback_providers` are REPLACED
(order is the chain), `model.aliases` is MERGED (the base's aliases overwrite identically-named
ones, foreign aliases survive — the file owns its keys, not the whole config), everything else
in the target config survives untouched, a foreign profile home under the same parent is never
touched, and the read-back (`--check`, `drift`) names every missing or altered owned key.
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

import scripts.apply_hermes_base_config as seam  # noqa: E402  (the real seam, never a copy)

REPO = Path(__file__).resolve().parent.parent
BASE_TEXT = (REPO / seam.BASE_CONFIG).read_text(encoding="utf-8")


def _root(tmp_path: Path) -> Path:
    """A fixture repo whose ONE home is the real committed base config."""
    agents = tmp_path / "agents"
    agents.mkdir(parents=True)
    (agents / "hermes-base-config.yaml").write_text(BASE_TEXT)
    return tmp_path


def _base():
    return yaml.safe_load(BASE_TEXT)


# ---------------------------------------------------------------------------
# the ONE home itself
# ---------------------------------------------------------------------------

def test_load_base_reads_the_owned_structure(tmp_path):
    root = _root(tmp_path)
    base = seam.load_base(root)
    assert base["model"]["default"] == "meituan/longcat-2.5:free"
    assert "nous-deepseek" in base["model"]["aliases"]
    assert base["fallback_providers"][-1]["model"] == "deepseek/deepseek-v4-flash-0731"


def test_a_base_without_model_aliases_fails_loudly(tmp_path):
    """A malformed ONE home is exit-2 loud, never a partial merge. The fixture carries the full
    route block so the aliases check is what trips (route keys are owned too — issue #2929)."""
    agents = tmp_path / "agents"
    agents.mkdir(parents=True)
    (agents / "hermes-base-config.yaml").write_text(
        "model:\n  default: nous-longcat\n  provider: custom\n"
        "  base_url: https://inference-api.nousresearch.com/v1\n"
        "  key_env: NOUS_API_KEY\n  max_tokens: 16000\n  context_window: 1048576\n"
        "fallback_providers:\n  - provider: custom\n    model: x\n"
    )
    try:
        seam.load_base(tmp_path)
        raise AssertionError("expected SystemExit for a base without aliases")
    except SystemExit as exc:
        assert "model.aliases" in str(exc)


def test_a_missing_base_fails_loudly(tmp_path):
    try:
        seam.load_base(tmp_path)
        raise AssertionError("expected SystemExit for a missing base config")
    except SystemExit as exc:
        assert "hermes-base-config.yaml" in str(exc)


# ---------------------------------------------------------------------------
# apply: OWNED keys land, everything else survives
# ---------------------------------------------------------------------------

def test_apply_writes_the_owned_keys_into_an_empty_home(tmp_path):
    home = tmp_path / "home"
    seam.apply(home, _base())
    data = yaml.safe_load((home / "config.yaml").read_text())
    assert data["model"]["default"] == "meituan/longcat-2.5:free"
    assert set(data["model"]["aliases"]) >= set(_base()["model"]["aliases"])
    assert data["fallback_providers"] == _base()["fallback_providers"]


def test_apply_keeps_foreign_config_and_foreign_aliases(tmp_path):
    """The file owns its keys — not the profile's whole config, not other providers' aliases."""
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.yaml").write_text(yaml.safe_dump({
        "model": {"default": "old-model", "aliases": {"openai-gpt": {"model": "gpt-4o"}}},
        "fallback_providers": [{"provider": "openrouter", "model": "x"}],
        "terminal": {"backend": "local"},
    }))
    seam.apply(home, _base())
    data = yaml.safe_load((home / "config.yaml").read_text())
    assert data["model"]["default"] == "meituan/longcat-2.5:free", "default is REPLACED"
    assert data["fallback_providers"] == _base()["fallback_providers"], "the chain order is REPLACED"
    assert data["model"]["aliases"]["openai-gpt"]["model"] == "gpt-4o", "foreign aliases SURVIVE"
    assert data["model"]["aliases"]["nous-longcat"]["max_tokens"] == 16000
    assert data["terminal"]["backend"] == "local", "unrelated config survives untouched"


def test_apply_is_idempotent(tmp_path):
    home = tmp_path / "home"
    seam.apply(home, _base())
    first = (home / "config.yaml").read_text()
    seam.apply(home, _base())
    assert (home / "config.yaml").read_text() == first


def test_drift_is_empty_after_apply_and_names_every_absence(tmp_path):
    home = tmp_path / "home"
    base = _base()
    seam.apply(home, base)
    assert seam.drift(home, base) == []

    # strip the chain back out: every owned key missing is named, one line each
    (home / "config.yaml").write_text(yaml.safe_dump({"model": {"aliases": {}}}))
    findings = seam.drift(home, base)
    assert any("model.default" in f for f in findings), findings
    assert any("nous-longcat" in f for f in findings), findings
    assert any("fallback_providers" in f for f in findings), findings


def test_a_reordered_alias_is_drift_not_a_prefix_match(tmp_path):
    """History (#405): a family-prefix match hid a wrong snapshot. Exact compare catches it."""
    home = tmp_path / "home"
    base = _base()
    seam.apply(home, base)
    data = yaml.safe_load((home / "config.yaml").read_text())
    data["model"]["aliases"]["nous-deepseek"]["model"] = "deepseek/deepseek-v4-flash"  # the April id
    (home / "config.yaml").write_text(yaml.safe_dump(data))
    findings = seam.drift(home, base)
    assert any("nous-deepseek differs" in f for f in findings), findings


# ---------------------------------------------------------------------------
# profile scoping + CLI
# ---------------------------------------------------------------------------

def test_profile_homes_touch_only_llgenie_lanes(tmp_path):
    parent = tmp_path / "profiles"
    for name in ("llgenie-planner", "llgenie-architect", "tll-other", "personal"):
        (parent / name).mkdir(parents=True)
    homes = seam.profile_homes(parent)
    assert sorted(p.name for p in homes) == ["llgenie-architect", "llgenie-planner"]


def test_cli_apply_all_lands_global_and_every_lane_and_check_is_green(tmp_path):
    root = _root(tmp_path)
    home = tmp_path / "hermes-home"
    profiles = home / "profiles"
    for name in ("llgenie-planner", "llgenie-security"):
        (profiles / name).mkdir(parents=True)

    rc = seam.main(["--home", str(home), "--profiles-parent", str(profiles), "--all",
                    "--root", str(root)])
    assert rc == 0
    assert (home / "config.yaml").is_file()
    for name in ("llgenie-planner", "llgenie-security"):
        data = yaml.safe_load((profiles / name / "config.yaml").read_text())
        assert data["model"]["default"] == "meituan/longcat-2.5:free"
        assert data["fallback_providers"][-1]["model"] == "deepseek/deepseek-v4-flash-0731"

    rc = seam.main(["--check", "--home", str(home), "--profiles-parent", str(profiles),
                    "--all", "--root", str(root)])
    assert rc == 0

    # break one lane: --check reds and names it
    data = yaml.safe_load((profiles / "llgenie-security" / "config.yaml").read_text())
    data["fallback_providers"] = []
    (profiles / "llgenie-security" / "config.yaml").write_text(yaml.safe_dump(data))
    rc = seam.main(["--check", "--home", str(home), "--profiles-parent", str(profiles),
                    "--all", "--root", str(root)])
    assert rc == 1


def test_lanes_scope_touches_profiles_not_the_global_home(tmp_path):
    """--lanes is the host target's scope: llgenie profiles get the chain, the interactive
    default home's own config.yaml is left completely alone (issue #2929)."""
    import yaml  # noqa: PLC0415
    root = _root(tmp_path)
    home = tmp_path / "hermes-home"
    profiles = home / "profiles"
    (profiles / "llgenie-planner").mkdir(parents=True)
    (home / "config.yaml").write_text(yaml.safe_dump(
        {"model": {"default": "human-interactive-model"}}))

    rc = seam.main(["--lanes", "--home", str(home), "--profiles-parent", str(profiles),
                    "--root", str(root)])
    assert rc == 0
    data = yaml.safe_load((profiles / "llgenie-planner" / "config.yaml").read_text())
    assert data["model"]["default"] == "meituan/longcat-2.5:free"
    untouched = yaml.safe_load((home / "config.yaml").read_text())
    assert untouched == {"model": {"default": "human-interactive-model"}}, \
        "--lanes must NOT rewrite the interactive default home"


def test_the_base_config_is_the_committed_chain(tmp_path):
    """The ONE home as committed: free models first (LongCat primary), the paid snapshot LAST."""
    base = yaml.safe_load(BASE_TEXT)
    aliases = base["model"]["aliases"]
    assert base["model"]["default"] == "meituan/longcat-2.5:free"
    assert aliases["nous-longcat"]["model"] == "meituan/longcat-2.5:free"
    order = [e["model"] for e in base["fallback_providers"]]
    assert order[-1] == "deepseek/deepseek-v4-flash-0731"
    assert all(m.endswith(":free") for m in order[:-1]), order
