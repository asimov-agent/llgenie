#!/usr/bin/env bash
# post-rebase-verify.sh — run BEFORE any lease push of a rebased branch.
#
# Why this exists: on a single night the same two mistakes each cost a ~40-minute
# CI cycle, and both are invisible to `git rebase`'s own success message.
#
#   1. A conflict marker survived `git rebase --continue` (which printed
#      "Successfully rebased") and was COMMITTED. Only a syntax check catches it.
#   2. `changes_index.py write` was run MID-replay; the fragments were fine so
#      `changes_index.py check` printed `ok: N fragment(s)`, but the committed
#      CHANGES.md row order no longer matched a fresh render, and linux/unit
#      red-ed on test_the_real_index_renders_the_committed_changes_md.
#
# Usage:  post-rebase-verify.sh <base-sha>
# Exit 0 = safe to push. Any nonzero = DO NOT PUSH.

set -uo pipefail

BASE="${1:?usage: post-rebase-verify.sh <base-sha>}"

fail=0
say() { printf '  %-46s %s\n' "$1" "$2"; }
ok()  { say "$1" "OK"; }
bad() { say "$1" "FAIL"; fail=1; }

cd "$(git rev-parse --show-toplevel)" || exit 2
HEAD_SHA=$(git rev-parse --short HEAD)
# Resolve BASE to a short sha for display: a caller may pass a ref (refs/remotes/origin/main)
# or an abbreviate-able sha, and `${BASE:0:8}` on the former prints "refs/rem" — measured.
BASE_SHA=$(git rev-parse --short "$BASE" 2>/dev/null || printf '%s' "$BASE" | cut -c1-8)
echo "post-rebase-verify  head=$HEAD_SHA  base=$BASE_SHA"

# 1. Clean worktree: an uncommitted file means the push ships the pre-fix tree.
if [ -z "$(git status --porcelain)" ]; then ok "worktree clean"; else bad "worktree dirty (commit or amend first)"; fi

# 2. No conflict markers ANYWHERE in the committed tree.
n=$(git grep -lE '^(<<<<<<<|>>>>>>>)' -- . 2>/dev/null | wc -l | tr -d ' ')
if [ "$n" = "0" ]; then ok "no conflict markers committed"; else bad "$n file(s) carry markers"; fi

# 3. Every changed .py must parse — the check that catches a committed marker.
pyfail=0
while IFS= read -r f; do
  [ -f "$f" ] || continue
  python3 -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" "$f" 2>/dev/null || {
    echo "     py: $f does not parse"; pyfail=$((pyfail+1)); }
done < <(git diff --name-only "$BASE"...HEAD -- '*.py' 2>/dev/null)
if [ "$pyfail" = "0" ]; then ok "changed .py all parse"; else bad "$pyfail .py file(s) do not parse"; fi

# 4. Every changed .json must load.
jsfail=0
while IFS= read -r f; do
  [ -f "$f" ] || continue
  python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$f" 2>/dev/null || {
    echo "     json: $f is invalid"; jsfail=$((jsfail+1)); }
done < <(git diff --name-only "$BASE"...HEAD -- '*.json' 2>/dev/null)
if [ "$jsfail" = "0" ]; then ok "changed .json all valid"; else bad "$jsfail json file(s) invalid"; fi

# 5. CHANGES.md must equal a FRESH render (not just `changes_index.py check`).
if [ -f scripts/changes_index.py ]; then
  if python3 - "$PWD" <<'PY'
import importlib.util, pathlib, sys
root = pathlib.Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("ci", root / "scripts" / "changes_index.py")
ci = importlib.util.module_from_spec(spec); spec.loader.exec_module(ci)
sys.exit(0 if (root / ci.CHANGES).read_text() == ci.render(root) else 1)
PY
  then ok "CHANGES.md == fresh render"
  else bad "CHANGES.md != render — write AT THE END of the replay, then amend"
  fi
else
  say "CHANGES.md render check" "skipped (no changes_index.py)"
fi

# 6. Census gate, if present.
if [ -f scripts/check_architecture_census.py ]; then
  if python3 scripts/check_architecture_census.py check >/tmp/_census.$$ 2>&1; then
    ok "check-architecture-census"
  else
    bad "check-architecture-census"; tail -3 /tmp/_census.$$ | sed 's/^/     /'
  fi
  rm -f /tmp/_census.$$
fi

# 7. Linefeed / markdown lint, if present.
if [ -f scripts/lint_linefeeds.py ]; then
  if python3 scripts/lint_linefeeds.py >/tmp/_lint.$$ 2>&1; then ok "lint_linefeeds"
  else bad "lint_linefeeds"; grep -E 'LINT FAIL|  - ' /tmp/_lint.$$ | head -4 | sed 's/^/     /'; fi
  rm -f /tmp/_lint.$$
fi

# 8/9. Relationship to the base, judged by whether the base's change actually merges.
# A PR branch is almost never an ANCESTOR of the base: main moves on while the branch carries its
# own commits, so neither tip is an ancestor of the other in the normal state. Failing on that
# blocks the exact state #1015 blesses (behind-but-mergeable) and pushes a reader into a rebase the
# rule says not to do — measured on this very branch: `base 864fffaa is NOT an ancestor FAIL` while
# the PR was MERGEABLE with 0 conflicts.
# The question that matters is whether the base's work can still be joined to the branch:
#   base under HEAD            -> rebased onto it
#   merges cleanly, no conflict-> merely behind; leave it (#1015)
#   conflicts                  -> genuinely needs the rebase, or the rebase did not take
if ! git cat-file -e "$BASE^{commit}" 2>/dev/null; then
  bad "base $BASE_SHA does not exist"
  echo "     Fetch it before verifying: git fetch origin +refs/heads/main:refs/remotes/origin/main"
elif git merge-base --is-ancestor "$BASE" HEAD 2>/dev/null; then
  ok "base is an ancestor of HEAD"
  if git merge-tree --write-tree "$BASE" HEAD >/dev/null 2>&1; then
    ok "merge-tree clean vs base"
  else
    bad "merge-tree reports conflicts"
  fi
else
  if git merge-tree --write-tree "$BASE" HEAD >/dev/null 2>&1; then
    say "not rebased onto $BASE_SHA, merges cleanly" "NOTE"
    echo "     The base has commits you lack and you have commits it lacks — the ordinary state"
    echo "     while main moves. Nothing is owed (#1015) until a merge actually conflicts."
  else
    bad "conflicts with $BASE_SHA"
    echo "     The base's work does not join to HEAD. Either the rebase did not take, or the base"
    echo "     moved and this branch now genuinely needs one. merge-base: $(git merge-base "$BASE" HEAD 2>/dev/null | cut -c1-8)"
  fi
fi

# 10. Live-head guard: has the remote moved past us since we fetched?
br=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
if [ -n "$br" ] && [ "$br" != "HEAD" ]; then
  for rem in origin fork; do
    rem_ref="refs/remotes/$rem/$br"
    if git rev-parse --verify --quiet "$rem_ref" >/dev/null 2>&1; then
      live=$(git rev-parse "$rem_ref")
      if [ "$live" = "$(git rev-parse HEAD)" ]; then
        ok "local HEAD == fetched $rem/$br"
      else
        echo "     note: $rem/$br is ${live:0:8}; a force-with-lease will overwrite it."
        echo "           Confirm nobody pushed since you fetched, or stand down."
      fi
    fi
  done
fi

# 11. No SILENT REVERT of base content. `-X theirs`/`-X ours` resolve every conflicting hunk in
# the chosen direction, so a hunk that was never meant to differ can be reverted and nothing
# conflicts to flag it. Measured: a strategy-flag rebase reverted main's `ci_images.py latest`
# back to an older `ref` in a Makefile recipe; the only symptom was a unit test asserting a
# command string, after a ~35-minute matrix.
#
# The test: every line the base has in a tracked text file, and HEAD lacks, must correspond to a
# deletion the branch actually intends. We cannot read intent, so instead we surface the deletions
# of base lines in files the branch does NOT otherwise add to -- that is the reverting shape.
# Generated files are excluded: they are re-rendered, not merged, so their diffs are expected.
# The test must distinguish a REVERT from simply being BEHIND. A file the branch never touched
# appears to "lose" every line main added after the merge-base — that is staleness, not a revert.
# So this check runs ONLY when the base is genuinely an ancestor of HEAD (a real post-rebase
# state, the condition assertion 8 already tests). In that state there is no staleness to
# confuse, and any base line missing from HEAD was dropped by the resolution.
GEN_RE='^(CHANGES\.md|docs/ARCHITECTURE\.md|.*/\.openspec\.yaml)$'
rev_files=""
del_files=""
if git merge-base --is-ancestor "$BASE" HEAD 2>/dev/null; then
  # What is provable: a -X-strategy revert is a SUBSTITUTION -- base's line is gone and a different
  # line took its place (`ci_images.py latest agent` -> `ref agent`). Intent is NOT provable: after
  # a rebase the merge-base IS the base, so a replayed revert sits inside the branch's own commits
  # and any "did the branch mean this" test classifies it as intended. And a PURE deletion may be
  # entirely correct (a branch removing an obsolete line), so failing on it would reject correct
  # work -- the thing this lane's rules forbid a test from doing.
  #
  # So: substitution FAILS (the confirmed defect shape), pure deletion is REPORTED for a human
  # without failing the push.
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    case "$f" in
      *.png|*.jpg|*.jpeg|*.gif|*.ico|*.pdf|*.zip|*.gz|*.woff*|*.ttf|*.lock) continue ;;
    esac
    printf '%s\n' "$f" | grep -Eq "$GEN_RE" && continue
    gone=$(git diff --no-color "$BASE" HEAD -- "$f" 2>/dev/null | grep -c '^-[^-]')
    added=$(git diff --no-color "$BASE" HEAD -- "$f" 2>/dev/null | grep -c '^+[^+]')
    if [ "$gone" -gt 0 ] && [ "$added" -gt 0 ]; then
      rev_files="$rev_files $(printf '%s(%s-%s)' "$f" "$gone" "$added")"
    elif [ "$gone" -gt 0 ]; then
      del_files="$del_files $(printf '%s(%s)' "$f" "$gone")"
    fi
  done < <(git diff --name-only "$BASE" HEAD 2>/dev/null)
fi
if [ -n "$rev_files" ]; then
  bad "base lines replaced:$rev_files"
  echo "     These files lost base lines AND gained others — the shape a --strategy flag"
  echo "     (-X theirs / -X ours) leaves when it resolves a hunk that never should have differed:"
  echo "     measured, main's 'ci_images.py latest agent' became an older 'ref agent'. Diff each"
  echo "     file against $BASE_SHA by hand and restore the base's wording, keeping your additions."
elif [ -n "$del_files" ]; then
  say "base lines deleted (review):$del_files" "NOTE"
  echo "     No file above added anything while losing base lines, so this reads as a deliberate"
  echo "     removal rather than a revert — NOT a failure. Confirm each is intended."
else
  ok "no base lines lost"
fi

# 12. Commit authorship/trailers. `linux/guard` runs check_pr_authors and reds the whole matrix on a
# wrong author or a stray Co-authored-by trailer, and nothing else in this script would notice —
# measured: a rebase that dropped an architect trailer was only found after a full unit cycle.
# This is a pre-push assertion precisely because the failure is cheap to fix locally and expensive
# to discover in CI.
if [ -f scripts/check_pr_authors.py ]; then
  if python3 scripts/check_pr_authors.py check --base "$BASE" --head HEAD >/tmp/_auth.$$ 2>&1; then
    ok "check_pr_authors"
  else
    bad "check_pr_authors"; grep -vE '^\s*$' /tmp/_auth.$$ | head -4 | sed 's/^/     /'
  fi
  rm -f /tmp/_auth.$$
fi

echo
if [ "$fail" = "0" ]; then echo "SAFE TO PUSH"; exit 0; else echo "DO NOT PUSH — see FAIL lines above"; exit 1; fi
