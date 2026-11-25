#!/usr/bin/env python3
"""Re-render the already-open engine-bump PR bodies through the seam (issue #3054).

Issue #3050 (PR #3058) gave the engine-bump lane ONE body composer, `make engine-bump-pr-body`
(`scripts/engine_bump_pr_body.py`), so a bump body can no longer glue a heading onto its `OPENSPEC:` line.
That fix only reaches the NEXT wave: the pull requests the 2026-11-23 wave already opened (#3029 ollama,
#3030 vllm, #3031 tensorrt-llm, #3032 llama.cpp-prism, #3033 llama.cpp, #3034 tensorfold, #3035 edge0) still
carry the glued bodies, so `guard` (`check-pr-openspec-change`) and `scope` (`check-pr-acceptance-form`) stay
red and they sit at `mergeStateStatus=BLOCKED`.

This leg closes that gap:

* it reads the bump facts from each open `chore/engine-bump-*` PR's LIVE body (never assumes them);
* it classifies each bump against the pin `main` ACTUALLY carries, read from
  `skills/engines/<engine>/SKILL.md`'s frontmatter `pinned:` on `main`: `pending` (main still holds the
  bump's old pin), `landed` (main already holds its new pin) or `superseded` (main moved to a third pin);
* a `pending` bump's body is re-rendered through the SAME composer (`render_body`), stamped through the
  `make bot-stamp-body` authority (`scripts/bot_preflight.py --stamp`, issue #2050) and written only through
  the guarded seam `scripts/pr_body_write.py` (`make bot-body-write`, issue #2131) — a raw
  `gh pr edit --body-file` is never issued here, because the seam is what refuses a write that drops a
  heading or a proven tick;
* a `landed`/`superseded` bump is closed with main's live pin as the evidence instead of being re-stamped, so
  a stale pin bump never masquerades as pending work. It is closed, never merged: the agent does not merge
  (AGENTS.md), CI's auto-merge job or a human lands the rest.

Dry by default: without `--apply` nothing is written, and without `--close-superseded` nothing is closed.
This script dispatches no CI pipeline (issue #2701): the body write itself is the GitHub event that makes the
PR's push lane re-read the body gates.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import proc  # the ONE subprocess policy (issue #797)
from check_pr_hygiene import OPENSPEC_REF  # the gate this leg must satisfy (issue #3050)
from engine_bump_pr_body import ACCEPTANCE_HEADING, DEFAULT_OPENSPEC, render_body

DEFAULT_REPO = "asimov-agent/llgenie"
BUMP_BRANCH_PREFIX = "chore/engine-bump-"
MAIN_REF = "main"
DEFAULT_AUTHOR = "Asimov Agent <support@docondee.com>"

# The composer's own fact lines (scripts/engine_bump_pr_body.py), read back off the live body.
ENGINE_LINE = re.compile(r"^- \*\*Engine:\*\* `([^`]+)`\s*$", re.M)
PIN_LINE = re.compile(r"^- \*\*Pin:\*\* `([0-9a-f]{7,40})` -> `([0-9a-f]{7,40})` \(`([^`]+)`\)\s*$", re.M)
COMPARE_LINE = re.compile(r"compare/([0-9a-f]{40})\.\.\.([0-9a-f]{40})", re.M)
HARD_FAIL_LINE = re.compile(r"\*\*Manual review required:\*\* (.*)$", re.M)
DEPS_LINE = re.compile(r"^- \*\*Dependencies:\*\* (.*)$", re.M)
#: The #3054 defect: the change name runs STRAIGHT INTO a heading (`…pin-images## Documentation review`).
#: Anchored on the `#`, because a well-composed reference line ENDS after the name (`OPENSPEC_REF`):
#: a trailing `\S.*` backtracks into the name and reports every clean composer body as defective.
GLUED_OPENSPEC_LINE = re.compile(r"^OPENSPEC:\s*[A-Za-z0-9_-]+#", re.M)
OPENSPEC_LINE = re.compile(r"^OPENSPEC:", re.M)
#: Where the documentation-review section starts, glued onto the reference line or on its own line.
REVIEW_START = re.compile(r"^#{2,3} Documentation review|^#{2,3} Engine params review", re.M)
#: The composer opens every section on a line-start heading, so the review ENDS at the next one: the
#: acceptance checklist (or the section that stands in for it) is review text never.
NEXT_SECTION = re.compile(r"^#{2,3} ", re.M)
STAMP_LINE = re.compile(r"^(AGENTS|BASE): ", re.M)
PINNED_FIELD = re.compile(r"^pinned:\s*([0-9a-f]{7,40})\s*$", re.M)

# pending = main holds the bump's old pin -> re-stamp it.
# landed  = main already holds the bump's new pin -> close as already overtaken.
# superseded = main holds a third pin -> close as overtaken.
PENDING, LANDED, SUPERSEDED = "pending", "landed", "superseded"
KNOWN_KINDS = (PENDING, LANDED, SUPERSEDED, "unknown-pin")


@dataclass
class BumpPr:
    number: str
    title: str
    branch: str
    head_sha: str
    engine: str = ""
    ref: str = ""
    old_sha: str = ""
    new_sha: str = ""
    review: str = ""
    hard_fail: str = ""
    deps: str = ""
    run_id: str = ""
    kind: str = ""
    main_pin: str = ""
    defect: str = ""
    body_path: Path | None = None
    problems: list[str] = field(default_factory=list)
    failing: list[str] = field(default_factory=list)


def open_bump_prs(repo: str) -> list[BumpPr]:
    """Every OPEN bump PR, oldest-number-first (the wave's own order)."""
    out = proc.run_text(["gh", "pr", "list", "--repo", repo, "--state", "open", "--limit", "60",
                         "--json", "number,title,headRefName,headRefOid"], timeout=120)
    rows = json.loads(out)
    bumps = [BumpPr(number=str(r["number"]), title=r.get("title", ""),
                    branch=r.get("headRefName", ""), head_sha=r.get("headRefOid", ""))
             for r in rows if r.get("headRefName", "").startswith(BUMP_BRANCH_PREFIX)]
    return sorted(bumps, key=lambda b: int(b.number))


def live_body(repo: str, number: str) -> str:
    return proc.run_text(["gh", "pr", "view", number, "--repo", repo, "--json", "body",
                          "-q", ".body"], timeout=120)


def read_facts(bump: BumpPr, body: str) -> list[str]:
    """Extract the composer's facts (and the review section) from the live body; name what is missing."""
    problems: list[str] = []
    if (m := ENGINE_LINE.search(body)):
        bump.engine = m.group(1)
    else:
        problems.append("no `- **Engine:**` line")
    if (m := PIN_LINE.search(body)):
        bump.old_sha, bump.new_sha, bump.ref = m.group(1), m.group(2), m.group(3)
    else:
        problems.append("no `- **Pin:** old -> new (ref)` line")
    if (m := COMPARE_LINE.search(body)):
        # The compare URL carries the FULL shas; trust them over the 8-char pin line and verify they agree.
        if bump.old_sha and not m.group(1).startswith(bump.old_sha):
            problems.append(f"compare old sha {m.group(1)[:8]} disagrees with the pin line {bump.old_sha}")
        if bump.new_sha and not m.group(2).startswith(bump.new_sha):
            problems.append(f"compare new sha {m.group(2)[:8]} disagrees with the pin line {bump.new_sha}")
        bump.old_sha, bump.new_sha = m.group(1), m.group(2)
    elif not problems:
        problems.append("no full compare shas")
    if (m := HARD_FAIL_LINE.search(body)):
        bump.hard_fail = m.group(1).strip()
    if (m := DEPS_LINE.search(body)):
        bump.deps = m.group(1).strip()
    if (m := REVIEW_START.search(body)):
        tail = body[m.start():]
        # Cut the review where the composer's NEXT section heading, the stamp pair or the reference line
        # begins: the acceptance checklist is never review text, and nothing gets embedded twice.
        cut = len(tail)
        if (nxt := NEXT_SECTION.search(body, m.end())):
            cut = min(cut, nxt.start() - m.start())
        for pat in (STAMP_LINE, OPENSPEC_LINE):
            if (c := pat.search(tail)):
                cut = min(cut, c.start())
        bump.review = tail[:cut].strip()
    if GLUED_OPENSPEC_LINE.search(body):
        bump.defect = "glued OPENSPEC line"
    elif not OPENSPEC_REF.search(body):
        bump.defect = "no resolvable OPENSPEC reference"
    elif ACCEPTANCE_HEADING not in body:
        bump.defect = "no own acceptance criteria section"
    return problems


def main_pin(repo: str, engine: str) -> str:
    """The pin `main` actually carries for this engine (frontmatter `pinned:`), '' when unreadable."""
    try:
        raw = proc.run_text(["gh", "api", f"repos/{repo}/contents/skills/engines/{engine}/SKILL.md",
                             "--jq", ".content"], timeout=120)
    except Exception as exc:  # a missing/renamed skill is reported, never guessed
        print(f"[restamp] main pin read failed for {engine}: {exc}", file=sys.stderr)
        return ""
    text = base64.b64decode(raw.strip()).decode("utf-8", "replace")
    m = PINNED_FIELD.search(text)
    return m.group(1) if m else ""


def classify_against(bump: BumpPr, main_pin: str) -> str:
    """Compare the bump against main's live pin; only a `pending` bump may be re-stamped."""
    bump.main_pin = main_pin
    if not main_pin:
        bump.kind = "unknown-pin"
    elif main_pin.startswith(bump.new_sha) or bump.new_sha.startswith(main_pin):
        bump.kind = LANDED
    elif main_pin.startswith(bump.old_sha) or bump.old_sha.startswith(main_pin):
        bump.kind = PENDING
    else:
        bump.kind = SUPERSEDED
    return bump.kind


RUN_LINK = re.compile(r"/runs/(\d+)")


def lane_runs(repo: str, number: str) -> tuple[str, list[str]]:
    """The bump lane's own (newest run id, failing job names) for the PR's CURRENT head.

    `gh pr checks` reports the checks GitHub evaluated on the live head, and each link names the run
    that produced it — so the newest id is replayable evidence for the stamp's proven clause, and the
    failing job names are what this leg is trying to turn green.
    """
    try:
        rows = json.loads(proc.run_text(["gh", "pr", "checks", number, "--repo", repo,
                                         "--json", "name,bucket,link"], timeout=180))
    except Exception as exc:
        print(f"[restamp] pr checks failed for #{number}: {exc}", file=sys.stderr)
        return "", []
    ids = {int(m.group(1)) for r in rows for m in [RUN_LINK.search(r.get("link") or "")] if m}
    failing = sorted({r["name"] for r in rows if r.get("bucket") in ("fail", "cancel")})
    return (str(max(ids)) if ids else ""), failing


def render_for(bump: BumpPr, repo_slug: str = DEFAULT_REPO) -> str:
    """The replacement body: the SAME composer #3050 landed, with the live body's review section kept."""
    return render_body(engine=bump.engine, ref=bump.ref, old_sha=bump.old_sha, new_sha=bump.new_sha,
                       run_id=bump.run_id, author=DEFAULT_AUTHOR, repo_slug=repo_slug,
                       openspec=DEFAULT_OPENSPEC, hard_fail=bump.hard_fail, deps=bump.deps,
                       review_section=bump.review)


def close_comment(bump: BumpPr) -> str:
    return (f"This bump is closed as overtaken, not re-stamped. `main` currently pins `{bump.engine}` at "
            f"`{bump.main_pin[:12]}`; this PR proposed `{bump.new_sha[:8]}` from `{bump.old_sha[:8]}`, so main "
            f"{'already holds' if bump.kind == LANDED else 'moved past'} that pin and re-stamping this body "
            f"would leave a stale pin bump masquerading as pending work. Re-open it only if the pin it "
            f"proposed is the pin main should move to. Issue #3054.")


def process(repo: str, apply: bool, close_superseded: bool, out_dir: Path) -> dict[str, int]:
    tally = {k: 0 for k in KNOWN_KINDS}
    tally.update({"written": 0, "closed": 0, "refused": 0, "unstamped": 0, "unchanged": 0})
    bumps = open_bump_prs(repo)
    if not bumps:
        print(f"[restamp] no open {BUMP_BRANCH_PREFIX}* pull requests in {repo}")
        return tally
    for bump in bumps:
        body = live_body(repo, bump.number)
        bump.problems = read_facts(bump, body)
        bump.run_id, bump.failing = lane_runs(repo, bump.number)
        tally[classify_against(bump, main_pin(repo, bump.engine) if bump.engine else "")] += 1
        line = (f"#{bump.number} engine={bump.engine or '?'} {bump.kind} "
                f"old={bump.old_sha[:8] or '?'} new={bump.new_sha[:8] or '?'} "
                f"main-pin={bump.main_pin[:8] or '?'} run={bump.run_id or '-'} "
                f"defect={bump.defect or 'none'}")
        if bump.failing:
            line += f" red-lane={', '.join(bump.failing)}"
        if bump.problems:
            line += f" UNPARSED={'; '.join(bump.problems)}"
        if bump.kind == PENDING:
            if not bump.run_id:
                print(line + " SKIP=no lane run id (a proven clause must be replayable)")
                continue
            text = render_for(bump, repo)
            out_dir.mkdir(parents=True, exist_ok=True)
            bump.body_path = out_dir / f"pr-{bump.number}-body.md"
            bump.body_path.write_text(text, encoding="utf-8")
            line += f" body={bump.body_path}"
            print(line)
            if apply:
                # The stamp authority (make bot-stamp-body) then the guarded write seam (make bot-body-write).
                py = sys.executable or "python3"
                try:
                    stamp = proc.run_checked([py, str(REPO_ROOT / "scripts" / "bot_preflight.py"),
                                              "--stamp", str(bump.body_path)], timeout=180)
                except proc.ProcError as exc:
                    tally["unstamped"] += 1
                    print(f"[restamp] #{bump.number} the stamp authority refused ({exc}); nothing written")
                    continue
                print(f"[restamp] #{bump.number} stamped: {stamp.strip().splitlines()[-2:]}")
                try:
                    written = proc.run_checked([py, str(REPO_ROOT / "scripts" / "pr_body_write.py"),
                                                "--repo", repo, "--pr", bump.number,
                                                "--new", str(bump.body_path)], timeout=180)
                except proc.ProcError as exc:
                    tally["refused"] += 1
                    print(f"[restamp] #{bump.number} the guarded seam refused the write ({exc}); "
                          f"the live body stands")
                    continue
                if "no write:" in written:
                    tally["unchanged"] += 1
                    print(f"[restamp] #{bump.number} the live body already carries this body; nothing written")
                    continue
                if "write refused" in written:
                    tally["refused"] += 1
                    print(f"[restamp] #{bump.number} the guarded seam declined the write; the live body stands")
                    continue
                tally["written"] += 1
                print(f"[restamp] #{bump.number} seam: {written.strip()}")
                after = live_body(repo, bump.number)
                ok = bool(OPENSPEC_REF.search(after)) and ACCEPTANCE_HEADING in after
                print(f"[restamp] #{bump.number} re-read after the write: "
                      f"OPENSPEC={'resolvable' if ok else 'STILL NOT RESOLVABLE'}")
        else:
            print(line)
            if apply and close_superseded and bump.kind in (LANDED, SUPERSEDED) and bump.main_pin:
                note = close_comment(bump)
                proc.run_checked(["gh", "pr", "close", bump.number, "--repo", repo, "--comment", note])
                tally["closed"] += 1
                print(f"[restamp] #{bump.number} closed as overtaken: {note}")
    print("[restamp] tally " + " ".join(f"{k}={v}" for k, v in tally.items()))
    return tally


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Re-render the open engine-bump PR bodies through the composer + guarded write seam (issue #3054).")
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--apply", action="store_true",
                    help="write the re-rendered bodies through make bot-body-write (default: dry, writes nothing)")
    ap.add_argument("--close-superseded", action="store_true",
                    help="with --apply: close landed/superseded bumps with main's live pin as the evidence")
    ap.add_argument("--out-dir", default="/tmp/engine-bump-restamp", help="where the rendered bodies land")
    a = ap.parse_args(argv)
    process(a.repo, a.apply, a.close_superseded, Path(a.out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
