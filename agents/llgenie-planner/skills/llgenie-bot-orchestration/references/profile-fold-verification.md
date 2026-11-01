# Verifying and pre-checking a live→tree profile-skill fold

A "fold" commits a live-profile skill (`~/.hermes/profiles/<p>/skills/<bundle>/`) into the repo tree
(`agents/<p>/skills/<bundle>/`) so the rulebook is reviewable in a diff. Two things bite every fold: the
SCOPE of the copy, and which `check_agent_profiles.py` finding you are actually fixing.

## Scope is BUNDLE-wide, byte-identical

A skill bundle is `SKILL.md` **plus** its `references/` (and `templates/`, `scripts/`) subtree. Folding only
`SKILL.md` leaves the SKILL pointing at `references/*.md` files absent from the tree — the exact
`skill-reference-missing` failure. Copy the whole bundle, then prove byte-identity per file (size says nothing):

```bash
cmp -s "$LIVE/$f" "$TREE/$f" && echo OK:$f
```

## `check_agent_profiles.py check` reports TWO classes — do not conflate them

- **Tree-only class** — `skill-reference-missing` (a `SKILL.md` names a `references/x.md` not in the tree).
  This is what CI's `test_agent_profiles.py` / `make check-agent-profiles` asserts; a fold must drive it to **0**.
- **Live-comparison drift** — `live-longer` / `live-lines-missing` (committed tree vs the machine's live
  profile). A SEPARATE backlog tracked per-lane; it makes `check` exit rc=1 on a plain tree too and is NOT
  part of a single fold issue. A fold PR that also "fixes" these is out of scope and unreviewable.
- **Advisory `note` (not a failure)** — e.g. "states X more than once (duplicate canonical rule — one bullet,
  one place, #972)" when a SOUL/SKILL carries a canonical rule twice. It leaves `check` rc=0 and is printed to
  stderr, so the rc alone hides it — grep the output for `note:`. It is still worth filing (see below): it is a
  standing re-measure on every run and its fix is a tiny, versioned, low-risk PR, but it does NOT block a fold
  or flag a live/tree mismatch.

So **rc=1 on the fold worktree is not proof the fold is incomplete.** Isolate the class you own:

```bash
python3 scripts/check_agent_profiles.py check 2>&1 | grep -cE 'skill-reference-missing.*<bundle>'   # BEFORE -> AFTER=0
```

## Attribute the red before you refuse: same gate at `origin/main` AND at the PR head, per file

A fold PR whose gate reds has NOT necessarily introduced the red. Run the identical no-args gate in two clean
detached worktrees — one at the PR head, one at the just-fetched `origin/main` — and classify each failing file at
both:

```bash
for f in <failing-file-stems>; do
  # at MAIN worktree
  python3 scripts/check_agent_profiles.py check 2>&1 | grep "references/$f.md" | grep -oE 'FAIL (live-longer|absent-from-tree|live-edited-not-tree)'
  # then the same in the HEAD worktree
 done
```

Three outcomes, three different rulings — do not collapse them into "the fold failed":

- **red at head, clean at main** → introduced by this PR → refuse, lane re-cuts.
- **red at both** → ambient drift that predates the branch; the PR did not introduce it. Refusing the lane for it
  is a false accusation. Honest ruling: "your DECLARED folds are clean; the gate still lists N ambient rows that
  are out of your declared scope — extend the fold to cover them (if they are the same drift class) or file an
  explicit owner scope question."
- **clean at head, red at main** → the fold fixed it.

Why: a drift gate reds on a *set*. A lane folds its declared subset, and the gate still enumerates ambient rows it
never touched; blaming the lane teaches the wrong rule and sends it to re-verify a clean fold. In the refusal,
name each file's class **per head**. One more tell: a file that reads `absent-from-tree` at main but `live-longer`
at the head proves the branch's tree *does* contain it (folded) and the live copy grew past it since — the fold's
actual content exceeded its reported scope, and the live set is moving (see the moving-target section).

## When your own refusal over-stated the defect, supersede it — on both boards

If the harder measurement shows the lane was partly right (declared folds clean), post a REFINED verdict that names
the earlier comment id it supersedes and states the corrected per-file picture. Then split the board state:
**vehicle verdict on the PR** (per-file, scope-revised re-cut directive) and **tracker status on the tracker
issue** ("acceptance NOT MET at head `<sha>`, because …"). A tracker left inert while its vehicle is red reads as
"in progress" to the next reader. One vehicle, one trail: extend the existing branch, never a new PR.

## Where you run the gate decides what tree it measures

`check_agent_profiles.py` sets `REPO_ROOT = Path(__file__).resolve().parents[1]` — it reads **the checkout the
script lives in**, plus the machine's live profile. Run it from the long-lived primary clone and you measure that
clone's stale working tree, not upstream: every commit landed since its last pull shows up as `live-longer` /
`absent-from-tree` drift for files that are already correct on `origin/main`. Discard any drift conclusion whose
measurement came from the primary clone; re-measure from a **clean worktree at `origin/main`** (the recipe below
already does this — do not shortcut it by cd-ing into the primary clone). Quote the sha the worktree is at
alongside the finding, and hand the lane that same caveat so it never runs the gate in the stale clone and
"fixes" drift that does not exist.

## Pre-verification recipe (prove the fix before any branch is cut)

Disposable detached worktree off the merge base — de-risks the implementer's run and hands the lane sealed
evidence without the planner implementing:

```bash
WT=$(mktemp -d "$SCRATCH/wt-fold.XXXXXX")
git -C <repo> worktree add -f --detach "$WT" origin/main
# copy the live bundle files in, cmp each, then:
( cd "$WT" && python3 scripts/check_agent_profiles.py check 2>&1 | grep -cE 'skill-reference-missing.*<bundle>' )
```

Leave the worktree in place for the lane to inspect. Post the BEFORE→AFTER table on the issue so the lane
knows the target is 0 and that the residual rc=1 is the OTHER class.

**Removing your OWN just-created verification worktree is NOT the forbidden prune.** The fleet rule forbids
touching a *lane's* worktree (it may hold uncommitted mid-flight work; the "already merged" test reads the
branch ref only and cannot see that). But a detached worktree you created *this pass*, holding no lane work and
no uncommitted change, is yours to clean up — leaving it is debt. The distinction is authorship: your own
scratch worktree → `git worktree remove --force` (or wipe + `rm -rf` + `git worktree prune`); any worktree you
did not create → measure and report only, deletion is the owner's call.

**Running the gate in a `-u root` container leaves root-owned files that block cleanup.** If you ran
`check_agent_profiles.py` / pytest inside `llgenie/test:latest` with `-u root` against a bind-mounted rw
worktree, the container writes root-owned `__pycache__/` and `.pytest_cache/` that `rm -rf` as your user cannot
remove (`Permission denied`, and passwordless sudo may be absent). Wipe them from a root container instead of
fighting the host:

```bash
docker run --rm -u root -v "$WT":/wipe:rw -w /wipe alpine \
  sh -c 'rm -rf /wipe/.git /wipe/__pycache__ /wipe/scripts/__pycache__ /wipe/tests/__pycache__ /wipe/.pytest_cache'
rm -rf "$WT" && git -C <repo> worktree prune
```

Then confirm `ls -d "$WT"` returns *No such file* and `git worktree list --porcelain` no longer names it — a
disk-state cleanup claim needs both readbacks, not just the `rm`'s exit 0.

## One vehicle, and the fold owner

Profile folds route through a lane, never the planner's own seat. Default owner is the documentation lane; when
that lane's queue is already carrying live work, route to the implementer lane — either way ONE issue, `bot-claim:`ed
with the done-condition (`cmp` byte-identical at the merged head + the class you own driven to 0). One issue per
file set; never a second issue for the same files, and never a fold PR from the planner's own seat.

Residual live-comparison drift (the `live-longer` / `absent-from-tree` class, when it is the whole finding and no
`skill-reference-missing` is involved) gets its OWN issue for that profile's bundle, routed the same way — that is
not "a fold PR that also fixes drift", it is the drift-tail fold. Say so explicitly in the issue so the lane does
not think it is duplicating an earlier bundle fold.

## The live profile is a MOVING TARGET — a fold PR is a snapshot that goes stale in minutes

A busy lane's live profile is edited by that lane *while* you fold it. Measured repeatedly: a fold merged at
16:18 carried sizes that had already grown by 16:23–16:31, and a *second* drift-tail fold issue was needed for
the same bundle before the first PR was an hour old. Expect N tail folds, not one, for a lane that is actively
working; this is normal, not a defect in the lane or in you.

Consequences for dispatch:

- **Re-measure the residual rows at the CURRENT head at the moment you dispatch**, and paste the live/tree sizes
  and mtimes into the dispatch. A dispatch that quotes sizes measured an hour ago sends the lane at a stale blob.
- **Acceptance is "0 rows at the PR's OWN head", never "0 rows at the head I measured".** The gate is re-run in a
  clean worktree at the PR head; a size that has to match a number in the issue body is unwinnable.
- **Do not accumulate vehicles.** One open fold issue per profile bundle; a later snapshot is a comment with fresh
  numbers on the same issue, and a later PR needs the previous one merged/closed first.

## The gate auto-resolves the live root — do not hand it `--agents-dir`

From a clean detached worktree the script derives `live_root` from the host layout itself
(`~/.hermes/profiles/<p>/skills/...`) and compares committed tree vs the real live profile. Passing an explicit
`--agents-dir` / `--profile-dir` overrides that and fails (rc=2, usage error) — the failure looks like a repo
problem but is a bad invocation. Plain `check` from the worktree is correct; quote its rc and findings.

Scope the class you own with the flag rather than grepping the whole report:

```bash
python3 scripts/check_agent_profiles.py check --only live-longer,absent-from-tree 2>&1 | grep -E 'llgenie-<lane>/'
```

Count every class (live-longer, live-lines-missing, absent-from-tree, live-edited-not-tree) before you claim
anything about drift: a "ZERO findings" claim from one scoped run is a claim about one class, and quoting it as
"the gate is clean" is how a planner contradicts a lane that measured all four.

## A stale-arrival report about an already-merged PR

Lanes report "PR #N ready for review" long after the owner merged it. Verify before acting:

```bash
gh pr view <n> --json state,mergedAt,mergeCommit,headRefOid   # state MERGED?
git merge-base --is-ancestor <prHead> origin/main             # usually FALSE after a squash
```

A **squash merge makes the PR head NOT an ancestor of main** while the merge commit is — so "head not in history"
is not evidence of an unmerged PR, and the report is not evidence of an unmerged one either. Read `mergeCommit`.
When it is merged: no new vehicle, no re-open of the closed issue, no duplicate fold for the files it already
carried — re-point the lane at the *current* tracker with the current residual rows.

## An advisory `note` is still a file-and-route, never a silent edit

A #972 duplicate-canonical-rule note on a LANE's own SOUL is that lane's versioned behaviour text — fix it through
the normal implementer queue (one issue, one PR folding the two occurrences into one without information loss,
closing the issue, never merge/arm), never by silently editing SOUL.md from the planner seat. `check` rc=0 means
"not blocking", not "leave it": the note re-asserts every run, so it accumulates as standing re-measure noise and
a reviewer reading the gate output sees it as a defect signal. File it with the two measured line numbers, the
exact wording of the note, and the gate invocation that produced it.
