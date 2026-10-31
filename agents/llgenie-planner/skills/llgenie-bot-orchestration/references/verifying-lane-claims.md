# Verifying a lane's claims before you repeat them

A lane's report is a claim; the API and the object store are the evidence. Repeat offenders
seen in practice, each with the check that settles it.

## 1. "Committed `<sha>`, merge-clean on main" → often the lane's OWN clone

Lanes build in sibling clones (e.g. `/home/asimov/repository/git/ai-repositories/llgenie`), not in
the planner's tree and not upstream. `git -C /home/asimov/repository/git/llgenie cat-file -t <sha>`
returning `fatal: Not a valid object name` does **not** mean the lane fabricated the commit.

Check, in order:

```bash
# where does it actually live?
for d in /home/asimov/repository/git/ai-repositories/llgenie; do git -C "$d" cat-file -t <sha>; done
# what's in it (file count / insertions should match the lane's description)
git -C <sibling> show --stat --oneline <sha>
# is it published, or held for the owner's gate?
git ls-remote origin refs/heads/<branch>     # empty output = not pushed (owner-gate), which is correct for lane work
```

A commit that resolves in a sibling clone with the described file count is verified work, not a
phantom. Say "held locally, owner-gated" — never "unpushed and therefore unverified".

## 2. Worktree listing is not the evidence either

`git worktree list --porcelain` shows worktrees of one clone only; a lane's work can be in a
sibling clone that no worktree listing mentions. Search clones and branches, not just worktrees.

## 3. Run-level duration includes queue dwell

Sweep tools that print `run.created_at → run.completed_at` are queue-inclusive: `217m24s` and
`246m02s` are starved runners, not test legs. The real leg wall is job-level:

```bash
gh api repos/asimov-agent/llgenie/actions/runs/<id>/jobs --jq \
  '[.jobs[]|select(.name=="linux / unit")|"competition \(.started_at)→\(.completed_at)"]'
```

Quote the job-level span when the claim is "the unit leg took N minutes".

## 4. Short shas and stale posts

- An 8-char prefix is not an identity. A re-author (off-allowlist → allowlisted) produces a *new*
  commit that can share the old prefix family; read `headRefOid` in full before comparing heads,
  and verify ancestry with `git merge-base --is-ancestor` / `compare` (expect `diverged a1/b1`,
  not an ancestor).
- A lane's message can be generated *before* your correction lands. Compare the timestamp of the
  comment it quotes against the timestamp of your correction; a "fresh pasted" post that predates
  the correction is stale board state, not a refusal to read the API. Say so plainly and re-send
  the corrected fields once, with the exact job id.

## 4b. "That sha / comment does not exist on this repo" — check the ID, not a search

A lane dismissing evidence as nonexistent ("the cited main `7640feae` and comment `6537516392`
don't exist on this repo") is itself a claim, and it is routinely wrong: a search endpoint, a
branch-scoped listing or a `--search` query returns a subset, so an artifact that exists is
invisible. Settle it with the ID-specific endpoints — they answer for the object, not a result set:

```bash
gh api "repos/<o>/<r>/commits/<sha>" --jq '"\(.sha[0:12]) \(.commit.message|split("\n")[0])"'
gh api "repos/<o>/<r>/issues/comments/<id>" --jq '"\(.id) \(.created_at) \(.user.login) \(.issue_url)"'
```

The comment endpoint is **repo-level**, not nested under the issue: `.../issues/<n>/comments/<id>`
404s, and `gh api ".../issues/<n>/comments?sort=..."` ignores `sort` and returns oldest-first — so a
recent comment looks absent. Use the paginated issues/comments read or the ID endpoint.

When the artifact does exist but **predates a closure**, the honest correction is "superseded, not
absent": name the closure timestamp and the timestamp of the cited comment (`02:00Z` comment vs
`04:28Z` close) so the lane sees *why* it read as stale. Correct the false-absent claim as firmly
as the false-present one — a lane that reports real work as nonexistent sends the next reader to
re-derive it.

## 5. "My drift rows are 0" is a snapshot, not a state

A lane that opened a live→tree sync PR and reports "after <head>, my rows: 0" measured its
*worktree at its base*. Before accepting it: re-run `check_agent_profiles.py check` at current
`origin/main` and stat the **live** profile mtimes (`ls -la --time-style=full-iso`). A cron that
writes lessons into live profiles (the dirty-watch class) regrows drift after every clearing PR,
so by merge time the gate can show new live-longer lines and files that were never in the vehicle.

What to do: keep the bounded vehicle as-is (do **not** re-push it to chase the drift — the writer
outruns you and the push re-triggers review), name the residual files with their byte sizes and
mtimes, and flag the live-writer on the live-drift tracker with those mtimes as evidence. Then ask
the lane whether it writes its own live profile (a cron id or watcher state) rather than assuming.

## 5b. A real drift is still not the reporting lane's work — ownership follows the tree

A lane that measures a genuine live↔tree delta in **another** lane's `agents/<lane>/` tree is a
useful sensor, not the owner. Verify the delta and then route it to the tree's owner; do not let the
reporting lane open the PR. Two independent facts must both hold before you dispatch:

1. **The drift is real** — measure it, don't accept the claim. Compare the served tree blob at the
   fetched `main` sha against the live profile file, isolated by skill dir (live path is
   `<profile>/skills/<skill-dir>/...`, no `agents/` prefix; locate it with `find`, never construct it):
   ```bash
   git show <main>:agents/<lane>/skills/<skill-dir>/SKILL.md | wc -l
   wc -l < <profile>/skills/<skill-dir>/SKILL.md
   diff <(git show <main>:agents/<lane>/skills/<skill-dir>/SKILL.md) \
        < <profile>/skills/<skill-dir>/SKILL.md     # the live-only hunk IS the delta
   # references/ parity (an identical refs set means SKILL.md is the only drift):
   git ls-tree <main> --name-only agents/<lane>/skills/<skill-dir>/references/ | sed 's|.*/||'
   ls <profile>/skills/<skill-dir>/references/
   ```
   A live-longer-than-tree SKILL.md with identical `references/` is the #1062-shaped "bring the tree
   up to current live" follow-up, not a truncation.
2. **It is unclaimed** — no OPEN PR touches `agents/<lane>/` (check `pulls/<n>/files` for the open
   set, not a bare crossref list) and the merged precursor issue is CLOSED.

Dispatch the delta to `@llgenie-<lane>` — its own tree, per lanes-version-their-own-rules — with the
8-line-or-whatever hunk quoted, the merged precursor PR sha named, the fresh-branch-off-`main`
discipline, and (when the edit itself is a tracked-behaviour change) the #1123 change→note duty the
lesson prescribes (`agent-wiki/<stem>.md` + `docs/changes.d/<stem>.md` + `make changes-index` +
commit the regenerated `CHANGES.md`). Tell the reporting lane to **withdraw its claim on-record**
("drift confirmed real but <owner-lane>'s tree; routed there") and proceed to its actual vehicle —
never let it touch `agents/<other-lane>/`, the same boundary it should hold on any peer tree.

**Worktree/PR-attribution corrections are usually right — accept them when verified.** When a lane
says "those worktrees / that sweep aren't mine", check the facts: worktrees under a shared
`llgenie-wt/` with rebase-lane suffixes (`pr*`/`*-rebase`) are the pr-merge-conflict lane's, and if
their PRs are `MERGED` the branches are history, not a live vehicle. A lane correctly refusing scope
it never took is a correction of *your* tracker — record it and re-route, don't re-insist.

## 6. "The PR contains <file>" — read the head tree, not the report

Verify a PR's promised file set and contents against the pushed sha, without a checkout:

```bash
gh pr view <n> --json headRefOid,baseRefOid,isDraft,mergeStateStatus,files \
  --jq '.headRefOid,.baseRefOid,(.files[].path)'
git cat-file -e <head>:<path>                       # fixture/file present at that exact head
git show <head>:<path> | grep -nE '<marker>'       # the promised line is in the served blob
git merge-base --is-ancestor origin/main <head>    # or compare baseRefOid with freshly fetched main
```

A `baseRefOid` behind the freshly fetched `main` means the PR was branched from a stale tree even when
the lane says "branched fresh" — report the base sha, not the claim.

**A lane's on-record "base=current origin/main `<sha>`" is the claimed base, never the branch point.**
`gh pr view`'s `baseRefName` is always `main` (a branch name), so it can neither confirm nor refute a
rebase — the lane is asserting where it *thinks* it sits. Prove it on the objects: the head's real
branch point must equal the cited `main` sha, i.e. `git merge-base origin/main <head>` == the sha the
lane quoted. If the merge-base is an *older* commit, the rebase did not happen no matter what the
report or the PR summary says — a lane repeatedly reporting "based on current main `<new>`" while its
head still sits on `<old>` is reporting the desired state, not the object state.

**A named remote-tracking ref is a SNAPSHOT, not live — force-refresh it immediately before measuring.** `git fetch origin pull/<n>/head:refs/remotes/origin/pr<n>v2` creates `origin/pr<n>v2` at the head *as of that fetch*; later pushes to the branch do NOT update it, and a second fetch under a *different* name (`pr<n>x`) creates a separate ref while the old one keeps a stale head. Measuring `git diff origin/main..origin/pr<n>v2` minutes later therefore reads an old head — you can report the wrong file count ("3 files") and even report a diff hunk as ABSENT when the live head carries it (a self-inflicted false-negative that makes you accuse an honest lane of dodging a real finding). Rule: **fetch with an explicit `+`/`--force` into the SAME ref name right before every measurement, and never reuse a ref you did not just refresh**:
```bash
git fetch origin +pull/<n>/head:refs/remotes/origin/pr<n>   # '+' = force-update; run each time
git rev-parse --short origin/pr<n>                         # == the head you quoted in the same breath
git diff --name-status origin/main..origin/pr<n>           # the live file set
```
When a fresh fetch contradicts a figure you just gave a lane, retract it explicitly and re-measure — the fix is identical to §6b's: fetch fresh, name the ref, quote the sha.

**Fetch the PR head into a DEDICATED ref — never FETCH_HEAD.** `git fetch origin main` (and every
`git fetch <remote> <branch>`) **re-points `FETCH_HEAD`**, so a `git fetch origin pull/<n>/head` you ran
first is silently overwritten and your next `git rev-parse FETCH_HEAD` / `git show FETCH_HEAD:<path>` /
`git diff origin/main FETCH_HEAD` is measuring `main`, not the PR — producing head files that appear
present then absent, or a spurious "0 commits ahead", in consecutive calls. Name the ref explicitly
and keep it stable across the whole investigation:

```bash
git fetch origin pull/<n>/head:refs/remotes/origin/pr<n>
git rev-parse origin/pr<n>                       # the head sha — stable
# optionally fetch main too, but you now measure <head> as origin/pr<n>, never FETCH_HEAD
git merge-base origin/main origin/pr<n>          # the TRUE branch point
```

**A stale base can silently revert the sibling merge between it and the tip.** `git diff --name-status
origin/main origin/pr<n>` showing files as **`D` (deleted)** that the intervening merge ADDED means
merging the PR as-is would undo that merged work. Check the file set, not just the base sha:

```bash
git fetch origin main
git log <merge-base>..origin/main --oneline     # what landed since the PR branched
git diff --name-status origin/main origin/pr<n> # 'D' of a since-merged file = revert
# cross-check specific promised files exist AT the head:
for f in <files the merged work added>; do git show origin/pr<n>:$f >/dev/null 2>&1 || echo "MISSING $f (revert)"; done
```

No overlap ⇒ the stale base is cosmetic (rebase for a clean diff); overlap plus a deletion ⇒ the PR is
a revert and must be rebased before it can be a vehicle. When the deleted set is the *whole* of a
sibling PR (a feature's code+test+note+changes.d all marked `D`), the PR is a mass-revert and the lane's
"based on current main" plus "gates green locally" are both claims about a tree it never had — restate
the gate as: `git merge-base origin/main <new-head>` = the cited sha AND `git diff origin/main <new-head>
-- <sibling file>` empty, quoted back in the lane's report.

## 6b. "Rebased onto <main> @ <sha>, PR open" — the push may not have landed

A lane reporting a rebase+push is often reporting its **local** clone: the rebase commit exists
as an object, but the remote branch and the PR still point at the old head. Verify the remote, not
the report:

```bash
git rev-parse origin/<branch>                     # remote branch ref
git rev-parse origin/main                         # the base it claims to sit on (may have moved again)
gh pr view <n> --json headRefOid --jq .headRefOid  # what the PR actually tracks (=== remote ref expected)
```

If the reported sha is not the remote branch ref / `headRefOid`, the push did not land — say
"`<reported sha>` is an unpushed local commit; remote/PR still at `<actual>`" and correct the PR
record. Do not accept "rebased fresh" as fact; also re-fetch main, since it commonly advances
again between the lane's fetch and your read (a lane can be honest about fetching and still one
commit behind by the time you measure).

## 6c. A reply that answers a different (crossed/stale) dispatch

A lane's reply can address an **older queue** than the one you just sent — it lists items you are
not tracking this round and calls them "already done", while ignoring the item you actually
dispatched (often one with a red gate at an unchanged head). Reconcile before arguing:

- Check the item it calls "done" is genuinely closed/merged (`gh issue view <n> --json state`,
  `gh pr view <n> --json state,mergedAt`, and `git cat-file -e <main>:<path>` for the promised
  file). If it is, accept it plainly — no duplicate vehicle — and say so.
- Then re-anchor on the REAL dispatched item: quote its head + the red run id
  (`gh api .../runs?head_sha=<full>`) and restate the exact unblock (files, checks, push, report).
- When the DM channel is `queue_full`, do **not** resend: route the correction as a comment on the
  PR/issue (`gh pr comment <n>`) so it is on-record, and cite the comment id as the evidence the
  dispatch landed.
- When the **Nerve progress guard** blocks `message_agent` ("requires task-relevant implementation
  now"), do not clear it by editing a peer lane's files — a red check is better than breaking the
  lane boundary. Post the same routing/relief text as `gh issue comment` / `gh pr comment` (the
  planner's correct on-record channel anyway) and cite the comment id. Retry the DM only once the
  guard is no longer the blocker.
- When the guard escalates and demands a **repo-level mutation** (a commit/branch/PR), a planner
  has no lawful one — "you do not implement" means a branch/PR/commit from the planner lane is the
  mistake, and mirroring your own reference files into the shared clone's `main` working tree is
  worse than useless: those files are **untracked in a checkout the implementer never sees** (it
  branches off `origin/main` in its own worktree) and risk being swept into someone's later commit.
  Refuse, leave the tree clean, and report the measured board state — a red completion check is
  preferred to a role violation or a fabricated vehicle.

## 6d. "This issue already has a PR" — crossrefs include dead vehicles

The one-vehicle check before dispatch is a **two-step** query, not one. An issue's timeline
`cross-referenced` events list every PR that ever touched it — merged months ago, closed unmerged,
abandoned — so a single timeline read makes almost every recurring-theme issue look already-claimed
and freezes the fleet for no reason. Collect the PR numbers, then filter to those still `OPEN`:

```bash
# step 1: which PRs ever cross-referenced this issue
gh api repos/<o>/<r>/issues/<n>/timeline \
  --jq '[.[]|select(.event=="cross-referenced" and (.source.issue|has("number")) and .source.issue.pull_request!=null)|.source.issue.number]|unique'
# step 2: keep only the ones still open — THAT is the live vehicle
for pn in <numbers>; do
  st=$(gh pr view "$pn" -R <o>/<r> --json state --jq .state 2>/dev/null)
  [ "$st" = "OPEN" ] && echo "$pn OPEN"
done
```

Only an `OPEN` PR number is a vehicle that blocks a fresh dispatch. A closed/merged crossref is
history: dispatch onto the issue normally. Skipping step 2 — or trusting the bare crossref list —
is how a lane gets parked on a `do-not-merge` reason that expired long ago, indistinguishable on the
board from abandonment.

## 6e. A sweep/rebase lane's table is N claims, not one

A sweep lane reports a *matrix* — "#A → head sha, red=scope; #B → head, 0-red; #C → guard=FAILURE" —
and the temptation is to accept the whole table because two rows check out. Verify **each row
independently** against the API before you repeat "the sweep is accurate":

```bash
for pr in <A> <B> <C>; do
  gh pr view "$pr" -R <o>/<r> --json headRefOid,mergeStateStatus --jq '"#\($pr) \(.headRefOid[0:8]) mss=\(.mergeStateStatus)"'
  gh pr checks "$pr" -R <o>/<r> 2>&1 | grep -E 'bucket=fail'      # the red it attributes, at THAT head
  git merge-base --is-ancestor origin/main "$(gh pr view "$pr" -R <o>/<r> --json headRefOid --jq .headRefOid)" && echo "#\($pr) on-main"
done
```

A row's head sha binds its verdict: if the sweep cites `head=h` but the PR is now at `h2` (another lane
pushed), the attributed red is about a branch state that no longer exists — quote the live head and re-read
its checks rather than repeating the stale diagnosis. Rows commonly diverge in *kind* too: a "rebase-fixable"
red (scope/format) is a different remedy than a label/linked-issue guard red (see the guard section of
`stalled-lane-and-dispatch-delivery.md`) — do not let one lane's blanket "rebase and re-run" cover a row whose
red never touches the base. Accepting a sweep is accepting every row; a single unverified row is an
unrepeatable claim.

## 6f. A profile-fold PR: refs are byte-identical, SKILL.md is a union (and WILL differ)

When a lane folds a live profile into the tree and reports "refs sha256-identical live↔tree, SKILL.md
**union** (0 live lines lost)", the two claims must be verified *differently* — a naive byte-compare
false-reds the SKILL.md and a constructed path yields a false "missing":

- **`references/` files = strict byte copies; they must match live exactly:**
  ```bash
  git show <head>:agents/<lane>/skills/<skill-dir>/references/x.md | sha256sum
  sha256sum <profile>/skills/<skill-dir>/references/x.md
  ```
- **SKILL.md = union, so it is *larger* than live, not identical.** The fold appends tree-only
  `## Rules/## Procedure/## Never` sections that live never carried (versioning a live profile into
  `agents/<lane>/`). "DIFFERS tree=24382b live=20309b" is the *expected* result of a correct union —
  report it as union-verified, never as a mismatch or truncation. Verify the **union property**, not
  sha equality: every live line survives (`comm -23 <(sort live) <(sort tree)` empty / "0 live lines
  lost"). A tree *smaller* than live is the truncation red flag; a tree larger is the union working.

**Locate the live skill dir with `find`, never construct it.** The live path is
`<profile>/skills/<skill-dir>/...` — no `agents/<lane>/` prefix — and `<skill-dir>` can differ from
both the lane name and the repo path (`agents/<lane>/skills/security-scan-ops/` ↔ live
`skills/security-scan-ops/`). A hand-built path returns `0 lines` and reads as "file absent/truncated":
```bash
find ~/.hermes/profiles/<lane> -type d -name <skill-dir>
```
A **third** fold beyond the two dispatched files is acceptable when it stays under the lane's own
`agents/<lane>/` and is disclosed — but it is also the signal a live writer is active: route that
writer to the owner-gated live-drift tracker, and keep this bounded vehicle as a snapshot (do not
re-push it to chase the drift; the writer outruns you and every push re-triggers review).

## 6g. "In flight" is a claim too — a named branch is not a vehicle

Before you list an issue as "in flight" in a queue, a stand-down, or another dispatch's premise,
prove the vehicle exists on the remote. The dispatch that *named* a branch (`fix/<n>-...`) and the
lane that *said* it started are both claims; measure them:

```bash
git ls-remote origin "refs/heads/fix/<n>*"                        # empty = nothing pushed
gh pr list -R <o>/<r> --head "fix/<n>-..." --json number,state   # empty = no PR
```

Empty on both means the item is **"awaiting branch", not "in flight"** — it holds no vehicle, blocks
no fresh dispatch, and must not be counted as a lane's load or armed (`gh pr merge --auto` on a
phantom arms nothing and reports success). Do not route a *second* item on the assumption the lane is
busy with it. When you discover your own premise was wrong, correct the on-record queue/issue with the
measured emptiness and the `main` sha you measured at — a fleet-state claim is verified exactly like a
lane's claim, and an unverified "in flight" is what makes the board look blocked when it is idle.
(For `gh pr view <n>` on an ISSUE number → `Could not resolve to a PullRequest`, see the issue-vs-PR
section of `stalled-lane-and-dispatch-delivery.md` — that error means `<n>` is an issue, not a
vanished PR.)

## 6g-bis. Heads-ref absent but `refs/pull/<n>/head` resolves = PR lives, branch does not

The mirror of 6g: `gh pr view <n>` reports `headRefName=fix/<x>` and a `headRefOid`, the PR is
`OPEN`/`base=main`, and `gh api pulls/<n>` returns a real sha — yet:

```bash
git ls-remote origin refs/heads/fix/<x>              # EMPTY — branch not addressable
git ls-remote origin refs/pull/<n>/head             # resolves to the same sha — PR ref survives
git cat-file -t <sha>                               # may fail locally (object only remote-side)
gh api "repos/<o>/<r>/actions/runs?head_sha=<sha>" --jq .total_count   # 0 = no CI ever ran there
```

That combination is not fabrication and not a complete vehicle: the commit is real (reachable through
the pull ref) but no lane can fetch or rebase the branch, and `merge --auto` there arms nothing useful.
Also `total_count=0` with `state=pending`/zero contexts proves the lane's "verified at head" is
**local-only** — honest when it separately defers arming, but never a CI-green verdict. Reply: credit
the content, name both anomalies, and require the `refs/heads/` push plus a completed run id before
crediting the vehicle.

## 6h. The arm field (`autoMergeRequest`) flaps on a MERGED PR — verify `state`/`mergedAt`

A lane reporting "`autoMergeRequest` moved 20:53:30Z → `none` between two reads, did someone
disarm?" is usually reading a **merged** PR, where the field is meaningless noise. `gh pr view
<n> --json state,mergedAt,autoMergeRequest` can return the stale `enabledAt`/`mergeMethod`
metadata on one call and `none` on the next, with `state=MERGED` throughout — the several-minute
flap is a #1106-class observation ambiguity, not an action. Settle it on the PR's lifecycle, never
on the arm field:

```bash
gh pr view <n> -R <o>/<r> --json state,mergedAt,mergeCommit --jq '{state,mergedAt,merge:.mergeCommit.oid[0:8]}'
```

If `state=MERGED`, the arm was consumed at `mergedAt` and there was never a live arm to disarm —
say "merged `<sha>` at `<time>`, arm moot" and drop it. Never act on an `autoMergeRequest`-only
observation (no push, no cancel, no re-arm) on a PR whose `state` you have not read.

**On an OPEN PR, a lane's "armed `<time>` method SQUASH (read back)" is still a claim — read the field yourself.** `gh pr merge --auto` exits 0 and can arm NOTHING (non-default base, blocked state, a phantom branch), and the lane's own read-back line is not evidence. Settle it directly:

```bash
gh pr view <n> -R <o>/<r> --json autoMergeRequest --jq '.autoMergeRequest // "NONE"'
```

An object with a non-null `enabledAt` and `mergeMethod` is armed; `null` — or `enabledBy:null` — means nothing is armed despite the exit 0. A PR `BLOCKED` only on `reviewDecision=REVIEW_REQUIRED` with every check `completed`/success is genuinely done-waiting-on-the-owner-review-wall (lanes cannot self-approve, §6j), which is exactly the case armed automerge belongs in — so tell the lane to re-arm and quote the read-back object before claiming it. The same
stale-premise class shows up in a lane *holding* on a merged vehicle ("won't advance X until Y
merges" when both are already merged): dissolve the dead precondition, re-point the lane at its
one genuinely open vehicle, and quote the merge shas as the proof the hold expired.

**An owner merge can pre-empt a lane's "RED / not done / not armed" verdict.** A lane can measure a
red run at a head and report it, then the owner approves and merges the very same PR a minute later
— so when the lane's message arrives, "#N is RED, not armed" is already false: `state=MERGED`. Before
you spend any dispatch relaying or fixing a "not done" verdict, read the lifecycle first and treat a
merge as the final word:

```bash
gh pr view <n> -R <o>/<r> --json state,mergedAt,mergedBy,mergeCommit,headRefOid \
  --jq '"#\(<n>) \(.state) mergedAt=\(.mergedAt//"-") by=\(.mergedBy.login//"-") mc=\(.mergeCommit.oid[0:8]//"-")"'
```

If `state=MERGED`, the red run is moot: correct the lane on-record ("merged `<sha>` at `<time>` by
`<who>`; the RED run at `<old head>` predates the merge"), verify the merged content is actually on
`main` (`git show origin/main:<path>`), and drop the fix — identical content is on `main`. Do NOT
re-open or re-arm. Merged-by = the owner identity (`asimov-agent`) is a legitimate fast approval;
merged-by = a bot/lane identity crossing a review wall it does not hold is the incident (§6j's
approval pairing), not the convenience.

## 6i. The lane's own cited head may be a pre-rebase sha that no longer exists

A lane that rebased onto a newer `main` before reporting often quotes the **pre-rebase** head; the
rebase rewrote it, so the PR's commit list contains only the new sha and the cited one is not
ancestor of anything. Do not call it a phantom (the lane did push real work) and do not carry its
"I will arm at `<cited sha>`" plan forward — arming at a sha that is not the PR head arms nothing.

```bash
gh api repos/<o>/<r>/pulls/<n>/commits --paginate --jq '.[]|.sha[0:8]'   # the shas that ARE the PR
gh pr view <n> --json headRefOid,baseRefOid --jq '.headRefOid[0:8],.baseRefOid[0:8]'
```

If the cited sha is absent from the commit list, correct it explicitly: quote the live `headRefOid`,
the `baseRefOid` (often already the current `main`, proving the rebase landed), and restate the
gate as "all checks completed/success **at <live head>** — arm there, then read `autoMergeRequest`
back". A cited-head mismatch is a reporting-staleness fact, not an integrity finding; state it in one
line and re-anchor the lane, don't escalate it as fabrication.

## 6i-bis. A verification/re-confirm run at an OLDER sha is not head-evidence

A lane may dispatch its proof-run (re-confirm, engine-build, acceptance gate) with `workflow_dispatch`
pinned to a sha **older** than the PR head, then argue "the workflow doesn't read the file I dropped,
so the run is still valid." That argument is usually a dodge: `git diff --name-only <run-head> <live-head>`
shows *what actually differs*, and a diff in any file the run installs/executes/measures (a skill
reference, a Makefile, a test) makes the run a measurement of a tree the PR no longer has — regardless
of which other file the lane is talking about.

```bash
git fetch origin +pull/<n>/head:refs/remotes/origin/pr<n>   # live head, force-refreshed
git diff --name-only <run-head-sha> origin/pr<n>            # run-head vs live-head, not vs main
gh api repos/<o>/<r>/actions/runs/<id> --jq '.head_sha'     # the run's actual head
```

AC/verdict is valid **only when run-head == PR-head** (or the run-head's tree is provably identical in
*every consumed input*). Restate it as: re-dispatch at the live head, report `run-head == PR-head` on
conclusion. A green the lane points at that exists *because* of the edit it is about to keep (a census
re-point against a shared gate, say) is not a green for that gate — require the edit dropped or the run
re-pointed before the AC is written. State it once on-record with evidence quoted; do not reargue it
five times — let the ball sit on the lane's head.

## 6k. "Picked & implemented → PR #N" can be a duplicate of work already on main

A lane's "first pick done, PR open" is itself a claim that the issue still needed the work. Before
crediting a new PR as the vehicle — and especially before spending a two-live-vehicle merit
comparison — prove the issue is still OPEN and the change is not already shipped:

```bash
gh issue view <n> -R <o>/<r> --json state,closedAt                         # CLOSED = already delivered
git fetch origin main
git log --oneline <lane's-cached-base>..origin/main -- <files the PR touches>   # a commit "(#<n>)" = shipped
git show origin/main:<path> | grep -cE '<marker>'                          # the promised behaviour is on main
```

If the issue is CLOSED and a merge commit for it sits on `main` between the lane's base and the tip,
the new PR is a **duplicate of delivered work**, not a live vehicle: close it as redundant (quoting
the merge sha and the on-main file evidence), delete the branch, and say explicitly that the
diagnosis was delivered, not rejected. Do **not** run a comparison table — that is for two *OPEN*
vehicles; comparing a fresh PR against already-shipped work only legitimises the duplicate. When the
new PR also sits on a stale base and shows `mergeable=CONFLICTING ms=DIRTY`, the conflict is usually
just the already-merged sibling in the same file — rebasing onto the tip cannot make it a vehicle.

Two follow-on traps:

- **A board mutation can exit 0 and change nothing — and a pipeline hides the real status.** `gh pr close`
  takes `--comment`, NOT `--comment-file`/`-F` (those belong to `create`/`comment`); an invalid flag makes it
  print usage to stderr while `| tail -2` reports `tail`'s exit 0, so the failed close reads as success. Never
  pipe a state-changing `gh` command through `tail`/`head` — check `$?` on the command itself. After ANY board
  mutation (close/open/label/state) re-read it (`gh pr view <n> --json state`); if it did not take, drive it
  through the API and re-read again: `gh api -X PATCH repos/<o>/<r>/pulls/<n> -f state=closed --jq .state`.
  Confirm a close (not a merge) with `merged=never` + `mergeCommit=nil`.
- **`gh pr close` on an already-closed PR posts NO comment and exits reporting "already closed".** The
  lane (or a pre-empting owner) may have self-closed first — every lane shares one token, so the
  closer's identity is indistinguishable on the timeline. Read the comment list back
  (`gh api repos/<o>/<r>/issues/<n>/comments`) before assuming your evidence trail exists; if only the
  pre-empting comment is there, your detailed comparison never landed — re-post it if the record needs
  it, otherwise credit the self-correction (a lane that reads main before re-picking is the behaviour
  you want) and move it to its next real vehicle.
- **A "surface-facts" report omits the fatal field.** "OPEN / not-draft / base main" is fully
  consistent with `mergeable=CONFLICTING` and `mergeStateStatus=DIRTY`, and a DIRTY PR gets **no CI run
  at all**. Always read `mergeable,mergeStateStatus` alongside `state`; a PR quoted as ready while DIRTY
  is a stalled vehicle the lane must rebase onto the live tip before anyone can gate it.

## 6l. A report with placeholders or a guessed PR number is not a report

A lane that reports `head {HEAD}`, `run {RUN}`, or asks you to "confirm below" its own PR number
("PR #1218?") has not identified its vehicle. Resolve it by **branch**, never by the number the lane
proposes — the number it guesses is often a closed duplicate from the same lane's earlier work:

```bash
gh pr list -R <o>/<r> --state all --head <branch> --json number,state,headRefOid,baseRefName
```

The branch is the identity; PR number, head and run id are facts you fetch, not fields you accept.
Report the resolved number back in one line ("PR = #<n>, head <sha>, base <sha>") so the lane's next
report is anchored. Treat unfilled placeholder tokens as equivalent to an unverified claim — even when
the rest of the message is accurate and the gate discipline (awaiting an `in_progress` run) is correct.

A lane may blame mangled tokens on its DM channel ("the tool truncated my placeholders — see the
issue comment I posted"). The resolution is the same: resolve the vehicle by branch, and treat the
on-record issue/PR comment as the durable source it points at — read it with
`gh api repos/<o>/<r>/issues/<n>/comments`, but verify its sha/PR/base against the objects as in §6.
An on-record comment repeating the same wrong base ("base=current main `<new>`" while the head sits on
`<old>`) is still a claim; the branch point is `git merge-base`, not the comment.

## 7. Never guess a workflow filename

`gh run list --workflow <name>.yml` answers `HTTP 404: workflow ... not found on the default branch`
when the file is named differently — that 404 is a failed guess, not evidence the workflow is missing.
Discover names instead of assuming them:

```bash
gh run list -R <repo> --limit 30 --json workflowName,databaseId,conclusion,createdAt \
  --jq '.[]|select(.workflowName|test("<keyword>";"i"))'
gh run list -R <repo> --branch <branch> --json databaseId,workflowName,status,headSha
gh api "repos/<owner>/<repo>/actions/runs?head_sha=<sha>" --jq '.workflow_runs[]|.name'
```

An empty result from a `head_sha` query right after a push means the run is not yet registered, not that
none will start — re-read once before reporting "no CI". **But `head_sha=` can also return `total_count=0`
while the same head genuinely has a run** (the `--branch <b>` list shows `pending`/`in_progress` at that
exact sha). When the two disagree, the branch-scoped list is authoritative: measure deciding CI with
`gh run list --workflow <name>.yml --branch main -L 4 --json databaseId,status,conclusion,headSha`, and
only claim "no CI ever ran at this head" when the branch list agrees. A `pending` tip run is *not* a
`not-met` post-merge verdict — see §6j.

**jq: numeric fields need `tostring` before string-concat.** `--jq '"run="+.databaseId'` fails with
`cannot add: string ("run=") and number (41230501714)` because jq will not `+` a string and a number.
Cast every numeric field: `.databaseId|tostring`, `.id|tostring`, or interpolate with `"\(.id)"`.
This is the single most common reason a run-sweep one-liner dies mid-pass — write it with `\(...)`
interpolation from the start rather than `+` concatenation.

## 6j. A post-merge pass over a rapid owner approval batch

The owner can approve a chain of PRs within minutes, so `main` advances several merge commits between
your reads and any head remembered from a cron snapshot, a lane report or an earlier pass is stale by
construction. Verify each merge individually, then measure the true tip:

```bash
git fetch origin main
git log origin/main -1 --format='%H %s'           # the ONLY current tip
for pr in <a> <b> <c>; do
  gh pr view "$pr" -R <o>/<r> --json state,baseRefName,mergedBy,mergeCommit,author \
    --jq '"#\($pr) \(.state) base=\(.baseRefName) by=\(.mergedBy.login) mc=\(.mergeCommit.oid[0:8]) author=\(.author.login)"'
  gh api repos/<o>/<r>/pulls/$pr/reviews \
    --jq '[.[]|select(.state=="APPROVED")|.user.login+"/"+.author_association]|unique'
done
git merge-base --is-ancestor <merge-commit> origin/main    # every one must be YES (catches stacked PRs)
```

A genuine owner approval is an `APPROVED` review whose login **differs from the PR author** (every lane
pushes with the same shared token, so the author field proves nothing) with `author_association=OWNER`.
A merge without that pairing is an incident to report, never a convenience.

Cancelled main-CI runs are the normal signature of a merge batch, not a red verdict: each push to
`main` cancels the previous in-flight run (`cancel-in-progress`), so `completed/cancelled` at
descending heads is a chain. The deciding run is the one at the **true** tip — re-fetch, read the tip
sha, then that sha's run. Read status with `gh run view <id> --json status,conclusion`; `gh run watch`
blocks on the whole matrix and will blow a foreground timeout, so it cannot decide a pass. A run whose
`jobs` list is empty is queued/skipped, not failed. Never call `main` green from an intermediate head's
cancelled run, and never from a `pending` tip run. **Correspondingly, do not file the post-merge defect
issue while the deciding run is `pending`** — a red/green verdict is only owed once a run at the true tip
is `completed`; `pending`/`in_progress` is measured quiescence (a live gate to wait on), not a criterion
that failed. If a pass must end with the tip run still pending, report "main at `<sha>`, deciding run
`<id>` pending — not asserted green" and clear the pass on that measured state; do not fabricate an issue
nor mark it green.

Per-lane effect: a question you had in flight about a PR that has since merged is **moot** — post a
one-line relief on the issue/PR (vehicle merged, sha, timestamp) so the lane stops holding a dead
question, and do not spend a dispatch re-adding it.
