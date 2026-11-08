#!/usr/bin/env python3
"""Refuse an unrunnable task shape at creation time (issue #2123).

An implementation task was filed onto `llgenie-planner` (the orchestrator, which never
implements) with a `scratch` workspace (which has no checkout to edit). Either fault alone
made the task incapable of producing a PR; together they parked the #2089 carry blocked for
51 minutes until a human-side reclaim noticed. Nothing refused the bad assignment when it was
written, and a misassignment that is only caught by reading history is, until then, real queued
work that can never be started.

This guard closes the class at the moment the task is authored: a proposed task shape has two
facts that must agree — WHO is assigned (a lane that can act on the work class) and WHERE it
works (a workspace with a checkout when the task must produce a branch). A shape is refused when
either fact is broken, and the message names the offending FIELD so the creator can fix it in one
read:

* **assignee** — a branch-producing task assigned to `llgenie-planner` is refused: the planner
  triages, refines and dispatches; it never implements. The message quotes the role split and
  names the lane that owns the work class.
* **workspace** — a branch-producing task in a `scratch` workspace is refused: a scratch
  workspace has no git checkout to edit, so even a correct assignee would have nothing to commit
  into. The message names `--workspace worktree` (or `dir:<existing-worktree>` when the branch
  already exists) as the remedy.

A task is *branch-producing* when its title/body matches one of the fleet's four work classes —
implementation, docs, pipeline or rebase. Non-branch work (research, a report, a raw measurement)
is not refused for a scratch workspace: a read has no branch to build. The four classes and their
owning lanes are the role split recorded in `agents/llgenie-planner/SOUL.md` and the orchestrator
tick prompt, not a new authority.

Commands:
    check_task_shape.py refuse --assignee LANE --workspace KIND --title T --body "…"
        (or --body-file F)     refuse a proposed task shape; exit 1 on a refusal, 0 if acceptable
    check_task_shape.py scan --kanban-json FILE
                               surface blocked tasks whose assignee cannot do their work class
                               (the orchestrator-pass-report leg, AC-4); exit 1 when any found
                           (reads `kanban list --json` from stdin when no file is given)
    check_task_shape.py owners   print the work class -> owning lane table

The pure `refuse()` function is the single decision point and is imported by the tests — no mocks
of the product, only fixture text and fixture board JSON.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

#: The four work classes and the lane that owns each. This IS the role split the refusal quotes
#: (issue #2123, AC-5): implementation -> llgenie-issse-implementer, docs ->
#: llgenie-documentation-maintainer, pipeline -> llgenie-ci-pipelines-maintainer, rebase ->
#: llgenie-pr-merge-conflict.
CLASS_OWNER: dict[str, str] = {
    "implementation": "llgenie-issse-implementer",
    "docs": "llgenie-documentation-maintainer",
    "pipeline": "llgenie-ci-pipelines-maintainer",
    "rebase": "llgenie-pr-merge-conflict",
}

#: Per-class markers, matched case-insensitively on the TITLE only (the create dialog shows the
#: title; a creator reads the refusal against what they typed). Distinct-enough stems keep a task
#: in exactly one class so a refusal names one owner, but the guards use SUBSET semantics — a task
#: that matches several classes is refused for all of them.
CLASS_MARKERS: dict[str, tuple[str, ...]] = {
    "implementation": ("implement", "branch", "commit", "closes #", "open a pr", "pr: ", "author"),
    "docs": ("docs/", "agent-wiki", "changes.md", "documentation", "change note", "changelog"),
    "pipeline": ("workflow", "make target", "makefile", "ci-", ".yml", "pipeline", "gate", "docker"),
    "rebase": ("rebase", "merge-base", "merge conflict", "mergebase", "conflicting"),
}

#: The lane that is an ORCHESTRATOR, not an implementer: it must never hold a branch-producing task.
#: One lane is in this set (issue #2123); the message quotes its role split.
PLANNER = "llgenie-planner"
ROLE_SPLIT = "the planner triages, refines and dispatches; it never implements"

#: A workspace value that has no checkout to edit. None or a falsy value is the `scratch` default.
NO_CHECKOUT = ("scratch", "", None)


def _matches(text: str, stems: tuple[str, ...]) -> bool:
    low = text.lower()
    return any(stem in low for stem in stems)


def classify(title: str) -> set[str]:
    """The work classes `title` describes (empty == not branch-producing)."""
    return {cls for cls, stems in CLASS_MARKERS.items() if _matches(title, stems)}


def workspace_default(value: str | None) -> str:
    """Normalise a workspace value to a concrete kind (`scratch` when unspecified)."""
    return value if value in ("worktree", "dir", "scratch") else ("worktree" if value else "scratch")


def refuse(assignee: str, workspace: str | None, title: str) -> list[str]:
    """Refusal reasons for a proposed task shape, one per broken field (empty == acceptable).

    Each message names the offending FIELD and, where relevant, the lane that owns the work class
    and the remedy. A refusal is a hard error the creator must resolve before the task exists.
    """
    classes = classify(title)
    if not classes:
        return []  # not branch-producing -> both facts are acceptable a priori

    reasons: list[str] = []
    # assignee: an orchestrator lane cannot hold branch-producing work.
    if assignee == PLANNER:
        owners = ", ".join(sorted({CLASS_OWNER[c] for c in classes}))
        reasons.append(
            f"assignee: {assignee} cannot act on a {_class_list(classes)} task — {ROLE_SPLIT}. "
            f"Constructed a {_class_list(classes)} class, so own it on {owners}; "
            f"set --assignee to {owners}."
        )
    # workspace: a branch-producing task needs a checkout to edit.
    if workspace in NO_CHECKOUT:
        reasons.append(
            f"workspace: 'scratch' has no checkout to edit, and this {_class_list(classes)} task "
            f"must produce a branch. Use --workspace worktree (or dir:<existing-worktree> when the "
            f"branch already exists)."
        )
    return reasons


def _class_list(classes: set[str]) -> str:
    return "/".join(sorted(classes)) if classes else "non-code"


def _refuse_cli(args: argparse.Namespace) -> int:
    title = args.title or ""
    refusals = refuse(args.assignee, args.workspace, title)
    if not refusals:
        return 0
    for r in refusals:
        print(f"REFUSE {r}")
    return 1


def _owners_cli() -> int:
    for cls in sorted(CLASS_OWNER):
        print(f"  {cls:16} {CLASS_OWNER[cls]}")
    return 0


def _scan_cli(args: argparse.Namespace) -> int:
    """Surface blocked tasks whose assignee cannot do their work class (orchestrator pass, AC-4).

    Reads `kanban list --json` (a bare JSON array of task objects) from a file or stdin and prints
    a `MISASSIGNED <id>` line per blocked task that a refusal would have caught at creation — the
    shape that slipped past the pre-fix guard. Exit 1 when any is found, 0 when none.
    """
    if args.kanban_json:
        try:
            tasks = json.loads(Path(args.kanban_json).read_text())
        except Exception as exc:  # noqa: BLE001 -- report, never crash
            print(f"[check-task-shape] ERROR reading {args.kanban_json}: {exc}", file=sys.stderr)
            return 2
    else:
        tasks = json.loads(sys.stdin.read() or "[]")
    if not isinstance(tasks, list):
        tasks = []
    found = 0
    for t in tasks:
        if not isinstance(t, dict) or t.get("status") != "blocked":
            continue
        assignee = t.get("assignee") or ""
        workspace = t.get("workspace_kind") or t.get("workspace") or "scratch"
        title = t.get("title") or ""
        if refuse(assignee, workspace, title):
            found += 1
            print(f"MISASSIGNED {t.get('id') or '?'} assignee={assignee} workspace={workspace} "
                  f"title={(title or '')[:60]}")
    if found:
        print(f"  {found} blocked task(s) whose assignee cannot do the work class — route to the owner")
    return 1 if found else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="check_task_shape.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("refuse", help="refuse a proposed task shape (exit 1 on a refusal)")
    r.add_argument("--assignee", required=True)
    r.add_argument("--workspace", default="scratch", help="worktree | scratch | dir:<path>")
    r.add_argument("--title", default="")
    r.add_argument("--body-file", default=None)
    r.set_defaults(fn=_refuse_cli)
    s = sub.add_parser("scan", help="surface blocked tasks whose assignee cannot do the class")
    s.add_argument("--kanban-json", default=None)
    s.set_defaults(fn=_scan_cli)
    o = sub.add_parser("owners", help="print the work class -> owning lane table")
    o.set_defaults(fn=_owners_cli)
    args = ap.parse_args(argv)

    if args.cmd == "refuse" and args.body_file:
        try:
            args.title = args.title or Path(args.body_file).read_text().splitlines()[0][:200]
        except Exception:  # noqa: BLE001 -- a missing body file is not a shape decision
            pass
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
