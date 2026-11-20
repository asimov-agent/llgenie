#!/usr/bin/env python3
"""Fail when a remote branch carries commits no PR will ever deliver (issue #442).

Measured origin: while landing #413, the fix already existed — stranded. `feat/bot-model-1017`'s
only PR (#410) merged at 2026-10-20T11:00:47Z; the #413 fix was committed to that SAME branch at
12:17Z, after the merge. The branch's only PR had closed, so the commit rode no PR, no CI on the
base, no review: it sat a day while `main` kept failing. The pipeline had no step that notices a
remote branch whose tip moved past every open-or-merged PR's head. This is that step.

The rule (the exact measured shape, per openspec change `orphan-commit-guard`):

  a same-repo remote branch that IS the source of a merged pull request, whose current tip is
  NOT that PR's recorded merged head, is NOT an ancestor of origin/main, and is NOT covered by an
  OPEN pull request, is ORPHANED — every commit on it that is reachable from neither the merged
  head nor main is reported as `orphan: <branch> <sha> (merged PR #<n>, merged <mergedAt>) —
  <subject>` and the run exits non-zero.

Not orphans, each pinned by tests: a branch whose tip still equals the merged head (harmless
merge residue); a branch an open PR covers (in-flight work, e.g. a lane reusing its branch for a
new PR); a tip already merged into origin/main (the work landed). A refused PR-map read is a loud
hard failure, never an empty sweep — the same rule `bot_close_reasons` holds its own reads to.

The merged-PR map is REUSED from `scripts/bot_close_reasons.py` (the one merged-PR read the
repository already agrees on; cross-group edge recorded in package-layers.json), so this guard and
the closure report cannot disagree about which PRs merged.

Baseline tolerance (issue #442's own measured reality: its first live sweep found 4 residues
whose cleanup is CONSENT-gated, and the issue labels that cleanup "prerequisite for the gate's
green baseline"): `data/orphan-baseline.json` records residues already filed and tracked, as
(branch, merged PR number) pairs. A residue matching a baseline entry is PRINTED as
`tolerated baseline residue` — naming is never traded for silence — and does not fail the run;
any orphan NOT on the baseline fails exactly like before. Branches are reused in this repo, so
the match needs branch AND merged-PR number: a branch re-cut by a NEW merged PR gets no shelter
from an old entry.

Run locally or in CI: `make check-orphan-commits`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.bot_close_reasons import merged_pulls  # noqa: E402
from scripts.proc import ProcError, run_ok, run_text  # noqa: E402

BASE_REPO = "asimov-agent/llgenie"
BASELINE_RELPATH = "data/orphan-baseline.json"


def _load_baseline(path: Path) -> set[tuple[str, int]]:
    """Residues already filed on the board (issue #442's consent-gated cleanup): (branch,
    merged PR number) pairs. Missing file = no shelter. A malformed baseline is a LOUD exit,
    never a silently empty tolerance."""
    if not path.is_file():
        return set()
    try:
        rows = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[orphan-guard] baseline file {path} is not valid JSON: {exc}")
    if not isinstance(rows, list):
        raise SystemExit(f"[orphan-guard] baseline file {path} must be a JSON list")
    out: set[tuple[str, int]] = set()
    for row in rows:
        if isinstance(row, dict) and row.get("branch") is not None and row.get("merged_pr") is not None:
            out.add((str(row["branch"]), int(row["merged_pr"])))
    return out


def _open_pr_heads(gh: str, repo: str, pages: int) -> dict[str, int]:
    """branch -> open PR number. A refused read is a hard exit, never an empty sweep."""
    out: dict[str, int] = {}
    for page in range(1, pages + 1):
        try:
            raw = run_text([gh, "api", f"repos/{repo}/pulls?state=open&per_page=100"
                            f"&sort=updated&direction=desc&page={page}"], timeout=60)
            rows = json.loads(raw or "null")
        except (ProcError, json.JSONDecodeError) as exc:
            raise SystemExit(f"[orphan-guard] cannot read open PRs of {repo}: {exc}")
        if not isinstance(rows, list) or not rows:
            break
        for pr in rows:
            if isinstance(pr, dict) and isinstance(pr.get("head"), dict) and pr.get("number"):
                out[str(pr["head"].get("ref", ""))] = int(pr["number"])
        if len(rows) < 100:
            break
    return out


def _branch_tips(remote: str, cwd: Path) -> dict[str, str]:
    """branch -> tip sha for every branch on the remote, via one `git ls-remote`."""
    out: dict[str, str] = {}
    for line in run_text(["git", "ls-remote", "--heads", remote], cwd=str(cwd)).splitlines():
        sha, _, ref = line.partition("\t")
        if ref.startswith("refs/heads/"):
            out[ref.removeprefix("refs/heads/")] = sha
    return out


def _merged_pr_map(gh: str, repo: str, pages: int) -> dict[str, dict]:
    """branch -> the NEWEST merged PR whose head was that branch (same-repo heads only)."""
    out: dict[str, dict] = {}
    for pr in merged_pulls(gh, repo, pages):
        head = pr.get("head")
        head_repo = (head or {}).get("repo") or {}
        if head_repo.get("full_name") != repo:  # fork heads live in another tree, not this remote
            continue
        branch = str((head or {}).get("ref", ""))
        number = int(pr.get("number") or 0)
        prior = out.get(branch)
        if branch and number and (prior is None or number > prior["number"]):
            out[branch] = {
                "number": number,
                "head_sha": str((head or {}).get("sha", "")),
                "merged_at": str(pr.get("merged_at", "")),
            }
    return out


def _is_ancestor(sha: str, target: str, cwd: Path) -> bool:
    """merge-base --is-ancestor, as a value. rc 0 = ancestor, rc 1 = not; rc 128 with "not a
    valid ..." names a sha this checkout does not have YET — also "not" (the caller fetches the
    branch before listing its commits), so an unfetched orphan is never mistaken for landed."""
    r = run_ok(["git", "merge-base", "--is-ancestor", sha, target], cwd=str(cwd))
    if r.returncode == 0:
        return True
    if r.returncode == 1:
        return False
    combined = ((r.stderr or "") + (r.stdout or "")).lower()
    if any(p in combined for p in ("not a valid", "bad object", "unknown revision", "not our merge")):
        return False
    raise SystemExit(f"[orphan-guard] git merge-base failed: {(r.stderr or '').strip()[:200]}")


def _orphan_commits(branch: str, merged_head: str, cwd: Path) -> list[dict]:
    """Commits on the branch reachable from neither the merged head nor main, MINUS commits whose
    PATCH already landed on main. This repository squash-merges: a landed bump commit is not an
    orphan even though its sha never appears in main — `git cherry` (patch-id upstream
    equivalence, verified against `git patch-id` on a squash stand-in repo) is the judgement the
    squash itself relies on (measured on the first live sweep: four stale engine-bump branches,
    three genuinely undelivered, strata's landed as a squash under a different PR)."""
    run_text(["git", "fetch", "--no-tags", "origin",
              f"refs/heads/{branch}:refs/remotes/origin/{branch}"], cwd=str(cwd), timeout=300)
    neg = [f"^{merged_head}"] if merged_head else []
    log_out = run_text(["git", "log", "--no-merges", "--format=%H\t%h %s",
                        f"origin/{branch}", *neg, "^origin/main"], cwd=str(cwd))
    landed: set[str] = set()
    cherry = run_text(["git", "cherry", "origin/main", f"origin/{branch}"], cwd=str(cwd))
    for line in cherry.splitlines():
        if line.startswith("- "):
            landed.add(line[2:].strip())
    rows: list[dict] = []
    for line in log_out.splitlines():
        full, _, shown = line.partition("\t")
        short, _, subject = shown.partition(" ")
        if full and full not in landed:
            rows.append({"sha": short, "subject": subject})
    return rows


def check(repo: str = BASE_REPO, gh: str = "gh", remote: str = "origin",
          pages: int = 3, cwd: Path = REPO_ROOT,
          baseline_path: Path | None = None) -> int:
    merged = _merged_pr_map(gh, repo, pages)
    tips = _branch_tips(remote, cwd)
    open_heads = _open_pr_heads(gh, repo, pages)
    baseline = _load_baseline(baseline_path if baseline_path is not None
                              else Path(cwd) / BASELINE_RELPATH)
    run_text(["git", "fetch", "--no-tags", "--prune", remote, "main"], cwd=str(cwd), timeout=120)
    orphans = 0
    tolerated = 0
    for branch, pr in sorted(merged.items()):
        tip = tips.get(branch)
        if tip is None:
            continue  # the merge deleted the branch: the normal landed shape
        if tip == pr["head_sha"]:
            continue  # residue equals the recorded merged head: nothing moved past the PR
        if branch in open_heads:
            continue  # an open PR covers this branch: in-flight work is not orphaned work
        if _is_ancestor(tip, "origin/main", cwd):
            continue  # the tip's work landed by some other road
        commits = _orphan_commits(branch, pr["head_sha"], cwd)
        if not commits:
            continue  # tip differs from the merged head only through merge machinery
        filed = (branch, pr["number"]) in baseline
        for c in commits:
            line = (f"orphan: {branch} {c['sha']} (merged PR #{pr['number']}, "
                    f"merged {pr['merged_at']}) — {c['subject']}")
            if filed:
                tolerated += 1
                print(f"[orphan-guard] tolerated baseline residue ({BASELINE_RELPATH}): {line}")
            else:
                orphans += 1
                print(line)
    if orphans:
        print(f"[orphan-guard] {orphans} orphaned commit(s): a push landed on a branch whose "
              f"only PR had already closed. Cut a NEW branch + PR for each (AGENTS.md: a push to "
              f"a merged PR's branch is not a delivery).")
        return 1
    print(f"[orphan-guard] ok: no branch on '{remote}' carries commits past its merged PR "
          f"({len(merged)} merged-PR branch(es) inspected, {len(tips)} remote branch(es), "
          f"{tolerated} baseline residue(s) named-tolerated)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="check_orphan_commits.py",
                                 description=next(iter((__doc__ or "").splitlines()),
                                                   "fail on orphaned commits on merged PR branches"))
    ap.add_argument("--repo", default=BASE_REPO)
    ap.add_argument("--gh", default="gh")
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--pages", type=int, default=3,
                    help="how many 100-row pages of merged/open PRs to read (300 merged is weeks of board)")
    ap.add_argument("--cwd", default=str(REPO_ROOT))
    ap.add_argument("--baseline", default=str(REPO_ROOT / BASELINE_RELPATH),
                    help="JSON list of already-filed residues to tolerate ((branch, merged_pr) "
                         "pairs); pass '' to disable tolerance entirely")
    args = ap.parse_args(argv)
    baseline = None if args.baseline == "" else Path(args.baseline)
    return check(repo=args.repo, gh=args.gh, remote=args.remote, pages=args.pages,
                 cwd=Path(args.cwd), baseline_path=baseline)


if __name__ == "__main__":
    raise SystemExit(main())
