"""The bot preflight records the BASE beside the AGENTS line (issue #845 criterion 2).

The defect #845 names is that the base sha a worktree/PR was cut from is recorded
nowhere, so a lane spawned from a parked checkout carried the wrong base
invisibly. This pins the record: `render()` MUST carry `BASE: <sha> (==
origin/main at open)` directly beside the existing `AGENTS:` line, so a reviewer
can check the base without consulting the branch.
"""
from __future__ import annotations

import itertools
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

#: fresh per-call repo name so two _findings calls in one test never collide (id() is reused after GC).
_SEQ = itertools.count(1)

import scripts.bot_preflight as bp  # noqa: E402


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


def _hygiene_repo(tmp_path):
    """A git repo whose HEAD holds an AGENTS.md — the tree the hygiene gate reads AGENTS/BASE from."""
    import scripts.check_pr_hygiene as cph

    root = tmp_path
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    root.joinpath("AGENTS.md").write_text(cph.AGENTS_MANDATE + "\n\nbody\n")
    subprocess.run(["git", "-C", str(root), "add", "AGENTS.md"], check=True)
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
           "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.com",
                    "commit", "-q", "-m", "agents"], check=True, env={**__import__("os").environ, **env})
    return root


def _findings(tmp_path, body_builder):
    """Run `agents_line_findings` over a body built from the repo's HEAD (AGENTS sha = HEAD commit/files)."""
    import scripts.check_pr_hygiene as cph
    root = _hygiene_repo(tmp_path / f"repo-{next(_SEQ)}")
    subprocess.run(["git", "-C", str(root), "remote", "add", "origin", str(tmp_path / "nope.git")],
                   check=True)
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    body = body_builder(head)
    return root, head, cph.agents_line_findings(root, head, head, body)


def test_the_hygiene_gate_accepts_agents_and_base_together(tmp_path):
    """A body carrying AGENTS + a matching BASE line passes the #845 gate."""
    _, head, findings = _findings(
        tmp_path,
        lambda h: f"title\n\nAGENTS: {h} 5b 2l\n\nBASE: {h} (== origin/main at open)\ncloses #999\n")
    assert findings == [], findings


def test_the_hygiene_gate_refuses_a_missing_or_nonmatching_base_line(tmp_path):
    """A bot body with AGENTS but no BASE (or a wrong one) fails — the #845 recording is enforced."""
    _, head, findings = _findings(tmp_path, lambda h: f"AGENTS: {h[:8]} 1b 2l\n")
    assert findings and findings[0]["key"] == "base-line"
    assert "no `BASE:" in findings[0]["detail"]

    # a BASE line naming a DIFFERENT sha than AGENTS is a mismatch, not a pass
    _, head, findings = _findings(
        tmp_path,
        lambda h: f"AGENTS: {h[:8]} 1b 2l\n\nBASE: {'b'*40 if h[:9] != 'b'*9 else 'a'*40} (== origin/main at open)\n")
    assert findings and findings[0]["key"] == "base-line"
    assert "does not match" in findings[0]["detail"] or "names" in findings[0]["detail"]
