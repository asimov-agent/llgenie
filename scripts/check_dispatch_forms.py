#!/usr/bin/env python3
"""Every dispatchable workflow states the work it will do, before you dispatch it (issue #276).

A bot you cannot dispatch without reading its YAML is a bot only its author can operate. The
dispatch dialog is the interface a collaborator actually meets, so this guard holds every workflow
that a human can start by hand to three things:

* **a `name:` that states the work**, not the identifier — `issue-bot — implements ONE issue per run
  as a reviewable PR (never merges)`, so the Actions list is a list of jobs. A name that is just the
  file stem (`registry-sync`) says nothing about what the run does.
* **a self-documenting manual dispatch form**: every `workflow_dispatch` input carries a
  `description:` written as the instruction a user needs, plus a `default:` or `required: true`. A
  bare `workflow_dispatch:` (no `inputs:` at all) is allowed only when the file says why, in a
  greppable line — `# dispatch: no inputs — <reason>` — so "it takes no input" is a decision that
  was made, not a form that was forgotten.
* **the same header block**, so the contract is readable in the file you are about to dispatch:
  `# Trigger surface:`, `# Flow:`, `# Never:`. `Flow` names the make target behind each step
  (the one-make-path-per-stage rule); `Never` states the invariants (never merges, never pushes to
  main, never edits code) that the workflow must not break.

The README's dispatch table is generated from the workflows and verified against them, so the
documentation a dispatcher reads cannot drift from the pipelines it describes.

Commands:
    check_dispatch_forms.py check     exit non-zero on any violation, and on a stale README table
    check_dispatch_forms.py report    print the README table (the source of truth)

Usage:
    python3 scripts/check_dispatch_forms.py check
    python3 scripts/check_dispatch_forms.py report
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ".github/workflows"
README = "README.md"
#: The README's generated dispatch table lives between these markers.
BEGIN = "<!-- dispatch-forms:begin -->"
END = "<!-- dispatch-forms:end -->"
#: `# dispatch: no inputs — <reason>` exempts a workflow from the inputs requirement.
NO_INPUTS = re.compile(r"^#\s*dispatch:\s*no inputs\s*[—:-]\s*(\S.*)$", re.M)
#: A `name:` states the work when it reads `<identifier><separator><what it does>`.
NAME_SEPARATOR = re.compile(r"^(.{2,40}?)\s*(?:—|–|:|-)\s+(\S.*)$")
MIN_DESCRIPTION = 10
#: A `HH:MM UTC` the header names, e.g. "schedule daily 05:41 UTC" (the claim a reader believes).
HEADER_TIME = re.compile(r"(\d{1,2}):(\d{2})\s*UTC")
#: A `cron: "M H * * *"` line, so the header's claim can be checked against the schedule itself.
CRON = re.compile(r'cron:\s*"([^"]+)"')


def workflow_files(root: Path = REPO_ROOT) -> list[Path]:
    return sorted((root / WORKFLOWS).glob("*.yml"))


def _top_level_block(text: str, key: str) -> tuple[int, list[str]]:
    """The lines of a `key:` block — the key may sit under `on:` (indented), so its own indent
    decides where the block ends, not column 0."""
    lines = text.splitlines()
    start = next((n for n, l in enumerate(lines) if l.strip() == f"{key}:"), None)
    if start is None:
        return -1, []
    indent = len(lines[start]) - len(lines[start].lstrip())
    block: list[str] = []
    for line in lines[start + 1:]:
        if not line.strip():
            block.append(line)
            continue
        if (len(line) - len(line.lstrip())) <= indent:
            break
        block.append(line)
    return start, block


def name_of(text: str) -> str:
    m = re.search(r"^name:\s*(.+)$", text, re.M)
    return m.group(1).strip().strip("'\"") if m else ""


def name_states_the_work(text: str, stem: str) -> tuple[bool, str]:
    """Does `name:` say what the run does, rather than repeat the file name?"""
    name = name_of(text)
    if not name:
        return False, "there is no `name:`"
    if name == stem:
        return False, f"`name: {name}` repeats the file name; state the work instead"
    m = NAME_SEPARATOR.match(name)
    if not m:
        return False, (f"`name: {name}` has no `— what it does` part "
                       f"(e.g. `{stem} — <what the run does, and its bound>`)")
    what = m.group(2).strip()
    if len(what) < MIN_DESCRIPTION:
        return False, f"`name: {name}` describes the work in fewer than {MIN_DESCRIPTION} characters"
    return True, ""


def dispatch_inputs(text: str) -> list[dict]:
    """[{key, description, has_default, required}] for every `workflow_dispatch` input."""
    _, block = _top_level_block(text, "workflow_dispatch")
    if not block:
        return []
    # find `inputs:` inside the dispatch block, then its 6-space-indented keys
    try:
        i = next(n for n, l in enumerate(block) if l.strip() == "inputs:")
    except StopIteration:
        return []
    out: list[dict] = []
    current: dict | None = None
    for line in block[i + 1:]:
        if not line.strip() or line.strip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        key_match = re.match(r"^([A-Za-z_][\w-]*):\s*$", line.strip())
        if indent <= 6 and key_match:
            if current:
                out.append(current)
            current = {"key": key_match.group(1), "description": "", "has_default": False,
                       "required": False, "default": ""}
            continue
        if current is None:
            continue
        field = re.match(r"^(description|default|required):\s*(.*)$", line.strip())
        if not field:
            if indent <= 6:
                break                      # the block ended (permissions:, jobs:, …)
            continue
        field_name, value = field.group(1), field.group(2).strip().strip("'\"")
        if field_name == "description":
            current["description"] = value
        elif field_name == "default":
            current["has_default"] = True
            current["default"] = value
        elif field_name == "required":
            current["required"] = value.lower() == "true"
    if current:
        out.append(current)
    return out


def header_block(text: str) -> list[str]:
    """The `Trigger surface` / `Flow` / `Never` keys that are present, in the file's own order."""
    return [k for k in ("Trigger surface", "Flow", "Never") if re.search(rf"^#\s*{k}:", text, re.M)]


def analyse(path: Path) -> dict:
    text = path.read_text()
    exempt = NO_INPUTS.search(text)
    return {
        "file": path.name,
        "name": name_of(text),
        "stem": path.stem,
        "dispatch": _top_level_block(text, "workflow_dispatch")[0] != -1,
        "inputs": dispatch_inputs(text),
        "exempt": bool(exempt),
        "exempt_reason": (exempt.group(1).strip() if exempt else ""),
        "header": header_block(text),
        "header_lines": leading_comment_block(text),
        "crons": CRON.findall(text),
        "text": text,
    }


def leading_comment_block(text: str) -> str:
    """The comment block a reader sees first — where the header lives, verbatim.

    `header_block()` returns the KEY NAMES it found (that is what the missing-key rule needs), so a
    rule about what those lines CLAIM has to read the lines themselves.
    """
    out: list[str] = []
    for line in text.splitlines():
        if line.startswith("#"):
            out.append(line)
        elif not line.strip() and out:
            continue                      # a blank line inside the block, not the end of it
        elif out:
            break
    return "\n".join(out)


def violations(root: Path = REPO_ROOT) -> list[str]:
    """Every way a dispatchable workflow fails to state the work it will do."""
    out: list[str] = []
    for path in workflow_files(root):
        a = analyse(path)
        if not a["dispatch"]:
            continue                                  # not dispatchable by hand: out of scope
        ok, why = name_states_the_work(a["text"], a["stem"])
        if not ok:
            out.append(f"{a['file']}: {why}")

        missing_header = [k for k in ("Trigger surface", "Flow", "Never") if k not in a["header"]]
        if missing_header:
            out.append(f"{a['file']}: header block is missing "
                       f"{', '.join(f'`# {k}:`' for k in missing_header)}")

        # A header that names a TIME must name THIS file's time: the minutes moved in #275 and the
        # prose moved with them in one file and not in three others, which is exactly the drift this
        # guard exists to stop (a reader believes "schedule daily 05:41 UTC" more than the cron line).
        header_text = a["header_lines"]
        for hh, mm in HEADER_TIME.findall(header_text):
            fields = [c.split() for c in a["crons"]]
            named = f"{int(hh):02d}:{mm}"
            if not fields:
                out.append(f"{a['file']}: the header claims `{named} UTC` but the file has no schedule")
            elif not any(len(f) == 5 and f[0] == str(int(mm)) and f[1] == str(int(hh)) for f in fields):
                out.append(f"{a['file']}: the header claims `{named} UTC` but no cron in the file starts "
                           f"then ({', '.join(a['crons'])})")

        if not a["inputs"] and not a["exempt"]:
            out.append(f"{a['file']}: bare `workflow_dispatch:` — either give it a documented "
                       f"input, or state `# dispatch: no inputs — <reason>`")
        if a["exempt"] and len(a["exempt_reason"]) < MIN_DESCRIPTION:
            out.append(f"{a['file']}: the `# dispatch: no inputs` exemption needs a real reason "
                       f"(at least {MIN_DESCRIPTION} characters)")

        for i in a["inputs"]:
            if len(i["description"]) < MIN_DESCRIPTION:
                out.append(f"{a['file']}: input `{i['key']}` has no usable `description:` — the "
                           f"dispatch dialog is the only place a user sees what it means")
            if not i["has_default"] and not i["required"]:
                out.append(f"{a['file']}: input `{i['key']}` has neither `default:` nor "
                           f"`required: true`, so its meaning is undefined when left empty")
    return out


def table(root: Path = REPO_ROOT) -> str:
    """The README table, generated from the workflows themselves."""
    rows = ["| workflow | what the run does | dispatch inputs |", "|---|---|---|"]
    for path in workflow_files(root):
        a = analyse(path)
        if not a["dispatch"]:
            continue
        name = a["name"] or f"({a['stem']})"
        what = name.split("—", 1)[1].strip() if "—" in name else "(name does not state the work)"
        if a["inputs"]:
            cells = []
            for i in a["inputs"]:
                req = "required" if i["required"] else "optional"
                if i["has_default"] and i["default"] != "":
                    req += f", default `{i['default']}`"
                cells.append(f"`{i['key']}` ({req}) — {i['description']}")
            inputs = "<br>".join(cells)
        else:
            inputs = f"none — {a['exempt_reason']}" if a["exempt"] else "**none documented**"
        rows.append(f"| `{a['file']}` | {what} | {inputs} |")
    return "\n".join(rows)


def readme_stale(root: Path = REPO_ROOT) -> str | None:
    """The reason the README table does not match the workflows, or None when it does."""
    readme = root / README
    if not readme.exists():
        return f"{README} does not exist"
    text = readme.read_text()
    if BEGIN not in text or END not in text:
        return f"{README} has no `{BEGIN}` … `{END}` block for the generated dispatch table"
    have = text.split(BEGIN, 1)[1].split(END, 1)[0].strip()
    want = table(root).strip()
    if have != want:
        return (f"the {README} dispatch table is stale — regenerate it with "
                f"`make check-dispatch-forms report`")
    return None


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="check_dispatch_forms", description=__doc__)
    p.add_argument("cmd", choices=("check", "report"))
    p.add_argument("--root", default=str(REPO_ROOT))
    args = p.parse_args(argv)
    root = Path(args.root)

    if args.cmd == "report":
        print(table(root))
        return 0

    bad = violations(root)
    stale = readme_stale(root)
    if stale:
        bad.append(stale)
    dispatchable = [p.name for p in workflow_files(root) if analyse(p)["dispatch"]]
    if bad:
        print(f"[check-dispatch-forms] {len(bad)} violation(s):", file=sys.stderr)
        for b in bad:
            print(f"  - {b}", file=sys.stderr)
        return 1
    print(f"[check-dispatch-forms] OK {len(dispatchable)} dispatchable workflow(s) state the work "
          f"they do, their inputs are documented, and the README table matches: "
          f"{', '.join(dispatchable)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
