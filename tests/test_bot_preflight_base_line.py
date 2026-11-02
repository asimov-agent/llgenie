"""The bot preflight records the BASE beside the AGENTS line (issue #845 criterion 2).

The defect #845 names is that the base sha a worktree/PR was cut from is recorded
nowhere, so a lane spawned from a parked checkout carried the wrong base
invisibly. This pins the record: `render()` MUST carry `BASE: <sha> (==
origin/main at open)` directly beside the existing `AGENTS:` line, so a reviewer
can check the base without consulting the branch.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import bot_preflight as bp  # noqa: E402


def test_the_record_carries_the_base_line_beside_the_agents_line(tmp_path):
    """A record rendered for PR-open names the base on the AGENTS line's neighbour."""
    sha = "a" * 8 + "1" * 32
    record = {
        "main": sha,
        "agents_bytes": 91766,
        "agents_lines": 1363,
        "agents_headings": 42,
        "agents_headings_sha256": "0" * 64,
    }
    text = bp.render(record)

    # Then the AGENTS line and the BASE line both appear, BASE directly after AGENTS
    assert "AGENTS: " in text
    assert f"BASE: {sha} (== origin/main at open)" in text
    agents_pos = text.index(bp.agents_line(record))
    base_pos = text.index(bp.base_line(record))
    assert agents_pos < base_pos, "the BASE line must sit next to the AGENTS line"
    gap = text[agents_pos + len(bp.agents_line(record)):base_pos]
    assert "\n" in gap and not any(
        l.startswith("AGENTS") or l.startswith("BASE") for l in gap.splitlines()
    ), "no other record key may sit between AGENTS and BASE"


def test_the_base_line_names_the_same_sha_as_the_record(tmp_path):
    """`BASE:` echoes `record['main']` (the origin/main sha measured at open)."""
    record = {
        "main": "f" * 40,
        "agents_bytes": 1,
        "agents_lines": 2,
        "agents_headings": 3,
        "agents_headings_sha256": "0" * 64,
    }
    assert bp.base_line(record) == f"BASE: {record['main']} (== origin/main at open)"


def test_a_real_preflight_record_carries_both_lines(tmp_path):
    """A real checkout at origin/main yields a record with AGENTS and BASE together.

    This is the harness the preflight discipline already uses for `main` in
    tests/test_bot_preflight.py — the record is the input a lane preloads.
    """
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    (root / "a.txt").write_text("one\n")
    subprocess.run(["git", "-C", str(root), "add", "a.txt"], check=True)
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
           "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.com",
                    "commit", "-q", "-m", "seed"], check=True, env={**__import__("os").environ, **env})
    root.joinpath("AGENTS.md").write_text("## Rule\n\nbody\n")
    subprocess.run(["git", "-C", str(root), "add", "AGENTS.md"], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.com",
                    "commit", "-q", "-m", "agents"], check=True)

    rec = bp.rulebook(root, "HEAD")   # measure AGENTS.md at HEAD (no origin configured)
    text = bp.render(rec)
    assert "AGENTS: " in text
    assert "BASE:" in text and "(== origin/main at open)" in text
    assert text.index("AGENTS: ") < text.index("BASE:")
