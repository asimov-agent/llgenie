#!/usr/bin/env python3
"""Does every bot leg load its contract from a project skill, and does the gate say no? (issue #577)

The gate is real code under test (`scripts/check_agent_skills.py`) and the scratch trees are real
files on disk — a real Makefile, real `SKILL.md` files, a real `AGENTS.md` — so the product parses
exactly what it parses in the repository. No stand-in for the logic, no skipped case.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import check_agent_skills as cas  # noqa: E402

CLI = REPO / "scripts" / "check_agent_skills.py"
SKILL = "---\nname: {name}\ndescription: {name} test skill\n---\n\n## Inputs\n\nin\n\n" \
        "## Output\n\nout\n\n## Rules\n\nrules\n"
RULE = cas.RULE_HEADING + "\n\nThe gate is `make check-agent-skills`.\n"


def _run(root: Path, *args: str) -> subprocess.CompletedProcess:
    """The real CLI, against a real checkout (the repo by default, a scratch tree in tests)."""
    return subprocess.run([sys.executable, str(CLI), *args, "--root", str(root)],
                          capture_output=True, text=True, timeout=120)


def _skill(root: Path, name: str, body: str | None = None, declared: str | None = None) -> None:
    directory = root / ".hermes" / "skills" / name
    directory.mkdir(parents=True, exist_ok=True)
    text = body if body is not None else SKILL.format(name=declared or name)
    (directory / "SKILL.md").write_text(text)


def _tree(tmp_path: Path, makefile: str, *, skills: tuple[str, ...] = ("bot-unattended", "issue-triage"),
          rule: str | None = RULE) -> Path:
    """A real checkout skeleton: a Makefile, the rulebook and the named project skills."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "Makefile").write_text(makefile)
    if rule is not None:
        (tmp_path / "AGENTS.md").write_text(rule)
    for name in skills:
        _skill(tmp_path, name)
    return tmp_path


LEG = '_leg:\n\thermes -z "Follow the preloaded skill issue-triage." -s issue-triage,bot-unattended -m x\n'


# ---------------------------------------------------------------------------
# the real tree
# ---------------------------------------------------------------------------
def test_the_real_tree_has_one_complete_skill_per_leg_and_passes_the_gate():
    """Every leg preloads existing, complete skills, and the gate exits 0 on the checkout."""
    # Given the real checkout and its `hermes -z` legs
    found_legs = cas.legs(REPO)

    # When  the legs and the skills are read
    found_skills = {skill.name: skill for skill in cas.all_skills(REPO)}

    # Then  every leg preloads the shared skill and each named skill exists, is named for its
    #       directory and carries the three contract sections
    assert len(found_legs) >= 7, f"the bot legs disappeared: {len(found_legs)}"
    for leg in found_legs:
        assert cas.SHARED_SKILL in leg.skills, f"{leg.where} does not preload {cas.SHARED_SKILL}"
        for name in leg.skills:
            assert name in found_skills, f"{leg.where}: -s {name} names no skill"
            assert found_skills[name].declared == name
            assert not found_skills[name].missing, (name, found_skills[name].missing)

    # And   the nine skills the issue names are all present
    expected = {"bot-unattended", "issue-triage", "issue-refiner", "issue-dedup", "issue-implement",
                "architecture-doc", "agent-fetch", "rebase-conflict", "pr-fix"}
    assert expected <= set(found_skills), expected - set(found_skills)

    # And   the CLI itself is green on the real tree
    assert _run(REPO, "check").returncode == 0


def test_the_report_names_every_leg_its_prompt_size_and_each_skills_sections():
    """`make agent-skills-report` reads the same facts the gate does."""

    # Given the real checkout
    # When  the report is rendered
    out = _run(REPO, "report")

    # Then  it lists the legs with their skills and the skills with their sections
    assert out.returncode == 0
    assert "legs:" in out.stdout and "prompt=" in out.stdout
    assert "skills:" in out.stdout and "missing_sections=none" in out.stdout
    assert "findings: 0" in out.stdout


# ---------------------------------------------------------------------------
# every failure shape reds the gate
# ---------------------------------------------------------------------------
def test_a_leg_with_no_skill_fails(tmp_path):
    """A leg whose prompt is the whole contract again is the defect; `-s` is the fix."""

    # Given a leg that preloads nothing
    tree = _tree(tmp_path, '_leg:\n\thermes -z "you are a bot, do these things" -m x\n')

    # When  the gate checks it
    out = _run(tree, "check")

    # Then  it exits non-zero and names the leg and the missing -s
    assert out.returncode == 1
    assert "preloads no project skill" in out.stderr and "Makefile:2" in out.stderr


def test_a_leg_naming_a_missing_skill_fails(tmp_path):
    """`-s` pointing at no SKILL.md is a leg that would run with half its contract missing."""

    # Given a leg naming a skill directory that does not exist
    tree = _tree(tmp_path, '_leg:\n\thermes -z "pointer" -s issue-triage,bot-unattended,no-such -m x\n')

    # When  the gate checks it
    out = _run(tree, "check")

    # Then  it names the skill that resolves nowhere
    assert out.returncode == 1
    assert "no-such" in out.stderr and ".hermes/skills/no-such/SKILL.md" in out.stderr


def test_a_skill_whose_name_differs_from_its_directory_fails(tmp_path):
    """The frontmatter name is what `-s` resolves; a mismatch is a skill nobody can load by name."""

    # Given a directory `issue-triage` whose frontmatter says something else
    tree = _tree(tmp_path, LEG)
    _skill(tree, "issue-triage", declared="triage")

    # When  the gate checks it
    out = _run(tree, "check")

    # Then  it reports the declared/expected pair
    assert out.returncode == 1
    assert "declares name `triage`" in out.stderr and "expected `issue-triage`" in out.stderr


def test_a_skill_missing_a_contract_section_fails(tmp_path):
    """Inputs / Output / Rules are the contract; a skill without one is not loadable as a spec."""

    # Given a skill with no `## Output`
    tree = _tree(tmp_path, LEG)
    _skill(tree, "issue-triage", body="---\nname: issue-triage\ndescription: d\n---\n\n"
                                     "## Inputs\n\nin\n\n## Rules\n\nrules\n")

    # When  the gate checks it
    out = _run(tree, "check")

    # Then  it names the missing section
    assert out.returncode == 1
    assert "no `## Output` section" in out.stderr


def test_an_inline_prompt_over_the_pointer_budget_fails(tmp_path):
    """A rulebook creeping back into the recipe is exactly what the budget exists to catch."""

    # Given a leg whose inline prompt is well past the pointer budget
    prompt = "x" * (cas.MAX_PROMPT_CHARS + 1)
    tree = _tree(tmp_path, f'_leg:\n\thermes -z "{prompt}" -s issue-triage,bot-unattended -m x\n')

    # When  the gate checks it
    out = _run(tree, "check")

    # Then  it reports the measured size against the budget
    assert out.returncode == 1
    assert f"{cas.MAX_PROMPT_CHARS + 1} chars" in out.stderr
    assert f"{cas.MAX_PROMPT_CHARS}-char pointer budget" in out.stderr


def test_a_prompt_repeating_the_shared_contract_fails(tmp_path):
    """The unattended paragraph lives in bot-unattended once; a copy in a recipe is drift."""

    # Given a leg that repeats the shared wording inline
    tree = _tree(tmp_path, '_leg:\n\thermes -z "NEVER ask a question; a question fails the run." '
                              '-s issue-triage,bot-unattended -m x\n')

    # When  the gate checks it
    out = _run(tree, "check")

    # Then  it points at the shared skill instead
    assert out.returncode == 1
    assert "repeats `NEVER ask a question`" in out.stderr


def test_a_returning_second_rules_file_fails(tmp_path):
    """`scripts/fix_bot_rules.md` was retired into the pr-fix skill; a second contract is a defect."""

    # Given a tree that carries a rules file next to the skills
    tree = _tree(tmp_path, LEG)
    (tree / "scripts").mkdir()
    (tree / "scripts" / "fix_bot_rules.md").write_text("# rules\n")

    # When  the gate checks it
    out = _run(tree, "check")

    # Then  it names the second rules file
    assert out.returncode == 1
    assert "a second rules file" in out.stderr


def test_removing_the_rule_from_the_rulebook_fails(tmp_path):
    """The rule's removal would silently retire the seam, so it is a finding."""

    # Given a checkout whose rulebook and skill doc no longer carry the rule
    tree = _tree(tmp_path, LEG, rule="# AGENTS\n\nno seam rule here\n")

    # When  the gate checks it
    out = _run(tree, "check")

    # Then  it names the rule that is gone
    assert out.returncode == 1
    assert cas.RULE_HEADING in out.stderr and "is gone" in out.stderr


def test_a_tree_with_no_leg_at_all_cannot_pass(tmp_path):
    """A scan that finds nothing must not read as green — it would pass on an empty tree."""

    # Given a Makefile with no `hermes -z` invocation
    tree = _tree(tmp_path, '_leg:\n\tpython3 scripts/thing.py\n')

    # When  the gate checks it
    out = _run(tree, "check")

    # Then  it says the scan found nothing
    assert out.returncode == 1
    assert "no `hermes -z` leg was found" in out.stderr


# ---------------------------------------------------------------------------
# the image trusts the checkout, and the retired rules file is gone
# ---------------------------------------------------------------------------
def test_the_agent_image_trusts_the_checkout_for_project_skills():
    """Hermes discovers project skills only under a trusted root — the image must trust /repo."""

    # Given the image's Hermes install script and the Dockerfile that runs it
    install = (REPO / "scripts" / "install_hermes_ci.sh").read_text()
    dockerfile = (REPO / "containers" / "agent" / "Dockerfile").read_text()

    # When  the trust configuration is read
    # Then  the install sets skills.trusted_project_dirs to /repo and proves it landed
    assert "skills.trusted_project_dirs" in install
    assert 'TRUSTED_PROJECT_DIR="${HERMES_TRUSTED_PROJECT_DIR:-/repo}"' in install
    assert "hermes config get skills.trusted_project_dirs" in install

    # And   the image runs that script at build time
    assert "install_hermes_ci.sh" in dockerfile


def test_the_retired_rules_file_is_gone_and_the_fix_loop_loads_the_skill():
    """One contract, one home: the loop preloads `pr-fix`, it does not concatenate a rules file."""

    # Given the fix-bot loop and the tree
    loop = (REPO / "scripts" / "fix_loop.sh").read_text()

    # When  its agent command is read
    # Then  it preloads the project skills and names no rules file
    assert "-s pr-fix,bot-unattended" in loop
    assert "fix_bot_rules.md" not in loop
    assert not (REPO / "scripts" / "fix_bot_rules.md").exists()
