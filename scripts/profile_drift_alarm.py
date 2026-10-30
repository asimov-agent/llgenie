#!/usr/bin/env python3
"""Turn profile drift into ONE tracked issue, on a timer, where the live profiles exist (issue #928).

`make check-agent-profiles` runs in `ci-unit`, but its strongest finding — a tree copy that is a **prefix of
the live rulebook** — needs `~/.hermes/profiles/`, which a CI runner does not have. So `live-longer` was
enforceable only by whoever remembered to run the gate by hand, and a control whose trigger is memory is not a
control: it fired twice in one night, both times after the truncated tree had already been pushed.

This script is the caller that was missing. It runs the same check, keeps ONLY `live-longer`, and:

  (default)  prints the drift and exits 3 — read-only, safe anywhere;
  --file-issue  opens **one** issue titled `profile drift: N tree copies are truncated seeds`, or comments on the
                existing open one, so a recurring condition never becomes a stream of duplicate issues.

Why one issue and not one per finding: the drift is a condition of the tree, not a property of a file, and the
house already learned this the expensive way with duplicate-issue storms. The title carries the count, the body
carries each file with both sizes and the direction of the fix (take the tree copy FROM the live file).

Usage
  python3 scripts/profile_drift_alarm.py                    # print, exit 3 on drift
  python3 scripts/profile_drift_alarm.py --file-issue       # file/refresh the single issue
  python3 scripts/profile_drift_alarm.py --repo owner/name  # default: asimov-agent/llgenie
"""
from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TITLE = "profile drift: {summary}"

FIX = """\
## How to fix

Take each tree copy **from the live file**, never the other way round, by allowlist — `SOUL.md` plus the
profile's own skill directory. Never walk a profile home: a walk once copied 15,963 files including a 73 MB
`state.db` into the tree, i.e. state mistaken for rules.

```
CHECK=1 make agent-profile-report     # byte-for-byte, after the re-take
make profile-drift                    # must print `live comparisons: N` and exit 0
```

`make sync-agent-profile` in the other direction is refused by `shrinks()` (issue #924) when the tree copy is a
content subset or below `SHRINK_FLOOR` — that guard is the last line, not the fix.
"""


def _check_module():
    """The real gate, imported rather than re-implemented — a copy of its logic would drift from it too."""
    spec = importlib.util.spec_from_file_location("check_agent_profiles_gate",
                                                  REPO_ROOT / "scripts" / "check_agent_profiles.py")
    if spec is None or spec.loader is None:      # a missing or unreadable gate is a FAILURE, not a skip
        raise SystemExit("[profile-drift] FAIL: cannot load scripts/check_agent_profiles.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ALLOWLIST = ("SOUL.md", "skills/")          # what the tree tracks: the profile's rules and its own skills


def tracked(rel: str) -> bool:
    """Live profiles hold STATE as well as rules — `.curator_backups/`, `.backup.lock`, caches — and walking one
    home copied 15,963 files including a 73 MB `state.db` into the tree once already. Compare only what the
    tree is supposed to carry, on BOTH sides, or 52,165 files report as "missing" (measured)."""
    if rel == "SOUL.md":
        return True
    if not rel.startswith("skills/"):
        return False
    # `.archive/`, `.curator_backups/`, lock files: the profile's own housekeeping, not the tree's business.
    return not any(part.startswith(".") for part in rel.split("/")[1:])


def compare(root: Path, agents_dir: str, live: Path) -> list[dict]:
    """Every tree file against its live counterpart, with the DIRECTION of the difference named.

    Size alone cannot say which side lost lines, and the direction decides what a sync would destroy:

      identical   - no finding
      truncated   - the tree is missing live lines (tree subset of live): a sync DELETES live behaviour
      diverged    - both sides have lines the other lacks: a sync destroys work on BOTH sides (the #924 case)
      tree-ahead  - the tree carries lines live no longer has, and nothing else: a sync ADDS to live
      missing     - live has the file, the tree does not (or the reverse): structural, and never silent

    `tree-ahead` is not reported as a defect - a lane's copy legitimately runs ahead while the live file is being
    rewritten - but `diverged` is strictly worse than `truncated` and must never be reported as lag.
    """
    agents = root / agents_dir
    if not agents.is_dir():
        return []
    import json
    try:
        manifest = json.loads((agents / "manifest.json").read_text(encoding="utf-8"))
        names = [profile["name"] for profile in manifest.get("profiles", [])]
    except (OSError, ValueError, KeyError):
        return []
    items: list[dict] = []
    for name in names:
        tree_profile = agents / name
        live_profile = live / name
        if not live_profile.is_dir() or not tree_profile.is_dir():
            continue
        seen: set[str] = set()
        for path in sorted(tree_profile.rglob("*")):
            if not path.is_file():
                continue
            rel = str(path.relative_to(tree_profile))
            if not tracked(rel):
                continue
            seen.add(rel)
            counterpart = live_profile / rel
            if not counterpart.is_file():
                items.append({"kind": "missing", "where": f"{name}/{rel}",
                              "detail": "the tree carries this file and the live profile does not "
                                        "(`make sync-agent-profile` would create it live)"})
                continue
            try:
                tree_lines = {l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()}
                live_lines = {l for l in counterpart.read_text(encoding="utf-8").splitlines() if l.strip()}
            except OSError:
                items.append({"kind": "missing", "where": f"{name}/{rel}",
                              "detail": "cannot be read on one side, so it cannot be compared"})
                continue
            tree_only, live_only = tree_lines - live_lines, live_lines - tree_lines
            tree_b, live_b = path.stat().st_size, counterpart.stat().st_size
            if not tree_only and not live_only:
                continue
            if live_only and not tree_only:
                kind = "truncated"
                detail = (f"the tree has {tree_b} b, the live profile has {live_b} b, and the tree is missing "
                          f"{len(live_only)} live line(s): a sync would DELETE that behaviour")
            elif tree_only and live_only:
                kind = "diverged"
                detail = (f"the tree has {tree_b} b, the live profile has {live_b} b, with {len(tree_only)} "
                          f"tree-only and {len(live_only)} live-only line(s): a sync destroys work on BOTH sides")
            else:
                kind = "tree-ahead"
                detail = (f"the tree has {tree_b} b, the live profile has {live_b} b, and the tree carries "
                          f"{len(tree_only)} line(s) live no longer has")
            items.append({"kind": kind, "where": f"{name}/{rel}", "detail": detail})
        # NOT enumerated from the live side: a live profile carries every INSTALLED skill (3,184 files here),
        # while the tree is a CURATED subset - its own rules and its own skills. "Live has a file the tree does
        # not" is therefore not drift, it is the design; the tree is authoritative about what it carries.
    return items


def drift_items(items: list[dict]) -> list[dict]:
    """Only `live-longer`, and sorted, so two runs of the same tree produce the same issue body."""
    return sorted((item for item in items if item["key"] == "live-longer"), key=lambda item: item["where"])


def summary_of(items: list[dict]) -> str:
    """`2 truncated, 1 diverged` — the category is what a reader acts on, so it belongs in the TITLE."""
    counts: dict[str, int] = {}
    for item in items:
        counts[item["kind"]] = counts.get(item["kind"], 0) + 1
    return ", ".join(f"{n} {kind}" for kind, n in sorted(counts.items())) or "0 defects"


def _lines_note(item: dict) -> str:
    detail = item["detail"]
    import re
    match = re.search(r"(\d+) tree-only and (\d+) live-only", detail)
    if match:
        return f"{match.group(1)} tree-only · {match.group(2)} live-only"
    match = re.search(r"missing (\d+) live line", detail) or re.search(r"carries (\d+) line", detail)
    return f"{match.group(1)} missing live" if match and "missing" in match.group(0) else (match.group(0) if match else "?")


def render(items: list[dict], compared: int, ahead: int = 0, where: str = "") -> str:
    lines = [
        "**A tree copy would lose work on the next sync** — and every gate would stay green (issues #791, #924,",
        "#928). The DIRECTION decides what a sync destroys; each row names its category.",
        "",
        f"Measured by `scripts/profile_drift_alarm.py`: **{summary_of(items)}**, "
        f"**{compared} live comparison(s)**"
        + (f", plus **{ahead} tree-ahead** (a copy running ahead of a file being rewritten — not a defect)"
           if ahead else "") + ".",
        "",
    ]
    if where:
        # WHICH tree was measured, by sha. Without it a body reads identically for main and for a lane's
        # in-flight branch — and an issue that does not say where it measured is a claim about time, not a
        # branch (measured: a control run against a feature worktree filed this issue with "the tree" in it).
        lines += [f"Measured on `{where}` — a feature-branch tree and `main` are different answers.", ""]
    lines += [
        "| category | tree copy | tree | live | lines |",
        "|---|---|---|---|---|",
    ]
    for item in items:
        detail = item["detail"]
        # "the tree has 22296 b, the live profile has 23349 b — …"
        try:
            tree = int(detail.split("the tree has ", 1)[1].split(" b", 1)[0])
            live = int(detail.split("the live profile has ", 1)[1].split(" b", 1)[0])
            delta = f"+{live - tree:,} b"
        except (IndexError, ValueError):
            tree = live = None
            delta = "?"
        lines.append(f"| `{item['kind']}` | `{item['where']}` | {tree if tree is not None else '?'} | "
                     f"{live if live is not None else '?'} | {_lines_note(item)} |")
    lines += ["", FIX, "---", "_Filed automatically by `scripts/profile_drift_alarm.py` (issue #928)._"]
    return "\n".join(lines)


def gh(*args: str, repo: str) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args, "--repo", repo], capture_output=True, text=True)


def existing_open_issue(repo: str) -> dict | None:
    """The open issue this script owns, if any — matched on the title PREFIX, so the count can change."""
    # Deliberately NOT `--search`: GitHub's issue search is eventually consistent, and a just-created issue
    # was invisible to it for the next run — which filed a SECOND issue for the same condition (measured:
    # #930 then #931, one minute apart). Listing open issues and matching the title prefix locally is exact
    # and has no index to lag behind.
    listed = gh("issue", "list", "--state", "open", "--limit", "300",
                "--json", "number,title", repo=repo)
    if listed.returncode != 0:
        return None
    import json
    try:
        issues = json.loads(listed.stdout or "[]")
    except ValueError:
        return None
    for issue in issues:
        if issue["title"].startswith("profile drift:"):
            return issue
    return None


def file_or_refresh(items: list[dict], compared: int, repo: str, ahead: int = 0, where: str = "") -> str:
    body = render(items, compared, ahead, where)
    title = TITLE.format(summary=summary_of(items))
    found = existing_open_issue(repo)
    if found:
        # A comment, not an edit: the history of a recurring condition is worth more than a tidy title.
        posted = gh("issue", "comment", str(found["number"]), "--body", body, repo=repo)
        return f"refreshed #{found['number']}" if posted.returncode == 0 else f"comment failed: {posted.stderr.strip()}"
    created = gh("issue", "create", "--title", title, "--body", body, repo=repo)
    return ((created.stdout or "").strip().splitlines()[-1] if created.returncode == 0
            else f"create failed: {created.stderr.strip()}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default="asimov-agent/llgenie")
    parser.add_argument("--file-issue", action="store_true",
                        help="open or refresh the single tracking issue (needs gh auth)")
    parser.add_argument("--root", default=str(REPO_ROOT), help="tree to read (the tests use this)")
    parser.add_argument("--agents-dir", default="agents")
    args = parser.parse_args(argv)

    gate = _check_module()
    root = Path(args.root).resolve()
    live, where = gate.live_root_info()
    if live is None:
        print(f"[profile-drift] SKIPPED: no live profiles at {where} — this alarm exists to run WHERE THEY "
              f"EXIST, so a run here proves nothing", file=sys.stderr)
        return 2  # distinct from 0: "could not compare" must never read as "compared and clean"
    found = compare(root, args.agents_dir, live)
    compared = len(gate.read_manifest((root / args.agents_dir))[0])
    # Only the destructive directions are filed. `tree-ahead` is a lane's copy running ahead of a file being
    # rewritten, and a target that is red for that teaches the fleet to filter the alarm (issue #928).
    defects = [i for i in found if i["kind"] in ("truncated", "diverged", "missing")]
    ahead = [i for i in found if i["kind"] == "tree-ahead"]
    counts = {}
    for item in defects:
        counts[item["kind"]] = counts.get(item["kind"], 0) + 1
    summary = ", ".join(f"{n} {kind}" for kind, n in sorted(counts.items())) or "0 defects"
    print(f"[profile-drift] live comparisons: {compared} · {summary} · {len(ahead)} tree-ahead")
    for item in ahead:
        print(f"  tree-ahead (not a failure): {item['where']} — {item['detail']}")
    if not defects:
        return 0
    for item in defects:
        print(f"  {item['kind']}: {item['where']}: {item['detail']}")
    if args.file_issue:
        sha = subprocess.run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True).stdout.strip() or "unknown"
        print(f"[profile-drift] {file_or_refresh(defects, compared, args.repo, ahead=len(ahead), where=f'{root} @ {sha}')}")
    return 3


if __name__ == "__main__":
    sys.exit(main())
