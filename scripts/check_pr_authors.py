#!/usr/bin/env python3
"""A PR's commits are authored by Andy Holst or Asimov Agent — and by no one else (issue #345).

A commit's author is the attribution a reader trusts: `git log`, `git blame` and `git bisect` all
answer "who wrote this line" from it. In this repository the same two identities appear under several
different names, and one of them is what the CURRENT git config authors as, so "who wrote this" is
already ambiguous on `main`:

    git log --all --format='%an <%ae>' | sort | uniq -c | sort -rn
        182 Asimov Agent <support@docondee.com>
        108 Andy Holst <andy.holst@protonmail.com>
         51 Andy <andy.holst@protonmail.com>
         50 Mr. Asimov <support@docondee.com>
         46 andyholst <andy.holst@protonmail.com>
         37 github-actions[bot] <andy.holst@protonmail.com>
         11 asimov-agent <asimov-agent@users.noreply.github.com>
          7 Hermes Agent <agent@asimov.local>
          2 asimov-agent <asimov@users.noreply.github.com>
          2 andyholst <andyholst@users.noreply.github.com>
          1 llama-ai-agent <agent@llama-ai>

Only two identities may author a PR's commits:

    Andy Holst <andy.holst@protonmail.com>
    Asimov Agent <support@docondee.com>

Every other author is a violation — `Andy`, `andyholst`, `Mr. Asimov`, `github-actions[bot]`,
`llgenie fix-bot`, `Hermes Agent`, `asimov-agent`, `llama-ai-agent`. The name must match exactly AND
the email must be the one that belongs to that name, so a commit authored `Andy Holst <someone@else>`
is as much a violation as one authored `Andy`.

The scan is bounded to the commits a PR ADDS (`git rev-list --no-merges <base>..<head>`):

* a merge commit's author is the merge machinery, not the PR's author, so merges are skipped;
* a commit already reachable from the base branch is someone else's landed work, not this PR's.

This is why the merge commit GitHub writes on `main` (authored `GitHub <noreply@github.com>`) is out of
scope by construction, and why this gate can never fail on history it did not create.

It also checks the `Co-authored-by:` trailers in a commit's message: a commit authored by an allowed
identity that carries a co-author outside the allowlist is the same violation, one level down — the
co-author's name is attribution too, and it is what GitHub links a contribution to.

The static half runs in `ci-unit`: `AGENTS.md` MUST state the rule (so deleting it is a red gate, not a
silent edit) and the repository's own producers MUST commit as an allowed identity. Every workflow that
authors a PR commit is read — `.github/workflows/*.yml`, the `Makefile` and `scripts/**` — and a
producer that sets a name/email outside the allowlist is a violation. That is what keeps the guard
green on the automation's own PRs instead of red on the first bump PR after it lands.

Commands:
    check_pr_authors.py check     exit non-zero on any violation, and list them
    check_pr_authors.py report    print every commit in the range with its verdict

Usage:
    python3 scripts/check_pr_authors.py check
    python3 scripts/check_pr_authors.py check --base origin/main --head HEAD
    python3 scripts/check_pr_authors.py report --base <sha> --head <sha>
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ".github/workflows"
SCRIPTS = "scripts"
AGENTS = "AGENTS.md"
MAKEFILE = "Makefile"
#: The identities a PR's commits may be authored by. Name -> the ONE email that name must carry.
#: The name matches exactly: `Andy`, `andyholst` and `Mr. Asimov` are the same people but NOT the
#: allowed spelling, because the spelling is what a reader of `git log` sees.
ALLOWED: dict[str, str] = {
    "Andy Holst": "andy.holst@protonmail.com",
    "Asimov Agent": "support@docondee.com",
}
#: The AGENTS.md section the rule must keep. Deleting it is a violation, not an edit.
AGENTS_MANDATE = "## A PR's commits are authored by Andy Holst or Asimov Agent — no one else"
#: A `Co-authored-by:` trailer, as git writes it. The name is everything before the `<`.
COAUTHOR = re.compile(r"^[ \t]*co-authored-by:[ \t]*(?P<name>[^<]+?)[ \t]*<(?P<email>[^>]*)>",
                      re.IGNORECASE | re.MULTILINE)
#: The value of an assignment. A quoted value is tried FIRST, so `"llgenie fix-bot"` reads whole
#: rather than as the single token `llgenie` — a name with a space is the whole point of the check.
_VALUE = r"""(?P<value>"[^"]*"|'[^']*'|\$\{[^}]*\}|\$\{\{[^}]*\}\}|\$\([^)]*\)|[^"'\s\\]+)"""
#: A git identity assigned in a producer: `git config user.name "x"`, `user.name="x"`.
SET_NAME = re.compile(
    r"""(?:\bgit\s+(?:-c\s+)?config\s+user\.name|(?<![\w-])user\.name\s*=)\s*""" + _VALUE,
)
SET_EMAIL = re.compile(
    r"""(?:\bgit\s+(?:-c\s+)?config\s+user\.email|(?<![\w-])user\.email\s*=)\s*""" + _VALUE,
)
#: A `GIT_AUTHOR_NAME: <value>` / `GIT_COMMITTER_EMAIL=<value>` assignment — YAML `env:` or shell. The
#: value runs to the end of the line (a `#` comment is not part of it), so an UNQUOTED
#: `GIT_AUTHOR_NAME: Asimov Agent` reads whole instead of as the bare token `Asimov` — YAML does not
#: need quotes for a space, and reading only `Asimov` would flag an ALLOWED identity as a violation.
ENV_NAME = re.compile(
    r"""GIT_(?:AUTHOR|COMMITTER)_NAME\s*[:=][ \t]*(?P<value>[^\n#]*?)[ \t]*(?:#.*)?$""", re.M)
ENV_EMAIL = re.compile(
    r"""GIT_(?:AUTHOR|COMMITTER)_EMAIL\s*[:=][ \t]*(?P<value>[^\n#]*?)[ \t]*(?:#.*)?$""", re.M)
#: A git identity set in one `git -c user.name=... -c user.email=... commit` invocation.
INLINE_NAME = re.compile(r"""user\.name\s*=\s*""" + _VALUE)
INLINE_EMAIL = re.compile(r"""user\.email\s*=\s*""" + _VALUE)
#: A value a producer resolves at run time (`$(gh api user --jq .login)`, `${{ github.actor }}`) cannot
#: be read from the file at all, so it is reported in `report` and NOT counted as a violation. Every
#: producer in THIS repository pins a literal allowed identity, so this is the allowance for a future
#: one that genuinely cannot — and the commit scan is what ultimately governs the PR either way.
RUNTIME = ("$(", "${", "${{")


def _run(args: list[str], cwd: Path) -> str:
    """Run git and return its stdout. A failure is raised, never swallowed."""
    proc = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()}")
    return proc.stdout


def commits_in_range(base: str, head: str, cwd: Path = REPO_ROOT) -> list[dict]:
    """Every NON-MERGE commit the PR adds: sha, author name, author email, full message.

    The range is `<base>..<head>` — the commits reachable from `head` and not from `base`. A merge
    commit is skipped: its author is the merge machinery, not the PR's author.
    """
    fmt = "%H%x1f%an%x1f%ae%x1f%B%x1e"
    out = _run(["git", "rev-list", "--no-merges", f"--format={fmt}", f"{base}..{head}"], cwd)
    commits: list[dict] = []
    for record in out.split("\x1e"):
        record = record.strip("\n")
        if not record:
            continue
        # `git rev-list --format` prints "commit <sha>\n" before each record.
        record = re.sub(r"^commit [0-9a-f]{40}\n", "", record, count=1)
        parts = record.split("\x1f", 3)
        if len(parts) != 4:
            continue
        sha, name, email, message = parts
        commits.append({"sha": sha.strip(), "name": name.strip(), "email": email.strip(),
                        "message": message.rstrip("\n")})
    return commits


def _identity_finding(where: str, sha: str, name: str, email: str) -> dict | None:
    """The violation an author identity is, or None when it is exactly an allowed pair."""
    allowed_email = ALLOWED.get(name)
    if allowed_email is not None and allowed_email == email:
        return None
    expected = " or ".join(f"{n} <{e}>" for n, e in ALLOWED.items())
    return {
        "key": f"author/{where}:{sha[:12]}",
        "title": f"ci: {where} carries a commit authored outside the allowlist",
        "evidence": (
            f"`{where}` commit `{sha[:12]}` is authored `{name} <{email}>`, which is outside the "
            f"allowlist. A PR's commits may be authored by {expected} and by no one else "
            f"(issue #345). Set the identity on the branch and re-author: "
            f"`git config user.name \"Andy Holst\"` / "
            f"`git config user.email andy.holst@protonmail.com`, then "
            f"`git rebase --reset-author` (or `git commit --amend --reset-author`) and "
            f"`git push --force-with-lease` on your own PR branch."
        ),
        "where": where,
    }


def check_commits(commits: list[dict], where: str = "pull request") -> list[dict]:
    """Every commit's author AND every `Co-authored-by:` trailer is an allowed identity."""
    out: list[dict] = []
    for c in commits:
        finding = _identity_finding(where, c["sha"], c["name"], c["email"])
        if finding:
            out.append(finding)
        for m in COAUTHOR.finditer(c["message"]):
            name, email = m.group("name").strip(), m.group("email").strip()
            finding = _identity_finding(where, c["sha"], name, email)
            if finding:
                finding["key"] = f"co-author/{where}:{c['sha'][:12]}:{name}"
                finding["title"] = (
                    f"ci: {where} carries a commit co-authored outside the allowlist"
                )
                finding["evidence"] = (
                    f"`{where}` commit `{c['sha'][:12]}` carries `Co-authored-by: {name} <{email}>`. "
                    f"A PR's commits may be authored by "
                    f"{' or '.join(f'{n} <{e}>' for n, e in ALLOWED.items())} and by no one else "
                    f"(issue #345); a co-author's name is attribution too. Drop the trailer or make "
                    f"the co-author one of the two allowed identities."
                )
                out.append(finding)
    return out


#: This guard's own source. It is NOT a producer: it names identities as DATA — in the docstring, in
#: the regexes and in the evidence text a finding carries — and never assigns one to a commit.
#: `_identity_finding` builds `git config user.name "Andy Holst"` as the REMEDIATION it prints, and
#: `_producer_values` documents `user.name "x"` as the shape it matches. Scanning this file reports
#: those words as violations, which drowns a real one in noise (measured: 12 of the 21 findings on
#: this repository's own tree were this file matching itself).
SELF = Path(__file__).resolve()


def producer_files(root: Path = REPO_ROOT) -> list[Path]:
    """Every file the repository owns that can author a commit — except this guard itself."""
    out: list[Path] = list(sorted((root / WORKFLOWS).glob("*.yml")))
    makefile = root / MAKEFILE
    if makefile.exists():
        out.append(makefile)
    for pattern in ("*.sh", "*.py"):
        out += sorted((root / SCRIPTS).rglob(pattern))
    return [p for p in out if p.resolve() != SELF]


def _runtime_value(value: str) -> bool:
    """A value a producer resolves at run time cannot be read statically."""
    return any(tok in value for tok in RUNTIME)


def _unquote(value: str) -> str:
    """A matched assignment value without its surrounding quotes, so it compares to a real identity."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _producer_values(text: str) -> tuple[list[str], list[str]]:
    """Every git name and email a producer's text assigns, quotes stripped.

    Four shapes, all read: `git config user.name "x"`, `user.name="x"`, an inline
    `git -c user.name=...` and a `GIT_AUTHOR_NAME: x` env assignment. A value is read ONCE however
    many shapes it matches (`git -c user.name="Asimov Agent"` matches both the inline and the
    `git config` form), so a finding is never duplicated for the same assignment.
    """
    names = {_unquote(m.group("value")) for pat in (SET_NAME, INLINE_NAME, ENV_NAME)
             for m in pat.finditer(text)}
    emails = {_unquote(m.group("value")) for pat in (SET_EMAIL, INLINE_EMAIL, ENV_EMAIL)
              for m in pat.finditer(text)}
    names.discard("")
    emails.discard("")
    return sorted(names), sorted(emails)


def check_producers(root: Path = REPO_ROOT) -> list[dict]:
    """The repository's own producers assign an allowed git identity, or record a decision.

    A producer that assigns a literal name/email outside the allowlist is a violation: its commits
    land authored off the allowlist and the PR they open fails the scan above. A producer whose
    identity is resolved at run time (`$(gh api user --jq .login)`) cannot be read from the file at
    all, so it is reported in `report` and NOT counted — the commit scan is the authority either way.
    Every producer in THIS repository pins a literal allowed identity, precisely so a bump/sync PR is
    green instead of red on the gate it just landed under.
    """
    out: list[dict] = []
    for path in producer_files(root):
        where = str(path.relative_to(root))
        names, emails = _producer_values(path.read_text())
        for name in names:
            if _runtime_value(name) or name in ALLOWED:
                continue
            out.append({
                "key": f"producer-name/{where}:{name}",
                "title": f"ci: {where} authors commits as `{name}`, outside the allowlist",
                "evidence": (
                    f"`{where}` sets `user.name` to `{name}`. A PR's commits may be authored by "
                    f"{' or '.join(f'{n} <{e}>' for n, e in ALLOWED.items())} and by no one else "
                    f"(issue #345). Set the allowed identity instead."
                ),
                "where": where,
            })
        for email in emails:
            if _runtime_value(email) or email in ALLOWED.values():
                continue
            out.append({
                "key": f"producer-email/{where}:{email}",
                "title": f"ci: {where} authors commits as `{email}`, outside the allowlist",
                "evidence": (
                    f"`{where}` sets `user.email` to `{email}`. A PR's commits may be authored by "
                    f"{' or '.join(f'{n} <{e}>' for n, e in ALLOWED.items())} and by no one else "
                    f"(issue #345). Set the allowed identity instead."
                ),
                "where": where,
            })
    return out


def check_agents_mandate(root: Path = REPO_ROOT) -> list[dict]:
    """AGENTS.md states the author rule, so the rule cannot be deleted silently."""
    path = root / AGENTS
    text = path.read_text() if path.exists() else ""
    if AGENTS_MANDATE in text:
        return []
    return [{
        "key": "agents-mandate",
        "title": "ci: AGENTS.md no longer states the commit-author rule",
        "evidence": (
            f"`{AGENTS}` must carry the section `{AGENTS_MANDATE}` so the rule is stated where every "
            f"agent reads it. Deleting the rule is a violation, not an edit."
        ),
        "where": AGENTS,
    }]


def findings(base: str, head: str, root: Path = REPO_ROOT) -> list[dict]:
    """Every violation: the commits in the range, the producers and the AGENTS.md mandate."""
    try:
        commits = commits_in_range(base, head, root)
    except RuntimeError as exc:
        return [{
            "key": "range",
            "title": "ci: the commit range could not be read",
            "evidence": str(exc),
            "where": f"{base}..{head}",
        }]
    out = check_commits(commits)
    out += check_producers(root)
    out += check_agents_mandate(root)
    return out


def report(base: str, head: str, root: Path = REPO_ROOT) -> str:
    """Every commit in the range with its verdict, and what the producers assign."""
    lines: list[str] = []
    try:
        commits = commits_in_range(base, head, root)
    except RuntimeError as exc:
        return f"[check-pr-authors] cannot read {base}..{head}: {exc}"
    lines.append(f"[check-pr-authors] {len(commits)} non-merge commit(s) in {base}..{head}")
    for c in commits:
        verdict = "OK" if _identity_finding("x", c["sha"], c["name"], c["email"]) is None else "FAIL"
        trailers = [f"{m.group('name').strip()} <{m.group('email').strip()}>"
                    for m in COAUTHOR.finditer(c["message"])]
        extra = f"  co-authors: {'; '.join(trailers)}" if trailers else ""
        lines.append(f"  {verdict}  {c['sha'][:12]}  {c['name']} <{c['email']}>{extra}")
    lines.append(f"[check-pr-authors] allowed: "
                 f"{', '.join(f'{n} <{e}>' for n, e in ALLOWED.items())}")
    for path in producer_files(root):
        where = str(path.relative_to(root))
        names, emails = _producer_values(path.read_text())
        for name in names:
            tag = "runtime" if _runtime_value(name) else ("OK" if name in ALLOWED else "FAIL")
            lines.append(f"  {tag}  {where}  user.name={name}")
        for email in emails:
            tag = "runtime" if _runtime_value(email) else ("OK" if email in ALLOWED.values() else "FAIL")
            lines.append(f"  {tag}  {where}  user.email={email}")
    return "\n".join(lines)


def render(items: list[dict]) -> str:
    if not items:
        return "[check-pr-authors] OK — every commit in the range is authored by an allowed identity"
    lines = [f"[check-pr-authors] {len(items)} violation(s)"]
    for it in items:
        lines.append(f"  {it['title']}")
        lines.append(f"    {it['evidence']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="check_pr_authors.py")
    p.add_argument("cmd", nargs="?", choices=("check", "report"))
    p.add_argument("--base", default="origin/main")
    p.add_argument("--head", default="HEAD")
    p.add_argument("--root", default=str(REPO_ROOT))
    args = p.parse_args(argv)
    if not args.cmd:
        p.error("need a command: check | report")
    root = Path(args.root)
    if args.cmd == "report":
        print(report(args.base, args.head, root))
        return 0
    items = findings(args.base, args.head, root)
    print(render(items))
    return 1 if items else 0


if __name__ == "__main__":
    sys.exit(main())
