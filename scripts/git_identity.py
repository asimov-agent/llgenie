#!/usr/bin/env python3
"""ONE source for the git identity every leg of this repository commits as (issue #840).

`scripts/check_pr_authors.py::ALLOWED` is the POLICY — the two identities a PR's commits may carry,
and no others:

    Andy Holst <andy.holst@protonmail.com>
    Asimov Agent <support@docondee.com>

This module answers a different question: WHICH of the two the automation commits as, and it answers
it from ONE place. Before this file the same pair was typed as a literal into nine producers in three
spellings — `git config user.name …`, `git -c user.name=…`, `GIT_AUTHOR_NAME: …` — so a new leg, or
an edit to one of them, was one typo away from `Asimov Agent <agent@asimov.invalid>`, which keeps a
correct-LOOKING name and changes only the domain. That is the mechanism behind every violation in
issue #840: a human reading `git log --format='%an'` cannot see it, `check_pr_authors` can, and
`check_pr_authors` only runs at the END of `linux / unit`, 30+ minutes in.

The identity is the BOT HALF of the allowlist, derived from `ALLOWED` — never restated:

    identity() -> ("Asimov Agent", "support@docondee.com")

`apply()` writes it into the repository's own git config, so a leg that sources it commits as an
allowed identity even when the host's `~/.gitconfig` says something else. `check()` is the other
half: it reads the identity git would ACTUALLY use for the next commit — `GIT_AUTHOR_*` first (git's
own precedence), then `git config --show-origin`, which names the FILE that set it — and fails,
naming the identity, its source and the allowlist, when that pair is not one of the two. It runs as
the `guard` job's first step, so a wrong author is reported in seconds instead of at the end of the
longest job on the board.

A `-c user.email=…` flag still beats a correct config by design (git's documented precedence), which
is why `check()` is not the only guard: the commit scan in `check_pr_authors` reads the PRODUCED
authors, and the same scan now runs in `guard` too.

`line()` is what a PR body reports, so a reviewer sees the author up front:

    Author: Asimov Agent <support@docondee.com>

Commands:
    git_identity.py check     exit non-zero when the identity this repo will commit as is not allowed
    git_identity.py apply     write the allowlisted identity into the repo's git config
    git_identity.py line      print `Author: <name> <email>` for a PR body
    git_identity.py report    print the identity, where it came from, and the allowlist

Usage:
    python3 scripts/git_identity.py check
    python3 scripts/git_identity.py check --cwd <repo>
    python3 scripts/git_identity.py apply
    python3 scripts/git_identity.py line
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
try:  # imported as a module (`scripts.git_identity`), which is how the tests read it
    from scripts.check_pr_authors import ALLOWED
except ModuleNotFoundError:  # run as a script: `scripts/` is sys.path[0]
    from check_pr_authors import ALLOWED

#: The half of the allowlist the automation commits as. The NAME is the allowlist key, so the email is
#: read from `ALLOWED` and can never drift from the policy it is checked against.
BOT_NAME = "Asimov Agent"
#: `git var GIT_AUTHOR_IDENT` prints `<name> <<email>> <timestamp> <tz>`.
IDENT = re.compile(r"^(?P<name>.*?) <(?P<email>[^>]*)>")


def identity() -> tuple[str, str]:
    """The `(name, email)` every leg commits as — the bot half of `ALLOWED`, and nothing else."""
    return BOT_NAME, ALLOWED[BOT_NAME]


def allowed_note() -> str:
    """One sentence naming the allowlist, for a finding's evidence."""
    return ("A PR's commits may be authored by "
            + " or ".join(f"{n} <{e}>" for n, e in ALLOWED.items()) + " and by no one else")


def _git(args: list[str], cwd: Path) -> tuple[int, str]:
    """Run git and return `(returncode, stdout)`. A failure is a return code, never an exception: a
    repository with no identity at all must produce a FINDING, not a traceback."""
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    return proc.returncode, proc.stdout.strip()


def _config(cwd: Path, key: str) -> tuple[str, str]:
    """`(value, origin)` for one git config key — the origin is the file that set it (`file:/…`)."""
    rc, out = _git(["config", "--show-origin", "--get", key], cwd)
    if rc != 0 or not out:
        return "", ""
    origin, _, value = out.partition("\t")
    return value.strip(), origin.strip()


def _ident(cwd: Path) -> tuple[str, str]:
    """The identity git itself resolves, used only when neither env nor config states one."""
    rc, out = _git(["var", "GIT_AUTHOR_IDENT"], cwd)
    if rc != 0:
        return "", ""
    m = IDENT.match(out)
    return (m.group("name").strip(), m.group("email").strip()) if m else ("", "")


def resolve(cwd: Path = REPO_ROOT) -> dict:
    """The identity the next commit in `cwd` would carry, and where EACH half came from.

    Git's own precedence is honoured: `GIT_AUTHOR_NAME` / `GIT_AUTHOR_EMAIL` (then `EMAIL`) beat the
    config, and the config is read with `--show-origin` so a finding can name the FILE. The source is
    the part a reader needs: "it is wrong" is useless without "it came from `~/.gitconfig`".
    """
    env_name = os.environ.get("GIT_AUTHOR_NAME", "").strip()
    env_email = os.environ.get("GIT_AUTHOR_EMAIL", "").strip() or os.environ.get("EMAIL", "").strip()
    cfg_name, cfg_name_origin = _config(cwd, "user.name")
    cfg_email, cfg_email_origin = _config(cwd, "user.email")
    fallback_name, fallback_email = _ident(cwd)
    if env_name:
        name, name_source = env_name, "GIT_AUTHOR_NAME"
    elif cfg_name:
        name, name_source = cfg_name, cfg_name_origin or "git config user.name"
    else:
        name, name_source = fallback_name, "git's default (no user.name set)"
    if env_email:
        source = "GIT_AUTHOR_EMAIL" if os.environ.get("GIT_AUTHOR_EMAIL") else "EMAIL"
        email, email_source = env_email, source
    elif cfg_email:
        email, email_source = cfg_email, cfg_email_origin or "git config user.email"
    else:
        email, email_source = fallback_email, "git's default (no user.email set)"
    return {"name": name, "email": email, "name_source": name_source, "email_source": email_source}


def check(cwd: Path = REPO_ROOT) -> list[dict]:
    """Findings when the identity git would commit as is not one of the two allowed pairs."""
    got = resolve(cwd)
    if ALLOWED.get(got["name"]) == got["email"]:
        return []
    name, email = identity()
    return [{
        "key": "identity/ambient",
        "title": "ci: the identity this repository would commit as is outside the allowlist",
        "evidence": (
            f"A commit in `{cwd}` would be authored `{got['name']} <{got['email']}>` "
            f"(name from {got['name_source']}, email from {got['email_source']}), which is outside the "
            f"allowlist. {allowed_note()} (issue #345). Source the ONE identity instead of inheriting "
            f"whatever the host gives: `make git-identity-apply` writes `{name} <{email}>` into this "
            f"repository's git config, and `make check-git-identity` proves it afterwards. A "
            f"`git -c user.name=… -c user.email=…` flag overrides the config by design, so drop it and "
            f"let the seam decide (issue #840)."
        ),
        "where": str(cwd),
    }]


def apply(cwd: Path = REPO_ROOT) -> None:
    """Write the allowlisted identity into the repository's OWN git config (never the global one)."""
    name, email = identity()
    for key, value in (("user.name", name), ("user.email", email)):
        proc = subprocess.run(["git", "config", key, value], cwd=str(cwd),
                              capture_output=True, text=True)
        if proc.returncode != 0:
            raise SystemExit(f"[git-identity] `git config {key}` failed in {cwd}: "
                             f"{proc.stderr.strip()}")


def pr_author_line() -> str:
    """The line a bot's PR body carries, so a reviewer sees the author without `gh api`."""
    name, email = identity()
    return f"Author: {name} <{email}>"


def report(cwd: Path = REPO_ROOT) -> str:
    got = resolve(cwd)
    verdict = "OK" if check(cwd) == [] else "FAIL"
    lines = [
        f"[git-identity] {verdict}  {got['name']} <{got['email']}>",
        f"[git-identity]   name  source: {got['name_source']}",
        f"[git-identity]   email source: {got['email_source']}",
        f"[git-identity] allowed: {', '.join(f'{n} <{e}>' for n, e in ALLOWED.items())}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="git_identity.py")
    p.add_argument("cmd", choices=("check", "apply", "line", "report"))
    p.add_argument("--cwd", default=str(REPO_ROOT), help="the repository to read/apply in")
    args = p.parse_args(argv)
    cwd = Path(args.cwd)
    if args.cmd == "line":
        print(pr_author_line())
        return 0
    if args.cmd == "apply":
        apply(cwd)
        name, email = identity()
        print(f"[git-identity] set {cwd} to {name} <{email}>")
        return 0
    if args.cmd == "report":
        print(report(cwd))
        return 0
    items = check(cwd)
    if not items:
        name, email = identity()
        got = resolve(cwd)
        print(f"[git-identity] OK — {cwd} commits as {got['name']} <{got['email']}> "
              f"(the allowlisted {name} <{email}>)")
        return 0
    print(f"[git-identity] {len(items)} violation(s)")
    for it in items:
        print(f"  {it['title']}")
        print(f"    {it['evidence']}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
