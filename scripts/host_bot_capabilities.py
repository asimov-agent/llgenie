#!/usr/bin/env python3
"""Pin each host llgenie bot to the toolsets and skills its lane uses (issue #1038).

The ten desktop profiles under a Hermes home were cloned from one config: no
``platform_toolsets`` pin, an empty ``skills.disabled``, and a force-push
approval on every lane. This module is the check and the apply. The unit test
drives it against a fake profile tree. Applying it to a live home is a host
action (``python3 scripts/host_bot_capabilities.py apply --home ~/.hermes``).

Stdlib plus PyYAML, which the unit image already imports.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests" / "fixtures" / "host-bot-capabilities.json"
MARKER_BEGIN = "<!-- host-bot-tools:begin -->"
MARKER_END = "<!-- host-bot-tools:end -->"
NAME_RE = re.compile(r"^name:\s*[\"']?([^\"'\n]+)", re.M)


def load_fixture(path: Path | None = None) -> dict:
    return json.loads((path or FIXTURE).read_text(encoding="utf-8"))


def toolsets_for(spec: dict, profile: str) -> list[str]:
    """The cli toolset pin for one profile: the shared base plus that lane's extras."""
    row = spec["profiles"][profile]
    names = list(spec["base_toolsets"]) + list(row.get("extra_toolsets") or [])
    return sorted(set(names))


def discover_skills(skills_dir: Path) -> list[dict]:
    """Frontmatter ``name`` and path for every SKILL.md that is not under a dot directory."""
    found: list[dict] = []
    if not skills_dir.is_dir():
        return found
    for skill in sorted(skills_dir.rglob("SKILL.md")):
        rel = skill.relative_to(skills_dir)
        if any(part.startswith(".") for part in rel.parts):
            continue
        text = skill.read_text(encoding="utf-8", errors="replace")
        match = NAME_RE.search(text)
        name = match.group(1).strip() if match else skill.parent.name
        found.append({"name": name, "path": skill, "rel": str(rel)})
    return found


def disabled_names(discovered: list[dict], keep: list[str]) -> list[str]:
    """Every discovered skill name outside the keep list. A name that is kept stays off the list."""
    keep_set = set(keep)
    return sorted({row["name"] for row in discovered if row["name"] not in keep_set})


def tools_block(spec: dict, profile: str) -> str:
    """The marker block a lane skill carries so the loaded contract matches the fixture."""
    row = spec["profiles"][profile]
    toolsets = ", ".join(f"`{name}`" for name in toolsets_for(spec, profile))
    keep = ", ".join(f"`{name}`" for name in sorted(row["keep_skills"]))
    return (
        f"{MARKER_BEGIN}\n"
        "## Tools\n"
        "\n"
        f"This lane's chat session is pinned to these Hermes toolsets and no others: {toolsets}.\n"
        "\n"
        f"Skills that stay enabled: {keep}.\n"
        "Every other installed skill is listed in `skills.disabled`.\n"
        "The pin is `tests/fixtures/host-bot-capabilities.json` in asimov-agent/llgenie "
        f"(issue #{spec['issue']}).\n"
        f"{MARKER_END}\n"
    )


def insert_tools_block(text: str, block: str) -> str:
    """Replace an existing marker or insert the block after the first heading."""
    begin = text.find(MARKER_BEGIN)
    end = text.find(MARKER_END)
    if begin != -1 and end != -1 and end > begin:
        end_line = text.find("\n", end)
        if end_line == -1:
            end_line = len(text)
        else:
            end_line += 1
        return text[:begin] + block + text[end_line:]
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.startswith("# "):
            return "".join(lines[: index + 1]) + "\n" + block + "".join(lines[index + 1 :])
    return text.rstrip() + "\n\n" + block


def apply_config(config: dict, spec: dict, profile: str, discovered: list[dict]) -> dict:
    """Return the config with this lane's tool pin, disabled skills, and allowlist."""
    row = spec["profiles"][profile]
    config = dict(config)
    platform = dict(config.get("platform_toolsets") or {})
    platform["cli"] = toolsets_for(spec, profile)
    config["platform_toolsets"] = platform
    known = dict(config.get("known_builtin_toolsets") or {})
    known["cli"] = list(spec["known_builtin_toolsets"])
    config["known_builtin_toolsets"] = known
    skills = dict(config.get("skills") or {})
    skills["disabled"] = disabled_names(discovered, row["keep_skills"])
    config["skills"] = skills
    allow = [item for item in (config.get("command_allowlist") or []) if item != spec["force_push_entry"]]
    if row.get("allow_force_push"):
        allow.append(spec["force_push_entry"])
    config["command_allowlist"] = allow
    kanban = dict(config.get("kanban") or {})
    kanban["orchestrator_profile"] = spec["orchestrator_profile"]
    config["kanban"] = kanban
    return config


def check_config(config: dict, spec: dict, profile: str, discovered: list[dict]) -> list[str]:
    """Findings for one profile. Empty means the config matches the fixture."""
    want = apply_config(config, spec, profile, discovered)
    findings: list[str] = []
    if list((config.get("platform_toolsets") or {}).get("cli") or []) != want["platform_toolsets"]["cli"]:
        findings.append(f"{profile}: platform_toolsets.cli is not the fixture pin")
    disabled = sorted((config.get("skills") or {}).get("disabled") or [])
    if disabled != want["skills"]["disabled"]:
        findings.append(f"{profile}: skills.disabled does not match the keep list")
    allow = list(config.get("command_allowlist") or [])
    has_force = spec["force_push_entry"] in allow
    if has_force != bool(spec["profiles"][profile].get("allow_force_push")):
        findings.append(f"{profile}: force-push allowlist entry is wrong")
    return findings


def _dump(config: dict) -> str:
    return yaml.safe_dump(config, sort_keys=False, default_flow_style=False, width=4096)


def apply_profile(profile_dir: Path, spec: dict, profile: str) -> list[str]:
    """Write config.yaml, profile.yaml description, and the lane skill marker. Returns actions."""
    actions: list[str] = []
    config_path = profile_dir / "config.yaml"
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    discovered = discover_skills(profile_dir / "skills")
    updated = apply_config(raw, spec, profile, discovered)
    config_path.write_text(_dump(updated), encoding="utf-8")
    actions.append(f"config {profile}")
    profile_yaml = profile_dir / "profile.yaml"
    if profile_yaml.is_file():
        meta = yaml.safe_load(profile_yaml.read_text(encoding="utf-8")) or {}
        meta["description"] = spec["profiles"][profile]["description"]
        profile_yaml.write_text(_dump(meta), encoding="utf-8")
        actions.append(f"description {profile}")
    lane = spec["profiles"][profile]["lane_skill"]
    block = tools_block(spec, profile)
    for row in discovered:
        if row["name"] != lane:
            continue
        path = row["path"]
        path.write_text(insert_tools_block(path.read_text(encoding="utf-8"), block), encoding="utf-8")
        actions.append(f"skill {profile} {row['rel']}")
    return actions


def apply_repo_skills(repo: Path, spec: dict) -> list[str]:
    """Stamp the host-skill copies that live in the repository."""
    actions: list[str] = []
    mapping = {
        "llgenie-engine-improver": repo / ".hermes" / "skills" / "llgenie-engine-improver" / "SKILL.md",
        "llgenie-architect": repo / ".hermes" / "skills" / "llgenie-architecture-pass" / "SKILL.md",
    }
    for profile, path in mapping.items():
        if not path.is_file():
            continue
        block = tools_block(spec, profile)
        path.write_text(insert_tools_block(path.read_text(encoding="utf-8"), block), encoding="utf-8")
        actions.append(str(path.relative_to(repo)))
    return actions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pin host llgenie bot toolsets and skills (issue #1038).")
    parser.add_argument("action", choices=("apply", "check"))
    parser.add_argument("--home", type=Path, required=True, help="Hermes home that contains profiles/")
    parser.add_argument("--fixture", type=Path, default=FIXTURE)
    parser.add_argument("--repo", type=Path, default=None, help="Also stamp HOST skills in this checkout")
    args = parser.parse_args(argv)
    spec = load_fixture(args.fixture)
    root = args.home / "profiles"
    findings: list[str] = []
    for profile in spec["profiles"]:
        profile_dir = root / profile
        if not profile_dir.is_dir():
            findings.append(f"{profile}: profile directory missing")
            continue
        if args.action == "apply":
            for action in apply_profile(profile_dir, spec, profile):
                print(action)
        else:
            raw = yaml.safe_load((profile_dir / "config.yaml").read_text(encoding="utf-8")) or {}
            discovered = discover_skills(profile_dir / "skills")
            findings.extend(check_config(raw, spec, profile, discovered))
    if args.action == "apply" and args.repo is not None:
        for action in apply_repo_skills(args.repo, spec):
            print(action)
    if findings:
        print("\n".join(findings), file=sys.stderr)
        return 1
    if args.action == "check":
        print(f"ok {len(spec['profiles'])} profiles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
