#!/usr/bin/env python3
"""Tick the acceptance criteria a review verdict proved, on the issue body (issue #1644).

An issue's `## Acceptance criteria` — the repository's own definition of "done"
(issue #745: "a criterion a reviewer cannot tick is not one") — was never
transcribed: a PR merge ticked nothing, so a closed issue read 5/5 `- [ ]`
even after a reviewer's COMMENTED verdict proved every criterion.

This seam turns the write-back into a checked state:

* on a reviewed-green merge, the lane holding the verdict calls this on the
  target issue with the acceptance items the verdict proved;
* it ticks exactly those `- [ ]` items to `- [x]` in the issue body, and leaves
  every item the verdict did NOT prove unticked (and names it);
* the tick carries provenance — the proving verdict's reviewer + review id +
  head sha + run id — so a reader goes from the tick to the measured evidence.

Bounding (issue #1644): the write-back is driven by a COMMENTED verdict, never
by the merge itself. An auto-merged PR with no reviewer verdict (#1088-class)
ticks nothing — an un-reviewed merge stays honest (boxes unticked). The seam
is the only thing that mutates an acceptance box to `- [x]`.

The transformation is pure and stdlib-only so the unit suite proves it on a
bare host; the GitHub write is the thin `gh api PATCH` wrapper around it.

Usage:
    acceptance_writeback.py apply    --body-file BODY --proven 1,3 --verdict-ref '...'
    acceptance_writeback.py writeback --issue N --proven 1,3 --verdict-ref '...' [--dry]
    acceptance_writeback.py check    --body-file BODY --proven 1,3 --verdict-ref '...'

Exit codes: 0 ok, 2 a `gh` call failed or a body is not writable-shaped.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import issue_body  # noqa: E402  (the one issue shape, #745)
from proc import run_ok, run_checked  # noqa: E402  the subprocess policy seam (issue #797)

BASE_REPO = "asimov-agent/llgenie"
CHECKBOX_RE = re.compile(r"^(\s*-\s+)\[(?P<state> |x|X)\](?P<rest>.*)$")
PROVEN_SUFFIX = "proven:"            # inline marker on a ticked line
UNPROVEN_PREFIX = "unproven:"        # the naming bullet
#: An existing `(proven: ...)` suffix already on a ticked line (idempotence).
_PROVEN_ON_LINE = re.compile(r"\s*\(proven:[^)]*\)\s*$")
#: An existing `- unproven:` naming bullet already in the section (idempotence).
_UNPROVEN_BULLET = re.compile(r"^-\s*unproven:.*$")
_HEADING_RE = issue_body.HEADING_RE


class BodyError(ValueError):
    """A body the seam refuses to modify."""


def acceptance_items(body: str) -> list[str]:
    """Every acceptance checkbox line (`- [ ]` / `- [x]`), in order.

    Only items inside `## Acceptance criteria` count — a checkbox in a spec or a
    README is not an acceptance criterion and the seam must not silently flip it.
    """
    section = issue_body.section_body(body, "Acceptance criteria")
    if not section:
        raise BodyError("the body has no `## Acceptance criteria` section")
    items = []
    for line in section.splitlines():
        if CHECKBOX_RE.match(line):
            items.append(line)
    return items


def _bounds(body: str) -> tuple[int, int]:
    """(line-index of the `## Acceptance criteria` heading, end of its section).

    `end` is the line index of the next `##` heading, or `len(lines)` when the
    acceptance section is the final section. `Technical` is the last section of
    the repository shape, so the criteria precede it in practice.
    """
    lines = body.splitlines()
    start = end = None
    for i, line in enumerate(lines):
        m = _HEADING_RE.match(line)
        if not m:
            continue
        if start is None and m.group(1).strip() == "Acceptance criteria":
            start = i
        elif start is not None:
            end = i
            break
    if start is None:
        raise BodyError("the body has no `## Acceptance criteria` heading")
    return start, (end if end is not None else len(lines))


def _unticked_text(line: str) -> str:
    m = CHECKBOX_RE.match(line)
    return m.group("rest").strip() if m else ""


def tick_acceptance(body: str, proven: set[int], verdict_ref: str) -> str:
    """Return `body` with acceptance items at 1-based `proven` positions ticked.

    A ticked line becomes `- [x] <text>  (proven: <verdict-ref>)`; an unproven
    item keeps its exact `- [ ] <text>` line. One `- unproven:` bullet is appended
    at the end of the acceptance section naming every item the verdict did NOT
    prove (`1. <text>` order positions kept so a reader can map them back).
    Idempotent: a line already `- [x]` in `proven` stays ticked.
    """
    items = acceptance_items(body)
    if not items:
        raise BodyError("`## Acceptance criteria` carries no `- [ ]` item")
    proven_num = {int(i) for i in proven}
    if not proven_num:
        raise BodyError("no proven items given — a write-back with an empty verdict is not one")
    invalid = [i for i in proven_num if not (1 <= i <= len(items))]
    if invalid:
        raise BodyError(f"proven {sorted(invalid)} outside the {len(items)} acceptance items")
    ref = str(verdict_ref).strip()
    if not ref:
        raise BodyError("a write-back must name the proving verdict (reviewer/review/sha/run)")

    lines = body.splitlines()
    start, end = _bounds(body)

    # Rebuild the acceptance section lines in place, by original position.
    item_ord = 0
    rebuilt: list[str] = []
    for i, line in enumerate(lines[start + 1:end]):
        m = CHECKBOX_RE.match(line)
        if not m:
            if _UNPROVEN_BULLET.match(line):
                continue  # replace this old naming bullet with the freshly computed one below
            rebuilt.append(line)
            continue
        item_ord += 1
        text = _PROVEN_ON_LINE.sub("", m.group("rest")).strip()
        if item_ord in proven_num:
            rebuilt.append(f"- [x] {text}  ({PROVEN_SUFFIX} {ref})")
        else:
            rebuilt.append(f"- [ ] {text}")

    # The `- unproven:` bullet naming what stayed unticked (in order).
    unproven = [f"{i}. {_unticked_text(it)}" for i, it in enumerate(items, 1) if i not in proven_num]
    if unproven:
        rebuilt.append(f"- {UNPROVEN_PREFIX} " + "; ".join(unproven))

    return "\n".join(lines[:start + 1] + rebuilt + lines[end:]).rstrip("\n") + "\n"


def _write(gh: str, repo: str, issue: int, body: str, dry: bool = False) -> None:
    """PATCH the issue body. This is the ONE write that touches issue text."""
    if dry:
        print(f"[acceptance-writeback] would PATCH #{issue} body ({len(body)} chars)")
        return
    r = run_ok([gh, "api", "--method", "PATCH",
                f"repos/{repo}/issues/{issue}",
                "-f", f"body={body}"])
    if r.returncode != 0:
        raise SystemExit(f"[acceptance-writeback] PATCH #{issue} failed ({r.returncode}): " + (r.stderr or "").strip())
    print(f"[acceptance-writeback] PATCHED #{issue}")


def _fetch_body(gh: str, repo: str, issue: int) -> str:
    out = run_checked([gh, "issue", "view", str(issue), "--repo", repo, "--json", "body"])
    return json.loads(out)["body"]


def _proven(arg: str) -> set[int]:
    out = set()
    for token in arg.split(","):
        token = token.strip()
        if not token:
            continue
        out.add(int(token))
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="acceptance_writeback", description=(__doc__ or "").splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("apply", "check"):
        c = sub.add_parser(name)
        c.add_argument("--body-file", required=True)
        c.add_argument("--proven", required=True, help="comma-separated 1-based item positions")
        c.add_argument("--verdict-ref", required=True, help="reviewer + review id + head sha + run id")
    wp = sub.add_parser("writeback")
    wp.add_argument("--issue", required=True, type=int)
    wp.add_argument("--proven", required=True)
    wp.add_argument("--verdict-ref", required=True)
    wp.add_argument("--repo", default=BASE_REPO)
    wp.add_argument("--gh", default="gh")
    wp.add_argument("--dry", action="store_true")
    args = p.parse_args(argv)

    if args.cmd in ("apply", "check"):
        body = Path(args.body_file).read_text()
        out = tick_acceptance(body, _proven(args.proven), args.verdict_ref)
        if args.cmd == "check":
            # `check` verifies the write-back happened: at least one box ticked,
            # and an unproven box still unticked (the honest #1088 contrast).
            if "- [x]" not in out or "- [ ]" not in out:
                raise BodyError("write-back did not leave both a ticked and an unticked box")
            return 0
        sys.stdout.write(out)
        return 0

    body = _fetch_body(args.gh, args.repo, args.issue)
    out = tick_acceptance(body, _proven(args.proven), args.verdict_ref)
    _write(args.gh, args.repo, args.issue, out, args.dry)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
