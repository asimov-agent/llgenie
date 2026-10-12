#!/usr/bin/env python3
"""Shared engine-bump PR sync logic (issue #206 + #208).

The engine-bump workflow (`.github/workflows/engine-bump.yml`, issue #107) opens
a `chore/engine-bump-<id>` PR per changed engine directly on the UPSTREAM repo
(`asimov-agent/llgenie`), so those branches are NOT on a contributor's fork. On
a clone where `origin` is the fork, fetching + rebasing them against a stale
fork `main` never reaches the never-merge-behind gate (issue #9).

This module holds the ONE implementation of "forward-merge the upstream `main`
into a behind engine-bump PR branch and force-with-lease-push it back". The CI
rebase entrypoint (`scripts/engine_bump_rebase.py`) imports it, so there is no
duplicated logic (AGENTS.md: no dual paths for the same resource).

The functions are pure: they take the git runner and logger as parameters so a
caller can inject its own (a CI script's `run_git`/`log`).
"""

from __future__ import annotations

import subprocess

# The repo every engine-bump PR targets (issue #206). A clone's `origin` is the
# upstream on one machine and the fork on another, so the remote is resolved
# from its URL, never assumed from its name.
UPSTREAM_SLUG = "asimov-agent/llgenie"
UPSTREAM_URL = f"https://github.com/{UPSTREAM_SLUG}.git"


def is_engine_bump_pr(pr) -> bool:
    """True if *pr* is one of the automated engine-bump PRs (issue #107).

    The engine-bump workflow opens `chore/engine-bump-<id>` PRs directly on
    `asimov-agent/llgenie` (the upstream), so their branches are NOT on a
    contributor's fork. These are the ONLY PRs that are auto-rebased /
    forward-merged against the UPSTREAM `asimov-agent/main` (issue #206).
    """
    ref = (pr.get("head") or {}).get("ref", "") or ""
    if ref.startswith("chore/engine-bump-"):
        return True
    repo = (pr.get("head") or {}).get("repo") or {}
    return (repo.get("full_name") or "") == UPSTREAM_SLUG


def upstream_remote(repo: str, run_git=None, log=None) -> str:
    """Name of the remote whose URL is the upstream repo; added when absent.

    `origin` is the upstream in one clone and the fork in another (issue #206),
    so the remote is resolved from its URL, never from its name. A clone with no
    upstream remote gets one named `upstream`; only a checkout where that cannot
    be added keeps the `origin` behaviour.
    """
    run_git = run_git or (lambda *a, **k: subprocess.run(
        ["git", "-C", repo, *a], capture_output=True, text=True, **k))
    log = log or (lambda *a, **k: None)
    r = run_git("remote", "-v")
    for line in (r.stdout or "").splitlines():
        parts = line.split()
        if len(parts) >= 2 and UPSTREAM_SLUG in parts[1].replace(":", "/"):
            return parts[0]
    add = run_git("remote", "add", "upstream", UPSTREAM_URL)
    if add.returncode == 0:
        log(f"  added remote `upstream` -> {UPSTREAM_URL} (issue #206)")
        return "upstream"
    log("  no upstream remote and cannot add one -> syncing against origin")
    return "origin"


def upstream_main(repo: str, run_git=None, log=None) -> str:
    """The ref an engine-bump PR is rebased / forward-merged onto: <upstream>/main."""
    return f"{upstream_remote(repo, run_git, log)}/main"


def sync_pr_with_main(pr, repo: str, run_git=None, log=None) -> bool:
    """Bring a behind engine-bump PR's head up to date with the upstream `main`.

    issue #9: a PR that is behind main MUST NOT be merged out of sync. Instead of
    merely skipping it, forward-merge the upstream main into the PR branch so it
    no longer drifts, then let CI re-run so the gate re-attempts on a later tick.
    Conflicts are never auto-resolved — if a merge conflict arises, leave the
    branch for its worker to resolve and return False (the PR stays NOT merged).

    issue #206: ONLY the engine-bump bot's PRs are forward-merged against the
    UPSTREAM `asimov-agent/main`, fetched from and pushed back to the upstream
    remote (their branches live there, not on the fork). Every other PR is
    synced against `origin/main` exactly as before.

    Returns True if the PR head is now in sync with main, False otherwise.
    """
    run_git = run_git or (lambda *a, **k: subprocess.run(
        ["git", "-C", repo, *a], capture_output=True, text=True, **k))
    log = log or (lambda *a, **k: None)
    head_ref = pr["head"]["ref"]
    head_sha = pr["head"]["sha"]
    n = pr["number"]
    if is_engine_bump_pr(pr):
        remote = upstream_remote(repo, run_git, log)  # the remote holding the branch (#206)
    else:
        remote = "origin"
    main_ref = f"{remote}/main"
    r = run_git("fetch", remote, f"+refs/heads/{head_ref}:refs/remotes/{remote}/{head_ref}")
    if r.returncode != 0:
        log(f"  PR#{n}: sync fetch failed for {head_ref}: {r.stderr.strip()[:120]}")
        return False
    run_git("branch", "-D", "_dispatch_sync")  # clear any stale temp branch
    r = run_git("branch", "_dispatch_sync", f"{remote}/{head_ref}")
    if r.returncode != 0:
        log(f"  PR#{n}: cannot create temp sync ref: {r.stderr.strip()[:120]}")
        return False
    r = run_git(
        "merge", main_ref, "--no-ff",
        "-m", f"chore: sync to latest {main_ref} before merge (issue #9, PR #{n})",
    )
    if r.returncode != 0:
        run_git("merge", "--abort")
        run_git("branch", "-D", "_dispatch_sync")
        log(f"  PR#{n}: merge conflict syncing {head_ref} onto {main_ref} -> needs manual "
            f"resolution, NOT merged (issue #9)")
        return False
    # Advance the PR branch to the synced head. force-with-lease pins to the known sha
    # so we never clobber newer commits a worker pushed concurrently.
    r = run_git(
        "push", remote, "_dispatch_sync:" + head_ref,
        f"--force-with-lease={head_ref}:{head_sha}",
    )
    run_git("branch", "-D", "_dispatch_sync")
    if r.returncode != 0:
        log(f"  PR#{n}: sync push failed for {head_ref}: {r.stderr.strip()[:160]}")
        return False
    log(f"  PR#{n}: {head_ref} synced to {main_ref} (merge forward); CI must re-run, "
        "re-attempting gate next tick")
    return True
