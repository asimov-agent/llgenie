# Salvage audit: which local branches and worktrees hold work that exists nowhere else

A **read-only** report for the owner before any prune. You never delete, prune or remove; you
produce the sentence "safe in principle to delete: N; must be preserved: <list>" so the decision
is made on evidence instead of a list of names.

## The trap that makes a naive audit useless

**`git diff --shortstat main...<tip>` being non-empty does NOT mean the branch holds unique work.**
The three-dot diff measures against the *merge base*, so a branch whose content was squash-merged
or rebased onto main still shows its full diff while every byte of it is already upstream — and a
hardcoded "UNIQUE" bucket built on that number reports almost every scratch branch as work to
preserve, which is the same as reporting nothing.

Two further false positives, both measured:

- **A branch that is a local replay of an open PR** is unique by diff and by name, but deleting it
  loses nothing a reviewer cannot see. Match by branch name against `gh pr list --state open`, then
  by the branch's added paths existing in any open PR head.
- **A branch of an already-MERGED PR** (the usual `rb<PR>` scratch replay) is unique by diff and is
  not an ancestor of main after a squash. Match its name against `gh pr list --state merged`.

So the decision is never one diff. It is: is the tip an ancestor of main (LANDED); is it an open
PR's head or that PR's branch (ON-A-PR); is it a merged PR's branch (MERGED-REPLAY); does main
already cover every path it touches (NO-DIFF); **otherwise** does it add a path main has never had
(UNIQUE). Only the last bucket is at risk.

## Procedure

```bash
# 1. fresh base, and settle the shadow question every time
git fetch origin +refs/heads/main:refs/remotes/origin/main
git rev-parse refs/remotes/origin/main            # the real base
git rev-parse refs/heads/origin/main             # rc=128 = no shadow; a sha here is the hazard
git branch --format='%(refname:short)' | wc -l
git worktree list --porcelain | grep -c '^worktree '
```

```bash
# 2. per branch, in this order (stop at the first bucket that matches)
git merge-base --is-ancestor <tip> refs/remotes/origin/main     # → LANDED
# name against open PRs, then tip against open PR heads          # → ON-A-PR
# name against merged PRs                                       # → MERGED-REPLAY
python3 - <<'PY'                                                 # → UNIQUE vs NO-DIFF
# for each path in `git diff --name-status main...<tip>` whose status is A,
# ask `git cat-file -e main:<path>`: rc!=0 means main has NEVER had that path
PY
```

```bash
# 3. per worktree: dirty is invisible to every ancestry test
for p in $(git worktree list --porcelain | grep '^worktree ' | sed 's/^worktree //'); do
  d=$(git -C "$p" status --porcelain 2>/dev/null | wc -l)
  echo "$d  $p  $(git -C "$p" rev-parse --abbrev-ref HEAD 2>/dev/null)"
done
```

## What each bucket means for the owner

| bucket | delete loses | how to say it |
|---|---|---|
| LANDED | nothing — work is upstream | safe |
| ON-A-PR | nothing — a reviewer can see it | safe |
| MERGED-PR-REPLAY | nothing — merged, local replay | safe |
| NO-DIFF | nothing — main covers every path it touches | safe |
| **UNIQUE** | **the only copy** | **preserve, list the added paths** |
| **dirty worktree** | **uncommitted work, invisible to ancestry** | **preserve, list the file count** |

`refs/pull/<n>/head` and a surviving branch ref resolve long after a PR closes, so a resolving ref
is never evidence of liveness — only `.state` is. And an unreadable tip (deleted upstream, missing
object) is its own bucket; say so instead of guessing.

## Declare your own leftovers, and clean them yourself

A lane's own scratch trees are usually the biggest dirty entries and they hide the real ones. A
staged `git merge --no-commit` tree is `M ` index dirt with **no unique commits** — say it is yours,
and clear it (`git merge --abort`, else `git reset --hard HEAD`) rather than padding the owner's
preserve list. Prove no loss by **blob identity**, never ancestry (a squash merge leaves your tip a
non-ancestor): `git rev-parse <mergeCommit>:<path>` must equal `git rev-parse <main>:<path>`.

## Two audits of one question must agree — run both, it is the cheapest test there is

When a repository has two independent implementations of the same census (a shell script and a
python one, a fast path and a careful one), **run both back to back and compare their two
conclusion lines**. Same repo, same instant, two different answers means one of them is lying to
the owner about what is safe to delete — and a single audit has no way to be wrong out loud.

Measured divergence that motivated this rule:

```
shell   SAFE 162 branches / 125 worktrees   PRESERVE 7 + 18
python  SAFE  45 branches / 132 worktrees   PRESERVE 7 + 11
```

Two independent arithmetic defects in the second tool:

1. **Worktrees: `total - dirty` marks CLEAN work on a unique branch as deletable.** A worktree is
   safe only when it is clean **and** its HEAD carries nothing unique. Subtracting only the dirty
   set called six clean-but-unique worktrees safe — the optimistic answer, instructing the owner to
   delete work that exists nowhere else. Preserve set = **union** of dirty and on-a-unique-branch,
   never `total - dirty`.
2. **Branches: enumerating buckets silently drops the lossless orphans.** Summing
   `landed + on-a-PR + merged-replay` reported 45 where the truth was 162, because every orphan
   that adds nothing main lacks is also deletable. Deletable = **`total - unique`**, never a bucket
   sum.

## Assert the RULES, not the numbers, and never the source text

An exact-count assertion reds on every unrelated push (the repo moves minute to minute). A
grep-the-source-text assertion is worse: it passes while the arithmetic bug is live and fails on a
harmless whitespace change — exactly inverted. Measured: a test grepping for the subtraction
expression failed after the fix merely reformatted it, while the real divergence was invisible to it.

Extract the verdict into a **pure function** (`summarise(rows, wts)` returning `keep`,
`safe_branches`, `safe_worktrees`) and unit-test that against synthetic rows and worktrees. It needs
no `gh`, no network and no repository, so it runs anywhere and needs no skip. Then prove each rule
bites with a negative control — reintroduce the defect and require the test to FAIL:

```
union loop removed          -> "a clean worktree on a unique branch was called safe"
bucket-enum deletable back  -> "lossless/held-by-PR orphans must count as deletable"
restored                    -> all pass
```

AGENTS.md forbids skipped tests outright, so a test that needs `gh` must be rewritten to test the
pure part rather than guarded with `pytest.skip`.

## Report shape

One table, then the numbers, then the sentence the owner actually needs — with the measurement
time stamped, because work materialises during a multi-minute audit and a dirty worktree can appear
that belongs to another lane's live PR preparation. Re-measure the dirty set immediately before
the owner acts:

```
conclusion: N landed · N on-a-PR · N merged-replay · N no-diff · N UNIQUE (list the subtree)
worktrees: N total · N dirty (list) · N with a UNIQUE head (list) · 0 removed
safe in principle to delete: N branches, N worktrees
must be preserved: <UNIQUE branches> + <dirty worktrees>
```

## Two tools, one UNIQUE label — verify the SETS agree, not just the counts

The lane ships BOTH `salvage-audit.sh` (shell) and `salvage-four-bucket.py` (python) for the same
audit. They reconciled at UNIQUE=7 on main 7640feae, but a count match does not prove agreement:
two implementations can both count N while naming DIFFERENT branches, and then "they agree" is a
lie. The load-bearing check is the set comparison:

    # python output → branch names of the "orphan — UNIQUE" block
    # shell output  → names under "=== UNIQUE — content that exists only on these branches ==="
    comm -23 <(sort pu.txt) <(sort su.txt)   # only-in-python: must be EMPTY
    comm -13 <(sort pu.txt) <(sort su.txt)   # only-in-shell:  must be EMPTY

Verified at 7640feae: both name the SAME 7 branches as UNIQUE (empty in both directions), and the
python reconciliation line prints `its UNIQUE == this UNIQUE == {len(uniq)}` from a live length,
not a hardcoded count. Run this every time the salvage logic changes; a count-only "they agree"
does not exercise the predicate that matters.
