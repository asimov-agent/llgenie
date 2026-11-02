#!/usr/bin/env python3
"""Delete non-`main` remote branches that are at least 3 days old AND fully delivered.

Issue #1344. The repo accumulates non-`main` branches (48 measured at origin/main@793ac1dc); most are
squash-merged PR branches (tip NOT an ancestor of main — the #1317 lesson) or unmerged
bot/verification branches. A naive age sweep would destroy in-flight and already-delivered-squash work,
so deletion is gated on a live-vehicle check, never on age alone.

Safety predicate (a branch is deleted ONLY when BOTH hold):
  * no open PR names that head ref, AND
  * every commit on it is already in `origin/main` (the tip is behind/identical via the compare
    endpoint) OR its PR is MERGED/CLOSED — a squash-merged branch tip is never an ancestor, so the PR
    state is what recognises it as delivered.
A branch with an open PR, or with commits `origin/main` does not have and no merged/closed PR, is
REPORTED, never deleted. `main` and any protected branch are never touched.

Default is report-only (lists the would-delete set, exits 0, never mutates). Deletion happens only when
APPLY=1 is passed. Every deletion logs branch, tip sha, age, and the evidence.

Hermetic: pure GitHub API via `gh` (no local clone needed). Network is the API the pipeline exists for.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess
import sys

from pathlib import Path

_GH = "gh"


def _gh(args: list[str]):
    """Run `gh` and return (returncode, stdout). Never raises."""
    r = subprocess.run([_GH, *args], capture_output=True, text=True)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
    return r.returncode, (r.stdout or "")


class BranchListReadError(RuntimeError):
    """The branch-list read failed (`gh` rc != 0) or returned an unreadable body.

    A read failure is NEVER "no branches to sweep" — an unreadable answer must not be read as
    a clean board (#1514, restoring the #453 discipline). `main` turns this into a non-zero
    exit so the daily run reds instead of reporting a clean sweep it never actually made.
    """


def _paged_json(endpoint: str, *, strict: bool = True):
    """All pages of a JSON array endpoint, via `gh api --paginate`.

    strict=True (default): a non-zero rc or empty/un-JSON body raises BranchListReadError —
    a faulted read reds the run instead of collapsing to []. strict=False returns [] on
    faults, for a caller that genuinely treats an unreadable result as "no data".
    """
    rc, out = _gh(["api", "--paginate", "--silent", endpoint])
    if rc != 0 or not out.strip():
        if strict:
            raise BranchListReadError(
                f"branch-list read failed: `gh api {endpoint}` rc={rc} "
                f"stdout={(out or '').strip()[:200]!r}")
        return []
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        if strict:
            raise BranchListReadError(
                f"branch-list read failed: non-JSON body from `gh api {endpoint}`")
        return []
    return data if isinstance(data, list) else data.get("items", [data])


def _pr_state(repo: str, branch: str) -> str:
    """OPEN | MERGED | CLOSED | NONE for the newest PR naming that head (state open OR all)."""
    rc, out = _gh(["pr", "list", "--repo", repo, "--head", branch,
                   "--state", "open", "--json", "number,state", "--limit", "1"])
    if rc == 0 and out.strip() and "null" not in out and out.strip() != "[]":
        try:
            return "OPEN"
        except Exception:
            pass
    rc2, out2 = _gh(["pr", "list", "--repo", repo, "--head", branch,
                     "--state", "all", "--json", "number,state", "--limit", "1"])
    if rc2 == 0 and out2.strip() and out2.strip() != "[]":
        try:
            state = json.loads(out2)[0]["state"]
            return "MERGED" if state == "MERGED" else ("CLOSED" if state == "CLOSED" else state)
        except Exception:
            pass
    return "NONE"


def _is_protected(repo: str, branch: str) -> bool:
    """A 200 from the branch-protection endpoint means the branch is protected (skip it)."""
    rc, _ = _gh(["api", f"repos/{repo}/branches/{branch}/protection",
                 "--jq", "."])
    return rc == 0


def _delivered(repo: str, default: str, tip: str, pr_state: str) -> tuple[bool, str]:
    """Is the branch fully delivered? (true, evidence string)."""
    if pr_state in ("MERGED", "CLOSED"):
        return True, f"PR {pr_state}"
    rc, out = _gh(["api", "--jq", ".status",
                   f"repos/{repo}/compare/{default}...{tip}"])
    if rc == 0:
        st = (out or "").strip() or ""
        if st in ("behind", "identical"):
            return True, f"compare {st} (all commits in {default})"
    return False, f"commits not in {default}, PR {pr_state}"


def _delete(repo: str, branch: str) -> tuple[int, str]:
    return _gh(["api", "--method", "DELETE", "-X", "DELETE",
                f"repos/{repo}/git/refs/heads/{branch}"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default="asimov-agent/llgenie")
    ap.add_argument("--age-days", type=int, default=3)
    ap.add_argument("--apply", action="store_true", help="delete the selected branches")
    ap.add_argument("--sample", type=int, default=0, help="cap the branch count for a dry-run")
    args = ap.parse_args(argv)

    repo = args.repo
    now = _dt.datetime.now(_dt.timezone.utc)

    rc, defout = _gh(["repo", "view", repo, "--json", "defaultBranchRef",
                      "--jq", ".defaultBranchRef.name"])
    default = (defout or "main").strip() if rc == 0 else "main"

    labels = {"main": "default"}
    try:
        labels = dict((l.split()[1:2] and (l.split()[1], "branch-protegida") for l in ["x"])
                      if False else {"main": "default"})
    except Exception:
        pass

    try:
        branches = _paged_json(f"repos/{repo}/branches?per_page=100")
    except BranchListReadError as e:
        print(f"stale-branch cleanup FAILED — could not read the branch list: {e}", file=sys.stderr)
        print("(a branch-list read failure reds the run; it is never a clean board)", file=sys.stderr)
        return 1
    candidates: list[dict] = []
    reported: list[dict] = []
    deleted = 0
    denied = 0

    for b in branches[: args.sample] if args.sample else branches:
        name = b.get("name", "")
        sha = (b.get("commit") or {}).get("sha", "")
        if name == default or name in ("main", "master") or _is_protected(repo, name):
            continue
        rc, dout = _gh(["api", "--jq", ".commit.committer.date",
                        f"repos/{repo}/commits/{name}"])
        age_s = None
        if rc == 0 and dout.strip():
            try:
                dt = _dt.datetime.fromisoformat(dout.strip().rstrip("Z"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=_dt.timezone.utc)
                age_s = (now - dt).total_seconds() / 86400.0
            except ValueError:
                age_s = None
        age = round(age_s, 1) if age_s is not None else None
        if age is not None and age < args.age_days:
            reported.append({"branch": name, "sha": sha[:8], "age_days": age,
                             "disposition": f"younger than {args.age_days}d — kept"})
            continue

        pr_state = _pr_state(repo, name)
        delivered, evidence = _delivered(repo, default, sha, pr_state)
        has_open = pr_state == "OPEN"
        if has_open or not delivered:
            reported.append({"branch": name, "sha": sha[:8], "age_days": age,
                             "disposition": f"live vehicle ({pr_state}) — kept"
                             if has_open else f"unreachable — kept ({evidence})"})
            continue

        candidates.append({"branch": name, "sha": sha[:8], "age_days": age, "evidence": evidence})

    print(f"stale-branch cleanup scan on {repo} (default={default}, age >= {args.age_days}d, "
          f"{'APPLY' if args.apply else 'report-only'})")
    for c in candidates:
        print(f"  WOULD-DELETE {c['branch']}@{c['sha']} age={c['age_days']}d "
              f"evidence={c['evidence']}")
    for rep in reported:
        print(f"  KEEP {rep['branch']}@{rep['sha']} age={rep['age_days']}d — {rep['disposition']}")

    if not args.apply:
        print(f"report-only: {len(candidates)} would be deleted, 0 deleted, "
              f"{len(reported)} kept")
        return 0

    for c in candidates:
        rc, out = _delete(repo, c["branch"])
        if rc == 0:
            print(f"  DELETED {c['branch']}@{c['sha']} age={c['age_days']}d "
                  f"evidence={c['evidence']}")
            deleted += 1
        else:
            print(f"  DELETE-FAILED {c['branch']}@{c['sha']} — {(out or '').strip()[:120]}")
            denied += 1

    print(f"applied: {deleted} deleted, {denied} failed, {len(reported)} kept")
    return 0


if __name__ == "__main__":
    sys.exit(main())
