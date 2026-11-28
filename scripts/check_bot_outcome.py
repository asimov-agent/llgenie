#!/usr/bin/env python3
"""Shared backstop for bot outcome steps (issue #3124).

A bot may write a `bot-done … fixed` success marker only when a durable changed
path exists: a moved head, an `agent/issue-<n>-*` branch on origin, or a PR that
names the issue. A vacuous check (an empty PR/issue body, or a triage leg that
never created a session) is never evidence of a change.

This only ADDS a failure mode; it does not weaken any existing gate.

Examples:
  python3 scripts/check_bot_outcome.py verify-changed-path \
      --bot issue-bot --issue 3124 --pre-head OLD --post-head NEW \
      --branch agent/issue-3124-work --head NEW --pr-body-file pr.md
  python3 scripts/check_bot_outcome.py verify-changed-path --no-gh  # env-driven
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable

EXIT_OK = 0
EXIT_NO_CHANGED_PATH = 2

ISSUE_BRANCH = re.compile(r"^agent/issue-(\d+)-[A-Za-z0-9][A-Za-z0-9_.-]*$")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _truthy(value: str | None) -> bool | None:
    if value is None or not value.strip():
        return None
    return value.strip().lower() in {"1", "true", "yes", "y"}


def _read_body(path: str | None) -> str:
    if not path:
        return ""
    p = Path(path)
    if not p.is_file():
        return ""
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _gh(*args: str, repo: str) -> str:
    gh = shutil.which("gh")
    if not gh:
        return ""
    env = dict(os.environ)
    env.setdefault("GH_NO_UPDATE_NOTIFIER", "1")
    try:
        r = subprocess.run(
            [gh, *args, "--repo", repo],
            capture_output=True, text=True, env=env, timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def _live_signals(issue: str, repo: str) -> tuple[list[str], list[str]]:
    """Return (issue branches, PR numbers) from the live API; empty when --no-gh."""
    branches: list[str] = []
    prs: list[str] = []
    if not issue or not issue.isdigit() or not repo:
        return branches, prs
    out = _gh(
        "api", f"repos/{repo}/branches", "--jq", ".[].name", repo=repo
    )
    for line in out.splitlines():
        name = line.strip()
        m = ISSUE_BRANCH.match(name)
        if m and m.group(1) == str(int(issue)):
            branches.append(name)
    out = _gh(
        "pr", "list", "--state", "all", "--limit", "100",
        "--search", f"{issue} in:title,body", "--json", "number",
        "--jq", ".[].number", repo=repo,
    )
    prs = [line.strip() for line in out.splitlines() if line.strip().isdigit()]
    return branches, prs


def verify(args: argparse.Namespace) -> int:
    bot = args.bot or _env("BOT_OUTCOME_BOT", "bot")
    issue = args.issue or _env("BOT_OUTCOME_ISSUE", "")
    pre = args.pre_head or _env("BOT_OUTCOME_PRE_HEAD", "")
    post = args.post_head or _env("BOT_OUTCOME_POST_HEAD", "")
    branch = args.branch or _env("BOT_OUTCOME_BRANCH", "")
    head = args.head or _env("BOT_OUTCOME_HEAD", "")
    pr_body_files = args.pr_body_file or [
        p for p in [_env("BOT_OUTCOME_PR_BODY_FILE")] if p
    ]
    issue_body_files = args.issue_body_file or [
        p for p in [_env("BOT_OUTCOME_ISSUE_BODY_FILE")] if p
    ]
    session = _truthy(args.session_created)
    if session is None:
        session = _truthy(_env("BOT_OUTCOME_SESSION_CREATED"))
    repo = args.repo or _env("BOT_OUTCOME_REPO", "")
    pr = args.pr or _env("BOT_OUTCOME_PR", "")
    changed = _truthy(_env("BOT_OUTCOME_CHANGED"))

    pr_bodies = [_read_body(p) for p in pr_body_files]
    issue_bodies = [_read_body(p) for p in issue_body_files]

    vacuous: list[str] = []
    if session is False:
        vacuous.append("no session was created (triage leg with no outcome)")
    for p, body in zip(pr_body_files, pr_bodies):
        if not body.strip():
            vacuous.append(f"empty PR body: {p}")
    for p, body in zip(issue_body_files, issue_bodies):
        if not body.strip():
            vacuous.append(f"empty issue body: {p}")

    live_branches: list[str] = []
    live_prs: list[str] = []
    if not args.no_gh:
        live_branches, live_prs = _live_signals(issue, repo)

    head_moved = bool(pre and post and pre != post) or changed is True
    branch_exists = False
    if branch:
        m = ISSUE_BRANCH.match(branch)
        if m and issue.isdigit() and m.group(1) == str(int(issue)):
            branch_exists = True
    branch_exists = branch_exists or bool(live_branches)
    pr_exists = bool(pr) or bool(live_prs) or any(b.strip() for b in pr_bodies)
    signals = {
        "head_moved": head_moved,
        "issue_branch_on_origin": branch_exists,
        "pr_names_issue": pr_exists,
    }
    durable = any(signals.values()) and not vacuous

    result = {
        "bot": bot,
        "issue": issue,
        "pre_head": pre,
        "post_head": post,
        "branch": branch,
        "head": head,
        "pr": pr,
        "changed": changed,
        "vacuous": vacuous,
        "signals": signals,
        "durable_changed_path": durable,
    }
    if args.json:
        print(json.dumps(result, sort_keys=True))
    if durable:
        print(
            f"[check-bot-outcome] OK — {bot} has a durable changed path for "
            f"#{issue or '?'} ("
            + ", ".join(k for k, v in signals.items() if v)
            + "); a success marker may be written."
        )
        return EXIT_OK
    reasons: list[str] = []
    if vacuous:
        reasons.append("vacuous check: " + "; ".join(vacuous))
    if not any(signals.values()):
        reasons.append(
            "post-head equals pre-head, no agent/issue-<n>-* branch on origin, "
            "and no PR names the issue"
        )
    print(
        "[check-bot-outcome] NO CHANGED PATH — "
        + "; ".join(reasons)
        + f". {bot} must end non-success and write NO `bot-done … fixed` marker.",
        file=sys.stderr,
    )
    return EXIT_NO_CHANGED_PATH


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verify-changed-path")
    v.add_argument("--bot", help="bot name (default: BOT_OUTCOME_BOT)")
    v.add_argument("--issue", help="issue/PR id (default: BOT_OUTCOME_ISSUE)")
    v.add_argument("--pre-head", help="head before the bot leg")
    v.add_argument("--post-head", help="head after the bot leg")
    v.add_argument("--branch", help="pushed agent/issue-<n>-* branch")
    v.add_argument("--head", help="current head of that branch")
    v.add_argument("--pr", help="PR number that names the issue")
    v.add_argument("--pr-body-file", action="append", default=[])
    v.add_argument("--issue-body-file", action="append", default=[])
    v.add_argument("--session-created", choices=["true", "false"])
    v.add_argument("--repo", help="owner/repo for live gh queries")
    v.add_argument("--no-gh", action="store_true", help="disable live queries")
    v.add_argument("--json", action="store_true")
    v.set_defaults(func=verify)
    return p


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
