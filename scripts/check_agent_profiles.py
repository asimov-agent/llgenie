#!/usr/bin/env python3
"""Guard the host agents' behaviour tree (issue #791).

The bots' contracts live in `.hermes/skills/`, are preloaded with `hermes -s <name>` and are gated
by `scripts/check_agent_skills.py` (issue #577). The two **host** agents — `llgenie-planner` (the
orchestrator) and `llgenie-issse-implementer` (the implementer) — keep the same two kinds of file
(`SOUL.md`, `skills/<name>/SKILL.md`) but live outside version control, in
`~/.hermes/profiles/<profile>/`. An instruction that changes a credential-holding agent's behaviour
was therefore the one change in this repository nobody could diff or review.

This tree is that behaviour's home (`agents/<profile>/…`, one directory per profile, the layout
Hermes itself loads) and this gate is what keeps it honest:

* a profile listed in `agents/manifest.json` with no directory — nothing to sync, and nothing to
  review;
* a profile directory the manifest does not list — a tree nobody syncs and nobody gates;
* a profile with no `SOUL.md` — the role it runs under is missing;
* a skill whose frontmatter `name` disagrees with its directory — Hermes resolves a skill by the
  frontmatter name, so the profile would load nothing;
* a skill with no `---` frontmatter block, or an empty `description:` — invisible in the index;
* a skill whose body names a `references/<file>.md` that is not in the tree — a promised recipe
  that is missing after a sync;
* a secret-shaped value in any committed file of the tree — the whole point is that these are read
  by an agent that holds write credentials, so a key in here is a leak with a diff;
* a `SOUL.md` that stops stating a standing rule the manifest declares for that profile (the
  orchestrator must keep "never implement" and "never merge"), or a manifest that declares
  `never-merge` for no profile at all — the rule the issue exists to protect, deletable only in
  public;
* `state.db`, `sessions/`, `memories/`, `config.yaml` or `.env` in the tree — the profile's data is
  not behaviour, and it must never be committed.

Usage:
    python3 scripts/check_agent_profiles.py check    # exit 1 on any finding, 2 when the tree is unreadable
    python3 scripts/check_agent_profiles.py report   # print what the gate reads, always exit 0

Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

#: The frontmatter reader is the same one the bots' gate uses: a skill is a skill (issue #577).
from check_agent_skills import frontmatter  # noqa: E402  (import after the path fix above)

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = Path("agents")
MANIFEST = "manifest.json"
SOUL = "SOUL.md"
SKILLS = "skills"
SKILL_FILE = "SKILL.md"

#: The standing rules a profile's `SOUL.md` must keep stating. The manifest names which apply to
#: which profile; a rule key that is not here is a manifest defect, not a silent pass.
STANDING_RULES = {
    "never-implement": re.compile(r"never\s+implement|do(?:es)?\s+not\s+implement", re.I),
    "never-merge": re.compile(r"never\s+merge", re.I),
}
#: The one rule every manifest must keep for at least one profile: the orchestrator is the agent
#: that can dispatch a merge, and the rule was once a file nobody diffed.
REQUIRED_RULE = "never-merge"

#: A profile's data — memory, sessions, credentials — is not behaviour and is never committed.
FORBIDDEN_NAMES = {"state.db", "config.yaml", ".env", "auth.lock"}
FORBIDDEN_DIRS = {"memories", "sessions", "logs", "home", "cron"}

#: Credential SHAPES, never a name: a token that reaches this tree is a leak with a diff.
SECRET_PATTERNS = (
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}")),
    ("github-pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}")),
    ("hf-token", re.compile(r"\bhf_[A-Za-z0-9]{30,}")),
    ("api-key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("aws-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
)
#: A skill body may point at a recipe it expects beside itself.
REFERENCE_RE = re.compile(r"references/[A-Za-z0-9._-]+\.md")


def read_manifest(agents: Path) -> tuple[list[dict], list[dict]]:
    """The manifest's profiles as `[{name, rules}]`, plus every finding the manifest itself carries."""
    items: list[dict] = []
    path = agents / MANIFEST
    where = f"{agents.name}/{MANIFEST}"
    if not path.is_file():
        items.append({
            "key": "manifest-missing",
            "where": where,
            "detail": "no manifest — nothing says which profiles this tree is the source of truth "
                      "for, so the gate would pass vacuously",
        })
        return [], items
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        items.append({"key": "manifest-invalid", "where": where, "detail": f"unreadable JSON: {exc}"})
        return [], items

    raw = data.get("profiles") if isinstance(data, dict) else data
    if not isinstance(raw, list) or not raw:
        items.append({
            "key": "manifest-empty",
            "where": where,
            "detail": "`profiles` is missing or empty — a manifest that lists nothing gates nothing",
        })
        return [], items

    profiles: list[dict] = []
    for entry in raw:
        if isinstance(entry, str):
            name, rules = entry, []
        elif isinstance(entry, dict) and isinstance(entry.get("name"), str) and entry["name"].strip():
            name = entry["name"]
            rules = entry.get("rules") or []
        else:
            items.append({
                "key": "manifest-entry",
                "where": where,
                "detail": f"{entry!r} is neither a profile name nor an object with a `name`",
            })
            continue
        if not isinstance(rules, list) or not all(isinstance(rule, str) for rule in rules):
            items.append({
                "key": "manifest-entry",
                "where": where,
                "detail": f"{name}: `rules` must be a list of rule names",
            })
            rules = []
        for rule in rules:
            if rule not in STANDING_RULES:
                items.append({
                    "key": "manifest-rule-unknown",
                    "where": where,
                    "detail": f"{name} declares the rule {rule!r}, which this gate does not know "
                              f"(known: {', '.join(sorted(STANDING_RULES))}) — a misspelt rule is a "
                              "rule nobody enforces",
                })
        profiles.append({"name": name, "rules": [rule for rule in rules if rule in STANDING_RULES]})
    return profiles, items


def profiles_from_manifest(agents: Path) -> list[dict]:
    """Just the profiles, for the sync target (one manifest reader, never two)."""
    profiles, _ = read_manifest(agents)
    return profiles


def _text_files(profile: Path) -> list[Path]:
    """Every committed file of a profile, in a stable order."""
    return sorted(p for p in profile.rglob("*") if p.is_file())


def _secret_findings(path: Path, root: Path, key: str = "secret") -> list[dict]:
    """The credential shapes a file carries (the file is never printed, only its path)."""
    items: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [{"key": "unreadable", "where": str(path.relative_to(root)), "detail": str(exc)}]
    for name, pattern in SECRET_PATTERNS:
        match = pattern.search(text)
        if match:
            items.append({
                "key": key,
                "where": str(path.relative_to(root)),
                "detail": f"carries a {name} value (`{match.group(0)[:6]}…`) — these files are read "
                          "by an agent that holds write credentials; name the environment variable, "
                          "never paste the value",
            })
    return items


def _skill_findings(skill_dir: Path, root: Path) -> list[dict]:
    """One skill's frontmatter, sections and reference links."""
    items: list[dict] = []
    path = skill_dir / SKILL_FILE
    where = str(path.relative_to(root))
    meta = frontmatter(path)
    if meta is None:
        items.append({
            "key": "skill-frontmatter",
            "where": where,
            "detail": "no `---` frontmatter block, so Hermes cannot index the skill (it needs "
                      "`name:` and `description:`)",
        })
    else:
        if meta.get("name", "") != skill_dir.name:
            items.append({
                "key": "skill-name",
                "where": where,
                "detail": f"frontmatter name is {meta.get('name')!r} but the directory is "
                          f"{skill_dir.name!r}; Hermes resolves a skill by its frontmatter name, so "
                          f"the profile would load `{meta.get('name')}` and find nothing",
            })
        if not meta.get("description", "").strip():
            items.append({
                "key": "skill-description",
                "where": where,
                "detail": "empty `description:` — that is the line the agent's skill index shows",
            })
    body = path.read_text(encoding="utf-8")
    for reference in sorted(set(REFERENCE_RE.findall(body))):
        if not (skill_dir / reference).is_file():
            items.append({
                "key": "skill-reference-missing",
                "where": where,
                "detail": f"names `{reference}`, which is not in the tree — a sync would leave the "
                          "profile with a rule that points at a file it does not have",
            })
    return items


def findings(root: Path = REPO_ROOT, agents_dir: Path = AGENTS_DIR) -> list[dict]:
    """Every way the host agents' tree can be broken. An empty list is the only pass."""
    items: list[dict] = []
    agents = (root / agents_dir) if not agents_dir.is_absolute() else agents_dir
    if not agents.is_dir():
        return [{
            "key": "agents-dir",
            "where": str(agents_dir),
            "detail": "no agents/ tree — the host agents' behaviour has nowhere to live, which is "
                      "the state issue #791 removes",
        }]

    profiles, manifest_items = read_manifest(agents)
    items.extend(manifest_items)
    if not any(REQUIRED_RULE in profile["rules"] for profile in profiles):
        items.append({
            "key": "manifest-rule",
            "where": f"{agents.name}/{MANIFEST}",
            "detail": f"no profile declares `{REQUIRED_RULE}` — the rule that every merge needs the "
                      "owner's approval is the one this tree exists to keep reviewable",
        })

    listed = {profile["name"] for profile in profiles}
    for profile in profiles:
        name = profile["name"]
        base = agents / name
        if not base.is_dir():
            items.append({
                "key": "profile-directory",
                "where": f"{agents.name}/{name}",
                "detail": "listed in the manifest, but the directory does not exist — there is "
                          "nothing to sync, so the profile's behaviour is still unversioned",
            })
            continue
        soul = base / SOUL
        if not soul.is_file():
            items.append({
                "key": "soul-missing",
                "where": f"{agents.name}/{name}",
                "detail": "no SOUL.md — the role this profile runs under is not in the tree",
            })
        else:
            text = soul.read_text(encoding="utf-8")
            for rule in profile["rules"]:
                if not STANDING_RULES[rule].search(text):
                    items.append({
                        "key": "standing-rule",
                        "where": f"{agents.name}/{name}/{SOUL}",
                        "detail": f"no longer states `{rule}` — the manifest says this profile's "
                                  "SOUL must carry it, and dropping it silently is the change this "
                                  "gate exists to make loud",
                    })
        skills_dir = base / SKILLS
        if skills_dir.is_dir():
            for skill_dir in sorted(p for p in skills_dir.iterdir() if (p / SKILL_FILE).is_file()):
                items.extend(_skill_findings(skill_dir, root))
        for path in _text_files(base):
            rel = path.relative_to(base)
            if path.name in FORBIDDEN_NAMES or any(part in FORBIDDEN_DIRS for part in rel.parts[:-1]):
                items.append({
                    "key": "forbidden-path",
                    "where": str(path.relative_to(root)),
                    "detail": "a profile's memory, sessions, logs or credentials are its data, not "
                              "its behaviour: they must never be committed",
                })
            items.extend(_secret_findings(path, root))

    for entry in sorted(p for p in agents.iterdir() if p.is_dir()):
        if entry.name not in listed:
            items.append({
                "key": "profile-unlisted",
                "where": str(entry.relative_to(root)),
                "detail": "a profile directory the manifest does not list — nothing syncs it and "
                          "nothing gates it, so it is behaviour with no audit trail",
            })
    return items


def report(root: Path = REPO_ROOT, agents_dir: Path = AGENTS_DIR) -> str:
    """What the gate reads: each profile with its SOUL, its skills and the rules it must keep."""
    agents = (root / agents_dir) if not agents_dir.is_absolute() else agents_dir
    profiles, manifest_items = read_manifest(agents) if agents.is_dir() else ([], [])
    lines = [f"[check-agent-profiles] {str(agents_dir)}/ ({len(profiles)} profile(s)):"]
    for profile in profiles:
        base = agents / profile["name"]
        soul = base / SOUL
        size = soul.stat().st_size if soul.is_file() else 0
        skills_dir = base / SKILLS
        skill_names = sorted(p.name for p in skills_dir.iterdir() if (p / SKILL_FILE).is_file()) \
            if skills_dir.is_dir() else []
        rules = ",".join(profile["rules"]) or "(none)"
        lines.append(f"  {profile['name']}: SOUL.md={'yes' if soul.is_file() else 'MISSING'} "
                     f"({size} b) skills={','.join(skill_names) or '(none)'} rules={rules}")
    items = findings(root, agents_dir)
    lines.append(f"[check-agent-profiles] {len(items)} finding(s)")
    for item in items:
        lines.append(f"  {item['key']}: {item['where']}: {item['detail']}")
    if manifest_items:
        lines.append(f"[check-agent-profiles] {len(manifest_items)} manifest finding(s)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("mode", nargs="?", default="check", choices=("check", "report"))
    parser.add_argument("--root", default=str(REPO_ROOT), help="tree to read (the tests use this)")
    parser.add_argument("--agents-dir", default=str(AGENTS_DIR),
                        help="path of the agents tree, relative to --root (the tests use this)")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"[check-agent-profiles] FAIL: {root} is not a directory", file=sys.stderr)
        return 2
    agents_dir = Path(args.agents_dir)
    if args.mode == "report":
        print(report(root, agents_dir))
        return 0
    items = findings(root, agents_dir)
    if not items:
        profiles, _ = read_manifest((root / agents_dir) if not agents_dir.is_absolute() else agents_dir)
        print(f"[check-agent-profiles] OK: {len(profiles)} host-agent profile(s), each with a "
              "SOUL.md stating the rules its manifest declares; every skill's frontmatter name "
              "matches its directory and carries no secret value")
        return 0
    for item in items:
        print(f"[check-agent-profiles] FAIL {item['key']}: {item['where']}: {item['detail']}")
    print(f"[check-agent-profiles] {len(items)} finding(s) — an instruction a credential-holding "
          "agent runs under is unreviewable when this tree is wrong, so this is a failure, not a "
          "style note", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
