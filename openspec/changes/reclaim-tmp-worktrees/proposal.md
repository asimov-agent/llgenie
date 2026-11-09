# reclaim-tmp-worktrees — proposal

Issue: [#2141](https://github.com/asimov-agent/llgenie/issues/2141)

## Why

`/tmp` tipped **zero free inodes** once — three directories alone held 457,032 of the 1,048,576
tmpfs inodes — and nothing reclaimed it. `make check-host-space` only measures and refuses; it never
deletes, and lanes hand-cut probe/attribution trees into `/tmp` (`attr1696`, `base2071`,
`verify2127`, ...) that nothing later cleaned. The preflight that refuses doomed builds has no safe
way to reclaim what a build left behind.

## What Changes

This lands the DELETE half of that preflight: `scripts/reclaim_tmp_worktrees.sh` +
`make reclaim-tmp-worktrees`. A registered worktree is removed only when it is clean AND its `HEAD`
is an ancestor of `origin/main` AND idle >= `MIN_IDLE_MIN`. `DRY=1` is the default and deletes (and
pins) NOTHING. `FORCE=1` drops the on-main and idle tests but **never** the uncommitted-files
refusal, and before a forced removal of a novel head (on no remote ref) it pins that head as
`refs/reclaimed/<worktree-name>` inside the collector's repo and verifies it with
`git for-each-ref refs/reclaimed` — a forced removal can no longer destroy the only copy of a lane's
work (the prior 41 pins were made by hand). A second pass clears deregistered debris (a `.git`
remnant, or cache-only root-owned `__pycache__`/`.pytest_cache`) only when head-pinned; root-owned
leftovers are reported with the exact `sudo rm -rf <path>` remedy instead of being retried. The four
measured operator directories (`/tmp/Notification Cache`, `/tmp/hf`, `/tmp/gatepkg`,
`/tmp/1898-unzip` shapes) are reproduced as fixtures and never touched.

The make target is `DRY=1` by default (`DRY=0` to act), passes `FORCE=1` through, and honours
`SCAN_ROOT=`/`REPO=`/`MIN_IDLE_MIN=` overrides. The host-space tick step names the target by name in
the docs, and the placement rule for ad-hoc probe trees is stated under
`$HOME/repository/git/llgenie-wt/` (never `/tmp`) in `agents/standing-rules.md`.
