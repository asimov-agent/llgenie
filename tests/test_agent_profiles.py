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
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

import scripts.check_agent_profiles as guard  # noqa: E402  (the real gate, never a copy)
import scripts.profile_drift_alarm as drift   # noqa: E402  (the drift-alarm caller, real, wired here)

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
    """The committed orchestrator SOUL states both rules in its own voice, not by quoting them."""

    # Given the committed planner SOUL.md
    text = (REPO / "agents" / "llgenie-planner" / "SOUL.md").read_text(encoding="utf-8")

    # When  each standing rule is matched against what the file STATES
    stated = guard.stated_text(text)

    # Then  both are stated, and the strip that removes quotations kept them
    for rule, pattern in guard.STANDING_RULES.items():
        assert pattern.search(stated), f"agents/llgenie-planner/SOUL.md no longer states {rule}"


QUOTED_ONLY_SOUL = """# LLGenie Orchestrator

**Role:** fixture orchestrator

You do not implement. A branch or a PR from you is a mistake.

This lane does not arm auto-merge: the owner's instruction to this profile is the stricter one:
*"Never merge PRs (no squash/auto-merge/push to main): every merge needs the user's approval; stop at
the reviewable PR."* Where a fleet rule and a direct owner instruction disagree, the owner wins.
"""

STATED_AND_QUOTED_SOUL = """# LLGenie Architect

**Role:** fixture architect

**You do not implement and you never merge.** You measure, file and refine issues, and review other
lanes' PRs.

**This lane does not arm auto-merge — a standing owner instruction overrides the fleet rule.** The
owner's instruction to this profile is the stricter one:
*"Never merge PRs (no squash/auto-merge/push to main): every merge needs the user's approval; stop at
the reviewable PR."* Where a fleet rule and a direct owner instruction disagree, the owner wins.
"""


def test_a_soul_that_only_quotes_never_merge_is_rejected(tmp_path):
    """Issue #922's sabotage: quoting the rule must not satisfy the gate for stating it.

    Before this test existed, ``re.compile(r"never\\s+merge").search(text)`` matched the QUOTE, so a
    SOUL whose statement was deleted — while its lane section still cited the owner's instruction —
    printed OK and exited 0.
    """

    # Given a SOUL whose only mention of never-merge is a quotation of the owner's instruction
    root = fixture_tree(tmp_path)
    write_soul(root / "agents", "llgenie-planner", QUOTED_ONLY_SOUL)

    # When  the gate reads the tree
    items = guard.findings(root, guard.AGENTS_DIR)

    # Then  the quotation is not a statement: the finding names the file AND the rule
    quoted = [item for item in items if item["key"] == "standing-rule-quoted"]
    assert quoted, items
    assert quoted[0]["where"] == "agents/llgenie-planner/SOUL.md"
    assert "never-merge" in quoted[0]["detail"]
    # And it is a DIFFERENT finding from a rule that was deleted outright, so a reader knows which
    assert "standing-rule" not in {item["key"] for item in items}


def test_a_rule_inside_a_fence_or_a_blockquote_is_also_only_quoted(tmp_path):
    """A fenced sample and a blockquote are the other two shapes a quotation takes (issue #922)."""

    # Given one SOUL that mentions never-merge only in a fenced block, and one only in a blockquote
    fenced = fixture_tree(tmp_path / "fenced")
    write_soul(fenced / "agents", "llgenie-planner",
               "# LLGenie Orchestrator\n\nYou do not implement.\n\n```\nNever merge PRs.\n```\n")
    quoted_line = fixture_tree(tmp_path / "quoted")
    write_soul(quoted_line / "agents", "llgenie-planner",
               "# LLGenie Orchestrator\n\nYou do not implement.\n\n> Never merge without approval.\n")

    # When  the gate reads each tree
    # Then  neither shape puts the agent under the rule
    for root in (fenced, quoted_line):
        assert "standing-rule-quoted" in keys(root), root


def test_a_stated_rule_passes_even_when_the_soul_also_quotes_it(tmp_path):
    """The live shape of #921's architect SOUL: statement plus quotation must PASS, not fail.

    This is the case a naive "fail any file containing the words inside quotation marks" reds — a
    correct SOUL that states its rule *and* documents the owner instruction it overrides.
    """

    # Given a SOUL that states the rule and also quotes the owner's instruction
    root = fixture_tree(tmp_path)
    write_soul(root / "agents", "llgenie-planner", STATED_AND_QUOTED_SOUL)

    # When  the gate reads the tree and the strip is applied directly
    stated = guard.stated_text(STATED_AND_QUOTED_SOUL)

    # Then  nothing is a finding, the statement survives the strip, and the quotation does not
    assert guard.findings(root, guard.AGENTS_DIR) == []
    assert "you never merge" in stated.lower()
    assert "owner's approval; stop at the reviewable" not in stated


def test_a_profile_with_no_declared_rules_is_reported_unprotected(tmp_path):
    """`rules: []` is "unenforced", not "nothing to check" — it must never read as a pass (#922)."""

    # Given a manifest entry that declares no standing rule
    root = fixture_tree(tmp_path, profiles=[{"name": "llgenie-planner", "rules": []}])

    # When  the gate reports what it reads
    rendered = guard.report(root)

    # Then  the profile is named UNPROTECTED, and no standing-rule finding claims it passed
    assert "UNPROTECTED" in rendered
    assert "llgenie-planner" in rendered.split("UNPROTECTED", 1)[1]
    assert guard.unprotected(guard.profiles_from_manifest(root / "agents")) == ["llgenie-planner"]
    assert "standing-rule" not in keys(root)
    assert "standing-rule-quoted" not in keys(root)


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


def test_a_live_write_to_a_skill_reference_is_a_cron_path_finding(tmp_path, monkeypatch):
    """A live-only write to a skill's `references/*.md` (the dirty-watch cron's own path class) is caught.

    Issue #1156 measured the exact shape: the dirty-watch cron appended lesson lines to the LIVE
    `references/pitfalls.md` (17391 -> 19096 b) after a PR had just cleared the lane's drift row.
    `make sync-agent-profile` is one-way (tree -> live), so that write can never return to the tree
    and the gate must report it. The gate walks every tree file including a skill's `references/`,
    so this asserts behaviour on the skill-reference path, not on SOUL.md (which prior tests cover).
    """
    import os

    import check_agent_profiles as cap

    agents = tmp_path / "agents"
    prof = agents / "someone"
    skill = prof / "skills" / "llgenie-pr-rebase" / "references"
    skill.mkdir(parents=True)
    (prof / "SOUL.md").write_text("short\n")
    tree_pit = skill / "pitfalls.md"
    tree_pit.write_text("- a versioned lesson line\n")
    (agents / "manifest.json").write_text('{"profiles": [{"name": "someone", "rules": ["never-merge"]}]}')

    # Given a live mirror that a cron appended a lesson to (longer + edited AFTER the tree commit).
    live = tmp_path / "live" / "someone"
    live_ref = live / "skills" / "llgenie-pr-rebase" / "references"
    live_ref.mkdir(parents=True)
    (live / "SOUL.md").write_text("short\n")
    live_pit = live_ref / "pitfalls.md"
    live_pit.write_text("- a versioned lesson line\n- a cron lesson written only into the live profile\n")
    src = cap.source_time(agents, "someone", tree_pit)
    os.utime(live_pit, (src + 600, src + 600))

    # When the gate reads it (the live home is the parent of the per-profile directory)
    monkeypatch.setenv("HERMES_PROFILES_HOME", str(live.parent))
    items = cap.findings(tmp_path, agents)

    # Then the live-only skill-reference write fires the drift keys
    keys = {i["key"] for i in items}
    assert "live-longer" in keys, items
    assert "live-edited-not-tree" in keys, items
    pitfalls = [i for i in items if "pitfalls.md" in i["where"]]
    assert pitfalls, items
    assert {"live-longer", "live-edited-not-tree"} <= {i["key"] for i in pitfalls}, items


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


def test_the_live_finding_names_the_reference_age_not_only_its_size(tmp_path):
    """A size without an age cannot be reproduced; the same numbers minutes later read differently (#924).

    Measured on #919: tree 22,175 b against a live 24,791 b, then against a live 21,349 b minutes later.
    The finding changed verdict while the tree was byte-identical, so the message has to carry when the
    reference was read.
    """
    import re

    import check_agent_profiles as cap

    agents = tmp_path / "agents"
    prof = agents / "someone"
    prof.mkdir(parents=True)
    (prof / "SOUL.md").write_text("short\n")
    live = tmp_path / "live" / "someone"
    live.mkdir(parents=True)
    (live / "SOUL.md").write_text("a much longer live rulebook\n" * 100)
    (agents / "manifest.json").write_text('{"profiles": [{"name": "someone", "rules": ["never-merge"]}]}')

    item = cap.shrink_findings(tmp_path, agents, live.parent)[0]
    assert "live mtime" in item["detail"], item["detail"]
    stamp = re.search(r"live mtime (\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)", item["detail"])
    assert stamp, f"the finding carries no parsable timestamp: {item['detail']}"


def test_a_live_file_rewritten_during_the_check_is_reported_as_a_snapshot(tmp_path):
    """The reference is not frozen: another lane rewrites it mid-review, so the verdict is a snapshot.

    `started` is the moment the check began. A live file newer than that changed underneath the run, and
    the caveat says so instead of implying a still reference; an older file produces no caveat at all, so
    the sentence means something when it appears.
    """
    import time

    import check_agent_profiles as cap

    agents = tmp_path / "agents"
    (agents / "someone").mkdir(parents=True)
    (agents / "someone" / "SOUL.md").write_text("the same rulebook\n")
    live = tmp_path / "live" / "someone"
    live.mkdir(parents=True)
    (live / "SOUL.md").write_text("the same rulebook\n")
    (agents / "manifest.json").write_text('{"profiles": [{"name": "someone", "rules": ["never-merge"]}]}')

    moved = cap.snapshot_caveat(tmp_path, agents, live.parent, started=0)
    assert moved and "changed WHILE this check was reading it" in moved, moved
    assert "SNAPSHOT" in moved and "re-run to confirm" in moved, moved
    # Negative control: a reference older than the run start says nothing at all.
    assert cap.snapshot_caveat(tmp_path, agents, live.parent, started=time.time() + 3600) is None


def test_the_snapshot_note_is_audible_in_the_check_and_is_not_a_failure(tmp_path, capsys, monkeypatch):
    """Announcing a moving reference must not red the tree: the tree is not the party that changed."""
    import check_agent_profiles as cap

    agents = tmp_path / "agents" / "someone"
    agents.mkdir(parents=True)
    (agents / "SOUL.md").write_text("# Someone\n\n## Rules\n\n- never merge\n")
    (tmp_path / "agents" / "manifest.json").write_text(
        '{"profiles": [{"name": "someone", "rules": ["never-merge"]}]}')
    live = tmp_path / "profiles" / "someone"
    live.mkdir(parents=True)
    (live / "SOUL.md").write_text("# Someone\n\n## Rules\n\n- never merge\n")
    monkeypatch.setenv("HERMES_PROFILES_HOME", str(tmp_path / "profiles"))
    monkeypatch.setattr(cap, "_STARTED", 0.0)          # every live file counts as changed during the run

    assert cap.main(["check", "--root", str(tmp_path), "--agents-dir", "agents"]) == 0
    captured = capsys.readouterr()
    assert "SNAPSHOT" in captured.err, captured.err
    assert "moved DURING this run, so the comparison is a snapshot" in captured.out, captured.out


def test_a_live_file_edited_after_sync_is_a_finding_naming_the_profile(tmp_path):
    """A live-only edit — a hand write with no tree change — becomes a NAMED finding, not a re-take.

    The live profile is a copy the tree feeds; editing it directly with no tree change is the exact
    drift #968 exists to end. `live-edited-not-tree` must name the profile, both sizes and the remedy
    (commit the edit via issue+PR under agents/<profile>), so a re-take or a silent sync cannot pass.
    """
    import os

    import check_agent_profiles as cap

    os.mkdir(tmp_path / "agents")
    agents = tmp_path / "agents"
    (agents / "someone").mkdir(parents=True)
    (agents / "someone" / "SOUL.md").write_text("a committed tree copy\n")
    (agents / "manifest.json").write_text('{"profiles": [{"name": "someone", "rules": ["never-merge"]}]}')

    # Given a live profile the tree was synced into, then edited by hand AFTER the tree copied out.
    live = tmp_path / "live" / "someone"
    live.mkdir(parents=True)
    live_soul = live / "SOUL.md"
    live_soul.write_text("a committed tree copy\na live-only rule someone wrote by hand\n")
    # No git history in the fixture, so source_time falls back to the tree file mtime; make the live
    # file's mtime clearly newer so the guard uses the mtime signal, not a tie.
    src = cap.source_time(agents, "someone", agents / "someone" / "SOUL.md")
    os.utime(live_soul, (src + 600, src + 600))

    # When the gate reads it
    items = cap.live_edited_findings(tmp_path, agents, live.parent)

    # Then it is one finding naming the profile and both sizes, with the one-way remedy
    assert [i["key"] for i in items] == ["live-edited-not-tree"], items
    assert items[0]["where"] == "someone/SOUL.md", items[0]
    detail = items[0]["detail"]
    assert "someone" in detail, detail
    assert "b" in detail, detail  # both sizes are named ('the tree has N b, the live profile has M b')
    assert "issue+PR under agents/someone/" in detail, detail
    assert "one-way" in detail, detail


def test_a_tree_to_live_sync_clears_the_live_edited_finding(tmp_path):
    """The remedy #968 names clears the finding: the tree carries the edit, a tree→live sync follows.

    The sync is one-way (tree → live). A live-only edit is a finding; once that edit lands in the tree
    (the issue+PR under agents/<profile>), a real tree→live sync overwrites the live copy with identical
    bytes and the finding disappears. This drives the REAL script, not a copy of its logic.
    """

    # Given a tree whose profile is synced into a temporary live home, then the live copy is hand-edited
    agents = tmp_path / "agents"
    prof = agents / "someone"
    prof.mkdir(parents=True)
    (prof / "SOUL.md").write_text("a committed tree copy\n")
    (agents / "manifest.json").write_text('{"profiles": [{"name": "someone", "rules": ["never-merge"]}]}')
    profiles_root = tmp_path / "profiles"          # the profiles-home the gate reads (parent of one home)
    home = profiles_root / "someone"               # the profile's Hermes home the sync writes into
    assert run_sync("--profile", "someone", "--root", str(tmp_path),
                    "--dest", str(home)).returncode == 0

    # When the live file is edited by hand (no tree change yet) — the finding appears
    live_soul = home / "SOUL.md"
    live_soul.write_text("a committed tree copy\na live-only rule\n")
    import os

    import check_agent_profiles as cap

    src = cap.source_time(agents, "someone", prof / "SOUL.md")
    os.utime(live_soul, (src + 600, src + 600))
    assert cap.live_edited_findings(tmp_path, agents, profiles_root) != []  # the finding exists

    # And once the edit lands in the tree and a tree→live sync runs again
    (prof / "SOUL.md").write_text("a committed tree copy\na live-only rule\n")
    assert run_sync("--profile", "someone", "--root", str(tmp_path),
                    "--dest", str(home)).returncode == 0

    # Then the finding clears — behaviour, not text
    assert cap.live_edited_findings(tmp_path, agents, profiles_root) == []
    assert cap.shrink_findings(tmp_path, agents, profiles_root) == []




def test_no_live_profile_home_means_the_comparison_is_skipped_not_failed(tmp_path):
    """CI has no `~/.hermes/profiles/`; a gate that cannot see the live files must say nothing, not fail."""
    import check_agent_profiles as cap

    agents = tmp_path / "agents"
    (agents / "someone").mkdir(parents=True)
    (agents / "someone" / "SOUL.md").write_text("x\n")
    (agents / "manifest.json").write_text('{"profiles": [{"name": "someone", "rules": ["never-merge"]}]}')
    assert cap.shrink_findings(tmp_path, agents, None) == []


# ---- the reverse direction: a live file with no tree twin (issue #1069) -----------------------------


def _mirror(tmp_path: Path, skill: str = "llgenie-bot-orchestration") -> tuple[Path, Path, Path]:
    """A tree profile AND its live mirror, identical: (root, agents dir, live profiles home).

    The live side is a whole profile home, not just the skill, because that is what the gate reads on a
    host — and it is why the reverse comparison has to bound the surface it walks. The Hermes home's
    own `skills/` (the library every profile is seeded from) is created beside `profiles/`, because
    that is where the gate looks for it when it decides what is a lane's own skill.
    """
    root = tmp_path / "tree"
    agents = root / "agents"
    (agents / "someone" / "skills" / skill).mkdir(parents=True)
    (agents / "manifest.json").write_text('{"profiles": [{"name": "someone", "rules": ["never-merge"]}]}')
    soul = "# S\n\nNever merge anything; every merge needs the owner.\n"
    (agents / "someone" / "SOUL.md").write_text(soul)
    (agents / "someone" / "skills" / skill / "SKILL.md").write_text(
        SKILL_BODY.format(name=skill))
    (agents / "someone" / "skills" / skill / "references").mkdir()
    (agents / "someone" / "skills" / skill / "references" / "known.md").write_text("known\n")

    live_home = tmp_path / "profiles" / "someone"
    (live_home / "skills" / skill / "references").mkdir(parents=True)
    (live_home / "SOUL.md").write_text(soul)
    (live_home / "skills" / skill / "SKILL.md").write_text(SKILL_BODY.format(name=skill))
    (live_home / "skills" / skill / "references" / "known.md").write_text("known\n")
    write_shared_library(tmp_path)
    return root, agents, live_home.parent


def write_shared_library(tmp_path: Path, names: tuple[str, ...] = ("docx", "p5js")) -> Path:
    """The Hermes home's own `skills/`: the library every profile on the host is seeded from.

    It sits beside the `profiles/` directory, which is the only structural way to tell a lane's own
    skill from the ~116 skills the machine installs into every profile (issue #1086).
    """
    library = tmp_path / "skills"
    for name in names:
        d = library / "productivity" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(SKILL_BODY.format(name=name))
    return library


def _lane_tree(tmp_path: Path, tree_skills: dict[str, str] | None = None) -> tuple[Path, Path, Path]:
    """A tree profile whose `skills/` is EMPTY (the five-lane shape) and a live profile mirroring it.

    `tree_skills` maps a relative skill path to a file the tree carries there; the live side gets the
    same path plus whatever the test adds. Returns (root, agents dir, live profiles home).
    """
    root = tmp_path / "tree"
    agents = root / "agents"
    (agents / "someone").mkdir(parents=True)
    (agents / "manifest.json").write_text('{"profiles": [{"name": "someone", "rules": ["never-merge"]}]}')
    soul = "# S\n\nNever merge anything; every merge needs the owner.\n"
    (agents / "someone" / "SOUL.md").write_text(soul)
    for rel in (tree_skills or {}):
        path = agents / "someone" / "skills" / rel / "SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(SKILL_BODY.format(name=path.parent.name))
    live_home = tmp_path / "profiles" / "someone"
    live_home.mkdir(parents=True)
    (live_home / "SOUL.md").write_text(soul)
    for rel in (tree_skills or {}):
        path = live_home / "skills" / rel / "SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(SKILL_BODY.format(name=path.parent.name))
    write_shared_library(tmp_path)
    return root, agents, live_home.parent


def test_a_whole_live_only_skill_directory_is_one_finding_naming_lane_path_and_count(tmp_path):
    """The measured defect (#1086): five lanes carry no `skills/` in the tree, so nothing was gated."""

    # Given a tree profile with no skills/ at all, and a live profile that runs a whole lane skill
    root, agents, profiles = _lane_tree(tmp_path)
    skill = profiles / "someone" / "skills" / "software-development" / "llgenie-lane-skill"
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_text(SKILL_BODY.format(name="llgenie-lane-skill"))
    (skill / "references" / "a.md").write_text("a\n")

    # When  the gate runs
    items = guard.absent_from_tree_findings(root, agents, profiles)

    # Then  ONE finding names the lane, the directory's path and its file count — not one per file
    assert [i["key"] for i in items] == ["absent-from-tree"], items
    assert items[0]["where"] == "someone/skills/software-development/llgenie-lane-skill", items[0]
    assert "2 file(s)" in items[0]["detail"], items[0]["detail"]
    assert "agents/someone/skills/" in items[0]["detail"], items[0]["detail"]


def test_a_whole_live_only_skill_directory_beside_the_skill_md_is_named(tmp_path):
    """A warning whose presence depends on how it is spelled is the test being wrong, not the gate:
    assert the path the message carries, never one sentence shape."""

    # Given a tree skill the lane has versioned, and a second live skill directory beside it
    root, agents, profiles = _lane_tree(tmp_path, {"llgenie-bot-orchestration": ""})
    (profiles / "someone" / "skills" / "llgenie-bot-orchestration" / "SKILL.md").write_text(
        SKILL_BODY.format(name="llgenie-bot-orchestration"))
    extra = profiles / "someone" / "skills" / "llgenie-second-skill"
    extra.mkdir(parents=True)
    (extra / "SKILL.md").write_text(SKILL_BODY.format(name="llgenie-second-skill"))

    # When  the gate runs
    wheres = [i["where"] for i in guard.absent_from_tree_findings(root, agents, profiles)]

    # Then  only the unmirrored directory is named, at its own path
    assert wheres == ["someone/skills/llgenie-second-skill"], wheres


def test_the_library_hermes_installs_is_not_a_lane_skill(tmp_path):
    """The bundle manifest and the hub lock are Hermes's own records of what it installed (structural,
    not a name list): a skill either record names is the machine's library, never this lane's."""

    # Given a live profile whose skills/ carries a bundled skill, a hub package, and the shared library
    root, agents, profiles = _lane_tree(tmp_path)
    skills = profiles / "someone" / "skills"
    skills.mkdir(parents=True, exist_ok=True)
    (skills / ".bundled_manifest").write_text("docx:5dec2bad528191d2a82c1b0d4270d6a3\n")
    (skills / ".hub").mkdir()
    (skills / ".hub" / "lock.json").write_text(json.dumps({"installed": {"notion": {"source": "hub"}}}))
    for name in ("docx", "notion"):
        d = skills / "productivity" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(SKILL_BODY.format(name=name))
    shared = profiles / "skills" / "health" / "shared-only"
    shared.mkdir(parents=True)
    (shared / "SKILL.md").write_text(SKILL_BODY.format(name="shared-only"))

    # When  the gate runs
    items = guard.absent_from_tree_findings(root, agents, profiles)

    # Then  none of the library is a finding — the manifest, the lock and the shared home all count
    assert items == [], items


def test_a_skill_symlinked_out_of_the_profile_is_not_a_lane_skill(tmp_path):
    """A profile symlinks host-wide skills in (`diagnose-crash -> /usr/share/omarchy/…`); the file
    lives outside the profile and was never this lane's to version."""

    # Given a live profile whose skills/ holds a symlink to a directory outside it
    root, agents, profiles = _lane_tree(tmp_path)
    target = tmp_path / "usr-share" / "diagnose-crash"
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text(SKILL_BODY.format(name="diagnose-crash"))
    (profiles / "someone" / "skills").mkdir(parents=True, exist_ok=True)
    (profiles / "someone" / "skills" / "diagnose-crash").symlink_to(target, target_is_directory=True)

    # When  the gate runs
    items = guard.absent_from_tree_findings(root, agents, profiles)

    # Then  the symlink is not a finding
    assert items == [], items


def test_a_tree_category_directory_is_not_a_skill(tmp_path):
    """The 52-finding false positive: `skills/software-development/` is Hermes's CATEGORY, not a skill.

    Measured at `d5fb875c`: the tree carries `agents/llgenie-pr-reviever/skills/software-development/
    llgenie-pr-review/`, and treating the category as a skill made the reverse direction report the
    whole live category — 52 `absent-from-tree` findings, all shared library, burying the real ones.
    """

    # Given a tree skill nested in a category, and a live category carrying the same skill plus the
    # shared library beside it
    root, agents, profiles = _lane_tree(tmp_path, {"software-development/llgenie-pr-review": ""})
    live = profiles / "someone" / "skills" / "software-development"
    for name in ("docx", "p5js"):
        d = live / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(SKILL_BODY.format(name=name))

    # When  the gate runs
    items = guard.absent_from_tree_findings(root, agents, profiles)

    # Then  the mirrored skill and the library are silent
    assert items == [], items

    # And a file the live mirrored skill carries but the tree does not is named, not the category
    (live / "llgenie-pr-review" / "REFERENCE.md").write_text("x\n")
    assert [i["where"] for i in guard.absent_from_tree_findings(root, agents, profiles)] == \
        ["someone/skills/software-development/llgenie-pr-review/REFERENCE.md"]


def test_the_check_fails_naming_a_live_only_directory_and_passes_once_it_is_removed(tmp_path,
                                                                                    monkeypatch, capsys):
    """The negative control the issue asks for, both directions, through the REAL entry point."""

    # Given a tree and a live profile that agree
    root, _agents, profiles = _lane_tree(tmp_path)
    monkeypatch.setenv("HERMES_PROFILES_HOME", str(profiles))
    assert guard.main(["check", "--root", str(root)]) == 0
    capsys.readouterr()

    # When  a whole skill directory exists only in the live profile
    live = profiles / "someone" / "skills" / "software-development" / "llgenie-lane-skill"
    live.mkdir(parents=True)
    (live / "SKILL.md").write_text(SKILL_BODY.format(name="llgenie-lane-skill"))

    # Then  the gate fails and names the path
    assert guard.main(["check", "--root", str(root)]) == 1
    out = capsys.readouterr().out
    assert "FAIL absent-from-tree: someone/skills/software-development/llgenie-lane-skill" in out, out

    # And when it is removed the gate passes again
    (live / "SKILL.md").unlink()
    live.rmdir()
    assert guard.main(["check", "--root", str(root)]) == 0


def test_no_shared_library_means_the_directory_comparison_is_skipped_not_guessed(tmp_path,
                                                                                 monkeypatch, capsys):
    """Without the library the gate cannot tell a lane's skill from the machine's, so it must say it
    did not compare instead of naming the whole library (a skip must be audible, never silent)."""

    # Given a live profiles home with NO shared library beside it
    root, _agents, profiles = _lane_tree(tmp_path)
    shutil.rmtree(profiles.parent / "skills")
    monkeypatch.setenv("HERMES_PROFILES_HOME", str(profiles))
    d = profiles / "someone" / "skills" / "llgenie-lane-skill"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(SKILL_BODY.format(name="llgenie-lane-skill"))

    # When  the gate runs
    code = guard.main(["check", "--root", str(root)])

    # Then  it does not invent the finding, and the skip is printed
    err = capsys.readouterr().err
    assert "live-only skill DIRECTORIES were NOT compared" in err, err
    assert guard.absent_from_tree_findings(root, _agents, profiles) == []
    assert code == 0, code


def test_findings_is_the_union_of_the_reverse_directions_with_the_new_key(tmp_path, monkeypatch):
    """`findings()` must carry the directory finding too: `check` and `report` both read that list."""

    # Given a live-only file and a live-only whole directory under one lane
    root, agents, profiles = _mirror(tmp_path)
    monkeypatch.setenv("HERMES_PROFILES_HOME", str(profiles))
    (profiles / "someone" / "skills" / "llgenie-bot-orchestration" / "EXTRA.md").write_text("x\n")
    whole = profiles / "someone" / "skills" / "llgenie-lane-skill"
    whole.mkdir(parents=True)
    (whole / "SKILL.md").write_text(SKILL_BODY.format(name="llgenie-lane-skill"))

    # When  every direction runs over the same tree
    items = guard.findings(root)

    # Then  both shapes are in `findings()`, and the union drops nothing
    wheres = {i["where"] for i in items if i["key"] == "absent-from-tree"}
    assert {"someone/skills/llgenie-bot-orchestration/EXTRA.md",
            "someone/skills/llgenie-lane-skill"} <= wheres, items
    assert all(i in items for i in guard.absent_from_tree_findings(root, agents, profiles))




def test_a_live_only_reference_file_is_a_finding_naming_profile_and_path(tmp_path):
    """The measured defect: 21 planner references exist only in the live profile and were invisible."""

    # Given a tree whose skill carries references/known.md, and a live mirror that also carries
    # references/new-tonight.md
    root, agents, profiles = _mirror(tmp_path)
    live = profiles / "someone" / "skills" / "llgenie-bot-orchestration" / "references"
    (live / "new-tonight.md").write_text("a rule written only on the host\n")

    # When  the gate runs
    items = guard.absent_from_tree_findings(root, agents, profiles)

    # Then  exactly one finding names the lane, the skill, the path and the live size
    assert [i["key"] for i in items] == ["absent-from-tree"], items
    assert items[0]["where"] == \
        "someone/skills/llgenie-bot-orchestration/references/new-tonight.md", items[0]
    assert f"({(live / 'new-tonight.md').stat().st_size} b)" in items[0]["detail"], items[0]["detail"]
    assert "agents/someone/skills/llgenie-bot-orchestration/" in items[0]["detail"], items[0]["detail"]


def test_a_live_only_file_beside_the_skill_md_is_a_finding(tmp_path):
    """Not only under `references/`: a file at the skill's root is named by its own relative path."""

    # Given a live skill directory carrying a file the tree does not have, beside SKILL.md
    root, agents, profiles = _mirror(tmp_path)
    (profiles / "someone" / "skills" / "llgenie-bot-orchestration" / "REFERENCE.md").write_text("x\n")

    # When  the gate runs
    items = guard.absent_from_tree_findings(root, agents, profiles)

    # Then  the finding names REFERENCE.md at the skill root
    assert [i["where"] for i in items] == \
        ["someone/skills/llgenie-bot-orchestration/REFERENCE.md"], items


def test_a_clean_mirror_reports_nothing_and_one_added_file_does(tmp_path):
    """The control in both directions: an identical mirror is silent, one live-only file is not."""

    # Given a tree and a live profile that are identical
    root, agents, profiles = _mirror(tmp_path)

    # Then  there is nothing to report
    assert guard.absent_from_tree_findings(root, agents, profiles) == []

    # When  one file is added live
    added = profiles / "someone" / "skills" / "llgenie-bot-orchestration" / "references" / "added.md"
    added.write_text("added\n")

    # Then  it is named
    assert [i["where"] for i in guard.absent_from_tree_findings(root, agents, profiles)] == \
        ["someone/skills/llgenie-bot-orchestration/references/added.md"]

    # And when it is removed again the gate is silent once more
    added.unlink()
    assert guard.absent_from_tree_findings(root, agents, profiles) == []


def test_the_profile_data_is_not_reported_by_the_reverse_direction(tmp_path):
    """A live profile is a whole Hermes home; its data is not behaviour and must never be a finding.

    Measured: 4,804 live files for llgenie-planner at `ac12cae9` — `state.db`, `sessions/`, `memories/`,
    `cron/`, `logs/`, `.curator_backups/`, `worker-outboxes/`. Reporting them would bury the 22 files
    that ARE lane behaviour.
    """

    # Given a live profile carrying its own data beside its behaviour
    root, agents, profiles = _mirror(tmp_path)
    home = profiles / "someone"
    for rel, text in (("state.db", "sqlite\n"), ("config.yaml", "k: v\n"), (".env", "A=1\n"),
                      ("sessions/s1.json", "{}\n"), ("memories/m.md", "m\n"), ("logs/run.log", "l\n"),
                      ("cron/jobs.json", "[]\n"), (".curator_backups/blobs/abc", "b\n"),
                      ("worker-outboxes/w/pending.json", "{}")):
        (home / rel).parent.mkdir(parents=True, exist_ok=True)
        (home / rel).write_text(text)

    # When  the gate runs
    items = guard.absent_from_tree_findings(root, agents, profiles)

    # Then  nothing in the profile's data is a finding
    assert items == [], items


def test_the_shared_skill_library_is_not_reported(tmp_path):
    """Hermes bundles the same ~200 skills into every profile; they are not this lane's behaviour."""

    # Given a live profile whose skills/ also carries skills no tree skill directory names
    root, agents, profiles = _mirror(tmp_path)
    for rel in ("productivity/docx/SKILL.md", "creative/p5js/SKILL.md"):
        path = profiles / "someone" / "skills" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("shared\n")

    # When  the gate runs
    items = guard.absent_from_tree_findings(root, agents, profiles)

    # Then  they are not findings: the tree versions no such skill for this lane
    assert items == [], items


def test_bookkeeping_files_beside_a_skill_are_not_reported(tmp_path):
    """The agent tooling writes hidden scratch files itself — a finding for those would be noise."""

    # Given a live skill directory carrying Hermes's own bookkeeping
    root, agents, profiles = _mirror(tmp_path)
    skill = profiles / "someone" / "skills" / "llgenie-bot-orchestration"
    (skill / ".DS_Store").write_text("x\n")
    (skill / "__pycache__").mkdir()
    (skill / "__pycache__" / "m.pyc").write_text("x\n")
    (skill / ".curator_state").write_text("x\n")

    # When  the gate runs
    items = guard.absent_from_tree_findings(root, agents, profiles)

    # Then  none of it is a finding
    assert items == [], items


def test_a_lane_with_no_live_profile_produces_no_reverse_finding(tmp_path):
    """`absent-live` stays a different condition: a lane this host does not run has no live files."""

    # Given a tree listing two profiles, and a live profiles home holding only the first
    root = tmp_path / "tree"
    agents = root / "agents"
    for name in ("someone", "not-on-this-host"):
        (agents / name / "skills" / "s").mkdir(parents=True)
        (agents / name / "SOUL.md").write_text("# S\n")
        (agents / name / "skills" / "s" / "SKILL.md").write_text(SKILL_BODY.format(name="s"))
    (agents / "manifest.json").write_text(
        '{"profiles": [{"name": "someone", "rules": []}, {"name": "not-on-this-host", "rules": []}]}')
    live_home = tmp_path / "profiles" / "someone"
    (live_home / "skills" / "s").mkdir(parents=True)
    (live_home / "SOUL.md").write_text("# S\n")
    (live_home / "skills" / "s" / "SKILL.md").write_text(SKILL_BODY.format(name="s"))

    # When  the gate runs
    items = guard.absent_from_tree_findings(root, agents, live_home.parent)

    # Then  the absent lane is silent — neither a reverse finding nor an error
    assert items == [], items


def test_the_check_fails_naming_a_live_only_file_and_passes_once_it_is_removed(tmp_path, monkeypatch,
                                                                             capsys):
    """The negative control, both directions, through the REAL entry point.

    A gate that fails only in a unit fixture is unproven: this drives `main(["check", …])` against a
    `HERMES_PROFILES_HOME` fixture, so the exit code a `&&` chain reads is the one asserted.
    """

    # Given a tree and an identical live profile, read through the gate's own env var
    root, _agents, profiles = _mirror(tmp_path)
    monkeypatch.setenv("HERMES_PROFILES_HOME", str(profiles))

    # Then  the gate passes
    assert guard.main(["check", "--root", str(root)]) == 0
    out = capsys.readouterr().out
    assert "no file exists only in the live profile" in out, out

    # When  one file exists only in the live profile
    added = profiles / "someone" / "skills" / "llgenie-bot-orchestration" / "references" / "added.md"
    added.write_text("a rule that never reached the tree\n")

    # Then  the gate fails and names it
    assert guard.main(["check", "--root", str(root)]) == 1
    out = capsys.readouterr().out
    assert "FAIL absent-from-tree: someone/skills/llgenie-bot-orchestration/references/added.md" in out, out

    # And when the file is removed the gate passes again
    added.unlink()
    assert guard.main(["check", "--root", str(root)]) == 0


def test_report_lists_the_absent_from_tree_finding(tmp_path, monkeypatch):
    """`report` is the readable entry point, so the key must appear there too."""

    # Given one live-only file
    root, _agents, profiles = _mirror(tmp_path)
    monkeypatch.setenv("HERMES_PROFILES_HOME", str(profiles))
    (profiles / "someone" / "skills" / "llgenie-bot-orchestration" / "EXTRA.md").write_text("x\n")

    # When  the report is rendered
    text = guard.report(root)

    # Then  it names the path and counts the finding
    assert "absent-from-tree: someone/skills/llgenie-bot-orchestration/EXTRA.md" in text, text
    assert "1 finding(s)" in text, text


def test_the_existing_keys_and_counts_are_unchanged_by_the_reverse_direction(tmp_path, monkeypatch):
    """The three directions coexist: the two older keys keep their counts when the new one fires.

    Measured at `ac12cae9` before this change: 12 `live-longer`, 1 `live-edited-not-tree`. Asserted as a
    shape (one each in the fixture, all three keys present), never as the host's counts — #1060 adds
    findings as lanes are versioned, and an exact list would red on that legitimate work.
    """
    import os

    # Given a live profile whose rulebook is longer (live-longer), was hand-edited
    # (live-edited-not-tree) and carries a file the tree has never held (absent-from-tree)
    root, agents, profiles = _mirror(tmp_path)
    monkeypatch.setenv("HERMES_PROFILES_HOME", str(profiles))   # findings() reads the env, not `live=`
    live_soul = profiles / "someone" / "SOUL.md"
    live_soul.write_text((agents / "someone" / "SOUL.md").read_text()
                         + "\n- a live-only rule written by hand\n")
    src = guard.source_time(agents, "someone", agents / "someone" / "SOUL.md")
    os.utime(live_soul, (src + 600, src + 600))
    (profiles / "someone" / "skills" / "llgenie-bot-orchestration" / "references" / "extra.md") \
        .write_text("extra\n")

    # When  every direction runs over the same tree
    items = guard.findings(root)

    # Then  all three keys are present, and the two older ones are one finding each
    keys = [i["key"] for i in items]
    assert keys.count("live-longer") == 1, items
    assert keys.count("live-edited-not-tree") == 1, items
    assert keys.count("absent-from-tree") == 1, items
    # and `findings()` is the union of its directions: the new one drops nothing the others found
    assert all(i in items for i in guard.shrink_findings(root, agents, profiles))
    assert all(i in items for i in guard.live_edited_findings(root, agents, profiles))
    assert all(i in items for i in guard.absent_from_tree_findings(root, agents, profiles))


def test_a_tree_only_checkout_never_reports_the_reverse_key():
    """CI has no live profiles: the reverse direction must not invent a finding from nothing.

    On the owner's host the same call reports the measured live-only files instead — this asserts the
    tree-only half, which is the half every CI runner exercises.
    """

    # Given a checkout whose host has no live profile directory... (this host may have them, so read
    # the gate's own root: with no profiles home it returns None and the comparison is skipped)
    import check_agent_profiles as cap

    # When  the comparison explicitly has no live base the reverse direction is empty, not an error
    assert cap.absent_from_tree_findings(REPO, cap.AGENTS_DIR, None) == [
        i for i in cap.absent_from_tree_findings(REPO, cap.AGENTS_DIR) if cap.live_root(REPO) is None
    ]
    # Then  every key the gate emits at the committed tree is a known one (no typo'd key ship)
    assert {i["key"] for i in cap.findings(REPO)} <= {
        "absent-from-tree", "live-longer", "live-lines-missing", "live-edited-not-tree",
        "skill-reference-missing", "soul-missing", "profile-directory", "profile-unlisted",
        "manifest-rule", "manifest-missing", "manifest-invalid", "manifest-empty", "manifest-entry",
        "manifest-rule-unknown", "fleet-block-drift", "fleet-exemption-stale", "fleet-exemptions",
        "fleet-exemption-unknown", "fleet-block-source", "standing-rule", "standing-rule-quoted",
        "forbidden-path", "secret", "unreadable", "skill-frontmatter", "skill-name",
        "skill-description",
    }



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


def test_the_make_sync_recipe_wires_FORCE_to_the_force_flag(tmp_path):
    """`FORCE=1` must reach the script as `--force`, or `make sync-agent-profile … FORCE=1` silently
    runs in refuse-mode. Measured on #919's repair: `FORCE` was documented in the help text but never
    passed on the recipe line — `$(if $(CHECK),--check,)` had a sibling, `$(if $(FORCE),--force,)` did
    not. The recipe is what the gate's own callers use, so it gets pinned here, not just the script flag.
    """
    makefile = (REPO / "Makefile").read_text()
    # the recipe line is the one containing scripts/agent_profile_sync.py
    line = next(l for l in makefile.splitlines() if "scripts/agent_profile_sync.py" in l)

    assert "$(if $(FORCE),--force,)" in line, line          # FORCE flows to the script
    assert "$(if $(CHECK),--check,)" in line, line          # and CHECK still flows
    assert "FORCE=1 bypasses the refusal" in makefile, "help text documents FORCE (the documented-but-dead flag is the defect)"
    assert "FORCE=1" in " ".join(l for l in makefile.splitlines() if "Usage: make sync-agent-profile" in l)


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


def test_this_lane_s_soul_carries_each_canonical_rule_once_and_no_retired_bullet():
    """The #973 dedupe: one bullet, one place, and the retired arming rule is gone.

    This lane's SOUL restated rules 13/14 twice (top standing-rules section AND the fleet block) and
    carried the retired "Arm auto-merge at PR creation" bullet that contradicts rule 16 (arm when done).
    The planner measured r13=2 r14=2 r15=1 on this lane. After the dedupe each canonical rule appears
    exactly once (in the fleet block), the retired bullet is absent, and rule 16 (arm when done) survives.
    Any editor who re-adds a duplicate or the retired bullet must make this red.
    """
    soul = (REPO / "agents" / "llgenie-issse-implementer" / "SOUL.md").read_text()
    for title in ["Never hold a PR without a remedy",
                  "Announce the work where the work lives",
                  "Start from a fresh upstream main"]:
        assert soul.count(title) == 1, f"a canonical rule must appear exactly once (it may not be restated): {title}"
    assert "Arm auto-merge at PR creation" not in soul, \
        "the retired arm-at-creation bullet (contradicts rule 16) must not be in this lane's SOUL"
    assert "Arm auto-merge when the work is done, not when it is approved" in soul, \
        "rule 16 (arm when done) must survive the dedupe"


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
                       "remove the tag yourself",
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


def test_the_author_gate_lesson_is_in_the_skill():
    """A display-name ban against main's own authors is a policy change, not a branch fix.

    Measured on #919: my commits report OK (I author `Andy Holst <andy.holst@protonmail.com>`); the 11
    failures are other lanes' `Andy <…>` commits plus one typo'd domain. Re-authoring a mid-history commit
    rewrites every sha after it and strands stacked PRs — so the skill carries the two responses instead of
    teaching the next lane to rewrite shared history for a gate that will never pass.
    """
    ref = " ".join((REPO / "agents" / "llgenie-issse-implementer" / "skills" / "containerized-repo-verification"
                    / "references" / "queue-and-pr-mechanics.md").read_text().lower().split())

    assert "the author allowlist bans a display name" in ref
    for phrase in ["the stable key is the email; the display name is not",
                   "re-authoring a mid-history commit rewrites",
                   "a policy change in the gate's own allowlist",
                   "a conversation first"]:
        assert phrase in ref, f"the author-gate lesson is missing: {phrase}"
    # A re-author ORDER can be stale (3-vs-14) and contradict an earlier no-rewrite ruling:
    # measure at the current head and escalate, never force-push a rewrite that cannot clear the gate.
    for phrase in ["a re-author instruction can itself be built on a stale head",
                   "escalate a contradiction rather than force-push",
                   "email-matching) removes",
                   "cannot clear the gate",
                   "re-measure at the current head before asserting the gate's red size",
                   "a stated count is a snapshot of a head, not a constant",
                   "a snapshot earned by re-measuring, not by trusting the earlier head's number"]:
        assert phrase in ref, f"the stale-count guard is missing: {phrase}"


def test_the_arm_when_done_rule_is_in_the_skill():
    """Owner directive 2026-10-29 (#873): done triggers the arm, not approval.

    The SOUL states the constraint; the skill must carry the operative half — the arm command, the read-back
    that the exit code never is, and the only accepted reason for a finished PR to sit unarmed. Without it,
    a finished PR sits invisible to the merger sweep and waits for a human to notice.
    """
    ref = " ".join((REPO / "agents" / "llgenie-issse-implementer" / "skills" / "containerized-repo-verification"
                    / "references" / "queue-and-pr-mechanics.md").read_text().lower().split())

    assert "arm when the work is done, not when it is approved" in ref
    for phrase in ["the last push, the last check on a finished pr",
                   "gh pr merge <n> --squash --auto",
                   "auto=none (owner instruction)",
                   "read the arm state back in the same comment"]:
        assert phrase in ref, f"the arm-when-done operative half is missing: {phrase}"


def test_the_never_arm_a_stacked_pr_lesson_is_in_the_skill():
    """The #954 hazard: `gh pr merge --auto` on a stacked PR MERGES it into its non-main base.

    #954 auto-merged into feat/agent-profile-implementer-skill at 2026-10-29T08:27:41Z; its commit,
    88abd614, is an ancestor of neither main nor the tree head. A stacked arm is a wrong-branch merge,
    not a no-op, so the skill must teach "never arm a base that is not main", not the stale "has nothing
    to merge into".
    """
    ref = " ".join((REPO / "agents" / "llgenie-issse-implementer" / "skills" / "containerized-repo-verification"
                    / "references" / "queue-and-pr-mechanics.md").read_text().lower().split())

    for phrase in ["a stacked pr (base != `main`) must **never** be armed",
                   "it merges the pr into its non-main base",
                   "ancestor of neither `main` nor the tree head",
                   "never arm a pr whose base is not `main`",
                   "auto=none (stacked, base is not main)"]:
        assert phrase in ref, f"the stacked-arm hazard is missing: {phrase}"

    # The inverse must hold too: the STALE teaching that #954 disproved — "has nothing to merge into"
    # or "cannot be armed, so the arm fails" — is exactly the wrong-rule regression, and it can coexist
    # with any single "never". If it returns, the section has drifted back and must fail.
    assert "has nothing to merge into" not in ref, "the stale no-op teaching has returned"
    assert "cannot be armed, so name that too" not in ref, "the stale 'cannot be armed' teaching has returned"


def test_a_rule_inside_a_fenced_block_is_a_quote_not_a_statement():
    """Pinning the maintainer's offered delta (#956/#944): a pasted example is a quote, not a statement.

    `_stated_block` must NOT treat a fleet block quoted inside Markdown fences as though the SOUL states it
    verbatim — the fence lines break exact equality, so a SOUL that only quotes the block is drift, and the
    gate has to say so rather than passing on a paraphrase one level up.
    """
    import check_agent_profiles as cap

    canonical = cap.fleet_block(REPO / "agents")
    assert canonical is not None, "the fleet block must exist to test against"

    soul_stated = ("# LLGenie X\n\n## Role\n\n" + cap.FLEET_HEADING + "\n\n"
                   + canonical + "\n")
    soul_fenced = ("# LLGenie X\n\n## Role\n\n```\n" + canonical + "\n```\n")

    assert cap._stated_block(soul_stated) == canonical, \
        "a verbatim copy is a statement — it matches the canonical block"
    # the fenced copy still CONTAINS the heading, so a section is found; what must differ is that its
    # body carries the fence markers and is therefore NOT the canonical text
    assert cap._stated_block(soul_fenced) != canonical, \
        "a fenced quote is NOT a statement — the fence lines break exact equality with canonical"


def test_the_duplicate_rule_discriminator_treats_the_period_variant_as_the_same_rule(tmp_path):
    """A duplicate drifts by punctuation before it drifts by text (#972 #922): `remedy.**` and `remedy**`
    are the SAME rule.

    The canonical rule-13 title has a period inside the bold (`**Never hold a PR without a remedy.**`),
    so an editor who re-types it drops the period (`**…remedy**`) and the gate must still count BOTH as
    one rule stated twice — not pass the no-period copy as a different, single bullet. `_duplicate_rule_debts`
    normalises by matching `**<stripped-title><optional-punctuation>**`, so either punctuation variant is
    counted. This is the near-copy the planner keeps catching by hand; now it is a pinned gate property.
    """
    import check_agent_profiles as cap
    import shutil
    from check_agent_profiles import _duplicate_rule_debts
    canonical = cap.fleet_block(REPO / "agents")
    assert canonical is not None, "the fleet block must exist to test against"

    # the real rule-13 title as it appears in the canonical block (with its period)
    per = None
    for line in canonical.splitlines():
        if line.startswith("- **") and "Never hold a PR without a remedy" in line:
            per = line[4: line.find("**", 3)]           # e.g. "Never hold a PR without a remedy."
            break
    assert per is not None and per.endswith("."), f"expected a period-ending title, got {per!r}"
    stripped = per.rstrip(".,:;!?")

    def debts(soul_text):
        # `_duplicate_rule_debts` resolves the canonical rule titles from `standing-rules.md`, so a
        # synthetic agents root must carry it (copied from the real tree) or `fleet_block` returns None
        # and the helper silently counts nothing.
        # Use the test's `tmp_path` (auto-cleaned at the end of the test) instead of `tempfile.mkdtemp()`,
        # which leaks a directory per call.
        agent = tmp_path / "agents"
        shutil.rmtree(agent, ignore_errors=True)   # fresh root per call (three calls in this test)
        agent.mkdir()
        shutil.copy(REPO / "agents" / cap.FLEET_BLOCK, agent / cap.FLEET_BLOCK)
        p = agent / "per-test" / "SOUL.md"
        p.parent.mkdir(parents=True)
        p.write_text(soul_text, encoding="utf-8")
        return _duplicate_rule_debts(agent, [{"name": "per-test"}])

    block_head = "## " + cap.FLEET_HEADING.replace("## ", "") + "\n\n"
    one_each = ("# LLGenie X\n\n" + block_head
                + f"- **{per}** one\n"          # period copy (canonical form)
                + f"- **{stripped}** two\n")     # no-period copy (the drift)
    two_period = ("# LLGenie X\n\n" + block_head
                  + f"- **{per}** one\n" + f"- **{per}** two\n")
    only_one = ("# LLGenie X\n\n" + block_head + f"- **{per}** one\n")

    assert any(name == "per-test" and title == stripped for name, title in debts(one_each)), \
        "a period + no-period copy of the same rule must be counted as a duplicate (same rule)"
    assert any(name == "per-test" and title == stripped for name, title in debts(two_period)), \
        "two identical copies must be counted as a duplicate"
    assert debts(only_one) == [], "one copy of the rule must NOT be a duplicate"


def test_the_prove_it_is_safe_to_push_before_push_lesson_is_in_the_skill():
    """A push into a head with a `queued` run cancels that verdict — never infer safety from breath.

    The skill teaches "push once then FREEZE the branch", but freezing is only advisory; the operable half
    is the probe that proves a push is safe (`gh api .../commits/<HEAD>/check-runs` → 0 in_progress or
    queued). A branch can be green while a run is still queued, and a push then throws away the very
    verdict the branch was waiting on. This pin holds the probe and the freeze rule in the skill.
    """
    ref = " ".join((REPO / "agents" / "llgenie-issse-implementer" / "skills" / "containerized-repo-verification"
                    / "references" / "queue-and-pr-mechanics.md").read_text().lower().split())

    for phrase in ["prove it is safe to push before you do",
                   "push once, then freeze the branch",
                   "commits/<head>/check-runs",
                   'select(.status=="in_progress" or .status=="queued")',
                   "`0` is the only \"safe to push\"",
                   "but not every `queued` job is the verdict; read the gate, not the count",
                   "is the run the pr's gate actually waits on (`guard`, `check-pr-authors`, `check-agent-profiles`)",
                   "only a detached matrix job lingers"]:
        assert phrase in ref, f"the push-safety probe / gate discriminator lesson is missing: {phrase}"


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
                 "a start with no finish is an abandoned claim",
                 # the fresh-canonical-main rule (owner directive): fetch BEFORE any work, every job
                 "fetch fresh canonical `main` before any other work",
                 "confirm which remote is canonical first",
                 "never from a remote name you *assume* exists",
                 "answer a plan against the current `main`, not a four-heads-old snapshot",
                 # the same-turn re-read (planner 13:20Z): a quoted sha is the past the moment another
                 # lane can push; quote what you just fetched, never what you memorised
                 "re-read the head in the same turn you quote it",
                 "git ls-remote origin refs/heads/<branch>",
                 "a sha is a claim about the past"]:
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


def test_a_count_clean_dedupe_that_paraphrases_the_fence_is_still_refused():
    """Item 10 (#972's sharper edge): a dedupe can be count-clean (one per rule, retired bullet gone)
    and STILL fail `block_in_soul` if its retained fence paraphrases a canonical rule.

    Measured against #919's doc-SOUL at 11dd97d3: the doc offer counted `1 occurrence per rule` with the
    retired bullet gone, yet `_stated_block` differed from canonical because rule 16 had been reworded
    ("Arm when done, and only on a base of main" vs "Arm auto-merge when the work is done, not when it is
    approved"). A take accepted on the count alone imports a gate-red fence. Assert both assertions of the
    refusal: the count discriminator (each canonical rule once) can be satisfied while the fence comparison
    (the gate's real test) is not.
    """
    import check_agent_profiles as cap
    canonical = cap.fleet_block(REPO / "agents")
    assert canonical is not None

    # build a SOUL whose block keeps one copy of each canonical rule but REWORDS rule 16
    reworded = canonical.replace(
        "**Arm auto-merge when the work is done, not when it is approved.**",
        "**Arm when done, and only on a base of `main`.**")
    assert reworded != canonical, "the reworded block must differ from canonical"
    soul = ("# LLGenie X\n\n## Role\n\n" + reworded + "\n")

    # the gate's real test: block in soul must be FALSE under the paraphrase
    assert cap._stated_block(soul) != canonical, \
        "a fence-paraphrasing dedupe must NOT pass block_in_soul even though it is count-clean"


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
    assert "and the content differs: 1 live line(s) the tree lacks" in text, text  # mtime first, then the cost
    assert "of another lane's work" not in text, text  # the tree has no ownership info; never assign blame
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


def test_the_one_bullet_one_place_lesson_is_in_the_skill():
    """Every canonical bullet lives once, then once only (measured on #972 / planner 11:40Z).

    A canonical rule stated twice is a second source of truth that drifts first — the block stays
    canonical while the stray lane-rules copy paraphrases and goes stale (that is how #972's SOUL
    "had 16 bullets" yet was wrong). The skill must teach count-occurrences-not-totals, or the next
    editor ships another duplicate.
    """
    ref = " ".join((REPO / "agents" / "llgenie-issse-implementer" / "skills"
                    / "containerized-repo-verification" / "references"
                    / "agent-profile-tree.md").read_text().lower().split())

    for phrase in ["one canonical bullet, one place",
                   "a duplicate is a second source of truth that drifts first",
                   "count occurrences, not a bullet total",
                   "pin the occurrence count as a red test first",
                   "a lane-offered re-take must pass the gate's own comparison before you take it",
                   "a refusal that keeps the tree green is a result",
                   "a count-clean dedupe can still fail the fence — dedupe is not immunity",
                   "run `_stated_block(live) == fleet_block()` even on a dedupe the lane certifies as count-clean"]:
        assert phrase in ref, f"the re-take-gate-check lesson is missing: {phrase}"


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


def test_no_souls_fleet_block_carries_the_retired_arming_rule():
    """Two arming rules in one block is how a lane obeys the wrong one (measured on #972).

    The canonical fence carried both "Arm auto-merge at PR creation" (old) and "Arm when done, and
    only on a base of main" (rule 16); the old one is retired. A block that states it — in any
    profile's SOUL — contradicts rule 16 and must be a finding, because the gate's verdict is what
    a lane runs under.
    """
    for lane_dir in (REPO / "agents").iterdir():
        if not (lane_dir / "SOUL.md").is_file():
            continue
        soul = (lane_dir / "SOUL.md").read_text(encoding="utf-8")
        block = guard._stated_block(soul)
        if block is None:
            continue
        assert "Arm auto-merge at PR creation" not in block, (
            f"{lane_dir.name}/SOUL.md: retired arming rule is inside the fleet block — contradict "
            f"rule 16 (Arm when done). It belongs in the lane-rules section at most, never in the "
            f"canonical fence the gate compares."
        )


def test_every_real_souls_fleet_block_states_rule_16():
    """Rule 16 (arm when done) must be in every real SOUL's stated block, not only canonical.

    The planner caught three SOULs still carrying the retired arming bullet; the complement is that
    each must carry the replacement — a lane that dropped the old rule but never gained rule 16 would
    have no arming guidance at all.
    """
    canonical = guard.fleet_block(REPO / "agents") or ""
    assert "Arm auto-merge when the work is done" in canonical, "canonical lost rule 16"
    for lane_dir in (REPO / "agents").iterdir():
        if not (lane_dir / "SOUL.md").is_file():
            continue
        block = guard._stated_block((lane_dir / "SOUL.md").read_text(encoding="utf-8")) or ""
        assert "Arm auto-merge when the work is done" in block, (
            f"{lane_dir.name}/SOUL.md stated block lacks rule 16 (arm when done)"
        )


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


def test_the_report_names_duplicate_canonical_rules_and_the_gate_does_not_fail_on_them():
    """A canonical rule stated twice is a second source of truth (one bullet, one place — #972).

    `check-agent-profiles report` must NAME every profile that states a canonical rule more than once,
    while `findings()` (the pass/fail path) must NOT fail on them — removal is a protected SOUL write
    the owner routes, so it is visible debt, not a silent amnesty nor a red the lane cannot clear.

    Follow-up #1006/#1007 deleted the outside-fence duplicates: the doc lane's SOUL was taken in from its
    in-lane write (#1007) so documentation is now clean, and #1008 dedups the other lanes. The durable
    invariant: a lane must NOT be re-flagged when it is clean, the planner's content-bearing `never-push`
    paragraph (its own SOUL, its call to remove) may remain, and implementer stays clean. An exact row
    count would be a moving snapshot — "a snapshot is not a certificate" (#54's lesson).
    """
    report_text = guard.report(REPO)
    names = sorted(l.split(":")[0].strip() for l in report_text.splitlines()
                   if "stated more than once" in l)
    assert names, "report must name at least one duplicate canonical rule"

    # a deduped lane must NOT be named; if any is, the dedupe regressed
    deduped = {"llgenie-documentation-maintainer", "llgenie-issse-implementer",
               "llgenie-ci-pipelines-maintainer", "llgenie-pr-reviever", "llgenie-tester"}
    assert not (deduped & set(names)), f"a deduped lane was re-flagged as a duplicate: {names}"

    # after #1006/#1007/#1008 the ONLY legitimate duplicate is the planner's content-bearing
    # `never-push` paragraph (its own SOUL, its call to remove); #1008 itself cleans the other lanes
    remaining = set(names) - {"llgenie-issse-implementer"}
    assert remaining <= {"llgenie-planner"}, f"an unexpected lane still carries a duplicate: {names}"

    assert all("issse-implementer" not in n for n in names), \
        "implementer's duplicate rule was deduped into the fleet block — it must not be re-flagged"

    # The discriminator is a BOLDED-RULE statement, not a bullet-line-only scan (which under-counts a
    # bold paragraph outside a fence) and not a raw whole-text count (which over-claims a prose mention).
    # The named LANES are the stable contract; a wrong discriminator shifts which lanes appear.
    assert guard.findings(REPO) == []   # duplicates are informational, never a gate failure


def test_the_retired_rule_debt_is_reported_and_never_fails_the_gate(tmp_path):
    """A SOUL still stating the retired arming bullet contradicts rule 16 (#873/#950) — visible, not fatal.

    The retired "Arm auto-merge at PR creation" bullet is neither a canonical title nor (when it appears
    once) a duplicate, so it sat invisible to `findings()`, `_duplicate_rule_debts`, and the fleet-block leg
    (which only reads the stated block). Measured: documentation and pr-reviever each carry it once and the
    gate said nothing. `_retired_rule_debts` is the REPORT debt that makes it visible; like the duplicate
    debt, removal is a protected SOUL write the owner routes, so it must never turn the gate red.
    """
    import check_agent_profiles as cap
    import shutil

    agents = tmp_path / "agents"
    shutil.rmtree(agents, ignore_errors=True)
    agents.mkdir()
    shutil.copy(REPO / "agents" / cap.FLEET_BLOCK, agents / cap.FLEET_BLOCK)
    (agents / "manifest.json").write_text(
        '{"profiles": [{"name": "lane", "rules": ["never-merge"]}]}')
    prof = agents / "lane"
    prof.mkdir()
    soul = ("# Lane\n\n- **Never merge without the owner's approval.**\n\n"
            "## This lane's rules\n\n- **Arm auto-merge at PR creation.** `gh pr merge <n> --squash --auto`\n")
    (prof / "SOUL.md").write_text(soul)

    retired = cap._retired_rule_debts(agents, [{"name": "lane"}])
    assert ("lane", cap.RETIRED_ARM_RULE) in retired, retired
    # report names it, gate stays green: it is debt with an owner route, not a red the lane cannot clear
    assert "retired canonical rule still stated" in cap.report(tmp_path, agents)
    assert "retired" not in {i["key"] for i in cap.findings(tmp_path, agents)}


def test_the_fleet_block_has_one_canonical_lesson_is_in_the_skill():
    """The gate ships with its "compare against fleet_block(), never the issue fence" lesson (#1009).

    Two authorities for rule 16 (agents/standing-rules.md vs #873's fence) is how the planner's
    "take 13,394, block True" got measured against the wrong canonical and shipped an instruction that
    re-introduced a gate red. The lesson must survive the next rewrite of the ref, or the same
    divergent-source mistake returns.
    """
    ref = " ".join((REPO / "agents" / "llgenie-issse-implementer" / "skills"
                    / "containerized-repo-verification" / "references"
                    / "agent-profile-tree.md").read_text().lower().split())
    for phrase in ["the fleet block has one canonical",
                   "never the issue fence",
                   "compares byte-for-byte against `standing-rules.md` only",
                   "measured against the wrong canonical and was withdrawn",
                   "two authorities for one fleet rule",
                   "compare against `fleet_block()`, never a sampled fence"]:
        assert phrase in ref, f"the single-canonical lesson is missing: {phrase}"


def test_the_doc_soul_stated_block_matches_the_gate_canonical():
    """Pin the exact measurement the planner's "+1 retired bullet" claim failed to reproduce (#1005, #1009).

    The doc SOUL's stated block == fleet_block() was asserted FALSE (5,869/20 vs 5,870/21 b) then TRUE
    then FALSE again across planner reads — none reproduced on the gate's own functions. At head 2804433f
    the retired bullet sits at line 108, OUTSIDE the stated-block region (86–106), and the stated block is
    byte-identical to the 18-line canonical fence. Pinning it as a durable regression so the claim can never
    recur unchecked: if the fence drifts, this reds with the name and the first differing line, and the fix
    is a protected in-lane (~#1006/#1008) dedupe, never a from-live copy.
    """
    canonical = guard.fleet_block(REPO / "agents")
    assert canonical is not None, "the canonical fleet block must exist"
    doc = REPO / "agents" / "llgenie-documentation-maintainer" / "SOUL.md"
    stated = guard._stated_block(doc.read_text(encoding="utf-8"))
    assert stated == canonical, (
        "doc SOUL stated block != canonical fleet_block() — the fence drifted. Diff the gate's own "
        "fleet_block() vs _stated_block() and dedupe in-lane; do NOT re-source from live (that reintroduces "
        "the #1009 block-in-soul failure)."
    )


def test_the_ambiguous_refname_lesson_is_in_the_skill():
    """The stale-base-watch lesson: an explicit refspec, never `origin/main` by a short name (#994).

    Measured: `git rev-parse origin/main` returned 6d9fef1d (an old leftover) instead of the real current
    main (238dcd2c), because the short name is ambiguous and resolved to a stale ref — so a base-watch
    claimed #919 was "~1 behind" against a wrong sha. The fresh-main rule must teach the explicit
    `+refs/heads/main:refs/remotes/origin/main` fetch + `refs/remotes/origin/main` read, or the ambiguity
    produces false base-drift reports.
    """
    ref = " ".join((REPO / "agents" / "llgenie-issse-implementer" / "skills"
                    / "containerized-repo-verification" / "references"
                    / "queue-and-pr-mechanics.md").read_text().lower().split())
    for phrase in ["a refname can be ambiguous and read a stale ref",
                   "fetch with an explicit refspec, never `origin/main` by a short name",
                   "`+refs/heads/main:refs/remotes/origin/main`",
                   "the fresh-main rule"]:
        assert phrase in ref, f"the ambiguous-refname lesson is missing: {phrase}"


def test_the_pr_head_is_the_remote_branch_lesson_is_in_the_skill():
    """The halt-dispute lesson, pinned: a PR's head is the REMOTE branch, never a local worktree.

    During the fleet stop, a lane claimed "#919 advanced under the freeze" citing three shas
    (e9c7e7f3, 7e4a8519, 5e74cb68). All three resolved to LOCAL scratch branches (tmp/retake-myskill,
    tmp/lint-fix, pr944-replay) — never pushed — while the remote #919 head was frozen throughout. The
    authoritative read is the remote branch, twice-verified; a disputed sha's membership is an ancestry
    check against origin/<branch>. This pin holds that lesson so a future "your branch moved" claim is
    settled against the remote, not a local read.
    """
    ref = " ".join((REPO / "agents" / "llgenie-issse-implementer" / "skills"
                    / "containerized-repo-verification" / "references"
                    / "queue-and-pr-mechanics.md").read_text().lower().split())
    for phrase in ["a pr's head is the remote branch, not a local worktree or scratch ref",
                   "settled against the remote",
                   "resolved to local scratch branches",
                   "the authoritative read is the remote branch, twice-verified",
                   "git merge-base --is-ancestor <sha> origin/<branch>"]:
        assert phrase in ref, f"the remote-branch-head lesson is missing: {phrase}"


def test_one_vehicle_for_a_gate_follow_on_lesson_is_in_the_skill():
    """The two-vehicle one-line landing rule, pinned so the #824 collision shape cannot recur.

    When #993 and #977 both fix the same email-keyed author gate, the architect co-author line owed by
    each must land on the consolidation WINNER only, never both. The lesson must survive the next rewrite
    of the ref, or a lane pushes the line onto both vehicles and re-creates the collision.
    """
    ref = " ".join((REPO / "agents" / "llgenie-issse-implementer" / "skills"
                    / "containerized-repo-verification" / "references"
                    / "queue-and-pr-mechanics.md").read_text().lower().split())
    for phrase in ["two vehicles for one gate fix",
                   "land the same line on one, never both",
                   "the vehicle that wins the consolidation",
                   "landing it on both is how `#824` became a",
                   "measure the gate's own `aliases`/`allowed` symbol",
                   "co-authored-by: llgenie architect <architect@llgenie.local>"]:
        assert phrase in ref, f"the one-vehicle landing lesson is missing: {phrase}"


def test_the_mergeable_but_behind_rule_is_in_the_skill():
    """#1015's apply decision, pinned: a MERGEABLE-but-behind PR is NOT broken — leave it (#1015).

    On one directive round main moved to f244efe8 while #919/#977/#1008 each read MERGEABLE; all three were
    left in place because a rebase that chases main rewrites shas under stacked children for a verdict the
    arm already holds. The rebase trigger is the PR's own `mergeable` field, never main moving. This pin holds
    the decision (live-wording, authoritative) so a future "main is ahead, rebase it" reflex cannot mis-fire.
    """
    ref = " ".join((REPO / "agents" / "llgenie-issse-implementer" / "skills"
                    / "containerized-repo-verification" / "references"
                    / "queue-and-pr-mechanics.md").read_text().lower().split())
    for phrase in ["an armed branch does not need to chase `main`",
                   "rebase only when the pr is actually `conflicting`, or its base merges",
                   "a branch that is `mergeable` but slightly behind is not broken",
                   "`gh pr view <n> --json mergeable` → `mergeable` means leave it armed and report",
                   "`conflicting` means rebase",
                   "behind-but-clean branch is not a reason to rebase"]:
        assert phrase in ref, f"the #1015 apply decision is missing: {phrase}"


def test_the_oneto_rebase_of_a_stacked_child_lesson_is_in_the_skill():
    """The `--onto` three-argument form, pinned so the drop-the-child mistake cannot recur.

    Measured #1008: `git rebase --onto <new-tip> <own-branch-remote>` has an empty review range and just
    moves the branch to the new tip, silently dropping the child commit. The lesson must teach the correct
    upstream (the OLD parent tip) and the recovery (reset --hard to the still-existing commit), or the next
    stacked-PR rebase repeats it.
    """
    ref = " ".join((REPO / "agents" / "llgenie-issse-implementer" / "skills"
                    / "containerized-repo-verification" / "references"
                    / "queue-and-pr-mechanics.md").read_text().lower().split())
    for phrase in ["rebase --onto <new-parent-tip> <old-parent-tip>",
                   "empty `<old-tip>..head` range",
                   "branch moves to the new tip",
                   "puts the branch back",
                   "merge-base --is-ancestor origin/<parent> head"]:
        assert phrase in ref, f"the `--onto` stacked-rebase lesson is missing: {phrase}"


def test_this_lane_s_soul_uses_the_canonical_rule16_wording_not_the_drifted_fence():
    """The #1009 defect, pinned on the lane that owns it: ONE canonical, the gate's.

    issue #873's body fence states rule 16 as "Arm when done, and only on a base of main"; the gate's
    canonical (agents/standing-rules.md via fleet_block()) states it as "Arm auto-merge when the work is
    done, not when it is approved". `_stated_block()` compares byte-for-byte against standing-rules.md
    only — so a SOUL built from the #873 fence passes a sampler and FAILS the gate (measured: taking the
    doc lane's live 13,394, which matched #873, re-introduced block-in-soul FAIL; planner's instruction
    withdrawn, #1009). This lane's SOUL must state the gate's wording and the drifted wording must not
    appear in its stated block, so the divergent-source mistake cannot return here.
    """
    soul = (REPO / "agents" / "llgenie-issse-implementer" / "SOUL.md").read_text()
    block = guard._stated_block(soul)
    assert block is not None, "this lane's SOUL must state the canonical fence"
    assert "Arm auto-merge when the work is done" in block, \
        "this lane's stated block must carry the gate's canonical rule-16 wording"
    assert "Arm when done, and only on a base of" not in block, \
        "the drifted #873-fence wording must not be in this lane's stated block (it fails the gate)"


def test_the_retired_rule_debt_lesson_is_in_the_skill():
    """The gate change ships with its lesson, or the next editor re-introduces the silent pass.

    `_retired_rule_debts` is behaviour; the skill is why it exists and how to act on it — that the retired
    bullet was invisible to the old gate, that removal is a protected SOUL write (never fix another lane's
    to clear the note), and that keeping report() while dropping the check note re-silences the debt where
    the reviewer runs. This pins those three sentences so the property survives the next rewrite of the ref.
    """
    ref = " ".join((REPO / "agents" / "llgenie-issse-implementer" / "skills"
                    / "containerized-repo-verification" / "references"
                    / "agent-profile-tree.md").read_text().lower().split())
    for phrase in ["the retired arming bullet is gate-named debt",
                   "neither a canonical title nor (appearing once) a duplicate",
                   "the old gate saw nothing",
                   "a protected soul write the owner routes",
                   "do not remove the bullet from another lane's soul to clear the note",
                   "makes the debt silent again"]:
        assert phrase in ref, f"the retired-rule debt lesson is missing: {phrase}"


def test_the_check_command_names_a_so_souls_retired_rule_on_a_green_tree_and_stays_green(tmp_path, capsys):
    """The note a reviewer running `make check-agent-profiles` sees, not just the report() unit.

    `_retired_rule_debts` is wired into TWO surfaces: `report()` and the `check` command's informational
    note. The check-command note only prints when findings() is empty (a red tree goes to the FAIL branch
    before it is reached), so it cannot be pinned against the real repo — which is red on the tester's two
    live-longers. It has to be driven on a synthetic green tree that carries the retired bullet, asserting
    BOTH the note and the exit code, so a future edit cannot delete the note wiring while keeping the
    report() call and the gate green.
    """
    import shutil

    agents = tmp_path / "agents"
    shutil.rmtree(agents, ignore_errors=True)
    agents.mkdir()
    shutil.copy(REPO / "agents" / guard.FLEET_BLOCK, agents / guard.FLEET_BLOCK)
    # a single clean profile: `never-merge` stated plainly (the fleet block does not carry it — it is
    # the orchestrator's rule), the canonical fleet block verbatim (its heading is already the first
    # line of `fleet_block()`), and the retired arming bullet OUTSIDE the block
    canonical = guard.fleet_block(REPO / "agents")
    soul = ("# Lane\n\n**You never merge.**\n\n" + canonical
            + "\n\n## This lane's rules\n\n"
              "- **Arm auto-merge at PR creation.** `gh pr merge <n> --squash --auto`\n")
    prof = agents / "lane"
    prof.mkdir()
    (prof / "SOUL.md").write_text(soul)
    (agents / "manifest.json").write_text(
        '{"profiles": [{"name": "lane", "rules": ["never-merge"]}]}')

    rc = guard.main(["check", "--root", str(tmp_path), "--agents-dir", "agents"])
    captured = capsys.readouterr()
    text = captured.out + captured.err
    assert rc == 0, f"the retired-rule note must not turn the gate red: {text}"
    assert "OK:" in text, text
    assert "retired" in text, text
    assert f"lane still states the retired {guard.RETIRED_ARM_RULE!r}" in text, text
    assert "rule 16 replaced it" in text, text


def test_the_check_command_names_duplicate_rules_but_stays_green(capsys):
    """The gate must not keep duplicate-rule debt silent when green (one bullet, one place, #972).

    `make check-agent-profiles` is what a reviewer runs, so the tree's duplicate canonical rules must
    appear there — as informational `note:` lines that do NOT change the exit code (a protected SOUL
    write the owner routes, not a red the lane cannot clear).
    """
    import subprocess
    proc = subprocess.run(
        [sys.executable, "scripts/check_agent_profiles.py", "check"],
        cwd=REPO, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "OK:" in proc.stdout
    assert "duplicate canonical rule" in proc.stderr, proc.stderr
    assert "more than once" in proc.stderr, proc.stderr


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



# --- fleet orchestration symmetry (#1010) -----------------------------------------------------------------


def test_the_architect_soul_carries_the_orchestration_block():
    """Fleet symmetry: every lane reports to the inbox; a new PR goes to the reviewer; version here (#1010).

    The fleet standing-rules block is the fleet's; this is this lane's own protocol, stated so a session does
    not re-derive it. Each part is asserted separately because leaving one out reads as "done" and is not.
    """
    soul = " ".join((REPO / "agents" / "llgenie-architect" / "SOUL.md").read_text().lower().split())

    assert "orchestration" in soul, "the orchestration heading is missing"
    for demand in ["report back", "@llgenie-planner",
                   "the inbox", "post the head sha, the pr number",
                   "a new pr goes to the reviewer", "@llgenie-pr-reviever",
                   "this lane does not review its own pr",
                   "version here", "make sync-agent-profile profile=llgenie-architect check=1",
                   "byte-identical",
                   "one lane, one pr", "bot-claim:", "agent/issue-"]:
        assert demand in soul, f"the orchestration block is missing: {demand}"


def test_the_architect_soul_rebases_only_on_conflict():
    """Owner rule #1015: stacked PRs are not rebased onto every main move; only an actual CONFLICT does it.

    Rebase-by-mainmove is how a green gets discarded twice — the branch chases a moving base and every
    re-run restarts. So the SOUL states the trigger: rebase only when CONFLICTING, stay stacked, arm on
    retarget. The API-vs-shadow warning is part of it: `origin/main` can be a stale local ref, so read the
    real head from the API when a sha matters.
    """
    soul = " ".join((REPO / "agents" / "llgenie-architect" / "SOUL.md").read_text().lower().split())

    assert "rebase only on conflict" in soul, "the SOUL lost the #1015 rebase rule"
    for demand in ["a rebase is for when a branch is actually",
                   "arm on retarget",
                   "stale shadow",
                   "read the real head from the api"]:
        assert demand in soul, f"the #1015 rebase rule is missing: {demand}"


# --- pipeline maintainer: monitor & route, never rebase (owner 2026-10-30) --------------------------------

def test_the_pipeline_maintainer_soul_monitors_and_routes_never_rebases():
    """Owner re-scope: this lane measures the pipelines and routes reds; it does not rebase PRs.

    The PR-rebase lane owns rebasing. On a red failure the maintainer does three things, so each is
    asserted separately: comment the finding with proof, notify the rebase lane, notify inbox triage.
    """
    soul = " ".join((REPO / "agents" / "llgenie-ci-pipelines-maintainer" / "SOUL.md").read_text().lower().split())

    assert "i monitor the pipelines; i do not rebase prs" in soul, \
        "the re-scoped role line is missing"
    for demand in ["measure", "the rebase lane's job",
                   "@llgenie-pr-merge-conflict", "notify",
                   "@llgenie-planner", "comment the finding",
                   "the measured head"]:
        assert demand in soul, f"the monitor-and-route rule is missing: {demand}"


def test_the_pipeline_maintainer_soul_always_monitors_and_reports_reds_from_logs():
    """Owner behavior: this lane's steady state is watching PR CI runs, reading the failing log,
    and reporting each red to the inbox for it to decide — never from a status badge alone.
    """
    soul = " ".join((REPO / "agents" / "llgenie-ci-pipelines-maintainer" / "SOUL.md").read_text().lower().split())

    assert "always monitor" in soul, "the always-monitor steady state is missing"
    for demand in ["read the failing job's log", "the failing job's log",
                   "@llgenie-planner", "inbox triage", "report", "the log-quoted cause",
                   "cancelled run reads"]:
        assert demand in soul, f"the monitor-and-report-from-log rule is missing: {demand}"


def test_the_pass_skill_carries_orchestration_and_orchestration_rebase():
    """Version-here means both carriers agree: the SOUL has the orchestration + #1015 block, so must the skill.

    A rule that lives only in the SOUL is read at session start; the skill is what loads when a pass runs. If
    the two drift, one of them teaches a different protocol than the other — which is the divergence versioning
    exists to catch (#1010, #1015).
    """
    skill = " ".join((REPO / ".hermes" / "skills" / "llgenie-architecture-pass"
                      / "SKILL.md").read_text().lower().split())

    for demand in ["report back", "@llgenie-planner", "a new pr goes to the reviewer",
                   "@llgenie-pr-reviever", "one lane, one pr", "bot-claim:",
                   "agent/issue-", "rebase only on conflict", "arms on retarget"]:
        assert demand in skill, f"the pass skill lost the orchestration/#1015 lesson: {demand}"


def test_profile_drift_alarm_compares_tree_vs_live_and_names_truncation_direction(tmp_path):
    """The drift-alarm caller reuses the real gate's tree↔live comparison (issue #928).

    Imported and exercised here so the script is part of the CI-wired test graph (a host-only caller is
    recorded by wiring because a runner has no live profiles, but its comparison logic must still run in CI).
    """
    agents = tmp_path / "agents"
    live = tmp_path / "live"
    write_manifest(agents, [{"name": "llgenie-blank"}])
    (agents / "llgenie-blank").mkdir(parents=True, exist_ok=True)
    (agents / "llgenie-blank" / "SOUL.md").write_text("A\n", encoding="utf-8")
    (live / "llgenie-blank").mkdir(parents=True)
    (live / "llgenie-blank" / "SOUL.md").write_text("A\nB\n", encoding="utf-8")

    items = drift.compare(tmp_path, "agents", live)
    kinds = [i["kind"] for i in items]
    assert "truncated" in kinds, "a tree missing live lines must be reported as truncated (#928)"
    assert drift.tracked("SOUL.md") and not drift.tracked("state.db")
def test_fleet_findings_report_repo_relative_paths(tmp_path):
    """A `where:` that cannot be opened from the repo root is a finding about the reporter (#973).

    Measured before the fix: `agents.parents[1]` sits one level above the repository, so a drift finding
    printed `zz9/agents/llgenie-architect/SOUL.md` from `--root /tmp/zz9` and `w/agents/…` from `--root /w`.
    A path the implementer cannot open trains them to grep instead of trust, and a report built on it sends
    them to a file that does not exist.
    """
    import re

    import check_agent_profiles as cap

    agents = tmp_path / "agents"
    (agents / "someone").mkdir(parents=True)
    (agents / "someone" / "SOUL.md").write_text("# Someone\n\n## Rules\n")
    (agents / "manifest.json").write_text('{"profiles": [{"name": "someone", "rules": ["never-merge"]}]}')
    (agents / "standing-rules.md").write_text(
        "## Standing rules (fleet, learned 2026-10-28)\n\n- **Assert behaviour, not text.** a very long "
        "canonical bullet that the SOUL does not state\n")

    items = cap._fleet_findings(agents, cap.read_manifest(agents)[0])
    drift = [i for i in items if i["key"] == "fleet-block-drift"]
    assert drift, "expected a fleet-block-drift finding"
    # the reported path must be openable from the repo root, i.e. start with agents/, never the tmp dir name
    where = drift[0]["where"]
    assert where.startswith("agents/"), f"path is not repo-relative: {where}"
    assert not where.startswith(tmp_path.name), f"repo directory name prefixed: {where}"
    assert not re.match(r"^[A-Za-z0-9_./-]+/agents/.*/.*/SOUL", where), where


def test_the_exemption_path_and_the_drift_path_share_the_convention(tmp_path):
    """The two path-writing styles must agree; a mixed convention is how a reviewer stops trusting paths (#973).

    `path.parents[1]` on the exemptions FILE resolves to the repo root (correct), while `agents.parents[1]`
    on the agents DIR resolves one level above (wrong). If a future edit normalises the wrong one to match
    the right one, or vice versa, the tuple still reads two ways and the checklist here keeps it honest.
    """
    import check_agent_profiles as cap

    agents = tmp_path / "agents"
    (agents / "someone").mkdir(parents=True)
    (agents / "someone" / "SOUL.md").write_text("# Someone\n\n## Rules\n")
    (agents / "manifest.json").write_text('{"profiles": [{"name": "someone", "rules": ["never-merge"]}]}')
    (agents / "standing-rules.md").write_text(
        "## Standing rules (fleet, learned 2026-10-28)\n\n- **Assert behaviour, not text.** x\n")

    # force a stale-exemption shape to exercise that path too
    (agents / "fleet-block-exemptions.json").write_text(
        '{"exemptions": [{"profile": "someone", "reason": "g", "owner": "o"}]}')

    items = cap._fleet_findings(agents, cap.read_manifest(agents)[0])
    for i in items:
        assert i["where"].startswith("agents/"), f"{i['key']} where is not repo-relative: {i['where']}"
        assert i["where"] != "agents/agents/", i["key"]
def test_the_exemption_path_and_the_drift_path_share_the_convention(tmp_path):
    """The two path-writing styles must agree; a mixed convention is how a reviewer stops trusting paths (#973).

    `path.parents[1]` on the exemptions FILE resolves to the repo root (correct), while `agents.parents[1]`
    on the agents DIR resolves one level above (wrong). If a future edit normalises the wrong one to match
    the right one, or vice versa, the tuple still reads two ways and the checklist here keeps it honest.
    """
    import check_agent_profiles as cap

    agents = tmp_path / "agents"
    (agents / "someone").mkdir(parents=True)
    (agents / "someone" / "SOUL.md").write_text("# Someone\n\n## Rules\n")
    (agents / "manifest.json").write_text('{"profiles": [{"name": "someone", "rules": ["never-merge"]}]}')
    (agents / "standing-rules.md").write_text(
        "## Standing rules (fleet, learned 2026-10-28)\n\n- **Assert behaviour, not text.** x\n")

    # force a stale-exemption shape to exercise that path too
    (agents / "fleet-block-exemptions.json").write_text(
        '{"exemptions": [{"profile": "someone", "reason": "g", "owner": "o"}]}')

    items = cap._fleet_findings(agents, cap.read_manifest(agents)[0])
    for i in items:
        assert i["where"].startswith("agents/"), f"{i['key']} where is not repo-relative: {i['where']}"
        assert i["where"] != "agents/agents/", i["key"]
