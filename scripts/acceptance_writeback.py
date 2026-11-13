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


def _is_acceptance_heading(line: str) -> bool:
    """True when `line` is a `##` heading whose text is (or starts with) `Acceptance criteria`.

    The write-back ticks the acceptance seam leniently: a producer may author a
    human-readable heading such as `## Acceptance criteria (what closing means)`
    (issue #1800). `issue_body.section_body` deliberately stays exact-match (#745
    canonical form check); the lenient prefix match lives here, in the seam only.
    """
    m = _HEADING_RE.match(line)
    return bool(m) and m.group(1).strip().startswith("Acceptance criteria")


def _acceptance_section(body: str) -> str | None:
    """The text under the first `## Acceptance criteria...` heading (prefix match).

    Returns `None` when no such heading exists, so the caller can emit a canary
    naming the headings actually present (issue #1802: absence is distinguishable
    from a spelling variant).
    """
    lines = (body or "").splitlines()
    start = None
    for i, line in enumerate(lines):
        if _is_acceptance_heading(line):
            start = i
            break
    if start is None:
        return None
    rest = lines[start + 1:]
    end = next((i for i, line in enumerate(rest) if _HEADING_RE.match(line)), len(rest))
    return "\n".join(rest[:end])


def _found_headings(body: str) -> list[str]:
    """Every `##` heading text, in order — the canary for a missing acceptance section."""
    return [m.group(1).strip() for m in _HEADING_RE.finditer(body or "")]


def acceptance_items(body: str) -> list[str]:
    """Every acceptance checkbox line (`- [ ]` / `- [x]`), in order.

    Only items inside `## Acceptance criteria` count — a checkbox in a spec or a
    README is not an acceptance criterion and the seam must not silently flip it.
    The heading match is lenient (prefix, see `_is_acceptance_heading`): a suffix
    like `(what closing means)` still selects the section (issue #1802).
    """
    section = _acceptance_section(body)
    if section is None:
        headings = _found_headings(body)
        found = ", ".join(f"`## {h}`" for h in headings) if headings else "none"
        raise BodyError("the body has no `## Acceptance criteria` section "
                        f"(found headings: {found})")
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
        if not _HEADING_RE.match(line):
            continue
        if start is None and _is_acceptance_heading(line):
            start = i
        elif start is not None:
            end = i
            break
    if start is None:
        headings = _found_headings(body)
        found = ", ".join(f"`## {h}`" for h in headings) if headings else "none"
        raise BodyError("the body has no `## Acceptance criteria` heading "
                        f"(found headings: {found})")
    return start, (end if end is not None else len(lines))


def _unticked_text(line: str) -> str:
    m = CHECKBOX_RE.match(line)
    return m.group("rest").strip() if m else ""


#: Grammar floor (#2288): a verdict-ref must name the tree its evidence measured — a 7–40-char hex
#: head sha. Reviewer names, review ids and run ids are decimal identifiers, not shas; a ref with
#: no sha cannot be re-checked against any revision, so the seam refuses to stamp one.
HEAD_SHA_REF = re.compile(r"\b[0-9a-f]{7,40}\b")
#: Run citations inside a verdict-ref; the `writeback` command proves each GREEN live before a tick (#2288).
RUN_REF = re.compile(r"\brun\s*=\s*(\d+)")


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
    if not HEAD_SHA_REF.search(ref):
        raise BodyError("the verdict-ref names no measured head sha — a tick must pin the tree it "
                        "measured (issue #2288): reviewer/comment/run ids are not shas")

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


def assert_runs_green(gh: str, repo: str, ref: str) -> None:
    """Every `run=<id>` a verdict-ref cites must have CONCLUDED GREEN before a tick is written (#2288).

    Measured roster: 11 accepted ticks cited 4 runs that ended failure/cancelled — the seam stamped
    whatever `--verdict-ref` it was handed. This refuses with `BodyError` naming the run and its
    conclusion (issue #2288: the seam raises evidence it cannot vouch for), so no tick is ever
    stamped from evidence that failed; refs citing no run (reviewer/comment + head sha form) pass
    through to the grammar floor in `tick_acceptance`.
    """
    for m in RUN_REF.finditer(str(ref or "")):
        rid = int(m.group(1))
        r = run_ok([gh, "api", f"repos/{repo}/actions/runs/{rid}",
                    "--jq", "[.status, .conclusion, .head_sha] | @tsv"])
        parts = (r.stdout or "").strip().split("\t") if r.returncode == 0 else []
        status = parts[0].strip() if parts else ""
        if r.returncode != 0 or not status or status == "null":
            raise BodyError(f"run {rid} is unreadable via `gh api repos/{repo}/actions/runs/{rid}` "
                            f"— a verdict-ref may not cite what the writer cannot read (issue #2288)")
        conclusion = (parts[1] if len(parts) > 1 else "").strip().lower()
        if conclusion != "success" or status.lower() != "completed":
            raise BodyError(f"run {rid} concluded `{conclusion or status}` — only a completed "
                            f"`success` run proves a ticked criterion (issue #2288)")


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

    # #2288: the live write-back proves each cited run GREEN before any tick is computed or PATCHed.
    assert_runs_green(args.gh, args.repo, args.verdict_ref)
    body = _fetch_body(args.gh, args.repo, args.issue)
    out = tick_acceptance(body, _proven(args.proven), args.verdict_ref)
    _write(args.gh, args.repo, args.issue, out, args.dry)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
