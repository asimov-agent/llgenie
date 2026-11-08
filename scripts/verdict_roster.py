#!/usr/bin/env python3
"""Which workflows can put a check-run on a PR head, and which ones `ci-verdict` actually judges (#2116).

`ci-verdict` judged exactly ONE workflow. `.github/workflows/ci-verdict.yml` declared

    on:
      workflow_run:
        workflows:
          - CI

and GitHub matches that list VERBATIM against a workflow's top-level `name:` (no wildcard, #349). So a
check-run posted by any OTHER `pull_request` workflow was never read by the verdict, while
`scripts/auto_merge.py` refused the merge on ANY red check-run at the head, "whatever
`mergeStateStatus` says" (#1386). The two rules composed into a state the board could not express:
verdict green, auto-merge armed, merge impossible, and nothing on the head said why.

Measured specimen — PR #1982, head `aeac049f` (2026-11-08): `ci-verdict` `success`,
`autoMergeRequest` armed, `engine-build-pr-trigger` `failure` (run 42440650801, job 128608980091,
`[will] FAIL engine=surogate: wait bound (60 min) expired`). A reader who trusted the verdict saw
"green and armed" on a PR that could never merge.

This module is the roster half of the fix, and it is a SUBSET check, never equality: the workflow set
grows by design, so only "every judged workflow must be able to post" and "every poster must carry a
decision" are assertions. `scripts/ci_verdict.py` is the runtime half — it names a red check-run it did
not judge instead of posting a plain `success`.

The decision file (`data/verdict-roster.json`) is what makes a poster's absence from the judged set a
DECISION rather than an omission: `judged: true` for a workflow whose check-runs the judged run already
accounts for, and `judged: false` with a reason, a date and an issue for one that is deliberately left
outside the verdict (the verdict still NAMES its red). An entry that no longer matches a poster is
reported STALE, so the file cannot rot either — the same shape as
`tests/fixtures/workflow-run-exemptions.json` (#349) and `tests/fixtures/docs-exceptions.json` (#257).

Entries are keyed by the workflow FILE (`scope.yml`), never by its `name:`: this repo's names are
sentences, so a roster keyed by a sentence is unreadable and re-keyed by every rename. The `name:` is
what GitHub matches, so it is printed beside the file and it is what `ci-verdict.yml` must list.

Commands (stdlib only — the tree's own workflow files are the only input):

    verdict_roster.py report    # posters, judged set, the difference, and every finding
    verdict_roster.py check     # exit 1 on any finding (run by `make check-workflows`)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ".github/workflows"
#: The consumer whose `workflow_run.workflows:` roster is the JUDGED set.
VERDICT_WORKFLOW = ".github/workflows/ci-verdict.yml"
#: The dated decisions: one entry per workflow that can post a check-run at a PR head.
DECISIONS = "data/verdict-roster.json"
DECISION_SCHEMA = 1

#: Every event that makes a workflow run on a pull request, and therefore able to post a check-run to
#: the PR's head commit. `pull_request_target` runs in the base repo against the base ref but still
#: reports its jobs to the PR head's check list, so it belongs in the poster population.
POSTER_TRIGGERS = ("pull_request", "pull_request_target")

#: A top-level `on:` key, quoted or bare (YAML 1.1 reads the bare one as the boolean `True`).
ON_KEY = re.compile(r"^[\"']?on[\"']?:(?P<rest>.*)$")
#: A top-level `name:` value, quoted or bare — the string GitHub matches `workflow_run.workflows` on.
NAME_KEY = re.compile(r"^name:\s*(?P<value>.+?)\s*$", re.M)
#: An `on.workflow_run:` trigger, at any indentation (never a `run:` block's script text).
WORKFLOW_RUN_KEY = re.compile(r"^(?P<indent>[ \t]*)workflow_run:\s*(?P<rest>.*)$")
#: The `workflows:` list a `workflow_run` trigger carries — the JUDGED roster.
WORKFLOWS_KEY = re.compile(r"^(?P<indent>[ \t]*)workflows:\s*(?P<rest>.*)$")


def unquote(value: str) -> str:
    """A YAML scalar's value: GitHub matches the DECODED string, so quotes never count."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def indented_block(lines: list[str], start: int, indent: int) -> list[str]:
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


def workflow_files(root: Path = REPO_ROOT) -> list[Path]:
    """Every workflow file in the tree, by name — the population both halves of #2116 read."""
    return sorted((root / WORKFLOWS).glob("*.yml"))


def workflow_names(root: Path = REPO_ROOT) -> dict[str, str]:
    """Every workflow's top-level `name:` -> its file name. The roster is matched against these."""
    out: dict[str, str] = {}
    for path in workflow_files(root):
        m = NAME_KEY.search(path.read_text(encoding="utf-8"))
        if m is not None:
            out[unquote(m.group("value"))] = path.name
    return out


def workflow_run_lists(path: Path) -> list[tuple[int, list[str]]]:
    """Each `workflow_run.workflows:` list in a file: (line number of the key, the names it lists).

    Both shapes GitHub accepts are read: the block form (`- name` per line, this repo's) and the inline
    form (`[CI, pipeline]`). A name is returned exactly as it is written minus YAML quoting, because
    that is what GitHub compares against each workflow's `name:` — no globbing, no fuzzy match.

    This lives here, not in `scripts/check_workflows.py` (which imports it): the JUDGED roster and the
    POSTER population are read by one module, so the two cannot disagree about what a `name:` is.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[tuple[int, list[str]]] = []
    for i, line in enumerate(lines):
        m = WORKFLOW_RUN_KEY.match(line)
        if m is None:
            continue
        body = indented_block(lines, i, len(m.group("indent")))
        for j, item in enumerate(body):
            w = WORKFLOWS_KEY.match(item)
            if w is None:
                continue
            rest = w.group("rest").strip()
            if rest.startswith("["):
                out.append((i + 1, [unquote(x) for x in rest.strip("[]").split(",") if x.strip()]))
                continue
            names = []
            for entry in indented_block(body, j, len(w.group("indent"))):
                if entry.strip().startswith("-"):
                    names.append(unquote(entry.split("-", 1)[1]))
            out.append((i + 1, names))
    return out


def triggers(text: str) -> set[str]:
    """The event keys under a file's top-level `on:` — both the block and the inline-list shape.

    Anchored at column zero, so a `run:` block's script text (never at column zero in a workflow)
    cannot be read as a trigger, and a commented `# on:` cannot either.
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = ON_KEY.match(line)
        if m is None:
            continue
        rest = m.group("rest").strip()
        if rest:
            if rest.startswith("["):
                return {unquote(x) for x in rest.strip("[]").split(",") if x.strip()}
            return {unquote(rest)}
        out: set[str] = set()
        base: int | None = None
        for child in lines[i + 1:]:
            if not child.strip() or child.lstrip().startswith("#"):
                continue
            indent = len(child) - len(child.lstrip(" \t"))
            if indent == 0:
                break
            if base is None:
                base = indent
            if indent != base:
                continue
            out.add(unquote(child.split(":", 1)[0]))
        return out
    return set()


def poster_workflows(root: Path = REPO_ROOT) -> dict[str, str]:
    """Every workflow that can post a check-run at a PR head: its FILE name -> its `name:`."""
    out: dict[str, str] = {}
    for path in workflow_files(root):
        text = path.read_text(encoding="utf-8")
        events = triggers(text)
        if not any(event in events for event in POSTER_TRIGGERS):
            continue
        m = NAME_KEY.search(text)
        out[path.name] = unquote(m.group("value")) if m is not None else ""
    return out


def judged_workflows(root: Path = REPO_ROOT) -> set[str]:
    """The workflows `ci-verdict.yml`'s `workflow_run.workflows:` roster judges, verbatim."""
    path = root / VERDICT_WORKFLOW
    if not path.is_file():
        return set()
    names: set[str] = set()
    for _line, listed in workflow_run_lists(path):
        names.update(listed)
    return names


def judged_files(root: Path = REPO_ROOT) -> set[str]:
    """The judged roster resolved to workflow FILE names, so the comparison is file-shaped."""
    by_name = {name: filename for filename, name in poster_workflows(root).items()}
    return {by_name[name] for name in judged_workflows(root) if name in by_name}


def decisions(root: Path = REPO_ROOT) -> dict[str, dict]:
    """The dated decisions, keyed by a workflow's FILE name."""
    path = root / DECISIONS
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != DECISION_SCHEMA:
        raise SystemExit(
            f"{DECISIONS} is schema {data.get('schema')!r}; this guard reads {DECISION_SCHEMA}")
    return data.get("workflows") or {}


def difference(root: Path = REPO_ROOT) -> list[str]:
    """The posters `ci-verdict` does NOT judge — the set whose reds used to be invisible."""
    return sorted(set(poster_workflows(root)) - judged_files(root))


def coverage(root: Path = REPO_ROOT) -> list[dict]:
    """Every way the poster population and the judged set can drift apart, as findings.

    (a) a poster with no decision is an omission, not a judgement — adding a `pull_request` workflow
        must be a deliberate decision about whether the verdict accounts for its check-runs;
    (b) a decision that claims `judged` while `ci-verdict.yml` does not list the workflow is a lie the
        reader cannot see — the reds it posts would be invisible;
    (c) a decision left outside the judged set must carry its reason, its date and its issue, or the
        next reader cannot tell a decision from a forgotten row;
    (d) an entry naming no poster is STALE (renamed, deleted, or it lost its `pull_request` trigger),
        which is how a roster rots silently in the other direction;
    (e) SUBSET: the judged set must be able to post at a PR head (`judged <= posters`). Never equality
        — the workflow set grows by design.
    """
    out: list[dict] = []
    posters = poster_workflows(root)
    judged = judged_workflows(root)
    judged_by_file = judged_files(root)
    decided = decisions(root)

    for filename, name in sorted(posters.items()):
        if filename in decided:
            continue
        out.append({
            "key": f"verdict-roster-unrecorded/{filename}",
            "title": f"ci: {filename} can post a check-run at a PR head and has no judgement decision",
            "evidence": (
                f"`{WORKFLOWS}/{filename}` ({name}) runs on `pull_request`, so its jobs post "
                f"check-runs on the PR head — and `scripts/auto_merge.py` refuses a merge on ANY red "
                f"one. `{VERDICT_WORKFLOW}` judges only {sorted(judged)}. Record the decision in "
                f"`{DECISIONS}`: `judged: true` when the judged run already accounts for its "
                f"check-runs, or `judged: false` with a reason, a date and an issue (the verdict still "
                f"NAMES its red — issue #2116)."
            ),
            "where": f"{WORKFLOWS}/{filename}",
        })

    for filename, decision in sorted(decided.items()):
        if filename not in posters:
            out.append({
                "key": f"verdict-roster-stale/{filename}",
                "title": f"ci: {DECISIONS} decides {filename!r}, which can no longer post a check-run at a PR head",
                "evidence": (
                    f"`{DECISIONS}` carries an entry for {filename!r}, and no workflow file of that "
                    f"name runs on `pull_request`/`pull_request_target` any more. Either it was "
                    f"renamed or deleted, or it lost its pull-request trigger — in every case the "
                    f"decision describes a surface that no longer exists, and a stale decision is how "
                    f"a renamed workflow becomes unaccounted a second time. Delete or re-point the "
                    f"entry."
                ),
                "where": DECISIONS,
            })
            continue
        if decision.get("judged") is True:
            if filename not in judged_by_file:
                out.append({
                    "key": f"verdict-roster-not-judged/{filename}",
                    "title": f"ci: {DECISIONS} says {filename!r} is judged, and {VERDICT_WORKFLOW} does not list its name",
                    "evidence": (
                        f"`{DECISIONS}` records `judged: true` for {filename!r} "
                        f"({posters[filename]}), whose check-runs would then be read as accounted "
                        f"for. `{VERDICT_WORKFLOW}`'s `workflow_run.workflows:` roster is "
                        f"{sorted(judged)} — GitHub matches it VERBATIM against a workflow's `name:` "
                        f"(no wildcard, #349), so this workflow is NOT judged and a red it posts "
                        f"would be invisible to a `ci-verdict: success`. Add its `name:` to the "
                        f"roster, or record `judged: false` with the reason."
                    ),
                    "where": DECISIONS,
                })
        else:
            missing = [field for field in ("reason", "date", "issue") if not decision.get(field)]
            if missing:
                out.append({
                    "key": f"verdict-roster-undated/{filename}",
                    "title": f"ci: {DECISIONS} leaves {filename!r} outside the verdict with no {', '.join(missing)}",
                    "evidence": (
                        f"`{DECISIONS}` records {filename!r} as not judged, and the entry carries no "
                        f"{', '.join(missing)}. An exemption without a reason and a date is "
                        f"indistinguishable from a forgotten row, and the next reader cannot tell "
                        f"whether its red is deliberately unjudged or simply unwatched (#349/#257 "
                        f"shape)."
                    ),
                    "where": DECISIONS,
                })

    for name in sorted(judged - set(posters.values())):
        out.append({
            "key": f"verdict-roster-blind/{name}",
            "title": f"ci: {VERDICT_WORKFLOW} judges {name!r}, which cannot post a check-run at a PR head",
            "evidence": (
                f"`{VERDICT_WORKFLOW}`'s `workflow_run.workflows:` roster names {name!r}, and no "
                f"workflow with that `name:` runs on `pull_request`/`pull_request_target` in "
                f"`{WORKFLOWS}`. A judged workflow that never runs on a pull request cannot have "
                f"PR-head check-runs to account for — the roster is matching nothing on the surface "
                f"the verdict exists for. This is a SUBSET assertion (`judged <= posters`), never "
                f"equality: the workflow set grows by design."
            ),
            "where": VERDICT_WORKFLOW,
        })
    return out


def report(root: Path = REPO_ROOT) -> str:
    """The whole picture: posters, judged, the difference, and every finding."""
    posters = poster_workflows(root)
    judged = judged_workflows(root)
    judged_by_file = judged_files(root)
    diff = difference(root)
    lines = [
        f"[verdict-roster] posters ({len(posters)}) — every workflow that can post a check-run at a PR head:",
    ]
    lines += [f"  {filename}  <{name or '(no name)'}>" for filename, name in sorted(posters.items())]
    lines.append(
        f"[verdict-roster] judged ({len(judged_by_file)}) — `{VERDICT_WORKFLOW}`'s workflow_run roster:")
    lines += [f"  {filename}  <{posters[filename]}>" for filename in sorted(judged_by_file)]
    lines += [f"  {name}  <names no pull-request workflow>"
              for name in sorted(judged) if name not in set(posters.values())]
    lines.append(
        f"[verdict-roster] NOT judged ({len(diff)}) — a red here is NAMED by the verdict, never a "
        f"plain success:")
    lines += [f"  {filename}  <{posters[filename]}>" for filename in diff]
    items = coverage(root)
    if not items:
        lines.append(
            "[verdict-roster] a subset check holds: judged <= posters, every poster carries a dated "
            "decision, no decision is stale")
    for item in items:
        lines.append(f"[verdict-roster] FAIL {item['key']}: {item['title']}")
    lines.append(
        f"[verdict-roster] verdict: {'green' if not items else f'red ({len(items)} finding(s))'}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The check-run posters vs the judged set (#2116).")
    parser.add_argument("command", choices=("check", "report"), nargs="?", default="report")
    args = parser.parse_args(argv)
    print(report())
    return 1 if args.command == "check" and coverage() else 0


if __name__ == "__main__":
    sys.exit(main())
