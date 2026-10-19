#!/usr/bin/env python3
"""No secret VALUE may reach a log, a summary or a process list — for every key, not just one.

The JEV preflight has its own redaction and its own tests (issue #238). Every other key this repo
uses travels the same way: a CI secret, `docker run -e VAR` (the NAME, never `VAR=value`), and a
guard that echoes only the name when it is missing. That convention is easy to break in one line —
`echo "$HF_TOKEN"`, a `set -x` in a script that reads a key, `${{ secrets.X }}` interpolated into a
`run:` block instead of an `env:` — and nothing caught it.

What the rule is really about:

* **GitHub masks a registered secret in its own logs, and that is not enough.** Masking is a filter
  over the log stream, not a property of the code: a value that is transformed (base64, a URL, a
  slice) sails past it, and nothing is masked in a log the job uploads itself.
* **A value on a command line is public to the machine.** `docker run -e KEY=$KEY` puts it in `ps`
  and in any `--debug` output, for every user of that host.

Checks (each one is a rule with a name, so a failure says what to do):

    secrets-in-run-block   `${{ secrets.X }}` — or GitHub's own `${{ github.token }}` /
                           `${{ github['token'] }}` — interpolated inside a `run:` block: it becomes
                           part of the script text and of its output — pass it through `env:` instead
    prints-secret-value    a printing command that expands a secret-shaped variable's value
                           (`echo "$HF_TOKEN"`, `printf '%s' "$NOUS_API_KEY"`)
    xtrace-with-secrets    `set -x` in a file that also reads a secret: xtrace prints every expansion
    value-in-argv          `-e VAR=$VAR` / `--build-arg VAR=$VAR` / `-e VAR=${{ … }}`: the value
                           lands in the process list, not only in the environment
    env-dump               a bare `env` / `printenv` whose output reaches a log
    key-shaped-literal     something that looks like a real credential, committed
    whole-stdout-into-output-file
                           a command's WHOLE stdout redirected into `$GITHUB_OUTPUT` (a pipeline, or a
                           `$(…)` substitution, ending in `>> "$GITHUB_OUTPUT"`): the file must hold
                           `key=value` only — `make` echoes its recipe line, which is enough to fail
                           the step with `Invalid format` and throw away the work behind it, and every
                           byte a target prints lands in the output file (issue #361)
    whole-stdout-into-log  a command piped into `tee /dev/stderr`: the same whole stream copied into
                           the job log — GitHub masks registered values only, so a transformed one
                           sails past (issue #361)

Commands:
    check_secret_output.py check     exit non-zero on any violation (the `ci-unit` gate)
    check_secret_output.py report    every file scanned, and the secret-shaped variables it uses

Usage:
    python3 scripts/check_secret_output.py check
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: The variables that carry a credential in this repo (by name — the values never appear here).
SECRET_VARS = (
    "NOUS_API_KEY", "NOUS_PORTAL_API_TOKEN", "GH_TOKEN", "GITHUB_TOKEN", "BUMP_TOKEN",
    "HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "TYPESAFE_API_KEY",
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY",
)
SECRET_ALT = "|".join(SECRET_VARS)

#: A printing command whose output goes to a terminal or a log (a redirect is a file, not output).
PRINTING = re.compile(r"^(?:@|-)?\s*(?:echo|printf|say|warn|annotate|print|sys\.stdout\.write|"
                      r"logger(?:\.\w+)?)\b")
#: The value of a secret-shaped variable, however it is spelled.
SECRET_VALUE = re.compile(rf"\$\{{?(?:{SECRET_ALT})\b")
#: Concatenated / embedded in a bigger expansion (`${KEY:-}`, `"prefix$VAR"`).
SECRET_EXPANSION = re.compile(rf"\$\{{?(?:{SECRET_ALT})(?::[-][^}}]*)?\}}?")
#: A value handed over on a command line instead of through the environment.
VALUE_IN_ARGV = re.compile(rf"(?:-e|--env|--build-arg)\s+(?:{SECRET_ALT})=\S")
#: Anything that looks like a live credential (second alarm). The BODY must be a bare alphanumeric
#: run: a real token has no `_` or `-` after its prefix, while the fixtures this repo writes look
#: like names (`hf_get_wrapped`, `hf_download_stall`) or carry separators
#: (`jev-NEVER-PRINT-THIS-…`) — measured against the 13 hits the loose pattern produced, all of
#: which were fixture names. A deliberate test value can still be committed: mark its file with
#: `# secret-output: test value` and the check accepts it there, visibly.
KEY_SHAPED = re.compile(r"(?:hf_|sk-|sk_|jev-)[A-Za-z0-9]{20,}")
#: The marker that declares deliberate, non-live credential shapes in a file (tests do this).
TEST_VALUE_MARKER = "secret-output: test value"
#: `set -x` (or `set -ex`, `set -eux`) at the START of a command — xtrace prints every expansion.
#: Anchored to a command position on purpose: the word inside a quoted `echo "… runs under set -x"`
#: is documentation, and a rule that fires on its own help text gets muted (measured).
XTRACE = re.compile(r"^\s*(?:@|-)?\s*set\s+-[a-z]*x\b")
#: A bare environment dump.
ENV_DUMP = re.compile(r"(?:^|[|;&(]\s*)(?:sudo\s+)?(?:env|printenv)\s*(?:$|[|>])")
#: A redirect to a FILE (`> path`, `>> path`), which is where a key IS allowed to live
#: (`printf '%s=%s\n' "$KEY_VAR" "$key" >> "${HERMES_HOME}/.env"`). `2>&1` is not a file.
FILE_REDIRECT = re.compile(r">>?\s*['\"]?[^\s|&>]+")
#: `${{ secrets.X }}` (any name) sitting inside a `run:` block.
RUN_SECRET_EXPR = re.compile(r"\$\{\{\s*secrets\.([A-Za-z0-9_]+)")
#: GitHub's OWN credential: `${{ github.token }}` and the bracketed `${{ github['token'] }}` are the
#: same secret as `secrets.GITHUB_TOKEN`, and interpolating one into a `run:` block leaks it the same
#: way — the script text, `ps`, any `--debug` output. The rule matches both sources (issue #361).
RUN_GITHUB_TOKEN = re.compile(r"\$\{\{\s*github\s*(?:\.\s*token\b|\[\s*['\"]token['\"]\s*\])")

#: A pipeline whose last stage redirects into Actions' OUTPUT FILE: the file then holds a command's
#: WHOLE stdout instead of `key=value` — `make` echoing its recipe line is enough to kill the step
#: (issue #346's class) and every line a target prints lands in the output file. The redirect must be
#: OUTSIDE a command substitution: `echo "k=$(cmd | sed …)" >> "$GITHUB_OUTPUT"` prints one computed
#: LITERAL, which is the safe shape. The pipe must be a SINGLE one: llgenie's workflows use `a || b`
#: shell-or chains that end in `>> "$GITHUB_OUTPUT"`, and a loose `|` matched those (measured).
PIPE_INTO_OUTPUT = re.compile(r"(?<!\|)\|(?!\|)[^|]*?(>>\s*['\"]?\$GITHUB_OUTPUT)")
#: The same whole-stdout problem through a command SUBSTITUTION (`$(make x) >> "$GITHUB_OUTPUT"`).
SUBST_INTO_OUTPUT = re.compile(r"\$\([^)]*\)\s*>>\s*['\"]?\$GITHUB_OUTPUT")
#: `… | tee /dev/stderr` (or `/dev/stdout`): copies the whole stream into the job LOG. GitHub masks
#: the values it knows, so a transformed one (base64, a URL, a slice) sails past.
TEE_TO_LOG = re.compile(r"\|\s*tee\s+(?:-a\s+)?['\"]?/dev/std(?:err|out)\b")

def _inside_dquotes(line: str, pos: int) -> bool:
    """True when `pos` sits inside a `"…"` string — the discriminator between the two shapes that
    both contain a pipe and `>> $GITHUB_OUTPUT`:

        echo "k=$(cmd | sed …)" >> "$GITHUB_OUTPUT"     pipe INSIDE the quoted argument
                                                        -> one computed literal, SAFE
        cmd | tee /dev/stderr >> "$GITHUB_OUTPUT"       pipe at top level
                                                        -> the whole stream, UNSAFE
    """
    in_q = False
    for i in range(pos):
        c = line[i]
        if c == '"' and (i == 0 or line[i - 1] != "\\"):
            in_q = not in_q
    return in_q


SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".pytest_cache"}
#: Files that legitimately CONTAIN the patterns (this guard and its tests) — the only exemption,
#: because a check that exempts the things it checks is not a check.
SELF_EXEMPT = {"scripts/check_secret_output.py", "tests/test_secret_output.py"}


def tracked_files(root: Path = REPO_ROOT) -> list[Path]:
    """Every text file a reviewer would call part of the repo."""
    out: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in (".sh", ".py", ".yml", ".yaml", ".mk", ".bash", ".zsh"):
            if path.name != "Makefile":
                continue
        out.append(path)
    return out


def _run_blocks(text: str) -> list[tuple[int, str]]:
    """(line number, line) for the lines inside a workflow `run:` block (scalar or `|`)."""
    lines = text.splitlines()
    out: list[tuple[int, str]] = []
    block_indent: int | None = None
    for n, line in enumerate(lines, 1):
        s = line.strip()
        if re.match(r"^(?:- )?run:\s*[|>]?\s*$", s):
            block_indent = len(line) - len(line.lstrip())
            continue
        if block_indent is not None:
            if not s:
                continue
            indent = len(line) - len(line.lstrip())
            if indent <= block_indent and not line.lstrip().startswith("run:"):
                block_indent = None
            else:
                out.append((n, line))
    return out


def violations(root: Path = REPO_ROOT) -> list[str]:
    """Every way a secret value could leave the process, with the line that does it."""
    bad: list[str] = []
    for path in tracked_files(root):
        rel = path.relative_to(root).as_posix()
        if rel in SELF_EXEMPT:
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        is_workflow = rel.startswith(".github/workflows/")
        lines = text.splitlines()

        if any(XTRACE.search(l) for l in lines) and SECRET_VALUE.search(text):
            line = next(n for n, l in enumerate(lines, 1) if XTRACE.search(l))
            bad.append(f"{rel}:{line}: xtrace-with-secrets — `set -x` in a file that reads a "
                       f"secret prints every expansion; drop the flag or the secret")

        if TEST_VALUE_MARKER not in text:
            for m in KEY_SHAPED.finditer(text):
                line = text[:m.start()].count("\n") + 1
                bad.append(f"{rel}:{line}: key-shaped-literal — something that looks like a live "
                           f"credential is committed (shape '{m.group(0)[:6]}…'); a deliberate test "
                           f"value needs '{TEST_VALUE_MARKER}' in the file")

        if is_workflow:
            for n, line in _run_blocks(text):
                for m in RUN_SECRET_EXPR.finditer(line):
                    bad.append(f"{rel}:{n}: secrets-in-run-block — `${{{{ secrets.{m.group(1)} }}}}` "
                               f"inside `run:` becomes script text and output; pass it through `env:`")
                if RUN_GITHUB_TOKEN.search(line):
                    bad.append(f"{rel}:{n}: secrets-in-run-block — `${{{{ github.token }}}}` inside "
                               f"`run:` is the same credential as `secrets.GITHUB_TOKEN`, and it "
                               f"leaks the same way; pass it through `env:`")

        for n, line in enumerate(lines, 1):
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if PRINTING.match(s) and SECRET_EXPANSION.search(s) and not FILE_REDIRECT.search(s):
                bad.append(f"{rel}:{n}: prints-secret-value — a printing command expands a secret's "
                           f"value: {s[:80]}")
            if VALUE_IN_ARGV.search(s):
                bad.append(f"{rel}:{n}: value-in-argv — the value is on the command line (visible in "
                           f"`ps`), not only in the environment: {s[:80]}")
            if ENV_DUMP.search(s) and not s.startswith("#"):
                bad.append(f"{rel}:{n}: env-dump — a bare environment dump reaches the log: {s[:80]}")
            if TEE_TO_LOG.search(s):
                bad.append(f"{rel}:{n}: whole-stdout-into-log — a command's whole stdout reaches the "
                           f"job log (`tee /dev/stderr`); GitHub masks registered values only, so a "
                           f"transformed one leaks. Print the parsed fields instead: {s[:80]}")
            m = PIPE_INTO_OUTPUT.search(s)
            if (m and not _inside_dquotes(s, m.start())) or SUBST_INTO_OUTPUT.search(s):
                bad.append(f"{rel}:{n}: whole-stdout-into-output-file — a command's whole stdout is "
                           f"redirected into $GITHUB_OUTPUT; write the parsed `key=value` fields only "
                           f"(`make` echoes its recipe line, which is not key=value): {s[:80]}")
    return bad


def report(root: Path = REPO_ROOT) -> list[dict]:
    """What each file does with a secret-shaped variable (for a maintainer reading, not a gate)."""
    rows = []
    for path in tracked_files(root):
        rel = path.relative_to(root).as_posix()
        if rel in SELF_EXEMPT:
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        named = sorted({m for m in re.findall(rf"\b({SECRET_ALT})\b", text)})
        if named:
            rows.append({"file": rel, "names": named,
                         "prints": bool(PRINTING.search(text) and SECRET_EXPANSION.search(text)),
                         "xtrace": bool(XTRACE.search(text))})
    return rows


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="check_secret_output", description=__doc__)
    p.add_argument("cmd", choices=("check", "report"))
    p.add_argument("--root", default=str(REPO_ROOT))
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    root = Path(args.root)

    if args.cmd == "report":
        rows = report(root)
        if args.json:
            print(json.dumps(rows, indent=2))
        else:
            print(f"{len(rows)} file(s) name a secret-shaped variable:")
            for r in rows:
                flags = "".join("!" if r["prints"] else ".", )
                print(f"  {flags} {r['file']} — {', '.join(r['names'])}")
        return 0

    bad = violations(root)
    if bad:
        print(f"[check-secret-output] {len(bad)} violation(s):", file=sys.stderr)
        for b in bad:
            print(f"  - {b}", file=sys.stderr)
        return 1
    print(f"[check-secret-output] OK: {len(tracked_files(root))} file(s) scanned — no secret VALUE "
          f"is printed, passed on a command line, receiver of an xtrace, dumped, or committed; "
          f"secret-shaped names: {', '.join(SECRET_VARS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
