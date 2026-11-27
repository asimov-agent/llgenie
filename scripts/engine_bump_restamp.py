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
from engine_bump_pr_body import (ACCEPTANCE_CLAIMS, ACCEPTANCE_HEADING, DEFAULT_OPENSPEC,
                                 acceptance_items, render_body)

#: Issue #3076: the producer side also has to restamp the COMMIT text. The reader gates already
#: refuse draft stubs in a commit's `(proven: ...)` clauses (`check_pr_acceptance.DRAFT_STUB` and
#: `check_pr_hygiene._COMMIT_PROVEN_STUB`, issue #3075), but the bump lane used to push its commit
#: with the composer's assumptions instead of the measured proof. The commit mirror is rendered
#: by the SAME composer (`acceptance_items`) the body uses; only the BLOCK is replaced, so a
#: lane's subject and its non-acceptance paragraphs are byte-preserved.
COMMIT_ACCEPTANCE_HEADING = "## Acceptance:"
DRAFT_STUB = re.compile(r"\b(?:PLACEHOLDER|HEADSHA|MAINSHA)\b")
ANY_HEADING = re.compile(r"^#{1,6}\s")

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
#: A heading that begins INSIDE a line (the #3031 shape: `…apt_removed=## Documentation review`).
GLUED_HEADING = re.compile(r"##")
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
    evidence_gaps: list[str] = field(default_factory=list)
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
    review_at: int | None = None
    scan_from: int = 0
    if (m := REVIEW_START.search(body)):
        review_at, scan_from = m.start(), m.end()
    if (m := DEPS_LINE.search(body)):
        fields = m.group(1)
        # The measured #3031 residue: the producer glued the review heading onto the END of its own
        # field line (`…apt_removed=## Documentation review`), so the heading is not a line start and
        # REVIEW_START cannot see it. The dependency fields are four `key=value` pairs and can never
        # contain a heading, so the first `##` ENDS the field line and starts the section the
        # composer owns — cut there and re-home the heading instead of carrying it inside the fields.
        if (g := GLUED_HEADING.search(fields)):
            fields = fields[: g.start()]
            glued_at = m.start(1) + g.start()
            if review_at is None or glued_at < review_at:
                review_at, scan_from = glued_at, m.end()
        bump.deps = fields.strip()
    if review_at is not None:
        tail = body[review_at:]
        # Cut the review where the composer's NEXT section heading, the stamp pair or the reference line
        # begins: the acceptance checklist is never review text, and nothing gets embedded twice.
        cut = len(tail)
        if (nxt := NEXT_SECTION.search(body, scan_from)):
            cut = min(cut, nxt.start() - review_at)
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


#: Where the pin and the frozen params actually live, and how the image lane names its runs.
#: `gh pr checks` ids are CHECK SUITE ids, not workflow run ids: `gh api repos/<repo>/actions/runs/
#: <suite id>` 404s (measured on #3029: suite `137942170961`), and `check_pr_acceptance.py` reports
#: `tick-run-unreadable` for a clause that cites one (issue #2288). The workflow run id is read from
#: each check run html_url (`.../actions/runs/<id>`), which IS readable.
ENGINE_BUILD_PREFIX = "engine-build-"
SKILL_PATH_TMPL = "skills/engines/{engine}/SKILL.md"
PARAMS_PATH_TMPL = "containers/engines/params/{engine}.json"
RUN_URL_RE = re.compile(r"/actions/runs/(\d+)")


def pr_files(repo: str, number: str) -> list[str]:
    """Every path the PR touches (the changed files at the head)."""
    out = proc.run_text(["gh", "pr", "view", number, "--repo", repo, "--json", "files",
                         "-q", ".files[].path"], timeout=120)
    return [ln for ln in out.splitlines() if ln.strip()]


def repo_file_at(repo: str, path: str, ref: str) -> tuple[str, str]:
    """The text of a file at a commit, read through the git BLOB API (no checkout needed).

    The contents endpoint with `?ref=<sha>` is NOT safe here: measured on #3033, the same request
    (`contents/skills/engines/llama.cpp/SKILL.md?ref=cf5208ba…`) served main's older blob (pinning
    `7d7f0287…`) once and the head blob (pinning `23924232…`) on the next call — a cached read that
    would make a proven clause describe a commit the PR does not carry. Git objects are immutable, so
    the tree of the head commit is resolved first and the blob sha is fetched by id.
    """
    out = proc.run_text(["gh", "api", f"repos/{repo}/git/trees/{ref}?recursive=1", "--jq",
                         f'.tree[] | select(.path == "{path}") | .sha'], timeout=180)
    blob_sha = out.strip().splitlines()[0].strip() if out.strip() else ""
    if not blob_sha:
        return "", ""
    raw = proc.run_text(["gh", "api", f"repos/{repo}/git/blobs/{blob_sha}", "--jq", ".content"],
                        timeout=180).strip()
    text = base64.b64decode(raw).decode("utf-8", "replace") if raw else ""
    return text, blob_sha


def engine_build_runs(repo: str, head_sha: str, engine: str) -> dict[str, tuple[str, str]]:
    """variant -> (conclusion, readable workflow run id) for this head engine-build check runs.

    `--paginate` because a bump head carries every PR job, and one page of 100 silently drops a
    variant (measured: llama.cpp showed rocm/cuda/cpu but not vulkan on the first page). The check is
    named `engine-build-<engine>-<variant>`, so the engine is stripped to leave the matrix variant.
    """
    out = proc.run_text(["gh", "api", "--paginate",
                         f"repos/{repo}/commits/{head_sha}/check-runs?per_page=100",
                         "--jq", '.check_runs[] | select(.name | startswith("engine-build")) '
                                 '| [.name, (.conclusion // ""), (.html_url // "")] | @tsv'],
                         timeout=240)
    variants: dict[str, tuple[str, str]] = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        name, conclusion, url = parts[0], parts[1], parts[2]
        row = {"name": name, "conclusion": conclusion, "url": url}
        if not name.startswith(ENGINE_BUILD_PREFIX):
            continue
        arch = name[len(ENGINE_BUILD_PREFIX):]
        if engine and arch.startswith(engine + "-"):
            arch = arch[len(engine) + 1:]
        m = RUN_URL_RE.search(row.get("url", ""))
        run_id = m.group(1) if m else ""
        variants[arch] = (row.get("conclusion", ""), run_id)
    return variants


def expected_variants(repo: str, engine: str) -> list[str]:
    """The arches this repo builds this engine for, read from the build matrix itself."""
    out = proc.run_text(["make", "-s", "engine-build-matrix", f"ENGINE={engine}"], timeout=180)
    start = out.find("{")
    if start < 0:
        return []
    matrix = json.loads(out[start:])
    # The matrix keys the variant as "variant" (cpu/cuda/rocm/vulkan), not "arch".
    return sorted({inc.get("variant", "") for inc in matrix.get("include", []) if inc.get("variant")})


@dataclass
class Evidence:
    files: list[str] = field(default_factory=list)
    skill_pin: str = ""
    skill_blob: str = ""
    params_blob: str = ""
    params_names_pin: bool = False
    variants: dict[str, tuple[str, str]] = field(default_factory=dict)
    expected: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)


def read_evidence(repo: str, bump: BumpPr) -> Evidence:
    """What the head actually proves: the files it touched, the pin at the head, the image lane."""
    ev = Evidence(files=pr_files(repo, bump.number))
    ev.expected = expected_variants(repo, bump.engine)
    skill, ev.skill_blob = repo_file_at(repo, SKILL_PATH_TMPL.format(engine=bump.engine), bump.head_sha)
    if m := re.search(r"pinned:[^#]*?([0-9a-f]{12,40})", skill):
        ev.skill_pin = m.group(1)
    params, ev.params_blob = repo_file_at(repo, PARAMS_PATH_TMPL.format(engine=bump.engine),
                                          bump.head_sha)
    ev.params_names_pin = bool(params) and (bump.new_sha in params or bump.new_sha[:12] in params
                                            or bump.ref in params)
    ev.variants = engine_build_runs(repo, bump.head_sha, bump.engine)
    for arch in ev.expected:
        if arch not in ev.variants:
            ev.gaps.append(f"no {ENGINE_BUILD_PREFIX}{arch} check run reported at {bump.head_sha[:12]}")
    for arch, (concl, _run) in sorted(ev.variants.items()):
        if arch in ev.expected and concl != "success":
            ev.gaps.append(f"{ENGINE_BUILD_PREFIX}{arch} conclusion={concl or 'in flight'}")
    if not ev.skill_pin or not (bump.head_sha.startswith(ev.skill_pin)
                                or ev.skill_pin.startswith(bump.new_sha)
                                or bump.new_sha.startswith(ev.skill_pin)):
        ev.gaps.append(f"the skill at the head pins {ev.skill_pin[:12] or '?'}, not {bump.new_sha[:12]}")
    if not ev.params_names_pin:
        ev.gaps.append(
            f"{PARAMS_PATH_TMPL.format(engine=bump.engine)} at the head does not name {bump.new_sha[:12]}")
    return ev


def prove(repo: str, bump: BumpPr, ev: Evidence,
          deferred: dict[str, str]) -> tuple[list[str], list[str], list[str]]:
    """(ticked items the head backs, out-of-scope lines, refusals) — never a tick the head cannot back.

    Item 1 proves the pin and the re-derivation through the head own files; item 2 through the params
    file at the head; item 3 only when EVERY arch the matrix expects reported green, citing each
    arch readable workflow run id. A red or unreported arch becomes `## Not covered` naming the issue
    passed through `--deferred ENGINE=ISSUE`; with no mapping the leg refuses to stamp that PR.
    """
    items: list[str] = []
    not_covered: list[str] = []
    refusals: list[str] = []
    head = bump.head_sha
    if not any(g.startswith("the skill at the head") for g in ev.gaps):
        items.append(f"- [x] {ACCEPTANCE_CLAIMS[0]} "
                     f"(proven: gh api repos/{repo}/git/blobs/{ev.skill_blob} rc=0 {head})")
    else:
        refusals.append("skill pin at the head does not match the bump")
    if ev.params_names_pin:
        items.append(f"- [x] {ACCEPTANCE_CLAIMS[1]} "
                     f"(proven: gh api repos/{repo}/git/blobs/{ev.params_blob} rc=0 {head})")
    else:
        refusals.append("params file at the head does not name the new pin")
    green: list[str] = []
    for arch, (concl, run) in sorted(ev.variants.items()):
        if concl == "success" and arch in ev.expected and run and run not in green:
            green.append(run)
    if ev.expected and len(green) == len(ev.expected):
        items.append(f"- [x] {ACCEPTANCE_CLAIMS[2]} "
                     f"(proven: {' '.join(f'run={r}' for r in green)} {head})")
    else:
        issue = deferred.get(bump.engine, "")
        gaps = [g for g in ev.gaps
                if g.startswith(ENGINE_BUILD_PREFIX) or g.startswith("no engine-build")]
        if gaps and not issue:
            refusals.extend(f"image gap with no --deferred mapping: {gap}" for gap in gaps)
        elif gaps:
            # One line per engine, naming every unresolved variant and the issue that owns them.
            not_covered.append(
                f"the {bump.engine} image gap ({'; '.join(gaps)}, head {head[:12]}) "
                f"— tracked in #{issue}")
    return items, not_covered, refusals


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


def render_for(bump: BumpPr, repo_slug: str = DEFAULT_REPO, items: list[str] | None = None,
               not_covered: tuple[str, ...] = ()) -> str:
    """The replacement body: the SAME composer #3050 landed, with the live body's review section kept.

    `items`/`not_covered` are what the leg MEASURED at the live head: the composer renders them, under
    its own heading, and names the head in every proven clause (issue #2288 head rule).
    """
    return render_body(engine=bump.engine, ref=bump.ref, old_sha=bump.old_sha, new_sha=bump.new_sha,
                       run_id=bump.run_id, author=DEFAULT_AUTHOR, repo_slug=repo_slug,
                       openspec=DEFAULT_OPENSPEC, hard_fail=bump.hard_fail, deps=bump.deps,
                       review_section=bump.review, head_sha=bump.head_sha,
                       acceptance_items=items, not_covered=not_covered)


def close_comment(bump: BumpPr) -> str:
    return (f"This bump is closed as overtaken, not re-stamped. `main` currently pins `{bump.engine}` at "
            f"`{bump.main_pin[:12]}`; this PR proposed `{bump.new_sha[:8]}` from `{bump.old_sha[:8]}`, so main "
            f"{'already holds' if bump.kind == LANDED else 'moved past'} that pin and re-stamping this body "
            f"would leave a stale pin bump masquerading as pending work. Re-open it only if the pin it "
            f"proposed is the pin main should move to. Issue #3054.")


def process(repo: str, apply: bool, close_superseded: bool, out_dir: Path,
            deferred: dict[str, str] | None = None) -> dict[str, int]:
    deferred = deferred or {}
    tally = {k: 0 for k in KNOWN_KINDS}
    tally.update({"written": 0, "closed": 0, "refused": 0, "unstamped": 0, "unchanged": 0,
                  "unproven": 0})
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
            ev = read_evidence(repo, bump)
            bump.evidence_gaps = ev.gaps
            items, not_covered, refusals = prove(repo, bump, ev, deferred)
            line += f" proven={len(items)} not-covered={len(not_covered)}"
            if refusals:
                tally["unproven"] += 1
                print(line + " SKIP=unproven: " + "; ".join(refusals)
                      + " (pass --deferred ENGINE=ISSUE to reclassify them as Not covered)")
                continue
            text = render_for(bump, repo, items=items, not_covered=tuple(not_covered))
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


def restamp_commit_text(message: str, *, engine: str, run_id: str,
                        image_runs: tuple[str, ...] = ()) -> tuple[str, int]:
    """Replace the commit's acceptance block with the composer's MEASURED clauses (issue #3076).

    The proof names the workflow run id (`rc=0 run=<id>`), never a head sha: a self-amending commit
    cannot name its own final sha, and a sha stamped before the amend would be stale at the live
    head (issue #2288). The PR body carries the head-stamped clauses; the commit mirror carries the
    run-stamped ones. Returns the new message and the number of draft-stub tokens it replaced.
    """
    block = "\n".join([COMMIT_ACCEPTANCE_HEADING,
                       *acceptance_items(engine, run_id, image_runs=image_runs)])
    lines = message.rstrip("\n").splitlines()
    idx = next((i for i, line in enumerate(lines) if line.strip() == COMMIT_ACCEPTANCE_HEADING), None)
    if idx is None:
        return "\n".join([*lines, "", block]).rstrip() + "\n", len(DRAFT_STUB.findall(message))
    end = len(lines)
    for j in range(idx + 1, len(lines)):
        if ANY_HEADING.match(lines[j]):
            end = j
            break
    replaced = len(DRAFT_STUB.findall("\n".join(lines[idx:end])))
    out = [*lines[:idx], *block.splitlines(), *lines[end:]]
    return "\n".join(out).rstrip() + "\n", replaced


def restamp_commit_file(commit_in: str, commit_out: str, engine: str, run_id: str,
                        image_runs: tuple[str, ...]) -> int:
    """CLI seam: read a commit message file, restamp it, refuse any surviving draft stub."""
    source = Path(commit_in)
    if not source.is_file():
        raise SystemExit(f"--commit-in names no file: {commit_in}")
    updated, replaced = restamp_commit_text(source.read_text(encoding="utf-8"),
                                            engine=engine, run_id=run_id, image_runs=image_runs)
    if DRAFT_STUB.search(updated):
        raise SystemExit("[restamp] commit text still carries a draft stub — refusing to write")
    target = Path(commit_out) if commit_out else source
    target.write_text(updated, encoding="utf-8")
    print(f"[restamp] commit text: {replaced} draft stub token(s) -> measured proof "
          f"(engine={engine} run={run_id}) -> {target}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Re-render the open engine-bump PR bodies through the composer + guarded write seam (issue #3054).")
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--apply", action="store_true",
                    help="write the re-rendered bodies through make bot-body-write (default: dry, writes nothing)")
    ap.add_argument("--close-superseded", action="store_true",
                    help="with --apply: close landed/superseded bumps with main's live pin as the evidence")
    ap.add_argument("--out-dir", default="/tmp/engine-bump-restamp", help="where the rendered bodies land")
    ap.add_argument("--deferred", action="append", default=[], metavar="ENGINE=ISSUE",
                    help="map an engine whose image builds are red/unreported to the issue that owns that "
                         "gap; the body then carries it as `## Not covered` instead of a tick it cannot back")
    ap.add_argument("--commit-in", default="", help="issue #3076: a commit MESSAGE file whose "
                    "acceptance block is restamped from the measured run proof before push")
    ap.add_argument("--commit-out", default="", help="where the restamped commit message is written "
                    "(default: overwrite --commit-in)")
    ap.add_argument("--engine", default="", help="engine id for --commit-in (the bump lane's ENGINE)")
    ap.add_argument("--run", default="", help="workflow run id for --commit-in")
    ap.add_argument("--image-run", action="append", default=[], metavar="RUN_ID",
                    help="per-variant engine-build run id for --commit-in")
    a = ap.parse_args(argv)
    if a.commit_in:
        if not a.engine or not a.run:
            raise SystemExit("--commit-in requires --engine and --run")
        return restamp_commit_file(a.commit_in, a.commit_out, a.engine, a.run,
                                   tuple(a.image_run))
    deferred: dict[str, str] = {}
    for item in a.deferred:
        if "=" not in item:
            raise SystemExit(f"--deferred wants ENGINE=ISSUE, got {item!r}")
        engine, issue = item.split("=", 1)
        deferred[engine.strip()] = issue.strip()
    process(a.repo, a.apply, a.close_superseded, Path(a.out_dir), deferred)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
