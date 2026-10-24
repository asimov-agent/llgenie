#!/usr/bin/env python3
"""Is every bot leg's contract a project skill an agent can load? (issue #577)

Every bot leg used to carry its whole contract as one inline string in the `Makefile` (or a
script's heredoc): the triage rules, the refiner rules, the implementer's hard rules, and the
~500-character "UNATTENDED: ..." paragraph repeated verbatim in each of them. Three consequences,
all measured:

- the contract was not a file an agent could load — changing what a bot may write meant editing a
  1000+ character make recipe next to unrelated targets;
- the unattended paragraph was duplicated, so a wording fix had to be applied seven times and two
  legs had already diverged;
- every leg paid for the whole of `AGENTS.md` to learn its own fraction.

Hermes already has the mechanism: project skills under `<repo>/.hermes/skills/**/SKILL.md`,
preloaded by name with `hermes -s <name>`. This module is the gate that keeps the seam honest.

  check_agent_skills.py report    what each leg preloads, its prompt size, each skill's sections
  check_agent_skills.py check     exit 1 on a leg with no skill, a missing/misnamed/incomplete
                                  skill, a rulebook-sized prompt, a duplicated shared contract, a
                                  second rules file, or an AGENTS.md that lost the rule

What a "leg" is: a command line in the `Makefile`, `tools/Makefile` or `scripts/*.sh` that runs
`hermes` with the one-shot `-z` prompt flag. The prompt may be a here-string, a quoted string, or
the STDIN passthrough `"$(cat)"` — whatever it is, its LENGTH is the pointer budget and its
companions are the `-s` skills. A `hermes -z` invocation built inside a Python module is not a leg:
`scripts/hermes_smoke.py` assembles one to prove the alias can CALL A TOOL, carries no bot
contract, and is deliberately outside this scan (it would otherwise need a skill with nothing in
it).

Stdlib only, no network, no model.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS_DIR = ".hermes/skills"
MAKEFILES = ("Makefile", "tools/Makefile")
#: Every `-z` leg's inline prompt is a POINTER plus that run's parameters. A rulebook creeping
#: back into the recipe is the defect this budget exists to catch; a pointer is ~100-230 chars.
MAX_PROMPT_CHARS = 400
#: The one skill every leg preloads: the shared unattended contract, written once.
SHARED_SKILL = "bot-unattended"
#: A skill is the file an agent loads and a reviewer reads: these three sections are its contract.
REQUIRED_SECTIONS = ("Inputs", "Output", "Rules")
#: The second rules file this change replaced. If it comes back, there are two contracts again.
RETIRED_RULES_FILE = "scripts/fix_bot_rules.md"
#: The wording of the shared contract, which belongs in bot-unattended and nowhere else.
DUPLICATED_MARKERS = ("NEVER ask a question", "UNATTENDED:")
#: The durable rule this change adds; its removal would silently retire the seam. It belongs in
#: the repository rulebook (`AGENTS.md`). `docs/AGENT-SKILLS.md` is the same rule's home for a
#: run that cannot write the rulebook (AGENTS.md is a protected agent-instruction file whose
#: write needs a human's approval), so the gate accepts either and names both when neither has it.
RULE_HOMES = ("AGENTS.md", "docs/AGENT-SKILLS.md")
RULE_HEADING = "## Every bot leg's contract is a project skill"
RULE_GATE = "make check-agent-skills"

PROMPT_RE = re.compile(r"-z\s+\\?\"((?:[^\"\\]|\\.)*?)\\?\"")
SKILLS_RE = re.compile(r"(?:^|\s)-s\s+([A-Za-z0-9][A-Za-z0-9,._-]*)")
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
NAME_RE = re.compile(r"^name:\s*(\S+)\s*$", re.M)


@dataclass(frozen=True)
class Leg:
    """One `hermes -z` invocation: where it is, its inline prompt, the skills it preloads."""

    path: str
    line: int
    prompt: str
    skills: tuple[str, ...]

    @property
    def where(self) -> str:
        return f"{self.path}:{self.line}"


@dataclass(frozen=True)
class Skill:
    """One project skill directory: its name from the frontmatter, its missing sections."""

    name: str
    directory: str
    declared: str
    sections: tuple[str, ...]

    @property
    def missing(self) -> tuple[str, ...]:
        return tuple(s for s in REQUIRED_SECTIONS if s not in self.sections)


def _scanned_files(root: Path) -> list[Path]:
    files = [root / rel for rel in MAKEFILES if (root / rel).is_file()]
    scripts = root / "scripts"
    if scripts.is_dir():
        files.extend(sorted(scripts.glob("*.sh")))
    return files


def legs(root: Path = REPO) -> list[Leg]:
    """Every `hermes -z` leg in the tree, with its prompt and the skills it preloads."""
    found: list[Leg] = []
    for path in _scanned_files(root):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), start=1):
            if "hermes" not in line:
                continue
            match = PROMPT_RE.search(line)
            if not match:
                continue
            prompt = match.group(1)
            skills_match = SKILLS_RE.search(line[match.end():])
            skills = tuple(s.strip() for s in skills_match.group(1).split(",") if s.strip()) \
                if skills_match else ()
            found.append(Leg(path=rel, line=number, prompt=prompt, skills=skills))
    return found


def skill(root: Path, name: str) -> Skill | None:
    """The skill directory `name` resolves to, or None when there is no SKILL.md for it."""
    directory = root / SKILLS_DIR / name
    skill_md = directory / "SKILL.md"
    if not skill_md.is_file():
        return None
    text = skill_md.read_text(encoding="utf-8")
    front = FRONTMATTER_RE.match(text)
    name_match = NAME_RE.search(front.group(1)) if front else None
    declared = name_match.group(1) if name_match else ""
    sections = tuple(re.findall(r"^##\s+(.+?)\s*$", text, re.M))
    return Skill(name=name, directory=directory.relative_to(root).as_posix(),
                 declared=declared, sections=sections)


def all_skills(root: Path = REPO) -> list[Skill]:
    """Every project skill directory in the tree, sorted by directory name."""
    base = root / SKILLS_DIR
    if not base.is_dir():
        return []
    out = []
    for child in sorted(p for p in base.iterdir() if p.is_dir()):
        found = skill(root, child.name)
        if found is not None:
            out.append(found)
    return out


def _rule_home(root: Path) -> tuple[str, str] | None:
    """(path, text) of the rule's home — the rulebook first, then the skill doc."""
    for rel in RULE_HOMES:
        path = root / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if RULE_HEADING in text:
            return rel, text
    return None


def findings(root: Path = REPO) -> list[str]:
    """Every defect, as `path:line: message` (or `path: message` for a whole-file rule)."""
    out: list[str] = []
    for leg in legs(root):
        where = leg.where
        if not leg.skills:
            out.append(f"{where}: the leg preloads no project skill — add `-s <skill>,{SHARED_SKILL}`")
            continue
        if SHARED_SKILL not in leg.skills:
            out.append(f"{where}: the leg does not preload `{SHARED_SKILL}`, so the shared "
                       f"unattended contract is not loaded")
        for name in leg.skills:
            found = skill(root, name)
            if found is None:
                out.append(f"{where}: `-s {name}` names no {SKILLS_DIR}/{name}/SKILL.md")
                continue
            if found.declared != name:
                out.append(f"{where}: {found.directory}/SKILL.md declares name "
                           f"`{found.declared or '<none>'}`, expected `{name}`")
            for section in found.missing:
                out.append(f"{where}: {found.directory}/SKILL.md has no `## {section}` section")
        if len(leg.prompt) > MAX_PROMPT_CHARS:
            out.append(f"{where}: the inline prompt is {len(leg.prompt)} chars, over the "
                       f"{MAX_PROMPT_CHARS}-char pointer budget — move the rules into the skill")
        for marker in DUPLICATED_MARKERS:
            if marker in leg.prompt:
                out.append(f"{where}: the inline prompt repeats `{marker}`, which belongs in "
                           f"{SHARED_SKILL} once")

    retired = root / RETIRED_RULES_FILE
    if retired.exists():
        out.append(f"{RETIRED_RULES_FILE}: a second rules file — the contract is the project "
                   f"skill, loaded with `-s`")

    home = _rule_home(root)
    if home is None:
        out.append(f"{' or '.join(RULE_HOMES)}: the rule `{RULE_HEADING}` is gone")
    elif RULE_GATE not in home[1]:
        out.append(f"{home[0]}: the rule does not name the gate `{RULE_GATE}`")

    if not legs(root):
        out.append("Makefile: no `hermes -z` leg was found — the scan would pass on nothing")
    return out


def report(root: Path = REPO) -> str:
    """The whole picture: each leg, its prompt size, the skills and their sections."""
    lines: list[str] = []
    found_legs = legs(root)
    lines.append(f"legs: {len(found_legs)} (pointer budget {MAX_PROMPT_CHARS} chars)")
    for leg in found_legs:
        skills = ", ".join(leg.skills) or "<none>"
        lines.append(f"  {leg.where}  prompt={len(leg.prompt)}  skills={skills}")
    found_skills = all_skills(root)
    lines.append(f"skills: {len(found_skills)} under {SKILLS_DIR}")
    for found in found_skills:
        users = [leg.where for leg in found_legs if found.name in leg.skills]
        missing = ", ".join(found.missing) or "none"
        lines.append(f"  {found.directory}  name={found.declared or '<none>'}  "
                     f"missing_sections={missing}  preloaded_by={len(users)}")
    problems = findings(root)
    lines.append(f"findings: {len(problems)}")
    lines.extend(f"  {problem}" for problem in problems)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Is every bot leg's contract a project skill loaded with -s? (issue #577)")
    parser.add_argument("command", choices=("check", "report"))
    parser.add_argument("--root", default=str(REPO), help="the checkout to read (default: repo)")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if args.command == "report":
        print(report(root))
        return 0
    problems = findings(root)
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        print(f"check-agent-skills: FAIL ({len(problems)} finding(s))", file=sys.stderr)
        return 1
    print(f"check-agent-skills: OK ({len(legs(root))} leg(s), {len(all_skills(root))} skill(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
