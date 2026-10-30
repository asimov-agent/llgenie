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

# 8. The branch must actually be on top of the base we claim.
if git merge-base --is-ancestor "$BASE" HEAD 2>/dev/null; then ok "base is an ancestor of HEAD"; else bad "base $BASE_SHA is NOT an ancestor"; fi

# 9. Merge-tree must be clean against that base (exit code, not a path grep).
if git merge-tree --write-tree "$BASE" HEAD >/dev/null 2>&1; then ok "merge-tree clean vs base"; else bad "merge-tree reports conflicts"; fi

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

echo
if [ "$fail" = "0" ]; then echo "SAFE TO PUSH"; exit 0; else echo "DO NOT PUSH — see FAIL lines above"; exit 1; fi
