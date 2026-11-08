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
# deletion the branch actually intends. We cannot read intent directly, so we compare the base
# lines HEAD lost AGAINST the branch's OWN diff -- the lines the branch deleted from the fork
# point it diverged from the base. The branch's own diff is the pre-rebase tip (`git rebase`
# records it in ORIG_HEAD) diffed back to `merge-base(base, ORIG_HEAD)`:
#
#   - A CORRECT edit deleted those lines itself: the line is a `-` in the branch's own diff,
#     so the base-line loss is accounted for -- intended, reported as a NOTE, never FAIL.
#   - A replayed REVERT (`-X theirs` resolves the hunk to the branch's older side) dropped a
#     base line the branch NEVER touched: the line is absent from the branch's own `-` set,
#     so the loss is unexplained -- the provable revert shape, and it FAILs.
#
# This replaces the old `gone>0 && added>0` predicate, which treated every substitution as a
# revert and fired FAIL on every ordinary code edit (#2069 `engine_build_trigger.py(5-51)`,
# #2085 `engine_image.py(5-49)` were both clean rebases whose only conflict was CHANGES.md).
# Generated files are excluded: they are re-rendered, not merged, so their diffs are expected.
# The test must distinguish a REVERT from simply being BEHIND. A file the branch never touched
# appears to "lose" every line main added after the merge-base -- that is staleness, not a revert.
# So this check runs ONLY when the base is genuinely an ancestor of HEAD (a real post-rebase
# state, the condition assertion 8 already tests). In that state there is no staleness to
# confuse, and any base line missing from HEAD was dropped by the resolution.
GEN_RE='^(CHANGES\.md|docs/ARCHITECTURE\.md|.*/\.openspec\.yaml)$'
rev_files=""
del_files=""
if git merge-base --is-ancestor "$BASE" HEAD 2>/dev/null; then
  # Branch's own diff = pre-rebase tip (ORIG_HEAD) vs the fork point where it left the base.
  # ORIG_HEAD is only meaningful for a real rebase; without it, intent is unprovable, so we fall
  # back to a NOTE rather than FAIL -- over-firing is the exact defect this rewrite removes.
  OWN_TIP=""
  if git rev-parse --verify --quiet ORIG_HEAD >/dev/null 2>&1; then
    OWN_TIP=$(git rev-parse ORIG_HEAD)
    if [ "$OWN_TIP" = "$(git rev-parse HEAD)" ]; then OWN_TIP=""; fi
  fi
  if [ -n "$OWN_TIP" ]; then
    FORK=$(git merge-base "$BASE" "$OWN_TIP" 2>/dev/null || true)
  else
    FORK=""
  fi
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    case "$f" in
      *.png|*.jpg|*.jpeg|*.gif|*.ico|*.pdf|*.zip|*.gz|*.woff*|*.ttf|*.lock) continue ;;
    esac
    printf '%s\n' "$f" | grep -Eq "$GEN_RE" && continue
    gone=$(git diff --no-color "$BASE" HEAD -- "$f" 2>/dev/null | grep '^-[^-]' | cut -c2-)
    added=$(git diff --no-color "$BASE" HEAD -- "$f" 2>/dev/null | grep '^+[^+]' | cut -c2-)
    [ -n "$gone" ] || continue
    gone_n=$(printf '%s\n' "$gone" | grep -c . )
    # Which gone base lines did the BRANCH itself delete? (its own diff fork..own-tip, `-` set)
    if [ -n "$FORK" ]; then
      own_del=$(git diff --no-color "$FORK" "$OWN_TIP" -- "$f" 2>/dev/null | grep '^-[^-]' | cut -c2-)
      unexplained=$(comm -23 <(printf '%s\n' "$gone" | sort -u) <(printf '%s\n' "$own_del" | sort -u))
    else
      # No ORIG_HEAD means no provable intent either way. A `-X theirs` revert and a deliberate
      # edit look identical without the pre-rebase tip, so reserving FAIL for the provable shape
      # (the issue's rule) means: with no ORIG_HEAD, report as NOTE, never FAIL -- over-firing is
      # the exact defect this rewrite removes.
      unexplained=""
    fi
    if [ -n "$unexplained" ]; then
      un_n=$(printf '%s\n' "$unexplained" | grep -c .)
      add_n=$(printf '%s\n' "$added" | grep -c . || true)
      rev_files="$rev_files $(printf '%s(%s-%s)' "$f" "$un_n" "$add_n")"
    else
      del_files="$del_files $(printf '%s(%s)' "$f" "$gone_n")"
    fi
  done < <(git diff --name-only "$BASE" HEAD 2>/dev/null)
fi
if [ -n "$rev_files" ]; then
  bad "base lines reverted:$rev_files"
  echo "     These files LOST base lines the branch's own diff never deleted — the shape a"
  echo "     strategy flag (-X theirs / -X ours) leaves when it resolves a hunk that never"
  echo "     should have differed: measured, main's 'ci_images.py latest agent' became an"
  echo "     older 'ref agent'. Diff each file against $BASE_SHA by hand and restore the base's"
  echo "     wording, keeping your additions."
elif [ -n "$del_files" ]; then
  say "base lines replaced by branch's own diff (review):$del_files" "NOTE"
  echo "     Every lost base line IS a deletion in the branch's own diff, so these are the"
  echo "     branch's intended substitutions — NOT a revert. Confirm each is what was meant."
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

# 13. Import-roots ratchet. CI runs `check import-roots` and reds when a NEW file carries its own
# sys.path entry or imports a scripts module bare -- the exact regression measured on #919, where a
# rebase brought in a branch file written before the gate landed. Nothing else here would notice.
# Two subcommands exist and the naming trap is real: `check` is a raw SHAPE scan that returns 1 on
# ANY vestige (main still has ~104 grandfathered roots, so `check` reds a clean tree by design);
# `ratchet` compares the COUNT to the baseline and fails only when it ROSE -- that is what CI runs
# and what this assertion must use. Sat on the conftest seam (no per-file roots) whenever the
# baseline fixture exists.
if [ -f scripts/check_import_roots.py ] && [ -f tests/fixtures/import-roots-baseline.json ]; then
  if python3 scripts/check_import_roots.py ratchet >/tmp/_ir.$$ 2>&1; then
    ok "import-roots ratchet"
  else
    bad "import-roots ratchet"; tail -4 /tmp/_ir.$$ | sed 's/^/     /'
  fi
  rm -f /tmp/_ir.$$
fi

echo
if [ "$fail" = "0" ]; then echo "SAFE TO PUSH"; exit 0; else echo "DO NOT PUSH — see FAIL lines above"; exit 1; fi
