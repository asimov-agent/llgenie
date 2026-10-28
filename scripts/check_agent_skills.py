#!/usr/bin/env python3
"""Guard the bots' Hermes project skills (issue #577).

Every agent leg used to carry its whole contract as one inline string in the `Makefile`: 1005-1629
characters of rules per leg, the same `UNATTENDED: …` paragraph repeated seven times, and each leg
starting with "Load AGENTS.md" to learn what its own bot may do. The contract now lives in a Hermes
**project skill** — `.hermes/skills/<name>/SKILL.md`, the layout Hermes discovers from a trusted
checkout — preloaded by the leg with `hermes -s <name>`, and the leg's inline prompt is a pointer
plus the run's parameters.

This gate keeps that true, because nothing else can:

* a leg that preloads nothing is back to an inline rulebook;
* a leg naming a skill that does not exist runs with no contract at all, and reports success;
* a skill whose frontmatter `name` disagrees with its directory is not resolvable by `-s`;
* a skill whose `Inputs`/`Output`/`Rules` section went missing is a contract with a hole in it;
* a prompt that grows past the pointer budget means the rules crept back into the recipe;
* a host skill (an operator loop no CI leg can preload) is admitted by NAME, never by shape, so
  every admission is a reviewed diff and the contract rules still apply to it;
* the unattended contract inlined again is the duplication this change removed;
* an `AGENTS.md` that no longer states the rule lets the seam be deleted silently.

Scan scope: `Makefile` and `scripts/*.sh` — the shell legs. `scripts/hermes_smoke.py` invokes the
same CLI from Python to prove tool use; it carries no bot contract and is covered by its own test.

Usage:
    python3 scripts/check_agent_skills.py check    # exit 1 on any finding, 2 when the tree is unreadable
    python3 scripts/check_agent_skills.py report   # print what the gate reads, always exit 0
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = Path(".hermes") / "skills"
SKILL_FILE = "SKILL.md"
#: The inline prompt is a pointer, not a rulebook. 400 characters fits a pointer naming every
#: parameter of the longest leg; the rules it used to carry are 1000-1600 characters each.
PROMPT_BUDGET = 400
#: Every bot skill states what it is given, what it may write, and what it must not do.
REQUIRED_SECTIONS = ("## Inputs", "## Output", "## Rules")
#: The shared unattended contract, preloaded beside each bot's own skill.
UNATTENDED_SKILL = "bot-unattended"
#: Skills an operator runs on a HOST on demand, which no CI leg preloads. They live here so their
#: behaviour is versioned with the repo they drive, and they still owe frontmatter and
#: Inputs/Output/Rules — they are exempt from the unused-skill rule only. Listed by name (never
#: detected from the body), so admitting another one is a reviewed diff.
HOST_SKILLS = frozenset({"llgenie-engine-improver", "llgenie-architecture-pass"})
#: The rule AGENTS.md must keep, so the seam cannot be deleted silently.
AGENTS_MARKER = "## A bot's behaviour lives in its project skill"
#: The retired second place a bot's rules lived (moved into `.hermes/skills/pr-fix/SKILL.md`).
RETIRED_RULES_FILE = Path("scripts") / "fix_bot_rules.md"
#: Text that belongs in `bot-unattended/SKILL.md` and nowhere near a make recipe.
INLINE_UNATTENDED = "NEVER ask a question"
LEG_SOURCES = ("Makefile", "scripts/*.sh")
_SKILL_FLAG = re.compile(r"(?:^|\s)(?:-s|--skills)[\s=]+(\S+)")


def leg_sources(root: Path) -> list[Path]:
    """The files that can carry an agent leg, in a stable order."""
    files = [root / name for name in LEG_SOURCES if "*" not in name]
    for pattern in LEG_SOURCES:
        if "*" in pattern:
            files.extend(sorted(root.glob(pattern)))
    return [p for p in files if p.is_file()]


def _prompt_at(line: str, start: int) -> tuple[str, int]:
    """The quoted prompt argument of a `hermes -z` call starting at *start*, and its end index."""
    i = start
    while i < len(line) and line[i].isspace():
        i += 1
    # A shell leg inside a `bash -lc '…'` string writes the quote escaped (`\"`); both forms close
    # the same way, so remember which one opened it.
    escaped = line.startswith('\\"', i)
    if escaped:
        i += 2
    elif line.startswith('"', i):
        i += 1
    else:  # an unquoted prompt (a bare word) — read to the next space
        end = i
        while end < len(line) and not line[end].isspace():
            end += 1
        return line[i:end], end
    close = '\\"' if escaped else '"'
    end = line.find(close, i)
    if end < 0:
        return line[i:], len(line)
    return line[i:end], end + len(close)


_MAKE_ASSIGN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:?=\s*(.*)$")


def make_vars(root: Path) -> dict[str, str]:
    """Simple `NAME := value` / `NAME = value` assignments from the Makefile (issue #641).

    A leg may not put a literal comma inside `$(call scrubbed_run,…)` — make splits the call's
    arguments on commas in the UNEXPANDED text — so its `-s` list comes from a variable. The guard
    has to expand those the way make would, or it reads `$(SKILLS)` as a skill name.
    """
    values: dict[str, str] = {}
    mk = root / "Makefile"
    try:
        lines = mk.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for line in lines:
        m = _MAKE_ASSIGN.match(line)
        if m and not line.startswith((" ", "\t")):
            values.setdefault(m.group(1), m.group(2).strip())
    return values


def expand_make(text: str, values: dict[str, str], passes: int = 3) -> str:
    """Replace `$(NAME)` / `${NAME}` for known assignments, a few levels deep."""
    for _ in range(passes):
        new = re.sub(r"\$\(([A-Za-z_][A-Za-z0-9_]*)\)", lambda m: values.get(m.group(1), m.group(0)), text)
        new = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", lambda m: values.get(m.group(1), m.group(0)), new)
        if new == text:
            break
        text = new
    return text


def iter_legs(root: Path) -> list[dict]:
    """Every `hermes -z …` invocation in the shell legs, with its prompt and preloaded skills."""
    legs: list[dict] = []
    variables = make_vars(root)
    for path in leg_sources(root):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:  # unreadable is a finding, never an empty pass
            legs.append({"where": f"{path.name}:unreadable", "error": str(exc), "prompt": "",
                         "skills": []})
            continue
        for n, line in enumerate(text.splitlines(), 1):
            line = expand_make(line, variables)
            at = line.find("hermes -z")
            if at < 0:
                continue
            prompt, prompt_end = _prompt_at(line, at + len("hermes -z"))
            tail = line[prompt_end:]
            names: list[str] = []
            for match in _SKILL_FLAG.finditer(tail):
                names.extend(part for part in re.split(r"[,\s]+", match.group(1)) if part)
            legs.append({
                "where": f"{path.relative_to(root)}:{n}",
                "prompt": prompt,
                "skills": names,
                "error": "",
            })
    return legs


def frontmatter(path: Path) -> dict[str, str] | None:
    """The skill's frontmatter as a flat name→value map, or None when it has none."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    if not lines or lines[0].strip() != "---":
        return None
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        if ":" in line and not line.startswith((" ", "\t")):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip().strip("'\"")
    return None


def skills(root: Path) -> dict[str, Path]:
    """Every skill directory under `.hermes/skills/` that carries a SKILL.md."""
    base = root / SKILLS_DIR
    if not base.is_dir():
        return {}
    return {d.name: d for d in sorted(base.iterdir()) if (d / SKILL_FILE).is_file()}


def findings(root: Path = REPO_ROOT) -> list[dict]:
    """Every way the seam can be broken. An empty list is the only pass."""
    items: list[dict] = []
    found = skills(root)
    if not found:
        items.append({
            "key": "skills-dir",
            "where": str(SKILLS_DIR),
            "detail": f"no {SKILLS_DIR}/<name>/{SKILL_FILE} in the tree — the bots' contracts "
                      "have nowhere to live",
        })

    # ---- every skill is a real, resolvable contract --------------------------------
    for name, dirpath in found.items():
        path = dirpath / SKILL_FILE
        meta = frontmatter(path)
        if meta is None:
            items.append({
                "key": "skill-frontmatter",
                "where": str((dirpath / SKILL_FILE).relative_to(root)),
                "detail": "no `---` frontmatter block, so Hermes cannot index it (it needs `name:` "
                          "and `description:`)",
            })
        else:
            if meta.get("name", "") != name:
                items.append({
                    "key": "skill-name",
                    "where": str((dirpath / SKILL_FILE).relative_to(root)),
                    "detail": f"frontmatter name is {meta.get('name')!r} but the directory is "
                              f"{name!r}; `hermes -s {name}` resolves by the frontmatter name, so "
                              "the leg would preload nothing",
                })
            if not meta.get("description", "").strip():
                items.append({
                    "key": "skill-description",
                    "where": str((dirpath / SKILL_FILE).relative_to(root)),
                    "detail": "empty `description:` — that is the line the agent's skill index shows",
                })
        body = path.read_text(encoding="utf-8")
        for section in REQUIRED_SECTIONS:
            # An EXACT heading, never a substring: `## Rules for reviewers` is not the contract's
            # `## Rules`, and a renamed heading must stop satisfying the gate (issue #805).
            if not re.search(rf"^{re.escape(section)}\s*$", body, re.M):
                items.append({
                    "key": "skill-section",
                    "where": str((dirpath / SKILL_FILE).relative_to(root)),
                    "detail": f"missing `{section}` — a contract without it leaves the agent to "
                              "guess what it was given, may write, or must not do",
                })

    # ---- every leg preloads its contract, and keeps its prompt a pointer ----------
    legs = iter_legs(root)
    if not legs:
        items.append({
            "key": "legs",
            "where": ", ".join(LEG_SOURCES),
            "detail": "no `hermes -z` leg found — the scan is looking in the wrong place, which "
                      "would pass vacuously",
        })
    seen: set[str] = set()
    for leg in legs:
        if leg["error"]:
            items.append({"key": "leg-unreadable", "where": leg["where"], "detail": leg["error"]})
            continue
        if not leg["skills"]:
            items.append({
                "key": "leg-no-skill",
                "where": leg["where"],
                "detail": "the leg preloads no skill (`-s <name>`); its rules are back inline in "
                          "the recipe, which is the state issue #577 removed",
            })
            continue
        for name in leg["skills"]:
            seen.add(name)
            if name not in found:
                items.append({
                    "key": "leg-unknown-skill",
                    "where": leg["where"],
                    "detail": f"preloads `{name}`, but {SKILLS_DIR}/{name}/{SKILL_FILE} does not "
                              "exist — the run would start with no contract and report success",
                })
        if UNATTENDED_SKILL not in leg["skills"]:
            items.append({
                "key": "leg-no-unattended",
                "where": leg["where"],
                "detail": f"does not preload `{UNATTENDED_SKILL}`; a detached run that asks a "
                          "question dies with exit 3 and reports \"changed nothing\"",
            })
        if len(leg["prompt"]) > PROMPT_BUDGET:
            items.append({
                "key": "leg-prompt-budget",
                "where": leg["where"],
                "detail": f"inline prompt is {len(leg['prompt'])} characters, over the "
                          f"{PROMPT_BUDGET}-character pointer budget — the rules belong in the "
                          "skill, the prompt names the parameters",
            })
        if INLINE_UNATTENDED in leg["prompt"]:
            items.append({
                "key": "leg-inline-unattended",
                "where": leg["where"],
                "detail": f"inlines the unattended contract; it lives once in "
                          f"{SKILLS_DIR}/{UNATTENDED_SKILL}/{SKILL_FILE}",
            })

    for name in found:
        if name not in seen and name not in HOST_SKILLS:
            items.append({
                "key": "skill-unused",
                "where": str((found[name] / SKILL_FILE).relative_to(root)),
                "detail": "no leg preloads this skill — a contract nothing loads is dead weight, "
                          "not a rule",
            })

    # ---- one mechanism, and a rulebook that states it ------------------------------
    if (root / RETIRED_RULES_FILE).exists():
        items.append({
            "key": "rules-file",
            "where": str(RETIRED_RULES_FILE),
            "detail": "this file is back: a second place a bot's rules live. It moved into "
                      f"{SKILLS_DIR}/pr-fix/{SKILL_FILE}, which the fix loop preloads",
        })
    agents = root / "AGENTS.md"
    try:
        agents_text = agents.read_text(encoding="utf-8")
    except OSError as exc:
        items.append({"key": "agents-md", "where": "AGENTS.md", "detail": f"unreadable: {exc}"})
    else:
        if AGENTS_MARKER not in agents_text:
            items.append({
                "key": "agents-md",
                "where": "AGENTS.md",
                "detail": f"does not carry the heading `{AGENTS_MARKER}`, so the rule that a bot's "
                          "behaviour lives in its skill can be deleted without anything noticing",
            })
    return items


def report(root: Path = REPO_ROOT) -> str:
    """What the gate reads: each leg with its prompt size and preloaded skills, then each skill."""
    lines = ["[check-agent-skills] agent legs (prompt budget "
             f"{PROMPT_BUDGET} characters):"]
    legs = iter_legs(root)
    for leg in legs:
        if leg["error"]:
            lines.append(f"  {leg['where']}: UNREADABLE ({leg['error']})")
            continue
        names = ",".join(leg["skills"]) or "(none)"
        lines.append(f"  {leg['where']}: prompt={len(leg['prompt'])} skills={names}")
    lines.append(f"  {len(legs)} leg(s)")
    found = skills(root)
    lines.append(f"[check-agent-skills] {SKILLS_DIR}/ ({len(found)} skill(s)):")
    for name, dirpath in found.items():
        meta = frontmatter(dirpath / SKILL_FILE) or {}
        kind = " host-skill" if name in HOST_SKILLS else ""
        lines.append(f"  {name}:{kind} name={meta.get('name')!r} "
                     f"description={'yes' if meta.get('description') else 'MISSING'}")
    items = findings(root)
    lines.append(f"[check-agent-skills] {len(items)} finding(s)")
    for item in items:
        lines.append(f"  {item['key']}: {item['where']}: {item['detail']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("mode", nargs="?", default="check", choices=("check", "report"))
    parser.add_argument("--root", default=str(REPO_ROOT), help="tree to read (the tests use this)")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"[check-agent-skills] FAIL: {root} is not a directory", file=sys.stderr)
        return 2
    if args.mode == "report":
        print(report(root))
        return 0
    items = findings(root)
    if not items:
        legs = len(iter_legs(root))
        print(f"[check-agent-skills] OK: {legs} agent leg(s) preload a project skill, "
              f"{len(skills(root))} skill(s) carry Inputs/Output/Rules, prompts within "
              f"{PROMPT_BUDGET} characters")
        return 0
    for item in items:
        print(f"[check-agent-skills] FAIL {item['key']}: {item['where']}: {item['detail']}")
    print(f"[check-agent-skills] {len(items)} finding(s) — a bot leg without a resolvable skill "
          "runs with no contract, so this is a failure, not a style note", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
