#!/usr/bin/env python3
"""The host agents' SOUL and skills live in this repo, and both halves of the seam are real (issue #791).

`.hermes/skills/` holds the CI legs' contracts and is gated by `scripts/check_agent_skills.py`
(issue #577). The two HOST agents — `llgenie-planner` (the orchestrator) and
`llgenie-issse-implementer` (the implementer) — keep the same two kinds of file under
`~/.hermes/profiles/<profile>/`, outside version control, and every instruction they run under was
therefore unreviewable. `agents/<profile>/` is that behaviour's home now.

These tests drive the REAL scripts — `scripts/check_agent_profiles.py` and
`scripts/agent_profile_sync.py` — never a copy of their logic, against fixture trees that carry each
shape the gate exists to catch (one rejection per test, never a happy-path-only suite) and against
a temporary `HERMES_PROFILE_HOME` for the sync. The committed tree is exercised too, so a profile
that loses its `SOUL.md` fails here as well as in `make check-agent-profiles`.

The host-only proof — `CHECK=1` against the owner's live `~/.hermes/profiles/<profile>/` — cannot
run where no profile exists; it is recorded in `agent-wiki/2026-10-28-agent-profiles-tree.md`.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import check_agent_profiles as guard  # noqa: E402  (the real gate, never a copy)

SOUL_ORCHESTRATOR = """# LLGenie Orchestrator

**Role:** fixture orchestrator

You do not implement. A branch or a PR from you is a mistake.

Never merge, never push to `main`: every merge needs the owner's approval.
"""

SKILL_BODY = """---
name: {name}
description: A fixture skill named {name}.
---

# {name}

## When to Use

- a fixture condition
"""


def write_manifest(agents: Path, profiles: list) -> None:
    agents.mkdir(parents=True, exist_ok=True)
    (agents / "manifest.json").write_text(json.dumps({"profiles": profiles}, indent=2) + "\n",
                                          encoding="utf-8")


def write_soul(agents: Path, name: str, text: str = SOUL_ORCHESTRATOR) -> None:
    base = agents / name
    base.mkdir(parents=True, exist_ok=True)
    (base / "SOUL.md").write_text(text, encoding="utf-8")


def write_skill(agents: Path, profile: str, skill: str, body: str | None = None,
                references: dict[str, str] | None = None) -> None:
    d = agents / profile / "skills" / skill
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(body if body is not None else SKILL_BODY.format(name=skill),
                                encoding="utf-8")
    for rel, text in (references or {}).items():
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / rel).write_text(text, encoding="utf-8")


def fixture_tree(tmp_path: Path, profiles: list | None = None) -> Path:
    """A minimal tree the gate can read: `agents/manifest.json` plus one clean profile."""
    root = tmp_path / "tree"
    agents = root / "agents"
    write_manifest(agents, profiles if profiles is not None else
                   [{"name": "llgenie-planner", "rules": ["never-implement", "never-merge"]}])
    write_soul(agents, "llgenie-planner")
    write_skill(agents, "llgenie-planner", "llgenie-bot-orchestration")
    return root


def keys(root: Path) -> set[str]:
    """The finding keys the gate reports for *root*."""
    return {item["key"] for item in guard.findings(root, guard.AGENTS_DIR)}


# ---- the committed tree ----------------------------------------------------------


def test_committed_tree_passes_the_gate():
    """The tree this repository ships is clean: two profiles, each SOUL stating its rules."""

    # Given the repository's own agents/ tree
    # When the gate reads it
    items = guard.findings(REPO)

    # Then it reports no finding at all
    assert items == [], items


def test_manifest_lists_both_host_profiles():
    """`agents/manifest.json` names the orchestrator and the implementer (acceptance criterion 4)."""

    # Given the committed manifest
    profiles = guard.profiles_from_manifest(REPO / "agents")
    names = [profile["name"] for profile in profiles]

    # When  it is read as the sync target reads it
    # Then  both live host profiles are listed, and the orchestrator keeps both standing rules
    assert names == ["llgenie-planner", "llgenie-issse-implementer"]
    planner = next(p for p in profiles if p["name"] == "llgenie-planner")
    assert set(planner["rules"]) == {"never-implement", "never-merge"}


def test_committed_planner_soul_states_both_standing_rules():
    """The committed orchestrator SOUL still forbids implementing and merging."""

    # Given the committed planner SOUL.md
    text = (REPO / "agents" / "llgenie-planner" / "SOUL.md").read_text(encoding="utf-8")

    # When  each standing rule is matched
    # Then  both are stated
    for rule, pattern in guard.STANDING_RULES.items():
        assert pattern.search(text), f"agents/llgenie-planner/SOUL.md no longer states {rule}"


# ---- one rejection per gate rule -------------------------------------------------


def test_missing_profile_directory_is_rejected(tmp_path):
    """A profile the manifest lists with no directory has nothing to sync."""

    # Given a manifest that lists a profile whose directory does not exist
    root = fixture_tree(tmp_path, profiles=[
        {"name": "llgenie-planner", "rules": ["never-merge"]},
        {"name": "ghost-profile", "rules": []},
    ])

    # When  the gate reads the tree
    # Then  the absent directory is a finding, not a silent pass
    assert "profile-directory" in keys(root)


def test_profile_without_soul_is_rejected(tmp_path):
    """A profile directory with no SOUL.md has no role in the tree."""

    # Given a listed profile whose directory exists but carries no SOUL.md
    root = fixture_tree(tmp_path)
    (root / "agents" / "llgenie-planner" / "SOUL.md").unlink()

    # When  the gate reads the tree
    # Then  the missing SOUL.md is a finding
    assert "soul-missing" in keys(root)


def test_skill_name_that_differs_from_its_directory_is_rejected(tmp_path):
    """Hermes resolves a skill by its frontmatter name, so a mismatch loads nothing."""

    # Given a skill filed under a directory whose name its frontmatter disagrees with
    root = fixture_tree(tmp_path)
    write_skill(root / "agents", "llgenie-planner", "wrong-directory",
                SKILL_BODY.format(name="some-other-skill"))

    # When  the gate reads the tree
    # Then  the mismatch is a finding
    assert "skill-name" in keys(root)


def test_skill_without_frontmatter_is_rejected(tmp_path):
    """A SKILL.md with no `---` block cannot be indexed by Hermes."""

    # Given a skill file that opens with prose instead of frontmatter
    root = fixture_tree(tmp_path)
    write_skill(root / "agents", "llgenie-planner", "no-frontmatter", "# no frontmatter here\n")

    # When  the gate reads the tree
    # Then  the missing frontmatter block is a finding
    assert "skill-frontmatter" in keys(root)


def test_secret_shaped_value_in_a_skill_is_rejected(tmp_path):
    """A credential value in a skill is a leak with a diff — the agent it feeds has write access."""

    # Given a skill whose body carries a token-shaped value (assembled so this test is not itself
    # a secret a scanner would flag)
    token = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
    root = fixture_tree(tmp_path)
    write_skill(root / "agents", "llgenie-planner", "leaky-skill",
                SKILL_BODY.format(name="leaky-skill") + f"\n- run with `{token}`\n")

    # When  the gate reads the tree
    # Then  the value is a finding
    assert "secret" in keys(root)


def test_soul_that_dropped_never_merge_is_rejected(tmp_path):
    """The orchestrator's never-merge rule is the one this tree exists to keep reviewable."""

    # Given a planner SOUL.md that no longer forbids merging
    root = fixture_tree(tmp_path)
    write_soul(root / "agents", "llgenie-planner",
               "# LLGenie Orchestrator\n\nYou do not implement. A branch from you is a mistake.\n")

    # When  the gate reads the tree
    # Then  the dropped rule is a finding
    assert "standing-rule" in keys(root)


def test_manifest_that_declares_never_merge_for_nobody_is_rejected(tmp_path):
    """A manifest that emptied the rule list would otherwise make every SOUL compliant."""

    # Given a manifest where no profile declares the never-merge rule
    root = fixture_tree(tmp_path, profiles=[{"name": "llgenie-planner", "rules": []}])

    # When  the gate reads the tree
    # Then  the emptied rule set is a finding
    assert "manifest-rule" in keys(root)


def test_profile_directory_the_manifest_does_not_list_is_rejected(tmp_path):
    """A profile directory nothing lists is behaviour that syncs and gates never see."""

    # Given a profile directory the manifest omits
    root = fixture_tree(tmp_path)
    write_soul(root / "agents", "unlisted-profile")

    # When  the gate reads the tree
    # Then  the unlisted directory is a finding
    assert "profile-unlisted" in keys(root)


def test_skill_reference_that_is_not_in_the_tree_is_rejected(tmp_path):
    """A rule that points at `references/x.md` is broken when that file was never committed."""

    # Given a skill that names a reference file the tree does not carry
    root = fixture_tree(tmp_path)
    write_skill(root / "agents", "llgenie-planner", "with-reference",
                SKILL_BODY.format(name="with-reference") + "\nRecipes: `references/missing.md`.\n")

    # When  the gate reads the tree
    # Then  the dangling reference is a finding
    assert "skill-reference-missing" in keys(root)


def test_profile_data_in_the_tree_is_rejected(tmp_path):
    """A profile's memory, sessions and state database are data, never behaviour."""

    # Given a committed state.db beside the profile's SOUL.md
    root = fixture_tree(tmp_path)
    (root / "agents" / "llgenie-planner" / "state.db").write_bytes(b"SQLite format 3\x00")

    # When  the gate reads the tree
    # Then  the committed profile data is a finding
    assert "forbidden-path" in keys(root)


def test_missing_agents_tree_is_rejected(tmp_path):
    """No agents/ tree is the state this issue removes, not an empty pass."""

    # Given a root with no agents/ directory at all
    root = tmp_path / "empty"
    root.mkdir()

    # When  the gate reads it
    # Then  the absent tree is a finding
    assert "agents-dir" in keys(root)


def test_unknown_rule_key_in_the_manifest_is_rejected(tmp_path):
    """A misspelt rule is a rule nobody enforces."""

    # Given a manifest naming a rule the gate does not know
    root = fixture_tree(tmp_path, profiles=[
        {"name": "llgenie-planner", "rules": ["never-merge", "never-mrege"]},
    ])

    # When  the gate reads the tree
    # Then  the unknown rule name is a finding
    assert "manifest-rule-unknown" in keys(root)


# ---- the sync target -------------------------------------------------------------


def run_sync(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    """The real `scripts/agent_profile_sync.py`, as `make sync-agent-profile` runs it."""
    environment = dict(os.environ)
    environment.pop("HERMES_PROFILE_HOME", None)
    environment.update(env or {})
    return subprocess.run(
        [sys.executable, str(REPO / "scripts" / "agent_profile_sync.py"), *args],
        capture_output=True, text=True, env=environment,
    )


def test_sync_copies_the_tree_into_a_temporary_profile_home(tmp_path):
    """`make sync-agent-profile` writes the tree into the profile, then reads it back."""

    # Given a temporary HERMES_PROFILE_HOME standing in for the profile's Hermes home
    dest = tmp_path / "profile-home"

    # When  the sync runs for the orchestrator
    result = run_sync("--profile", "llgenie-planner", "--dest", str(dest))

    # Then  it exits 0, and every file the tree carries is byte-identical in the profile
    assert result.returncode == 0, result.stderr
    committed = sorted(p.relative_to(REPO / "agents" / "llgenie-planner")
                       for p in (REPO / "agents" / "llgenie-planner").rglob("*") if p.is_file())
    assert committed, "the tree carries no file"
    for rel in committed:
        assert (dest / rel).read_bytes() == (REPO / "agents" / "llgenie-planner" / rel).read_bytes()


def test_sync_check_passes_after_the_copy_and_names_a_tampered_file(tmp_path):
    """`CHECK=1` compares every file and fails on the first one a profile changed."""

    # Given a profile home the sync has just written
    dest = tmp_path / "profile-home"
    assert run_sync("--profile", "llgenie-planner", "--dest", str(dest)).returncode == 0

    # When  one copied file is tampered with and the check runs again
    tampered = dest / "SOUL.md"
    tampered.write_text(tampered.read_text(encoding="utf-8") + "\nan extra line\n", encoding="utf-8")
    result = run_sync("--profile", "llgenie-planner", "--check", "--dest", str(dest))

    # Then  the check fails and names that path
    assert result.returncode == 1
    assert "SOUL.md" in result.stderr


def test_sync_check_honours_HERMES_PROFILE_HOME(tmp_path):
    """The destination comes from `$HERMES_PROFILE_HOME` when no `--dest` is given."""

    # Given HERMES_PROFILE_HOME pointing at a profile home the sync wrote
    dest = tmp_path / "env-home"
    assert run_sync("--profile", "llgenie-issse-implementer",
                    env={"HERMES_PROFILE_HOME": str(dest)}).returncode == 0

    # When  the check runs with the same environment and no explicit destination
    result = run_sync("--profile", "llgenie-issse-implementer", "--check",
                      env={"HERMES_PROFILE_HOME": str(dest)})

    # Then  it reads the environment's path and passes
    assert result.returncode == 0, result.stderr
    assert str(dest) in result.stdout


def test_sync_of_an_unknown_profile_exits_2(tmp_path):
    """An unknown profile is an error, never a no-op that reports success."""

    # Given a profile name the manifest does not list
    # When  the sync runs
    result = run_sync("--profile", "not-a-profile", "--check", "--dest", str(tmp_path))

    # Then  it exits 2 and says which profiles it knows
    assert result.returncode == 2
    assert "llgenie-planner" in result.stderr
