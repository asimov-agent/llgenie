#!/usr/bin/env bash
# Reclaim /tmp worktrees and probe debris that are safe to delete.
#
# WHY: /tmp is a shared 32G / 1,048,576-inode tmpfs. At zero free inodes it wedges the
# next lane that writes, with no tree state saved. See
# references/host-tmp-and-worktree-reclaim.md for the full rationale and the measured causes.
#
# SAFETY MODEL — default (no force) deletes a registered worktree ONLY when:
#   1. clean working tree (no uncommitted files), AND
#   2. HEAD is an ancestor of BASE (content already merged), AND
#   3. idle for at least MIN_IDLE_MIN minutes.
# FORCE=1 drops (2) and (3) but NEVER (1): force is for staleness, not for discarding edits.
# A deregistered directory is only touched when it is cache-only debris (see below).
#
# BEFORE using FORCE=1, pin any head that exists on no remote ref:
#   git update-ref "refs/reclaimed/$(basename "$w")" "$(git -C "$w" rev-parse HEAD)"
#
# Usage:
#   DRY=1         bash reclaim_tmp_worktrees.sh    # plan only (deletes nothing)
#   DRY=1 FORCE=1 bash reclaim_tmp_worktrees.sh    # plan the wider set
#   FORCE=1       bash reclaim_tmp_worktrees.sh    # reclaim
set -uo pipefail

REPO="${REPO:-$HOME/repository/git/llgenie}"
BASE="${BASE:-origin/main}"
MIN_IDLE_MIN="${MIN_IDLE_MIN:-60}"
DRY="${DRY:-0}"
FORCE="${FORCE:-0}"
# NOT $TMP: the Hermes environment sets TMP/TMPDIR to the agent scratch dir, so
# TMP="${TMP:-/tmp}" would silently scan the wrong place and report reclaimed=0.
SCAN_ROOT="${SCAN_ROOT:-/tmp}"

cd "$REPO" || { echo "[reclaim] cannot cd $REPO" >&2; exit 1; }
git rev-parse --verify "$BASE" >/dev/null 2>&1 || { echo "[reclaim] $BASE does not resolve" >&2; exit 1; }

now=$(date +%s)
removed=0; freed=0; kept_novel=0; kept_dirty=0; blocked_root=0; kept_active=0
debris=0; debris_freed=0; debris_blocked=0; debris_kept=0
say() { printf '[reclaim] %s\n' "$*"; }
self=$(id -un)

# ---- pass 1: registered worktrees under the scan root ------------------------
for w in $(git worktree list --porcelain 2>/dev/null | awk -v t="$SCAN_ROOT/" '/^worktree /{if (index($2,t)==1) print $2}'); do
  [ -d "$w" ] || { say "gone (record only): $w"; continue; }

  n=$(find "$w" 2>/dev/null | wc -l)
  dirty=$(git -C "$w" status --porcelain 2>/dev/null | wc -l)
  m=$(stat -c %Y "$w" 2>/dev/null || echo "$now")
  idle=$(( (now - m) / 60 ))

  # NEVER relaxed, even under FORCE: a dirty tree may be the only copy of a lane's work.
  if [ "$dirty" -gt 0 ]; then
    say "KEEP  $w — $dirty uncommitted file(s); never delete another lane's work"
    kept_dirty=$((kept_dirty+1)); continue
  fi

  head=$(git -C "$w" rev-parse HEAD 2>/dev/null || true)
  if [ -z "$head" ]; then
    say "KEEP  $w — cannot resolve HEAD; touch nothing"
    kept_novel=$((kept_novel+1)); continue
  fi

  if ! git merge-base --is-ancestor "$head" "$BASE" 2>/dev/null; then
    if [ "$FORCE" != "1" ]; then
      say "KEEP  $w — head ${head:0:8} is NOT on $BASE; may hold the only copy (FORCE=1 to remove)"
      kept_novel=$((kept_novel+1)); continue
    fi
    say "FORCED $w — head ${head:0:8} not on $BASE, FORCE=1 given"
  fi

  if [ "$FORCE" != "1" ] && [ "$idle" -lt "$MIN_IDLE_MIN" ]; then
    say "KEEP  $w — active ${idle}m ago (< ${MIN_IDLE_MIN}m)"
    kept_active=$((kept_active+1)); continue
  fi

  if [ "$DRY" = "1" ]; then
    say "would reclaim $w — head ${head:0:8}, idle ${idle}m, $n inodes"
    removed=$((removed+1)); freed=$((freed+n)); continue
  fi

  if git worktree remove --force "$w" 2>/dev/null; then
    say "reclaimed $w — head ${head:0:8}, idle ${idle}m, $n inodes"
    removed=$((removed+1)); freed=$((freed+n))
  elif sudo -n rm -rf "$w" 2>/dev/null; then
    say "reclaimed (sudo) $w — root-owned files cleared, $n inodes"
    removed=$((removed+1)); freed=$((freed+n))
  else
    say "BLOCKED $w — root-owned files remain; a human must run: sudo rm -rf $w"
    blocked_root=$((blocked_root+1))
  fi
done

# ---- pass 2: deregistered debris ---------------------------------------------
# A dir under the scan root ABSENT from `git worktree list` is a worktree whose
# .git/worktrees/<name> admin dir is gone. `git worktree remove` refuses it, so pass 1
# cannot see it at all — this is where most of the waste hides.
for w in "$SCAN_ROOT"/*/; do
  w="${w%/}"
  [ -d "$w" ] || continue
  git worktree list --porcelain 2>/dev/null | grep -qx "worktree $w" && continue

  if [ ! -f "$w/.git" ]; then
    # Cache-only debris test. Two guards, both essential:
    #   (a) no asimov-owned FILE may remain — owned DIRECTORIES are just the skeleton
    #       the root-owned caches sit in and do not mean the tree is in use;
    #   (b) at least one actual root-owned cache artefact must exist, otherwise an
    #       empty directory or an operator's own dir matches and gets deleted.
    [ "$(find "$w" -user "$self" -type f 2>/dev/null | wc -l)" = "0" ] || continue
    stray=$(find "$w" ! -user "$self" 2>/dev/null \
              | grep -vE '/(__pycache__|\.pytest_cache)(/|$)' | grep -vE '\.pyc$' | head -1)
    [ -z "$stray" ] || continue
    caches=$(find "$w" ! -user "$self" \( -name '__pycache__' -o -name '.pytest_cache' \) 2>/dev/null | wc -l)
    [ "$caches" -gt 0 ] || continue
  fi

  name=$(basename "$w")
  n=$(find "$w" 2>/dev/null | wc -l)
  pinned=$(git rev-parse --verify "refs/reclaimed/$name" 2>/dev/null || true)

  if [ -z "$pinned" ] && [ "$FORCE" != "1" ]; then
    say "KEEP  $w — deregistered debris, head not pinned as refs/reclaimed/$name (FORCE=1 to remove)"
    debris_kept=$((debris_kept+1)); continue
  fi
  [ -z "$pinned" ] && say "FORCED $w — deregistered debris, head UNPINNED, FORCE=1 given (work may be lost)"

  if [ "$DRY" = "1" ]; then
    say "would clear deregistered debris $w — $n inodes, pinned=${pinned:0:8}"
    debris=$((debris+1)); debris_freed=$((debris_freed+n)); continue
  fi

  find "$w" -user "$self" -delete 2>/dev/null
  if rm -rf "$w" 2>/dev/null; then
    say "cleared deregistered debris $w — $n inodes"
    debris=$((debris+1)); debris_freed=$((debris_freed+n))
  else
    say "BLOCKED $w — root-owned files remain ($(find "$w" 2>/dev/null | wc -l) entries); a human must run: sudo rm -rf $w"
    debris_blocked=$((debris_blocked+1))
  fi
done

say "----"
say "registered: reclaimed=$removed inodes~$freed | kept: novel=$kept_novel dirty=$kept_dirty active=$kept_active blocked_root=$blocked_root"
say "debris:     cleared=$debris inodes~$debris_freed kept_unpinned=$debris_kept blocked_root=$debris_blocked"
say "inodes free now: $(df -i "$SCAN_ROOT" 2>/dev/null | awk 'NR==2{print $4}')"
[ $((blocked_root + debris_blocked)) -gt 0 ] && \
  say "NOTE: root-owned leftovers need a human with sudo — run builds with --user \$(id -u):\$(id -g) to stop the class recurring."
exit 0
