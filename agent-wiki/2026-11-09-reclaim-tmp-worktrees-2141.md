# reclaim-tmp-worktrees: a safe collector for /tmp worktree and probe-tree debris (#2141)

The shared host tmpfs hit ZERO free inodes once (three directories alone held 457,032
of the 1,048,576 inodes) and nothing reclaimed it: `make check-host-space` only measures
and refuses, it never deletes, and lanes hand-cut probe trees into `/tmp` (`attr1696`,
`base2071`, `verify2127`, ...) that nothing later cleaned. `scripts/reclaim_tmp_worktrees.sh`
(`make reclaim-tmp-worktrees`, issue #2141) is the DELETE side of that preflight.

## The safety contract (a tree is removed only when it cannot lose work)

A **registered worktree** is deleted only when all three hold: its working tree is clean
(`git status --porcelain` empty), its HEAD is an ancestor of `origin/main` (the content is
already merged), and it has been idle at least `MIN_IDLE_MIN` minutes. A dirty tree and a
tree whose HEAD may be the only copy of novel work are reported, never deleted.

`FORCE=1` drops the on-main and idle tests but NEVER the uncommitted-files refusal. Before a
forced removal of a NOVEL head (not an ancestor of the base and on no remote branch) the head
is PINNED as `refs/reclaimed/<worktree-name>` inside the collector's repo and verified with
`git for-each-ref refs/reclaimed` (issue #2141; the previous 41 pins were made by hand). An
unpinnable novel head is reported, never deleted. `git worktree remove` failures caused by
root-owned container-build files are reported with the exact `sudo rm -rf <path>` remedy
(no passwordless sudo -> a lane cannot delete them, and the script says the one command that
does instead of pretending it cleaned them).

A second pass handles **deregistered debris** — a directory under the scan root absent from
`git worktree list` (a `.git`-file worktree remnant, or a cache-only tree of root-owned
`__pycache__`/`.pytest_cache` left by a container build). It deletes only when its head is
pinned; the four measured operator directories (`/tmp/Notification Cache`, `/tmp/hf`,
`/tmp/gatepkg`, `/tmp/1898-unzip` shapes) are reproduced as test fixtures and never touched.

## The defaults and overrides

`DRY=1` is the DEFAULT and deletes (and pins) NOTHING — `DRY=0` acts. `SCAN_ROOT=` (default
`/tmp`, NOT `$TMP` — Hermes sets `TMP` to the agent scratch dir), `REPO=` (default
`$HOME/repository/git/llgenie`), `MIN_IDLE_MIN=` (default 60), `BASE=` and `FORCE=` all
override. The Makefile target reads them from the environment with `DRY` defaulting to `1`.

## What was verified

`tests/test_reclaim_tmp_worktrees.py` (6 tests, real git fixtures, no mocks) proves, on a
real temp repo with real worktrees:

- `DRY=1` deletes nothing: a reclaimable tree survives and the `df -i` free-inode count is
  unchanged; only `would reclaim` is printed;
- the three refusals + the negative control: dirty kept, head-not-on-main kept, active
  (< `MIN_IDLE_MIN`) kept, and a clean+on-main+idle tree reported as reclaimable;
- `FORCE=1 DRY=1` reports the wider set while writing no pin and deleting nothing, and
  `FORCE=1` real still keeps the dirty tree while pinning the novel head —
  `git for-each-ref refs/reclaimed` then lists `refs/reclaimed/w-novel` at the novel head
  BEFORE the tree is removed;
- the debris pass excludes the four operator-dir fixtures, clears a pinned-head debris dir,
  and reports an unpinned-novel debris head with the exact `sudo rm -rf <path>` remedy and
  never deletes it.

A live root-owned cache-only reproduction needs passwordless sudo (measured on this host:
`sudo -n true` requires a password), so the debris proof exercises the `.git`-file worktree-
remnant shape, which needs no privilege.

Writing `$HOME`, never `/home/asimov`, in every doc/agents file touched (issue #2145). No
container-build configuration changed: detection + the `sudo rm -rf` remedy are this issue's
scope, not the `--user` build fix. This lane never merges and never arms auto-merge; the PR
stops reviewable at `closes #2141`.
