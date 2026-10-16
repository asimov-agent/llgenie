#!/usr/bin/env python3
"""A commit message and a PR body state the issue, the fix and the benefit (issue #313).

A reviewer who reads a commit or a PR must learn three things without opening the issue: **what the
issue was**, **how the change solves it**, and **what the benefit is** — plus the technical detail
(files, tests, gates, measured numbers) that lets them verify the claim. A subject-only commit or an
empty PR body carries none of that, so this guard makes both a red `ci-unit` instead of a habit.

It reads the producers the repository OWNS — `.github/workflows/*.yml`, the `Makefile`,
`scripts/**/*.sh` (shell invocations) and `scripts/**/*.py` (an argv list handed to the repo's `_gh`
helper) — extracts every commit and every PR open they run, and reports:

* `commit-message`      a commit with no message, a placeholder message, a subject that is not a
                        typed Conventional Commit, or no body (a bare subject);
* `pr-body`             a PR opened with no body, or a body that is empty / a placeholder;
* `agents-mandate`      an `AGENTS.md` that no longer carries the mandate section, so the rule
                        cannot be deleted silently.

A producer that opens a PR through a variable or a file is accepted — the guard checks that a real
body is PASSED, and the producers' own tests pin what that body says. Message content (the
Issue/Fix/Benefit parts and the technical extension) is stated in AGENTS.md and pinned by
`tests/test_pr_hygiene.py`.

Commands:
    check_pr_hygiene.py check     exit non-zero on any violation, and list them
    check_pr_hygiene.py report    print every producer and what its messages pass

Usage:
    python3 scripts/check_pr_hygiene.py check
    python3 scripts/check_pr_hygiene.py report
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ".github/workflows"
SCRIPTS = "scripts"
AGENTS = "AGENTS.md"
#: The mandate heading AGENTS.md must carry. Deleting it is a violation, not an edit.
AGENTS_MANDATE = "## Every PR body and commit message carries the issue, the fix and the benefit"
#: A typed Conventional Commit subject: `type(scope): summary`.
CONVENTIONAL = re.compile(r"^(build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)"
                          r"(\([^)]+\))?!?: \S")
#: A message that says nothing. Compared case-insensitively after trimming.
PLACEHOLDERS = {"", "-", "--", "wip", "update", "fix", "msg", "tbd", "todo", "n/a", "na",
                "x", ".", "none", "nothing", "nop"}
#: The invocations this guard governs, as a shell command runs them.
GIT_COMMIT = re.compile(r"\bgit\s+commit\b")
GH_PR_CREATE = re.compile(r"\bgh\s+pr\s+create\b")
#: The same invocations as a Python argv list handed to `_gh(gh, [...])`.
PY_GIT_COMMIT = re.compile(r"""["']git["']\s*,\s*["']commit["']""")
PY_PR_CREATE = re.compile(r"""["'](?:gh["']\s*,\s*["'])?pr["']\s*,\s*["']create["']""")
#: The flag that carries a PR body — file first, so `--body` does not shadow `--body-file`.
BODY_FLAG = re.compile(r"(?<![\w-])(--body-file|--body|-b)(?!=)")
#: The flag that carries a commit message.
MSG_FLAG = re.compile(r"(?<![\w-])(--message|-m|-F|--file)(?!=)")
BODY_FLAGS = ("--body-file", "--body", "-b")
MSG_FLAGS = ("--message", "-m", "-F", "--file")
#: Shell keywords and Python call openings a real invocation may sit behind.
INVOKE_PREFIXES = ("if ", "if ! ", "then ", "do ", "sudo ", "sudo -E ", "! ", "exec ",
                   "subprocess.run(", "subprocess.check_call(", "subprocess.check_output(", "run(")
#: A shell separator an invocation may follow.
INVOKE_SEPARATORS = ("; ", "&& ", "|| ", "| ")


def producer_files(root: Path = REPO_ROOT) -> list[Path]:
    """Every file the repository owns that can run a commit or open a PR."""
    out = list(sorted((root / WORKFLOWS).glob("*.yml")))
    makefile = root / "Makefile"
    if makefile.exists():
        out.append(makefile)
    for pattern in ("*.sh", "*.py"):
        out += sorted((root / SCRIPTS).rglob(pattern))
    return out


def _commands(text: str) -> list[str]:
    """Logical shell commands: backslash-continued lines joined, every other line on its own."""
    out: list[str] = []
    buf = ""
    for line in text.splitlines():
        if line.strip().startswith("#"):
            continue
        stripped = line.rstrip()
        if stripped.endswith("\\"):
            buf += stripped[:-1] + " "
            continue
        buf += stripped
        if buf.strip():
            out.append(buf.strip())
        buf = ""
    if buf.strip():
        out.append(buf.strip())
    return out


def _normalize(cmd: str) -> str:
    """A shell-ish view of a command: the Python argv separators and the brackets flattened."""
    s = re.sub(r"""["'],\s*["']""", " ", cmd)
    for ch in ("[", "]", '"', "'"):
        s = s.replace(ch, " ")
    return s


def _invokes(cmd: str, pattern: re.Pattern) -> bool:
    """Does `cmd` INVOKE this program, rather than merely mention it in prose?

    The invocation must stand at the start of a command — after a shell keyword, a call opening, or
    a separator — so a docstring that names the command mid-sentence is not read as a producer.
    """
    def at_start(s: str) -> bool:
        s = s.lstrip()
        for prefix in INVOKE_PREFIXES:
            if s.startswith(prefix):
                s = s[len(prefix):].lstrip()
        return bool(pattern.match(s))

    if at_start(cmd):
        return True
    for sep in INVOKE_SEPARATORS:
        idx = cmd.find(sep)
        while idx != -1:
            if at_start(cmd[idx + len(sep):]):
                return True
            idx = cmd.find(sep, idx + 1)
    return False


def _shell_value(cmd: str, m: re.Match) -> str | None:
    """The value after a flag in a shell command: a quoted span (spaces included), or one token."""
    rest = cmd[m.end():].lstrip()
    if not rest:
        return None
    if rest[0] in "\"'":
        end = rest.find(rest[0], 1)
        return rest[1:end] if end != -1 else rest[1:]
    return rest.split()[0]


def _shell_values(cmd: str, flag_re: re.Pattern) -> list[str]:
    out = []
    for m in flag_re.finditer(cmd):
        value = _shell_value(cmd, m)
        if value is not None:
            out.append(value)
    return out


def _py_values(chunk: str, flags: tuple[str, ...]) -> list[str]:
    """The values after a flag in a Python argv list: `"--body", body` -> `body`."""
    out = []
    for name in flags:
        pattern = re.compile(rf"""(?<![\w-]){re.escape(name)}["']?\s*,\s*([^\s,\]\)]+)""")
        out += [m.group(1).strip("\"'") for m in pattern.finditer(chunk)]
    return out


def _py_chunks(text: str) -> list[str]:
    """The text up to each `]` — an argv list ends there, so a chunk is one call's arguments."""
    out: list[str] = []
    start = 0
    for m in re.finditer(r"\]", text):
        out.append(text[start:m.end()])
        start = m.end()
    return out


def _placeholder(value: str) -> bool:
    return value.strip().strip("\"'").strip().lower() in PLACEHOLDERS


def _body_of(message_parts: list[str]) -> bool:
    """A message carries a body when a SECOND real part is passed, or the message spans lines."""
    real = [p for p in message_parts if not _placeholder(p)]
    if len(real) >= 2:
        return True
    return any("\n" in p or "\\n" in p for p in real)


def _commit_finding(where: str, shown: str, parts: list[str]) -> dict | None:
    """The violation a commit's message parts are, or None when the message is complete."""
    if not parts:
        return {
            "key": f"commit-message/{where}:{shown[:40]}",
            "title": f"ci: {where} runs a commit with no message",
            "evidence": (
                f"`{where}` runs `{shown[:160]}` and passes no message, so the commit lands empty "
                f"(or git opens an editor that does not exist in CI). AGENTS.md requires a typed "
                f"Conventional Commit subject plus a body stating the issue, the fix and the benefit."
            ),
            "where": where,
        }
    subject = parts[0]
    if _placeholder(subject):
        return {
            "key": f"commit-message-placeholder/{where}:{shown[:40]}",
            "title": f"ci: {where} commits a placeholder message (`{subject}`)",
            "evidence": (
                f"`{where}` runs `{shown[:160]}` with the subject `{subject}`, which says nothing "
                f"about what changed. A placeholder subject is the same defect as an empty one for "
                f"anyone reading the history."
            ),
            "where": where,
        }
    if not CONVENTIONAL.match(subject):
        return {
            "key": f"commit-message-subject/{where}:{shown[:40]}",
            "title": f"ci: {where} commits a subject that is not a typed Conventional Commit",
            "evidence": (
                f"`{where}` runs `{shown[:160]}` with the subject `{subject}`; AGENTS.md requires "
                f"`type(scope): summary` so the history is machine-readable and a reviewer sees the "
                f"intent before the diff."
            ),
            "where": where,
        }
    if not _body_of(parts):
        return {
            "key": f"commit-message-body/{where}:{shown[:40]}",
            "title": f"ci: {where} commits a subject with no body",
            "evidence": (
                f"`{where}` runs `{shown[:160]}` with a single message part and no body. A reader of "
                f"that commit learns the what, never the issue it answers, the mechanism that fixes "
                f"it, or the benefit — AGENTS.md requires a body carrying all three plus the "
                f"technical extension."
            ),
            "where": where,
        }
    return None


def _pr_finding(where: str, shown: str, values: list[str]) -> dict | None:
    """The violation a PR-open's body is, or None when a real body is passed."""
    if not values:
        return {
            "key": f"pr-body-missing/{where}:{shown[:40]}",
            "title": f"ci: {where} opens a PR with no body",
            "evidence": (
                f"`{where}` runs `{shown[:200]}` and passes no body, so the PR opens with an empty "
                f"description. AGENTS.md requires the body to state the issue, the fix and the "
                f"benefit, plus the technical extension, and to end with `closes #<issue>`."
            ),
            "where": where,
        }
    if _placeholder(values[0]):
        return {
            "key": f"pr-body-placeholder/{where}:{shown[:40]}",
            "title": f"ci: {where} opens a PR with a placeholder body (`{values[0]}`)",
            "evidence": (
                f"`{where}` runs `{shown[:200]}` with a body of `{values[0]}`, which tells a "
                f"reviewer nothing about the issue, the fix or the benefit."
            ),
            "where": where,
        }
    return None


def check_producers(root: Path) -> list[dict]:
    """Every commit and PR open a producer in this repository runs carries a real message/body."""
    out: list[dict] = []
    for path in producer_files(root):
        where = str(path.relative_to(root))
        text = path.read_text()
        if path.suffix == ".py":
            for chunk in _py_chunks(text):
                if PY_GIT_COMMIT.search(chunk):
                    finding = _commit_finding(where, chunk.strip()[-160:], _py_values(chunk, MSG_FLAGS))
                    if finding:
                        out.append(finding)
                if PY_PR_CREATE.search(chunk):
                    finding = _pr_finding(where, chunk.strip()[-200:], _py_values(chunk, BODY_FLAGS))
                    if finding:
                        out.append(finding)
            continue
        for cmd in _commands(text):
            if _invokes(cmd, GIT_COMMIT):
                finding = _commit_finding(where, cmd, _shell_values(cmd, MSG_FLAG))
                if finding:
                    out.append(finding)
            if _invokes(_normalize(cmd), GH_PR_CREATE):
                finding = _pr_finding(where, cmd, _shell_values(cmd, BODY_FLAG))
                if finding:
                    out.append(finding)
    return out


def check_agents_mandate(root: Path) -> list[dict]:
    """AGENTS.md carries the mandate section, so the rule cannot be deleted silently."""
    text = (root / AGENTS).read_text() if (root / AGENTS).exists() else ""
    if AGENTS_MANDATE in text:
        return []
    return [{
        "key": "agents-mandate/agents-md",
        "title": "ci: AGENTS.md no longer carries the PR/commit message mandate",
        "evidence": (
            f"`{AGENTS}` does not contain the heading `{AGENTS_MANDATE}`. That section states what "
            f"every commit message and PR body must carry — the issue, the fix, the benefit and the "
            f"technical extension. A rule that can be deleted by accident is not a rule, so its "
            f"presence is checked (issue #313)."
        ),
        "where": AGENTS,
    }]


def findings(root: Path = REPO_ROOT) -> list[dict]:
    return check_producers(root) + check_agents_mandate(root)


def render(items: list[dict]) -> str:
    if not items:
        return "[pr-hygiene] OK: every producer states the issue, the fix and the benefit"
    lines = [f"[pr-hygiene] {len(items)} violation(s)"]
    for f in items:
        lines += ["", f"- {f['title']}", f"  where: {f['where']}", f"  {f['evidence']}"]
    return "\n".join(lines)


def report(root: Path = REPO_ROOT) -> str:
    """Every producer and the messages it passes — the human view of what the guard reads."""
    lines = ["[pr-hygiene] producers and their messages"]
    for path in producer_files(root):
        rel = str(path.relative_to(root))
        found: list[str] = []
        text = path.read_text()
        if path.suffix == ".py":
            for chunk in _py_chunks(text):
                if PY_GIT_COMMIT.search(chunk):
                    parts = _py_values(chunk, MSG_FLAGS)
                    found.append(f"    commit      parts={len(parts)} subject={parts[0] if parts else '(none)'}")
                if PY_PR_CREATE.search(chunk):
                    values = _py_values(chunk, BODY_FLAGS)
                    found.append(f"    pr open     body={values[0] if values else '(none)'}")
        else:
            for cmd in _commands(text):
                if _invokes(cmd, GIT_COMMIT):
                    parts = _shell_values(cmd, MSG_FLAG)
                    found.append(f"    commit      parts={len(parts)} subject={parts[0] if parts else '(none)'}")
                if _invokes(_normalize(cmd), GH_PR_CREATE):
                    values = _shell_values(cmd, BODY_FLAG)
                    found.append(f"    pr open     body={values[0] if values else '(none)'}")
        if found:
            lines.append(f"- {rel}")
            lines += found
    lines += ["", render(findings(root))]
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="check_pr_hygiene", description=__doc__)
    sub = p.add_subparsers(dest="cmd")
    for name in ("check", "report"):
        c = sub.add_parser(name)
        c.add_argument("--root", default=str(REPO_ROOT))
    args = p.parse_args(argv)
    if not args.cmd:
        p.error("need a command: check | report")
    root = Path(args.root)
    if args.cmd == "report":
        print(report(root))
        return 0
    items = findings(root)
    print(render(items))
    return 1 if items else 0


if __name__ == "__main__":
    raise SystemExit(main())
