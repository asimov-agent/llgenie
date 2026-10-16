#!/usr/bin/env python3
"""Every workflow file is validated before it can be merged (issues #330, #329).

GitHub REFUSES a whole workflow file whose `${{ ... }}` expression it cannot parse, and the refusal is
silent: the run appears with `status=completed`, `conclusion=failure`, **zero** jobs, a `name` equal to
the file PATH, and no log. Measured on `main` — `.github/workflows/engine-bump-rebase.yml` carried

    # folded into one `${{ ... }}` so the mode this run took is readable in the log.

inside the `rebase` job's `run: |` block. A `#` line inside a block scalar is **script text, not a YAML
comment**, so the expression parser read `${{ ... }}`, could not parse `...`, and refused the file — for
every push touching `.github/workflows/**` (`38850302335`, `38850145191`, `38849945773`, `38844778241`).
`yaml.safe_load` accepts it, because PyYAML has no notion of `${{ }}`.

So this guard reads every YAML file in the repository and reports:

* `workflow-expression`  a `${{ ... }}` that does not parse — the class GitHub rejects a file for;
* `workflow-newline`     a YAML file that does not end with a newline (the repo's lint spec);
* `workflow-name`        a `.github/workflows/*.yml` with no top-level `name:` — which is what makes a
                         startup failure present itself as a path instead of a workflow.

The expression check is a real recursive-descent parser over GitHub's expression grammar (`||`, `&&`,
comparisons, `+ - * / %`, unary `! -`, property access `.x` / `.*` / `[...]`, function calls, numbers,
single-quoted strings, `true`/`false`/`null`). It is stdlib only, so the gate runs on the host exactly as
`check-docs` and `check-pr-hygiene` do, on Linux and macOS alike. `tests/test_workflows_valid.py` adds the
checks only a YAML library can make (a strict parse with no duplicate keys) and pins each rule.

Commands:
    check_workflows.py check     exit non-zero on any violation, and list them
    check_workflows.py report    print every YAML file and what the guard reads

Usage:
    python3 scripts/check_workflows.py check
    python3 scripts/check_workflows.py report
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ".github/workflows"
YAML_SUFFIXES = (".yml", ".yaml")
#: Every `${{ ... }}` in a file. GitHub scans the raw text, so a comment inside a `run:` block counts.
EXPRESSION = re.compile(r"\$\{\{(.*?)\}\}", re.S)
#: A top-level YAML key (column zero), used for the `name:` rule without a YAML library.
TOP_LEVEL_KEY = re.compile(r"^([A-Za-z_][\w.-]*):", re.M)

_WS = " \t\r\n"
_OPERATORS = ("==", "!=", "<=", ">=", "&&", "||", "<", ">", "!", "*", "/", "%", "+", "-",
              "(", ")", "[", "]", ",", ".")


class ExpressionError(ValueError):
    """A `${{ ... }}` GitHub's expression parser would refuse."""


def _tokenize(src: str) -> list[str]:
    """The expression's tokens, or ExpressionError on a character GitHub does not allow."""
    out: list[str] = []
    i, n = 0, len(src)
    while i < n:
        ch = src[i]
        if ch in _WS:
            i += 1
            continue
        if ch == "'":                       # a GitHub string literal; '' is an escaped quote
            j = i + 1
            while True:
                j = src.find("'", j)
                if j == -1:
                    raise ExpressionError(f"unterminated string at offset {i}")
                if src[j + 1:j + 2] == "'":
                    j += 2
                    continue
                break
            out.append(src[i:j + 1])
            i = j + 1
            continue
        if ch.isdigit():
            m = re.match(r"\d+(\.\d+)?([eE][+-]?\d+)?", src[i:])
            assert m is not None  # the pattern matches any leading digit
            out.append(m.group(0))
            i += len(m.group(0))
            continue
        if ch.isalpha() or ch == "_":
            m = re.match(r"[A-Za-z_][A-Za-z0-9_-]*", src[i:])
            assert m is not None  # the pattern matches any leading identifier character
            out.append(m.group(0))
            i += len(m.group(0))
            continue
        for op in _OPERATORS:               # longest first, so `==` never reads as two `=`
            if src.startswith(op, i):
                out.append(op)
                i += len(op)
                break
        else:
            raise ExpressionError(f"unexpected token {ch!r} at offset {i}")
    return out


class _Parser:
    """GitHub's expression grammar, precedence climbing, over the token list."""

    def __init__(self, tokens: list[str]):
        self.toks = tokens
        self.i = 0

    def peek(self) -> str | None:
        return self.toks[self.i] if self.i < len(self.toks) else None

    def take(self, tok: str | None = None) -> str:
        got = self.peek()
        if got is None:
            raise ExpressionError("unexpected end of expression")
        if tok is not None and got != tok:
            raise ExpressionError(f"expected {tok!r}, got {got!r}")
        self.i += 1
        return got

    def parse(self) -> None:
        self.or_()
        if self.peek() is not None:
            raise ExpressionError(f"unexpected trailing token {self.peek()!r}")

    def or_(self) -> None:
        self.and_()
        while self.peek() == "||":
            self.take()
            self.and_()

    def and_(self) -> None:
        self.cmp()
        while self.peek() == "&&":
            self.take()
            self.cmp()

    def cmp(self) -> None:
        self.add()
        while self.peek() in ("==", "!=", "<=", ">=", "<", ">"):
            self.take()
            self.add()

    def add(self) -> None:
        self.mul()
        while self.peek() in ("+", "-"):
            self.take()
            self.mul()

    def mul(self) -> None:
        self.unary()
        while self.peek() in ("*", "/", "%"):
            self.take()
            self.unary()

    def unary(self) -> None:
        if self.peek() in ("!", "-"):
            self.take()
            self.unary()
            return
        self.postfix()

    def postfix(self) -> None:
        self.primary()
        while True:
            nxt = self.peek()
            if nxt == ".":
                self.take()
                if self.peek() == "*":      # the object filter, `context.*`
                    self.take()
                else:
                    self.take_ident()
            elif nxt == "[":
                self.take("[")
                self.or_()
                self.take("]")
            elif nxt == "(":                # a function call, e.g. fromJSON(x) / cancelled()
                self.take("(")
                if self.peek() != ")":
                    self.or_()
                    while self.peek() == ",":
                        self.take()
                        self.or_()
                self.take(")")
            else:
                return

    def take_ident(self) -> None:
        got = self.peek()
        if got is None or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", got):
            raise ExpressionError(f"expected a property name, got {got!r}")
        self.take()

    def primary(self) -> None:
        got = self.peek()
        if got is None:
            raise ExpressionError("unexpected end of expression")
        if got == "(":
            self.take("(")
            self.or_()
            self.take(")")
            return
        if got.startswith("'") or got[0].isdigit():
            self.take()
            return
        if got in ("true", "false", "null") or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", got):
            self.take()
            return
        raise ExpressionError(f"unexpected token {got!r}")


def parse_expression(src: str) -> None:
    """Raise ExpressionError unless `src` is an expression GitHub would accept."""
    toks = _tokenize(src)
    if not toks:
        raise ExpressionError("empty expression")
    _Parser(toks).parse()


def _tracked(root: Path) -> list[Path] | None:
    """git's tracked YAML files, or None when `root` is not its own checkout.

    `root/.git` exists in a normal clone AND in a worktree (where it is a file), so a test fixture under
    a temp dir takes the walk path — and a temp dir that happens to sit inside some other repository can
    never be read through that repository's index and silently report nothing.
    """
    if not (root / ".git").exists():
        return None
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files", "*.yml", "*.yaml"],
                             capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return [root / line for line in out.splitlines() if line.strip()]


def yaml_files(root: Path = REPO_ROOT) -> list[Path]:
    """Every YAML file the guard reads: git's tracked list in a checkout, else a filesystem walk."""
    files = _tracked(root)
    if files is None:
        files = [p for p in sorted(root.rglob("*"))
                 if p.is_file() and p.suffix in YAML_SUFFIXES and ".git" not in p.parts]
    return sorted(p for p in files if p.exists() and p.suffix in YAML_SUFFIXES)


def workflow_files(root: Path = REPO_ROOT) -> list[Path]:
    return sorted((root / WORKFLOWS).glob("*.yml"))


def check_expressions(root: Path = REPO_ROOT) -> list[dict]:
    """No YAML file may carry a `${{ ... }}` GitHub's parser would refuse."""
    out: list[dict] = []
    for path in yaml_files(root):
        where = str(path.relative_to(root))
        text = path.read_text()
        for lineno, line in enumerate(text.splitlines(), start=1):
            for m in EXPRESSION.finditer(line):
                inner = m.group(1)
                try:
                    parse_expression(inner)
                except ExpressionError as exc:
                    out.append({
                        "key": f"workflow-expression/{where}:{lineno}",
                        "title": f"ci: {where}:{lineno} carries a `${{{{ ... }}}}` GitHub cannot parse",
                        "evidence": (
                            f"`{where}` line {lineno} contains `{m.group(0).strip()}`, and its "
                            f"expression cannot be parsed: {exc}. GitHub evaluates every `${{{{ ... }}}}` "
                            f"in the file's raw text — a `#` line inside a `run:` block scalar is script "
                            f"text, NOT a YAML comment — so an unparseable expression makes GitHub REFUSE "
                            f"the whole workflow file. The refusal is silent: the run arrives with 0 jobs, "
                            f"`conclusion=failure`, a `name` equal to the file path and no log (issue #330, "
                            f"measured on engine-bump-rebase.yml: four such runs on `main`)."
                        ),
                        "where": where,
                    })
    return out


def check_newlines(root: Path = REPO_ROOT) -> list[dict]:
    """Every YAML file ends with a newline — the repository's linefeed lint spec."""
    out: list[dict] = []
    for path in yaml_files(root):
        raw = path.read_bytes()
        if raw and not raw.endswith(b"\n"):
            where = str(path.relative_to(root))
            out.append({
                "key": f"workflow-newline/{where}",
                "title": f"ci: {where} does not end with a newline",
                "evidence": (
                    f"`{where}` ends without a trailing newline. `make lint` requires one on every tracked "
                    f"text file, and a file that fails it does not survive the lint stage."
                ),
                "where": where,
            })
    return out


def check_workflow_names(root: Path = REPO_ROOT) -> list[dict]:
    """Every workflow declares a top-level `name:`, so a failed run names a workflow, not a path."""
    out: list[dict] = []
    for path in workflow_files(root):
        if re.search(r"^name:", path.read_text(), re.M):
            continue
        where = str(path.relative_to(root))
        out.append({
            "key": f"workflow-name/{where}",
            "title": f"ci: {where} declares no top-level `name:`",
            "evidence": (
                f"`{where}` has no top-level `name:`. GitHub then labels its runs with the file PATH, which "
                f"is the same thing a startup failure looks like — so a rejected file and an unnamed one "
                f"are indistinguishable in `gh run list`, and the yellow Actions list stops describing the "
                f"work (issue #276 asks for the same thing for dispatchable workflows)."
            ),
            "where": where,
        })
    return out


def findings(root: Path = REPO_ROOT) -> list[dict]:
    return check_expressions(root) + check_newlines(root) + check_workflow_names(root)


def render(items: list[dict]) -> str:
    if not items:
        return "[workflows] OK: every YAML file parses, ends with a newline, and names its workflow"
    lines = [f"[workflows] {len(items)} violation(s)"]
    for f in items:
        lines += ["", f"- {f['title']}", f"  where: {f['where']}", f"  {f['evidence']}"]
    return "\n".join(lines)


def report(root: Path = REPO_ROOT) -> str:
    """Every YAML file the guard reads, how many expressions it validated, and the verdict."""
    files = yaml_files(root)
    total = sum(len(EXPRESSION.findall(p.read_text())) for p in files)
    lines = [
        f"[workflows] {len(files)} YAML file(s), {total} `${{{{ ... }}}}` expression(s) validated, "
        f"{len(workflow_files(root))} workflow file(s)",
        "[workflows] rule: every expression parses; every file ends with a newline; every workflow "
        "declares a top-level `name:`",
    ]
    for f in findings(root):
        lines += ["", f"- {f['title']}", f"  where: {f['where']}"]
    lines += ["", render(findings(root))]
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="check_workflows", description=__doc__)
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
