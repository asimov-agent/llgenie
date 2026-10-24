#!/usr/bin/env python3
"""Every bot leg must load its contract from a Hermes project skill (issue #577).

The rule these tests lock: a leg's inline prompt is a pointer plus its parameters, and the rules it
runs under are `.hermes/skills/<name>/SKILL.md` — the layout Hermes discovers from a trusted
checkout — preloaded with `hermes -s <name>`. The guard is `scripts/check_agent_skills.py`; these
tests drive the REAL script, both against this tree and against fixture trees that carry each shape
the guard exists to catch (the failure shapes, one per test, never a happy-path-only suite).

The proof that Hermes actually LOADS the skill for a bot is not here: it needs hermes-agent's own
preload path and runs in `tests/test_agent_skills_live.py` (`make test-agent-skills-live`).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import check_agent_skills as guard  # noqa: E402  (the real guard, never a copy)

AGENTS = "# AGENTS.md\n\n## A bot's behaviour lives in its project skill\n"

GOOD_SKILL = """---
name: {name}
description: A fixture skill named {name}.
---

# {name}

## Inputs

- a fixture input

## Output

- a fixture output

## Rules

- a fixture rule
"""


def make_tree(tmp_path: Path, makefile: str, skills: dict[str, str] | None = None,
              agents: str | None = AGENTS) -> Path:
    """A minimal tree the guard can read: a Makefile, `.hermes/skills/`, AGENTS.md."""
    root = tmp_path / "tree"
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "Makefile").write_text(makefile, encoding="utf-8")
    for name, body in (skills or {}).items():
        d = root / ".hermes" / "skills" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(body, encoding="utf-8")
    if agents is not None:
        (root / "AGENTS.md").write_text(agents, encoding="utf-8")
    return root


def leg_line(prompt: str = "Follow the preloaded skill demo.",
             skills: str = "demo,bot-unattended") -> str:
    """A recipe line shaped like the real legs: `hermes -z "<pointer>" -s <names> …`."""
    preload = f" -s {skills}" if skills else ""
    return f'\thermes -z "{prompt}"{preload} $(nous-alias) --reasoning low --yolo\n'


def phony_block(makefile: str) -> str:
    """The `.PHONY:` declarations, with their backslash continuations joined — one block."""
    out: list[str] = []
    inside = False
    for line in makefile.splitlines():
        if line.startswith(".PHONY:"):
            inside = True
        if inside:
            out.append(line)
            if not line.rstrip().endswith("\\"):
                inside = False
    return "\n".join(out)


def keys(root: Path) -> set[str]:
    return {item["key"] for item in guard.findings(root)}


# --------------------------------------------------------------------------- this tree passes


def test_this_tree_passes_the_gate():
    """The repository's own legs and skills satisfy the contract."""

    # Given this repository as it is checked out
    # When  the guard reads it
    # Then  it finds nothing, and it read the legs (a vacuous pass would find no leg at all)
    assert guard.findings(REPO) == [], "\n".join(guard.report(REPO).splitlines())
    legs = guard.iter_legs(REPO)
    assert len(legs) >= 8, f"only {len(legs)} agent leg(s) found: the scan reads nothing"
    assert all(leg["skills"] for leg in legs)


# --------------------------------------------------------------------------- the failure shapes


def test_a_leg_without_a_preload_is_refused(tmp_path):
    """A leg that preloads no skill is a leg whose rules are inline again."""

    # Given a Makefile whose leg names no skill
    # When  the guard runs
    # Then  the leg is a finding, not a style note
    root = make_tree(tmp_path, leg_line(skills=""),
                     {"demo": GOOD_SKILL.format(name="demo"),
                      "bot-unattended": GOOD_SKILL.format(name="bot-unattended")})
    assert "leg-no-skill" in keys(root)


def test_a_leg_naming_a_missing_skill_is_refused(tmp_path):
    """`-s issue-triage` with no such directory runs with no contract and reports success."""

    # Given a leg that preloads a skill the tree does not carry
    # When  the guard runs
    # Then  it names the leg and the missing skill
    root = make_tree(tmp_path, leg_line(skills="ghost,bot-unattended"),
                     {"bot-unattended": GOOD_SKILL.format(name="bot-unattended")})
    items = guard.findings(root)
    assert "leg-unknown-skill" in {i["key"] for i in items}
    assert any("ghost" in i["detail"] for i in items if i["key"] == "leg-unknown-skill")


def test_a_leg_that_forgets_the_unattended_skill_is_refused(tmp_path):
    """A detached run that asks a question exits 3 and reports "changed nothing"."""

    # Given a leg that preloads only its own skill
    # When  the guard runs
    # Then  the missing unattended preload is a finding
    root = make_tree(tmp_path, leg_line(skills="demo"),
                     {"demo": GOOD_SKILL.format(name="demo"),
                      "bot-unattended": GOOD_SKILL.format(name="bot-unattended")})
    assert "leg-no-unattended" in keys(root)


def test_a_prompt_over_the_pointer_budget_is_refused(tmp_path):
    """A rulebook creeping back into the recipe is exactly what this change removed."""

    # Given a leg whose prompt is a rulebook again
    # When  the guard runs
    # Then  the over-budget prompt is a finding
    long_prompt = "Load AGENTS.md for rules. " + ("and do this too. " * 40)
    root = make_tree(tmp_path, leg_line(prompt=long_prompt),
                     {"demo": GOOD_SKILL.format(name="demo"),
                      "bot-unattended": GOOD_SKILL.format(name="bot-unattended")})
    items = guard.findings(root)
    assert "leg-prompt-budget" in {i["key"] for i in items}
    assert any(str(guard.PROMPT_BUDGET) in i["detail"] for i in items
               if i["key"] == "leg-prompt-budget")


def test_the_unattended_contract_is_not_inlined_again(tmp_path):
    """The contract lives once, in the skill; a prompt that repeats it is the duplication."""

    # Given a leg that inlines the unattended rule it also preloads
    # When  the guard runs
    # Then  the inline copy is a finding
    root = make_tree(tmp_path, leg_line(prompt="NEVER ask a question and never wait."),
                     {"demo": GOOD_SKILL.format(name="demo"),
                      "bot-unattended": GOOD_SKILL.format(name="bot-unattended")})
    assert "leg-inline-unattended" in keys(root)


def test_a_skill_whose_name_disagrees_with_its_directory_is_refused(tmp_path):
    """`-s` resolves by the frontmatter name, so a mismatch preloads nothing."""

    # Given a skill directory whose frontmatter names something else
    # When  the guard runs
    # Then  the mismatch is a finding
    root = make_tree(tmp_path, leg_line(),
                     {"demo": GOOD_SKILL.format(name="something-else"),
                      "bot-unattended": GOOD_SKILL.format(name="bot-unattended")})
    assert "skill-name" in keys(root)


def test_a_skill_missing_a_section_is_refused(tmp_path):
    """A contract without `Rules` leaves the agent to guess what it must not do."""

    # Given a skill with no Rules section
    # When  the guard runs
    # Then  the missing section is a finding
    body = """---
name: demo
description: A fixture skill.
---

# demo

## Inputs

- a fixture input

## Output

- a fixture output
"""
    root = make_tree(tmp_path, leg_line(),
                     {"demo": body, "bot-unattended": GOOD_SKILL.format(name="bot-unattended")})
    items = guard.findings(root)
    assert "skill-section" in {i["key"] for i in items}
    assert any("## Rules" in i["detail"] for i in items if i["key"] == "skill-section")


def test_a_skill_nothing_preloads_is_reported(tmp_path):
    """A contract no leg loads is dead weight, not a rule."""

    # Given a skill directory no leg names
    # When  the guard runs
    # Then  it is reported as unused
    root = make_tree(tmp_path, leg_line(),
                     {"demo": GOOD_SKILL.format(name="demo"),
                      "bot-unattended": GOOD_SKILL.format(name="bot-unattended"),
                      "orphan": GOOD_SKILL.format(name="orphan")})
    assert "skill-unused" in keys(root)


def test_the_retired_rules_file_is_refused(tmp_path):
    """One mechanism: the fix bot's rules are the `pr-fix` skill, not a second file."""

    # Given a tree that carries scripts/fix_bot_rules.md again
    # When  the guard runs
    # Then  it is refused
    root = make_tree(tmp_path, leg_line(),
                     {"demo": GOOD_SKILL.format(name="demo"),
                      "bot-unattended": GOOD_SKILL.format(name="bot-unattended")})
    (root / "scripts" / "fix_bot_rules.md").write_text("# rules\n", encoding="utf-8")
    assert "rules-file" in keys(root)


def test_agents_md_must_state_the_rule(tmp_path):
    """Deleting the rule that a bot's behaviour lives in its skill must not be silent."""

    # Given an AGENTS.md without the heading
    # When  the guard runs
    # Then  the rule's disappearance is a finding
    root = make_tree(tmp_path, leg_line(),
                     {"demo": GOOD_SKILL.format(name="demo"),
                      "bot-unattended": GOOD_SKILL.format(name="bot-unattended")},
                     agents="# AGENTS.md\n\nnothing about skills\n")
    assert "agents-md" in keys(root)


# --------------------------------------------------------------------------- wiring and the seam


def test_the_gate_is_wired_into_ci_unit_and_make():
    """A guard no CI job runs is a defect, not a spare part."""

    # Given the Makefile and the CI stage
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")

    # When  the gate's target, its help line, its .PHONY entry and its CI stage are read
    # Then  all four exist and `make -n` prints the real command
    assert "check-agent-skills: ## " in makefile
    assert "check-agent-skills" in phony_block(makefile), "the target must be declared .PHONY"
    assert "\t$(MAKE) check-agent-skills\n" in makefile
    printed = subprocess.run(["make", "-n", "check-agent-skills"], cwd=REPO,
                             capture_output=True, text=True, check=True).stdout
    assert "python3 scripts/check_agent_skills.py check" in printed


def test_the_agent_image_registers_the_skills_directory():
    """Hermes reads skills from its home + `skills.external_dirs`; the image registers the repo's."""

    # Given the agent image's install script
    script = (REPO / "scripts" / "install_hermes_ci.sh").read_text(encoding="utf-8")

    # When  its skill-registration section is read
    # Then  it points Hermes at the checkout's `.hermes/skills` and proves the value landed
    assert "hermes_skills_register.py" in script
    assert "/repo/.hermes/skills" in script
    assert "--check" in script, "the build must read the value back, not assume it landed"


def test_the_fix_bot_preloads_its_contract_instead_of_inlining_it():
    """The fix loop used to `cat` its rules into the prompt; now it preloads the skill."""

    # Given the fix loop script
    script = (REPO / "scripts" / "fix_loop.sh").read_text(encoding="utf-8")

    # When  its agent command and prompt builder are read
    # Then  the command preloads the skills and the prompt no longer carries the rules
    assert "-s pr-fix,bot-unattended" in script
    assert 'cat "$RULES"' not in script
    assert "Follow the preloaded skills" in script


def test_the_rebase_prompt_no_longer_restates_the_rules():
    """The conflict prompt carries the conflict; the rules are the preloaded skill."""

    # Given the rebase bot's prompt builder
    script = (REPO / "scripts" / "rebase_bot.sh").read_text(encoding="utf-8")

    # When  it is read
    # Then  it points at the preloaded skill instead of restating the hard rules
    assert "preloaded skills rebase-conflict" in script
    assert "HARD RULES: preserve BOTH sides" not in script


# --------------------------------------------------------------------------- the registration


def test_the_register_script_writes_a_yaml_list_any_hermes_reads(tmp_path):
    """`hermes config set` differs across versions; the script writes the shape both read."""

    # Given an empty Hermes home
    home = tmp_path / "home"
    skill_dir = tmp_path / "checkout" / ".hermes" / "skills"

    # When  the registration script runs on it
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "hermes_skills_register.py"),
                        "--home", str(home), "--dir", str(skill_dir)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr

    # Then  config.yaml holds a LIST under skills.external_dirs (not a JSON string)
    text = (home / "config.yaml").read_text()
    assert "external_dirs:" in text
    assert f"- {skill_dir}" in text
    assert '"[\\"' not in text, "a JSON string is what the pinned CLI misreads as ONE directory"

    # And  --check accepts it, and is idempotent (a second run does not duplicate the entry)
    check = subprocess.run([sys.executable, str(REPO / "scripts" / "hermes_skills_register.py"),
                            "--home", str(home), "--dir", str(skill_dir), "--check"])
    assert check.returncode == 0
    subprocess.run([sys.executable, str(REPO / "scripts" / "hermes_skills_register.py"),
                    "--home", str(home), "--dir", str(skill_dir)], check=True,
                   capture_output=True)
    assert (home / "config.yaml").read_text().count(str(skill_dir)) == 1


def test_an_unregistered_home_fails_the_check(tmp_path):
    """A build that trusts a registration that did not land is the silent failure this closes."""

    # Given a Hermes home with no registration
    home = tmp_path / "home"
    home.mkdir()

    # When  --check runs
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "hermes_skills_register.py"),
                        "--home", str(home), "--dir", str(tmp_path / "skills"), "--check"],
                       capture_output=True, text=True)

    # Then  it exits 1 and names the consequence
    assert r.returncode == 1
    assert "preload no skill" in r.stderr


def test_a_broken_config_is_refused_not_overwritten(tmp_path):
    """Silently rewriting a config we cannot parse would drop whatever it held."""

    # Given a config.yaml that is not a mapping
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.yaml").write_text("- just\n- a list\n")

    # When  the registration runs
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "hermes_skills_register.py"),
                        "--home", str(home), "--dir", str(tmp_path / "skills")],
                       capture_output=True, text=True)

    # Then  it refuses, exit 2, and leaves the file alone
    assert r.returncode == 2
    assert "not a YAML mapping" in r.stderr
    assert (home / "config.yaml").read_text() == "- just\n- a list\n"
