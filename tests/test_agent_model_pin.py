"""The bots' model pin is ONE snapshot, and drift is a finding (issue #405, change bot-model-1017).

Measured 2026-10-20 against https://inference-api.nousresearch.com/v1/models:

    deepseek/deepseek-v4.1-flash         canonical_slug deepseek/deepseek-v4.1-flash-20260910
    deepseek/deepseek-v4.1-flash-1017    canonical_slug deepseek/deepseek-v4.1-flash-20261017

Both answer 200, so no bot job could tell them apart. Every pin now names the `-1017` snapshot,
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
    bad = _PIN.findings(REPO) + _PIN.budget_findings(REPO)

    # Then  every place agrees with the pin, and the declared pin is the 1017 snapshot
    assert bad == [], bad
    assert _PIN.MODEL_ID == "deepseek/deepseek-v4.1-flash-1017"
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
    # Given the Makefile
    makefile = (REPO / "Makefile").read_text()

    # When  the ci-unit recipe and the .PHONY block are read
    ci_unit = re.search(r"^ci-unit:.*?(?=^\S)", makefile, re.MULTILINE | re.DOTALL)
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
    makefile = (REPO / "Makefile").read_text()

    # When  the recipe behind the gate is read
    # Then  it runs this exact script's `check`, and `report` mirrors it
    assert "python3 scripts/agent_model_pin.py check" in makefile
    assert "python3 scripts/agent_model_pin.py report" in makefile
    assert shutil.which("python3"), "python3 is the interpreter every gate uses"
