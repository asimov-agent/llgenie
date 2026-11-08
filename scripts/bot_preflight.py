#!/usr/bin/env python3
"""Bot preflight: fetch `origin/main`, prove the tree is current, record the rulebook (issue #792).

A leg that starts from a stale tree applies a rulebook nobody currently enforces, and a wasted
60-minute implement run is the usual price. This module makes the *start* of work measurable:

    main                        the `origin/main` commit the run is measured against
    agents_bytes / agents_lines the size of `AGENTS.md` at that commit
    agents_headings_sha256      a digest of its `## ` headings, which survives prose edits
    AGENTS: <sha> <bytes>b <lines>l     the one line every bot PR body must carry

`make bot-preflight` writes those into `preflight.txt`, so the record is an input a leg preloads
beside `issue.md` rather than a claim it makes afterwards. `--check` re-derives the record and fails
when it disagrees with the file on disk, which is what a CI step wants.

Since #1782 the target ALSO surfaces the owner's profile-propagation obligation (issue #1724): when
the working diff (`HEAD` vs `origin/main`) touches `agents/<profile>/`, it runs the CI gate's own
`check_pr_hygiene.pr_sync_line_findings` over a prospective body. `BODY=<path>` (a `--body-file`)
refuses the preflight when the body is missing/mis-citing a touched profile's `SYNC:` line; without a
body yet it warns loudly; a non-profile or human-only range is silent. Every verdict names #1724 and
the contract location `scripts/check_pr_hygiene.py:499`.

Since #1790 the target ALSO surfaces every bot PR body's `AGENTS:`/`BASE:` obligation (issues #792
and #845): it runs the CI gate's own `check_pr_hygiene.pr_agents_line_findings` over the prospective
body, so a bot PR that opens with no or mis-cited `AGENTS:`/`BASE:` lines hears it at preflight
instead of on the first red `check-pr-agents-line` (`#1788` opened preflight-green with zero actual
hygiene lines and redded CI). The verdict refuses when a body is supplied but missing/mis-citing the
lines, warns loudly when no body is supplied yet (the gate cannot read one it does not have), and is
silent for a human-only / non-`is_bot_pr` range. Every verdict names #792/#845 and the contract
location `scripts/check_pr_hygiene.py:518`.

Never a silent proceed: a checkout that cannot be brought to `origin/main` (dirty, or diverged with
commits both ways) is an error naming the paths, not a warning.

`--stamp BODY` is the WRITE side of the same contract (issue #2050): it inserts or replaces the
`AGENTS:`/`BASE:` pair in a PR body file, measuring the rulebook from the first ref of
`--base`/`--refs` that resolves (`origin/main`, then a producer's own `main`). Every bot PR producer
calls it before `gh pr create`/`gh pr edit` — `make bot-stamp-body` — so a bot PR carries the pair at
OPEN instead of depending on a leg remembering `make bot-preflight`. It never syncs: a producer that
is mid-run stands where it stands, and a refused measurement is a refused PR, never an unstamped one.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: The ref the preflight measures. `origin/main` and never `main`: a leg must not trust a local branch.
BASE = "origin/main"

#: The record a leg preloads; committing it is not required, reading it is.
RECORD = "preflight.txt"

HEADING = re.compile(r"^(#{2,3})\s+(.*\S)\s*$", re.M)


class PreflightError(RuntimeError):
    """The tree cannot be proven current — a leg must stop, not proceed."""


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)


def _ok(root: Path, *args: str) -> str:
    r = _git(root, *args)
    if r.returncode != 0:
        raise PreflightError(f"git {' '.join(args)} failed: {(r.stderr or r.stdout).strip()}")
    return r.stdout.strip()


def headings(text: str) -> list[str]:
    """Every `##`/`###` heading, in order — the rulebook's table of contents, not its prose."""
    return [f"{m.group(1)} {m.group(2)}" for m in HEADING.finditer(text)]


def heading_digest(text: str) -> str:
    """sha256 over the heading list, so editing a rule's wording does not move it but adding one does."""
    return hashlib.sha256("\n".join(headings(text)).encode()).hexdigest()


def fetch(root: Path = REPO_ROOT, base: str = BASE) -> None:
    """`git fetch origin main` — the first thing a leg does, before it reads anything else."""
    remote, _, branch = base.partition("/")
    r = _git(root, "fetch", "--no-tags", remote or "origin", branch or "main")
    if r.returncode != 0:
        raise PreflightError(f"git fetch {base} failed: {(r.stderr or r.stdout).strip()}")


def is_ancestor(root: Path, sha: str, ref: str) -> bool:
    return _git(root, "merge-base", "--is-ancestor", sha, ref).returncode == 0


def sync(root: Path = REPO_ROOT, base: str = BASE) -> str:
    """Bring the checkout to `base`, or fail. Fast-forward only — never a silent rebase.

    Three states, and only one of them is a question:
      * `HEAD` is `base`, or `base` is already an ancestor of `HEAD`  -> nothing to do
      * `HEAD` is a clean ancestor of `base`                          -> `merge --ff-only`
      * anything else (dirty, or commits on both sides)               -> PreflightError
    """
    head = _ok(root, "rev-parse", "HEAD")
    if head == _ok(root, "rev-parse", base):
        return head
    if is_ancestor(root, base, "HEAD"):
        return head                                    # ahead of main: a leg's own branch, fine
    if not is_ancestor(root, "HEAD", base):
        ahead = _ok(root, "rev-list", "--count", f"{base}..HEAD")
        behind = _ok(root, "rev-list", "--count", f"HEAD..{base}")
        paths = _ok(root, "diff", "--name-only", f"HEAD...{base}").splitlines()
        shown = ("\n  " + "\n  ".join(paths[:20])) if paths else " (no differing paths)"
        raise PreflightError(
            f"HEAD diverged from {base}: {ahead} commit(s) ahead, {behind} behind; "
            f"rebase by hand, the preflight never does it for you:{shown}"
        )
    # The record this target writes must not make the next run refuse its own output: a leg that runs
    # the preflight twice would otherwise fail the second time ("behind main but dirty") because of a
    # file the preflight itself created. Every other uncommitted path is still a refusal.
    dirty = [
        p for p in _ok(root, "status", "--porcelain").splitlines()
        if p.strip() and not p.strip().endswith(RECORD)
    ]
    if dirty:
        shown = ("\n  " + "\n  ".join(dirty[:20]))
        raise PreflightError(f"HEAD is behind {base} but the tree is dirty; commit or stash first:{shown}")
    r = _git(root, "merge", "--ff-only", base)
    if r.returncode != 0:
        raise PreflightError(f"git merge --ff-only {base} failed: {(r.stderr or r.stdout).strip()}")
    return _ok(root, "rev-parse", "HEAD")


def rulebook(root: Path = REPO_ROOT, ref: str = BASE) -> dict:
    """`AGENTS.md` as it is at `ref` — measured from the commit, never from the working tree."""
    sha = _ok(root, "rev-parse", ref)
    r = _git(root, "show", f"{ref}:AGENTS.md")
    if r.returncode != 0:
        raise PreflightError(f"AGENTS.md is unreadable at {ref}: {(r.stderr or r.stdout).strip()}")
    text = r.stdout
    return {
        "main": sha,
        "agents_bytes": len(text.encode()),
        "agents_lines": text.count("\n"),
        "agents_headings_sha256": heading_digest(text),
        "agents_headings": len(headings(text)),
    }


def agents_line(record: dict) -> str:
    """The one line a bot PR body carries: `AGENTS: <sha> <bytes>b <lines>l`."""
    return f"AGENTS: {record['main']} {record['agents_bytes']}b {record['agents_lines']}l"


def base_line(record: dict) -> str:
    """The base at PR-open, beside the `AGENTS:` line (issue #845).

    `record['main']` is the `origin/main` commit the preflight measured at open.
    Recording it lets a reviewer check the base without consulting the branch —
    the defect #845 names is that the base was recorded nowhere, so a worktree cut
    from the primary checkout's parked branch carried the wrong base invisibly.
    """
    return f"BASE: {record['main']} (== origin/main at open)"


def stamp_body(text: str, record: dict) -> str:
    """Insert or REPLACE the `AGENTS:`/`BASE:` pair in a PR body — the one stamp authority (#2050).

    A bot PR opened unstamped because the pair was a step a leg had to remember: the producer that
    builds the body (`issue_implementer.render_pr_body`, `engine-bump.yml`, `registry-sync.yml`,
    `security_bot`) never wrote it, and a repair pass (`fix-bot`) never re-wrote it, so the guard job
    redded five bot PRs at once. This function is what those producers call, so the pair is written by
    the seam that OPENS the PR instead of by the agent's memory.

    Both lines are emitted FLUSH-LEFT and adjacent, exactly as `render()` prints them: the gate matches
    `^AGENTS:`/`^BASE:` with `re.MULTILINE`, so an indented or quoted copy does not count. Any existing
    `AGENTS:`/`BASE:` line (valid-looking, stale or mangled prose) is dropped first, which makes the
    stamp idempotent and lets a re-stamp repair a body a previous pass got wrong.
    """
    from check_pr_hygiene import AGENTS_LINE, BASE_LINE  # noqa: PLC0415  (one gate, never a restated copy)

    kept: list[str] = []
    for line in text.rstrip().splitlines():
        bare = line.strip()
        if bare.startswith(("AGENTS:", "BASE:")):
            continue                                    # replaced by the measured pair below
        kept.append(line)
    while kept and not kept[-1].strip():
        kept.pop()                                       # no blank padding before the pair
    pair = [agents_line(record), base_line(record)]
    if not (AGENTS_LINE.fullmatch(pair[0]) and BASE_LINE.fullmatch(pair[1])):
        raise PreflightError(f"the stamp would not satisfy the gate: {pair!r}")
    return "\n".join([*kept, "", *pair, ""])


def resolve_record(root: Path = REPO_ROOT, base: str = BASE, refs: tuple[str, ...] = ()) -> dict:
    """The record to stamp with, from the first ref that resolves — `origin/main`, `origin/HEAD`, `main`.

    A producer's checkout is `main` itself (engine-bump, registry-sync) and `origin/main` may not be a
    ref there, so the caller names the fallbacks it trusts. `HEAD` is deliberately NOT a default: on an
    agent branch `HEAD` is the branch tip, and a rulebook cited from there is not an ancestor of the
    base, which the gate reds (`check_pr_hygiene.agents_line_findings`). Refusing is the point — a
    producer that cannot measure `main` must not open a PR with a stamp it cannot stand behind.
    """
    tried: list[str] = []
    for ref in (base, *refs):
        tried.append(ref)
        r = _git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
        if r.returncode == 0 and r.stdout.strip():
            return rulebook(root, ref)
    raise PreflightError(
        f"no ref to measure the rulebook at (tried {', '.join(tried)}) — fetch `origin/main` or pass "
        "`BASE=<the main ref this checkout stands on>`; a PR must not open with an unmeasurable stamp "
        "(issue #2050)"
    )


def render(record: dict) -> str:
    return "\n".join(
        [
            f"main: {record['main']}",
            f"agents_bytes: {record['agents_bytes']}",
            f"agents_lines: {record['agents_lines']}",
            f"agents_headings: {record['agents_headings']}",
            f"agents_headings_sha256: {record['agents_headings_sha256']}",
            agents_line(record),
            base_line(record),
            "",
        ]
    )


def write_record(root: Path = REPO_ROOT, record: dict | None = None) -> Path:
    record = record or rulebook(root)
    path = root / RECORD
    path.write_text(render(record))
    return path


def preflight(root: Path = REPO_ROOT, base: str = BASE, base_ref: str | None = None) -> dict:
    """The whole thing, in the order a leg must do it: fetch, sync, measure."""
    fetch(root, base)
    head = sync(root, base)
    record = rulebook(root, base_ref or base)
    record["head"] = head
    return record


def stale_record(root: Path = REPO_ROOT, base: str = BASE) -> str | None:
    """The reason `preflight.txt` does not match the tree it sits in, or None when it does."""
    path = root / RECORD
    if not path.exists():
        return f"{RECORD} is missing — run `make bot-preflight`"
    have = path.read_text().splitlines()
    want = render(rulebook(root, base)).splitlines()
    missing = [ln for ln in want if ln not in have]
    if missing:
        return f"{RECORD} is stale, missing or differing: {', '.join(l.split(':')[0] for l in missing)}"
    return None


def sync_line_verdict(root: Path, head: str, base: str, body: str) -> list[dict]:
    """The #1724 findings the would-be-pushed range carries — the gate's own function, imported.

    `bot_preflight` IS the pre-push surface a lane runs before opening a PR (issue #792). A profile the
    working diff touches with no matching `SYNC:` line is redded in CI by `make check-pr-sync-line`
    (issue #1724) reading the LIVE PR body — the one source a hermetic preflight cannot reach. So we reuse
    `check_pr_hygiene.pr_sync_line_findings` (the SAME function CI mounts, never a restated copy) over the
    would-be body, and surface its verdict here so the lane hears it at preflight, not on the first red run.
    """
    from check_pr_hygiene import pr_sync_line_findings  # noqa: PLC0415  (local import keeps preflight standalone)
    return pr_sync_line_findings(root, head, base, body)


def render_sync_line_findings(items: list[dict]) -> str:
    """One line per #1724 finding, naming the contract location (`check_pr_hygiene.py:499`)."""
    lines = []
    for it in items:
        lines.append(f"  - {it.get('detail', it.get('key', 'profile-sync'))}")
        lines.append("    (issue #1724; contract: scripts/check_pr_hygiene.py:499 — "
                     "add a `SYNC: <p> make sync-agent-profile PROFILE=<p>` line per changed profile)")
    return "\n".join(lines)


def agents_base_verdict(root: Path, head: str, base: str, body: str) -> list[dict]:
    """The #792/#845 findings a would-be bot PR body carries — the gate's own function, imported.

    A bot PR with a missing or mis-cited `AGENTS:`/`BASE:` pair is redded in CI by
    `make check-pr-agents-line` (issues #792, #845) reading the LIVE PR body — the one source a
    hermetic preflight cannot reach. `#1788` opened preflight-green with zero actual hygiene lines
    and redded CI. So we reuse `check_pr_hygiene.pr_agents_line_findings` (the SAME gate CI mounts,
    never a restated copy) over the would-be body, surfacing its verdict here so the lane hears it
    at preflight, not on the first red run. The gate itself enforces the #845 BASE==AGENTS-equality
    (`check_pr_hygiene.py:564`), so the verdict inherits that contract too.
    """
    from check_pr_hygiene import pr_agents_line_findings  # noqa: PLC0415  (local import keeps preflight standalone)
    return pr_agents_line_findings(root, head, base, body)


def render_agents_base_findings(items: list[dict]) -> str:
    """One line per #792/#845 finding, naming the contract location (`check_pr_hygiene.py:518`)."""
    lines = []
    for it in items:
        lines.append(f"  - {it.get('detail', it.get('key', 'agents-line'))}")
        lines.append("    (issue #792/#845; contract: scripts/check_pr_hygiene.py:518 — run `make "
                     "bot-preflight` and cite the `AGENTS: <sha> <bytes>b <lines>l` + "
                     "`BASE: <sha> (== origin/main at open)` lines it writes)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="bot_preflight", description=__doc__)
    p.add_argument("--root", default=str(REPO_ROOT))
    p.add_argument("--base", default=BASE, help="the ref to measure (default origin/main)")
    p.add_argument("--check", action="store_true", help="fail when preflight.txt disagrees with the tree")
    p.add_argument("--no-write", action="store_true", help="measure and print, write no record")
    p.add_argument("--no-sync", action="store_true", help="fetch and measure, do not fast-forward")
    p.add_argument("--body-file", default=None,
                   help="the prospective PR body; when the working diff touches agents/<profile>/, its "
                        "SYNC: lines are checked here (issue #1724), so a lane hears the verdict pre-push")
    p.add_argument("--stamp", metavar="BODY", default=None,
                   help="insert/replace the AGENTS:/BASE: pair in this PR body file (in place, or into "
                        "--out) and print the result — the #2050 stamp authority every bot PR producer "
                        "calls before `gh pr create`/`gh pr edit`. Measures the rulebook, never syncs")
    p.add_argument("--out", default=None,
                   help="with --stamp: write the stamped body here instead of back into BODY")
    p.add_argument("--refs", default="",
                   help="with --stamp: comma-separated fallback refs to measure main at (e.g. "
                        "'origin/HEAD,main'), tried after --base; a producer checked out ON main passes "
                        "'main'")
    args = p.parse_args(argv)
    root = Path(args.root).resolve()
    if args.stamp:
        try:
            body = Path(args.stamp).read_text()
            record = resolve_record(root, args.base,
                                    tuple(r for r in args.refs.split(",") if r.strip()))
        except (OSError, PreflightError) as exc:
            print(f"[bot-preflight] REFUSED: cannot stamp {args.stamp}: {exc}", file=sys.stderr)
            return 1
        stamped = stamp_body(body, record)
        out = Path(args.out) if args.out else Path(args.stamp)
        out.write_text(stamped)
        print(f"[bot-preflight] stamped {args.stamp} -> {out} at {record['main']} "
              f"({record['agents_bytes']}b / {record['agents_lines']}l) (issue #2050)", file=sys.stderr)
        print(stamped, end="")
        return 0
    body = ""
    if args.body_file:
        try:
            body = Path(args.body_file).read_text()
        except OSError as exc:
            print(f"[bot-preflight] REFUSED: cannot read --body-file: {exc}", file=sys.stderr)
            return 1
    try:
        if args.check:
            bad = stale_record(root, args.base)
            if bad:
                print(f"[bot-preflight] REFUSED: {bad}", file=sys.stderr)
                return 1
            print(f"[bot-preflight] OK: {RECORD} matches {args.base}")
            return 0
        record = (rulebook(root, args.base) if args.no_sync else preflight(root, args.base))
        if not args.no_write:
            write_record(root, record)
        print(render(record), end="")
        print(f"[bot-preflight] OK: measured {args.base} ({record['agents_bytes']} b / "
              f"{record['agents_lines']} l of AGENTS.md, {record['agents_headings']} headings)", file=sys.stderr)
        # #1724: surface the SYNC-line verdict a profile-touching PR will meet in CI (issue #1782).
        findings = sync_line_verdict(root, "HEAD", args.base, body)
        if findings and args.body_file:
            print("[bot-preflight] REFUSED: the PR body is missing or mis-citing a required "
                  "`SYNC:` line for a touched agent profile — CI `make check-pr-sync-line` will red it "
                  "(issue #1724):", file=sys.stderr)
            print(render_sync_line_findings(findings), file=sys.stderr)
            return 1
        if findings:
            print("[bot-preflight] WARN: this branch changes an agent profile; the PR body must carry a "
                  "`SYNC: <p> make sync-agent-profile PROFILE=<p>` line per touched profile or CI `make "
                  "check-pr-sync-line` will red it (issue #1724; contract scripts/check_pr_hygiene.py:499):",
                  file=sys.stderr)
            print(render_sync_line_findings(findings), file=sys.stderr)
        # #1790: surface the AGENTS/BASE verdict a bot PR body will meet in CI (issues #792/#845).
        agents_findings = agents_base_verdict(root, "HEAD", args.base, body)
        if agents_findings and args.body_file:
            print("[bot-preflight] REFUSED: the PR body is missing or mis-citing a required "
                  "`AGENTS:`/`BASE:` pair — CI `make check-pr-agents-line` will red it "
                  "(issue #792/#845):", file=sys.stderr)
            print(render_agents_base_findings(agents_findings), file=sys.stderr)
            return 1
        if agents_findings:
            print("[bot-preflight] WARN: a bot PR body must carry `AGENTS: <sha> <bytes>b <lines>l` + "
                  "`BASE: <sha> (== origin/main at open)` beside one another or CI `make "
                  "check-pr-agents-line` will red it (issue #792/#845; contract "
                  "scripts/check_pr_hygiene.py:518):", file=sys.stderr)
            print(render_agents_base_findings(agents_findings), file=sys.stderr)
        return 0
    except PreflightError as exc:
        print(f"[bot-preflight] REFUSED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
