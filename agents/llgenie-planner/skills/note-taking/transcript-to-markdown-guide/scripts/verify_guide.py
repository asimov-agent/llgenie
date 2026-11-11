#!/usr/bin/env python3
"""Verification for generated transcript guide(s): structure + code-block syntax.

    python3 scripts/verify_guide.py <guide.md> [more.md ...] [--min-sections N]

Three check classes, all offline, none of which executes anything the guide
contains:

  structure  h1 title, >= --min-sections `##` headings, balanced fences, every
             `](#anchor)` TOC link resolvable and every heading present in the
             TOC, every table rectangular.
  syntax     ```bash/```sh blocks parse with `bash -n`; ```json parses with
             json.loads; ```yaml parses with yaml.safe_load (WARN, not FAIL,
             when pyyaml is missing — `pip install pyyaml` into the same
             interpreter fixes it).
  pasteable  unquoted `<placeholder>` inside a bash block is a shell input
             redirection, not a placeholder: `kubectl logs <pod> | head` is a
             syntax error for whoever pastes it. Reported as a WARN with the
             fix (`"<pod>"`). Placeholders containing spaces (`<CNI manifest>`)
             are the same bug and only surface as a bare `bash -n` failure, so
             the pattern matches any `<...>` token, not just a single word.

Two traps this file exists to get right, both of which produce false failures
in a hand-rolled checker:

  * an escaped pipe `\\|` inside a table cell is content, not a column
    separator — count cells with split_unescaped(), never line.count('|').
  * the TOC slug keeps the space a stripped character leaves behind, so an
    em-dash heading slugs to a DOUBLE hyphen (`step-1--user-generates...`).
    Do not collapse runs of hyphens; GitHub does not.

Exit 1 on any hard failure, 0 otherwise. Warnings never fail the run.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

BLOCK = re.compile(r"^```([A-Za-z0-9_-]*)\n(.*?)^```$", re.M | re.S)
PLACEHOLDER = re.compile(r"(?<![\"'<\w])<([^<>\n]{1,40})>(?![\"'\w])")


def slug(heading: str) -> str:
    """GitHub-ish: lowercase, drop everything but [a-z0-9 -], spaces to hyphens.

    A stripped character leaves its surrounding spaces behind, so an em dash
    yields two hyphens. Runs are NOT collapsed on purpose.
    """
    return re.sub(r"[^a-z0-9 \-]", "", heading.lower()).replace(" ", "-")


def split_unescaped(line: str) -> list[str]:
    cells, cur, i = [], "", 0
    while i < len(line):
        if line[i] == "\\" and i + 1 < len(line) and line[i + 1] == "|":
            cur += "\\|"
            i += 2
            continue
        if line[i] == "|":
            cells.append(cur)
            cur = ""
        else:
            cur += line[i]
        i += 1
    cells.append(cur)
    return cells


def quote_mask(line: str) -> list[bool]:
    """Per character: True when inside a quote or a ${...} expansion."""
    mask: list[bool] = []
    sq = dq = False
    depth = 0
    i = 0
    while i < len(line):
        c = line[i]
        if c == "\\" and i + 1 < len(line):
            mask.extend([sq or dq, sq or dq])
            i += 2
            continue
        if c == "'" and not dq:
            sq = not sq
        elif c == '"' and not sq:
            dq = not dq
        elif c == "$" and i + 1 < len(line) and line[i + 1] == "{" and not sq:
            depth += 1
        elif c == "}" and depth:
            depth -= 1
        mask.append(sq or dq or depth > 0)
        i += 1
    return mask


def bash_n(body: str) -> tuple[int, str]:
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as handle:
        handle.write(body)
        path = handle.name
    try:
        proc = subprocess.run(["bash", "-n", path], capture_output=True, text=True)  # proc-allow: vendored skill script folded live->tree (issue #2262 fold parity; not a bot-lane runner)
    finally:
        Path(path).unlink(missing_ok=True)
    return proc.returncode, proc.stderr


def check_file(path: Path, minimum: int) -> tuple[list[str], list[str], dict[str, int]]:
    failures: list[str] = []
    warnings: list[str] = []
    stats: dict[str, int] = {}

    if not path.is_file():
        return [f"missing file: {path}"], warnings, stats
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return [f"empty file: {path}"], warnings, stats

    h1 = re.findall(r"^# (.+)$", text, re.M)
    headings = re.findall(r"^## (.+)$", text, re.M)
    fences = re.findall(r"^```", text, re.M)
    tables = re.findall(r"^\|\s*-{2,}", text, re.M)
    stats = {"h1": len(h1), "h2": len(headings), "codeblocks": len(fences) // 2, "tables": len(tables)}

    # ---- structure ----------------------------------------------------
    if not h1:
        failures.append("no `# ` title heading")
    if len(headings) < minimum:
        failures.append(f"only {len(headings)} `##` sections (want >= {minimum})")
    if len(fences) % 2:
        failures.append(f"unbalanced code fences ({len(fences)} ``` markers)")

    anchors = {slug(h) for h in headings}
    links = re.findall(r"\]\(#([^)]+)\)", text)
    unresolved = sorted({link for link in links if link not in anchors})
    if unresolved:
        failures.append("unresolved TOC anchor(s): " + ", ".join(unresolved))
    listed = set(links)
    unlisted = [h for h in headings if slug(h) not in listed and "table of contents" not in h.lower()]
    if unlisted:
        failures.append("heading(s) missing from the TOC: " + "; ".join(unlisted))

    lines = text.split("\n")
    idx = 0
    while idx < len(lines):
        if lines[idx].startswith("|") and idx + 1 < len(lines) and re.match(r"^\|[\s\-:|]+\|$", lines[idx + 1].strip()):
            width = len(split_unescaped(lines[idx]))
            row = idx
            while row < len(lines) and lines[row].startswith("|"):
                if len(split_unescaped(lines[row])) != width:
                    failures.append(
                        f"table row {row + 1} has {len(split_unescaped(lines[row]))} cells, header has {width} "
                        f"— escape a literal pipe as \\|"
                    )
                row += 1
            idx = row
        else:
            idx += 1

    # ---- syntax + pasteability ----------------------------------------
    try:
        import yaml  # noqa: PLC0415
    except Exception:
        yaml = None
        warnings.append("pyyaml absent — ```yaml blocks not parsed (pip install pyyaml)")

    for match in BLOCK.finditer(text):
        lang = match.group(1).lower()
        body = match.group(2)
        where = text[: match.start()].count("\n") + 1
        if lang == "json":
            try:
                json.loads(body)
            except Exception as exc:
                failures.append(f"line {where}: ```json block does not parse ({str(exc)[:70]})")
        elif lang in ("yaml", "yml") and yaml is not None:
            try:
                list(yaml.safe_load_all(body))  # multi-doc blocks (`---`) are legal
            except Exception as exc:
                failures.append(f"line {where}: ```{lang} block does not parse ({str(exc)[:70]})")
        elif lang in ("bash", "sh", "shell"):
            code, err = bash_n(body)
            if code:
                detail = (err.strip().splitlines() or [""])[-1]
                failures.append(f"line {where}: bash -n failed — {detail[-90:]}")
            for offset, line in enumerate(body.split("\n"), 1):
                if line.lstrip().startswith("#"):
                    continue
                mask = quote_mask(line)
                for hit in PLACEHOLDER.finditer(line):
                    if hit.start() < len(mask) and mask[hit.start()]:
                        continue
                    warnings.append(
                        f"line {where + offset}: unquoted <{hit.group(1)}> is a shell redirection — "
                        f'write "<{hit.group(1)}>"'
                    )

    return failures, warnings, stats


def main(argv: list[str]) -> int:
    minimum = 8
    paths: list[str] = []
    i = 1
    while i < len(argv):
        if argv[i] == "--min-sections" and i + 1 < len(argv):
            minimum = int(argv[i + 1])
            i += 2
            continue
        if not argv[i].startswith("--"):
            paths.append(argv[i])
        i += 1
    if not paths:
        print(__doc__.strip().splitlines()[2].strip())
        return 2

    bad = warned = 0
    for raw in paths:
        path = Path(raw).expanduser()
        failures, warnings, stats = check_file(path, minimum)
        print(f"\nfile      {path}  ({path.stat().st_size if path.is_file() else 0} bytes)")
        if stats:
            print("          " + "  ".join(f"{k} {v}" for k, v in stats.items()))
        for warning in warnings:
            print(f"WARN {warning}")
        for failure in failures:
            print(f"FAIL {failure}")
        if failures:
            bad += 1
        elif warnings:
            warned += 1
        else:
            print("OK  structure, syntax, and anchors are consistent")

    print(f"\n{len(paths)} file(s): {len(paths) - bad} pass, {bad} fail, {warned} with warnings")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
