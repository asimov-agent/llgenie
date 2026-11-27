#!/usr/bin/env python3
"""Deterministic halves of the weekly fleet-architecture review (issue #3106).

`brief` reads only the tree: docs/ARCHITECTURE.md, agents/manifest.json and every
agents/<profile>/SOUL.md. `publish` files AT MOST ONE refined issue from the agent's
suggestions file, and nothing at all when the file is empty or an open issue already
carries this producer's marker. There is no code write, branch, commit or merge here.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import issue_body  # noqa: E402
import proc  # noqa: E402

MARKER_PREFIX = "<!-- fleet-architecture-review:"
DOC = "docs/ARCHITECTURE.md"
MANIFEST = "agents/manifest.json"
TITLE_PREFIX = "ci(architecture): weekly fleet-doc improvement suggestions"


def brief(out: Path, doc: Path = ROOT / DOC, manifest: Path = ROOT / MANIFEST) -> int:
    import json

    profiles = [str(p["name"]) for p in json.loads(manifest.read_text(encoding="utf-8"))["profiles"]]
    parts = [
        "# Fleet architecture brief",
        "",
        "The weekly Hermes leg reads ONLY this brief. It may write ONLY the suggestions file.",
        "It never edits code, a workflow, a SOUL.md or a gate.",
        "",
        "## docs/ARCHITECTURE.md",
        "",
        doc.read_text(encoding="utf-8") if doc.is_file() else "(missing)",
        "",
        "## agents/manifest.json",
        "",
        manifest.read_text(encoding="utf-8") if manifest.is_file() else "(missing)",
        "",
        "## Lane SOUL.md files",
        "",
    ]
    for name in profiles:
        soul = ROOT / "agents" / name / "SOUL.md"
        parts += [f"### {name}", "", soul.read_text(encoding="utf-8") if soul.is_file() else "(no SOUL.md)", ""]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(parts) + "\n", encoding="utf-8")
    print(f"brief={out} profiles={len(profiles)} bytes={out.stat().st_size}")
    return 0


def _gh(gh: str, *args: str, stdin: str = "", token: str = "") -> str:
    env = {**os.environ, "GH_TOKEN": token} if token else None
    return proc.run_checked([gh, *args], env=env, input=stdin).strip()


def _existing_issue(gh: str, repo: str) -> str:
    """Dedupe on this producer's marker, across every open issue, independent of title."""
    listing = _gh(gh, "issue", "list", "--repo", repo, "--state", "open",
                  "--search", "fleet-architecture-review", "--json", "number,body")
    import json

    for issue in json.loads(listing or "[]"):
        if MARKER_PREFIX in str(issue.get("body") or ""):
            return f"https://github.com/{repo}/issues/{issue['number']}"
    return ""


def publish(suggestions: Path, repo: str, stamp: str, dry: bool = False) -> int:
    text = suggestions.read_text(encoding="utf-8").strip() if suggestions.is_file() else ""
    if not text:
        print("action=none reason=no-suggestions")
        return 0
    gh = shutil.which("gh") or "gh"
    token = os.environ.get("GH_TOKEN", "")
    if not dry:
        existing = _existing_issue(gh, repo)
        if existing:
            print(f"action=skip reason=open-issue-exists issue_url={existing}")
            return 0
    marker = f"{MARKER_PREFIX}{stamp} -->"
    short = text.splitlines()[0][:100] if text.splitlines() else "fleet architecture"
    body = issue_body.render(
        marker=marker,
        problem=(
            "The weekly review found gaps between the documented bot fleet and the live lane "
            f"setup: {short}. These are suggestions, not a defect proven by a CI red."
        ),
        why=(
            "A fleet doc that lags the profiles, or lanes whose hand-offs no longer match their "
            "SOUL.md rules, sends contributors and bots to a stale map. The Monday review makes "
            "the drift visible as one reviewable work item."
        ),
        how=[
            "Read `docs/ARCHITECTURE.md`, `agents/manifest.json` and every `agents/<profile>/SOUL.md`.",
            "Propose concrete additions or corrections to the fleet section and the hand-offs.",
            "File ONE issue; this bot writes no code, no workflow and no gate.",
        ],
        benefit="The architecture record is refreshed from the tree weekly, without a model editing source.",
        acceptance=[
            "Every suggestion names the lane or doc line it concerns.",
            "A reviewer can turn each suggestion into a separate implementation issue.",
            "No code, workflow, gate or SOUL.md was edited by this bot.",
            "Only one open issue carries this producer's marker at a time.",
        ],
        technical=[
            f"brief inputs: `{DOC}`, `{MANIFEST}`, `agents/*/SOUL.md` (tree copy only, #928)",
            f"head at review: `{stamp}`; suggestions file: `{suggestions}`",
            "dedupe: an open issue whose body carries `<!-- fleet-architecture-review:` stops filing",
            "the Hermes leg writes ONLY the suggestions file; this step owns the single issue write",
        ],
    )
    if dry:
        sys.stdout.write(body)
        print("action=dry", file=sys.stderr)
        return 0
    url = _gh(gh, "issue", "create", "--repo", repo, "--title", TITLE_PREFIX,
              "--body", body, token=token)
    print(f"action=filed issue_url={url}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("brief")
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--doc", type=Path, default=ROOT / DOC)
    b.add_argument("--manifest", type=Path, default=ROOT / MANIFEST)
    p = sub.add_parser("publish")
    p.add_argument("--suggestions", type=Path, required=True)
    p.add_argument("--repo", required=True)
    p.add_argument("--stamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M"))
    p.add_argument("--dry", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "brief":
        return brief(args.out, args.doc, args.manifest)
    return publish(args.suggestions, args.repo, args.stamp, args.dry)


if __name__ == "__main__":
    sys.exit(main())
