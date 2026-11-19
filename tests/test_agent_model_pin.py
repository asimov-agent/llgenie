"""The bots' model CHAIN has ONE home, and drift from it is a finding (issue #405 → #2929).

History: `deepseek/deepseek-v4-flash` and its `-0731` snapshot both answered 200 at
https://inference-api.nousresearch.com/v1/models, and a PREFIX assert let the drift ship
(issue #405). The chain now lives in `agents/hermes-base-config.yaml` — Nous FREE models
first (LongCat primary), the free entries as the ordered fallbacks, the paid
`deepseek/deepseek-v4-flash-0731` LAST — and `scripts/agent_model_pin.py` referees the file,
the seams that install it, the budgets, the wiring, and the absence of any `-m` bot call.
These tests prove each drift class is caught by name, not by prefix.
"""
from __future__ import annotations

import importlib.util
import re
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
from conftest import ci_unit_expanded, makefiles_text  # noqa: E402  (include-resolving reader + ci-unit seam reader, issue #2675)
SPEC = REPO / "scripts" / "agent_model_pin.py"
DOCKERFILE = REPO / "containers" / "agent" / "Dockerfile"
INSTALL_SCRIPT = REPO / "scripts" / "install_hermes_ci.sh"
BASE_CONFIG = REPO / "agents" / "hermes-base-config.yaml"
PROVISION = REPO / "scripts" / "provision_agent_profiles.py"


def _load():
    spec = importlib.util.spec_from_file_location("agent_model_pin", SPEC)
    assert spec is not None and spec.loader is not None, f"cannot load {SPEC}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_PIN = _load()

# every file the referee reads, so a fixture tree is complete (a missing input must be a finding,
# never a silent skip — the fixture must therefore carry the untouched files too)
_DEFAULTS = {
    "containers/agent/Dockerfile": DOCKERFILE,
    "scripts/install_hermes_ci.sh": INSTALL_SCRIPT,
    "scripts/provision_agent_profiles.py": PROVISION,
    "scripts/fix_loop.sh": REPO / "scripts" / "fix_loop.sh",
    "agents/hermes-base-config.yaml": BASE_CONFIG,
    "agents/manifest.json": REPO / "agents" / "manifest.json",
    "Makefile": REPO / "Makefile",
    "mk/bots.mk": REPO / "mk" / "bots.mk",
    "mk/agents.mk": REPO / "mk" / "agents.mk",
    "mk/engines.mk": REPO / "mk" / "engines.mk",
}


def _tree(tmp_path: Path, **overrides: str | None) -> Path:
    """A copy of every referee-read file, with the named ones rewritten or deleted (None)."""
    for rel, src in _DEFAULTS.items():
        text = overrides[rel] if rel in overrides else src.read_text(encoding="utf-8")
        dest = tmp_path / rel
        if text is None:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text)
    return tmp_path


def _chain_text() -> str:
    return BASE_CONFIG.read_text(encoding="utf-8")


def test_the_committed_chain_is_green_and_declared_once():
    """The tree as committed carries the free-first / paid-last chain, and the gate is green."""
    # Given the repository as committed
    # When  the referee runs against this checkout
    bad = _PIN.findings(REPO)

    # Then  nothing drifts, and the declared policy is the owner's chain
    assert bad == [], bad
    assert _PIN.PRIMARY_ALIAS == "nous-longcat"
    assert _PIN.PRIMARY_MODEL == "meituan/longcat-2.5:free"
    assert _PIN.LAST_MODEL == "deepseek/deepseek-v4-flash-0731"
    base = _PIN.load_base(REPO)
    assert base["model"]["default"] == _PIN.PRIMARY_MODEL


def test_the_paid_fallback_stays_last(tmp_path):
    """A different last entry is drift, and it is named with the value the file actually says."""
    # Given a chain whose last fallback is some other model
    chain = _chain_text().replace(
        "  - provider: custom\n    model: deepseek/deepseek-v4-flash-0731",
        "  - provider: custom\n    model: anthropic/claude-sonnet-4.5",
    )
    assert "claude-sonnet-4.5" in chain
    root = _tree(tmp_path, **{"agents/hermes-base-config.yaml": chain})

    # When  the referee runs
    bad = _PIN.chain_findings(root)

    # Then  the base config is named, the expected LAST model is named, and the substitute is quoted
    assert bad, bad
    assert all(f.startswith("agents/hermes-base-config.yaml:") for f in bad), bad
    assert any(_PIN.LAST_MODEL in f and "claude-sonnet-4.5" in f for f in bad), bad


def test_a_paid_model_before_the_last_slot_is_a_finding(tmp_path):
    """Only the LAST entry may be paid: the paid snapshot promoted early is caught."""
    # Given the paid model repeated at the fourth position
    chain = _chain_text().replace(
        "  - provider: custom\n    model: upstage/solar-mini4:free",
        "  - provider: custom\n    model: deepseek/deepseek-v4-flash-0731",
    )
    root = _tree(tmp_path, **{"agents/hermes-base-config.yaml": chain})

    # When  the referee runs
    bad = _PIN.chain_findings(root)

    # Then  the early paid entry is named outright
    assert any("before the last position" in f for f in bad), bad
    assert any("repeats a model" in f for f in bad), bad


def test_a_missing_base_config_is_a_finding_not_a_skip(tmp_path):
    """A tree with no home for the chain fails the gate; it is never 'nothing to compare'."""
    root = _tree(tmp_path, **{"agents/hermes-base-config.yaml": None})
    bad = _PIN.chain_findings(root)
    assert bad and "no home" in bad[0], bad


def test_the_install_and_provision_seams_must_be_wired(tmp_path):
    """The chain lands through the seams; a seam that stopped calling them is drift."""
    # Given an install script and a provisioner that dropped the apply seam
    root = _tree(
        tmp_path,
        **{
            "scripts/install_hermes_ci.sh": INSTALL_SCRIPT.read_text().replace(
                "apply_hermes_base_config.py", "something-else.sh"
            ),
            "scripts/provision_agent_profiles.py": PROVISION.read_text().replace(
                "apply_hermes_base_config", "something_else"
            ),
        },
    )

    # When  the referee runs
    bad = _PIN.chain_findings(root)

    # Then  both seams are named
    assert any("scripts/install_hermes_ci.sh" in f and "no installer" in f for f in bad), bad
    assert any("provision_agent_profiles.py" in f for f in bad), bad


def test_a_single_pin_build_arg_is_a_finding(tmp_path):
    """The single-model build ARGs are dead: resurrecting one names the ARG (issue #2929)."""
    root = _tree(
        tmp_path,
        **{"containers/agent/Dockerfile": DOCKERFILE.read_text() + '\nARG HERMES_MODEL_ID="x"\n'},
    )
    bad = _PIN.chain_findings(root)
    assert any("HERMES_MODEL_ID" in f and "ONE home" in f for f in bad), bad


def test_an_alias_in_the_default_slot_is_a_finding(tmp_path):
    """Hermes profile routing sends model.default straight to the endpoint; an alias there 404s
    (measured against Hermes 0.23.2), so putting the ALIAS back is drift the referee names."""
    chain = _chain_text().replace(
        "  default: meituan/longcat-2.5:free", "  default: nous-longcat",
    )
    assert "default: nous-longcat" in chain
    root = _tree(tmp_path, **{"agents/hermes-base-config.yaml": chain})
    bad = _PIN.chain_findings(root)
    assert any("model.default" in f and "404" in f for f in bad), bad


def test_the_default_route_must_carry_base_url(tmp_path):
    """A profile run resolves its config as its WHOLE route: dropping the endpoint from the
    chain home is drift, because the installed profiles inherit it."""
    chain = _chain_text().replace(
        "  default: meituan/longcat-2.5:free\n  provider: custom\n"
        "  base_url: https://inference-api.nousresearch.com/v1\n",
        "  default: meituan/longcat-2.5:free\n  provider: custom\n",
    )
    root = _tree(tmp_path, **{"agents/hermes-base-config.yaml": chain})
    bad = _PIN.chain_findings(root)
    assert any("model.base_url" in f for f in bad), bad


def test_a_fallback_entry_without_its_custom_route_is_a_finding(tmp_path):
    """A hop resolves the fallback ENTRY (provider + base_url + key_env), not the profile —
    Hermes's bundled nous provider is OAuth-only and a bare entry is silently skipped."""
    chain = _chain_text().replace(
        "  - provider: custom\n    model: deepseek/deepseek-v4-flash-0731\n"
        "    base_url: https://inference-api.nousresearch.com/v1\n    key_env: NOUS_API_KEY\n",
        "  - provider: nous\n    model: deepseek/deepseek-v4-flash-0731\n",
    )
    root = _tree(tmp_path, **{"agents/hermes-base-config.yaml": chain})
    bad = _PIN.chain_findings(root)
    assert any("fallback_providers[4]" in f and "custom" in f for f in bad), bad
    assert any("fallback_providers[4].base_url" in f for f in bad), bad


def test_the_profile_env_seed_seam_is_wired(tmp_path):
    """Profile mode reads key_env from the PROFILE's OWN .env (measured, Hermes 0.23.2): the
    image seeds it at every leg start through the same script the host runs; dropping the hook
    is drift (#2929)."""
    root = _tree(tmp_path, **{"containers/agent/Dockerfile": DOCKERFILE.read_text().replace(
        "seed_profile_hermes_env.py", "something_else.py",
    )})
    bad = _PIN.chain_findings(root)
    assert any("seed_profile_hermes_env.py" in f and "profile .env" in f for f in bad), bad


def test_a_model_flag_on_a_bot_call_is_a_finding(tmp_path):
    """Bots load the chain through their profile; a `-m` call site is a finding naming the file."""
    root = _tree(
        tmp_path,
        **{"mk/bots.mk": (REPO / "mk" / "bots.mk").read_text()
           + "\n\t$(HERMES_BIN) -z 'x' -m nous-longcat -p llgenie-issue-triage\n"},
    )
    bad = _PIN.chain_findings(root)
    assert any("mk/bots.mk" in f and "names a model" in f for f in bad), bad


def test_every_alias_carries_the_written_budget():
    """Every alias in the ONE home declares max_tokens 16000 and a positive window (issue #2319)."""
    base = _PIN.load_base(REPO)
    for name, entry in base["model"]["aliases"].items():
        assert entry["max_tokens"] == _PIN.MAX_TOKENS, name
        assert 0 < entry["max_tokens"] < entry["context_window"], name
    assert base["model"]["aliases"][_PIN.PRIMARY_ALIAS]["context_window"] == 1048576


def test_an_alias_without_its_budget_is_a_finding(tmp_path):
    """A chain entry that lost its budget is drift, named per alias."""
    chain = _chain_text().replace(
        "    nous-hy4:\n      model: tencent/hy4-flash:free\n      provider: custom\n"
        "      base_url: https://inference-api.nousresearch.com/v1\n"
        "      key_env: NOUS_API_KEY\n      max_tokens: 16000",
        "    nous-hy4:\n      model: tencent/hy4-flash:free\n      provider: custom\n"
        "      base_url: https://inference-api.nousresearch.com/v1\n"
        "      key_env: NOUS_API_KEY\n      max_tokens: 128",
    )
    assert "max_tokens: 128" in chain
    root = _tree(tmp_path, **{"agents/hermes-base-config.yaml": chain})
    bad = _PIN.chain_findings(root)
    assert any("nous-hy4.max_tokens" in f and "16000" in f for f in bad), bad


def test_ci_unit_runs_the_check_and_the_targets_are_phony():
    """A gate no CI job executes is a defect: `ci-unit` must run it, and both targets are .PHONY."""
    # Given the Makefile (the top + its mk/*.mk includes — check-agent-model lives behind one)
    makefile = makefiles_text()

    # When  the ci-unit recipe and the .PHONY block are read
    ci_unit = re.search(r"^ci-unit:.*?(?=^\S)", ci_unit_expanded(), re.MULTILINE | re.DOTALL)
    phony = re.search(r"^\.PHONY:.*?(?=^\S)", makefile, re.MULTILINE | re.DOTALL)
    assert ci_unit and phony

    # Then  ci-unit runs the check, and neither target can be shadowed by a file of its name
    assert "$(MAKE) check-agent-model" in ci_unit.group(0)
    for target in ("check-agent-model", "model-pin-report"):
        assert re.search(rf"^{target}:", makefile, re.MULTILINE), f"{target} is not a target"
        assert re.search(rf"\b{target}\b", phony.group(0)), f"{target} is not .PHONY (issue #392)"


def test_the_chain_module_is_wired_to_its_target():
    """The module is not dead code: a make target runs `check`, and the same file is the source."""
    # Given the Makefile and the module
    makefile = makefiles_text()

    # When  the recipe behind the gate is read
    # Then  it runs this exact script's `check`, and `report` mirrors it (both through $(PY),
    # the project python — the referee reads the chain through PyYAML like Hermes does, #2929)
    assert "$(PY) scripts/agent_model_pin.py check" in makefile
    assert "$(PY) scripts/agent_model_pin.py report" in makefile
    assert shutil.which("python3"), "python3 is the interpreter the rest of the gates use"


# ---------------------------------------------------------------------------
# The Hermes release the image installs (issue #2932)
# ---------------------------------------------------------------------------

def test_the_committed_hermes_version_pin_is_green():
    """The tree as committed names the Hermes release, its commit, and the read-back."""
    # Given the repository as committed
    # When  the version referee runs against this checkout
    bad = _PIN.version_findings(REPO)

    # Then  it is green, and the declared pin is the v0.23.2 peeled commit
    assert bad == [], bad
    assert _PIN.HERMES_VERSION == "0.23.2"
    assert _PIN.HERMES_INSTALL_COMMIT == "ae2a81ccc00e9b7c06301523e5bb09608397149c"


def test_the_dockerfile_names_the_release_the_commit_and_forwards_it():
    """The install channel is named at the ARG block AND reaches the install step."""
    text = DOCKERFILE.read_text()
    assert 'ARG HERMES_VERSION="0.23.2"' in text
    assert 'ARG HERMES_INSTALL_COMMIT="ae2a81ccc00e9b7c06301523e5bb09608397149c"' in text
    # The pin reaches install.sh: ARGS carries `--commit ${HERMES_INSTALL_COMMIT}`…
    assert "--commit ${HERMES_INSTALL_COMMIT}" in text
    # …and the version reaches the install step, where the read-back compares against it.
    assert "HERMES_VERSION=${HERMES_VERSION}" in text


def test_the_install_script_reads_the_installed_version_back():
    """install.sh compares the installed CLI against the pin; drift exits, never warns."""
    script = INSTALL_SCRIPT.read_text()
    assert 'HERMES_VERSION="${HERMES_VERSION:-0.23.2}"' in script
    assert "hermes --version" in script
    assert '!= "$HERMES_VERSION"' in script


def test_a_drifted_hermes_version_is_a_finding(tmp_path):
    """A Dockerfile installing a different Hermes is a finding naming file and value."""
    # Given a Dockerfile installing an older release
    root = _tree(tmp_path, **{"containers/agent/Dockerfile": DOCKERFILE.read_text().replace(
        'HERMES_VERSION="0.23.2"', 'HERMES_VERSION="0.19.0"'
    )})

    # When  the version referee runs
    bad = _PIN.version_findings(root)

    # Then  the Dockerfile is named, with the value it read
    assert any(_PIN.DOCKERFILE in f and "0.19.0" in f for f in bad), bad


def test_a_drifted_install_commit_is_a_finding(tmp_path):
    """A pin pointing at a different commit is drift, not 'close enough'."""
    root = _tree(tmp_path, **{"containers/agent/Dockerfile": DOCKERFILE.read_text().replace(
        _PIN.HERMES_INSTALL_COMMIT, "deadbeef"
    )})

    bad = _PIN.version_findings(root)
    assert any(_PIN.DOCKERFILE in f and "deadbeef" in f for f in bad), bad


def test_install_args_that_skip_the_commit_are_a_finding(tmp_path):
    """HERMES_INSTALL_ARGS must actually pass the commit to install.sh (issue #2932)."""
    # Given an ARGS list that dropped the --commit pin: install.sh would float on `stable`
    root = _tree(tmp_path, **{"containers/agent/Dockerfile": DOCKERFILE.read_text().replace(
        " --commit ${HERMES_INSTALL_COMMIT}", ""
    )})

    # When  the version referee runs
    bad = _PIN.version_findings(root)

    # Then  it names the ARGS line and what it refuses
    assert any("HERMES_INSTALL_ARGS" in f for f in bad), bad


def test_an_install_script_without_the_read_back_is_a_finding(tmp_path):
    """The version assert is part of the install step, not a comment about it."""
    root = _tree(tmp_path, **{"scripts/install_hermes_ci.sh": INSTALL_SCRIPT.read_text().replace(
        "hermes --version", "command -v hermes"
    )})

    bad = _PIN.version_findings(root)
    assert any("never read back" in f for f in bad), bad
