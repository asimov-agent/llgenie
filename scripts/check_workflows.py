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
                         startup failure present itself as a path instead of a workflow;
* `workflow-run-refs`    an `on.workflow_run` trigger with no `workflows:` list. GitHub REQUIRES the
                         list and REFUSES the whole file without it (`on.workflow_run` does not
                         reference any workflows), silently: 0 jobs, `conclusion=failure`, `name`
                         = the file path, no log. Measured on run-failure-reactor.yml, whose two
                         push runs (`38881240747`, `38881791437`) were refused exactly that way while
                         this guard passed — the gap this rule closes.

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
import json
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
#: An `on.workflow_run:` trigger, at any indentation (never a `run:` block's script text).
WORKFLOW_RUN_KEY = re.compile(r"^(?P<indent>[ \t]*)workflow_run:\s*(?P<rest>.*)$")
#: The `workflows:` list a `workflow_run` trigger must carry to be read at all.
WORKFLOWS_KEY = re.compile(r"^(?P<indent>[ \t]*)workflows:\s*(?P<rest>.*)$")
#: A top-level `name:` value, quoted or bare — the string GitHub matches `workflow_run.workflows` on.
NAME_KEY = re.compile(r"^name:\s*(?P<value>.+?)\s*$", re.M)
#: Workflows a `workflow_run` consumer deliberately does NOT watch (#349). An entry is a dated decision
#: with a `reason`, never a literal in this guard: exempting a workflow takes an edit here that says
#: why, and an entry naming no workflow (the workflow was renamed or deleted) is reported STALE so the
#: roster cannot rot. Same shape as `tests/fixtures/host-only-wiring.json` (#237) and
#: `tests/fixtures/docs-exceptions.json` (#257).
EXEMPTIONS = "tests/fixtures/workflow-run-exemptions.json"

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


def _indented_block(lines: list[str], start: int, indent: int) -> list[str]:
    """The lines a mapping key at `indent` owns: deeper-indented, up to the next peer.

    Blank lines and comments are skipped rather than read as a dedent, so a commented `workflows:`
    never counts and an interleaved blank line never truncates the block early.
    """
    out: list[str] = []
    for line in lines[start + 1:]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if len(line) - len(line.lstrip(" \t")) <= indent:
            break
        out.append(line)
    return out


def check_workflow_run_refs(root: Path = REPO_ROOT) -> list[dict]:
    """An `on.workflow_run` trigger must carry a `workflows:` list, or GitHub refuses the file."""
    out: list[dict] = []
    for path in workflow_files(root):
        where = str(path.relative_to(root))
        lines = path.read_text().splitlines()
        for i, line in enumerate(lines):
            m = WORKFLOW_RUN_KEY.match(line)
            if m is None:
                continue
            body = _indented_block(lines, i, len(m.group("indent")))
            if any(WORKFLOWS_KEY.match(b) for b in body):
                continue
            out.append({
                "key": f"workflow-run-refs/{where}:{i + 1}",
                "title": f"ci: {where}:{i + 1} declares `workflow_run` with no `workflows:` list",
                "evidence": (
                    f"`{where}` line {i + 1} declares `on.workflow_run` without a `workflows:` list. "
                    f"GitHub requires one and REFUSES the whole file without it — the run page says "
                    f"`Invalid workflow file: `on.workflow_run` does not reference any workflows` — and "
                    f"the refusal is silent: the run arrives with 0 jobs, `conclusion=failure`, a `name` "
                    f"equal to the file path and no log (the #330 signature). Measured on "
                    f"run-failure-reactor.yml, whose two push runs were refused that way while this "
                    f"guard passed. Name every workflow this repo owns, and never the file itself — a "
                    f"self-reference would make the trigger re-fire on its own completion."
                ),
                "where": where,
            })
    return out


def _unquote(value: str) -> str:
    """A YAML scalar's value: GitHub matches the DECODED string, so quotes never count."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def workflow_names(root: Path = REPO_ROOT) -> dict[str, str]:
    """Every workflow's top-level `name:` -> its file name. The roster is matched against these."""
    out: dict[str, str] = {}
    for path in workflow_files(root):
        m = NAME_KEY.search(path.read_text())
        if m is not None:
            out[_unquote(m.group("value"))] = path.name
    return out


def workflow_run_lists(path: Path) -> list[tuple[int, list[str]]]:
    """Each `workflow_run.workflows:` list in a file: (line number of the key, the names it lists).

    Both shapes GitHub accepts are read: the block form (`- name` per line, this repo's) and the inline
    form (`[CI, pipeline]`). A name is returned exactly as it is written minus YAML quoting, because
    that is what GitHub compares against each workflow's `name:` — no globbing, no fuzzy match.
    """
    lines = path.read_text().splitlines()
    out: list[tuple[int, list[str]]] = []
    for i, line in enumerate(lines):
        m = WORKFLOW_RUN_KEY.match(line)
        if m is None:
            continue
        body = _indented_block(lines, i, len(m.group("indent")))
        for j, item in enumerate(body):
            w = WORKFLOWS_KEY.match(item)
            if w is None:
                continue
            rest = w.group("rest").strip()
            if rest.startswith("["):
                out.append((i + 1, [_unquote(x) for x in rest.strip("[]").split(",") if x.strip()]))
                continue
            names = []
            for entry in _indented_block(body, j, len(w.group("indent"))):
                if entry.strip().startswith("-"):
                    names.append(_unquote(entry.split("-", 1)[1]))
            out.append((i + 1, names))
    return out


def _exemptions(root: Path = REPO_ROOT) -> dict[str, dict]:
    """The dated decisions that exempt a workflow from being watched, keyed by its `name:`."""
    path = root / EXEMPTIONS
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return data.get("workflows") or {}


def check_workflow_run_coverage(root: Path = REPO_ROOT) -> list[dict]:
    """Every workflow's completion is routed somewhere, and every name in a roster exists (#349).

    GitHub matches `workflow_run.workflows` against a workflow's top-level `name:` and takes no
    wildcard, so the list is a roster a human keeps by hand. It rots two ways, both silent until this
    rule existed: a workflow added later is never watched, and a workflow whose `name:` is edited stops
    matching — measured on `rebase-bot.yml`, renamed by #463 (`…ONE PR per run…` -> `…every eligible PR
    per run…`), after which its failures routed nowhere while the roster still carried the old string.
    So: (a) a listed name that matches no workflow is a violation, (b) a workflow no roster names is a
    violation unless an exemption with a reason covers it, (c) a workflow may not name itself (the
    trigger would re-fire on its own completion), and (d) an exemption without a reason or naming no
    workflow is a violation, so the exemption file cannot rot either.
    """
    out: list[dict] = []
    names = workflow_names(root)
    known = set(names)
    covered: set[str] = set()
    declared_any = False
    for path in workflow_files(root):
        where = str(path.relative_to(root))
        own = next((n for n, f in names.items() if f == path.name), None)
        for line, listed in workflow_run_lists(path):
            declared_any = True
            for name in listed:
                covered.add(name)
                if name == own:
                    out.append({
                        "key": f"workflow-run-self/{where}:{line}",
                        "title": f"ci: {where}:{line} watches its own completion",
                        "evidence": (
                            f"`{where}` line {line} names itself in its `workflow_run.workflows:` "
                            f"list. The trigger then re-fires on its own completion — a loop, not a "
                            f"route. The reactor's own header records the same rule (#286)."
                        ),
                        "where": where,
                    })
                elif name not in known:
                    out.append({
                        "key": f"workflow-run-unknown-name/{where}:{line}:{name}",
                        "title": f"ci: {where}:{line} watches a workflow that does not exist: {name!r}",
                        "evidence": (
                            f"`{where}` line {line} lists {name!r}, which is no workflow's `name:` in "
                            f"this tree. GitHub matches that list VERBATIM and takes no wildcard, so a "
                            f"renamed workflow's failures become invisible while the roster looks "
                            f"complete — measured on `rebase-bot.yml` after #463, whose failures routed "
                            f"nowhere for a week with this gate green. Fix the entry to the workflow's "
                            f"current `name:`."
                        ),
                        "where": where,
                    })
    if not declared_any:
        return out                          # nothing in this tree consumes runs; nothing to cover
    exempt = _exemptions(root)
    for name, filename in sorted(names.items(), key=lambda kv: kv[1]):
        if name in covered or name in exempt:
            continue
        out.append({
            "key": f"workflow-run-uncovered/{filename}",
            "title": f"ci: no workflow routes {filename}'s failures ({name})",
            "evidence": (
                f"`{filename}` ({name}) completes and no `workflow_run.workflows:` list watches it, so "
                f"a red run of it files nothing and dispatches nothing — the state the run-failure "
                f"reactor exists to end (#286). Add its `name:` to the reactor's roster, or record why "
                f"it is not watched in `{EXEMPTIONS}`."
            ),
            "where": f"{WORKFLOWS}/{filename}",
        })
    for name, decision in sorted(exempt.items()):
        if name not in known:
            out.append({
                "key": f"workflow-run-exemption-stale/{name}",
                "title": f"ci: {EXEMPTIONS} exempts a workflow that does not exist: {name!r}",
                "evidence": (
                    f"`{EXEMPTIONS}` exempts {name!r}, which is no workflow's `name:` in this tree. A "
                    f"stale exemption is how a renamed workflow becomes unwatched a second time; delete "
                    f"the entry or point it at the current `name:`."
                ),
                "where": EXEMPTIONS,
            })
        elif not str((decision or {}).get("reason") or "").strip():
            out.append({
                "key": f"workflow-run-exemption-no-reason/{name}",
                "title": f"ci: {EXEMPTIONS} exempts {name!r} with no reason",
                "evidence": (
                    f"`{EXEMPTIONS}` exempts {name!r} without a `reason`. An omission has to be a dated "
                    f"decision, not an accident: state what the workflow's red is already routed to."
                ),
                "where": EXEMPTIONS,
            })
    return out


def _jobs_block(lines: list[str]) -> "tuple[int, list[str]] | None":
    """The `jobs:` mapping and its indented body, read from lines so no YAML library is required.

    Every gate in this file works without `pyyaml`, because this host has no site-package for it while CI
    runs inside the test image: a check that silently returns nothing when the import fails would pass by
    not looking, which is the very defect it exists to catch.
    """
    for i, line in enumerate(lines):
        if re.match(r"^jobs:", line):
            return i, _indented_block(lines, i, 0)
    return None


def check_uses_job_keys(root: Path = REPO_ROOT) -> list[dict]:
    """A `uses:` job may not carry job-level keys: GitHub rejects the FILE, and no run ever has a job.

    This is the worst shape of defect because it reads green everywhere. `timeout-minutes` on a job that
    calls a reusable workflow makes the workflow fail to LOAD, so the run is `completed/failure` with
    **0 jobs and 0 check-runs**: a rollup aggregating jobs sees nothing to report, `gh pr checks` has no
    row, and no gate that reads conclusions can catch it. Measured on #882 (`b88e0c2`): two `uses:` jobs
    carried `timeout-minutes`, and the only evidence in the whole system was a push run with zero jobs.

    The ceilings belong INSIDE the called workflow's own jobs (`pipeline.yml`), which is also where a hang
    is actually detectable. A file whose `jobs:` block holds no job is reported for the same reason.
    """
    out: list[dict] = []
    #: Keys GitHub refuses on a job that delegates to a reusable workflow.
    forbidden = ("timeout-minutes", "steps", "runs-on", "container", "services", "strategy", "env",
                 "continue-on-error")
    for path in workflow_files(root):
        where = str(path.relative_to(root))
        lines = path.read_text().splitlines()
        found = _jobs_block(lines)
        if found is None:
            continue                        # no `jobs:` at all is another check's finding
        start, body = found
        job_starts = [i for i, line in enumerate(body) if re.match(r"^ {2}[A-Za-z0-9_-]+:\s*(#.*)?$", line)]
        if not job_starts:
            out.append({
                "key": f"workflow-jobs/{where}",
                "title": f"ci: {where} defines no job",
                "evidence": (
                    f"`{where}` has a `jobs:` block with no job under it, so a run of it can never contain "
                    f"a job. A `completed/failure` run with 0 jobs is what a rejected workflow looks like "
                    f"from the inside, and no rollup can see it (issue #882)."
                ),
                "where": where,
            })
            continue
        for n, idx in enumerate(job_starts):
            name = body[idx].strip().rstrip(":").strip()
            chunk = body[idx + 1:job_starts[n + 1] if n + 1 < len(job_starts) else len(body)]
            text = "\n".join(chunk)
            if not re.search(r"^ {4}uses:", text, re.M):
                continue
            bad = [key for key in forbidden if re.search(rf"^ {{4}}{re.escape(key)}:", text, re.M)]
            if not bad:
                continue
            out.append({
                "key": f"uses-job-key/{where}#{name}",
                "title": f"ci: {where} job `{name}` calls a reusable workflow and carries "
                         + ", ".join(f"`{k}`" for k in bad),
                "evidence": (
                    f"`{name}` has both `uses:` and " + ", ".join(f"`{k}`" for k in bad) + ". GitHub rejects "
                    f"the workflow at LOAD time: the run is `completed/failure` with 0 jobs and 0 check-runs, "
                    f"so every rollup reads `fail=0` and the PR looks clean while it cannot run at all. Put "
                    f"the ceiling on the jobs INSIDE the called workflow (e.g. `pipeline.yml`), or pass an "
                    f"input the called workflow declares (issue #882)."
                ),
                "where": where,
            })
    return out


def findings(root: Path = REPO_ROOT) -> list[dict]:
    return (check_expressions(root) + check_newlines(root) + check_workflow_names(root)
            + check_workflow_run_refs(root) + check_workflow_run_coverage(root)
            + check_uses_job_keys(root))


def render(items: list[dict]) -> str:
    if not items:
        return ("[workflows] OK: every YAML file parses, ends with a newline, names its workflow, "
                "every `workflow_run` names the workflows it reacts to, every workflow's "
                "completion is routed to a consumer, and no `uses:` job carries a job-level "
                "key GitHub rejects at load time")
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
        "declares a top-level `name:`; every `workflow_run` trigger names the workflows it reacts to",
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
