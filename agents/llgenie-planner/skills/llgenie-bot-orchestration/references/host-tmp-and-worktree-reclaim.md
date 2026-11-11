# Host /tmp: the shared tmpfs, why it fills, and how to reclaim it safely

`/tmp` is a **32G / 1,048,576-inode tmpfs** every lane shares for worktrees, probes and container
builds. It can hit **zero free inodes**, and a full tmpfs does not degrade — it wedges the next lane
that writes, with no tree state saved, and surfaces as an unrelated-looking error in whatever that
lane was doing.

## Gate first, every pass

```bash
make check-host-space     # reads BOTH axes; exits 1 below <20% space OR <50,000 free inodes
```

Run it before measuring the board and before any dispatch that opens a `/tmp` worktree or container
build. If it fails: report both numbers and **refuse the dispatch** — a doomed run costs more than a
skipped one.

## The three causes, all measured

1. **A few directories can hold half the tmpfs.** Three probe dirs held **457,032 inodes = 43%** of the
   whole tmpfs and appear nowhere in the tree. Find them with
   `for d in /tmp/*; do echo "$(find "$d" 2>/dev/null | wc -l)|$d"; done | sort -t'|' -k1 -rn | head`.
2. **Ad-hoc probe worktrees in /tmp.** Dozens of registered worktrees under /tmp held ~70% of live
   inodes. Heavy worktrees belong on **real disk under `$HOME/repository/git/llgenie-wt/`**;
   kanban honours it (`.worktrees/t_*`), but lanes hand-cut `attr<issue>`, `main<issue>`, `verify<issue>`…
3. **Lanes cannot always clean up after themselves.** Container builds run as **root** and leave
   root-owned files (`__pycache__/`, `.pytest_cache/`, `*.pyc`) inside an `asimov`-owned tree, so
   `git worktree remove --force` fails `Permission denied` on a tree the lane owns.

## What is safe to delete

Default (no force) — delete **only** when all three hold:

- the working tree is **clean** (`git -C <wt> status --porcelain` empty),
- `HEAD` is an **ancestor of `origin/main`** (`git merge-base --is-ancestor $(git -C <wt> rev-parse HEAD) origin/main`) — the content is already merged,
- it has been **idle** long enough that nobody is mid-probe.

**Report and never delete**: uncommitted files; a head on **no remote ref** (that tree may be the only
copy); a removal that fails on root-owned files.

## FORCE — what it may and may not drop

When the owner authorises forced removal, `FORCE=1` drops the **idle** and **on-`main`** requirements.
It must **never** drop the uncommitted-files refusal: force is for staleness, not for discarding a
lane's edits, and a dirty tree can be the only copy of work in progress.

**Pin before you force.** A head that exists on no remote ref is destroyed by worktree removal, so
archive it first — this costs nothing and makes force removal non-destructive:

```bash
git update-ref "refs/reclaimed/$(basename "$w")" "$(git -C "$w" rev-parse HEAD)"
git for-each-ref refs/reclaimed          # verify the pins exist
```

## Deregistered debris — the blind spot that hides most of the waste

A directory under the scan root **absent from `git worktree list`** is a worktree whose
`.git/worktrees/<name>` admin dir is gone (a half-failed removal). `git worktree remove` refuses it, so
a collector that iterates only `git worktree list` **cannot see it at all** — measured: 38 such
directories held 194,934 inodes while the script reported `reclaimed=0`.

Scan a second pass over `"$SCAN_ROOT"/*/` and skip anything `git worktree list` already owns. Two
usable shapes:

- **a `.git` FILE but no admin dir** — a half-removed worktree;
- **no `.git`, no asimov-owned file, only root-owned cache** — the owned files were already deleted.

## Exclude the operator's own directories (the over-reach trap)

A naive "no owned files and no stray" test deletes legitimately empty or operator-owned directories —
an empty directory satisfies it trivially. Require **at least one actual root-owned cache artefact**
before treating a directory as container debris:

```bash
caches=$(find "$w" ! -user "$(id -un)" \( -name '__pycache__' -o -name '.pytest_cache' \) 2>/dev/null | wc -l)
[ "$caches" -gt 0 ] || continue
```

And test for owned **files**, not owned paths — the surviving asimov-owned **directories** are the
skeleton the root-owned caches sit in and do not mean the tree is in use:

```bash
[ "$(find "$w" -user "$(id -un)" -type f 2>/dev/null | wc -l)" = "0" ] || continue
```

Verify the exclusions by name after tightening, not by the match count dropping: a real operator
directory and an empty one must both be reported as excluded.

## Root-owned leftovers

Try `sudo -n rm -rf "$w"` first; if sudo needs a password, **report the exact remedy and move on**:

```
BLOCKED <path> — root-owned files remain; a human must run: sudo rm -rf <path>
```

Never retry a removal that cannot succeed, and never let a permission failure stall the rest of the
pass. The durable fix is on the build side: run containers with `--user $(id -u):$(id -g)` so they stop
creating root-owned files inside an asimov-owned tree.

## Never blanket-prune

Do **not** use `git worktree prune` / `git worktree remove` as a fleet sweep. Their "already merged"
test reads the **branch ref only** and cannot see uncommitted work, so they destroy a mid-flight run —
which is why the repo gates `make worktree-prune` behind `CONFIRM=1`.

## The variable collision that silently scans the wrong place

Do **not** name the scan root `TMP`: the Hermes environment sets `TMP`/`TMPDIR` to the agent scratch
dir, so `TMP="${TMP:-/tmp}"` scans the scratch dir and the script reports `reclaimed=0` while `df -i`
shows a full tmpfs. Use `SCAN_ROOT`.

## Collector

`scripts/reclaim_tmp_worktrees.sh` applies everything above. **Dry-run first, always** — it prints the
plan and deletes nothing (`DRY=1`), including under `FORCE=1`.

```bash
DRY=1            bash scripts/reclaim_tmp_worktrees.sh   # plan only
DRY=1 FORCE=1    bash scripts/reclaim_tmp_worktrees.sh   # plan the wider set
FORCE=1          bash scripts/reclaim_tmp_worktrees.sh   # reclaim (pin novel heads first)
```

It prints a per-class summary (`registered:` / `debris:` with `reclaimed=`, `kept:` and `blocked_root=`)
and the current free-inode count, so a pass can quote numbers instead of adjectives.
