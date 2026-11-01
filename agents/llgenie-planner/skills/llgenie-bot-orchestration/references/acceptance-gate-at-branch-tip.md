# Gating acceptance: the FULL no-args gate at the branch TIP

When a lane reports a fold/fix "final" and "0 rows", the acceptance gate has exactly one correct
form. Everything else produces a false green.

## The one correct invocation

```bash
# at a CLEAN checkout/archive of the pushed commit, NOT the primary clone (REPO_ROOT=parents[1]):
python3 scripts/check_agent_profiles.py check        # NO arguments, NO --only
```

- **No `--only` filter.** `--only live-longer,absent-from-tree` silently DROPS the
  `live-edited-not-tree` class. A file can be flagged by BOTH classes at once (live grown past the
  tree AND live edited after the tree commit), so a `--only` run reads 0 while the full run reads
  those same files as failing. Measured: a lane reported "0 rows via `--only live-longer,...`" while
  the full gate at the same head read 4 planner rows, two of them `live-edited-not-tree`.
- **At the branch TIP, not a quoted/older/side commit.** Force-push can move a branch BACKWARD or
  the lane can push a commit that is a SIBLING of the one it quotes. Verify the tip and the ancestry:

```bash
gh api repos/asimov-agent/llgenie/branches/<branch> --jq .commit.sha   # the real tip
gh pr view <n> --json headRefOid --jq .headRefOid                       # PR's head sha
git merge-base --is-ancestor <quoted> <tip>; echo $?                     # 1 = quoted is NOT an ancestor
git merge-base --is-ancestor <tip> <quoted>; echo $?                     # both 1 = they are SIBLINGS
```

Two exit-1s above means the quoted sha and the tip are siblings — the lane folded a head the branch
moved past. Gate the TIP.

## The closing condition (state it verbatim)

#N closes only when the **full no-args** gate reads **0 <lane> rows at the pushed branch TIP**. A
`--only` subset, a side commit, or "captured live as of my commit" do not satisfy it. When the
lane's own live refs are still being written (in-session lessons appended to gate-authoritative
references), no fold can hold — say "no re-cut until the live set freezes, then ONE fold at the
frozen state" rather than dispatching another cut that will be overtaken.

## Reporting discipline

Every refusal quotes: (1) the tip sha re-measured now, (2) the FULL no-args gate row count at that
sha, (3) the ancestry exit codes for any sha the lane quoted. Do not re-post the same refusal to the
board every stale re-delivery — one refusal comment stands; subsequent repeats get a DM only.
