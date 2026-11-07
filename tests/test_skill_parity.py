from __future__ import annotations

import json
import os
from pathlib import Path

from scripts import skill_parity as sp


def _setup(tmp_path: Path, monkeypatch):
    """A fake repo (one profile with a tree skills dir) and a fake live profiles home."""
    repo = tmp_path / "repo"
    (repo / "agents" / "p1" / "skills" / "s" / "references").mkdir(parents=True)
    (repo / "agents" / "p1" / "skills" / "s" / "references" / "a.md").write_text("# a")
    (repo / "agents" / "p1" / "skills" / "s" / "references" / "only_in_tree.md").write_text("# t")
    manifest = {"note": "test", "profiles": [{"name": "p1", "rules": []}]}
    (repo / "agents" / "manifest.json").write_text(json.dumps(manifest))

    homes = tmp_path / "profiles"
    live_ref = homes / "p1" / "skills" / "s" / "references"
    live_ref.mkdir(parents=True)
    (live_ref / "a.md").write_text("# a")
    (live_ref / "only_live.md").write_text("# l")
    monkeypatch.setenv("HERMES_PROFILES_HOME", str(homes))
    monkeypatch.delenv("HERMES_PROFILE_HOME", raising=False)
    return repo


def _state(live_ref: Path) -> dict:
    return {p.name: p.read_text() for p in live_ref.iterdir() if p.is_file()}


def test_live_only_and_tree_only_reported(tmp_path, monkeypatch):
    repo = _setup(tmp_path, monkeypatch)
    drift = sp.profile_drift(repo)
    assert drift is not None
    rows = sp.findings(drift)
    joined = " ; ".join(rows)
    assert "1 live-only skill file" in joined and "only_live.md" in joined
    assert "1 tree-only skill file" in joined and "only_in_tree.md" in joined


def test_read_only_never_modified(tmp_path, monkeypatch):
    """Layer A MUST NOT write: the live profile and the tree are byte-identical before/after a report."""
    repo = _setup(tmp_path, monkeypatch)
    live_ref = tmp_path / "profiles" / "p1" / "skills" / "s" / "references"
    before = _state(live_ref)
    tree_state = {p.name: p.read_text() for p in (repo / "agents" / "p1" / "skills" / "s" / "references").glob("*.md")}
    sp.report(repo)  # runs the whole report path, must not write back
    assert _state(live_ref) == before, "skill-parity modified the live profile — it must be read-only"
    after_tree = {p.name: p.read_text() for p in (repo / "agents" / "p1" / "skills" / "s" / "references").glob("*.md")}
    assert after_tree == tree_state, "skill-parity modified the tree — it must be read-only"
    assert not list((tmp_path / "profiles" / "p1" / "skills" / "s" / "references").rglob("*.tmp"))


def test_check_fails_when_drift(tmp_path, monkeypatch):
    repo = _setup(tmp_path, monkeypatch)
    assert sp.check(repo) == 1


def test_no_live_profiles_is_not_a_failure(tmp_path, monkeypatch):
    """A host without live profiles cannot compare and must not fail (CI runner / bare checkout)."""
    repo = _setup(tmp_path, monkeypatch)
    monkeypatch.setenv("HERMES_PROFILES_HOME", str(tmp_path / "absent"))
    assert sp.check(repo) == 0
