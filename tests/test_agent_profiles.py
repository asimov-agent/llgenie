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
    # Then every profile the tree is expected to carry is listed, and the orchestrator keeps both rules.
    # SUBSET, not equality: an exact list is a snapshot of the membership and reds on the next legitimate
    # addition (issue #873's rule 12) - and this lane's own profile joins next.
    assert {
        "llgenie-planner", "llgenie-issse-implementer", "llgenie-architect", "llgenie-security",
        "llgenie-documentation-maintainer", "llgenie-ci-pipelines-maintainer", "llgenie-pr-reviever",
    } <= set(names), names
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


def test_a_tree_copy_LARGER_than_live_while_dropping_live_lines_is_a_finding(tmp_path):
    """The shape every size guard misses, and the one that actually shipped four times tonight.

    Measured on four lanes: each tree copy was BIGGER than the live file it replaced (4,936/6,346/6,046/
    5,714 b against 431/722/4,936/2,811) while dropping 4-32 live lines. A `there > tree` test reports
    nothing; a sync then deletes rules that exist only in the live profile.
    """
    import check_agent_profiles as cap

    agents = tmp_path / "agents"
    prof = agents / "someone"
    prof.mkdir(parents=True)
    # the tree is LONGER, has its own text, and is missing two lines the live file carries
    (prof / "SOUL.md").write_text("a rewritten rule \n" * 60)
    live = tmp_path / "live" / "someone"
    live.mkdir(parents=True)
    (live / "SOUL.md").write_text("a rewritten rule \nthe live-only rule that must not be lost\n"
                                  "another live-only rule\n")
    (agents / "manifest.json").write_text('{"profiles": [{"name": "someone", "rules": ["never-merge"]}]}')

    items = cap.shrink_findings(tmp_path, agents, live.parent)
    assert [i["key"] for i in items] == ["live-lines-missing"], items
    assert "2 line(s)" in items[0]["detail"]
    # which line is named first is sorted order, so assert the class rather than the instance
    assert "live-only" in items[0]["detail"]


def test_a_tree_that_only_DUPLICATES_live_lines_is_not_refused(tmp_path, capsys):
    """A subset that loses nothing is harmless: the sync deletes no rule, so refusing it teaches --force.

    Found while putting the canonical fleet block into every SOUL: the tree became 16,694 b against live
    10,824 b, every tree line already existed live (the block had been appended twice), and `shrinks()`
    refused while reporting "the tree file is SMALLER" and "would delete 0 line(s)". A guard that fires when
    no rule is lost is a guard people route around.
    """
    import agent_profile_sync as sync

    agents = tmp_path / "agents"
    (agents / "someone").mkdir(parents=True)
    live = tmp_path / "live"
    live.mkdir()
    rule = "- one long operating rule that matters\n"
    (live / "SOUL.md").write_text(rule)
    (agents / "someone" / "SOUL.md").write_text(rule * 3)      # larger, but adds nothing live lacks

    assert sync.write(agents, "someone", live) == 0
    assert "REFUSED" not in capsys.readouterr().out


def test_the_refusal_does_not_call_a_larger_tree_SMALLER(tmp_path, capsys):
    """The message has to name the case it is, because "SMALLER" over a larger file is the reader's trap."""
    import agent_profile_sync as sync

    agents = tmp_path / "agents"
    (agents / "someone").mkdir(parents=True)
    live = tmp_path / "live"
    live.mkdir()
    # every tree line exists in live (so it IS a subset) but the tree is larger, because it repeats one;
    # and it drops two live rules — the case where "SMALLER" was the wrong description
    kept = "- kept rule " + "x" * 200 + "\n"
    (live / "SOUL.md").write_text(kept + "- dropped one\n- dropped two\n")
    (agents / "someone" / "SOUL.md").write_text(kept * 3)

    rc = sync.write(agents, "someone", live)
    captured = capsys.readouterr()          # one call: a second readouterr() returns empty
    text = captured.out + captured.err
    assert rc != 0
    assert "SMALLER" not in text, text
    assert "drops live ones" in text, text


def test_the_two_directions_are_exclusive_so_a_finding_names_the_damage(tmp_path):
    """One file, one finding: `live-longer` (a sync would shrink live) or `live-lines-missing` (a sync would
    delete live-only rules) — never both, because the detail a reader acts on is whichever damage applies.
    """
    import check_agent_profiles as cap

    agents = tmp_path / "agents"
    prof = agents / "someone"
    prof.mkdir(parents=True)
    (prof / "SOUL.md").write_text("short\n")                        # shorter AND missing live lines
    live = tmp_path / "live" / "someone"
    live.mkdir(parents=True)
    (live / "SOUL.md").write_text("a longer live rulebook\n" * 40)
    (agents / "manifest.json").write_text('{"profiles": [{"name": "someone", "rules": ["never-merge"]}]}')

    items = cap.shrink_findings(tmp_path, agents, live.parent)
    assert [i["key"] for i in items] == ["live-longer"], items
    assert "live-lines-missing" not in " ".join(i["key"] for i in items)


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

# --- fleet rule 13: a hold without a remedy is abandonment (issue #948, rule in #873) -------------------


def test_this_lane_s_soul_carries_the_fleet_hold_rule():
    """The rule must be in the SOUL, not only in the skill that spells out the procedure.

    `mergeStateStatus` reads `BLOCKED` identically for a real defect and a forgotten tag, so the constraint
    has to be present before the situation is met. The fleet block (#873) states it; this lane's SOUL is
    what a session actually reads, and a skill is only loaded when its trigger matches — which a hold
    review does not.
    """
    soul = (REPO / "agents" / "llgenie-issse-implementer" / "SOUL.md").read_text().lower()
    block = (REPO / "agents" / "standing-rules.md").read_text().lower()

    assert "never hold a pr without a remedy" in block, "the fleet block lost rule 13"
    assert "never hold a pr without a remedy" in soul, "this SOUL does not carry rule 13"
    for commitment in ["file the issue that will make the tag removable",
                       "remove the tag myself",
                       "is a review, not a label"]:
        assert commitment in soul, f"rule 13 in the SOUL is missing: {commitment}"


def test_the_hold_procedure_is_in_the_skill_that_governs_prs():
    """The SOUL states the constraint; the skill states what to do, in order, where the work happens."""
    ref = (REPO / "agents" / "llgenie-issse-implementer" / "skills" / "containerized-repo-verification"
           / "references" / "queue-and-pr-mechanics.md").read_text().lower()

    assert "a hold is a debt with a named creditor" in ref
    for step in ["is a review",
                 "leave the label off",
                 "file the issue that makes the tag removable",
                 "exact condition for removal",
                 "remove the tag yourself",
                 "close the issue"]:
        assert step in ref, f"the hold procedure is missing a step: {step}"
    assert "no issue number" in ref and "no tag" in ref, "the no-issue-no-tag rule is not stated"


# --- fleet rule 14: announce the work, talk to the lane you overlap (#873) -----------------------------


def test_this_lane_s_soul_carries_the_fleet_announce_rule():
    """Rule 14 is a claim discipline, so it has to be in the text read at session start.

    Every collision tonight — a stale head quoted by two reviewers, a force-push over a tick's briefing,
    a PR called CONFLICTING while another lane held its worktree — was two lanes on one branch with no
    announcement. A rule kept in a DM is a rule the next reader cannot find.
    """
    # Prose wraps: a rule split across two lines still states the rule, so the assertion normalises
    # whitespace. Asserting the wrapped form would fail on a reformat and pass on a genuine edit.
    soul = " ".join((REPO / "agents" / "llgenie-issse-implementer" / "SOUL.md").read_text().lower().split())
    block = " ".join((REPO / "agents" / "standing-rules.md").read_text().lower().split())

    assert "announce the work where the work lives" in block, "the fleet block lost rule 14"
    assert "announce the work where the work lives" in soul, "this SOUL does not carry rule 14"
    for commitment in ["comment on the issue or pr",
                       "re-read that thread",
                       "message that lane directly",
                       "post the conclusion in the issue",
                       "a conversation first, a command second"]:
        assert commitment in soul, f"rule 14 in the SOUL is missing: {commitment}"


def test_the_skill_says_a_merged_pr_keeps_its_flags():
    """The trap that authorised a re-cut of an already-merged PR, pinned where the procedure lives.

    #847 merged at 08:36:01Z; a briefing still described it as cross=true / DIRTY thirty-four minutes later
    and authorised a re-cut whose only effect would have been deleting 4,869 lines. The lesson is a command
    order, not an anecdote: check `state,mergedAt` before planning work against a PR number.
    """
    ref = " ".join((REPO / "agents" / "llgenie-issse-implementer" / "skills" / "containerized-repo-verification"
                    / "references" / "queue-and-pr-mechanics.md").read_text().lower().split())

    assert "a merged pr keeps its flags" in ref
    for phrase in ["before planning work against it",
                   "is the content actually on main",
                   "would only delete work",
                   "a branch that is behind main is not a branch that needs re-cutting"]:
        assert phrase in ref, f"the merged-PR trap is missing: {phrase}"


def test_the_bookend_and_fresh_base_procedure_is_in_the_skill():
    """Fleet rule 15 (issue #873): branch from a freshly fetched main, bookend with two comments.

    The operative half has to be where the work happens, not only in the SOUL's statement of the rule. A
    stale base is the parent of the three findings in the reference (ratchet baseline, dead index row, lint
    rule that did not exist at cut), and an unbookended job is how the blame gets mis-assigned.
    """
    ref = " ".join((REPO / "agents" / "llgenie-issse-implementer" / "skills" / "containerized-repo-verification"
                    / "references" / "queue-and-pr-mechanics.md").read_text().lower().split())

    assert "bookend the work, and start from a freshly fetched main" in ref
    for step in ["never from a sha quoted in a chat message",
                 "branch from that pr's tip and name both shas",
                 "start comment",
                 "finish comment",
                 "report the same two lines to the planner",
                 "a start with no finish is an abandoned claim"]:
        assert step in ref, f"rule 15's operative half is missing a step: {step}"


def test_the_announce_procedure_is_in_the_skill_that_governs_prs():
    """The SOUL states the constraint; the skill states the four steps and the command that proves them."""
    ref = " ".join((REPO / "agents" / "llgenie-issse-implementer" / "skills" / "containerized-repo-verification"
                    / "references" / "queue-and-pr-mechanics.md").read_text().lower().split())

    assert "before the first edit: claim, re-read, message the lane" in ref
    for step in ["claim first, in the place the work lives",
                 "re-read the thread before your first edit",
                 "message the overlapping lane directly",
                 "post the conclusion in the issue",
                 "a conversation first, a command second"]:
        assert step in ref, f"the announce procedure is missing a step: {step}"
    assert "gh pr view <n> --json headrefoid" in ref, "the pre-push check is not named"


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


def test_a_newer_live_file_the_write_cannot_damage_is_not_refused(tmp_path, capsys, monkeypatch):
    """The mtime is a proxy; the HARM is losing a line the other lane wrote.

    Found by using the guard: every file had been written by the lane's own sync two minutes earlier, so a
    newer mtime refused a write that would have destroyed nothing — three files byte-identical and two where
    the live lines were a subset of the tree's. A guard that fires there is a guard people learn to `--force`.
    """
    sync, agents, live, _, live_text = _moving_fixture(tmp_path, monkeypatch)
    # live is NEWER, but the tree already carries every live line plus its own
    (agents / "someone" / "SOUL.md").write_text(live_text + "- a rule this tree adds\n")
    os.utime(live / "SOUL.md", (1_700_000_600, 1_700_000_600))

    assert sync.write(agents, "someone", live) == 0
    text = capsys.readouterr().out
    assert "REFUSED" not in text and "NEWER than the source commit" not in text, text
    assert (live / "SOUL.md").read_text().endswith("a rule this tree adds\n")


def test_an_identical_file_is_not_refused_for_being_newer(tmp_path, capsys, monkeypatch):
    """A sync of a byte-identical file writes nothing, so a newer mtime cannot be a reason to stop."""
    sync, agents, live, tree_text, _ = _moving_fixture(tmp_path, monkeypatch)
    (live / "SOUL.md").write_text(tree_text)                      # identical now
    os.utime(live / "SOUL.md", (1_700_000_600, 1_700_000_600))

    assert sync.write(agents, "someone", live) == 0
    assert "REFUSED" not in capsys.readouterr().out


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


def test_every_manifest_profile_names_a_directory_that_exists():
    """The other half of "never assert an exact list": the entries must resolve (#873).

    A subset assertion keeps the list extensible, but on its own it lets a TYPO through - a manifest
    entry naming a profile that has no `agents/<name>/SOUL.md` would be gated by nothing and synced
    nowhere. The rule is the member exists; the referent is that it is real.
    """
    profiles = guard.profiles_from_manifest(REPO / "agents")

    missing = [profile["name"] for profile in profiles
               if not (REPO / "agents" / profile["name"] / "SOUL.md").is_file()]

    assert not missing, (
        "these manifest entries name no agents/<name>/SOUL.md, so nothing gates them and the sync "
        f"target has nothing to copy (#873): {missing}")


# ---------------------------------------------------------------------------------------------------
# issue #873: the canonical fleet block lives ONCE, and every profile's SOUL must state it verbatim.
# The gate compares, names the profile and the first missing bullet, and refuses to pass by not looking.
FLEET_HEAD = "## Standing rules (fleet, learned 2026-10-28)"
BLOCK = FLEET_HEAD + "\n\n- **Never merge without the owner's approval.** A merge needs a human.\n" \
                    "- **Never prune a worktree.** Measure, report, never delete.\n"


def fleet_tree(tmp_path: Path, stated: str | None = BLOCK, canonical: str = BLOCK) -> Path:
    """A tree whose single copy and one profile's SOUL can disagree independently."""
    root = fixture_tree(tmp_path)
    (root / "agents" / "standing-rules.md").write_text("# Standing rules (fleet)\n\n" + canonical,
                                                       encoding="utf-8")
    write_soul(root / "agents", "llgenie-planner",
               SOUL_ORCHESTRATOR + ("\n" + stated if stated else ""))
    return root


def test_a_soul_that_states_the_canonical_block_verbatim_passes(tmp_path):
    root = fleet_tree(tmp_path)
    assert guard.findings(root) == []


def test_a_soul_missing_a_canonical_bullet_fails_and_names_it(tmp_path):
    """The gap must be actionable: which profile, and which bullet."""
    root = fleet_tree(tmp_path, stated=FLEET_HEAD + "\n\n- **Never merge without the owner's approval.** "
                                                  "A merge needs a human.\n")
    items = guard.findings(root)
    keys = [i["key"] for i in items]
    assert "fleet-block-drift" in keys, items
    detail = next(i["detail"] for i in items if i["key"] == "fleet-block-drift")
    assert "llgenie-planner" in detail, detail
    assert "Never prune a worktree" in detail, detail      # the first missing bullet, quoted


def test_deleting_the_single_copy_does_not_let_the_drift_pass(tmp_path):
    """A tree where a SOUL claims the heading but the canonical file is gone must fail, not skip."""
    root = fleet_tree(tmp_path)
    (root / "agents" / "standing-rules.md").unlink()
    keys = [i["key"] for i in guard.findings(root)]
    assert "fleet-block-source" in keys, keys


def test_an_exemption_holds_the_drift_open_but_goes_stale_once_the_profile_is_fixed(tmp_path):
    """An exemption is a named debt, never an amnesty: the moment the gap closes it must be reported."""
    root = fleet_tree(tmp_path, stated=FLEET_HEAD + "\n\n- **Never merge without the owner's approval.** "
                                                   "A merge needs a human.\n")
    exemptions = root / "agents" / "fleet-block-exemptions.json"
    exemptions.write_text(json.dumps({"exemptions": [
        {"profile": "llgenie-planner", "reason": "lane owns its own SOUL", "owner": "#834"}]}),
        encoding="utf-8")
    assert guard.findings(root) == []                       # exempted: real, owned, not a failure

    write_soul(root / "agents", "llgenie-planner", SOUL_ORCHESTRATOR + "\n" + BLOCK)   # the lane fixes it
    keys = [i["key"] for i in guard.findings(root)]
    assert "fleet-exemption-stale" in keys, keys            # … and the list must now be corrected


def test_an_exemption_without_a_written_reason_is_a_finding(tmp_path):
    root = fleet_tree(tmp_path)
    (root / "agents" / "fleet-block-exemptions.json").write_text(
        json.dumps({"exemptions": [{"profile": "llgenie-planner", "reason": "   ", "owner": "#834"}]}),
        encoding="utf-8")
    keys = [i["key"] for i in guard.findings(root)]
    assert "fleet-exemptions" in keys, keys


def test_an_exemption_without_an_owner_is_a_finding(tmp_path):
    """A gap with no owner is a gap nobody closes — the reason alone is not enough (#873)."""
    root = fleet_tree(tmp_path)
    (root / "agents" / "fleet-block-exemptions.json").write_text(
        json.dumps({"exemptions": [{"profile": "llgenie-planner", "reason": "the lane will do it"}]}),
        encoding="utf-8")

    items = guard.findings(root)
    detail = next(i["detail"] for i in items if i["key"] == "fleet-exemptions")
    assert "owner" in detail, detail


def test_the_gate_still_has_the_fleet_block_leg():
    """A merge that silently drops the leg would ungate three profiles without failing anything (#873).

    This PR carries the foundation that #877 also carries. If #877 lands *after* it, the base gate reverts
    to comparing only the rules a manifest declares - no error, no finding, three profiles quietly
    unchecked. So the leg itself is asserted to exist, which turns a bad merge order into a red test.
    """
    assert callable(getattr(guard, "fleet_block", None)), "the canonical-block reader is gone"
    assert callable(getattr(guard, "_fleet_findings", None)), "the fleet-block leg is gone from findings()"

    # and it is actually reached from findings(), not merely defined
    source = (REPO / "scripts" / "check_agent_profiles.py").read_text()
    assert "items.extend(_fleet_findings(" in source, "findings() no longer calls the fleet-block leg"


def test_report_lists_an_exempted_debt_so_it_is_never_silent(tmp_path):
    """`report` is where a reader looks to see what the gate is NOT failing on (#873).

    An exemption keeps the build green on purpose; if it also kept the gap invisible, the fleet block would
    decay exactly where nobody was looking. So the debt must appear BY NAME, with the reason it is allowed.
    """
    root = fleet_tree(tmp_path, stated=FLEET_HEAD + "\n\n- **Never merge without the owner's approval.** "
                                                   "A merge needs a human.\n")
    (root / "agents" / "fleet-block-exemptions.json").write_text(json.dumps({"exemptions": [
        {"profile": "llgenie-planner", "reason": "the lane authors its own block", "owner": "#834"}]}),
        encoding="utf-8")

    assert guard.findings(root) == []                       # exempted: green on purpose
    text = guard.report(root)
    assert "llgenie-planner" in text, text                  # … but named, never silent
    assert "the lane authors its own block" in text, text
    assert "fleet block" in text.lower(), text


# ---------------------------------------------------------------------------------------------------
# issue #791, measured on this host: an in-tree planner seed was 20,297 b against a live 100,031 b, and
# 5,149 b against 7,509 b. A sync would have replaced live behaviour with a fraction of itself, green.
LIVE_ONLY = "\n## Live-only section\n\n" + ("a rule that exists only live\n" * 40)


def sync_fixture(tmp_path: Path, live_soul: str | None) -> tuple[Path, Path]:
    """A one-profile tree plus a destination holding the live copy (or nothing at all)."""
    tree = tmp_path / "tree"
    (tree / "agents" / "llgenie-planner").mkdir(parents=True)
    (tree / "agents" / "manifest.json").write_text(
        json.dumps({"profiles": [{"name": "llgenie-planner",
                                  "rules": ["never-implement", "never-merge"]}]}), encoding="utf-8")
    (tree / "agents" / "llgenie-planner" / "SOUL.md").write_text(SOUL_ORCHESTRATOR, encoding="utf-8")
    dest = tmp_path / "live"
    if live_soul is not None:
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "SOUL.md").write_text(live_soul, encoding="utf-8")
    return tree, dest



# --- the architect lane states the rules its manifest declares (#873, #791) --------------------------------


def test_the_architect_soul_states_the_rules_its_manifest_declares():
    """The declaration and the statement have to exist together; either one alone is a hole.

    Measured on the base (`ce14dd36`): `agents/manifest.json` lists `llgenie-architect` with `"rules": []` and
    the SOUL never mentions merging or implementing, so `check-agent-profiles` reports
    `UNPROTECTED … declares no standing rule` — green, and protecting nothing. Declaring a rule the SOUL does
    not state is the other failure: it reds with `FAIL standing-rule … no longer states never-implement`. Both
    halves are asserted here because either one alone reads as fine. Whitespace is normalised: prose wraps.
    """
    import json

    soul = " ".join((REPO / "agents" / "llgenie-architect" / "SOUL.md").read_text().lower().split())
    manifest = json.loads((REPO / "agents" / "manifest.json").read_text())
    entry = next(p for p in manifest["profiles"] if p["name"] == "llgenie-architect")

    assert entry["rules"] == ["never-implement", "never-merge"], entry["rules"]
    assert "you do not implement" in soul, "the architect SOUL no longer states never-implement"
    assert "never merge" in soul, "the architect SOUL no longer states never-merge"
    assert "auto=none" in soul, \
        "the lane's no-auto-merge instruction must sit beside the fleet rule it overrides"


def test_the_declaration_is_what_protects_the_rule(tmp_path):
    """Three states of the same contract: undeclared is silent, declared-and-deleted reds, stated is clean.

    The silent direction is the point: a profile that declares nothing cannot fail on a rule it never declared,
    which is why the declaration is load-bearing rather than decoration.
    """
    import json

    import check_agent_profiles as cap

    def tree(name: str, rules, state_it: bool):
        agents = tmp_path / name
        prof = agents / "lane"
        prof.mkdir(parents=True)
        (prof / "SOUL.md").write_text(
            "# Lane\n\n## Rules\n\n" + ("- **You never merge.**\n" if state_it else "- **You review.**\n"))
        (agents / "manifest.json").write_text(
            json.dumps({"profiles": [{"name": "lane", "rules": rules}]}))
        return agents

    def standing(name, rules, state_it):
        return [i for i in cap.findings(tmp_path / f"root-{name}", tree(name, rules, state_it))
                if i["key"] == "standing-rule"]

    assert standing("undeclared", [], False) == [], "an empty rules array cannot fail on an undeclared rule"
    assert standing("declared", ["never-merge"], False), "declaring the rule must make its absence a finding"
    assert standing("kept", ["never-merge"], True) == [], "a stated rule must pass"


def test_the_soul_states_the_current_arming_directive_and_labels_the_older_one_superseded():
    """The owner changed the rule on 2026-10-29; the block must say which sentence is live.

    Measured risk: the older instruction ("no squash/auto-merge/push to main") and the newer directive ("set the
    PRs to automerge when the work is done") contradict each other, and a block that merely keeps both leaves a
    reader to guess. Deleting the old quote to make the new rule pass is the other failure — rules 13/14 are
    explicit that a standing rule is stated, and that a removed rule leaves no record of the change. So: the
    current directive is stated, and the older quote survives **labelled superseded with its date**.
    """
    soul = " ".join((REPO / "agents" / "llgenie-architect" / "SOUL.md").read_text().lower().split())

    assert "arm the pr when the work is done" in soul, "the SOUL does not state the current arming directive"
    assert "done" in soul and "armed" in soul, "the SOUL does not say that done means armed"
    for keep in ["never squashes by hand", "never pushes to `main`", "stops at the reviewable pr"]:
        assert keep in soul, f"the directive's permanent half is missing: {keep}"
    assert "superseded 2026-10-29" in soul, "the older instruction is not labelled superseded with its date"
    assert "never merge prs (no squash/auto-merge/push to main)" in soul, \
        "the older quote was deleted to let the new rule pass — keep it, labelled"
    # The live sentence must not still be the retired one.
    assert "this lane does not arm auto-merge" not in soul, \
        "the SOUL still states the superseded no-arming rule as live"


# --- fleet rule 15: a pass against a stale tree is a census of the past (#873) ----------------------------


def test_the_architect_soul_carries_fleet_rule_15_verbatim():
    """Rule 15 is the one this lane earned both ways: one finding dead, one decisive, same night.

    A retracted "truncated seed" claim measured against a head that had already moved, and a re-measurement
    at the freshest sha that found rules 13-14 missing from all seven SOULs, are the same lane on the same
    night. The rule lives in the text a session reads, not in a lesson someone remembers. Whitespace is
    normalised because prose wraps and asserting the wrapped form measures formatting, not the rule.
    """
    soul = " ".join((REPO / "agents" / "llgenie-architect" / "SOUL.md").read_text().lower().split())

    assert "start from a fresh upstream main" in soul, "the architect SOUL lost rule 15"
    for commitment in ["git fetch upstream main",
                       "at the sha you fetched in that moment",
                       "write the sha you branched from into your first comment",
                       "one comment when you start",
                       "one when you finish",
                       "an abandoned claim"]:
        assert commitment in soul, f"rule 15 in the SOUL is missing: {commitment}"


def test_the_pass_skill_puts_the_sha_in_the_census_header_and_bookends():
    """The SOUL states the constraint; the skill states where a pass starts and ends (rule 15)."""
    skill = " ".join((REPO / ".hermes" / "skills" / "llgenie-architecture-pass"
                      / "SKILL.md").read_text().lower().split())

    for step in ["start from a fresh upstream main, and put the sha in the census header",
                 "census header",
                 "one comment when you start",
                 "one comment when you finish",
                 "the sha fetched in that moment"]:
        assert step in skill, f"rule 15 in the skill is missing: {step}"


def test_the_pass_skill_refuses_a_finding_whose_path_cannot_be_opened():
    """A `where:` that does not resolve is a defect in the reporter, and this lane learned it the hard way.

    Measured tonight: `check_agent_profiles` reported `zz9/agents/llgenie-architect/SOUL.md` from
    `--root /tmp/zz9` and `w/agents/…` from `--root /w`, because `agents.parents[1]` is one level above the
    repository (issue #973). A report built on such a path sends the implementer to a file that does not
    exist, and two path conventions in one output is how a reviewer stops trusting paths altogether and
    loses the sha the finding was measured at.
    """
    skill = " ".join((REPO / ".hermes" / "skills" / "llgenie-architecture-pass"
                      / "SKILL.md").read_text().lower().split())

    assert "a finding that names a path you cannot open is a finding about the reporter" in skill
    for demand in ["open it from the repo root", "the measurement is wrong", "#973",
                   "two path conventions in one output"]:
        assert demand in skill, f"the path-check rule in the skill is missing: {demand}"

