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
    #
    # This asserted the EXACT list once, and it went red the moment a fourth lane joined the tree while
    # this branch was open - measured at 62ebbff, before any change of mine: the manifest carried three
    # profiles and the assertion required two. An exact list is a snapshot of the tree's membership, not
    # a rule about it; the rule is that these two are listed and that every listed profile is gated.
    assert {"llgenie-planner", "llgenie-issse-implementer"} <= set(names), names
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


def test_the_ci_maintainer_soul_carries_the_canonical_block_verbatim():
    """The fleet block is one text, not thirteen paraphrases (#873 acceptance criterion 1).

    `check_agent_profiles.py` gates the rules a manifest DECLARES; it does not compare the canonical block,
    which is how a profile can carry ten of eleven bullets and still pass. This compares byte-for-byte
    against the single committed copy, so the drift is a failing test - proven by the negative control in
    the PR: remove one bullet from `agents/standing-rules.md` and this reds.
    """
    heading = "## Standing rules (fleet, learned 2026-10-28)"
    canonical_file = (REPO / "agents" / "standing-rules.md").read_text()
    soul = (REPO / "agents" / "llgenie-ci-pipelines-maintainer" / "SOUL.md").read_text()

    # the canonical block is the heading plus everything this file states under it, to its end
    canonical = heading + "\n\n" + canonical_file.split(heading, 1)[1].strip("\n")
    stated = heading + "\n\n" + soul.split(heading, 1)[1].split("\n## This lane's rules", 1)[0].strip("\n")

    assert canonical in soul, "the canonical block is not stated verbatim in the CI-maintainer SOUL.md"
    # and it is the WHOLE fleet section - a subset that merely appears is not the same claim
    assert stated == canonical, "the SOUL's fleet section must be exactly the canonical block"


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


def test_sync_refuses_to_replace_a_longer_live_file(tmp_path):
    """A truncated in-tree copy must not overwrite the rulebook a running agent actually loads."""
    live = SOUL_ORCHESTRATOR + LIVE_ONLY
    tree, dest = sync_fixture(tmp_path, live)

    result = run_sync("--profile", "llgenie-planner", "--dest", str(dest), "--root", str(tree))

    assert result.returncode == 1, result.stderr
    assert "REFUSED" in result.stderr and "SOUL.md" in result.stderr, result.stderr
    assert "SHRINK" in result.stderr, result.stderr
    assert (dest / "SOUL.md").read_text(encoding="utf-8") == live, "the live file must be untouched"


def test_force_writes_anyway_when_the_shrink_is_intended(tmp_path):
    """`--force` is the explicit way to say the shorter copy is the one that is wanted."""
    tree, dest = sync_fixture(tmp_path, SOUL_ORCHESTRATOR + LIVE_ONLY)

    result = run_sync("--profile", "llgenie-planner", "--dest", str(dest), "--root", str(tree), "--force")

    assert result.returncode == 0, result.stderr
    assert (dest / "SOUL.md").read_text(encoding="utf-8") == SOUL_ORCHESTRATOR


def test_a_first_sync_into_an_empty_home_is_never_a_shrink(tmp_path):
    """The guard must not block the ordinary case: nothing live yet means nothing to protect."""
    tree, dest = sync_fixture(tmp_path, None)

    result = run_sync("--profile", "llgenie-planner", "--dest", str(dest), "--root", str(tree))

    assert result.returncode == 0, result.stderr
    assert (dest / "SOUL.md").is_file()


def test_check_names_a_truncated_tree_copy_as_a_truncation(tmp_path):
    """`--check` must not report a truncated copy as a neutral "differs" — the direction is the danger.

    The live file is longer, so syncing would DELETE live behaviour. Saying "differs, run make
    sync-agent-profile to make the profile the repository's copy" is exactly the instruction that
    destroys it, which is how a 100 kB rulebook became 20 kB with a green gate (issue #791).
    """
    live = SOUL_ORCHESTRATOR + LIVE_ONLY
    tree, dest = sync_fixture(tmp_path, live)
    (tree / "agents" / "llgenie-planner" / "SOUL.md").write_text(
        SOUL_ORCHESTRATOR.replace("Never merge", "Do not merge"), encoding="utf-8")

    result = run_sync("--profile", "llgenie-planner", "--dest", str(dest), "--root", str(tree), "--check")

    assert result.returncode == 1, result.stderr
    assert "TRUNCATED?" in result.stderr, result.stderr
    assert "would SHRINK" in result.stderr, result.stderr
    assert "do not sync it until it is re-copied" in result.stderr, result.stderr


def test_check_does_not_cry_truncation_when_the_tree_copy_is_longer(tmp_path):
    """The inverse: a tree copy that is merely newer and larger is a normal drift, not a truncation."""
    tree, dest = sync_fixture(tmp_path, SOUL_ORCHESTRATOR)
    (tree / "agents" / "llgenie-planner" / "SOUL.md").write_text(
        SOUL_ORCHESTRATOR + "\n## Newer rule\n\nadded upstream\n", encoding="utf-8")

    result = run_sync("--profile", "llgenie-planner", "--dest", str(dest), "--root", str(tree), "--check")

    assert result.returncode == 1, result.stderr          # it still differs …
    assert "TRUNCATED?" not in result.stderr, result.stderr   # … but it is not a truncation
