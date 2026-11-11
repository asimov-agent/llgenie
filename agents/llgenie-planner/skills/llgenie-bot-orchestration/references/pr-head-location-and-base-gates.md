# Where a PR head really lives, and the base/merge-base gate classes

Two verification traps that read as "the lane is wrong" when the lane is fine (or the reverse).
Both are about measuring the HEAD and the BASE correctly before crediting or rejecting a vehicle.

## 1. A PR's branch can live on a FORK — canonical `ls-remote refs/heads/` empty is expected

`git ls-remote origin refs/heads/<b>` returning empty does **not** prove the branch is unpushed
when the PR's head repo is a fork. Lane PRs commonly live on a personal fork
(`andyholst/llgenie`) with only `refs/pull/<n>/head` published on the canonical repo, so the
canonical `refs/heads/` is legitimately empty while the branch is fully live and CI-gated.

Read where the head actually is **first**, then measure the tip on the repo it names:

```bash
gh api repos/<o>/<r>/pulls/<n> --jq .head.repo.full_name     # 'andyholst/llgenie' = fork
gh api repos/<fork>/commits/<sha> --jq '{sha:.sha[0:8],m:(.commit.message|split("\n")[0])}'

# base relationship against the CANONICAL main, cross-repo:
gh api repos/<o>/<r>/compare/<main-sha>...<head-sha> --jq '{status,ahead_by,behind_by}'
```

The tell that bit a pass: `ls-remote origin refs/heads/fix/<x>` came back empty and the branch was
briefly read as a phantom; `.head.repo` said `andyholst/llgenie`, and the tip was live there the
whole time. Do not conclude "awaiting branch / nothing pushed" from the canonical empty — check
`.head.repo.full_name` first. (Same object from the pull-ref side: `refs/pull/<n>/head` resolves
though `refs/heads/` is empty on canonical; verify-lane-claims §6g-bis.)

## 2. A commit's parent must be the LIVE tip, not the lane's stated base

A lane reporting "rebased onto current main `<sha>`" is asserting where it *thinks* it sits. Prove
it on the objects — the head's real branch point is `git merge-base origin/main <head>` (or, for a
fork head, `gh api .../compare/<fresh-main>...<head>` → `behind_by`0 / `ahead_by`1). A head that
still reports `behind_by N`/`diverged` is NOT based on the cited main no matter what the report says,
and any CI verdict already run at that head measured a tree the branch has since replaced.

## 2b. A lane's named "canonical / stack / union head" is a CLAIM — the PR's own head is authoritative

On a stacked or umbrella PR, a lane will tell you which sha is "the canonical head to fold onto" and
report that it already rebased onto it. Neither is evidence. Lanes routinely name an **abandoned
off-live sibling** (a commit that shares a parent with the real base but is not on the PR's own
ancestry) as "canonical", and report a push that never landed. Measure both before you route a fold:

```bash

# the ACTUAL head the PR carries — never a sha quoted in prose
gh pr view <n> -R <o>/<r> --json headRefOid,headRefName --jq '{h:.headRefOid,b:.headRefName}'
git ls-remote origin refs/pull/<n>/head          # same object from the pull-ref side

# is the lane's claimed "canonical" actually on the PR's ancestry? (abbrev shas; on the live tip?)
git merge-base --is-ancestor <claimed-canonical> <actual-head> && echo ON-HEAD || echo OFF-HEAD
git rev-list --count <claimed-canonical>..origin/main   # >0 = the sha is behind live, an abandoned ref
```

A claimed canonical that reports `OFF-HEAD` and `behind live >0` is an off-live ref nobody's PR carries;
the correct fold target is the PR's real `headRefOid`, anywhere it names a live-based head. Correct the
lane on-issue at the measured head, not its stated one.

**"Pushed and verified via ls-remote →`<sha>`" is falsified by two reads, not accepted.** Confirm the
branch ref actually moved and the claimed sha has a remote ref — a lane that rebased locally then failed
the push leaves the remote tip on the OLD sha while its message says the new one is live:

```bash
git ls-remote origin refs/heads/<branch>            # tip must equal the claimed sha
 git ls-remote origin 2>/dev/null | grep -c <claimed-sha>   # 0 = the sha is nowhere on the remote
```

**A claimed on-issue "record" comment id must resolve.** Lanes cite a comment id (`On-issue record:
#<i> comment <id>`) as proof they posted; if `gh api repos/<o>/<r>/issues/<i>/comments` does not list that
id among the newest, the post never happened and no board fact exists. Verify the id, and the newest
comment's real id/timestamp, before crediting an "updated claim".

## 3. `check-pr-base` is its own gate class — clearing gate A does not clear it

`make check-pr-base` (a `guard`-job step) requires the PR's merge-base to equal its base (`main`)
**itself**. A branch cut from an OLD base reports `behind_by N`/`diverged` against the freshly
fetched tip and reds regardless of any OTHER fix the lane made at the same head (a proc-gate or
roster fix does not touch it). So a lane that fixes gate A and re-pushes can still be red on gate B
at the new head.

Before believing a re-push is green, enumerate the failing `guard` job's STEP:

```bash
gh api repos/<o>/<r>/actions/runs/<run-id>/jobs \
  --jq '.jobs[]|select(.conclusion=="failure")|.name+" :: "+([.steps[]|select(.conclusion=="failure")|.name]|join(","))'
```

Remedy: rebase/re-cut onto the current live `main` so `git merge-base origin/main <head>` ==
`origin/main`. A `mergeable=false ms=dirty` head is rebasable — the no-rebase rule protects only a
clean/approved head, not a dirty one. Then require a fresh COMPLETED run at the rebased head and
quote its job id; a run at the superseded head is void.

**The rebase target is the CANONICAL upstream `main`, not the fork's own `main` branch.** A lane
working in a fork clone whose `origin` is the fork will, on a plain `git rebase origin/main`, rebase
onto the fork's stale `main` — which predates recent merges and can be dozens of commits behind
the canonical tip. The result is still `behind_by N` (so `check-pr-base` reds) AND it silently drops
files that landed after the fork's main was last synced (a guard file, a may-arm script), so the
rebased tree is not a superset of main. Always `git fetch <canonical> main` and rebase onto
`<canonical-main-sha>`, then prove `compare/<canonical-main>...<head>` reports `ahead_by 1 /
behind_by 0` (parent == canonical main) before believing the rebase is correct. A lane reporting the
wrong-target rebase as done is an honest own-correction to accept, not a failure — verify parentage
rather than the reported sha.

## 3b. Diagnose WHAT the rebase must do before dispatching "just rebase"

When a PR is `mergeable=false`/`ms=dirty` and the head's merge-base is behind main, a bare "rebase
onto origin/main" wastes a run if the conflict is **semantic** (both sides rewrote the same files for
different reasons) rather than mechanical. Surface the exact conflict set with a dry-run merge and
compare it against what main changed:

```bash
git -C <repo> fetch origin main
git -C <repo> merge-base <head> origin/main            # the real branch point

# dry-run merge — prints the merged tree + every CONFLICT: line, changes nothing
git -C <repo> merge-tree --write-tree <head> origin/main | grep -E 'CONFLICT|^\{' 
git -C <repo> show --name-only origin/main --format= | sort -u   # files main's tip touched
git -C <repo> show --name-only <head> --format= | sort -u       # files the branch touched
```

If the conflicting files are exactly the files a **recently merged PR** rewrote, it is a semantic
collision: the lane must interleave both behaviours (keep main's new logic AND the branch's change),
not replay-on-top. Say that in the dispatch — name the two behaviours that must both survive and the
change-note rows that must both be kept — or the lane resolves the conflict by silently dropping one
side and re-reds. A plain rebase instruction is only enough when the conflicting set is disjoint from
what main recently added.

### The exception: a RENDERED-INDEX collision is mechanical, not semantic

`CHANGES.md` is generated from `docs/changes.d/<stem>.md` fragments — it is a rendered
index, not hand-authored prose. So a `dirty` whose only conflict is `CHANGES.md` where
both sides inserted a *new* row at the same newest-first slot (both dated the same day,
sitting on the same line number) is a **rendered collision, not a semantic one**: the two
rows live in *separate* fragments, so nothing has to be interleaved by hand. Prove it and
name the deterministic fix:

```bash
git -C <repo> fetch origin main
git -C <repo> fetch origin pull/<n>/head:pr-verify
git -C <repo> merge-tree <base> pr-verify | grep -E 'CONFLICT|^[0-9]{6} .*CHANGES\.md'   # real conflict + blob variants
git -C <repo> show <base>:CHANGES.md | grep -n '<branch-topic>'        # branch's new row line
git -C <repo> show pr-verify:CHANGES.md | grep -n '<branch-topic>'      # same line = rendered slot collision
git -C <repo> ls-tree pr-verify docs/changes.d/ | grep -E '<branch-stem>|<other-stem>'  # separate fragments
```

Both rows on the same line + both stems present as distinct fragments ⇒ the fix is
`make changes-resolve BASE=origin/main` (issue #1103): it takes BASE's CHANGES.md,
re-renders from the *merged* fragment set (both rows appear, ordered), and stages it. Tell
the lane explicitly **do not hand-edit `CHANGES.md`** (`make changes-index` / #934 says a
hand edit is always wrong — a hand-merge silently drops one row). This is the one case
where §3b's "semantic ⇒ interleave" does NOT apply even though the same files collide.

### Two OPEN PRs that both re-render the same index — a merge-ORDER, not a defect on either

When two sibling PRs (neither merged) each re-render `CHANGES.md` from their own fragment set,
neither render can see the other's *un-merged* row, so each collides with `main` and the two read
`mergeable=CONFLICTING`/`ms=DIRTY` **while both diffs are correct**. Cutting both from a base that
still carries an unhealed marker block (or any shared single-row index) guarantees this: the PR that
*heals* the content also earns the conflict, and the second cannot rebase past it because the heal
is not on `main` yet. Diagnose it as ordering, not a code defect:

- `mergeable=CONFLICTING` ⇒ the `ci-verdict` check reds with **NO annotation** (it is the
  conflicting-state verdict — the squash-merge ref does not exist — not a gate finding). A
  ci-verdict `failure` whose check-run carries zero annotations on a `CONFLICTING` PR is NOT a
  defect to route back to the lane; quote `annotations: []` as the proof and say so on the PR.
- Deterministic unblock is a **land order**: merge the content-healer PR FIRST (it removes the marker
  block and lands its row, all-green), THEN rebase the second onto the fresh `main` and re-render
  (`make changes-index write`). Rebasing the second onto the *pre-heal* base keeps the identical
  conflict — do not dispatch that rebase, it spends a run and re-reds. Tell the second lane to
  **hold the branch, create no second vehicle, and wait** until the healer merges.
- Confirm the heal lands: healer's `CHANGES.md` blob is marker-free (`grep -c '^<<<<<<<'` = 0) while
  the pre-heal `main` blob still carries one — that difference is the proof the merge order resolves it.

**A rendered-index rebase is not terminal while main keeps advancing.** Every new merge to
`main` that also appends a `CHANGES.md` row re-reds an already-rebased PR against the new tip
(its base is now one merge stale AND the rendered slot collides again with the newer row). The
lane rebased once onto the tip it was given; the tip moved under it; the PR reads `dirty` again
and that is NOT a lane failure to report as refusal. So on each pass: re-read the live tip
(`gh api repos/<o>/<r>/commits/main --jq .sha`), and if the base is behind it, dispatch ONE more
`make changes-resolve BASE=<current-tip>` rebase naming the *current* sha — never the sha you
dispatched last time. Expect the loop to repeat (bounded by the PR merging or being parked); do
not interpret the second dirty as the lane ignoring the first rebase, and do not fan out a second
re-dispatch to the same lane before checking whether the base simply advanced. If the target
issue carries a `do-not-merge` hold, stop chasing the rendered collision altogether — the PR is
owner-held, not queue-blocking.

### An owner hold is scoped to the ACTION it names — "don't push/merge" is not "don't touch"

Distinguish the two holds before parking a PR, because they have different work available:

- **A hold on a specific action** ("do not push `fix/<x>`", "do not merge/arm #1088", "do not release") bars
  that action only. Preparing the artifact so the action is a one-command step when the owner releases it is
  still allowed and still useful: re-basing the verified head onto the current `main` is preparation, not
  release. Prove the fold is conflict-free first, then dispatch the rebase and say explicitly "do NOT push,
  do NOT merge/arm":

  ```bash
  git -C <repo> fetch origin main
  git -C <repo> merge-tree --write-tree <verified-head> origin/main    # rc=0 + clean tree id = clean fold
  ```

  rc=0 means the extra commits main gained since the artifact was verified do not touch its files, so the
  artifact can be made current at zero risk with the release still held. Reporting "artifact is now current at
  <new-head>, release still owner-gated" is real forward progress, not a stall.
- **A hold on the PR itself** (`do-not-merge` where the criterion is unimplementable, e.g. a rendered-index
  collision that can only resolve by a merge ORDER) — stop chasing its rebase entirely; a repeated dirty is
  expected and re-dispatching spends runs for nothing.

Never widen a specific-action hold into "this PR cannot be touched", and never narrow a proper `do-not-merge`
into "just rebase it anyway". If it is unclear which the owner meant, quote the hold text and ask; do not
assume the stricter reading and idle the lane.

## 3c. A base-FIELD change is NOT a rebase — prove the parent, not `base.sha`

`pulls/<n>.base.sha == main-tip` proves only which branch the PR is *targeted* at. It does **not**
prove the head was re-cut from main. A lane can edit the PR's base ref to `main` and leave the head
object untouched: `base.sha` reads the live tip while `commits/<head>.parents[0]` is still the old
branch point, so `check-pr-base` keeps redding with "foreign commits (1): <old head>" and the branch
stays rooted in the superseded base. A lane does this the same evening it does a *correct* rebase on
another PR, so do not trust the lane's "rebased" for one because it was right on the other.

Tell them apart by the head's parent, never by `base.sha`:

```bash
gh api repos/<o>/<r>/pulls/<n> --jq '{head:.head.sha[0:8],base:.base.sha[0:8],ms:.mergeable_state}'
gh api repos/<fork-or-o>/<r>/commits/<head-sha> --jq '{sha:.sha[0:8],parent:.parents[0].sha[0:8]}'

# correct rebase: parent == live main tip  AND guard flips SUCCESS at the new head
gh api repos/<o>/<r>/commits/<head> --jq '.parents[0].sha[0:8]'   # must equal main tip
```

A good rebase shows up as a NEW head sha whose `parents[0]` equals the live main tip (e.g. the old
head `X` becomes new head `Y` with `Y.parents[0] == main`), and the `guard` check flipping to
SUCCESS at `Y` — that flip is the proof the foreign-commit red is gone. `base.sha == main` with the
SAME head sha and guard still FAILURE is a base-field change only. Remedy for that case is the same
as §3: rebuild the branch ONTO canonical main so the new head's parent IS main — say "rebase the
branch, not the base field" in the dispatch, and give done = head.parent == main tip + guard green.

## 3d. A main advance is a fleet-wide base debt — sweep every open PR, and split the dispatch

One owner merge moves the tip for every open PR at once. Sweep `behind_by` for the whole open set in a
single pass instead of rediscovering staleness PR-by-PR after each red:

```bash
gh api "repos/<o>/<r>/pulls?state=open&per_page=100" --jq '.[]|"\(.number) \(.base.sha[0:8]) \(.head.sha[0:8])"' \
 | while read n b h; do echo -n "#$n "; gh api repos/<o>/<r>/compare/main...$h --jq '"\(.status) ahead=\(.ahead_by) behind=\(.behind_by)"'; done
git fetch origin main && git merge-tree --name-only origin/main <head>   # rc=0 + behind>0 => base refresh only
```

`behind_by>0` with merge-tree rc=0 is a **base refresh, not a conflict fix** — say so in the dispatch and
tell the lane not to look for a semantic collision. Split the work by ownership: the **base refresh** goes to
the rebase/conflict lane (it owns rebases), while the **acceptance criteria / product scope** stay with the
lane that implemented the PR — sending the whole PR to the rebase lane gets you a rebase and no verdict, and
sending a bare rebase to the implementer spends an implementation run on a git operation. Record both on the
issue so the next reader sees the split.

**`mergeable: true` + `mergeStateStatus: blocked` does NOT mean "rebased onto latest main".** A PR that is
one merge behind reads exactly that: no conflict (`mergeable: true`), blocked only on `REVIEW_REQUIRED`/
approval. When a directive (or your own dispatch) says "rebase against latest main", the test is ancestry,
not mergeability:

```bash
MAIN=$(gh api repos/<o>/<r>/git/ref/heads/main --jq .object.sha)
gh api repos/<o>/<r>/compare/$MAIN...<head> --jq '{status,ahead_by,behind_by}'

#   rebased ⇒ status=ahead|identical, ahead_by>=1, behind_by=0  (head = main + its own commits)
gh api repos/<o>/<r>/commits/<head> --jq '.parents[0].sha'   # must equal MAIN (§3c)
```

**Direction is not cosmetic — `compare`'s labels are relative to the FIRST argument as the base.**
`compare/<head>...<main>` puts the head in the BASE slot, so its `behind_by` counts the HEAD's own
commits (always ≥1 for a real PR) and reads `behind_by=1` on a perfectly rebased branch. That is NOT
a staleness measure — reading it as "1 behind main" has sent a pass chasing a phantom rebase. Ask the
stale question in the `compare/<main>...<head>` direction only (ahead≥1 / behind=0), and cross-check
`parents[0] == MAIN`; the two together are the proof the head is rooted in today's main.
```

`behind_by>0` (with `merge-tree` against the live tip rc=0) is a **base-refresh rebase still owed** — dispatch
it even though the API reports the PR mergeable. Never answer "already rebased" from a `mergeable: true`
read: that field answers "will GitHub merge this", not "is it rooted in today's main". **And once a rebase lands, re-send any acceptance-criteria write-back you already dispatched citing the NEW head** — a `--proven` tick bound to the superseded sha is stale and re-reds `check-pr-acceptance` at the new head. Update the dispatch and the on-thread record in the same pass; do not leave a lane writing back against a head that no longer exists.

**Prove the write-back is sha-bound before you tell anyone it "survives the rebase".** The `acceptance_writeback --issue <i> --proven 1,2,3` tool PATCHES each criterion with a `(proven: … head=<sha> …)` pin — read the issue body for that pin to see the head it is anchored to. A pin carrying an old head sha does NOT stay green across a rebase onto a newer tip: the tick is bound to a commit the branch has left behind, so `check-pr-acceptance` re-reds at the new head and the whole write-back must be re-issued against it. The tempting reassurance "the write-back is keyed to the ACs, not the branch sha, so it survives a rebase" is FALSE for a pinned tick — assert it only after confirming the tick carries no head sha (rare), otherwise dispatch the rebase AND the `--proven` re-run at the new head together, so the returning lane does not discover the re-red on its own.

## 5. A PR's ANCESTRY can carry another issue's fix — a clean diff is not a clean branch

The PR `files` list (diff vs merge-base) can be exactly the issue's own files while the branch
**ancestry still contains another issue's commit**. This happens when a lane cuts its branch on top
of a sibling PR's still-unmerged fix commit instead of on `main`.

Read the fork branch's own commit chain and each head's parent — not just the diff:

```bash
gh api "repos/<fork>/<r>/commits?sha=<branch>&per_page=10" \
  --jq '.[]|{sha:.sha[0:11],m:(.commit.message|split("\n")[0][0:60])}'
gh api repos/<fork>/<r>/commits/<head> --jq '{sha:.sha[0:11],parent:.parents[0].sha[0:11]}'
gh api repos/<fork>/<r>/commits/<parent> --jq '.commit.message|split("\n")[0]'  # whose fix is it?
```

Tell: head's `parents[0]` is a commit whose message belongs to a *different* issue, and the PR's
merge-base resolves to that commit (not `main`). The consequence is a **merge-order hazard**: if this
PR merges first it silently lands the other issue's change (or collides with the sibling PR on shared
files like `CHANGES.md`/`docs/changes.d` rows). Confirm the sibling fix is genuinely un-landed by
checking `main` itself (e.g. the file lacks the fix) rather than trusting either PR's self-report.

Remedy and message: sequence the **isolated, priority** PR first (e.g. a severity-high security fix),
then re-base the entangled PR off the resulting `main` so the foreign ancestor drops out and its diff
becomes exactly its own files. State in the dispatch: done = new head's parent != the foreign commit,
shared files (`CHANGES.md`, `docs/changes.d`) non-colliding, diff = own files only. Do not rebase the
entangled PR before the priority PR lands — its current base may be clean; the fix is ordering, not a
premature rebase.

Do not settle ancestry from a `compare/main...<sha>` status line alone: a `...` compare can report
`identical / ahead_by 0 / behind_by 0` for a sha that is demonstrably ahead of `main`. Cross-check
`commits/<sha>.parents[0]` against the live `main` tip — that parent chain is the ground truth for
"is this commit on main / what is this branch stacked on".

## 3e. The body's `AGENTS:`/`BASE:` lines are a CITATION and can be stale even when the branch is fresh

`check-pr-agents-line`/`check-pr-base` read the `AGENTS:<sha>`/`BASE:<sha>` lines the PR body carries,
which a lane populates from `make bot-preflight`. A lane whose clone's `origin` is the FORK can run
preflight against the fork's stale `main` and paste a sha that is dozens of commits behind the
canonical tip — while the PR's actual `base.sha` is the live canonical main (it opened fresh). So the
branch is correctly based AND the body cites a stale sha: the red lands on `guard`/`check-pr-agents-line`
at the next run (often SKIPPED this run because `check-pr-closing` failed first), and reads like a
base problem when it is a citation problem. Measure the cited sha against live main, not the PR field:

```bash
git fetch origin main --quiet
git rev-list --left-right --count <cited-body-sha>...origin/main   # nonzero right = cited sha is BEHIND live main
gh api repos/<o>/<r>/pulls/<n> --jq '{base:.base.sha[0:8],body_base:(.body|capture("BASE: (?<s>[0-9a-f]+)").s[0:8])}'
```

`0 <behind N>` means the body's citation is stale even though `base.sha` is current — the remedy is to
re-run `make bot-preflight` against a fresh `origin/main` and repaste the LIVE canonical sha into
`AGENTS:`/`BASE:`, not a rebase (the branch parentage is already correct; §3c's parent check confirms
that).

**The AGENTS-line gate is ANCESTRY-of-both, not equality with BASE.** `check_pr_hygiene.py`'s
`agents_line_findings` requires the cited `AGENTS:<sha>` to be an ancestor of *both* head and base —
any such sha passes, including the AGENTS.md last-touch commit OR the merge-base. It is NOT a rule
that `AGENTS: == BASE:`. Do not accept a lane's assertion that it is: lanes have invented a
"`check_pr_hygiene.py:572` requires BASE sha == AGENTS sha" rule and propagated it fleet-wide, when
the file is ~509 lines with no such rule and `572` is out of range. `#845` is a *different* gate —
the branch-cut rule (`make check-pr-base`: merge-base must equal the base ref). **A lane's source-line
citation is a claim; verify it against the file** (`wc -l scripts/check_pr_hygiene.py`; grep the
function) before relaying or building on it — a fabricated line number costs the next lane a run.

**AGENTS-line unit shape is `(\d+)b\s+(\d+)l` with NO internal spaces.** A body line `AGENTS: <sha>
91766 b 1363 l` (spaces inside the units) reds `check-pr-agents-line` just as hard as a wrong sha;
the correct form is `AGENTS: <sha> 91766b 1363l`. When a lane's guard reds despite a plausible sha,
check the unit spacing before assuming the sha itself is the problem. Bundle it into the SAME single amend push as any close-text/docs fix on the vehicle — never a
separate round, and never trust the lane's "preflight ran, ancestor-checked" when the pasted sha is
behind main.

**On a stale-based PR, cite the MERGE-BASE, never the live main tip — the live tip is not an
ancestor of the un-rebased head.** When a branch was cut from `<old>` and `main` has since advanced
to `<new>`, the tempting "just cite current main" fix **reddens**: `<new>` is an ancestor of the
BASE (it *is* main) but NOT of the head, so `agents_line_findings` fails the both-sides test. The
sha that passes NOW is the branch's merge-base `<old>` (ancestor of both). But `<old>` is stale the
moment you rebase — so on a stale-based PR the ORDER is **rebase first, then cite**: rebase onto
`<new>` (also clears `check-pr-base`, §3), and only THEN paste `AGENTS==BASE==<new>` (now an
ancestor of both) + the `SYNC:` line. Do not let a reviewer's "measured at current main" remedy
get pasted onto the un-rebased head — it looks right and reddens. If AGENTS.md is byte/line-identical
at both shas, carry the `Nb Nl` units across the rebase unchanged.

Ancestry is measured with **abbreviated** shas: `git fetch origin <full-sha>` can fail
`couldn't find remote ref` for a commit main has already advanced past (GitHub won't fetch an
un-referenced sha by full id), but the abbrev still resolves locally through the fetched graph —
run `git merge-base --is-ancestor <abbrev> <head>` and `... <base>` on the 8-char form the
`git merge-base <head> origin/main` output gave you, not the 40-char id.

**Run the ancestry test on the CITED sha against BOTH head and base BEFORE you send any body-line
remedy.** A green-looking "just update the AGENTS:/BASE: line to current main" is itself a claim,
and it reddens when the cited sha is not an ancestor of the PR's own head. Measure first, then
advise:

```bash
git fetch origin main --quiet
for ref in <head-sha> <live-main-sha>; do
  git merge-base --is-ancestor <cited-body-sha> "$ref" && echo "$ref: ancestor" || echo "$ref: NOT ancestor"
done
```

Two outcomes, two different remedies — do not conflate them:
- **ancestor of BOTH** (a stale citation on a correctly-based branch): the fix is a body-only repaste
  of the live canonical sha (§3e); a rerun clears it because `ci.yml` re-fetches the LIVE body.
- **ancestor of base but NOT of head** (the branch was not actually cut from the base its body claims,
  or the head moved off it): a body-only change can name no sha that passes the both-sides test —
  `main` is not an ancestor of the un-rebased head. The fix is **rebase the branch onto live main
  first**, then preflight and paste the NEW base sha. Sending the body-only remedy here wastes a run
  and re-reds; the honest dispatch says "rebase, then cite", not "update the line".

When a lane's failing `check-pr-agents-line` log reads "no `AGENTS:` line" but the live body clearly
carries one, that is a **body-read race** — the line was added after that run's `gh api` body read
fired. `ci.yml` fetches the live body on rerun, so a body-only fix clears on rerun. But if the cited
sha also fails the ancestry test above, the real defect is the base, and only a rebase fixes it.

## 6. Identifying the VEHICLE: a PR number that resolves is not the right PR

A lane naming "PR #N (head <sha>)" is stating a claim, and the number can resolve to the WRONG
object — a different issue's PR, or an *issue* id adjacent to the PR's. A lane reported "PR #1808"
for its gate work when #1808 was an ISSUE and the real vehicle was #1810 (that issue's PR is #1809),
with a head sha matching neither. Do not route on a spoken number. Verify the vehicle two ways:

```bash

# 1. does the PR close the issue the lane claims to implement?
gh api repos/<o>/<r>/pulls/<n> \
  --jq '{n:.number,title,closes:(.body|capture("(?i)closes #(?<i>[0-9]+)").i?),head:.head.sha[0:8],branch:.head.ref}'

# 2. find the real vehicle when the number is wrong:
gh pr list --repo <o>/<r> --search 'closes #<issue>' --state open --json number,headRefName
```

If `.closes` is not the claimed issue, the number is wrong — correct the lane on-issue before
relaying its report. Same discipline for a **cited run id**: `gh run view <id>` must return a run at
all; an id that 404s is a phantom (fabricated or mistyped) and NO hotfix may be routed on it — demand
an id that resolves and quote its failing job+step. A branch's correct head sha is `pulls/<n>.head.sha`,
never a sha the lane typed in prose.

## 3f. `check-pr-base` fetches LIVE origin/main at RUN TIME — a branch cut at open reddens if main merges mid-matrix, and a prepared rebase script's baked-in base is stale

`make check-pr-base` resolves the live `origin/main` **when the matrix runs**, not the base the branch
was cut from at open. So a branch correctly cut from the tip at push time reddens the moment ANY other
PR merges while its matrix is in flight: the gate sees `merge-base(head, live-main) != live-main` and
fails, even though the branch was fresh when opened and the failing step is NOT a test defect. Read the
failing `guard` job's STEP (not the badge) and confirm `PR_BASE:` in its log != fresh `git rev-parse
origin/main` — that is the base-staleness class (#845/#1015), remedy is a rebase onto the CURRENT tip,
not a code change. On a long matrix this can recur repeatedly as main advances; each re-cut must target
the tip measured *at that moment*.

**Prove the base-drift is mechanical before you call it a lane error — and read the STEP, not the badge.**
On a fleet-vehicle red, `gh pr checks <n>` shows a `fail` row with its run id; `gh run view <run-id> --log-failed | grep -v '^\[' | tail -25` names `PR_BASE:`/`PR_HEAD:`, the measured merge-base and the foreign-commit subject in one read. Then settle the sequence with ancestry:

```bash
git merge-base --is-ancestor <old-main-tip> <new-main-tip>   # true ⇒ a merge landed AFTER the branch was cut
```

True proves the red is base-drift (#845/#1015), not a body/acceptance defect — the branch was fresh when cut and main advanced under it. Remedy is ONE rebase onto the tip measured now; a body edit does not retrigger the guard (only a new push does). On a multi-lane fleet tracker record the diagnosis on the tracker thread and dispatch only the rebase lane; the implementing lane still owes its verdict write-back at the NEW head (§3d), so do not hand it a git operation and do not report the red as its failure.

**A prepared rebase script that hard-codes a base sha goes stale between prep and execution.** A lane
that pre-writes `/tmp/rebase_<pr>_<sha>.sh` against the tip it saw an hour ago will re-redden
`check-pr-base` a second time when it finally runs, because main advanced in the gap (e.g. script
targeted `b9817d51`, but a doc PR merged as `43563ae5` in the meantime). At EXECUTION time re-read the
live tip (`git fetch origin main && git rev-parse origin/main`, or `git ls-remote origin
refs/heads/main`), substitute the real sha into the rebase target and into the body's `AGENTS:`/`BASE:`
lines, and emit them at the new tip — never run the script's baked-in base. Correct the lane on-issue
with the current sha before it executes a stale script; if AGENTS.md is byte-identical at both shas
(same `Nb Nl` units) carry the units across unchanged. A run at the superseded head is void — demand
a fresh COMPLETED run at the re-cut head and quote its job id.

## 3g. "The change is in the file" is a claim about the BLOB at head, not about the PR body

A lane that quotes its added text verbatim in the PR description looks verified, but the body is
authored from memory while the diff can land the text in a different file, a different section, or
not at all. Settle it against the tree at the PR's head, in order:

```bash

# 1. what does the PR ACTUALLY touch?
gh api repos/<o>/<r>/compare/<base-sha>...<head-sha> --jq '.files[]|{filename,status}'

# 2. is the anchoring text present at that exact path+head? (quote path + line number as evidence)
gh api "repos/<o>/<r>/contents/<path>?ref=<head-sha>" --jq .content | base64 -d | grep -n '<anchor sentence>'
```

Resolve the path from step 1's file list, never from a guess: lanes nest skills as
`agents/<lane>/skills/<lane>/SKILL.md` and `agents/<lane>/skills/<lane>-<topic>/SKILL.md` in the same
repo, so a wrong-guess grep returning empty is a path error, not a missing contract — retry against
the real path before reporting a lane short. A compare that shows only docs/wiki files when the
contract was supposed to go into the lane's SKILL.md means the contract has not shipped. Quote the
file path and the line number in the board record, so the next reader can re-run one command and
tell "body says so" from "file says so".

**A multi-PR rollout tracker: measure each lane's PR per branch, not a lane's "N of M landed" tally.**
When one tracker issue is satisfied by several lanes each opening its own PR, the tally is a snapshot
from whoever last counted. Existence-check every expected branch yourself:

```bash
for b in <lane-a-branch> <lane-b-branch> <lane-c-branch>; do
  gh pr list --repo <o>/<r> --head "$b" --json number,state,isDraft,mergeable \
    --jq ".[]|{b:\"$b\",number,state,isDraft,mergeable}"
done
```

A lane can be silent (no PR at all) while the others are green, so re-run this each pass and name the
exact missing branch when you pulse that lane — and post the pulse on the tracker's own thread (naming
branch, expected file, and what "done" is), because a queued DM is not a board fact the next reader
can see.

## 3h. Comparing abbreviated shas: normalise BOTH sides to one length, or you invent a drift

A false "base drifted / head never moved / rebase not taken" finding almost always comes from comparing
unequal-length prefixes. `base[:10]` yields `a3db2f113` while the recorded main tip is the 8-char
`a3db2f11`; the strings differ even though the base IS the live tip, and posting that reads to the fleet as a
real board change. It fires in the other direction too: a 10-char live head against an 8-char recorded tip
looks like "the lane did not push" on a branch that just moved.

- **Slice both sides to the same length** (`main[:10] == base[:10]`) or use `str.startswith` — never compare a
  slice against a fixed shorter literal.
- **Different flags give different widths** (`git rev-parse --short` → 8, an API field `sha[0:10]` → 10).
  Normalise once at capture (`sha = raw[:10]`) and compare only normalised values, everywhere.
- **For "is it on main", prefer ancestry** — `git merge-base --is-ancestor <sha> origin/main`, or
  `compare/<main>...<head>` → `behind_by 0` — which cannot be fooled by prefix length at all.
- If you already posted a drift claim built on a length mismatch, correct it on the same thread in the same
  pass, quoting the equal-length comparison; a false "base moved" post is indistinguishable from a real one to
  the next reader.

## 3i. A stale head's DIFF silently DELETES merged main work — `removed` in `pulls/<n>/files` is the tell

A PR can read `mergeable: true`, `base.sha == live main tip`, `draft: false`, and carry a well-written
body that closes exactly the right issue — and still be a **stale-branch revert**. GitHub computes a
PR's diff against its MERGE-BASE, so when the branch was cut before a merge landed on `main`, every
file that merge added appears in the PR as a *deletion*. Merging it undoes a merged PR. No mergeability
field reveals this: `base.sha` tracks the base branch, not the head's ancestry.

Proof is the per-file `status`, never the filename list (a filename list reads as "touched", which is
indistinguishable from "deleted"):

```bash
gh api repos/<o>/<r>/pulls/<n>/files \
  --jq '.[]|"\(.status)\t+\(.additions)/-\(.deletions)\t\(.filename)"' | grep -E '^(removed|modified)'
git cat-file -e origin/main:<path> && echo 'REVERT: path exists on main'   # for each `removed`
git log origin/main --oneline -3 -- <path>                                 # names the merge it would undo
```

`removed` on a path that exists on live `main`, or `modified` with a large `-` and no `+`, means the
branch predates the commit that added it. Fix = rebase onto live main (the reverts vanish; the issue's
own diff is unchanged); dispatch it to the rebase lane with the `removed` file set quoted verbatim, and
park any reviewer dispatch until the rebased head exists.

**A local `git merge-base origin/main origin/<branch>` printing EMPTY is a fetch failure, not "unrelated
history".** For a fork-hosted head the canonical remote has no `refs/heads/<branch>`; fetch
`refs/pull/<n>/head` or the fork's branch first, or answer the question from `gh api
.../compare/main...<head>` → `behind_by`. Never report "no common ancestor" from an empty merge-base.

**Why a lane's self-verification misses it:** a lane that runs its own gates and reports "gates verified,
PR open, routed" has verified its *own additions*, and its tests still pass on a tree that lacks the
newer main content. This check is the caller's, and it runs before crediting any finished PR.

## 3j. `check-pr-acceptance` red is a VERDICT gap, not a code defect — sequence it after the rebase

When `ci-scope` reds with `[check-pr-acceptance] N violation(s)` naming criteria "still `- [ ]` in the
linked issue's `## Acceptance criteria`, yet the PR body closes the issue", the diff is fine: the write-back
is verdict-gated, so only a reviewer tick clears it. Do not send that red back to the implementing lane as
a failure and do not let it block the base refresh — route the rebase first, then the reviewer at the NEW
head, and say so in the same on-PR comment so the ordering is visible.

## 4. "Run X in_progress" is routinely already COMPLETED — and often FAILURE

A lane reporting its own proof run as `in_progress` ("poller armed") is quoting a snapshot; that run
commonly reads `completed`/`failure` by the time you look, and the head it was launched at may be one
the lane already pushed past.

**Your own polling has the same trap: the head sha can change between two of your calls in one pass.**
`commits/<sha>/check-runs` is keyed to the sha you pass, so a check-runs read at a sha you captured a
minute earlier reports THAT commit's verdict while the PR's live head has since moved — a superseded
`failure` then looks like the current head's result. Re-read `.head.sha` fresh on every poll
(`gh api .../pulls/<n> --jq .head.sha`) and query check-runs at the sha you just read, not one from an
earlier turn. When the head has moved, the earlier run is void; only a run whose `head_sha` equals the
live head is a verdict. Verify the run by id, bind the verdict to its `head_sha`, and confirm
`head_sha == live headRefOid` before quoting it to the owner:

```bash
gh api repos/<o>/<r>/actions/runs/<id> --jq '{status,conclusion,head:(.head_sha[0:8]),name}'
H=$(gh pr view <n> -R <o>/<r> --json headRefOid --jq .headRefOid)
gh api "repos/<o>/<r>/actions/runs?head_sha=$H" --jq '.total_count, (.workflow_runs[]|{name,status,conclusion})'
```

`total_count=0` at the live head means no CI has run there yet (re-read once — a just-pushed head may
not be registered), NOT that the lane's stale run is the verdict. Report the measured object once on
the board, then hold; do not re-explain staleness on every repeat (§6c tombstone discipline).

### `commits/<sha>/check-runs` empty is not "no CI" — read the PR's own `statusCheckRollup`

A bare `gh api repos/<o>/<r>/commits/<sha>/check-runs` returning `[]` reads as "that head has no CI",
but for a fork-PR head the canonical commit graph may not resolve the sha the way you expect, and a
sha you took from a message or an earlier turn may simply not be the live head. Confirm where the head
really is (`gh api .../pulls/<n> --jq .head.repo.full_name`, then `--jq .head.sha`), and read its CI
state through the PR object, which resolves the PR's own head for you:

```bash
gh pr view <n> -R <o>/<r> --json headRefOid,statusCheckRollup \
  --jq '{head:.headRefOid[0:8], checks:[.statusCheckRollup[]?|{n:.name,s:.status,c:.conclusion}]}'
```

If that rollup is non-empty, the empty `commits/<sha>` answer was a wrong-sha or fork-resolution
artifact, not absent CI — do not report "no CI at the head" from it.

`commits/<x>/check-runs` also 422s with `"No commit found for SHA: <n>"` when `<x>` is a **PR
number** rather than a commit sha — the path takes a ref, not a pull id. Resolve the head sha first
(`gh api .../pulls/<n> --jq .head.sha`) and pass that; never pass the PR number.

### `mergeable_state` reads empty or `unknown` — that is a computation lag, not a verdict

`gh pr list --json mergeableState` (and the bulk `pulls?state=open` list) routinely returns an
EMPTY `mergeable_state`, and a single-PR `pulls/<n>` read right after a head push returns `unknown`
while GitHub recomputes mergeability. Neither is "clean" and neither is "dirty" — an empty/unknown
field silently no-jq's to a blank column and fools a sweep into thinking the query failed. Measure
per PR and re-query once before classifying:

```bash
gh api repos/<o>/<r>/pulls/<n> --jq '{ms:.mergeable_state,mergeable,head:.head.sha[0:9],base:.base.sha[0:9]}'

# again ~seconds later if ms=="unknown" (fresh head push) — then merge-tree to prove the dirty is real:
git -C <repo> merge-tree <live-main> <head> | grep -E 'CONFLICT|^[0-9]{6} '   # truth of dirty, independent of the API
```

A `dirty` from the API is a claim about the current base; `git merge-tree <live-main> <head>` is the
evidence — it prints the CONFLICT lines and the three blob variants (base / our-side / their-side),
which is what distinguishes a semantic collision from a rendered-index one. Never report `clean` from
an empty/`unknown` field, and never report `dirty` without the merge-tree line to back it.

### `pulls/<n>.base.sha` is the PUSH-TIME base, not live `main` — a stale base skews the dirty test

The PR object's `base.sha` is the base tip **recorded when the branch was last pushed**; it does NOT track
`main` afterwards. Reading `.base.sha` and calling it "current main" is wrong the moment any PR merges:
main advances, the PR's `base.sha` stays put, and the PR can flip `dirty`/stale while its content still
merges cleanly. Measure the live tip directly, never from the PR field:

```bash
git fetch origin main && git rev-parse origin/main    # authority for live main
git ls-remote origin refs/heads/main | cut -c1-12     # same, no local fetch
gh api repos/<o>/<r>/pulls/<n> --jq '.base.sha[0:8]'  # push-time base — compare, do NOT assume equal
```

When the API says `dirty` but `git merge-tree <recorded-base> <head>` returns rc=0 with no `CONFLICT`
line, do NOT conclude "no conflict, API lying": the recorded base is behind live main, so any real
conflict is against the **newer** tip. Re-run `git merge-tree <live-main> <head>` before calling it clean
— a clean tree against a stale base proves nothing about merging into today's main. A `dirty` whose
merge-tree against the LIVE tip is also clean is the stale-base artifact (base one merge behind) = a base
re-cut, not a conflict resolution. Either way the dispatch target sha is the LIVE tip, never the PR's
recorded `base.sha`.
