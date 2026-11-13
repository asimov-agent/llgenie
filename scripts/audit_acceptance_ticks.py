#!/usr/bin/env python3
"""Audit acceptance ticks over closed issues and supersede the recorded-stale ones.

The #2288 follow-up (issue #2631) as a repo tool. Three legs, one file:

    audit_acceptance_ticks.py audit  --repo R --roster FILE [--quiet]
        Page every closed issue (GraphQL), collect ticked criteria citing
        `run=<id>`, read each cited run's LIVE conclusion + head, exclude
        criteria covered by a `SUPERSEDE-2288` note, report the stale count.
        Exit 0 only when zero unsuperseded stale ticks remain.
    audit_acceptance_ticks.py notes  --repo R --roster FILE --notes-dir DIR
        Render the supersession comment bodies (render_supersede_note is the
        ONLY place the note shape exists) into DIR/<issue>.md.
    audit_acceptance_ticks.py post   --repo R --roster FILE --notes-dir DIR
        Append-only, marker-idempotent posting. An issue that already carries
        `<!-- SUPERSEDE-2288 -->` is skipped. No issue body is ever edited and
        no tick is ever rewritten.

Counting method (AC2 of #2631, recorded here and printed by `audit`):
GraphQL paging over ALL closed issues (`orderBy CREATED_AT DESC`, first:100);
ticked lines matching TICK_RE that cite `run=<digits>`; a criterion is stale
when NONE of its cited runs is completed/success AND the issue carries no
SUPERSEDE-2288 note covering it (cover = the note quotes the criterion line);
run state from `gh api repos/<repo>/actions/runs/<id>`.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from typing import Any

from proc import run_ok, run_checked  # noqa: E402  the subprocess policy seam (issue #797)

BASE_REPO = "asimov-agent/llgenie"
AUDIT_MARKER = "<!-- AUDIT-2288 -->"
SUPERSEDE_MARKER = "<!-- SUPERSEDE-2288 -->"
RED = {"failure", "cancelled", "timed_out", "startup_failure", "startup_error"}
TICK_RE = re.compile(r"^\s*- \[x\].*?run\s*=\s*(\d{6,})")
RUN_RE = re.compile(r"run\s*=\s*(\d{6,})")
COUNTING_METHOD = (
    "GraphQL paging over all closed issues (orderBy CREATED_AT DESC, first:100); ticked lines "
    "matching ^\\s*- \\[x\\].*?run=<digits>; stale iff no cited run is completed/success AND no "
    "SUPERSEDE-2288 note quotes the criterion; run state (status/conclusion/head/workflow) via "
    "gh api actions/runs/<id>; per-head survey of completed/success runs via gh api "
    "actions/runs?head_sha=<head>, stored in the roster as head_green."
)


# --------------------------------------------------------------------------- gh legs


def _gh_json(args: list[str], *, fail_ok: bool = False) -> Any:
    """One `gh api` call through the proc seam, read as JSON (concatenated
    --paginate documents are decoded one at a time)."""
    proc = run_ok(["gh", "api", *args])
    if proc.returncode != 0:
        if fail_ok:
            return None
        sys.stderr.write(f"gh api failed: {' '.join(args)}\n{proc.stderr}\n")
        raise SystemExit(1)
    text = proc.stdout.strip()
    if not text:
        return []
    docs, idx = [], 0
    while idx < len(text):
        value, idx = json.JSONDecoder().raw_decode(text, idx)
        docs.append(value)
    if len(docs) == 1:
        return docs[0]
    merged: list = []
    for doc in docs:
        merged.extend(doc if isinstance(doc, list) else [doc])
    return merged


def closed_issues(repo: str) -> list[dict]:
    """Every closed issue (number + body), newest created first — the same paging
    the #2288 audit used (UPDATED ordering times out on this corpus)."""
    items: list[dict] = []
    cursor = ""
    while True:
        query = (
            '{repository(owner:"%s",name:"%s"){'
            'issues(states:CLOSED,first:100%s,orderBy:{field:CREATED_AT,direction:DESC}){'
            ' pageInfo{hasNextPage endCursor} nodes{number body}}}}'
        ) % (repo.split("/")[0], repo.split("/")[1],
             f',after:"{cursor}"' if cursor else "")
        page = _gh_json(["graphql", "-f", f"query={query}"])["data"]["repository"]["issues"]
        items.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            return items
        cursor = page["pageInfo"]["endCursor"]
        time.sleep(0.15)


def run_states(repo: str, run_ids: list[str]) -> dict[str, tuple[str, str, str, str]]:
    states: dict[str, tuple[str, str, str, str]] = {}
    for rid in sorted(run_ids):
        out = run_ok(["gh", "api", f"repos/{repo}/actions/runs/{rid}",
                      "--jq", "[.status, .conclusion, .head_sha, .name] | @tsv"])
        line = out.stdout.strip()
        if out.returncode != 0 or not line or line == "null":
            states[rid] = ("unreadable", "", "", "")
        else:
            status, conclusion, head, name = (line.split("\t") + ["", "", ""])[:4]
            states[rid] = (status, conclusion, head, name)
        time.sleep(0.15)
    return states


def head_green(repo: str, heads: list[str]) -> dict[str, list[dict]]:
    """For each cited head: the completed/success runs GitHub lists AT that head
    (id + workflow name). The audit and the note renderer use it to say precisely
    whether the CITED workflow ever went green at the cited head — a green
    unrelated workflow at the same head does not re-prove a criterion."""
    facts: dict[str, list[dict]] = {}
    for head in sorted(heads):
        out = run_ok(["gh", "api",
                      f"repos/{repo}/actions/runs?head_sha={head}&per_page=100",
                      "--jq", '[.workflow_runs[] | select(.status == "completed" '
                              'and .conclusion == "success") | {id, name}]'])
        try:
            facts[head] = json.loads(out.stdout) if out.returncode == 0 and out.stdout.strip() else []
        except json.JSONDecodeError:
            facts[head] = []
        time.sleep(0.15)
    return facts


def issue_comments(repo: str, number: int) -> list[str]:
    docs = _gh_json([f"repos/{repo}/issues/{number}/comments", "--paginate"])
    return [c.get("body") or "" for c in docs if isinstance(c, dict)]


# ------------------------------------------------------------------- supersede notes


def render_supersede_note(issue: int,
                          entries: list[tuple[str, list[str], list[str]]],
                          run_states: dict[str, list[str]],
                          head_green: dict[str, list[dict]]) -> str:
    """The one renderer for a supersession note (never hand-built). entries:
    (criterion_line, cited_run_ids, conclusion_labels) exactly as `audit` found
    them; `run_states`/`head_green` are the stored measurements that let each
    criterion state, per cited head, whether the CITED workflow ever went green
    at that head."""
    lines = [
        SUPERSEDE_MARKER,
        "**Supersession note (#2288 sweep, follow-up #2631, append-only — ticks stay as written).**",
        "Measured by `scripts/audit_acceptance_ticks.py` (`make audit-ticks`): each cited run below "
        "reports the conclusion shown, and the head survey under each criterion records whether the "
        "CITED workflow ever produced a completed/success run at the cited head — green runs of "
        "unrelated workflows at the same head do not re-prove these criteria. These ticks are "
        "superseded, not rewritten: the issue stays closed on its merged implementation, and "
        "acceptance going forward is governed by the #2288 machinery "
        "(`scripts/check_pr_acceptance.py`, `scripts/acceptance_writeback.py`).",
    ]
    for line, run_ids, labels in entries:
        cited = ", ".join(f"run={r} ({labels[i]})" for i, r in enumerate(run_ids))
        lines.append(f"- cited: {cited}")
        lines.extend(_criterion_heads(run_ids, run_states, head_green))
        lines.append(f"> {line}")
    lines.append("")
    lines.append("Recorded stale by the AUDIT-2288 addendum; re-measure via `make audit-ticks` "
                 "(`scripts/audit_acceptance_ticks.py`).")
    return "\n".join(lines)


def _criterion_heads(run_ids: list[str], run_states: dict[str, list[str]],
                     head_green: dict[str, list[dict]]) -> list[str]:
    """One `  head <sha>: <fact>` line per distinct cited head."""
    per_head: dict[str, set[str]] = {}
    for rid in run_ids:
        st = run_states.get(rid) or ["unreadable", "", "", ""]
        head = st[2] if len(st) > 2 else ""
        if not head:
            continue
        per_head.setdefault(head, set()).add(st[3] if len(st) > 3 and st[3] else "<unknown-workflow>")
    out: list[str] = []
    for head, wfs in sorted(per_head.items()):
        greens = head_green.get(head, [])
        same = [g for g in greens if g.get("name") in wfs]
        wf_txt = "/".join(sorted(wfs))
        if same:
            fact = f"green run(s) of the cited workflow at this head: " \
                   f"{', '.join(str(g.get('id')) for g in same)}"
        elif greens:
            others = sorted({str(g.get("name", "?")) for g in greens})
            shown = ", ".join(others[:6]) + ("" if len(others) <= 6 else f" (+{len(others) - 6} more)")
            fact = (f"the cited workflow ({wf_txt}) never went green at this head; "
                    f"{len(greens)} green run(s) at the head belong to unrelated workflows: {shown}")
        else:
            fact = "no completed/success run exists at this head"
        out.append(f"  head {head[:10]}: {fact}")
    return out


def covered_criteria(comments: list[str]) -> set[str]:
    """Criterion lines covered by a SUPERSEDE-2288 note on the issue: the exact
    line the note quotes under `- cited:`."""
    covered: set[str] = set()
    for body in comments:
        if SUPERSEDE_MARKER not in body:
            continue
        quoted = False
        for line in body.splitlines():
            if line.startswith("- cited:"):
                quoted = True
            elif quoted and line.startswith("> "):
                covered.add(line[2:].strip())
            elif quoted and line.startswith("  head "):
                continue  # measured head-fact line, part of the same block
            elif quoted:
                quoted = False
    return covered


# ------------------------------------------------------------------------- audit


def collect_stale(repo: str, issues: list[dict], states: dict) -> dict[int, list[tuple[str, list[str], list[str]]]]:
    stale: dict[int, list[tuple[str, list[str], list[str]]]] = {}
    for issue in issues:
        body = issue.get("body") or ""
        for line in body.splitlines():
            if not TICK_RE.match(line):
                continue
            run_ids = RUN_RE.findall(line)
            if not run_ids:
                continue
            if any(states.get(r, ("unreadable", "", ""))[0] == "completed"
                   and states.get(r, ("unreadable", "", ""))[1] == "success" for r in run_ids):
                continue  # at least one green cited run -> honest tick
            stale.setdefault(int(issue["number"]), []).append((line.strip(), run_ids, []))
    return stale


def audit(repo: str, roster_path: Path, quiet: bool) -> int:
    issues = closed_issues(repo)
    ticks = [(int(i["number"]), l.strip(), RUN_RE.findall(l))
             for i in issues for l in (i.get("body") or "").splitlines()
             if TICK_RE.match(l) and RUN_RE.findall(l)]
    run_ids = sorted({r for _, _, rs in ticks for r in rs})
    states = run_states(repo, run_ids)
    stale = collect_stale(repo, issues, states)

    superseded: dict[int, list] = {}
    for num in list(stale):
        covered = covered_criteria(issue_comments(repo, num))
        keep = []
        for line, rs, _ in stale[num]:
            if line in covered:
                superseded.setdefault(num, []).append((line, rs))
            else:
                keep.append((line, rs, [states.get(r, ("unreadable", "", ""))[1] or
                                        states.get(r, ("unreadable", "", ""))[0] for r in rs]))
        if keep:
            stale[num] = keep
        else:
            del stale[num]

    # Head survey: for every head cited by a remaining stale criterion, the
    # completed/success runs GitHub lists at that head. Stored in the roster; the
    # note renderer states per criterion whether the CITED workflow ever went
    # green at its head (a green unrelated workflow never re-proves the tick).
    cited_heads = sorted({states[r][2]
                          for v in stale.values() for l, rs, _ in v for r in rs
                          if r in states and states[r][2]})
    green_at_head = head_green(repo, cited_heads)

    roster = {
        "counting_method": COUNTING_METHOD,
        "closed_issues": len(issues),
        "ticked_criteria_citing_runs": len(ticks),
        "stale": {str(k): [[l, rs, labs] for l, rs, labs in v] for k, v in sorted(stale.items())},
        "superseded": {str(k): [[l, rs] for l, rs in v] for k, v in sorted(superseded.items())},
        "run_states": {k: list(v) for k, v in states.items()},
        "head_green": green_at_head,
    }
    roster_path.parent.mkdir(parents=True, exist_ok=True)
    roster_path.write_text(json.dumps(roster, indent=1), encoding="utf-8")

    n_stale = sum(len(v) for v in stale.values())
    n_super = sum(len(v) for v in superseded.values())
    if not quiet:
        print(f"closed issues paged: {len(issues)}")
        print(f"ticked criteria citing run=<id>: {len(ticks)}")
        print(f"stale (unsuperseded) ticks: {n_stale} across {len(stale)} issues")
        print(f"superseded (SUPERSEDE-2288 covered): {n_super} across {len(superseded)} issues")
        print(f"counting method: {COUNTING_METHOD}")
        print(f"roster: {roster_path}")
    return 0 if n_stale == 0 else 1


# ------------------------------------------------------------------------- notes/post


def notes(repo: str, roster_path: Path, notes_dir: Path) -> int:
    roster = json.loads(roster_path.read_text(encoding="utf-8"))
    notes_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for num_str, entries in roster["stale"].items():
        rendered = render_supersede_note(
            int(num_str),
            [(line, rs, labs) for line, rs, labs in entries],
            roster["run_states"], roster.get("head_green", {}))
        (notes_dir / f"{num_str}.md").write_text(rendered, encoding="utf-8")
        written += 1
    print(f"supersession notes rendered: {written} -> {notes_dir}")
    return 0


def post(repo: str, roster_path: Path, notes_dir: Path) -> int:
    roster = json.loads(roster_path.read_text(encoding="utf-8"))
    posted = skipped = 0
    for num_str in roster["stale"]:
        num = int(num_str)
        if any(SUPERSEDE_MARKER in body for body in issue_comments(repo, num)):
            skipped += 1
            continue
        body = (notes_dir / f"{num_str}.md").read_text(encoding="utf-8")
        # The payload travels as a file, not piped stdin: main's `run_checked` still
        # absorbs unknown kwargs, and forwarding `input` is PR #2633's lane, not this one.
        payload = notes_dir / "post-payload.json"
        payload.write_text(json.dumps({"body": body}), encoding="utf-8")
        run_checked(
            ["gh", "api", "-X", "POST", f"repos/{repo}/issues/{num}/comments",
             "--input", str(payload)],
        )
        posted += 1
        time.sleep(0.2)
    print(f"supersession notes posted: {posted}; skipped (marker already on the issue): {skipped}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="audit_acceptance_ticks", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def _common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--repo", default=BASE_REPO)

    a = sub.add_parser("audit", help="re-measure the tick corpus; exit 0 only when no unsuperseded stale tick remains")
    _common(a)
    a.add_argument("--roster", required=True)
    a.add_argument("--quiet", action="store_true")
    n = sub.add_parser("notes", help="render supersession comment bodies from the roster")
    _common(n)
    n.add_argument("--roster", required=True)
    n.add_argument("--notes-dir", required=True)
    p = sub.add_parser("post", help="append-only idempotent posting of the rendered notes")
    _common(p)
    p.add_argument("--roster", required=True)
    p.add_argument("--notes-dir", required=True)

    args = ap.parse_args(argv)
    if args.cmd == "audit":
        return audit(args.repo, Path(args.roster), args.quiet)
    if args.cmd == "notes":
        return notes(args.repo, Path(args.roster), Path(args.notes_dir))
    return post(args.repo, Path(args.roster), Path(args.notes_dir))


if __name__ == "__main__":
    raise SystemExit(main())
