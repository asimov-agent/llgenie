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
#: YAML that GitHub never reads as a workflow: the vendored Semgrep rule pack (issue #1284). Its
#: rule set is third-party detection data — one entry's pattern is literally a `${{ github.event... }}`
#: GitHub-actions rule — which the JSON-expression parser here rejects even though the file is NEVER
#: fed to GitHub's workflow engine (it is a scanner rules snapshot, read only by the semgrep binary).
#: The carve is path-scoped to that one data file; every actual workflow/YAML still gets the parse.
VENDORED_PATHS: tuple[str, ...] = (
    "containers/scanners/semgrep/rules/default.yml",
)
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
#: A `workflow_dispatch` trigger key, at any indentation (never inside a `run:` block).
DISPATCH_KEY = re.compile(r"^(?P<indent>[ \t]*)workflow_dispatch:\s*$")
#: A top-level trigger key under `on:` — a schedule, a `workflow_run`, a push, a PR event …
ON_TRIGGER_KEY = re.compile(r"^(?P<indent>[ \t]*)([A-Za-z_][\w-]*?):\s*(#.*)?$")
#: Workflows that must be MANUAL-ONLY (owner directive 2026-11-08, #2293): a red PR is no longer an
#: automatic issue factory, so the run-failure-reactor and the fix-bot may start only on a human
#: `workflow_dispatch`. Re-adding ANY other trigger to either file is the exact regression this rule
#: exists to refuse.
MANUAL_ONLY_WORKFLOWS = ("run-failure-reactor.yml", "fix-bot.yml")
#: Workflows a `workflow_run` consumer deliberately does NOT watch (#349). An entry is a dated decision
#: with a `reason`, never a literal in this guard: exempting a workflow takes an edit here that says
#: why, and an entry naming no workflow (the workflow was renamed or deleted) is reported STALE so the
#: roster cannot rot. Same shape as `tests/fixtures/host-only-wiring.json` (#237) and
#: `tests/fixtures/docs-exceptions.json` (#257).
EXEMPTIONS = "tests/fixtures/workflow-run-exemptions.json"

#: The composite action that OWNS the ordered agent-leg preflight (issue #798): JEV #238,
#: shell-keys #358, routing-smoke #407 and the REDACTED-transcript upload #359. A bot leg calls
#: this instead of inlining those make invocations, so a fix to any one reaches every leg.
AGENT_LEG_ACTION = ".github/actions/agent-leg/action.yml"
#: The two inline `make` invocations that together spell the agent-leg preflight. A workflow whose
#: steps inline BOTH (instead of calling `AGENT_LEG_ACTION`) has re-introduced the six-copy drift
#: #798 exists to end. A single one alone is a different control (engine-bump's non-blocking JEV
#: report, search-smoke / issue-dedupe's lone shell-keys proof) and is not the preflight block.
JEV_PREFLIGHT_INLINE = re.compile(r"make\s+agent-jev-preflight\b")
SHELL_KEYS_INLINE = re.compile(r"make\s+agent-shell-keys-check\b")

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
        out = subprocess.run(["git", "-C", str(root), "ls-files", "*.yml", "*.yaml"],  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
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
    """No YAML file may carry a `${{ ... }}` GitHub's parser would refuse — except the vendored
    Semgrep rule pack, which GitHub never reads as a workflow (issue #1284, `VENDORED_PATHS`)."""
    out: list[dict] = []
    for path in yaml_files(root):
        where = str(path.relative_to(root))
        if where in VENDORED_PATHS:
            continue
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


def _vr():
    """`scripts/verdict_roster.py`, imported lazily — it owns the workflow-file reading this gate shares.

    ONE direction only (`check_workflows -> verdict_roster`): the roster module never imports this
    guard, so `make check-package-layers` sees no cycle, and `scripts/package-layers.json` states the
    `ci_verdict -> verdict_roster` edge.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import verdict_roster  # noqa: PLC0415 - deliberate laziness, see the docstring
    return verdict_roster


def _indented_block(lines: list[str], start: int, indent: int) -> list[str]:
    return _vr().indented_block(lines, start, indent)


def _unquote(value: str) -> str:
    return _vr().unquote(value)


def workflow_names(root: Path = REPO_ROOT) -> dict[str, str]:
    return _vr().workflow_names(root)


def workflow_run_lists(path: Path) -> list[tuple[int, list[str]]]:
    return _vr().workflow_run_lists(path)


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


def _on_triggers(lines: list[str]) -> list[str]:
    """The trigger keys under `on:` (the workflow's *event* surface), read from lines."""

    for i, line in enumerate(lines):
        if re.match(r"^on:", line):
            body = _indented_block(lines, i, 0)
            break
    else:
        return []
    triggers: list[str] = []
    for l in body:
        m = ON_TRIGGER_KEY.match(l)
        if m is None:
            continue
        indent = len(m.group("indent"))
        if indent != 2:                       # only the top-level triggers under `on:`
            continue
        triggers.append(m.group(2))
    return triggers


def check_manual_only(root: Path = REPO_ROOT) -> list[dict]:
    """Every MANUAL_ONLY_WORKFLOWS file may only trigger on `workflow_dispatch` (#2293)."""

    out: list[dict] = []
    for path in workflow_files(root):
        if path.name not in MANUAL_ONLY_WORKFLOWS:
            continue
        tr = _on_triggers(path.read_text().splitlines())
        bad = [t for t in tr if t != "workflow_dispatch"]
        if not bad:
            continue
        where = str(path.relative_to(root))
        out.append({
            "key": f"workflow-manual-only/{where}/{'/'.join(bad)}",
            "title": f"ci: {where} re-gained a non-dispatch trigger: {', '.join(bad)}",
            "evidence": (
                f"`{where}` carries {', '.join('`' + t + '`' for t in bad)} in its `on:` block. "
                f"Owner directive 2026-11-08 (#2293): the run-failure-reactor and the fix-bot are "
                f"MANUAL-ONLY — a red PR is surfaced to a human, not auto-filed or auto-repaired — so "
                f"only `workflow_dispatch` may trigger them. Remove `{', '.join(bad)}`."
            ),
            "where": where,
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


def check_scheduled_job_timeouts(root: Path = REPO_ROOT) -> list[dict]:
    """Every job of a schedule-triggered workflow declares a `timeout-minutes` (issue #2317).

    A scheduled engine/registry maintenance job with no ceiling inherits GitHub's
    360-minute default, so a hang is invisible for six hours and blocks the whole
    scheduled slot behind the workflow's concurrency group. The engine-build and
    pipeline timeout-bounds tests (test_engine_build_timeouts.py,
    test_pipeline_timeouts.py) cover the build/run paths; this rule nets the
    `on.schedule` workflows the maintenance spider relies on. A `uses:` caller
    cannot carry a ceiling (GitHub rejects the file, #882), so only jobs that run
    steps are checked.
    """
    out: list[dict] = []
    for path in workflow_files(root):
        where = str(path.relative_to(root))
        lines = path.read_text().splitlines()
        if "schedule" not in _on_triggers(lines):
            continue
        found = _jobs_block(lines)
        if found is None:
            continue                        # no `jobs:` at all is another check's finding
        start, body = found
        job_starts = [i for i, line in enumerate(body)
                      if re.match(r"^ {2}[A-Za-z0-9_-]+:\s*(#.*)?$", line)]
        for n, idx in enumerate(job_starts):
            name = body[idx].strip().rstrip(":").strip()
            chunk = body[idx + 1:job_starts[n + 1] if n + 1 < len(job_starts) else len(body)]
            text = "\n".join(chunk)
            if re.search(r"^ {4}uses:", text, re.M):
                continue                    # a `uses:` job cannot hold a ceiling (issue #882)
            if re.search(r"^ {4}timeout-minutes:", text, re.M):
                continue
            out.append({
                "key": f"workflow-scheduled-timeout/{where}#{name}",
                "title": f"ci: {where} scheduled job `{name}` declares no `timeout-minutes`",
                "evidence": (
                    f"`{where}` runs on `schedule` and its `{name}` job has no `timeout-minutes`, so a "
                    f"hang inherits GitHub's 360-minute default and is invisible for six hours — and it "
                    f"blocks the workflow's concurrency group behind a zombie (issue #2317). Give the job "
                    f"a bounded ceiling, as the engine-build (#1865) and pipeline (#846) paths already "
                    f"require."
                ),
                "where": where,
            })
    return out


def check_inline_agent_preflight(root: Path = REPO_ROOT) -> list[dict]:
    """A bot workflow that inlines BOTH agent-leg preflight `make` calls is a regression (#798).

    The ordered preflight — `make agent-jev-preflight` (#238) and
    `make agent-shell-keys-check` (#358) — MUST live in ONE place,
    `.github/actions/agent-leg/action.yml`, and every agent leg calls it. A workflow whose
    steps inline BOTH spellings re-introduces the six-copy drift #798 exists to end: a fix to
    a preflight stops reaching every leg, and a leg that misses one runs unattended without
    its JEV check or its credentials proven visible.

    A single one of the two is a DIFFERENT control and is not reddened: engine-bump.yml's JEV
    call is a non-blocking availability report, and search-smoke.yml / issue-dedupe.yml's lone
    shell-keys call is that single-key proof. The block is the pair.
    """
    out: list[dict] = []
    for path in workflow_files(root):
        text = path.read_text()
        has_jev = JEV_PREFLIGHT_INLINE.search(text) is not None
        has_keys = SHELL_KEYS_INLINE.search(text) is not None
        if not (has_jev and has_keys):
            continue
        where = str(path.relative_to(root))
        out.append({
            "key": f"workflow-inline-agent-leg/{where}",
            "title": f"ci: {where} inlines the agent-leg preflight instead of calling "
                     f"`{AGENT_LEG_ACTION}`",
            "evidence": (
                f"`{where}` carries both `make agent-jev-preflight` and "
                f"`make agent-shell-keys-check` in its steps. The ordered agent-leg preflight "
                f"lives in ONE place — `{AGENT_LEG_ACTION}` (issues #238/#358/#407/#359, "
                f"#798) — so a fix reaches every leg by construction. Inlining it here is a "
                f"regression: call `uses: ./.github/actions/agent-leg` with "
                f"`phase: preflight` (and `phase: upload` for the transcript) instead."
            ),
            "where": where,
        })
    return out


def check_verdict_roster(root: Path = REPO_ROOT) -> list[dict]:
    """Every workflow that can post a check-run at a PR head must carry a judgement decision (#2116).

    `ci-verdict.yml`'s `workflow_run.workflows:` roster is matched VERBATIM against a `name:` (no
    wildcard), so a `pull_request` workflow it does not list puts a check-run on the head that the
    verdict never reads — while `auto_merge.py` refuses the merge on any red one. The comparison is
    `scripts/verdict_roster.py`'s (a SUBSET check, never equality: the workflow set grows by design).
    """
    return _vr().coverage(root)


def findings(root: Path = REPO_ROOT) -> list[dict]:
    return (check_expressions(root) + check_newlines(root) + check_workflow_names(root)
            + check_workflow_run_refs(root) + check_workflow_run_coverage(root)
            + check_manual_only(root)
            + check_uses_job_keys(root) + check_scheduled_job_timeouts(root)
            + check_inline_agent_preflight(root)
            + check_verdict_roster(root))


def render(items: list[dict]) -> str:
    if not items:
        return ("[workflows] OK: every YAML file parses, ends with a newline, names its workflow, "
                "every `workflow_run` names the workflows it reacts to, every workflow's "
                "completion is routed to a consumer, every manual-only workflow is dispatch-only "
                "(#2293), every `pull_request` workflow carries a "
                "judgement decision the verdict can name, no `uses:` job carries a job-level "
                "key GitHub rejects at load time, every job of a schedule-triggered workflow "
                "declares a `timeout-minutes` ceiling (#2317), and no agent leg inlines the "
                "agent-leg preflight instead of calling the reusable composite action (#798)")
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
