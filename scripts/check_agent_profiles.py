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
  orchestrator must keep "never implement" and "never merge") — searched in the file's OWN VOICE,
  so a rule the SOUL merely quotes (an owner instruction it documents, a fenced sample, a
  blockquote of another lane's block) satisfies nothing (issue #922); a manifest that declares
  `never-merge` for no profile at all — the rule the issue exists to protect, deletable only in
  public — and a profile whose entry declares `rules: []`, reported `UNPROTECTED` because an entry
  that gates nothing must not read as an entry that passed;
* `state.db`, `sessions/`, `memories/`, `config.yaml` or `.env` in the tree — the profile's data is
  not behaviour, and it must never be committed.

Usage:
    python3 scripts/check_agent_profiles.py check    # exit 1 on any finding, 2 when the tree is unreadable
    python3 scripts/check_agent_profiles.py report   # print what the gate reads, always exit 0

Stdlib only.
"""

from __future__ import annotations

import argparse
import filecmp
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
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

#: A SOUL is read for what it INSTRUCTS, not for every string it contains (issue #922). A rule the
#: file merely quotes — an owner instruction it documents, a fenced sample, a blockquote of another
#: lane's block — is not a rule the agent runs under, and must not satisfy the gate for the rule it
#: quotes. These are the three shapes a quotation takes in this tree, each measured against all seven
#: committed SOULs before the strip was chosen: no legitimate statement lives in any of them.
FENCED_BLOCK = re.compile(r"^```.*?^```", re.M | re.S)
QUOTED_LINE = re.compile(r"^[ \t]*>.*$", re.M)
QUOTED_SPAN = re.compile(r'"[^"]*"', re.S)
#: Single quotes are deliberately NOT a quotation marker: `owner's` opens a span that would swallow
#: the rest of the sentence, and a stripper that deletes a legitimately stated rule is worse than the
#: bug it fixes (the same reason the imperative-form and exact-heading candidates were rejected:
#: `**Never merge, …**` and `**You never merge, …**` are both correct statements, and seven SOULs do
#: not share one heading).
#: The canonical fleet block, committed ONCE in `agents/standing-rules.md` so the same text can be compared
#: across profiles instead of trusted. A profile's SOUL must state it verbatim: thirteen paraphrases of one
#: rule is thirteen chances for it to stop being the rule (issue #873, acceptance criterion 1).
FLEET_BLOCK = "standing-rules.md"
FLEET_HEADING = "## Standing rules (fleet, learned 2026-10-28)"
#: The retired arming rule — "Arm auto-merge at PR creation" — that #873/super seeded with rule 16
#: (arm when DONE, and only on a base of `main`). A SOUL stating the retired bullet contradicts rule 16
#: (arming at creation is the wrong trigger, and a non-`main` base is exactly the stacked-arm hazard
#: #954 measured). The gate never treated it as a defect because it is not a canonical title and not a
#: duplicate — it sat invisible (measured: pr-reviever carries it once, `findings()` silent). It is report
#: debt like a duplicate: the removal is a protected SOUL write the owner routes.
RETIRED_ARM_RULE = "Arm auto-merge at PR creation"
#: Profiles whose block is not yet verbatim, each with a dated reason and the vehicle that owns the fix.
#: An exemption is legitimate only while it still describes a real gap: once the profile gains the block,
#: the entry is reported STALE and must be deleted, so the list cannot quietly become a permanent amnesty.
FLEET_EXEMPTIONS = "fleet-block-exemptions.json"


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


def stated_text(text: str) -> str:
    """The SOUL's own voice: fenced blocks, blockquote lines and `"…"` spans removed (issue #922).

    A standing rule must be STATED, not merely mentioned: a lane that documents the owner's
    instruction it overrides ("Never merge PRs …") quotes the rule without being put under a new one,
    and that quotation must not keep the gate green while the actual statement is deleted. Quotations
    are removed here and the rule is matched against what remains, so the two cases cannot be
    confused. Every committed SOUL was measured against this strip: each one that states a rule keeps
    stating it afterwards, and #921's architect SOUL (statement on one line, quote on another) keeps
    its statement while losing its quote.
    """
    without_fences = FENCED_BLOCK.sub("\n", text)
    without_quoted_lines = QUOTED_LINE.sub("", without_fences)
    return QUOTED_SPAN.sub("", without_quoted_lines)


def unprotected(profiles: list[dict]) -> list[str]:
    """Profiles whose manifest entry declares no rule: nothing in their SOUL is gated (issue #922).

    `rules: []` is not "no rules to check" — it is "this profile's rules are unenforced". It is
    reported, never failed: five of the seven committed profiles legitimately declare none yet, and a
    gate that is red for a reason nobody can act on is a gate that gets filtered.
    """
    return [profile["name"] for profile in profiles if not profile["rules"]]


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


def live_root_info() -> tuple[Path | None, str]:
    """(the profiles directory or None, where that path came from) — the two env vars mean DIFFERENT things.

    `agent_profile_sync.py` takes `HERMES_PROFILE_HOME` — **one profile's** home, e.g.
    `~/.hermes/profiles/llgenie-planner`. This gate needs the **parent** of that, the directory holding
    every profile. Accepting the singular name without that distinction would send the gate looking for
    `<a profile>/<lane>/SOUL.md`, find nothing, and report a green with the comparison skipped — the exact
    failure the audible skip exists to prevent, reintroduced through a variable name.
    """
    plural = os.environ.get("HERMES_PROFILES_HOME")
    singular = os.environ.get("HERMES_PROFILE_HOME")
    if plural:
        base, source = Path(plural).expanduser(), "$HERMES_PROFILES_HOME"
    elif singular:
        # The parent of anything exists — a typo, a bare filename, `/nonexistent-home` all have one —
        # so taking `.parent` unconditionally reported OK with no caveat while comparing nothing.
        base, source = Path(singular).expanduser().parent, "$HERMES_PROFILE_HOME (its parent directory)"
    else:
        base, source = Path.home() / ".hermes" / "profiles", "~/.hermes/profiles"
    # A profiles home HOLDS profiles. `exists()` is not the test: a directory that contains no
    # `<name>/SOUL.md` cannot answer the question, and must take the skip path with its caveat.
    holds_a_profile = base.is_dir() and any((d / "SOUL.md").is_file() for d in base.iterdir() if d.is_dir())
    return (base if holds_a_profile else None), source


def live_root(root: Path = REPO_ROOT) -> Path | None:
    """Where the host profiles live, or None when this checkout is not on a machine that has them.

    CI has no `~/.hermes/profiles/`, so the invariant is checked where it can be: on the host that holds
    the live rulebooks. A tree-only checkout skips it rather than failing, which keeps the gate honest
    about what it can see instead of pretending the comparison happened.
    """
    return live_root_info()[0]


def _iso(ts: float) -> str:
    """A UTC stamp a reader can compare against their own run (#924)."""
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


#: #968 moved the stamp into this module so `agent_profile_sync.py` imports it; keep the older name as an
#: alias of the one canonical formatter (issue #924).
_stamp = _iso


#: When this process started. A live file edited after this moment changed *during* the check, which makes
#: the comparison a snapshot rather than a verdict (issue #924).
_STARTED = time.time()


def snapshot_caveat(root: Path = REPO_ROOT, agents_dir: Path = AGENTS_DIR,
                    live: Path | None = None, started: float | None = None) -> str | None:
    """The line that says the live reference moved while we were reading it, or None.

    The live profile is not frozen: another lane rewrites it mid-review, so a `FAIL live-longer` can become
    `OK` with the tree byte-identical — measured on #919 (tree 22,175 b; live 24,791 b then 21,349 b minutes
    later). The gate cannot make a moving target stand still; what it can do is stop implying it compared
    against a still one (issue #924).
    """
    agents = (root / agents_dir) if not agents_dir.is_absolute() else agents_dir
    base = live if live is not None else live_root(root)
    moment = _STARTED if started is None else started
    if base is None or not agents.is_dir():
        return None
    profiles, _ = read_manifest(agents)
    moved: list[str] = []
    for profile in profiles:
        live_profile = base / profile["name"]
        tree_profile = agents / profile["name"]
        if not live_profile.is_dir() or not tree_profile.is_dir():
            continue
        for path in sorted(tree_profile.rglob("*")):
            if not path.is_file():
                continue
            counterpart = live_profile / path.relative_to(tree_profile)
            if not counterpart.is_file():
                continue
            mtime = counterpart.stat().st_mtime
            if mtime >= moment:
                moved.append(f"{profile['name']}/{path.relative_to(tree_profile)} "
                             f"(live mtime {_iso(mtime)})")
    if not moved:
        return None
    return ("the live reference changed WHILE this check was reading it: "
            + ", ".join(moved[:3])
            + (" …" if len(moved) > 3 else "")
            + " — this comparison is a SNAPSHOT of a moving file; re-run to confirm")


def source_time(agents: Path, name: str, path: Path) -> float:
    """When the tree copy was COMMITTED — not its mtime, which a fresh clone resets to now.

    A clone sets every file's mtime to checkout time, so an mtime comparison would say the tree is newer
    than any live file and quietly disarm this guard on exactly the checkout that runs it. The commit
    that last touched the path is the stable answer; an untracked fixture file falls back to its mtime.
    """
    rel = path.relative_to(agents.parent).as_posix()
    try:
        out = subprocess.run(["git", "-C", str(agents.parent), "log", "-1", "--format=%ct", "--", rel],
                             capture_output=True, text=True, timeout=20, check=False)
        if out.returncode == 0 and out.stdout.strip():
            return float(out.stdout.strip())
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return path.stat().st_mtime


def live_edited_findings(root: Path = REPO_ROOT, agents_dir: Path = AGENTS_DIR,
                         live: Path | None = None) -> list[dict]:
    """Every live file EDITED AFTER its tree copy was committed — a hand written edit, named.

    The sync is one-way: `make sync-agent-profile` copies the tree INTO the live profile, never the
    reverse. So a live file whose mtime is NEWER than the tree copy's source commit, and whose content
    differs, is not drift to re-take: it is the lane's own unversioned edit, and overwriting it with the
    tree — or silently re-copying it into the tree — would launder an edit nobody reviewed (issue #968).
    The finding names the profile, both sizes and the remedy, so the change stays an issue+PR under
    `agents/<profile>/` and the gate reports the drift instead of chasing it.
    """
    agents = (root / agents_dir) if not agents_dir.is_absolute() else agents_dir
    base = live if live is not None else live_root(root)
    if base is None or not agents.is_dir():
        return []
    profiles, _ = read_manifest(agents)
    items: list[dict] = []
    for profile in profiles:
        name = profile["name"]
        live_profile = base / name
        if not live_profile.is_dir():
            continue
        tree_profile = agents / name
        for path in sorted(tree_profile.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(tree_profile)
            counterpart = live_profile / rel
            if not counterpart.is_file():
                continue
            # The harm is a live-only edit: content differs AND the live file is newer than when the
            # tree copy was committed. Either alone is not it — an identical file writes nothing, and
            # a newer file without a content difference has nothing to reconcile.
            if filecmp.cmp(path, counterpart, shallow=False):
                continue
            tree, there = path.stat().st_size, counterpart.stat().st_size
            src, live_mtime = source_time(agents, name, path), counterpart.stat().st_mtime
            if live_mtime <= src + 1:  # same second of slack as the sync's own moving-reference guard
                continue
            items.append({
                "key": "live-edited-not-tree",
                "where": f"{tree_profile.name}/{rel}",
                "detail": f"the LIVE profile was edited at {_iso(live_mtime)}, AFTER the tree copy was "
                          f"committed at {_iso(src)} — the tree has {tree} b, the live profile has "
                          f"{there} b. Sync is one-way (tree → live), so this edit exists only in the "
                          f"live profile: commit it via an issue+PR under agents/{name}/, then "
                          f"`make sync-agent-profile PROFILE={name}` clears it. Do not re-take the "
                          f"live file into the tree.",
            })
    return items


def shrink_findings(root: Path = REPO_ROOT, agents_dir: Path = AGENTS_DIR,
                    live: Path | None = None) -> list[dict]:
    """Every live rulebook LONGER than its in-tree copy — the truncated seed, caught before a sync.

    This is the direction that loses a rule silently: `sync` copies the tree over the profile, so a
    tree file that is a prefix of the live one replaces it and every gate stays green (issue #791).
    """
    agents = (root / agents_dir) if not agents_dir.is_absolute() else agents_dir
    base = live if live is not None else live_root(root)
    if base is None or not agents.is_dir():
        return []
    profiles, _ = read_manifest(agents)
    items: list[dict] = []
    for profile in profiles:
        live_profile = base / profile["name"]
        if not live_profile.is_dir():
            continue
        tree_profile = agents / profile["name"]
        for path in sorted(tree_profile.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(tree_profile)
            counterpart = live_profile / rel
            if not counterpart.is_file():
                continue
            tree, there = path.stat().st_size, counterpart.stat().st_size
            # CONTENT decides, and size is only context. A live file can be bigger because it repeats a
            # block (measured: five SOULs carried the canonical fleet block twice after an append), and a
            # size test calls that a truncated seed when the tree carries every live rule already. The
            # question that matters is the one `sync` asks: would a copy delete a line the live file has?
            tree_lines = {ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()}
            live_lines = {ln.strip() for ln in counterpart.read_text(encoding="utf-8").splitlines()
                          if ln.strip()}
            missing = live_lines - tree_lines
            if missing and there > tree:
                items.append({
                    "key": "live-longer",
                    "where": f"{tree_profile.name}/{rel}",
                    "detail": f"the tree has {tree} b, the live profile has {there} b "
                              f"(live mtime {_iso(counterpart.stat().st_mtime)}) and carries "
                              f"{len(missing)} line(s) the tree lacks — the seed is a prefix of the "
                              f"rulebook, so `make sync-agent-profile` would replace {there} bytes with "
                              f"{tree} and no gate would notice (issue #791). First: "
                              f"{sorted(missing)[0][:80]!r}",
                })
                continue
            if missing:
                items.append({
                    "key": "live-lines-missing",
                    "where": f"{tree_profile.name}/{rel}",
                    "detail": f"the tree copy carries {len(missing)} line(s) the live profile has, "
                              f"although it is {tree} b against {there} b — size says nothing here, and a "
                              f"sync would delete rulebook that exists only live (issue #791). First: "
                              f"{sorted(missing)[0][:90]!r}",
                })
    return items


def fleet_block(agents: Path) -> "str | None":
    """The canonical fleet section, exactly as `agents/standing-rules.md` states it."""
    path = agents / FLEET_BLOCK
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    if FLEET_HEADING not in text:
        return None
    return FLEET_HEADING + "\n\n" + text.split(FLEET_HEADING, 1)[1].strip("\n")


def _stated_blocks(soul_text: str) -> "list[str]":
    """Every fleet section the SOUL states, in order — a SOUL may carry more than one.

    A lane that already had a partial fleet section and then appended the canonical block states BOTH, and
    reading only the first would report drift it does not have. The rule is "the canonical block is in this
    SOUL verbatim", so any section satisfying it counts; `_first_missing` then reads the closest one.
    """
    out: list[str] = []
    parts = soul_text.split(FLEET_HEADING)
    for rest in parts[1:]:
        body = rest.split("\n## ", 1)[0].strip("\n")
        out.append(FLEET_HEADING + "\n\n" + body)
    return out


def _stated_block(soul_text: str) -> "str | None":
    """The fleet section a SOUL states, or None when it states none (the longest, for a useful diff)."""
    blocks = _stated_blocks(soul_text)
    return max(blocks, key=len) if blocks else None


def _first_missing(canonical: str, stated: str | None) -> str:
    """The first canonical bullet the SOUL does not state — the line a reader can act on."""
    if stated is None:
        for line in canonical.splitlines():
            if line.startswith("- **"):
                return line[:120]
        return canonical.splitlines()[0][:120]
    for line in canonical.splitlines():
        if line.startswith("- **") and line not in stated:
            return line[:120]
    return "(the section is present but differs from the canonical text)"


def read_fleet_exemptions(agents: Path) -> tuple[dict, list[dict]]:
    """`{profile: reason}` plus any finding the exemption list itself carries."""
    path = agents / FLEET_EXEMPTIONS
    if not path.is_file():
        return {}, []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, [{"key": "fleet-exemptions", "where": str(path.relative_to(path.parents[1])),
                     "detail": f"not valid JSON: {exc}"}]
    items = raw if isinstance(raw, list) else raw.get("exemptions", [])
    out: dict[str, str] = {}
    owners: dict[str, str] = {}
    bad: list[dict] = []
    for entry in items:
        name = entry.get("profile") if isinstance(entry, dict) else None
        reason = (entry.get("reason") or "") if isinstance(entry, dict) else ""
        owner = (entry.get("owner") or "") if isinstance(entry, dict) else ""
        if not name or not reason.strip() or not owner.strip():
            missing = [part for part, value in (("profile", name), ("reason", reason), ("owner", owner))
                       if not (value or "").strip()]
            bad.append({"key": "fleet-exemptions",
                        "where": str(path.relative_to(path.parents[1])),
                        "detail": f"entry {entry!r} has no {' and no '.join(missing)} — a gap with no owner "
                                  "is a gap nobody closes, and one with no written reason is an amnesty"})
            continue
        out[name] = reason.strip()
        owners[name] = owner.strip()
    return out, bad


def _fleet_findings(agents: Path, profiles: list[dict]) -> list[dict]:
    """Every profile's SOUL must state the canonical fleet block verbatim (#873).

    An exemption downgrades a real drift to a stale-report once the profile is fixed, so the gap is either
    visible as a failing gate or visible as a debt the owner still owes - never invisible.
    """
    canonical = fleet_block(agents)
    if canonical is None:
        # A tree that never adopted the canonical block is not a finding - but a tree where a SOUL states
        # the heading while the single copy is gone IS: deleting the source must not be how a drift passes.
        claims = [p["name"] for p in profiles
                  if (agents / p["name"] / SOUL).is_file()
                  and FLEET_HEADING in (agents / p["name"] / SOUL).read_text(encoding="utf-8")]
        if not claims:
            return []
        return [{"key": "fleet-block-source",
                 "where": str((agents / FLEET_BLOCK).relative_to(agents.parent)),
                 "detail": f"`{FLEET_BLOCK}` is missing or has no heading, but {claims} state the fleet "
                           "heading — without the single copy nothing can be compared, so the check would "
                           "pass by not looking"}]
    exempt, items = read_fleet_exemptions(agents)
    stated_names = {p["name"] for p in profiles}
    for name in sorted(set(exempt) - stated_names):
        items.append({"key": "fleet-exemption-unknown",
                      "where": str((agents / FLEET_EXEMPTIONS).relative_to(agents.parent)),
                      "detail": f"exemption for `{name}`, which the manifest does not list — remove it "
                                "or list the profile"})
    for profile in profiles:
        name = profile["name"]
        soul = agents / name / SOUL
        if not soul.is_file():
            continue
        stated = _stated_block(soul.read_text(encoding="utf-8"))
        if stated == canonical or canonical in _stated_blocks(soul.read_text(encoding="utf-8")):
            if name in exempt:
                items.append({"key": "fleet-exemption-stale",
                              "where": str(soul.relative_to(agents.parent)),
                              "detail": f"`{name}` now states the canonical block verbatim, so its "
                                        f"exemption in {FLEET_EXEMPTIONS} is stale — delete it, or the "
                                        "list stops meaning anything"})
            continue
        if name in exempt:
            continue        # a real gap, owned by a named vehicle — reported by `report`, not failed
        items.append({"key": "fleet-block-drift",
                      "where": str(soul.relative_to(agents.parent)),
                      "detail": f"`{name}` does not state the canonical fleet block from {FLEET_BLOCK} "
                                f"verbatim; first missing bullet: {_first_missing(canonical, stated)}"})
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
    items.extend(shrink_findings(root, agents_dir))
    items.extend(live_edited_findings(root, agents_dir))
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
            stated = stated_text(text)
            where = f"{agents.name}/{name}/{SOUL}"
            for rule in profile["rules"]:
                if STANDING_RULES[rule].search(stated):
                    continue
                if STANDING_RULES[rule].search(text):
                    items.append({
                        "key": "standing-rule-quoted",
                        "where": where,
                        "detail": f"mentions `{rule}` only inside a quotation — a fenced code block, "
                                  "a blockquote line or a `\"…\"` span — and the manifest says this "
                                  "profile's SOUL must STATE it. Quoting an instruction (the owner's, "
                                  "another lane's block) does not put this profile under it, so this "
                                  "file no longer states the rule it is gated on (issue #922)",
                    })
                    continue
                items.append({
                    "key": "standing-rule",
                    "where": where,
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

    items.extend(_fleet_findings(agents, profiles))

    for entry in sorted(p for p in agents.iterdir() if p.is_dir()):
        if entry.name not in listed:
            items.append({
                "key": "profile-unlisted",
                "where": str(entry.relative_to(root)),
                "detail": "a profile directory the manifest does not list — nothing syncs it and "
                          "nothing gates it, so it is behaviour with no audit trail",
            })
    return items


def _duplicate_rule_debts(agents: Path, profiles: list[dict]) -> list[tuple[str, str]]:
    """Every (profile, canonical-rule-title) stated more than once in a SOUL — a second source of truth.

    The gate compares the canonical block verbatim, so a duplicate in the lane-rules section is *not*
    seen by `findings()` — but it is the exact drift mechanism #972 caught (a SOUL "had 16 bullets" yet
    paraphrased rule 13 because the block sat beside a stray copy). Count occurrences, not a bullet
    total. Reported, never failed: the removal is a protected SOUL write the owner routes.
    """
    canonical = fleet_block(agents)
    if canonical is None:
        return []
    # the title text inside the emphasis, punctuation-trimmed on BOTH ends — `**remedy.**`,
    # `**remedy**` and `remedy` are the same rule, and a duplicate drifts by punctuation before it
    # drifts by text (#972). Match the core phrase so both copies of a duplicated bullet are counted.
    titles = []
    for line in canonical.splitlines():
        if line.startswith("- **"):
            end = line.find("**", 3)
            title = line[4:end].strip()                  # text after the leading `**` (indices 2-3)
            title = title.rstrip(".,:;!?")                  # drop trailing punctuation (a full stop drift)
            if title:
                titles.append(title)
    # Count occurrences of the title in a BOLDED-RULE form (`**Title**` or `**Title.**`) — a second
    # statement of the rule, whether as a `- **` bullet or a bolded paragraph in a lane section.
    # A bare prose mention of the rule is not a statement of it. (Measured: documentation's rule 13 has
    # two `- **` bullets; implementer's rule 13/14 restate in bold paragraphs outside the fence — both
    # are real duplicates. A sentence like "there is no `never push` carve-out" is not.)
    import re as _re
    debts: list[tuple[str, str]] = []
    for profile in profiles:
        soul = agents / profile["name"] / SOUL
        if not soul.is_file():
            continue
        text = soul.read_text(encoding="utf-8")
        for title in titles:
            # the title, optionally with trailing punctuation, inside emphasis: `**Title**` / `**Title.**`
            pat = _re.compile(r"\*\*" + _re.escape(title) + r"[\u002e\u002c\u003a\u003b\u0021\u003f]?\*\*")
            if len(pat.findall(text)) > 1:
                debts.append((profile["name"], title))
    return sorted(debts)


def _retired_rule_debts(agents: Path, profiles: list[dict]) -> list[tuple[str, str]]:
    """Every (profile, retired-rule) a SOUL still states — a contradiction of the rule that replaced it.

    The retired "Arm auto-merge at PR creation" bullet is not a canonical title and not (necessarily) a
    duplicate, so the gate's other checks never saw it — measured: pr-reviever carries it once and
    `findings()` was silent about a SOUL that contradicts rule 16 (arm when done / main-base only, #873,
    #950). A lane running under it would arm at creation onto a non-`main` base, the exact stacked-arm
    hazard #954 measured. This is the same class as a duplicate: a protected SOUL write the owner routes,
    so it is REPORT debt (visible, never a hard gate red).
    """
    if not (agents / FLEET_BLOCK).is_file():
        return []
    import re as _re
    pat = _re.compile(r"\*\*" + _re.escape(RETIRED_ARM_RULE) + r"\b[^\n]*?\*\*")
    debts: list[tuple[str, str]] = []
    for profile in profiles:
        soul = agents / profile["name"] / SOUL
        if not soul.is_file():
            continue
        text = soul.read_text(encoding="utf-8")
        if pat.search(text):
            debts.append((profile["name"], RETIRED_ARM_RULE))
    return sorted(debts)


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
    idle = unprotected(profiles)
    if idle:
        # issue #922: an entry that gates nothing must not read as an entry that passed. A report,
        # not a finding - a profile may legitimately declare no rule yet.
        lines.append(f"[check-agent-profiles] UNPROTECTED: {', '.join(idle)} declare(s) no standing "
                     "rule, so nothing in that SOUL.md is gated (not the same as passing)")
    items = findings(root, agents_dir)
    lines.append(f"[check-agent-profiles] {len(items)} finding(s)")
    for item in items:
        lines.append(f"  {item['key']}: {item['where']}: {item['detail']}")
    if manifest_items:
        lines.append(f"[check-agent-profiles] {len(manifest_items)} manifest finding(s)")
    # debts the gate does not fail on, because a named owner is working them: visible, never silent
    exempt, _ = read_fleet_exemptions(agents_dir if agents_dir.is_absolute() else root / agents_dir)
    if exempt:
        lines.append("")
        lines.append("fleet block — still owned, not yet verbatim:")
        for name, reason in sorted(exempt.items()):
            lines.append(f"  {name}: {reason}")
    dups = _duplicate_rule_debts(agents, profiles)
    if dups:
        lines.append("")
        lines.append("duplicate canonical rule (one bullet, one place — #972):")
        for name, title in dups:
            lines.append(f"  {name}: {title} stated more than once")
    retired = _retired_rule_debts(agents, profiles)
    if retired:
        lines.append("")
        lines.append("retired canonical rule still stated (rule 16 replaced it — #873, #950):")
        for name, rule in retired:
            lines.append(f"  {name}: {rule}")
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
    # A skip must be AUDIBLE (issue #791 review): a check that cannot compare must say so, or a reader
    # concludes it compared. That distinction — "compared and fine" vs "could not compare" — is the same
    # one that `verified` vs `verified: N identical` failed to make, and it is how a truncated seed
    # reached a green gate in the first place.
    live_base, live_source = live_root_info()
    if live_base is None:
        print("[check-agent-profiles] live-profile comparison SKIPPED: no profiles directory at "
              f"{live_source} — tree checks only, and the live rulebooks were NOT compared", file=sys.stderr)
    items = findings(root, agents_dir)
    profiles, _ = read_manifest((root / agents_dir) if not agents_dir.is_absolute() else agents_dir)
    for name in unprotected(profiles):
        # issue #922: an entry with no rule gates nothing. Named, never failed - and never silent,
        # because a green line is what made "rules: []" read as compliance.
        print(f"[check-agent-profiles] UNPROTECTED {name}: the manifest declares no standing rule for "
              "this profile, so nothing in its SOUL.md is gated — that is not the same as passing")
    snapshot = snapshot_caveat(root, agents_dir, live_base)
    if snapshot:
        # Audible, and never a failure: the tree is not at fault when another lane rewrites the reference
        # mid-run, but a reader must not take the comparison for a verdict (#924).
        print(f"[check-agent-profiles] live-profile comparison is a SNAPSHOT: {snapshot}",
              file=sys.stderr)
    if not items:
        caveat = (" — tree checks only, LIVE RULEBOOKS NOT COMPARED" if live_base is None else "")
        if snapshot:
            caveat += " — the live reference moved DURING this run, so the comparison is a snapshot"
        print(f"[check-agent-profiles] OK: {len(profiles)} host-agent profile(s), each with a "
              "SOUL.md stating the rules its manifest declares; every skill's frontmatter name "
              f"matches its directory and carries no secret value{caveat}")
        # Informational, never a failure: a canonical rule stated twice is debt the gate must not
        # stay silent about even when green (one bullet, one place — #972); the removal is a
        # protected SOUL write the owner routes.
        dups = _duplicate_rule_debts(root / agents_dir if not agents_dir.is_absolute() else agents_dir,
                                     profiles)
        for name, title in dups:
            print(f"[check-agent-profiles] note: {name} states {title!r} more than once "
                  "(duplicate canonical rule — one bullet, one place, #972)", file=sys.stderr)
        retired = _retired_rule_debts(root / agents_dir if not agents_dir.is_absolute() else agents_dir,
                                     profiles)
        for name, rule in retired:
            print(f"[check-agent-profiles] note: {name} still states the retired {rule!r} "
                  "(rule 16 replaced it — #873, #950)", file=sys.stderr)
        return 0
    for item in items:
        print(f"[check-agent-profiles] FAIL {item['key']}: {item['where']}: {item['detail']}")
    print(f"[check-agent-profiles] {len(items)} finding(s) — an instruction a credential-holding "
          "agent runs under is unreviewable when this tree is wrong, so this is a failure, not a "
          "style note", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
