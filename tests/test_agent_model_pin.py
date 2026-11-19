"""The bots' model pin is ONE snapshot, and drift is a finding (issue #405, change bot-model-1017).

Measured 2026-10-20 against https://inference-api.nousresearch.com/v1/models:

    deepseek/deepseek-v4-flash           canonical_slug deepseek/deepseek-v4-flash-20260423
    deepseek/deepseek-v4-flash-0731      the July 31, 2026 V4 Flash snapshot

Both answer 200, so no bot job could tell them apart. Every pin now names the `-0731` snapshot,
and `scripts/agent_model_pin.py` compares the two files that carry it — the Dockerfile's
`ARG HERMES_MODEL_ID` default and the install script's `MODEL_ID` default — with the single value
the module declares. The old test asserted the PREFIX, which any newer id satisfies: that is how
the drift shipped, so these tests pin the exact id and prove each drift is caught.
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


def _load():
    spec = importlib.util.spec_from_file_location("agent_model_pin", SPEC)
    assert spec is not None and spec.loader is not None, f"cannot load {SPEC}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_PIN = _load()


def _tree(tmp_path: Path, dockerfile: str | None = None, script: str | None = None) -> Path:
    """A copy of the two pin-carrying files, optionally with one of them rewritten."""
    root = tmp_path
    (root / "containers" / "agent").mkdir(parents=True, exist_ok=True)
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / DOCKERFILE.relative_to(REPO)).write_text(
        dockerfile if dockerfile is not None else DOCKERFILE.read_text()
    )
    (root / INSTALL_SCRIPT.relative_to(REPO)).write_text(
        script if script is not None else INSTALL_SCRIPT.read_text()
    )
    return root


def test_the_committed_pin_matches_the_one_declared_value():
    """The tree as committed carries the pinned snapshot in both places, and the gate is green."""
    # Given the repository as committed
    # When  the checker runs against this checkout
    bad = _PIN.findings(REPO) + _PIN.budget_findings(REPO) + _PIN.version_findings(REPO)

    # Then  every place agrees with the pin, and the declared pin is the 0731 snapshot
    assert bad == [], bad
    assert _PIN.MODEL_ID == "deepseek/deepseek-v4-flash-0731"
    assert _PIN.pin_in_dockerfile(REPO) == _PIN.MODEL_ID
    assert _PIN.pin_in_install_script(REPO) == _PIN.MODEL_ID


def test_a_stale_default_in_the_dockerfile_is_a_finding(tmp_path):
    """The previous snapshot in the Dockerfile is caught, and ONLY the Dockerfile is named."""
    # Given a Dockerfile whose ARG default is the older, unpinned id
    stale = DOCKERFILE.read_text().replace(
        f'ARG HERMES_MODEL_ID="{_PIN.MODEL_ID}"', 'ARG HERMES_MODEL_ID="deepseek/deepseek-v4.1-flash"'
    )
    root = _tree(tmp_path, dockerfile=stale)

    # When  the checker runs against that tree
    bad = _PIN.findings(root)

    # Then  it names the Dockerfile with the value it read, and blames nothing else
    assert len(bad) == 1, bad
    assert bad[0].startswith("containers/agent/Dockerfile:")
    assert "deepseek/deepseek-v4.1-flash" in bad[0]
    assert str(_PIN.MODEL_ID) in bad[0]


def test_a_different_snapshot_in_the_install_script_is_a_finding(tmp_path):
    """A NEWER snapshot in the install script is drift too — a prefix assert called this green."""
    # Given an install script pinning a different release of the same family
    script = INSTALL_SCRIPT.read_text().replace(
        f'MODEL_ID="${{HERMES_MODEL_ID:-{_PIN.MODEL_ID}}}"',
        'MODEL_ID="${HERMES_MODEL_ID:-deepseek/deepseek-v4.1-flash-1102}"',
    )
    assert "deepseek-v4.1-flash-1102" in script, "the fixture must actually carry the other id"
    root = _tree(tmp_path, script=script)

    # When  the checker runs against that tree
    bad = _PIN.findings(root)

    # Then  the install script is the finding, and the prefix match alone would not have caught it
    assert len(bad) == 1, bad
    assert bad[0].startswith("scripts/install_hermes_ci.sh:")
    assert "deepseek-v4.1-flash-1102" in bad[0]
    assert "deepseek/deepseek-v4.1-flash" in bad[0], (
        "the old prefix assert was satisfied by this drift — exactly the defect"
    )


def test_a_missing_pin_is_a_finding_not_a_skip(tmp_path):
    """A file that lost its pin line fails the check; it is never silently 'nothing to compare'."""
    # Given a Dockerfile with the pin line removed
    without = "\n".join(
        line for line in DOCKERFILE.read_text().splitlines()
        if "ARG HERMES_MODEL_ID" not in line
    ) + "\n"
    root = _tree(tmp_path, dockerfile=without)

    # When  the checker runs
    bad = _PIN.findings(root)

    # Then  it reports the absence
    assert bad and bad[0].startswith("containers/agent/Dockerfile:")
    assert "no model pin found" in bad[0]


def test_the_image_writes_and_asserts_the_alias_budget():
    """The alias carries the snapshot's budget, and the build asserts it landed."""
    # Given the install script and the Dockerfile as committed
    script = INSTALL_SCRIPT.read_text()
    dockerfile = DOCKERFILE.read_text()

    # When  both are read for the budget the alias needs
    # Then  the script writes max_tokens + context_window, and the build asserts all three keys
    for key, value in (("max_tokens", _PIN.MAX_TOKENS), ("context_window", _PIN.CONTEXT_WINDOW)):
        assert f'hermes config set "model.aliases.${{ALIAS}}.{key}" "{value}"' in script, key
        assert f"model.aliases.${{HERMES_ALIAS}}.{key}" in dockerfile, key
    assert _PIN.budget_findings(REPO) == []


def test_the_context_window_matches_the_published_length():
    """The budget is the snapshot's own: 1M window (published context_length), 16000-token replies."""
    # Given the values the pin declares
    # When  they are compared with what the catalogue publishes for this id
    # Then  the window is the published 1048576 and the reply budget sits below it
    assert _PIN.CONTEXT_WINDOW == 1048576
    assert 0 < _PIN.MAX_TOKENS < _PIN.CONTEXT_WINDOW
    assert _PIN.MAX_TOKENS == 16000


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


def test_the_pin_module_is_wired_to_its_target():
    """The module is not dead code: a make target runs `check`, and the same file is the source."""
    # Given the Makefile and the module
    makefile = makefiles_text()

    # When  the recipe behind the gate is read
    # Then  it runs this exact script's `check`, and `report` mirrors it
    assert "python3 scripts/agent_model_pin.py check" in makefile
    assert "python3 scripts/agent_model_pin.py report" in makefile
    assert shutil.which("python3"), "python3 is the interpreter every gate uses"


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
    root = _tree(tmp_path, dockerfile=DOCKERFILE.read_text().replace(
        'HERMES_VERSION="0.23.2"', 'HERMES_VERSION="0.19.0"'
    ))

    # When  the version referee runs
    bad = _PIN.version_findings(root)

    # Then  the Dockerfile is named, with the value it read
    assert any(_PIN.DOCKERFILE in f and "0.19.0" in f for f in bad), bad


def test_a_drifted_install_commit_is_a_finding(tmp_path):
    """A pin pointing at a different commit is drift, not 'close enough'."""
    root = _tree(tmp_path, dockerfile=DOCKERFILE.read_text().replace(
        _PIN.HERMES_INSTALL_COMMIT, "deadbeef"
    ))

    bad = _PIN.version_findings(root)
    assert any(_PIN.DOCKERFILE in f and "deadbeef" in f for f in bad), bad


def test_install_args_that_skip_the_commit_are_a_finding(tmp_path):
    """HERMES_INSTALL_ARGS must actually pass the commit to install.sh (issue #2932)."""
    # Given an ARGS list that dropped the --commit pin: install.sh would float on `stable`
    root = _tree(tmp_path, dockerfile=DOCKERFILE.read_text().replace(
        " --commit ${HERMES_INSTALL_COMMIT}", ""
    ))

    # When  the version referee runs
    bad = _PIN.version_findings(root)

    # Then  it names the ARGS line and what it refuses
    assert any("HERMES_INSTALL_ARGS" in f for f in bad), bad


def test_an_install_script_without_the_read_back_is_a_finding(tmp_path):
    """The version assert is part of the install step, not a comment about it."""
    root = _tree(tmp_path, script=INSTALL_SCRIPT.read_text().replace(
        "hermes --version", "command -v hermes"
    ))

    bad = _PIN.version_findings(root)
    assert any("never read back" in f for f in bad), bad
