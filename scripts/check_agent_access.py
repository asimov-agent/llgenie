#!/usr/bin/env python3
"""Enforce the agent's GitHub access policy artifacts (issue #2923).

The agent lanes act as ONE named identity with a roster of token scopes, and that policy is
written down in exactly two versioned places: the AGENTS.md section
`## The agent's GitHub identity and required access` and the host agent's skill
`agents/llgenie-issse-implementer/skills/agent-github-access/SKILL.md`. This gate is what keeps
those two artifacts real, in both directions:

* the section removed, or no longer naming the acting identity `asimov-agent` — a lane acts under
  an unnamed identity, which is how finished acceptance items end up waiting on human round-trips;
* a scope in the roster losing the operation it maps to — a bare scope list teaches the next run
  nothing about WHICH step each scope unblocks (the roster's whole point, measured on #2914: the
  GC sweep was merged for weeks and no identity could run it);
* the skill removed, or stripped of an audit rule — the elevated run loses its requirement: an
  open issue that requested it, a stamp on that issue, and an identity read from `gh auth status`
  before the step;
* a token-shaped string inside either artifact — the documents that GRANT access must
  demonstrably contain no credential. The report names the kind and location only, never a value.

Usage:
    python3 scripts/check_agent_access.py check    # exit 1 on any finding, 2 when unreadable
    python3 scripts/check_agent_access.py report   # print what the gate reads, always exit 0

Stdlib only.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

AGENTS_MD = "AGENTS.md"
HEADING_PREFIX = "## The agent's GitHub identity and required access"
SKILL = "agents/llgenie-issse-implementer/skills/agent-github-access/SKILL.md"
IDENTITY = "asimov-agent"

#: Every scope the agent lanes need, and the operation word that must appear on the SAME line as
#: the scope token, so the roster stays a map (scope -> the step it unblocks) and never decays
#: into a bare list of scope names.
SCOPE_OPS = {
    "repo": "branch",
    "workflow": "workflows",
    "read:org": "membership",
    "gist": "scratch",
    "write:packages": "publish",
    "delete:packages": "garbage-collect",
}

#: Rule phrases the skill must state, verbatim, in its own voice.
SKILL_RULES = (
    "open issue",
    "stamped",
    "gh auth status",
)

#: Token-shaped strings that must not appear in either policy artifact. A finding names the KIND
#: and the location; the value is never echoed.
SECRET_KINDS = (
    ("classic-style OAuth token (gh[pousr]_...)", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("fine-grained token (github_pat_...)", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
)


def _section(text: str):
    """The identity/access section's lines: its heading up to (not including) the next `## `."""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith(HEADING_PREFIX):
            start = i
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if re.match(r"^##(?!#)", lines[j]):
            end = j
            break
    return lines[start:end]


def _missing_scope_ops(lines) -> "list[str]":
    """Scopes whose operation word never shares a line with the scope token."""
    missing = []
    for scope, op in SCOPE_OPS.items():
        if not any(scope in line and op in line for line in lines):
            missing.append(scope)
    return missing


def _secret_findings(artifact: str, text: str) -> "list[str]":
    findings = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for kind, rx in SECRET_KINDS:
            if rx.search(line):
                findings.append(
                    f"{artifact} line {lineno}: secret-shaped string — {kind}; "
                    "value suppressed, remove it (issue #2923)"
                )
    return findings


def check(root: Path) -> "list[str]":
    findings = []

    agents_path = root / AGENTS_MD
    if not agents_path.is_file():
        return [f"{AGENTS_MD}: unreadable — the identity/access policy cannot be verified"]
    section = _section(agents_path.read_text(encoding="utf-8"))
    if section is None:
        findings.append(
            f"{AGENTS_MD}: the agent's identity/access section is missing — issue #2923 requires "
            f"a section headed '{HEADING_PREFIX}' naming the acting identity and the scope roster"
        )
    else:
        text = "\n".join(section)
        if IDENTITY not in text:
            findings.append(
                f"{AGENTS_MD}: the identity/access section no longer names the acting identity "
                f"'{IDENTITY}' (issue #2923)"
            )
        for scope in _missing_scope_ops(section):
            findings.append(
                f"{AGENTS_MD}: the identity/access section no longer maps `{scope}` to the step "
                f"it authorizes (issue #2923)"
            )
        findings.extend(_secret_findings(f"{AGENTS_MD} identity/access section", text))

    skill_path = root / SKILL
    if not skill_path.is_file():
        findings.append(
            f"{SKILL}: missing — the host agent's access skill carries the audit rules "
            "(issue #2923)"
        )
    else:
        skill_text = skill_path.read_text(encoding="utf-8")
        low = skill_text.lower()
        for scope, op in SCOPE_OPS.items():
            if scope not in skill_text or op not in low:
                findings.append(
                    f"{SKILL}: the scope-to-operation map no longer names `{scope}` together with "
                    f"its operation (issue #2923)"
                )
        for phrase in SKILL_RULES:
            if phrase not in skill_text:
                findings.append(
                    f"{SKILL}: the skill no longer states the rule '{phrase}' (issue #2923)"
                )
        findings.extend(_secret_findings(SKILL, skill_text))

    return findings


def report(root: Path) -> int:
    agents_path = root / AGENTS_MD
    section = _section(agents_path.read_text(encoding="utf-8")) if agents_path.is_file() else None
    print(f"identity:        {IDENTITY}")
    print(f"AGENTS section:  {'present' if section is not None else 'MISSING'}")
    if section is not None:
        missing = _missing_scope_ops(section)
        for scope, op in SCOPE_OPS.items():
            print(f"  scope {scope:<16} mapped to its step: {'yes' if scope not in missing else 'NO'} (operation word: {op})")
    print(f"skill:           {SKILL} ({'present' if (root / SKILL).is_file() else 'MISSING'})")
    skill_text = ""
    if (root / SKILL).is_file():
        skill_text = (root / SKILL).read_text(encoding="utf-8")
        for phrase in SKILL_RULES:
            print(f"  rule '{phrase}': {'stated' if phrase in skill_text else 'MISSING'}")
    findings = check(root)
    print(f"secret scan:     {'token-shaped strings found' if any('secret-shaped' in f for f in findings) else 'clean (no token values)'}")
    print(f"verdict:         {'CLEAN' if not findings else 'FINDINGS (' + str(len(findings)) + ')'}")
    for finding in findings:
        print(f"  - {finding}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=(__doc__ or "Agent access policy gate").splitlines()[0])
    parser.add_argument("mode", choices=("check", "report"))
    args = parser.parse_args(argv)
    if args.mode == "report":
        return report(REPO)
    findings = check(REPO)
    for finding in findings:
        print(f"FINDING: {finding}")
    if findings:
        print(f"agent-access: {len(findings)} finding(s) — the identity policy is not enforced")
        return 1
    print("agent-access: OK — AGENTS.md names the identity and its scope map; the skill carries "
          "the audit rules; no secret values in either artifact")
    return 0


if __name__ == "__main__":
    sys.exit(main())
