#!/usr/bin/env python3
"""CI entrypoint: rebase open engine-bump PRs onto the latest upstream main.

Issue #208: the engine-bump workflow (`.github/workflows/engine-bump.yml`)
opens a `chore/engine-bump-<id>` PR per changed engine, but nothing kept those
PRs current with `main` except the watch-loop dispatcher's host crontab. This
script is the PURE CI path: it lists the open `chore/engine-bump-*` PRs on
`asimov-agent/llgenie` via the GitHub API and, for each one that is behind
`main`, calls the SAME shared sync logic the dispatcher uses
(`scripts/engine_bump_sync.py`) to forward-merge the latest `main` into the
branch and force-with-lease-push it back.

Run by `.github/workflows/engine-bump-rebase.yml` (daily cron) with the owner
PAT (`secrets.BUMP_TOKEN`). `--dry` prints what it would do without pushing.

Usage:
    python3 scripts/engine_bump_rebase.py [--dry] [--repo <path>]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request

# `python3 scripts/engine_bump_rebase.py` puts scripts/ on sys.path, so the
# package import below is missing unless the repo root is added first.
# Run 38318141627 died here with ModuleNotFoundError.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scripts.engine_bump_sync import (
    UPSTREAM_SLUG,
    is_engine_bump_pr,
    sync_pr_with_main,
)

API = f"https://api.github.com/repos/{UPSTREAM_SLUG}"


def load_token() -> str:
    for var in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(var):
            return os.environ[var]
    raise SystemExit("[engine-bump-rebase] no GITHUB_TOKEN/GH_TOKEN found")


TOK = load_token()
HEADER = {"Authorization": f"Bearer {TOK}", "Accept": "application/vnd.github+json"}


def api(path: str) -> list | None:
    req = urllib.request.Request(API + path, headers=HEADER)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None
    except Exception:
        return None  # fail closed: any API problem -> don't act


def open_engine_bump_prs() -> list:
    """The open PRs whose head ref is a `chore/engine-bump-*` branch."""
    prs = api("/pulls?state=open&per_page=100")
    if not isinstance(prs, list):
        return []
    return [pr for pr in prs if isinstance(pr, dict) and is_engine_bump_pr(pr)]


def pr_is_behind(pr) -> bool:
    """True if the PR head is BEHIND main / unverifiable (never merge those)."""
    cmp = api(f"/compare/{pr['base']['sha']}...{pr['head']['sha']}")
    if not isinstance(cmp, dict):
        return True
    return cmp.get("status") not in ("identical", "ahead")


def run_git(repo: str, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)


def log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry", action="store_true", help="print what would be done, push nothing")
    ap.add_argument("--repo", default=os.getcwd(), help="the llgenie checkout (default: cwd)")
    args = ap.parse_args()

    prs = open_engine_bump_prs()
    if not prs:
        log("[engine-bump-rebase] no open engine-bump PRs")
        return 0

    rebased = 0
    for pr in prs:
        n = pr["number"]
        ref = pr["head"]["ref"]
        if not pr_is_behind(pr):
            log(f"  PR#{n} ({ref}): not behind main — skip")
            continue
        log(f"  PR#{n} ({ref}): behind main — rebasing onto the upstream main")
        if args.dry:
            log(f"    [dry] would forward-merge the upstream main into {ref} and push")
            continue
        if sync_pr_with_main(pr, args.repo, lambda *a: run_git(args.repo, *a), log):
            rebased += 1
            log(f"  PR#{n} ({ref}): rebased; CI will re-run")
        else:
            log(f"  PR#{n} ({ref}): rebase failed (conflict or push error) — left for a human")
    log(f"[engine-bump-rebase] done: {rebased} rebased, {len(prs)} open engine-bump PRs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
