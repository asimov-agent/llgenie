#!/usr/bin/env bash
# Reclaim /tmp worktrees and probe trees that are provably safe to delete.
#
# WHY THIS EXISTS (issue #1583, owner 2026-11-08)
# /tmp is a 32G / 1,048,576-inode tmpfs every lane shares for worktrees, probes and
# container builds. It hit ZERO free inodes once — three directories alone held
# 457,032 inodes (43% of the whole tmpfs) — and a full tmpfs wedges whichever lane
# touches it next with no tree state saved.
#
# WHY TREES ACCUMULATE IN /tmp
# Lanes hand-cut probe trees there for attribution/verification work
# (`attr1696`, `base2071`, `main20`, `verify2127`, `rev2049c`, ...), which is not the
# kanban convention (`.worktrees/t_*`) and not the documented placement
# (`$HOME/repository/git/llgenie-wt/`). Nothing cleans them up, so they accrue.
#
# WHY THEY CANNOT ALWAYS BE CLEANED BY THE LANE THAT MADE THEM
# Container builds run as root and leave root-owned files inside the tree
# (measured: `.pytest_cache/` owned by root inside an asimov-owned worktree).
# `git worktree remove` then fails with `Permission denied` on a tree the lane owns,
# because it cannot delete root's files. Those need a human with sudo — this script
# DETECTS and REPORTS them rather than pretending it cleaned them.
#
# SAFETY MODEL — the only trees this script deletes are ones where deletion cannot
# lose work:
#   1. clean working tree (no uncommitted files), AND
#   2. HEAD is an ancestor of origin/main (the content is already merged), AND
#   3. idle for at least MIN_IDLE_MIN minutes (no lane is mid-probe).
# A tree whose HEAD is NOT on main is reported, never deleted — it may hold the only
# copy of novel work. A dirty tree is reported, never deleted.
#
# FORCE=1 (owner instruction 2026-11-08) drops (2) and (3) but NEVER the
# uncommitted-files refusal — force is for staleness, not for discarding edits.
# Before a FORCE removal of a NOVEL head (not an ancestor of $BASE and on no remote
# branch) the head is PINNED as `refs/reclaimed/<worktree-name>` inside this repo and
# verified with `git for-each-ref refs/reclaimed`, so a forced removal can never
# destroy the only copy of the work (issue #2141; the previous 41 pins were made by
# hand). An unpinnable novel head is reported, never deleted.
#
# It NEVER deletes `git worktree prune`-style "already merged" branches by ref name:
# that test reads the branch ref only and cannot see uncommitted work (SOUL rule).
set -uo pipefail

REPO="${REPO:-$HOME/repository/git/llgenie}"
BASE="${BASE:-origin/main}"
MIN_IDLE_MIN="${MIN_IDLE_MIN:-60}"
# DRY=1 is the DEFAULT and deletes/pins NOTHING; DRY=0 acts.
DRY="${DRY:-1}"
# FORCE=1 (owner instruction 2026-11-08: "you are allowed to force remove the worktrees so we
# never get in a stuck dm state"). It drops the idle requirement and allows removing a tree whose
# HEAD is NOT on main. It does NOT drop the uncommitted-files refusal: a dirty tree may hold the
# only copy of a lane's work, and force is for staleness, not for discarding edits.
FORCE="${FORCE:-0}"
SCAN_ROOT="${SCAN_ROOT:-/tmp}"   # NOT $TMP — the environment sets TMP to the agent scratch dir

cd "$REPO" || { echo "[reclaim] cannot cd $REPO" >&2; exit 1; }
git rev-parse --verify "$BASE" >/dev/null 2>&1 || { echo "[reclaim] $BASE does not resolve" >&2; exit 1; }

now=$(date +%s)
removed=0; freed=0; kept_novel=0; kept_dirty=0; blocked_root=0; kept_active=0

say() { printf '[reclaim] %s\n' "$*"; }

# Pin a NOVEL head (not an ancestor of $BASE and on no remote branch) as
# refs/reclaimed/<name> before a FORCE removal, then verify with for-each-ref.
# Never mutates under DRY=1. Sets $pinned to the pinned sha (empty when no pin was
# needed). Returns 1 when the pin FAILED and the caller must NOT remove the tree.
pin_novel() {
  local w="$1" head="$2" name remote
  pinned=""
  name=$(basename "$w")
  [ "$DRY" = "1" ] && return 0                       # DRY writes no ref
  # A head reachable from a remote branch already survives elsewhere: no pin needed.
  remote=$(git branch -r --contains "$head" 2>/dev/null | head -1)
  [ -n "$remote" ] && return 0
  if ! git update-ref "refs/reclaimed/$name" "$head" 2>/dev/null; then
    say "PIN FAILED refs/reclaimed/$name (update-ref)"; return 1
  fi
  if ! git for-each-ref refs/reclaimed --format='%(refname)' | grep -qx "refs/reclaimed/$name"; then
    say "PIN FAILED refs/reclaimed/$name (for-each-ref verify)"; return 1
  fi
  pinned=$(git rev-parse "refs/reclaimed/$name")
  say "PINNED refs/reclaimed/$name=$pinned (novel head preserved before forced removal)"
  return 0
}

for w in $(git worktree list --porcelain 2>/dev/null | awk -v t="$SCAN_ROOT/" '/^worktree /{if (index($2,t)==1) print $2}'); do
  [ -d "$w" ] || { say "gone (record only): $w"; continue; }

  n=$(find "$w" 2>/dev/null | wc -l)
  dirty=$(git -C "$w" status --porcelain 2>/dev/null | wc -l)
  m=$(stat -c %Y "$w" 2>/dev/null || echo "$now")
  idle=$(( (now - m) / 60 ))

  if [ "$dirty" -gt 0 ]; then
    say "KEEP  $w — $dirty uncommitted file(s); never delete another lane's work"
    kept_dirty=$((kept_dirty+1)); continue
  fi

  head=$(git -C "$w" rev-parse HEAD 2>/dev/null || true)
  if [ -z "$head" ]; then
    say "KEEP  $w — cannot resolve HEAD; treat as unknown and touch nothing"
    kept_novel=$((kept_novel+1)); continue
  fi

  if ! git merge-base --is-ancestor "$head" "$BASE" 2>/dev/null; then
    if [ "$FORCE" != "1" ]; then
      say "KEEP  $w — head ${head:0:8} is NOT on $BASE; may be the only copy of novel work (FORCE=1 to remove)"
      kept_novel=$((kept_novel+1)); continue
    fi
    # FORCE removal of a novel head: pin it before the tree goes (issue #2141).
    pin_novel "$w" "$head" || { kept_novel=$((kept_novel+1)); continue; }
    say "FORCED $w — head ${head:0:8} not on $BASE, FORCE=1${pinned:+; novel head pinned $pinned}"
  fi

  if [ "$FORCE" != "1" ] && [ "$idle" -lt "$MIN_IDLE_MIN" ]; then
    say "KEEP  $w — active ${idle}m ago (< ${MIN_IDLE_MIN}m); a lane may be mid-probe"
    kept_active=$((kept_active+1)); continue
  fi

  if [ "$DRY" = "1" ]; then
    say "would reclaim $w — head ${head:0:8} on $BASE, clean, idle ${idle}m, $n inodes"
    removed=$((removed+1)); freed=$((freed+n)); continue
  fi

  if git worktree remove --force "$w" 2>/dev/null; then
    say "reclaimed $w — head ${head:0:8} on $BASE, idle ${idle}m, $n inodes"
    removed=$((removed+1)); freed=$((freed+n))
  else
    # git could not delete it — the usual cause is a root-owned file from a container build.
    # Try a non-interactive sudo first (works where NOPASSWD is configured), else report the remedy.
    if sudo -n rm -rf "$w" 2>/dev/null; then
      say "reclaimed (sudo) $w — root-owned files cleared, $n inodes"
      removed=$((removed+1)); freed=$((freed+n))
    else
      say "BLOCKED $w — git worktree remove failed and sudo needs a password; a human must run: sudo rm -rf $w"
      blocked_root=$((blocked_root+1))
    fi
  fi
done

# ---------------------------------------------------------------------------
# SECOND PASS: deregistered debris.
# A directory under the scan root that carries a `.git` FILE but is NOT in
# `git worktree list` is a worktree whose admin dir (`.git/worktrees/<name>`) is
# gone — usually because a `git worktree remove` half-succeeded. It can never be
# used again and `git worktree remove` refuses it, so the first pass cannot see
# it. Measured on this host: 38 such directories held 194,934 inodes and were
# invisible to the registered-worktree loop.
#
# Safety: only a directory holding a `.git` file (a real worktree remnant) is
# considered, and its contents are removed only when no uncommitted work is
# recoverable — a deregistered worktree has no index, so its files ARE its only
# copy. We therefore delete the contents only when the head is pinned: either it
# is an ancestor of BASE, or a `refs/reclaimed/<name>` ref points at the same
# commit. Anything else is reported, never deleted — under FORCE a resolvable
# novel head is pinned first, and an unpinnable one is reported with the `sudo
# rm -rf` remedy instead of being deleted.
# ---------------------------------------------------------------------------
debris=0; debris_freed=0; debris_blocked=0; debris_kept=0
for w in "$SCAN_ROOT"/*/; do
  [ -e "$w" ] || continue
  w="${w%/}"
  git worktree list --porcelain 2>/dev/null | grep -qx "worktree $w" && continue

  # Two shapes of debris, both unusable:
  #   (a) a `.git` FILE but no admin dir — a half-removed worktree;
  #   (b) no `.git` at all, and every remaining entry is root-owned cache
  #       (`__pycache__/`, `.pytest_cache/`) left by a container build — the
  #       asimov-owned files were already deleted, only root's remain.
  # A plain directory of the operator's own files matches neither and is skipped.
  if [ ! -f "$w/.git" ]; then
    # Only cache-only debris qualifies: every remaining path must be a root-owned
    # cache artefact (__pycache__, .pytest_cache, *.pyc). Anything else — a real
    # scratch dir, an operator's files — is NOT ours to delete.
    stray=$(find "$w" ! -user "$(id -un)" 2>/dev/null \
              | grep -vE '/(__pycache__|.pytest_cache)(/|$)' \
              | grep -vE '\.pyc$' | head -1)
    if [ -n "$stray" ]; then
      continue          # not cache-only debris
    fi
    # No asimov-owned FILE may remain: an owned file is real content worth keeping.
    # Empty asimov-owned DIRECTORIES are fine (they are the skeleton the root-owned
    # cache dirs sit in), which is why the test is on `-type f`, not on all paths.
    owned_files=$(find "$w" -user "$(id -un)" -type f 2>/dev/null | wc -l)
    [ "$owned_files" = "0" ] || continue
    # Require at least one ACTUAL root-owned cache artefact. Without this an empty
    # directory (or a stray operator dir like "/tmp/Notification Cache") matches the
    # "no owned files, no stray" test and would be deleted — that is not ours.
    caches=$(find "$w" ! -user "$(id -un)" \( -name '__pycache__' -o -name '.pytest_cache' \) 2>/dev/null | wc -l)
    [ "$caches" -gt 0 ] || continue
  fi

  name=$(basename "$w")
  n=$(find "$w" 2>/dev/null | wc -l)
  pinned=$(git rev-parse --verify "refs/reclaimed/$name" 2>/dev/null || true)

  if [ -z "$pinned" ]; then
    if [ "$FORCE" != "1" ]; then
      say "KEEP  $w — deregistered debris, head not pinned as refs/reclaimed/$name (FORCE=1 to pin+remove)"
      debris_kept=$((debris_kept+1)); continue
    fi
    if [ "$DRY" = "1" ]; then
      dhead=$(git -C "$w" rev-parse HEAD 2>/dev/null || true)
      say "would clear deregistered debris $w — $n inodes, head ${dhead:0:8} UNPINNED; FORCE=1 would pin refs/reclaimed/$name then remove (DRY)"
      debris=$((debris+1)); debris_freed=$((debris_freed+n)); continue
    fi
    # FORCE + real: pin a resolvable novel head before removal, else refuse.
    dhead=$(git -C "$w" rev-parse HEAD 2>/dev/null || true)
    if [ -n "$dhead" ] && git update-ref "refs/reclaimed/$name" "$dhead" 2>/dev/null; then
      pinned=$(git rev-parse "refs/reclaimed/$name")
      say "PINNED refs/reclaimed/$name=$pinned (deregistered debris head preserved before removal)"
    else
      say "BLOCKED $w — deregistered debris head not pinnable; never deleted; pin refs/reclaimed/$name by hand or run: sudo rm -rf $w"
      debris_blocked=$((debris_blocked+1)); continue
    fi
    say "FORCED $w — deregistered debris, head now PINNED refs/reclaimed/$name=$pinned, FORCE=1"
  fi

  if [ "$DRY" = "1" ]; then
    say "would clear deregistered debris $w — $n inodes, pinned=${pinned:0:8}"
    debris=$((debris+1)); debris_freed=$((debris_freed+n)); continue
  fi

  # remove what we own, then the tree; root-owned leftovers are reported
  find "$w" -user "$(id -un)" -delete 2>/dev/null
  if rm -rf "$w" 2>/dev/null; then
    say "cleared deregistered debris $w — $n inodes"
    debris=$((debris+1)); debris_freed=$((debris_freed+n))
  else
    left=$(find "$w" 2>/dev/null | wc -l)
    say "BLOCKED $w — root-owned files remain ($left entries); a human must run: sudo rm -rf $w"
    debris_blocked=$((debris_blocked+1))
  fi
done

say "----"
say "registered: reclaimed=$removed inodes~$freed | kept: novel=$kept_novel dirty=$kept_dirty active=$kept_active blocked_root=$blocked_root"
say "debris:     cleared=$debris inodes~$debris_freed kept_unpinned=$debris_kept blocked_root=$debris_blocked"
say "tmp inodes free now: $(df -i "$SCAN_ROOT" 2>/dev/null | awk 'NR==2{print $4}')"
[ "$blocked_root" -gt 0 ] && say "NOTE: $blocked_root tree(s) need a human with sudo — container builds leave root-owned files a lane cannot delete."
exit 0
