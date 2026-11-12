#!/usr/bin/env python3
"""A commit message and a PR body state the issue, the fix and the benefit (issue #313), and a PR
closes the issue it implements (issue #324).

A reviewer who reads a commit or a PR must learn three things without opening the issue: **what the
issue was**, **how the change solves it**, and **what the benefit is** — plus the technical detail
(files, tests, gates, measured numbers) that lets them verify the claim. A subject-only commit or an
empty PR body carries none of that, so this guard makes both a red `ci-unit` instead of a habit. The
closing rule is the other half: a PR that implements an issue MUST close it (`closes #<n>`), so the
issue's state stays evidence about the code — measured on `main` (`4d999e3`), 13 of the last 38
merged PRs closed nothing.

It reads the producers the repository OWNS — `.github/workflows/*.yml`, the `Makefile`,
`scripts/**/*.sh` (shell invocations) and `scripts/**/*.py` (an argv list handed to the repo's `_gh`
helper) — extracts every commit and every PR open they run, and reports:

* `commit-message`      a commit with no message, a placeholder message, a subject that is not a
                        typed Conventional Commit, or no body (a bare subject);
* `pr-body`             a PR opened with no body, a PR body that is empty / a placeholder, or a PR
                        body that is a serialized JSON object (a `gh pr create` request payload
                        moments from being posted as the body);
* `pr-comment`          a comment (posted through `gh pr comment` / `gh issue comment`, or the
                        `/issues/{n}/comments` endpoint) whose body is the same serialized-object
                        class;
* `agents-mandate`      an `AGENTS.md` that no longer carries the message mandate, so the rule
                        cannot be deleted silently;
* `agents-closing-rule` an `AGENTS.md` that no longer states that a PR closes the issue it
                        implements, so the closing rule cannot be deleted silently either.

The object-vs-prose class: a message body must be **prose** the owner and reviewer can read. A body
that is a serialized JSON object — begins with `{` and parses as a `dict`, or carries the
`gh pr create` request keys (`title`, `base`, `body`) — is a machine payload dumped where prose
belonged. #1637's body was, for its whole life, that payload: it carried the real markdown on the
inside, so the old empty-only check stayed green while the human surface read the raw API JSON. A
producer that ever passes the request object where a message string belonged fails here by name
(issue #1638).

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
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ".github/workflows"
SCRIPTS = "scripts"
AGENTS = "AGENTS.md"
#: The mandate heading AGENTS.md must carry. Deleting it is a violation, not an edit.
AGENTS_MANDATE = "## Every PR body and commit message carries the issue, the fix and the benefit"
#: The closing rule AGENTS.md must carry — a PR that implements an issue closes it. The loophole
#: ("if the PR does not close an issue, still end with the issue reference") is what this forbids.
AGENTS_CLOSING_RULE = "A PR that implements an issue MUST close it"
#: A typed Conventional Commit subject: `type(scope): summary`.
CONVENTIONAL = re.compile(r"^(build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)"
                          r"(\([^)]+\))?!?: \S")
#: A message that says nothing. Compared case-insensitively after trimming.
PLACEHOLDERS = {"", "-", "--", "wip", "update", "fix", "msg", "tbd", "todo", "n/a", "na",
                "x", ".", "none", "nothing", "nop"}
#: The invocations this guard governs, as a shell command runs them.
GIT_COMMIT = re.compile(r"\bgit\s+commit\b")
GH_PR_CREATE = re.compile(r"\bgh\s+pr\s+create\b")
GH_PR_COMMENT = re.compile(r"\bgh\s+pr\s+comment\b")
GH_ISSUE_COMMENT = re.compile(r"\bgh\s+issue\s+comment\b")
GH_API_COMMENT = re.compile(r"\bgh\s+api\b.*?/issues/\d+/comments\b")
PY_COMMENT = re.compile(r"comment")
#: The same invocations as a Python argv list handed to `_gh(gh, [...])`.
PY_GIT_COMMIT = re.compile(r"""["']git["']\s*,\s*["']commit["']""")
PY_PR_CREATE = re.compile(r"""["'](?:gh["']\s*,\s*["'])?pr["']\s*,\s*["']create["']""")
#: The flag that carries a PR body — file first, so `--body` does not shadow `--body-file`.
BODY_FLAG = re.compile(r"(?<![\w-])(--body-file|--body|-b)(?!=)")
#: The flag that carries a commit message. `-[a-z]*m` also reads the SHORT-FLAG BUNDLE git accepts
#: (`-am`, `-sm`), because `git commit -am "…"` carries its message just as `-m "…"` does and a rule
#: that reads only `-m` reports a real message as "no message" (measured on `fix-bot.yml`, #840).
MSG_FLAG = re.compile(r"(?<![\w-])(--message|-[a-z]*m|-F|--file)(?!=)")
BODY_FLAGS = ("--body-file", "--body", "-b")
MSG_FLAGS = ("--message", "-m", "-F", "--file")
#: Shell keywords and Python call openings a real invocation may sit behind.
INVOKE_PREFIXES = ("if ", "if ! ", "then ", "do ", "sudo ", "sudo -E ", "! ", "exec ",
                   "subprocess.run(", "subprocess.check_call(", "subprocess.check_output(", "run(")  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
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
    """Logical shell commands: backslash-continued lines joined, and a MULTI-LINE quoted message kept
    whole — a `git commit -am "subject\\n\\nbody…"` spans lines and is still ONE command."""
    out: list[str] = []
    buf = ""
    for line in text.splitlines():
        if line.strip().startswith("#") and not buf:
            continue
        stripped = line.rstrip()
        if stripped.endswith("\\"):
            buf += stripped[:-1] + " "
            continue
        buf += stripped
        if buf.count('"') % 2 == 1:
            # An open double quote: the command continues on the next line.
            buf += "\n"
            continue
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


def _py_unquote(value: str) -> str:
    """A Python string literal without its quotes (and its `f` prefix), so it compares to real text."""
    value = value.strip()
    if value[:2] in ("f\"", "f'"):
        value = value[1:]
    return value.strip("\"'")


def _py_values(chunk: str, flags: tuple[str, ...]) -> list[str]:
    """The values after a flag in a Python argv list: `"--body", body` -> `body`.

    A QUOTED string is read whole, spaces included (`"-m", f"fix(x): one subject"` is ONE value), and
    only then a bare token is taken. Reading one token made every message containing a space look
    like a one-word subject — and a `-m` whose inline `-c` flags had hidden the call entirely was
    never read at all (measured while converting the producers to the one identity seam, #840).
    """
    out = []
    for name in flags:
        pattern = re.compile(
            rf"""(?<![\w-]){re.escape(name)}["']?\s*,\s*([f]?(?:"[^"]*"|'[^']*')|[^\s,\])]+)""")
        out += [_py_unquote(m.group(1)) for m in pattern.finditer(chunk)]
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
#: The `gh pr create` request keys that mark a message body as the serialized API payload, not prose.
#: #1637's body carried all three for its whole life (issue #1638).
CREATE_KEYS = ("title", "base", "body")


def _object_body(value: str) -> bool:
    """Is `value` a serialized JSON object (a `gh pr create` payload) instead of prose?"""
    naked = value.strip().strip("\"'""").strip()
    if not naked.startswith("{"):
        return False
    try:
        parsed = json.loads(naked)
    except ValueError:
        return all(json.dumps(k) in naked for k in CREATE_KEYS)
    if isinstance(parsed, dict):
        return True
    return all(json.dumps(k) in naked for k in CREATE_KEYS)



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
    if _object_body(values[0]):
        return {
            "key": f"pr-body-json/{where}:{shown[:40]}",
            "title": f"ci: {where} opens a PR with a body that is a serialized JSON object",
            "evidence": (
                f"`{where}` runs `{shown[:200]}` with a body that is the serialized `gh pr create` "
                f"request object (`{values[0][:120]}...`), not prose. GitHub renders that raw JSON "
                f"as the review surface — a reader sees the machine payload, never the markdown it "
                f"wraps. The body must be the prose itself (issue #1638)."
            ),
            "where": where,
        }
    return None


def _comment_finding(where: str, shown: str, values: list[str]) -> dict | None:
    """The violation a comment's body is, when it is the serialized-object class (issue #1638)."""
    for value in values:
        if _object_body(value):
            return {
                "key": f"pr-comment-json/{where}:{shown[:40]}",
                "title": f"ci: {where} posts a comment whose body is a serialized JSON object",
                "evidence": (
                    f"`{where}` runs `{shown[:200]}` and posts a comment whose body is the raw "
                    f"`gh pr create` request object (`{value[:120]}...`) instead of prose. A reader "
                    f"of the thread sees the machine payload, never the message it wraps — the same "
                    f"object-vs-prose rule that guards PR bodies guards comments (issue #1638)."
                ),
                "where": where,
            }
    return None


def _shell_field_values(cmd: str, name: str) -> list[str]:
    """The values of a `-f <name>=<value>` / `--field <name>=<value>` gh api field, as passed."""
    out: list[str] = []
    for prefix in ("-f ", "-F ", "--field "):
        token = prefix + name + "="
        pos = 0
        while True:
            pos = cmd.find(token, pos)
            if pos == -1:
                break
            rest = cmd[pos + len(token):].lstrip()
            if not rest:
                break
            if rest[0] in ('"', "'"):
                end = rest.find(rest[0], 1)
                out.append(rest[1:end] if end != -1 else rest[1:])
            else:
                out.append(rest.split()[0])
            pos += len(token)
    return out


def _py_comment_bodies(chunk: str) -> list[str]:
    """The comment bodies posted from a Python argv seam: `--body`, or a `"body=<value>"` field."""
    return _py_values(chunk, ("--body", "-b")) + _py_field_values(chunk, "body")


def _py_field_values(chunk: str, name: str) -> list[str]:
    """`"body", <value>` or `"body=<value>"` in a Python argv list handed to `_gh`."""
    out: list[str] = []
    nlen = len(name)
    pos = 0
    while True:
        pos = chunk.find(name, pos)
        if pos == -1:
            break
        after = chunk[pos + nlen:]
        sep = ""
        if after.startswith("="):
            sep = "="
        elif after.lstrip().startswith(","):
            sep = ","
        if sep:
            rest = after[len(sep):].lstrip()
            if rest and rest[0] in ('"', "'"):
                q = rest[0]
                end = rest.find(q, 1)
                if end != -1:
                    out.append(rest[1:end])
        pos += nlen
    return out


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
                if PY_COMMENT.search(chunk):
                    finding = _comment_finding(where, chunk.strip()[-200:], _py_comment_bodies(chunk))
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
            if _invokes(cmd, GH_PR_COMMENT) or _invokes(cmd, GH_ISSUE_COMMENT) \
                    or _invokes(_normalize(cmd), GH_API_COMMENT):
                finding = _comment_finding(where, cmd,
                                           _shell_values(cmd, BODY_FLAG)
                                           + _shell_field_values(cmd, "body"))
                if finding:
                    out.append(finding)
    return out


def check_agents_mandate(root: Path) -> list[dict]:
    """AGENTS.md carries the mandate section AND the closing rule, so neither is deleted silently."""
    text = (root / AGENTS).read_text() if (root / AGENTS).exists() else ""
    out: list[dict] = []
    if AGENTS_MANDATE not in text:
        out.append({
            "key": "agents-mandate/agents-md",
            "title": "ci: AGENTS.md no longer carries the PR/commit message mandate",
            "evidence": (
                f"`{AGENTS}` does not contain the heading `{AGENTS_MANDATE}`. That section states what "
                f"every commit message and PR body must carry — the issue, the fix, the benefit and the "
                f"technical extension. A rule that can be deleted by accident is not a rule, so its "
                f"presence is checked (issue #313)."
            ),
            "where": AGENTS,
        })
    if AGENTS_CLOSING_RULE not in text:
        out.append({
            "key": "agents-closing-rule/agents-md",
            "title": "ci: AGENTS.md no longer states that a PR closes the issue it implements",
            "evidence": (
                f"`{AGENTS}` does not contain `{AGENTS_CLOSING_RULE}`. A PR that implements an issue "
                f"must close it (`closes #<n>`); a partial implementation must not, and must name what "
                f"remains as a linked work item. Without the rule stated, a PR that closes nothing "
                f"passes review silently — 13 of the last 38 merged PRs did exactly that on `main` "
                f"(`4d999e3`), and #321 was closed by hand with no implementing PR while its defect "
                f"still reproduced. The rule cannot be deleted by an edit that leaves the code green "
                f"(issue #324)."
            ),
            "where": AGENTS,
        })
    return out


#: Every identity the bot lanes commit as. One email, several names: `check_pr_authors.py` allows
#: `Asimov Agent <support@docondee.com>` and `Mr. Asimov <support@docondee.com>`.
BOT_EMAILS = frozenset({"support@docondee.com"})

AGENTS_LINE = re.compile(r"^AGENTS:\s+([0-9a-f]{7,40})\s+(\d+)b\s+(\d+)l\s*$", re.M)
#: The `BASE:` line #845 adds beside the `AGENTS:` line — the origin/main sha the
#: PR was cut from, so a reviewer can check the base without consulting the branch.
#: `(=~ origin/main at open)` is the human reminder; the sha is what the gate reads.
BASE_LINE = re.compile(r"^BASE:\s+([0-9a-f]{7,40})\s+\(==\s*origin/main at open\)\s*$", re.M)
#: The `SYNC:` line issue #1724 adds: a landed profile change must report the live re-sync. The owner's
#: rule is that behaviour-versioned changes (SOUL/skills/rule) must propagate from the tree INTO the live
#: profile (`make sync-agent-profile PROFILE=<p>`), and the PR body must say so, so a reviewer can verify
#: propagation happened rather than just a commit. Each line names exactly one profile + its command.
SYNC_LINE = re.compile(r"^SYNC:\s+([A-Za-z0-9_-]+)\s+make sync-agent-profile PROFILE=\1\s*$", re.M)

#: The `OPENSPEC:` body line issue #1807 adds: an implementing PR with no openspec/ diff of its own may
#: deliberately name the active change it implements against, so a legitimately change-less PR opts out
#: explicitly instead of by silence. One name per line, matched literally against the ACTIVE change dirs.
OPENSPEC_REF = re.compile(r"^OPENSPEC:\s+([A-Za-z0-9_-]+)\s*$", re.M)


def pr_openspec_change_findings(root: Path, head: str, base: str, body: str) -> list[dict]:
    """`openspec_change_findings`, but only for a range that carries bot work — the gate's real entry point."""
    if not is_bot_pr(root, base, head):
        return []
    return openspec_change_findings(root, head, base, body)


def range_authors(root: Path, base: str, head: str) -> list[str]:
    """The author emails of the commits this PR adds, `--no-merges` so `refs/pull/N/merge` cannot hide them."""
    out = _git(root, "log", "--no-merges", "--format=%ae", f"{base}..{head}")
    return [line.strip() for line in (out or "").splitlines() if line.strip()]


def is_bot_pr(root: Path, base: str, head: str) -> bool:
    """Whether this PR carries a bot leg's work — **any** bot-authored commit, not every one.

    `all()` was the hole: a branch where a human commit sits beside a bot commit reported False, so a
    bot PR body with no `AGENTS:` line passed this gate — including the PR that introduced it. A human
    PR with no bot commit is still skipped, because the rule is stated nowhere a person reads.
    """
    return any(author in BOT_EMAILS for author in range_authors(root, base, head))


def pr_agents_line_findings(root: Path, head: str, base: str, body: str) -> list[dict]:
    """`agents_line_findings`, but only for a range that carries bot work — the gate's real entry point."""
    if not is_bot_pr(root, base, head):
        return []
    return agents_line_findings(root, head, base, body)


def agents_line_findings(root: Path, head: str, base: str, body: str) -> list[dict]:
    """A bot PR's `AGENTS:` line must cite a rulebook its head AND base both contain (issue #792).

    Ancestry, never equality with the merge base: `rebase-bot` moves the merge base while the cited
    rulebook stays reachable from both sides, so equality would reject exactly the PRs that were kept
    current. `--no-merges` on the range read keeps the `refs/pull/N/merge` commit CI checks out from
    hiding a citation that was never on either side.
    """
    m = AGENTS_LINE.search(body)
    if m is None:
        return [{
            "key": "agents-line",
            "where": "PR body",
            "detail": "no `AGENTS: <sha> <bytes>b <lines>l` line — run `make bot-preflight` and cite what "
                      "it writes (issue #792)",
        }]
    sha = m.group(1)
    resolved = _git(root, "rev-parse", "--verify", "--quiet", f"{sha}^{{commit}}")
    if resolved is None:
        return [{
            "key": "agents-line",
            "where": "PR body",
            "detail": f"the `AGENTS:` line cites {sha}, which is not a commit in this clone",
        }]
    bad = [ref for ref in (head, base) if not _is_ancestor(root, resolved, ref)]
    if bad:
        return [{
            "key": "agents-line",
            "where": "PR body",
            "detail": f"the `AGENTS:` line cites {sha[:12]}, which is not an ancestor of "
                      f"{', '.join(bad)} — the rulebook cited must be reachable from both the head and "
                      f"the base (issue #792)",
        }]
    # Issue #845: a bot PR MUST also record the base it was cut from, beside the AGENTS line, so a
    # reviewer can check it without the branch. preflight emits it (`BASE: <sha> (== origin/main at
    # open)`); the gate holds the body to the same `record['main']` — the sha of the origin/main commit
    # the AGENTS line already cites must be what the BASE line names. A missing or non-matching BASE
    # line is the defect #845 names (the base was recorded nowhere, so a worktree cut from the primary
    # checkout's parked branch carried the wrong base invisibly).
    mb = BASE_LINE.search(body)
    if mb is None:
        return [{
            "key": "base-line",
            "where": "PR body",
            "detail": "no `BASE: <sha> (== origin/main at open)` line — run `make bot-preflight` and "
                      "record the base the PR was cut from, beside the `AGENTS:` line (issue #845)",
        }]
    if mb.group(1) != sha:
        return [{
            "key": "base-line",
            "where": "PR body",
            "detail": f"the `BASE:` line names {mb.group(1)[:12]}, but the `AGENTS:` line cites "
                      f"{sha[:12]} — the base recorded must be the same origin/main commit the rulebook "
                      f"was measured at (issue #845)",
        }]
    return []


def _diff_profiles(root: Path, base: str, head: str) -> list[str]:
    """The profile dirs (`agents/<name>/`) a range touches — the owner's propagation rule (#1724) turns a
    landed profile change into a REQUIRED live re-sync report, so the gate reads which profiles the range
    actually edits (`git diff --name-only merge-base..head -- agents/`)."""
    # Anchor at the merge-base, never the literal range start (issue #1754). The sync-line gate passes
    # PR_BASE as the LIVE `origin/main` ref the step refreshes to the main TIP; `git diff A..B` compares
    # two TREES, so a foreign post-base `agents/` change on main appears as a deletion against head and
    # is misattributed to this PR as an absent SYNC-line demand. Resolving `git merge-base <base> <head>`
    # first (the #1527 pattern `check_pr_closing` already uses) restricts the diff to the commits THIS PR
    # introduces, so only genuine same-PR `agents/` edits demand a SYNC line (which they still do — the
    # gate is not weakened).
    anchor = _git(root, "merge-base", base, head) or base
    out = _git(root, "diff", "--name-only", f"{anchor}..{head}", "--", "agents")
    names: list[str] = []
    for line in (out or "").splitlines():
        line = line.strip()
        # an agents/<name>/... path, and not the top-level AGENTS.md-carrying file itself
        if line.startswith("agents/") and "/" in line[len("agents/"):]:
            rest = line[len("agents/"):].split("/", 1)[0]
            if rest and rest not in names:
                names.append(rest)
    return sorted(names)


def pr_sync_line_findings(root: Path, head: str, base: str, body: str) -> list[dict]:
    """`sync_line_findings`, but only for a range that carries bot work — the gate's real entry point."""
    if not is_bot_pr(root, base, head):
        return []
    return sync_line_findings(root, head, base, body)


def sync_line_findings(root: Path, head: str, base: str, body: str) -> list[dict]:
    """A bot PR that changes `agents/<profile>/` must report the live re-sync (issue #1724).

    The owner's propagation rule: behaviour-versioned changes (SOUL/skills/rule) must be re-synced from
    the tree INTO the live profile (`make sync-agent-profile PROFILE=<p>`), and that re-sync must be
    REPORTED in the PR body so a reviewer can verify propagation, not just the commit. A profile dir the
    diff touches with no matching `SYNC:` line is a finding: the tree can hold the new rule while the live
    profile that acts under it still runs the old one (the #1707 tree-vs-live drift, the #1719 lane that
    did not know its own PR merged). `--no-merges` keeps the merge-range commit from hiding a citation
    that was never on either side.
    """
    touched = _diff_profiles(root, base, head)
    if not touched:
        return []
    reported = set(SYNC_LINE.findall(body))
    missing = [p for p in touched if p not in reported]
    if not missing:
        return []
    return [{
        "key": "profile-sync",
        "where": "PR body",
        "detail": "this PR changes agents/ under "
                  f"{', '.join('`' + p + '`' for p in missing)} — the owner's propagation rule (#1724) "
                  "requires the profile-owning lane to re-sync the live profile and report it: "
                  "add a `SYNC: <p> make sync-agent-profile PROFILE=<p>` line for each changed profile",
    }]


def openspec_change_findings(root: Path, head: str, base: str, body: str) -> list[dict]:
    """An implementing bot PR must carry (or name) its own OpenSpec change (issue #1807).

    `ci-openspec` validates the STRUCTURE of every ACTIVE change (`openspec-validate-all`) and asserts
    none has an unchecked task (`openspec-tasks-check`), but both only iterate EXISTING changes — a PR
    that implements work with no openspec/ change at all is structurally invisible and CI-green. AGENTS.md
    (lines 27-53, MANDATORY) requires every change to start as an OpenSpec change created before the
    branch. This gate closes the presence half: a bot implementing PR's final diff must add a file under
    `openspec/changes/<name>/`, or the body must name one it implements against (`OPENSPEC: <name>`), or
    the PR must be a pure docs/regen change (nothing to spec-track). No re-validation here — the existing
    two gates own structure and ticks (no hand-rolled change validation, no weakening of either).
    """
    changed = _pr_files(root, base, head)
    if not changed:
        return []
    # pure docs / regen / change-note trio: nothing product to spec-track
    if all(_is_docs_only(p) for p in changed):
        return []
    # the PR's own diff adds an openspec/changes/<name> change dir
    if any(p.startswith("openspec/changes/") and not p.startswith("openspec/changes/archive/") for p in changed):
        return []
    # the body deliberately names an ACTIVE change it implements against
    named = OPENSPEC_REF.findall(body or "")
    active = set(_active_change_names(root))
    if any(n in active for n in named):
        return []
    return [{
        "key": "openspec-change",
        "where": "PR diff",
        "detail": "this PR changes product code but adds no file under `openspec/changes/` and names no "
                  "existing change — AGENTS.md requires every change to start as an OpenSpec change: "
                  "run `make openspec-new NAME=<kebab-name>` before implementing, or add a "
                  "`OPENSPEC: <name>` body line naming the active change this PR implements against",
    }]


def _pr_files(root: Path, base: str, head: str) -> list[str]:
    """Every path the PR's own range adds or modifies (`--name-only` of the merge-base..head diff)."""
    anchor = _git(root, "merge-base", base, head) or base
    out = _git(root, "diff", "--name-only", f"{anchor}..{head}")
    return [line.strip() for line in (out or "").splitlines() if line.strip()]


def _is_docs_only(rel: str) -> bool:
    """A path is pure docs/regen if it is the change-note machinery or a doc surface — nothing to spec-track."""
    return (
        rel == "CHANGES.md"
        or rel == "README.md"
        or rel.startswith("docs/")
        or rel.startswith("agent-wiki/")
    )


def _active_change_names(root: Path) -> list[str]:
    """Currently-ACTIVE (non-archived) change dirs under openspec/changes/ that have a tasks.md.

    Reuses the same convention `scripts/check_openspec_tasks.py::active_change_names` uses (an ACTIVE
    change is a non-`archive` dir holding a `tasks.md`), kept local so this gate needs no import seam for
    a pure directory read.
    """
    base = root / "openspec" / "changes"
    if not base.is_dir():
        return []
    out = []
    for p in sorted(base.iterdir()):
        if not p.is_dir() or p.name == "archive":
            continue
        if (p / "tasks.md").is_file():
            out.append(p.name)
    return out


#: An acceptance heading inside COMMIT text (issue #2519): any markdown heading line that names
#: acceptance. The commit-text twin of `acceptance_writeback._is_acceptance_heading` — kept lenient
#: (substring, not exact) because commit messages embed the issue body with its heading suffixes.
_COMMIT_ACCEPTANCE_HEADING = re.compile(r"^#{1,6}\s.*[Aa]cceptance", re.M)
_COMMIT_UNTICKED = re.compile(r"^\s*[-*]\s+\[\s?\]", re.M)
_COMMIT_TICKED = re.compile(r"^\s*[-*]\s+\[[xX]\]", re.M)


def commit_text_findings(messages: list[str], body: str) -> list[dict]:
    """The commit-text half of checkbox parity (issue #2519).

    A squash merge concatenates the branch's commit messages into the commit that lands on `main`,
    so the commit text is the PERMANENT record of the acceptance checklist. Measured on PR #2509:
    squash `49f0cc3be` carries `checked=0 unchecked=3` — the bot pasted the issue's unticked
    `## Acceptance criteria` into its commit message and nothing read it. Two findings:

    * `commit-unchecked-acceptance` — an unchecked `- [ ]` sitting under an acceptance heading in
      any commit message of the range (the #2509 shape, caught before merge);
    * `commit-acceptance-unmirrored` — the PR body declares N acceptance items
      (`acceptance_writeback.acceptance_items`, reused not restated) while the range's commit text
      carries fewer than N ticked `- [x]` boxes: the tick happened somewhere but never reached the
      permanent record.

    One tick, three mirrors: issue body, PR body, commit text. Closing stays the ONE automatic act
    (the `closes #N` keyword on merge) — this gate never closes and never ticks anything itself.
    Empty body (hermetic preflight, no PR body on a push) checks the commit-side rule only.
    """
    findings: list[dict] = []
    unticked = 0
    for msg in messages:
        in_acceptance = False
        for line in msg.splitlines():
            if line.lstrip().startswith("#"):
                in_acceptance = bool(_COMMIT_ACCEPTANCE_HEADING.match(line.lstrip()))
                continue
            if in_acceptance and _COMMIT_UNTICKED.match(line):
                unticked += 1
    if unticked:
        findings.append({
            "key": "commit-unchecked-acceptance",
            "where": "commit text",
            "detail": f"the range's commit text carries {unticked} unticked `- [ ]` under an acceptance "
                      "heading — a squash merge lands that text on main as the permanent record "
                      "(measured shape: #2509 squash `49f0cc3be`, checked=0 unchecked=3). Tick every "
                      "criterion in the commit message too, or drop the checklist from the message "
                      "(issue #2519)",
        })
    if body:
        from acceptance_writeback import acceptance_items, BodyError  # noqa: PLC0415 reuse, never restate
        try:
            items = acceptance_items(body)
        except BodyError:
            items = []
        if items:
            ticked = sum(len(_COMMIT_TICKED.findall(m)) for m in messages)
            if ticked < len(items):
                findings.append({
                    "key": "commit-acceptance-unmirrored",
                    "where": "commit text",
                    "detail": f"the PR body declares {len(items)} acceptance items but the range's "
                              f"commit text carries only {ticked} ticked `- [x]` boxes — the ticked "
                              "checklist must mirror into the commit message so the squash text on main "
                              "proves it was ticked (issue #2519); end the implementation commit with a "
                              "ticked `Acceptance:` block",
                })
    return findings


def commit_checkboxes_findings(root: Path, head: str, base: str, body: str) -> list[dict]:
    """`commit_text_findings` over a real PR range, bot ranges only (issue #2519)."""
    if not is_bot_pr(root, base, head):
        return []
    raw = _git(root, "log", "--no-merges", "--format=%B%x00", f"{base}..{head}") or ""
    messages = [m for m in raw.split("\x00") if m.strip()]
    return commit_text_findings(messages, body)


def pr_acceptance_form_findings(root: Path, head: str, base: str, body: str) -> list[dict]:
    """A bot PR's body must carry its own `## Acceptance criteria` `- [ ]` checklist (issue #1796).

    The owner's form rule (#1796): every issue a lane files AND every PR body it opens carries a
    `## Acceptance criteria` section with each criterion a `- [ ] ` markdown checkbox, one per provable
    outcome; a criterion a reviewer cannot tick is not one (#745). This is the PR-BODY half: the
    merge-time `check-pr-acceptance` gate (issue #1792) verifies the LINKED ISSUE's criteria are ticked,
    so a close of an un-proven issue does not verify green silently — but it is silent when the PR body
    itself never had the boxes to tick. This surface flags THAT: a bot-authored PR body with no (or an
    empty) acceptance checklist. Verification/surface only — it never blocks #1088 auto-merge and never
    ticks a box (that stays #1644). Human-only ranges are skipped (the rule is stated for fleet lanes, and
    `is_bot_pr` mirrors the other lookups).
    """
    if not is_bot_pr(root, base, head):
        return []
    from acceptance_writeback import acceptance_items, BodyError  # noqa: PLC0415  reuse, never restate (#1796)
    try:
        items = acceptance_items(body)
    except BodyError:
        items = []
    if items:
        return []
    return [{
        "key": "acceptance-form",
        "where": "PR body",
        "detail": "a bot PR body must carry its own `## Acceptance criteria` `- [ ]` checklist — each "
                  "criterion a `- [ ]` checkbox, one per provable outcome (#745); a criterion a reviewer "
                  "cannot tick is not one. This body has no tickable acceptance checklist (issue #1796) — "
                  "add the `## Acceptance criteria` section with at least one `- [ ]` item, one per "
                  "provable outcome",
    }]


def _git(root: Path, *args: str) -> str | None:
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
    return r.stdout.strip() if r.returncode == 0 else None


def _is_ancestor(root: Path, sha: str, ref: str) -> bool:
    r = subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", sha, ref],  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
                       capture_output=True, text=True, check=False)
    return r.returncode == 0


def _index_module():
    """`scripts/changes_index.py` — the ONE row parser, shared rather than re-implemented (#934)."""
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    import changes_index as ci  # noqa: PLC0415  (shared parser, imported beside its target)
    return ci


def changes_index_findings(root: Path = REPO_ROOT) -> list[dict]:
    """Every `CHANGES.md` row must correspond to a `docs/changes.d/<stem>.md` fragment (issue #1063).

    A TREE-CONSISTENCY check, not a diff check: reads `CHANGES.md` and the fragment directory in the
    checkout, so it behaves identically in `ci-unit`, `issue-bot-gates` and a direct run, and needs
    no base ref. Forward-looking by construction: a legitimate `make changes-index` regen builds rows
    *from* fragments so it passes, while a hand-added aggregate row and a union-merge duplicate fail.

    Two conditions, both required:
      1. every row's note has a `docs/changes.d/<stem>.md` fragment (currentness NOT required — a
         stale index passes);
      2. no note appears in more than one row (the union-merge shape). Condition 1 alone misses it:
         a duplicated row points at the same note that already has a fragment, so both copies pass.
    """
    ci = _index_module()
    changes = root / ci.CHANGES
    if not changes.exists():
        return []
    stems: list[str] = []
    for line in changes.read_text().splitlines():
        m = ci.ROW_RE.search(line)
        if m:
            note = m.group("note")
            stems.append(note[:-3] if note.endswith(".md") else note)
    fragments = set(ci._stems(root))
    out: list[dict] = []
    for stem in stems:
        if stem not in fragments:
            out.append({
                "key": "changes-index",
                "where": "CHANGES.md",
                "detail": f"row for note `{stem}` has no {ci.FRAGMENTS}/{stem}.md — a change adds its "
                          f"fragment, never a hand-written aggregate row; add "
                          f"{ci.FRAGMENTS}/{stem}.md with its row (issue #1063)",
            })
    seen: dict[str, int] = {}
    for stem in stems:
        seen[stem] = seen.get(stem, 0) + 1
    for stem, n in seen.items():
        if n > 1:
            out.append({
                "key": "changes-index",
                "where": "CHANGES.md",
                "detail": f"note `{stem}` appears in {n} rows, and a fragment is one row — re-render "
                          f"with `make changes-index` from {ci.FRAGMENTS}/{stem}.md; do not "
                          f"union-merge this file (issue #1063)",
            })
    return out


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
    a = sub.add_parser("agents-line", help="a PR body's `AGENTS:` line cites a reachable rulebook (issue #792)")
    a.add_argument("--root", default=str(REPO_ROOT))
    a.add_argument("--head", required=True, help="the PR head ref or sha")
    a.add_argument("--base", required=True, help="the PR base ref or sha")
    a.add_argument("--body-file", required=True, help="the file holding the PR body")
    a = sub.add_parser("sync-line", help="a profile-editing bot PR reports its live re-sync in a `SYNC:` line (issue #1724)")
    a.add_argument("--root", default=str(REPO_ROOT))
    a.add_argument("--head", required=True, help="the PR head ref or sha")
    a.add_argument("--base", required=True, help="the PR base ref or sha")
    a.add_argument("--body-file", required=True, help="the file holding the PR body")
    o = sub.add_parser("openspec-change", help="an implementing bot PR adds or names its own OpenSpec change (issue #1807)")
    o.add_argument("--root", default=str(REPO_ROOT))
    o.add_argument("--head", required=True, help="the PR head ref or sha")
    o.add_argument("--base", required=True, help="the PR base ref or sha")
    o.add_argument("--body-file", required=True, help="the file holding the PR body")
    a = sub.add_parser("acceptance-form", help="a bot PR's body carries its own `## Acceptance criteria` `- [ ]` checklist (issue #1796)")
    a.add_argument("--root", default=str(REPO_ROOT))
    a.add_argument("--head", required=True, help="the PR head ref or sha")
    a.add_argument("--base", required=True, help="the PR base ref or sha")
    a.add_argument("--body-file", required=True, help="the file holding the PR body")
    c = sub.add_parser("commit-checkboxes", help="a bot range's commit text carries the ticked acceptance mirror and no unticked acceptance box (issue #2519)")
    c.add_argument("--root", default=str(REPO_ROOT))
    c.add_argument("--head", required=True, help="the PR head ref or sha")
    c.add_argument("--base", required=True, help="the PR base ref or sha")
    c.add_argument("--body-file", default="", help="the file holding the PR body (omit: commit-side rule only)")
    c = sub.add_parser("changes-index", help="a CHANGES.md row has a docs/changes.d/<stem>.md fragment, and no note appears twice (issue #1063)")
    c.add_argument("--root", default=str(REPO_ROOT))
    args = p.parse_args(argv)
    if not args.cmd:
        p.error("need a command: check | report")
    root = Path(args.root)
    if args.cmd == "report":
        print(report(root))
        return 0
    if args.cmd == "agents-line":
        body = Path(args.body_file).read_text()
        items = pr_agents_line_findings(root, args.head, args.base, body)
        if items:
            for it in items:
                print(f"[check-pr-hygiene] {it['where']}: {it['detail']}", file=sys.stderr)
            return 1
        print("[check-pr-hygiene] OK: the `AGENTS:` line is reachable from both head and base")
        return 0
    if args.cmd == "sync-line":
        body = Path(args.body_file).read_text()
        items = pr_sync_line_findings(root, args.head, args.base, body)
        if items:
            for it in items:
                print(f"[check-pr-hygiene] {it['where']}: {it['detail']}", file=sys.stderr)
            return 1
        print("[check-pr-hygiene] OK: every changed agent profile reports its live re-sync (`SYNC:` line)")
        return 0
    if args.cmd == "openspec-change":
        body = Path(args.body_file).read_text()
        items = pr_openspec_change_findings(root, args.head, args.base, body)
        if items:
            for it in items:
                print(f"[check-pr-hygiene] {it['where']}: {it['detail']}", file=sys.stderr)
            return 1
        print("[check-pr-hygiene] OK: the bot PR's diff adds (or the body names) its own OpenSpec change")
        return 0
    if args.cmd == "acceptance-form":
        body = Path(args.body_file).read_text()
        items = pr_acceptance_form_findings(root, args.head, args.base, body)
        if items:
            for it in items:
                print(f"[check-pr-hygiene] {it['where']}: {it['detail']}", file=sys.stderr)
            return 1
        print("[check-pr-hygiene] OK: this bot PR's body carries its own `## Acceptance criteria` `- [ ]` checklist")
        return 0
    if args.cmd == "commit-checkboxes":
        body = Path(args.body_file).read_text() if args.body_file else ""
        items = commit_checkboxes_findings(root, args.head, args.base, body)
        if items:
            for it in items:
                print(f"[check-pr-hygiene] {it['where']}: {it['detail']}", file=sys.stderr)
            return 1
        print("[check-pr-hygiene] OK: the range's commit text carries the ticked acceptance mirror "
              "with no unticked acceptance box (issue #2519)")
        return 0
    if args.cmd == "changes-index":
        items = changes_index_findings(root)
        if items:
            for it in items:
                print(f"[check-pr-hygiene] {it['where']}: {it['detail']}", file=sys.stderr)
            return 1
        print("[check-pr-hygiene] OK: every CHANGES.md row has its docs/changes.d/ fragment, "
              "and no note appears twice (issue #1063)")
        return 0
    items = findings(root)
    print(render(items))
    return 1 if items else 0


if __name__ == "__main__":
    raise SystemExit(main())
