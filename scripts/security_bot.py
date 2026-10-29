#!/usr/bin/env python3
"""The security remediation bot: one `auto-fixable` issue -> one green PR (issue #717, parent #713).

The repository already has bot legs of a fixed shape (a Hermes skill under `.hermes/skills/<name>/`,
an inline prompt that is a pointer, and a deterministic script that does every GitHub write). This
is the deterministic half: it selects ONE issue that `make security-issues` filed (#716), parses the
advisory's `current -> fixed` pin out of the issue body, applies it to the one file that owns the
pin, and opens a focused PR that closes the issue.

**Green or nothing.** Before a branch is pushed the fast gates must pass
(`make lint check-wiring check-docs check-security-scan`). If they do not, the bot deletes the
branch, comments the real output on the issue, and opens NO PR — a red PR is worse than no PR, and
AGENTS.md forbids opening one it cannot make green. It never merges, never pushes to `main`, never
force-pushes.

It refuses, loudly, on a finding it cannot place:

* a **container** finding (an apk/base advisory): there is no per-package pin to move, so the fix is
  a base-image or scanner bump — a human decision, and the bot comments instead of guessing;
* a package that is not pinned anywhere it can see (no `.in` line, no `==` pin in a requirements file).

Commands (driven by make, never by hand):

    select          print the issue this run would take (oldest `auto-fixable`)   make security-bot-pick
    plan            print the edit it would make for that issue                    make security-bot DRY=1
    apply           make the edit, then push + open the PR                         make security-bot
    check           the bot's label/parse contract still matches the issuer        make check-security-bot
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import git_identity  # noqa: E402  the ONE source of the commit identity (issue #840)
import security_issues as si  # noqa: E402

SELECT_LABELS = ("security", "vulnerability", "auto-fixable")
#: The tie between this bot and the issuer (#716): the marker it files with is what the bot parses.
PIN_LINE = re.compile(r"^\s*(?P<pkg>[A-Za-z0-9_.-]+)\s*(?P<sep>==|=|>=|<=|~=|!=)\s*(?P<ver>[^\s#;]+)",
                      re.M)
#: Files that own a Python pin. Compiled `requirements.txt` files are NOT here: they are generated.
PIN_SOURCES = ("tools/requirements.in", "tools/requirements-dev.in")
CURRENT_FIXED = re.compile(r"\*\*Current → fixed:\*\*\s*`([^`]*)`\s*→\s*`([^`]*)`")
PACKAGE = re.compile(r"\*\*Affected package:\*\*\s*`([^`]+)`")
GATES = ("lint", "check-wiring", "check-docs", "check-security-scan")


@dataclass
class Target:
    """One issue's remediation, as the bot understands it."""

    number: int
    package: str
    current: str
    fixed: str
    component: str
    marker: str
    advisory: str = ""


def _gh(args: list[str], repo: str) -> subprocess.CompletedProcess:
    cmd = ["gh", *args, "--repo", repo]
    print(f"[security-bot] $ {' '.join(cmd)}")
    return subprocess.run(cmd, capture_output=True, text=True)


def select(repo: str) -> dict | None:
    """The ONE issue this run takes: oldest open issue carrying every select label."""
    res = _gh(["issue", "list", "--state", "open", "--limit", "100", "--json",
               "number,title,body,labels,createdAt"], repo)
    if res.returncode != 0:
        raise SystemExit(f"[security-bot] cannot list issues: {res.stderr.strip()}")
    wanted = set(SELECT_LABELS)
    candidates = [issue for issue in json.loads(res.stdout or "[]")
                  if wanted <= {l["name"] for l in issue.get("labels") or []}]
    if not candidates:
        return None
    return sorted(candidates, key=lambda i: (i.get("createdAt") or "", i["number"]))[0]


def parse(issue: dict) -> Target:
    """Read the advisory's package and `current -> fixed` out of the body the issuer wrote."""
    body = issue.get("body") or ""
    package = PACKAGE.search(body)
    versions = CURRENT_FIXED.search(body)
    if not package or not versions:
        raise SystemExit(f"[security-bot] #{issue['number']}: the body carries no package/version "
                         "line — refusing to guess (the issue format is #716's contract)")
    marker = si.MARKER_RE.search(body)
    return Target(
        number=int(issue["number"]), package=package.group(1).strip(),
        current=versions.group(1).strip(), fixed=versions.group(2).strip(),
        component="container" if "component:container" in body else "python",
        marker=marker.group(0) if marker else "",
        advisory=marker.group(2) if marker else "advisory",
    )


def apply_plan(target: Target, root: Path = REPO) -> tuple[Path, str, str] | None:
    """The (file, before, after) edit for a Python pin, or None when no line owns it."""
    if target.component == "container":
        return None
    fixed = re.split(r"[,\s]+", target.fixed)[0]  # "1.1, 1.2" -> the first fixed version
    for rel in PIN_SOURCES:
        path = root / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        m = re.search(rf"^{re.escape(target.package)}==(\S+)\s*$", text, re.M)
        if not m:
            continue
        before = m.group(0)
        after = f"{target.package}=={fixed}"
        return path, before, after
    return None


def write_plan(target: Target, plan: tuple[Path, str, str] | None, root: Path = REPO) -> None:
    """Print the plan a reviewer reads (`DRY=1`) or that `apply` then performs."""
    if plan is None:
        print(f"[security-bot] #{target.number}: no editable pin for `{target.package}` "
              f"({target.component}). Refusing: a container finding is a base-image/scanner bump, "
              "not a line the bot may edit.")
        return
    path, before, after = plan
    print(f"[security-bot] #{target.number}: {path.relative_to(root)}")
    print(f"  - {before}")
    print(f"  + {after}")


def _run_make(target: str, root: Path = REPO) -> subprocess.CompletedProcess:
    print(f"[security-bot] $ make {target}")
    return subprocess.run(["make", *target.split()], cwd=root, capture_output=True, text=True)


def gates(root: Path = REPO) -> tuple[bool, str]:
    """The fast gates that must be green BEFORE a branch is pushed."""
    output = []
    for name in GATES:
        res = _run_make(name, root)
        output.append(f"$ make {name} -> exit {res.returncode}\n{res.stdout[-2000:]}{res.stderr[-2000:]}")
        if res.returncode != 0:
            return False, "\n".join(output)
    return True, "\n".join(output)


def pr_body(target: Target, path: Path, before: str, after: str, root: Path = REPO) -> str:
    return "\n".join([
        # The author a reviewer sees, before the diff (issue #840).
        git_identity.pr_author_line(),
        "",
        f"Issue: #{target.number} — `{target.package}` is pinned at `{before.split('==')[-1]}`, and "
        f"the scanner reports `{target.current}` → `{target.fixed}`.",
        "",
        f"Fix: `{path.relative_to(root)}` moves `{before}` to `{after}`. The compiled "
        "`requirements*.txt` is regenerated by `make generate-requirements`; it is not hand-edited.",
        "",
        f"Benefit: the advisory is closed by the smallest possible change, and the scan that filed "
        f"#{target.number} is what re-verifies it on the next run.",
        "",
        "Technical:",
        f"- `{path.relative_to(root)}` — one pin.",
        f"- Fast gates run before the push: {', '.join('make ' + g for g in GATES)}.",
        f"- The change is one commit on `{branch_name(target)}`.",
        "",
        f"closes #{target.number}",
    ])


def branch_name(target: Target) -> str:
    """`fix/security-<advisory>-<package>` — one branch per advisory, readable in `git branch`."""
    advisory = re.sub(r"[^A-Za-z0-9]+", "-", target.advisory or "advisory").strip("-").lower()
    return f"fix/security-{advisory}-{target.package}".lower()[:60]


def comment(repo: str, number: int, text: str) -> None:
    _gh(["issue", "comment", str(number), "--body", text], repo)


def apply(repo: str, root: Path = REPO, dry: bool = False, run_url: str = "") -> int:
    issue = select(repo)
    if issue is None:
        print("[security-bot] no open issue carries security+vulnerability+auto-fixable — nothing to do")
        return 0
    target = parse(issue)
    plan = apply_plan(target, root)
    write_plan(target, plan, root)
    if dry:
        print("[security-bot] DRY: nothing written, nothing pushed, no PR")
        return 0
    if plan is None:
        # A finding the bot cannot place is a human decision; say so on the issue, open no PR.
        comment(repo, target.number,
                "The security bot cannot apply this automatically: "
                f"`{target.package}` has no per-package pin to move (`{target.component}`). "
                "This needs a base-image or scanner bump, which is a reviewed change.")
        return 0
    path, before, after = plan
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace(before, after, 1), encoding="utf-8")
    ok, output = gates(root)
    if not ok:
        # Green or nothing: revert, say why, open no PR.
        path.write_text(text, encoding="utf-8")
        comment(repo, target.number,
                f"The security bot did **not** open a PR: the fast gates are not green after the "
                f"change, so the branch was dropped.\n\n```\n{output[-4000:]}\n```")
        print("[security-bot] gates red after the edit — reverted, no PR")
        return 1
    branch = branch_name(target)
    # The identity comes from the ONE seam that sets it (`scripts/git_identity.py`, issue #840): a
    # command-line identity override beats every config layer by design, which is how a
    # correct-looking name once reached a head with the wrong domain.
    git_identity.apply(root)
    steps = [
        ["git", "checkout", "-b", branch],
        ["git", "add", str(path)],
        ["git", "commit",
         "-m", f"fix(security): bump {target.package} for {target.advisory}",
         "-m", f"Issue: #{target.number} — `{target.package}` is pinned below the advisory's fixed "
               f"version.\n\nFix: move the pin `{before}` -> `{after}` in "
               f"`{path.relative_to(root)}`.\n\nBenefit: the advisory `{target.advisory}` is closed by "
               f"the smallest possible change.\n\nTechnical: one pin, fast gates run before the push, "
               f"the PR closes #{target.number}."],
        ["git", "push", "-u", "origin", branch],
    ]
    for step in steps:
        res = subprocess.run(step, cwd=root, capture_output=True, text=True)
        if res.returncode != 0:
            raise SystemExit(f"[security-bot] `{' '.join(step)}` failed: {res.stderr.strip()}")
    body_file = root / ".git" / "security-bot-pr-body.md"
    body_file.write_text(pr_body(target, path, before, after, root) + "\n", encoding="utf-8")
    res = _gh(["pr", "create", "--head", branch, "--title",
               f"fix(security): bump {target.package} for {target.advisory}",
               "--body-file", str(body_file)], repo)
    if res.returncode != 0:
        raise SystemExit(f"[security-bot] pr create failed: {res.stderr.strip()}")
    print(f"[security-bot] opened {res.stdout.strip()}")
    return 0


def check(root: Path = REPO) -> int:
    """The bot's contract with the issuer (#716): labels, body fields, and no hand-editable compile."""
    problems: list[str] = []
    for label in SELECT_LABELS:
        if label not in si.LABELS:
            problems.append(f"the bot selects `{label}` but security_issues.LABELS does not define it")
    for rel in PIN_SOURCES:
        if not (root / rel).is_file():
            problems.append(f"{rel} is missing: the bot has no source of truth to edit")
    for rel in PIN_SOURCES:
        if rel.endswith(".txt"):
            problems.append(f"{rel}: compiled files must never be a bot edit target")
    if "container" not in " ".join(PIN_SOURCES):
        pass  # container findings are refused by design (see apply_plan)
    if problems:
        print(f"[security-bot] {len(problems)} problem(s):")
        for item in problems:
            print(f"  - {item}")
        return 1
    print(f"[security-bot] OK: selects {', '.join(SELECT_LABELS)}; pins from "
          f"{', '.join(PIN_SOURCES)}; container findings are refused, not guessed")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=("select", "plan", "apply", "check"))
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    ap.add_argument("--root", default=str(REPO))
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args(argv)
    root = Path(args.root)
    if args.command == "check":
        return check(root)
    if not args.repo:
        raise SystemExit("[security-bot] set --repo (or $GITHUB_REPOSITORY)")
    if args.command == "select":
        issue = select(args.repo)
        print(json.dumps(issue or {}, indent=2)[:2000])
        return 0
    return apply(args.repo, root, dry=args.dry or args.command == "plan")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
