#!/usr/bin/env python3
"""No instruction file may embed a literal home path (issue #2145)."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import check_agent_profiles as guard  # noqa: E402  (the real gate, never a copy)


def test_the_committed_tree_carries_no_literal_home_path():
    """The repo's own agents/**/*.md must be sweep-clean: `$HOME`, never a concrete `/home/<user>`.

    `scripts/check_agent_profiles.py`'s `home-path-literal` finding is the adapter; the committed
    tree is the fixture that must stay green, so a reintroduction reds here AND in `make
    check-agent-profiles` (issue #2145 acceptance criterion 1).
    """
    items = guard._home_path_findings(REPO / "agents", REPO)
    assert items == [], items


def test_a_reintroduced_literal_is_a_finding(tmp_path):
    """A one-line `/home/asimov` in an instruction file must red the gate, naming the file."""
    agents = tmp_path / "agents"
    (agents / "llgenie-test").mkdir(parents=True)
    skill = agents / "llgenie-test" / "SKILL.md"
    skill.write_text("# test\n```bash\ngit -C /home/asimov/repository/git/llgenie fetch origin main\n```\n",
                     encoding="utf-8")
    items = guard._home_path_findings(agents, tmp_path)
    keys = [item["key"] for item in items]
    assert "home-path-literal" in keys, items
    hit = next(item for item in items if item["key"] == "home-path-literal")
    assert "SKILL.md" in hit["where"]
    assert "/home/asimov" in hit["detail"]


def test_documented_carveouts_and_placeholders_do_not_red(tmp_path):
    """The carve-out is real and must not red: `%h`/systemd, a Docker image's `/home/agent`, a
    placeholder `/home/<user>`, and the `scripts/*.py` surface are all allowed (issue #2145)."""
    agents = tmp_path / "agents"
    (agents / "llgenie-test").mkdir(parents=True)
    for name, body in {
        "systemd.md": "# unit\n`EnvironmentFile=%h/.hermes/hermes.env` — the native systemd `%h` form, never `$HOME` here.\n",  # noqa: E501
        "container.md": "# image\n`RUN useradd -r -m -d /home/agent -s /bin/bash agent` is the image's user.\n",
        "placeholder.md": "# placeholder\nWrite `$HOME`, never `/home/<user>`; recipe paths read `/home/user/...`.\n",
    }.items():
        (agents / "llgenie-test" / name).write_text(body, encoding="utf-8")
    skill = agents / "llgenie-test" / "SKILL.md"
    skill.write_text("# ok\n```python\nimport pathlib\nreturn str(pathlib.Path.home())\n```\n",
                     encoding="utf-8")  # scripts/*.py-style literal is the carve-out, not an .md finding
    items = guard._home_path_findings(agents, tmp_path)
    assert items == [], items


def test_a_script_py_literal_is_not_scanned(tmp_path):
    """`scripts/*.py` is deliberately excluded — a Python literal needs a real path or
    `pathlib.Path.home()`, and `$HOME` there never expands (issue #2145 scope note)."""
    root = tmp_path
    agents = root / "agents"
    (agents / "llgenie-test" / "scripts").mkdir(parents=True)
    (agents / "llgenie-test" / "scripts" / "probe.py").write_text(
        'REPO_PATH = "/home/asimov/repository/git/llgenie"\n', encoding="utf-8")
    assert guard._home_path_findings(agents, root) == []


def test_a_systemd_unit_file_is_not_an_md_surface(tmp_path):
    """The one carve-out is a real context that never expands `$HOME`. A systemd unit is a
    `.service` file, never a `.md` instruction, so this gate cannot red it by construction."""
    agents = tmp_path / "agents"
    (agents / "llgenie-test").mkdir(parents=True)
    (agents / "llgenie-test" / "hermes.service").write_text(
        "EnvironmentFile=/home/asimov/.hermes/profiles/hermes.env\n", encoding="utf-8")
    assert guard._home_path_findings(agents, tmp_path) == []


def test_an_executed_shell_literal_is_a_finding(tmp_path):
    """An executed `agents/**/*.sh` line carrying a literal home path must red the gate too —
    the #2145 gate is no longer .md-only (issue #2436)."""
    agents = tmp_path / "agents"
    (agents / "llgenie-test" / "scripts").mkdir(parents=True)
    script = agents / "llgenie-test" / "scripts" / "replay.sh"
    script.write_text("#!/usr/bin/env bash\n"
                      '[ -f "$RESOLVER" ] || RESOLVER=/home/asimov/.hermes/profiles/x/resolve.py\n',
                      encoding="utf-8")
    items = guard._home_path_findings(agents, tmp_path)
    keys = [item["key"] for item in items]
    assert "home-path-literal" in keys, items
    hit = next(item for item in items if item["key"] == "home-path-literal")
    assert "replay.sh" in hit["where"]
    assert "/home/asimov" in hit["detail"]


def test_a_shell_comment_recounting_a_past_defect_does_not_red(tmp_path):
    """A `.sh` COMMENT keeps its absolute path (skill-script-hygiene.md: a comment recounting a
    past defect is not shipped behaviour); issue #2436 ensures only executed lines are scanned."""
    agents = tmp_path / "agents"
    (agents / "llgenie-test" / "scripts").mkdir(parents=True)
    script = agents / "llgenie-test" / "scripts" / "salvage.sh"
    script.write_text("#!/usr/bin/env bash\n"
                      "#   the sibling pinned /home/asimov/... and would have failed on every runner.\n",
                      encoding="utf-8")
    assert guard._home_path_findings(agents, tmp_path) == []
