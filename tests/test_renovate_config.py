"""The Renovate gate (issue #718): the config cannot grow a second merge path or edit a generated file.

`renovate.json` is acted on unattended, so the two properties this repository depends on are
checked by `make check-renovate` (inside `make ci-unit`) rather than trusted: automerge is
low-risk and single-path (CI's `auto-merge` job lands PRs), and vendored/generated files are
ignored. Each rule is proven on a fixture tree first, then the real config is asserted clean.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
from scripts import check_renovate as cr

CI_OK = (
    "name: CI\n"
    "on:\n"
    "  pull_request:\n"
    "    branches: [\"main\"]\n"
    "jobs:\n"
    "  engine-image:\n"
    "    runs-on: ubuntu-latest\n"
    "    steps:\n"
    "      - run: echo build\n"
)

BASE_RULE = {
    "matchManagers": ["pip_requirements", "pip-compile"],
    "matchUpdateTypes": ["patch", "pin", "digest"],
    "automerge": True,
    "automergeType": "pr",
    "platformAutomerge": False,
}


def _config(**overrides) -> dict:
    """The real config's shape, minimal, with one property changed per test."""
    cfg = {
        "$schema": "https://docs.renovatebot.com/renovate-schema.json",
        "extends": ["config:recommended"],
        "pip_requirements": {"fileMatch": ["(^|/)requirements\\.in$"]},
        "pip-compile": {"enabled": True, "fileMatch": ["(^|/)requirements\\.txt$"]},
        "packageRules": [
            dict(BASE_RULE),
            {"matchManagers": ["dockerfile"], "automerge": False},
            {"matchManagers": ["github-actions"], "enabled": False},
        ],
        "ignorePaths": list(cr.REQUIRED_IGNORES),
    }
    cfg.update(overrides)
    return cfg


def _tree(tmp_path: Path, cfg: dict | None = None, ci: str = CI_OK) -> Path:
    """A repository-shaped fixture: renovate.json, ci.yml and tools/requirements.in."""
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "requirements.in").write_text("numpy\n", encoding="utf-8")
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text(ci, encoding="utf-8")
    (tmp_path / "renovate.json").write_text(json.dumps(cfg or _config()), encoding="utf-8")
    return tmp_path


def test_the_real_config_passes(tmp_path):
    """The convention holds in the config that ships the gate."""

    # Given the real config
    # When  the gate runs over the real tree
    found = cr.findings(REPO)

    # Then  it reports nothing
    assert found == [], found


def test_top_level_automerge_is_refused(tmp_path):
    """`automerge: true` at the top merges every update type, including majors."""

    # Given a config that automerges everything
    root = _tree(tmp_path, _config(automerge=True))

    # When  the gate reads it
    found = cr.findings(root)

    # Then  it names the defect
    assert any("top-level" in f for f in found), found


def test_platform_automerge_is_a_finding(tmp_path):
    """Without `platformAutomerge: false` GitHub merges before the repository's checks land."""

    # Given an automerge rule that forgets `platformAutomerge: false`
    rule = dict(BASE_RULE)
    rule.pop("platformAutomerge")
    cfg = _config(packageRules=[rule, {"matchManagers": ["dockerfile"]},
                                {"matchManagers": ["github-actions"], "enabled": False}])
    root = _tree(tmp_path, cfg)

    # When  the gate reads it
    found = cr.findings(root)

    # Then  it refuses the second merge path
    assert any("platformAutomerge" in f for f in found), found


def test_automerge_of_a_minor_is_a_finding(tmp_path):
    """A minor numpy/gguf bump changes behaviour; it needs a human read."""

    # Given an automerge rule that also matches minors
    rule = dict(BASE_RULE, matchUpdateTypes=["patch", "minor"])
    cfg = _config(packageRules=[rule, {"matchManagers": ["dockerfile"]},
                                {"matchManagers": ["github-actions"], "enabled": False}])
    root = _tree(tmp_path, cfg)

    # When  the gate reads it
    found = cr.findings(root)

    # Then  it names the update type it refuses
    assert any("minor" in f for f in found), found


def test_a_missing_ignore_path_is_a_finding(tmp_path):
    """The generated engine Dockerfiles are written by make, never by a dependency bot."""

    # Given a config that forgot the generated engine paths
    root = _tree(tmp_path, _config(ignorePaths=["data/models.json"]))

    # When  the gate reads it
    found = cr.findings(root)

    # Then  it names each missing path
    assert sum("ignorePaths" in f for f in found) == 2, found


def test_github_actions_must_stay_disabled(tmp_path):
    """Actions move by `make update-actions` with a reviewed diff (docs/SECURITY.md)."""

    # Given a config where Renovate owns the Actions
    cfg = _config(packageRules=[dict(BASE_RULE), {"matchManagers": ["dockerfile"]}])
    root = _tree(tmp_path, cfg)

    # When  the gate reads it
    found = cr.findings(root)

    # Then  it refuses it
    assert any("GitHub Actions" in f for f in found), found


def test_pip_compile_must_be_enabled(tmp_path):
    """A Python bump edits the .in and recompiles; it never hand-edits the .txt."""

    # Given a config with pip-compile turned off
    cfg = _config(**{"pip-compile": {"enabled": False,
                                     "fileMatch": ["(^|/)requirements\\.txt$"]}})
    root = _tree(tmp_path, cfg)

    # When  the gate reads it
    found = cr.findings(root)

    # Then  it refuses it
    assert any("pip-compile" in f for f in found), found


def test_a_path_filtered_ci_fails_the_gate(tmp_path):
    """A base-image bump must reach the engine-image build, not skip it."""

    # Given a ci.yml whose pull_request is filtered by path
    ci = CI_OK.replace("  pull_request:\n", "  pull_request:\n    paths:\n      - \"scripts/**\"\n")
    root = _tree(tmp_path, None, ci)

    # When  the gate reads it
    found = cr.findings(root)

    # Then  it names the filter
    assert any("filters" in f for f in found), found


def test_report_prints_each_rule_and_its_automerge_state(tmp_path, capsys):
    """The report is what a reader uses to see which rule merges what."""

    # Given the fixture tree
    root = _tree(tmp_path)

    # When  the report runs
    rc = cr.report(root)

    # Then  it prints the rules and exits 0 on a clean config
    out = capsys.readouterr().out
    assert "managers=pip_requirements,pip-compile automerge=True" in out
    assert "ignorePaths:" in out
    assert rc == 0


def test_the_compiled_txt_must_not_be_a_source(tmp_path):
    """Only `requirements*.in` may be edited; the `.txt` is regenerated by pip-compile."""

    # Given a config whose pip_requirements manager also treats the COMPILED file as a source
    cfg = _config(**{"pip_requirements": {"fileMatch": ["(^|/)requirements\\.in$",
                                                        "(^|/)requirements\\.txt$"]}})
    root = _tree(tmp_path, cfg)

    # When  the gate reads it
    found = cr.findings(root)

    # Then  it refuses: a compiled file is generated, not validated and not hand-edited
    assert any("COMPILED file a source" in f for f in found), found


def test_pip_requirements_must_name_the_in_source(tmp_path):
    """A `pip_requirements` manager with no `.in` source has nothing legitimate to edit."""

    # Given a config whose Python source match names no `.in` file
    cfg = _config(**{"pip_requirements": {"fileMatch": ["(^|/)deps\\.cfg$"]}})
    root = _tree(tmp_path, cfg)

    # When  the gate reads it
    found = cr.findings(root)

    # Then  it names the missing source
    assert any("does not fileMatch a requirements*.in" in f for f in found), found
