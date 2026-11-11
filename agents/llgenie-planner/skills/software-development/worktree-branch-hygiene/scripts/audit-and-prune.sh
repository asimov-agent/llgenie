#!/usr/bin/env bash
# audit-and-prune.sh — prune worktrees/branches that a MERGED PR landed, in a
# squash-merging repo, with the two-pass leftover cleanup that a root-owned
# container run forces.
#
#   DRY=1 bash audit-and-prune.sh          # audit only (default): prints every keep reason
#   DRY=0 bash audit-and-prune.sh          # prune, clear leftovers, prune again, report
#   WT_ROOT=../myrepo-wt DRY=0 bash …      # override the worktree root (default: ../<repo>-wt)
#
# Eligibility comes from the PR ONLY: ancestry lies in a squash-merging repo (a
# squashed tip is never an ancestor of the base). A branch is prunable when its PR
# is MERGED *and* that PR's mergeCommit.oid is on origin/<base>.
#
# Never prunable: the main checkout, the worktree this script is running in, a
# detached-HEAD worktree, a dirty worktree, a closed-unmerged PR, a branch with no
# PR (a human decision).
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
REPO_ROOT="$(pwd)"
DRY="${DRY:-1}"
BASE="${BASE:-master}"
REMOTE="${REMOTE:-origin}"
WT_ROOT="${WT_ROOT:-$(dirname "$REPO_ROOT")/$(basename "$REPO_ROOT")-wt}"
CURRENT="$REPO_ROOT"

MAP="$(mktemp)"; WT="$(mktemp)"; trap 'rm -f "$MAP" "$WT"' EXIT

gh pr list --state all --limit 500 --json number,state,headRefName,mergeCommit \
  | jq -r '.[] | "\(.headRefName)\t\(.number)\t\(.state)\t\(.mergeCommit.oid // "-")"' > "$MAP"
git fetch --all --prune >/dev/null 2>&1 || true
git worktree list --porcelain > "$WT"

declare -A WT_PATH
path=""
while IFS= read -r line; do
  case "$line" in
    "worktree "*) path="${line#worktree }" ;;
    "branch refs/heads/"*) WT_PATH["${line#branch refs/heads/}"]="$path" ;;
  esac
done < "$WT"

prunable=(); keep_pr=(); keep_nopr=(); keep_closed=(); keep_dirty=(); keep_other=()
for b in $(git for-each-ref --format='%(refname:short)' refs/heads); do
  [ "$b" = "$BASE" ] && continue
  p="${WT_PATH[$b]:-}"
  if [ -n "$p" ] && [ "$p" = "$CURRENT" ]; then keep_other+=("$b (the checkout this runs in)"); continue; fi
  if [ -n "$p" ] && [ -n "$(git -C "$p" status --porcelain 2>/dev/null)" ]; then keep_dirty+=("$b ($p)"); continue; fi
  state="$(awk -F'\t' -v b="$b" '$1==b {print $3}' "$MAP" | head -1)"
  num="$(awk -F'\t' -v b="$b" '$1==b {print $2}' "$MAP" | head -1)"
  oid="$(awk -F'\t' -v b="$b" '$1==b {print $4}' "$MAP" | head -1)"
  case "$state" in
    MERGED)
      if [ "$oid" != "-" ] && git merge-base --is-ancestor "$oid" "$REMOTE/$BASE" 2>/dev/null; then
        prunable+=("$b|#${num}|${p}")
      else
        keep_other+=("$b (#$num MERGED but its merge commit is not on $REMOTE/$BASE)")
      fi ;;
    CLOSED) keep_closed+=("$b (#$num)") ;;
    OPEN)   keep_pr+=("$b (#$num)") ;;
    "")     keep_nopr+=("$b") ;;
    *)      keep_other+=("$b (#$num $state)") ;;
  esac
done

report() {
  echo "worktrees: $(git worktree list --porcelain | grep -c '^worktree ')   local branches: $(git for-each-ref refs/heads | wc -l)"
  echo "PRUNABLE (merged + merge commit on $REMOTE/$BASE): ${#prunable[@]}"
  echo "KEEP  open PR: ${#keep_pr[@]}    closed-unmerged: ${#keep_closed[@]}    no PR: ${#keep_nopr[@]}    dirty/other: ${#keep_dirty[@]} ${#keep_other[@]}"
  for x in "${keep_pr[@]}" "${keep_closed[@]}" "${keep_dirty[@]}" "${keep_other[@]}"; do echo "  keep: $x"; done
  [ "${#keep_nopr[@]}" -gt 0 ] && { echo "  keep (no PR — a human decision):"; printf '    %s\n' "${keep_nopr[@]}"; }
  [ -d "$WT_ROOT" ] && echo "worktree root $WT_ROOT: $(du -sh "$WT_ROOT" 2>/dev/null | cut -f1)"
  return 0
}

report
if [ "$DRY" != "0" ]; then
  echo; echo "DRY RUN — nothing removed. Re-run with DRY=0 to prune ${#prunable[@]} merged branch(es)."
  exit 0
fi

# PASS 1 — remove what git can remove; a root-owned worktree fails AFTER being
# unregistered, so the branch is kept here on purpose (never strand a ref).
removed=0; failed=0
for x in "${prunable[@]}"; do
  b="${x%%|*}"; rest="${x#*|}"; p="${rest#*|}"
  if [ -n "$p" ] && ! git worktree remove "$p" 2>/dev/null; then
    failed=$((failed+1)); continue
  fi
  git branch -D "$b" >/dev/null 2>&1 && removed=$((removed+1)) || failed=$((failed+1))
done
echo; echo "pass 1: removed $removed, kept $failed (unremovable worktree or refused delete)"

# PASS 2 — clear the orphan directories a container run left root-owned, then prune
# again: the worktrees are already unregistered, so their branches are now free.
if [ -d "$WT_ROOT" ] && [ "$(find "$WT_ROOT" -maxdepth 1 -mindepth 1 -type d | wc -l)" -gt 0 ]; then
  KEEP=" $(git worktree list --porcelain | sed -n 's/^worktree //p' | tr '\n' ' ') "
  if [ "$(find "$WT_ROOT" -not -user "$(id -un)" 2>/dev/null | wc -l)" -gt 0 ] && command -v docker >/dev/null 2>&1; then
    docker run --rm -v "$WT_ROOT:/wt" alpine:latest sh -c 'chown -R 1000:1000 /wt' >/dev/null 2>&1 || true
  fi
  for d in "$WT_ROOT"/*; do
    [ -d "$d" ] || continue
    case "$KEEP" in *" $d "*) continue ;; esac
    rm -rf -- "$d" && echo "  cleared leftover $d"
  done
fi

# Re-classify from scratch: the prune is idempotent, and this is what actually
# deletes the branches whose worktrees could only be freed in pass 2.
unset WT_PATH; declare -A WT_PATH
git worktree list --porcelain > "$WT"
path=""
while IFS= read -r line; do
  case "$line" in
    "worktree "*) path="${line#worktree }" ;;
    "branch refs/heads/"*) WT_PATH["${line#branch refs/heads/}"]="$path" ;;
  esac
done < "$WT"
again=()
for x in "${prunable[@]}"; do
  b="${x%%|*}"
  git show-ref --verify --quiet "refs/heads/$b" || continue
  p="${WT_PATH[$b]:-}"
  [ -n "$p" ] && [ "$p" != "$CURRENT" ] && continue
  again+=("$b")
done
second=0
for b in "${again[@]:-}"; do
  [ -n "$b" ] || continue
  git branch -D "$b" >/dev/null 2>&1 && second=$((second+1))
done
git fetch --all --prune >/dev/null 2>&1 || true

echo
echo "pass 2: removed $second more branch(es)"
unset prunable; prunable=(); unset keep_pr keep_closed keep_nopr keep_dirty keep_other
keep_pr=(); keep_closed=(); keep_nopr=(); keep_dirty=(); keep_other=()
declare -A WT_PATH2
git worktree list --porcelain > "$WT"
path=""
while IFS= read -r line; do
  case "$line" in
    "worktree "*) path="${line#worktree }" ;;
    "branch refs/heads/"*) WT_PATH2["${line#branch refs/heads/}"]="$path" ;;
  esac
done < "$WT"
for b in $(git for-each-ref --format='%(refname:short)' refs/heads); do
  [ "$b" = "$BASE" ] && continue
  state="$(awk -F'\t' -v b="$b" '$1==b {print $3}' "$MAP" | head -1)"
  num="$(awk -F'\t' -v b="$b" '$1==b {print $2}' "$MAP" | head -1)"
  oid="$(awk -F'\t' -v b="$b" '$1==b {print $4}' "$MAP" | head -1)"
  case "$state" in
    MERGED) if [ "$oid" != "-" ] && git merge-base --is-ancestor "$oid" "$REMOTE/$BASE" 2>/dev/null; then prunable+=("$b"); else keep_other+=("$b (#$num MERGED, merge not on base)"); fi ;;
    CLOSED) keep_closed+=("$b (#$num)") ;;
    OPEN)   keep_pr+=("$b (#$num)") ;;
    "")     keep_nopr+=("$b") ;;
    *)      keep_other+=("$b (#$num $state)") ;;
  esac
done
report
