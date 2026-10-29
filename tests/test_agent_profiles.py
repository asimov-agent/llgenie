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


def test_manifest_lists_every_host_profile():
    """`agents/manifest.json` names all seven host profiles (acceptance criterion 4, widened by the
    consolidation ruling: the tree lands once, with every lane's profile in it)."""

    # Given the committed manifest
    profiles = guard.profiles_from_manifest(REPO / "agents")
    names = [profile["name"] for profile in profiles]

    # When  it is read as the sync target reads it
    # Then  every host profile is listed, and the orchestrator keeps both standing rules
    assert names == [
        "llgenie-planner", "llgenie-issse-implementer", "llgenie-architect", "llgenie-security",
        "llgenie-documentation-maintainer", "llgenie-ci-pipelines-maintainer", "llgenie-pr-reviever",
    ]
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


def test_a_truncated_seed_is_refused_rather_than_shrinking_the_live_profile(tmp_path):
    """The defect this guards: a seed taken from an issue excerpt is a prefix, not an edit.

    `sync` copied whatever the tree held over the live profile, so a 5,149-byte excerpt replaced a
    7,509-byte rulebook with every gate green. Now the sync refuses and names both sizes.
    """
    import agent_profile_sync as sync

    agents = tmp_path / "agents"
    prof = agents / "someone"
    prof.mkdir(parents=True)
    (prof / "SOUL.md").write_text("short seed\n")
    live = tmp_path / "live"
    live.mkdir()
    (live / "SOUL.md").write_text("a much longer, real rulebook\n" * 200)

    assert [row[0] for row in sync.shrinks(agents, "someone", live)] == ["SOUL.md"]
    assert sync.shrinks(agents, "someone", live)[0][3] > 0, "the live file has lines the tree lacks"
    assert sync.write(agents, "someone", live) == 3
    assert (live / "SOUL.md").stat().st_size > 1000, "the refusal must not have written anything"

    assert sync.write(agents, "someone", live, force=True) == 0
    assert (live / "SOUL.md").read_text() == "short seed\n", "--force means it"


def test_a_live_rulebook_longer_than_the_tree_copy_is_a_finding(tmp_path):
    """The truncated seed, caught BEFORE a sync: `sync` copies tree over profile, so a prefix loses a rule."""
    import check_agent_profiles as cap

    agents = tmp_path / "agents"
    prof = agents / "someone"
    (prof / "skills" / "s").mkdir(parents=True)
    (prof / "SOUL.md").write_text("short\n")
    (prof / "skills" / "s" / "SKILL.md").write_text("also short\n")
    live = tmp_path / "live" / "someone"
    (live / "skills" / "s").mkdir(parents=True)
    (live / "SOUL.md").write_text("a much longer live rulebook\n" * 100)
    (live / "skills" / "s" / "SKILL.md").write_text("also short\n")          # identical: not a finding
    (agents / "manifest.json").write_text('{"profiles": [{"name": "someone", "rules": ["never-merge"]}]}')

    items = cap.shrink_findings(tmp_path, agents, live.parent)
    assert [i["key"] for i in items] == ["live-longer"]
    assert "SOUL.md" in items[0]["where"]
    assert "prefix of the rulebook" in items[0]["detail"]


def test_a_tree_copy_that_matches_or_exceeds_the_live_one_is_clean(tmp_path):
    import check_agent_profiles as cap

    agents = tmp_path / "agents"
    prof = agents / "someone"
    prof.mkdir(parents=True)
    (prof / "SOUL.md").write_text("the same rulebook\n")
    live = tmp_path / "live" / "someone"
    live.mkdir(parents=True)
    (live / "SOUL.md").write_text("the same rulebook\n")
    (agents / "manifest.json").write_text('{"profiles": [{"name": "someone", "rules": ["never-merge"]}]}')
    assert cap.shrink_findings(tmp_path, agents, live.parent) == []


def test_no_live_profile_home_means_the_comparison_is_skipped_not_failed(tmp_path):
    """CI has no `~/.hermes/profiles/`; a gate that cannot see the live files must say nothing, not fail."""
    import check_agent_profiles as cap

    agents = tmp_path / "agents"
    (agents / "someone").mkdir(parents=True)
    (agents / "someone" / "SOUL.md").write_text("x\n")
    (agents / "manifest.json").write_text('{"profiles": [{"name": "someone", "rules": ["never-merge"]}]}')
    assert cap.shrink_findings(tmp_path, agents, None) == []


def test_a_tree_file_that_is_a_content_SUBSET_is_refused_even_when_the_sizes_are_close(tmp_path):
    """Rule from the #791 review: content, not a size ratio.

    A seed that keeps every heading but drops the rules under them can be within a few percent of the
    live size, so a size floor alone passes it. Subset-of-lines catches it: every line the tree has is
    in the live file, and the live file has more.
    """
    import agent_profile_sync as sync

    agents = tmp_path / "agents"
    prof = agents / "someone"
    prof.mkdir(parents=True)
    live = tmp_path / "live"
    live.mkdir()
    rules = "".join(f"- rule {i}: a long operating rule that matters\n" for i in range(20))
    (live / "SOUL.md").write_text(rules + "- rule Z: only in live\n")
    subset = "".join(f"- rule {i}: a long operating rule that matters\n" for i in range(20))
    (prof / "SOUL.md").write_text(subset)                      # ~95 % of the size, 1 rule missing

    found = sync.shrinks(agents, "someone", live)
    assert [row[0] for row in found] == ["SOUL.md"]
    assert found[0][3] == 1, "exactly one line would be lost"
    assert sync.write(agents, "someone", live) == 3
    assert (live / "SOUL.md").read_text().endswith("only in live\n"), "the refusal wrote nothing"


def test_a_genuine_rewrite_that_is_not_a_subset_is_allowed(tmp_path):
    """The control: different rules are an edit, not a truncation — the guard must not block edits."""
    import agent_profile_sync as sync

    agents = tmp_path / "agents"
    prof = agents / "someone"
    prof.mkdir(parents=True)
    live = tmp_path / "live"
    live.mkdir()
    (live / "SOUL.md").write_text("- old rule A\n- old rule B\n")
    (prof / "SOUL.md").write_text("- new rule A\n- new rule B\n")
    assert sync.shrinks(agents, "someone", live) == []
    assert sync.write(agents, "someone", live) == 0
    assert (live / "SOUL.md").read_text() == "- new rule A\n- new rule B\n"


# ---- the MESSAGE is part of the contract, not just the exit code (review of #903) -----------


def test_a_refusal_names_both_sizes_says_smaller_and_never_says_verified(tmp_path, capsys):
    """A refusal that still prints "verified" is the same lie with a non-zero exit.

    The original defect was not that sync shrank a file: it was that it shrank one and printed
    `verified: 3 file(s) read back identical`. So the test pins the sentence, not the return code alone.
    """
    import agent_profile_sync as sync

    agents = tmp_path / "agents"
    (agents / "someone").mkdir(parents=True)
    live = tmp_path / "live"
    live.mkdir()
    tree_text = "- a\n- b\n"
    live_text = "- a\n- b\n- c the rule that would be lost\n"
    (agents / "someone" / "SOUL.md").write_text(tree_text)
    (live / "SOUL.md").write_text(live_text)
    tree_bytes, live_bytes = len(tree_text.encode()), len(live_text.encode())

    rc = sync.write(agents, "someone", live)
    out = capsys.readouterr()
    message = out.out + out.err

    assert rc != 0
    assert f"{tree_bytes} b" in message and f"{live_bytes} b" in message, message   # both sizes named
    assert "verified" not in message.lower(), message             # the lie this test exists for
    assert "smaller" in message.lower(), message
    assert "would delete" in message and "line(s)" in message
    assert (live / "SOUL.md").read_text().endswith("the rule that would be lost\n"), "nothing was written"


def test_a_successful_copy_never_claims_identical_for_a_changed_file(tmp_path, capsys):
    """The other half: success must say what happened, not that the destination was already right."""
    import agent_profile_sync as sync

    agents = tmp_path / "agents"
    (agents / "someone").mkdir(parents=True)
    live = tmp_path / "live"
    live.mkdir()
    (agents / "someone" / "SOUL.md").write_text("- brand new rule\n")
    (live / "SOUL.md").write_text("- an older rule\n")            # a genuine rewrite, not a subset

    assert sync.write(agents, "someone", live) == 0
    message = capsys.readouterr().out
    assert "copied" in message.lower() and "replaced an existing file" in message.lower(), message
    assert "identical" not in message.lower(), message


def test_the_force_path_says_it_shrank_and_never_claims_identity(tmp_path, capsys):
    """`--force` is the one case where a file legitimately shrinks — so the log must say so.

    Without this the refusal assertion only guards the path nobody takes: pass `--force` and the old
    "verified … read back identical" over a 2,360-byte deletion comes straight back (review of #903).
    """
    import agent_profile_sync as sync

    agents = tmp_path / "agents"
    (agents / "someone").mkdir(parents=True)
    live = tmp_path / "live"
    live.mkdir()
    tree_text = "- a\n- b\n"
    live_text = "- a\n- b\n- c the rule that would be lost\n"
    (agents / "someone" / "SOUL.md").write_text(tree_text)
    (live / "SOUL.md").write_text(live_text)
    tree_bytes, live_bytes = len(tree_text.encode()), len(live_text.encode())

    assert sync.write(agents, "someone", live, force=True) == 0
    message = capsys.readouterr().out.lower()

    assert "read back identical" not in message, message          # the sentence this exists to kill
    assert "shrank" in message and "--force" in message, message
    assert f"{tree_bytes:,} b" in message and f"{live_bytes:,} b" in message, message
    assert "line(s) removed" in message, message                  # it says what was lost, not just that it wrote
    assert (live / "SOUL.md").read_text() == tree_text, "force means it"


def test_the_live_comparison_skip_is_audible_not_silent(tmp_path, capsys, monkeypatch):
    """A check that cannot compare must say so, or a reader concludes it compared.

    The runner has no `~/.hermes/profiles/`, so the comparison cannot run there — but silence is how a
    truncated seed reached a green gate in the first place (review of #791). The skip is a stated
    outcome, and this asserts the sentence.
    """
    import check_agent_profiles as cap

    agents = tmp_path / "agents" / "someone"
    agents.mkdir(parents=True)
    (agents / "SOUL.md").write_text("# Someone\n\n## Rules\n\n- never merge\n")
    (tmp_path / "agents" / "manifest.json").write_text(
        '{"profiles": [{"name": "someone", "rules": ["never-merge"]}]}')
    monkeypatch.setenv("HERMES_PROFILES_HOME", str(tmp_path / "no-profiles-here"))

    assert cap.main(["check", "--root", str(tmp_path)]) == 0
    err = capsys.readouterr().err.lower()
    assert "skipped" in err, err
    assert "not compared" in err, err
    assert "tree checks only" in err, err


def test_the_singular_env_var_resolves_to_its_parent_and_still_compares(tmp_path, monkeypatch, capsys):
    """`HERMES_PROFILE_HOME` names ONE profile's home; the gate needs the directory holding them all.

    Taking the singular name at face value would look for `<a profile>/<lane>/SOUL.md`, find nothing, and
    report a green with the comparison skipped — the audible-skip defect reintroduced by a variable name.
    """
    import check_agent_profiles as cap

    profiles = tmp_path / "profiles"
    tree_side = profiles / "someone"
    tree_side.mkdir(parents=True)
    (tree_side / "SOUL.md").write_text("short\n")
    agents = tmp_path / "agents" / "someone"
    agents.mkdir(parents=True)
    (agents / "SOUL.md").write_text("short\n")
    (tree_side / "SOUL.md").write_text("short\n")
    (tmp_path / "agents" / "manifest.json").write_text(
        '{"profiles": [{"name": "someone", "rules": ["never-merge"]}]}')
    (agents / "SOUL.md").write_text("# S\n\n## Rules\n\n- never merge\n")
    (tree_side / "SOUL.md").write_text("# S\n\n## Rules\n\n- never merge\n")

    monkeypatch.delenv("HERMES_PROFILES_HOME", raising=False)
    monkeypatch.setenv("HERMES_PROFILE_HOME", str(tree_side))      # a PROFILE's home, not the root

    base, source = cap.live_root_info()
    assert base == profiles, f"the parent must be used, got {base} from {source}"
    assert "parent" in source

    assert cap.main(["check", "--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "LIVE RULEBOOKS NOT COMPARED" not in out, "the comparison DID run, so no caveat belongs here"


def test_the_ok_line_carries_the_caveat_when_the_comparison_is_skipped(tmp_path, monkeypatch, capsys):
    """`EXIT=0` hides the skip: a reader, and a `&&` chain, look at the OK line and nothing else."""
    import check_agent_profiles as cap

    agents = tmp_path / "agents" / "someone"
    agents.mkdir(parents=True)
    (agents / "SOUL.md").write_text("# S\n\n## Rules\n\n- never merge\n")
    (tmp_path / "agents" / "manifest.json").write_text(
        '{"profiles": [{"name": "someone", "rules": ["never-merge"]}]}')
    monkeypatch.setenv("HERMES_PROFILES_HOME", str(tmp_path / "absent"))
    monkeypatch.delenv("HERMES_PROFILE_HOME", raising=False)

    assert cap.main(["check", "--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "OK:" in out and "tree checks only, LIVE RULEBOOKS NOT COMPARED" in out, out

# --- the live profile is a MOVING reference: a sync must not overwrite work it did not read (issue #924)


def _moving_fixture(tmp_path, monkeypatch):
    """A tree copy committed at T, and a live file another lane edited at T+600 — the #924 shape."""
    import agent_profile_sync as sync

    agents = tmp_path / "agents"
    (agents / "someone").mkdir(parents=True)
    live = tmp_path / "live"
    live.mkdir()
    tree_text = "- a\n- b\n"
    live_text = "- a\n- b\n- a rule another lane added at 01:44Z\n"
    (agents / "someone" / "SOUL.md").write_text(tree_text)
    (live / "SOUL.md").write_text(live_text)
    monkeypatch.setattr(sync, "source_time", lambda *a, **k: 1_700_000_000.0)
    os.utime(live / "SOUL.md", (1_700_000_600, 1_700_000_600))
    return sync, agents, live, tree_text, live_text


def test_sync_refuses_to_overwrite_a_live_file_newer_than_the_source_commit(tmp_path, capsys, monkeypatch):
    """The write path is where a moving reference bites: no read-time caveat can see a sync it allowed.

    Measured on #919: a `cp` from live was one command away from deleting twelve lines of tree-only
    content that existed nowhere else, because the live file had been rewritten mid-review. A guard that
    only compares CONTENT cannot see that the other side moved, so the refusal is on the time, and it is
    checked BEFORE the shrink guard — the content problem would be the wrong description of the real one.
    """
    sync, agents, live, _, live_text = _moving_fixture(tmp_path, monkeypatch)

    rc = sync.write(agents, "someone", live)
    message = capsys.readouterr()
    text = message.out + message.err

    assert rc == 4, text
    assert "would overwrite" in text, text
    assert "edited AFTER the tree copy was committed" in text, text
    assert "2023-11-14T22:13:20Z" in text and "2023-11-14T22:23:20Z" in text, text  # both times, named
    assert "losing 1 line(s)" in text, text          # what the overwrite would cost
    assert "verified" not in text.lower(), text      # a refusal that prints success is the same lie
    assert (live / "SOUL.md").read_text() == live_text, "nothing was written"


def test_the_force_path_says_it_overwrote_a_newer_live_file(tmp_path, capsys, monkeypatch):
    """`--force` is the one legitimate overwrite of newer live work — so the log must name it."""
    sync, agents, live, _, _ = _moving_fixture(tmp_path, monkeypatch)

    assert sync.write(agents, "someone", live, force=True) == 0
    text = capsys.readouterr().out

    assert "overwrote a live file NEWER than the source commit by --force" in text, text
    assert "2023-11-14T22:23:20Z" in text, text
    assert "identical" not in text.lower(), text


def test_a_live_file_older_than_the_source_commit_is_not_refused(tmp_path, capsys, monkeypatch):
    """The control: the guard must not fire on the ordinary case, or it is just a red gate."""
    import agent_profile_sync as sync

    agents = tmp_path / "agents"
    (agents / "someone").mkdir(parents=True)
    live = tmp_path / "live"
    live.mkdir()
    (agents / "someone" / "SOUL.md").write_text("- brand new rule\n")
    (live / "SOUL.md").write_text("- an older rule\n")          # a genuine rewrite, not a subset
    monkeypatch.setattr(sync, "source_time", lambda *a, **k: 1_700_000_000.0)
    os.utime(live / "SOUL.md", (1_699_999_000, 1_699_999_000))

    assert sync.write(agents, "someone", live) == 0
    text = capsys.readouterr().out
    assert "REFUSED" not in text and "NEWER than the source commit" not in text, text


def test_the_source_time_is_the_COMMIT_not_the_file_mtime(tmp_path):
    """A fresh clone sets every mtime to now, which would disarm the guard on the very checkout using it."""
    import subprocess as sp

    import agent_profile_sync as sync

    agents = tmp_path / "agents"
    (agents / "someone").mkdir(parents=True)
    path = agents / "someone" / "SOUL.md"
    path.write_text("- a rule\n")
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "x"]):
        sp.run(cmd, cwd=tmp_path, check=True, capture_output=True)

    committed = sync.source_time(agents, "someone", path)
    os.utime(path, (4_000_000_000, 4_000_000_000))              # an mtime far in the future
    assert sync.source_time(agents, "someone", path) == committed
    assert committed < 4_000_000_000, "the mtime leaked into the source time"

