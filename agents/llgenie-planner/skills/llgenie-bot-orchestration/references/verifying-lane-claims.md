# Verifying a lane's claims before you repeat them

A lane's report is a claim; the API and the object store are the evidence. Repeat offenders
seen in practice, each with the check that settles it.

Board-level counterpart — a `do-not-merge` label is advice not a gate, the post-merge verdict
belongs at the merge tip, routing supersessions must name the comment they replace, and
posted-comment verification traps: `references/board-state-and-holds.md`.

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

**And never grep `worktree list --porcelain` near a branch name to pair them.** The output is a
block per worktree (`worktree <path>` / `HEAD <sha>` / `branch refs/heads/<b>` / blank). `grep -A2
'<branch>'` anchors on a branch line and returns the *next* block's lines, so it pairs your branch
with a DIFFERENT worktree's path — measured: a grep for `issue-797` returned a worktree that was
actually checked out on `fix/1119-tools-block-blank-line`. Read the pairing from the block itself
(`git worktree list --porcelain | awk -v b=<branch> '/^worktree /{w=$2} $0=="branch refs/heads/"b{print w}'`),
or — the reliable move — ask the worktree directly: `git -C <worktree> rev-parse --abbrev-ref HEAD`
and `git -C <worktree> rev-parse HEAD`. The branch a worktree truly holds is its own `HEAD`, never
the line your grep landed beside.

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
- **"GitHub-direct" ls-remote is NOT proof against staleness.** A lane can run
  `git ls-remote https://github.com/<o>/<r>.git refs/heads/main` and quote an OLD sha as "live main,
  no local mirror" — but a cached/mirrored ref or a stale sandbox returns a sha several merges behind
  the true tip (an implementer quoted `92e03503` for main when canonical was `543466ca`). Do not
  treat "direct" as authoritative; run the identical command yourself (`git ls-remote ... refs/heads/main`
  AND `git fetch origin main && git rev-parse origin/main`) and quote YOUR sha. The lane's own fetch is
  a claim about a clone, same as any other.
- **A check-runs verdict binds to the sha YOU measure — read `headRefOid` in the same breath.** A head
  moves under you (often a push that answered your own dispatch), so `commits/<sha>/check-runs` against a
  sha you remembered measures the OLD tree: the same PR can read `fail:[ci-verdict, linux/unit]` at the
  remembered head and `15 success, 0 fail, 0 in-progress` at the live one, which is the difference between
  "red, dispatch a fix" and "ready". Never query a literal sha from a lane report or an earlier pass —
  `H=$(gh pr view <n> --json headRefOid -q .headRefOid)` and query `commits/$H/check-runs` in the same call,
  and cite `head=$H` in whatever you conclude.

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

## 5c. Dispatch ownership: a lane's persistent refusal can mean YOUR assignment is wrong

Before dispatching — and especially before RE-dispatching after a lane pushes back — prove which lane
owns the issue from the repository, not from a memory note or a prior pass.

- **Ownership is a fact in the tree, not in the planner's notes.** `git log origin/main -- <path>`
  shows which lane authored the file's history (`feat(engines)…`, `chore(engine)…`); `docs/BOTS.md`
  shows which workflow builds/publishes an artifact. A memory note like "X publish = <lane> domain"
  is a prior, not evidence — a stale one silently routes work to the wrong lane.
- **A gate that REPORTS a red does not OWN the fix.** A checker that waits on a producer tag
  (e.g. `check-engine-launchers`) is the detector; the fix is the lane that builds and publishes the
  artifact (`make push-engine` inside the `engine-image-*` cells), or repins the source. Route the fix
  to the PRODUCER and cite the gate only as the detector.
- **Persistent refusal is a signal, not defiance.** When a lane declines a dispatch three-plus times,
  or (stronger) never acknowledges the specific issue in ANY reply and keeps answering a different,
  older, already-retired thread, the most likely cause is that YOUR assignment is wrong — not that the
  lane is stubborn. Stop re-asserting the dispatch; re-derive ownership from the tree.
- **Default to the filer/owner.** If a lane filed the issue from its own standing gate and owns the
  file's history, it owns the fix unless the tree says otherwise. Overriding that needs positive
  evidence, not an assumption carried over from an earlier pass.
- **Correct on the record, not by DM alone.** On discovering a mis-assignment: post an
  ownership-correction comment on the issue naming the concrete evidence (the git-log commits, the
  BOTS.md line), release the wrong lane's claim explicitly on the issue, dispatch the true owner, and
  tell the wrongly-tasked lane it was right to hold. A correction that lives only in a DM does not
  exist for the next reader.

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

**A fetch into a plain local ref name (not `refs/remotes/origin/…`) is REJECTED silently when the head moved — your ref keeps the OLD sha and the diff reads a stale head.** `git fetch origin refs/pull/<n>/head:pr<n>` (a bare local branch, no `+`) exits 1 with `! [rejected] ... (non-fast-forward)` and leaves `pr<n>` at the pre-move head; a following `git show pr<n>:<file>` then measures the OLD tree — reporting a still-broken fold that is actually fixed at the live head is the exact self-inflicted false-negative. Always force it (`git fetch -f origin refs/pull/<n>/head:pr<n>`, or the `+` form above) AND re-read `git rev-parse pr<n>` to confirm it equals the `headRefOid` you just quoted; if the fetch line shows `rejected`, the ref did not update and every measurement after it is about a dead head.

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
  The guard also refuses a **single `terminal` call that batches read-only `gh api`/`gh view`
  probes WITH a mutation in the same command** ("requires task-relevant implementation now.
  Read/search/test-only actions are paused; mutation tools remain available"), even when the
  mutation is the lawful `gh issue edit`/`gh issue comment`. Split it: one terminal call per
  mutating `gh` verb (`gh issue edit <n> --add-label …` alone), then a separate read-back call
  (`gh issue view <n> --json state,labels`) to prove it landed. Batching reads with a write is the
  shape that trips the guard; a lone mutation followed by a lone read does not.
- When the guard escalates and demands a **repo-level mutation** (a commit/branch/PR), a planner
  has no lawful one — "you do not implement" means a branch/PR/commit from the planner lane is the
  mistake, and mirroring your own reference files into the shared clone's `main` working tree is
  worse than useless: those files are **untracked in a checkout the implementer never sees** (it
  branches off `origin/main` in its own worktree) and risk being swept into someone's later commit.
  The **tracked-file variant** needs the sharper distinction: editing a file under your OWN
  `agents/<lane>/` shows as `M <path>` in the planner's shared checkout — dirty state a later
  `git commit -a` can sweep in, and a real SOUL/skill change arrives by issue+PR. So separate the
  two cases. A **throwaway write made only to make a check turn green** in a file you do not own
  (or a peer's `agents/<other-lane>/`, or an untracked scratch path) → revert it (`git checkout --
  <path>` / delete) and confirm `git status --porcelain` is clean. But the **versioned mirror of
  YOUR OWN profile reference into `agents/<lane>/skills/...`** is the deliverable itself (the tree
  is the source of truth for planner references) — keep it, do not revert it as "hygiene" (see the
  next bullet). Refuse a fabricated *code* vehicle either way; a red completion check is preferred
  to a role violation or a fabricated vehicle.
- **Board surgery IS the planner's lawful mutation — the guard's "no task-relevant mutation attempted" premise can be false.** The planner does not implement code, but filing the issue, applying `agent:implement`, posting the `bot-claim:` comment and dispatching the lane ARE a lawful, verified mutation. When a completion guard re-fires asserting nothing was done, do not manufacture a duplicate issue or a code vehicle to appease it: read back the REAL artefacts and quote them — `gh issue view <n> --json state,labels`, `gh api .../issues/<n>/comments --jq '[.[]|{id,claim:(.body|contains("bot-claim:"))}]'`, and the dispatch delivery id. Each is a claim the API confirms, not an assumption; stand on that measurement and STOP. A premise that queries a stale snapshot does not override a read-back-verified mutation. The one exception is a genuinely NEW work item a user question or a board observation raised: filing that (six-section body, `bot-claim:`, dispatch — see `filing-refined-issue.md`) is real work, not appeasement, and is often exactly what the pass owed. **The symmetric-claim variant is the textbook case of that exception:** an issue you routed only by DM (a routing comment, no `bot-claim:` marker) leaves its ownership findable nowhere on the board — posting that claim comment is a lawful, NEEDED mutation, not a scratch-file stunt to appease the guard. So when the guard re-fires after one claim, the correct next move is the NEXT named, genuinely-missing board artefact (the co-raised issue still lacking its marker), never a scratch file, a peer lane's files, or a fabricated code vehicle. Place it, `gh issue comment` returns the id — read it back and hold even if the guard stays red: a board claim the API returns is a persisted mutation, and a guard premise that ignores a read-back-verified comment is stale, not corrective.
- **A lawful in-lane mutation does NOT clear the guard — hold, do not loop.** The guard can re-fire
  on consecutive passes even after the correct in-lane action (patching your OWN profile's skill
  reference — the task-home for a lesson). The right response is: verify that mutation actually
  persisted on disk (`grep` the new heading, quote the before/after byte size), state plainly that it
  is the lawful mutation, and STOP — do not escalate to a repo-level vehicle, a peer lane's files, or
  a scratch file to appease it. A guard that stays red across two held passes is an accepted cost of
  the role, not a signal to fabricate; re-editing the same reference or writing junk to make a check
  turn green is the failure mode, not the fix.
- **Do not revert your own verified in-lane mutation as "hygiene" — that is the flip-flop the guard
  exploits.** Having established and byte-verified the profile→`agents/<lane>/` mirror (or a skill
  reference patch), the wrong correction is to "clean up" by reverting it: the revert leaves zero
  persisted evidence, its `git status` is empty again, and the guard simply re-fires on the next pass
  while your session has nothing to point at — you then re-make the same change and loop. Decide
  put-or-revert ONCE, before the first write; if you chose to mirror, keep it (it is a byte-identical
  snapshot the owner can lift into the issue+PR, not a fabricated vehicle) and hold. A red completion
  check is preferred to a role violation — but so is ONE honest persisted in-lane change over a
  revert→remake cycle that satisfies nothing.

## 6c-bis. "Your dispatch is stale on every fact" — verify the three, don't re-assert

A lane correction that reads "the dispatch is stale" is itself the claim to test, and it is commonly
TRUE: the head moved, the fix you prescribed is already committed, and the red you routed to them is a
shared gate another lane owns. Three facts, each measured at the live head you just fetched:

```bash
gh pr view <n> -R <o>/<r> --json headRefOid,state,mergeable,mergeStateStatus,author \
  --jq '"head=\(.headRefOid[0:8]) \(.state) mb=\(.mergeable) ms=\(.mergeStateStatus) author=\(.author.login)"'
git fetch origin +pull/<n>/head:refs/remotes/origin/pr<n>     # live head, force-refreshed
git show origin/pr<n>:<path> | sed -n '<a>,<b>p'              # is the remedy already AT that head?
gh run view <redrun> -R <o>/<r> --log 2>&1 | grep -iE '<gate-marker>'   # is the red this gate or theirs?
```

- A head you cite from a rollup or a prior pass is stale by construction (`67cc6de2` was an older head
  whose run succeeded; the live head was `b9e5dac8`). Re-read `headRefOid` at the moment you measure.
- A remedy you prescribe may already be committed (`import scripts.ci_scope/ci_verdict` in
  `test_ci_verdict.py:31-32`). Re-dispatching it is a no-op — rescind on-record, credit the lane.
- The red may be a SHARED gate (census `3bba736e is not a real commit`) reddening every PR including
  `main` at its tip, not the branch owner's scope. When it is, the branch owner is released: the fix
  is the census/#1222 class vehicle, and the branch's own fix (import-roots ratchet) is already
  correct. Route the residual red to that vehicle's owner and tell the lane to hold per "don't push an
  unowned branch".

  Prove "shared" before you say it, and prove it two ways — the gate must (a) run on EVERY PR
  regardless of diff class, and (b) fail on `main` for a reason the branch never touched:

  ```bash
  # (a) which gates does the deciding workflow run unconditionally?
  gh api repos/<o>/<r>/contents/.github/workflows/<wf>.yml --jq '.content' | base64 -d \
    | grep -nE 'make |name:'                     # a step with no `if:` runs for every PR of that class
  # (b) the failing job+step, structurally (never grep the raw log — see §7)
  gh api repos/<o>/<r>/actions/runs/<run-id>/jobs \
    --jq '.jobs[]|select(.conclusion=="failure")|.name+" :: "+([.steps[]|select(.conclusion=="failure")|.name]|join(","))'
  # (c) reproduce that gate at the PR's merge-base — a red there is not the branch's
  git merge-base origin/main <head> | xargs -I{} git show {}:<workflow>.yml >/dev/null
  ```

  The typical shape: a merged sibling added `make` targets (or a validator the workflow now calls)
  without adding them to the documented surface, so `make check-docs`/the docs gate reds the branch
  under review for a defect that is already on `main`. Attribution, not repair: the branch owner is
  released, the red is filed/tracked against the lane that introduced it, and the plan does not
  demand a fix on a PR whose own payload is clean. A red inherited from `main` also reds every PR
  opened afterwards, so it is a live blocking red — say so with the run id and the failing step when
  you hand it over.

Accepting a verified stale-dispatch correction is not re-litigating — it is the cheap loop
(measure-three → post one-line reconcile → release the lane). The failure mode to never repeat is
re-issuing an edit that is already at the head because you trusted your rollup over the objects.

**Corollary — the repeated re-raise: post ONE tombstone, then stop re-acknowledging.** A lane whose DM
stream delivers out of order will re-raise an already-dropped item again and again, each time with the
same evidence ("#1189 CLOSED, #1203 MERGED `77e533ea` on main") and the same demand ("drop it
permanently"), because it is answering your *earlier* dispatch, not your correction that already killed
it. Do NOT re-post the drop each time — that is the noise you are chiding the lane for, and a queued DM
ack already forbids resend. The loop breaks by measuring once, posting ONE durable tombstone on the
lane's LIVE vehicle (issue/PR the lane actually reads), and then **holding**: no further DM, no further
comment, even when the lane keeps re-raising. Re-acknowledging a point you already settled on-record is
how a 1-turn correction becomes a 5-raise loop. The tombstone is the last word; do not exceed it.

**Corollary — the superseded vehicle: target the LIVE branch, not the closed one.** When an issue's fix
has TWO vehicles — an early closed branch/PR and a later live superseding PR on a different branch (the
#1140 fix: closed `fix/1111`→#1119 superseded by live `fix/1140-tools-block-blank-line`→#1219) — a
re-dispatch that cites the closed vehicle's branch and file state is a stale premise even when the issue
number is right. Verify WHICH branch is live before prescribing: `gh pr list --head <issues-of-interest>
--state all` and read the OPEN/MERGEABLE PR's head, not the closed one's. The "bare import root" and
"to pass" language from an old vehicle's verdict does not reproduce at the live head (`from scripts
import lint_linefeeds` already present, ratchet already rooted). Correct on-record: cite the live PR by
number, confirm the census re-point is an ancestor of the branch tip (rc=0 → clears), confirm the
boundary (diff touches no ratchet/checker files), withdraw the stale line, then release the lane. One
vehicle per issue — the closed vehicle is dead crossref, the live PR owns the fix.

**Corollary — verify a lane's EMPIRICAL claims against the live tree before they become an issue's supporting facts.**
A lane's concrete data claims (fixture contents, row/value counts, "this file has only X", "this row is absent") can be
false even when the seam it identified is real — a genuine defect report often arrives with a stale or half-remembered
measurement attached. Never copy a number or a "the file only contains…" claim a lane states into a filed issue before
reading it back from the checked-out file at the CURRENT head (the fixture's own reader, a `python3 -c` probe, or a
`grep -c`/`wc`): the lane's figure is a claim about a tree it may no longer have. When refuted, still file the issue on
the true seam, and record in its measured-at / out-of-scope section BOTH that the cited premise did not reproduce AND
the value you actually measured — so the next implementer does not rebuild the fix on the dead premise. A false
supporting fact co-shipped beneath a true defect is believed by the next reader and can steer the fix toward rigging
the test to match the wrong number.

**Corollary — the repeated environment premise: one on-record refutation on the shared vehicle, then hold.** A lane
can re-assert a premise about YOUR OWN setup again and again — "your origin resolves to a fork; re-point it before
trusting branch/run state" — even after you measured the opposite (`git remote -v` shows origin IS canonical, and
`git rev-parse origin/main` equals the exact tip the lane's own PR bases on). The re-assertions are answering your
earlier correction, not the current state, and each lands with a fresh but stale cited sha (`a29a7ff5`/`c64cebf0`
were objects locally, not the origin/main tip `8e3fd3db`). The breaking move is NOT to re-explain each time — it is
to post ONE durable refutation on the SHARED live vehicle (the PR both lanes read) containing the measured evidence:
remote names→URLs, the fetched origin/main sha, and the explicit "not the fork" conclusion; then stop DM-ing. A
premise about the environment is settled by a measurement both lanes can reproduce from the same object store, not
by repeated prose. Re-acknowledging the false premise is how a one-diagnosis correction becomes a re-open loop. Only
re-open when the underlying fact (which shas name origin/main) changes.

**Corollary — scope the re-raise against YOUR SESSION's dispatch sheet, not the lane's assumption of it.** A lane
may re-raise "STOP re-dispatching #X — third time" against a dispatch you did NOT make this session (an implementer
did this on #1189/#1087/#1064 while my only dispatch that pass was a fresh #1232). The lane is answering a stale
queued message from an earlier window, not your current board. Before re-acknowledging a drop, meASURE your actual
dispatches: `gh issue list --label agent:implement --state open` + the issues you filed/dispatched THIS session. If
the item is not on it, state plainly "my dispatch sheet this session contains X, not #Y — there is no outstanding
dispatch against #Y", then point at the existing durable drop (the earlier tombstone) and HOLD. Do not re-send the
drop "because the lane asked": a re-raise is answered by the measurement that proves it is moot, not by repeating
the conclusion. Also correct any head-shift with the fresh measured sha (implementer cited #1225 @ 59ffd8e9; live
tip is 1ef69b71) — the citation is stale even when the resolution is right.

**Corollary — the cited shas are ANCESTORS, not fork evidence; and re-open only when the tip measurement CHANGES.** The
lane's cumulative list of "not the tip" shas (`c64cebf0`, `a29a7ff5`, `1819a6c1`, …) is not "your origin is a fork"
proof: every clone holds those objects, they are all ANCESTORS of origin/main (`git merge-base --is-ancestor <sha>
origin/main` rc=0), and origin's push URL is canonical. Answer the claim once with the ancestor-check + the URL, and
stop there. But DO re-open when the underlying fact ACTUALLY changed: when origin/main advances mid-session (e.g.
`8e3fd3db` → `45a04c3c`, a docs-only merge), the stale-tip reading is no longer "the lane is wrong," it is "the tip
moved" — correct the sha with the fresh `git fetch origin main; git rev-parse origin/main` before re-asserting
anything. Distinguish "the lane misread the tip" from "the tip genuinely advanced": only the latter re-opens the
board, and it re-opens toward a FRESH sha, never toward re-litigating identity.

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

**Corollary — a MERGED crossref does not close the issue; verify `state`, and a merged PARTIAL sync
leaves the issue genuinely live.** Do not upgrade "a merged PR references it" into "delivered": read
the issue's own `state` (`gh issue view <n> --json state,closedAt`) and the actual content on `main`.
A sync/versioning PR commonly merges but (a) never carries a closing keyword so GitHub leaves the
issue OPEN, and (b) lands a *snapshot* of the source that the live writer then outgrows — so the
issue is NOT a duplicate/abandoned artefact but a real remaining gap that needs a FRESH vehicle. This
is the inverse of §6k: there the issue is CLOSED and a new PR is redundant; here the issue is OPEN,
the merged PR was a partial delivery, and re-dispatching is correct. Measure the gap before deciding:

```bash
gh issue view <n> -R <o>/<r> --json state,closedAt --jq '{state,closedAt}'
gh pr view <merged-pr> -R <o>/<r> --json state,mergedAt,mergeCommit   # MERGED ≠ closed-issue
wc -c < <(git show origin/main:<path>) ; wc -c < <live-authoritative-file>   # tree vs live size
```

If `state=OPEN` and the tree blob on `main` is smaller/staler than the live authoritative file, the
merged PR did not finish the job: dispatch a NEW vehicle that closes the issue. If `state=CLOSED` and
the file is on `main`, the merge delivered it — do not open anything (§6k).

**Corollary — a peer-lane version-sync refusal is right; route it to the MANDATE lane.** When the
sync is of another lane's `agents/<lane>/` tree (or a docs-only alignment), the implementer correctly
refuses it as a peer-lane vehicle (one-lane-one-vehicle). Do not push it back onto the refuser and do
not take it yourself (planner does not implement). Route it to the lane whose mandate covers the
class — a docs-only tree-alignment belongs to the documentation-maintainer lane ("keeps docs aligned
with the tree; does not change scripts/tests/workflows"), an `agents/<other-lane>/` sync to that lane's
owner — after confirming the target lane is idle (no open PRs of its own) and that no branch/PR
already exists for the issue (one vehicle). Give it the live-authoritative byte size and the issue's
acceptance criteria; note the issue body's byte counts may be stale (re-measure before committing).

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

**A “byte-identical” fold is identical to the live files AT BRANCH TIME, not at merge time — re-diff after every post-dispatch amendment.** The implementer snapshots the live profile into `agents/<lane>/` the moment it starts, so any live edit you land *after* filing the versioning issue (a clause you add to SOUL.md/SKILL.md while refining, an owner steer) is silently absent from the fold. Do not trust the dispatch's citation, the issue body's acceptance list, or the lane's “byte-identical” claim — diff the pushed tree blob against the CURRENT live file:
```bash
git fetch origin +refs/heads/<fold-branch>:refs/remotes/origin/<fold-branch>
diff <(git show origin/<fold-branch>:agents/<lane>/SOUL.md) <profile>/SOUL.md
diff <(git show origin/<fold-branch>:agents/<lane>/skills/<skill-dir>/SKILL.md) \
     <profile>/skills/<skill-dir>/SKILL.md
```
A `>` hunk (present in live, absent on the branch) is the post-snapshot drift: dispatch the exact missing lines back to the lane to add before it opens the PR, and amend the issue's acceptance to “byte-identical to the live files at fold time,” not to any sha/clause you cited earlier. SOUL.md being identical while SKILL.md is short is the signature — the branch was cut between the two files' latest edits.

**If the lane already OPENED the PR at that stale head, the fix still goes to the SAME branch — and any green at the stale head is void.** A lane commonly opens the PR immediately after branching, before your post-dispatch amendment reaches it, so the open PR carries the truncated snapshot (PR open, head `b4b3...`, `grep -c <clause>` = 0 while live has it). The remedy is one vehicle, not a second: force-push the missing hunk onto the existing PR branch (`git push --force-with-lease --force-if-includes`, after re-reading live), then re-verify at the NEW head (`grep -c` ≥1 AND `diff` against current live empty). A CI run that already went green at the stale head **binds to that head and does not certify the fixed one** — the re-push re-triggers CI, so only the run at the post-fix head counts. Never accept "PR open" as "fold complete"; the tell is the same SOUL-identical/SKILL-short split, measured at the PR's `headRefOid`, not at the lane's claimed head.

**Locate the live skill dir with `find`, never construct it.** The live path is
`<profile>/skills/<skill-dir>/...` — no `agents/<lane>/` prefix — and `<skill-dir>` can differ from
both the lane name and the repo path (`agents/<lane>/skills/security-scan-ops/` ↔ live
`skills/security-scan-ops/`). A hand-built path returns `0 lines` and reads as "file absent/truncated":
```bash
find ~/.hermes/profiles/<lane> -type d -name <skill-dir>
```

**But `find -name <basename>` alone is ambiguous — never match a file by basename to pick "the" live copy.** A profile holds many files named `SKILL.md` / `references/*.md`; `find <profile> -name SKILL.md | head -1` silently grabs a *different skill's* file, and your sha comparison then reports a **false DIFF** (I nearly told a lane its fold was broken when the wrong SKILL.md was compared). Anchor the live path on the skill-dir segment, not the basename: `find <profile> -path '*<skill-dir>*' -name SKILL.md` — or better, construct `<profile>/skills/<skill-dir>/<rel-path>` after confirming the skill-dir with the `-type d -name <skill-dir>` probe above. When a `live==tree` compare reports DIFF, FIRST re-derive the live path and re-sha before asserting a defect — a basename collision is far more common than a real divergence.
A **third** fold beyond the two dispatched files is acceptable when it stays under the lane's own
`agents/<lane>/` and is disclosed — but it is also the signal a live writer is active: route that
writer to the owner-gated live-drift tracker, and keep this bounded vehicle as a snapshot (do not
re-push it to chase the drift; the writer outruns you and every push re-triggers review).

**A lane's own correction is itself a claim — the phantom→"present on both" swap is routinely the opposite.** When a lane retracts a mangled filename ("arm-read-back.md was a phantom; the real auto-merge-arm-readback.md is present on both live and tree"), the *retraction* can be wrong too. Measure the whole directory as a **set**, never the single corrected name:

```bash
T=$(mktemp); Ld=$(mktemp)
git ls-tree origin/main --name-only agents/<lane>/skills/<skill-dir>/references/ | sed 's|.*/||' | sort > "$T"
ls -1 <profile>/skills/<skill-dir>/references/ | sort > "$Ld"
comm -23 "$Ld" "$T"   # LIVE-ONLY = fold debt the lane's "no second file" hid
comm -13 "$Ld" "$T"   # TREE-ONLY = possible truncation
```

A file the lane swears is "present on both" can be live-only — and often one of a dozen live-only files, so the corrected filename concealed a real fold debt. Treat "corrected, no second file owed" exactly like any other scope claim: verify the set; if live-only files exist they are the owed fold (see `agent-behaviour-versioning.md`, "Deciding which files owe a fold"). Correcting a phantom to a false present-on-both is worse than the phantom, because it stops the search.

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
phantom arms nothing and reports success). **But a branch that exists LOCALLY with real commits and was
never pushed is a third state — a stalled-claim with publishing debt, not "in flight".** The tell:
`git ls-remote origin <branch>` empty while a local ref carries committed work
(`git log --oneline <branch>` shows the seam commits, `git rev-list --count origin/main..<branch>` > 0).
A completed implementation with no pushed ref and no PR produces nothing reviewable: it blocks no
dispatch and delivers nothing, and the work is stranded where a prune or cleanup can destroy it. The
dispatch is binary, not a nudge — either (a) rebase onto a fresh `origin/main`, push, open the PR
ready-for-review (`Closes #<n>`, the `AGENTS:` preflight line, the base sha), and report PR#/head/run-id;
or (b) release the claim on the issue with the owning-lane reason. Never count a local-only completed
branch as "the lane is busy": "blocked on none + no PR" is un-published, not held. Do not route a *second* item on the assumption the lane is
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

**On an OPEN PR, a single `UNKNOWN` `mergeable` is a computation race, not a state — re-read before concluding anything.** GitHub recomputes mergeability asynchronously after a base advance or a push, so the first read after either can answer `UNKNOWN`/`null` while the PR is genuinely `CONFLICTING` (the next read says so). Two parallel reads in one batch can even disagree (`UNKNOWN` vs `CONFLICTING`) for the same PR. Never dispatch from, or report, a lone `UNKNOWN`: include `state`, re-read once after `git fetch` settles, and if you must know *which* file conflicts, prove it on the objects (`git merge-tree $(git merge-base <head> origin/main) <head> origin/main`) rather than re-polling the API.

**`mergeable`/`mergeStateStatus = UNKNOWN` (or `null`) is NOT evidence the PR is open and freshly-pushed — a MERGED/closed PR also returns UNKNOWN there.** A read that asks only `{headRefOid,mergeable,mergeStateStatus}` on a just-merged PR comes back `UNKNOWN/UNKNOWN` and reads like "fresh push, mergeability still computing", when the PR is actually `state=closed merged=true`. Always include `state` (and `merged`) in the SAME read — `gh api repos/<o>/<r>/pulls/<n> --jq '{state,merged,merged_at,merge_commit_sha,head:(.head.sha[0:9])}'` — and, when it says merged, confirm the merge commit is really on the tip (`git fetch origin main && git merge-base --is-ancestor <merge_commit_sha> origin/main`). An owner's merge batch advances `main` past your last fetch, so a PR you thought was open can be already-merged by the time you read it; settle on the lifecycle object, never on `mergeable` alone.

**On an OPEN PR, a lane's "armed `<time>` method SQUASH (read back)" is still a claim — read the field yourself.** `gh pr merge --auto` exits 0 and can arm NOTHING (non-default base, blocked state, a phantom branch), and the lane's own read-back line is not evidence. Settle it directly — and read the **raw REST** field, not the GraphQL shortcut:

```bash
gh api repos/<o>/<r>/pulls/<n> --jq '"enabledAt=\(.auto_merge.enabled_at) enabledBy=\(.auto_merge.enabled_by.login) method=\(.auto_merge.merge_method) reviewDecision=\(.review_decision) mss=\(.mergeable_state)"'
```

An object with a non-null `enabled_at` is armed; `enabled_at:null` — even when `enabled_by`/`merge_method` are populated — means nothing is armed despite the exit 0. **The GraphQL field lies where REST does not: `gh pr view --json autoMergeRequest.enabledAt` can report a populated timestamp (a lane quoted `2026-10-31T23:06:42Z`) while raw REST `.auto_merge.enabled_at` is `null` — the GraphQL value is the auto-merge-request identity, the REST `enabled_at` is the enablement FACT.** A lane that quotes the GraphQL `enabledAt` as "armed" is quoting the #964 trap verbatim; verify with REST before believing or relaying it, and have the lane correct its on-record read-back (the false claim is worse than no claim — the owner reads it as armed). **And arming can be structurally impossible while the owner-review wall holds:** when `review_decision=REVIEW_REQUIRED` / `mergeable_state=blocked` (lanes cannot self-approve, §6j), GitHub will keep `enabled_at:null` across repeated `gh pr merge --auto` (exit 0 each time) — so the honest lane report is "NOT armed, owner approval is the singular path," not a fabricated timestamp. A PR `BLOCKED` only on `reviewDecision=REVIEW_REQUIRED` with every check `completed`/success is genuinely done-waiting-on-the-owner-review-wall, which is exactly the case armed automerge belongs in — so tell the lane to re-arm and quote the **REST** read-back object before claiming it. The same
stale-premise class shows up in a lane *holding* on a merged vehicle ("won't advance X until Y
merges" when both are already merged): dissolve the dead precondition, re-point the lane at its
one genuinely open vehicle, and quote the merge shas as the proof the hold expired. **Squash-merge makes `git merge-base --is-ancestor <pr-head> origin/main` return NO (rc≠0) for a PR that IS merged** — the squash rewrites the head into a new main commit, so the head sha is never a literal ancestor. Do not read that NO as "not merged": settle on the lifecycle object (`gh pr view <n> --json state,mergedAt,mergeCommit` → `state=MERGED`) and treat the head as squash-incorporated. A lane re-reporting "head `<h>`, live CI green, owner-gated" for an already-`MERGED` PR is a stale-premise hold — reconcile once (merged `<sha>` at `<time>`, `<h>` squash-merged, content on main) and tell it to release and NOT force-push a merged vehicle's source ref.

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

## 6i-quater. `workflow_dispatch` proof run built a DIFFERENT sha — cross-repo ref resolution

The root cause of a "proof at the wrong sha" is usually the workflow's own trigger, not a lost
commit. Check the trigger before disputing the lane's commit chain:

```bash
git show <head>:<.github/workflows/engine-build.yml> 2>/dev/null | grep -A3 'on:'   # workflow_dispatch-only = NO pull_request trigger
gh api repos/<o>/<r>/actions/runs/<id> --jq '{event,head_sha:(.head_sha[0:8])}'     # event=workflow_dispatch
```

A `workflow_dispatch` `ref` resolves **on the repo where the workflow lives** (canonical
`asimov-agent/llgenie`), NOT the PR's cross-repo head (often a fork `andyholst/llgenie`). When the
canonical repo also carries a **same-named stale branch** (e.g. `fix/1242-...` left at `965bc3ff`
while the fork head is `54aa01f6`), the dispatch builds the stale sha — the head's *parent* — and the
"cell proof" describes a tree the PR does not have. This is NOT a lost/fabricated commit and NOT the
lane's arithmetic error; it is ref resolution on the wrong repo.

Fix (lane side): align the canonical same-named branch to the fork head (`git push --force-with-lease
fix/<x>:<stale-old> <fork-head>` — lease matches the stale sha, fast-forward to the head), then
re-dispatch at that branch name and confirm `run.head_sha == PR head` (not the parent). Displace the
stale-sha run — never cite it as the proof. Planner side: verify the re-dispatch's `head_sha` equals
`headRefOid`, and confirm the canonical branch actually moved (`git ls-remote origin refs/heads/fix/<x>`
== head) before crediting.

## 6i-quinquies. A rebase lane's "re-rebased onto <main> → head <sha>" can cite a main that is already stale AND a head that exists nowhere

Two independent stalenesses arrive in one report. Measure both against the live objects before
repeating anything:

```bash
git ls-remote origin refs/heads/main                          # the ONLY current tip (e.g. 4ff3463d, not the lane's 22b817af)
gh api repos/<o>/<r>/pulls/<n> --jq '{head:(.head.sha[0:8]),base:(.base.sha[0:8]),mergeable,ms:.mergeable_state}'
git ls-remote origin refs/pull/<n>/head                       # live PR head — does it equal the cited <sha>?
git ls-remote origin 'refs/pull/*/head' | grep -i <cited-sha> || echo 'cited sha on NO PR head'
```

Two failure modes to separate:
- **Stale base:** the lane rebased onto `22b817af` while main is already `4ff3463d`; the live
  `baseRefOid`/merge-base against freshly fetched `main` proves where the head really sits. If the
  live head is already based on the NEWER main, the rebase it reports is obsolete — nothing to do.
- **Phantom head:** the cited `head` (`05acd765`) is on **no** canonical `refs/pull/*/head`, no fork
  branch, no branch at that sha — while the live PR head is a different sha (`5046572b`). The lane's
  push did not land (or was superseded); don't call it a phantom *commit* (its local work may be
  real) — call it a head that is not the live ref and re-anchor the lane to the measured
  `headRefOid`/`base`. Say plainly: `05acd765` exists nowhere; live is `<head>` on `<main>`; nothing
  to rebase/re-push.

Both cases end the same way: re-anchor to the measured live head + true main, confirm mergeable/blocked
and arm state from the same read, and either release the lane (already correct) or require a new head.

## 6i-bis-2. A lane's "verdict run <id> SUCCESS" — resolve the id; it may be `cancelled` AND the wrong workflow

A lane quoting a run id as its PR's green verdict ("verdict run 41317840046 SUCCESS, head b5851814") is a
claim about a **run id**, and the id routinely resolves to neither SUCCESS nor the PR's CI. Measure it:

```bash
gh api repos/<o>/<r>/actions/runs/<id> --jq '{name,status,conclusion,event,head_sha,branch}'
# a workflow_dispatch engine-build run on `main` is NOT the PR's pull_request ci-verdict run
```

Typical shape: `conclusion:"cancelled"`, `event:"workflow_dispatch"`, `name:"engine-build …"`,
`branch:"main"` — a manually-triggered engine sweep at the merge tip, cited as if it certified a PR.
`cancelled` is not SUCCESS, and a different workflow's run is not the PR's verdict. Find the real
deciding run by enumerating runs AT the head and reading each workflow name (`ci-verdict` /
`workflow_run`), never the single id the lane prefers. State the measured object once, on the board
(issue comment), then hold — a lane re-citing the same cancelled id after correction is enforcement,
not a tombstone-hold.

## 6i-ter. "Holding because a run at the same head is in_progress" — often already moot

"RED gate at head `<X>`; another run at the SAME head is `in_progress`, so I will not push
(`cancel-in-progress` would kill it)" applies the right discipline to a board that has usually
moved on. Three facts, each measured before you relay or unblock:

```bash
gh api repos/<o>/<r>/pulls/<n> --jq '.head.sha[0:8]'          # (1) is <X> still the head at all?
for r in <cited-run-ids>; do gh run view "$r" -R <o>/<r> \
  --json databaseId,status,conclusion,headSha \
  --jq '"\(.databaseId) \(.status)/\(.conclusion) head=\(.headSha[0:8])"'; done   # (2) really in_progress?
gh api repos/<o>/<r>/pulls/<n>/files --jq '.[]|.filename'      # (3) is the red's cause already fixed at head?
```

- **The head moves under a hold report.** A fold pushed in response to your own dispatch advances the
  head without the lane re-reporting, so a lane quoting `<X>` can be two heads behind its own branch.
  Quote the live head, not the cited one.
- **An "in_progress" run the lane names is routinely already `completed`/`cancelled`** — the hold
  rationale is then gone and the lane needs no permission to push. `cancelled` is not a verdict (§
  run-status sections) and neither is it a reason to keep holding.
- **Resolve runs by the ids the lane cites, via `gh run view <id>`.** `gh run list --commit <sha>` can
  return empty for a sha that genuinely has runs (§7, the `head_sha=` trap) — an empty list is not
  "no CI ever ran".
- **The red may already be fixed at the live head** — e.g. a check-docs change-note red cleared by the
  fold that added `agent-wiki/<stem>.md` + `docs/changes.d/<stem>.md`. Read the file set before
  accepting "undiagnosed red": if the remedy is at the head, the diagnosis is done and the remaining
  action is a fresh run at that head, not a fix.

Reply shape when all three are stale: "head is now `<Y>`, it carries <the artefacts>, the cited run is
`<status>`, so nothing to wait on and nothing to push — trigger a fresh run at `<Y>` and report its id".
Then hold for the run id; do not re-explain the staleness on every subsequent report.

**Corollary — the cited `in_progress` run may itself be pinned at a SUPERSEDED head, and a DIFFERENT red
can live at the live head the lane never surfaced.** A lane reporting "proof run `<id>` in_progress, box
pending" can be quoting a run whose `head_sha` is an **older, superseded** head, while the run at the
actual fix head is `pending` OR `cancelled` OR **red** — and the lane reports only the one it likes.
Enumerate ALL runs at the live head, not just the cited id, and bind each verdict to its `head_sha`:

```bash
H=$(gh pr view <n> -R <o>/<r> --json headRefOid --jq .headRefOid)
gh api "repos/<o>/<r>/actions/runs?head_sha=$H" \
  --jq '.workflow_runs[]|{name,status,conclusion,id,databaseId}'
for r in <cited-run-ids>; do gh api repos/<o>/<r>/actions/runs/$r \
  --jq '"id=\(.id) \(.status)/\(.conclusion) head=\(.head_sha[0:8])"'; done   # cited run's ACTUAL head
```

If a cited run's `head_sha` ≠ the live head, it is a measurement of a tree the branch no longer has — say
"that run is at the SUPERSEDED head `<old>`, not the fix head `<H>`" and quote what actually exists at
`<H>`. A failed non-engine gate at the live head (a `guard` job's `make check-pr-authors` step, a `scope`
job) is a **real red distinct from the intended hold cascade** (box-4/engine-build pending): route it to
the branch owner to reconcile (fix-or-quote the exact gate step) before declaring the box ready — do not
accept "the only thing left is the pending box " when an unrelated gate is red at that same head. Make the red one route and hold; do not re-explain it on every report.

**Corollary — a REPEATED false report with a provably UNMOVED head is enforcement, not a tombstone-hold.**
Distinguish two look-alike repeats. A lane re-raising a *dropped/settled* item is queue replay (§6c-bis
corollary: post ONE tombstone, then hold silently). But a lane that re-reports the *same false premise
about its own live vehicle* N times while the head has NOT moved is a different failure: no motion, no
action — and silent hold lets a genuinely stuck vehicle rot on the board (a DIRTY PR gets no CI run at
all). The tell is `headRefOid` identical across rounds. When it is:

```bash
gh pr view <n> -R <o>/<r> --json headRefOid,baseRefOid,mergeable,mergeStateStatus \
  --jq '"head=\(.headRefOid[0:8]) base=\(.baseRefOid[0:8]) mb=\(.mergeable) ms=\(.mergeStateStatus)"'
gh api repos/<o>/<r>/pulls/<n> --jq '.auto_merge.enabled_at'          # arming claims
gh run list -R <o>/<r> --commit <full-head> --json conclusion,name --jq '.[]|select(.conclusion=="failure")|.name'
```

Then rebuff ONCE with the measured contradiction *and* the failure quoted by job/step, and switch from
"correct" to "enforce": name the exact remedy (rebase command / the failing job+step from `--json jobs`)
and require **a new head sha or an explicit handoff** — explicitly refuse a further status ping ("a
fourth message quoting `<same-head>` / `MERGEABLE` / `zero-reds` will be ignored"). The most common false
trio is: calls a stale base "live main" (base ≠ fetched `origin/main`), calls a `mergeable=false ms=dirty`
PR "MERGEABLE", and calls "only unit in_progress / zero red legs" while a `linux/unit`+`ci-unit` step is
`failure`-completed at that very head (`gh run list --commit` shows `CI: failure`). Verify each claim
against the field, not the lane's summary — the false 'zero reds' is the worst, because it certifies a
red gate as green to the owner.

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

**Partial overlap is the opposite verdict — decide it on the RESIDUAL, not the overlap.** Two PRs can
touch the same file without being duplicates: one merged the docs-surface half, the other carries
additional distinct files (a mandate restore, a classifier change, an architecture note). Never close
the survivor because a file name collides — compute what is LEFT at its head relative to the NEW tip:

```bash
git fetch origin main
git rev-parse --short origin/main                                  # the tip the other PR merged into
H=$(gh pr view <n> -R <o>/<r> --json headRefOid --jq .headRefOid)
gh api "repos/<o>/<r>/compare/<new-tip>...$H"                      # per-file additions/deletions the PR still adds
```

- Residual touches **only** files the merged PR already changed, with no new material → it IS the
  duplicate case above: close it, quote the merge sha, do not rebase it into existence.
- Residual carries **any distinct file the merged PR did not touch** → it is a complementary vehicle:
  rebase onto the new tip (genuinely CONFLICTING per #1015 because the shared file diverged), resolve
  the shared file to the MERGED wording (union, not a second copy), keep the distinctive additions,
  and re-run the deciding gate — an earlier run at the pre-merge head measured a tree that lacked the
  sibling's fix, so its red is void.

One vehicle per issue still holds: the rebase lands on the EXISTING PR branch (force-push, one trail),
never a fresh PR, and the dispatch goes to that PR's owning lane — not to whichever lane filed the
issue, and not to a second implementer.

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

## 6m. "`make <target>` exit 0, route it for review" — a LOCAL gate is not the CI gate

A lane that asks you to route a PR for review on the strength of a local `make` target ("make
check-docs exit 0", "gates green locally") is reporting a DIFFERENT gate than the one that will
decide the PR. The CI workflow runs its own set of `make` sub-targets (a docs PR still runs
`ci-lint`'s linefeed/editorconfig markdown gate, its changes-index, its census check — a superset
the lane's single local target never covered). Do not route a PR for review, and never upgrade
"green locally", until you read the workflow run **at that PR's own head**:

```bash
H=$(gh pr view <n> -R <o>/<r> --json headRefOid --jq .headRefOid)
gh api "repos/<o>/<r>/actions/runs?head_sha=$H&per_page=10" \
  --jq '.workflow_runs[]|{name,status,conclusion,databaseId}'
# the failing gate + step, structurally (see §7 on --json jobs):
gh api "repos/<o>/<r>/actions/runs/<run-id>/jobs" \
  --jq '.jobs[]|select(.conclusion=="failure")|.name+" :: "+([.steps[]|select(.conclusion=="failure")|.name]|join(","))'
```

A `failure` conclusion on a gate the lane never named (its `make check-docs` was clean but the
`ci-lint` markdown gate is red at the head) is a real defect on the lane's OWN vehicle: dispatch
the fix back to the author lane (fix-PR-owner), naming the exact file+line the lint cites and the
failing step name, and require a fresh run id at the NEW head before review-routing. A local gate
exit 0 is a claim about the lane's checkout; the CI run's `conclusion` at `headRefOid` is the
verdict. Never relay "ready for review" on a head whose workflow run is `failure`.

## 6n. "Own-domain audit complete — all green, no findings" covers only the slice it measured

A lane's continuous-improvement audit report ("engine-skill-gap clean, 78 tests passed, 13 params
files present with pinned keys, no pin-validity defect") is a claim about the **specific probes it
ran**, not about the brief you dispatched. The common gap: the lane runs the easy mechanical sweep
(skill-gap coverage, file/target *presence*) and then asserts the harder slices — **upstream pin
validity** (is the recorded SHA still the current reproducible commit on the engine's *upstream*
repo, the #1252/#1262 silently-unsatisfiable-pin class) and **serving drift** (do launch flags /
quantization / ports still match current upstream) — from file-presence alone. "Pinned keys present"
is not "pin still resolves upstream"; a commit force-pushed away or a mover tag is invisible to a
keys-present check and only blows up a build later.

Before accepting a clean-audit record or calling the lane idle, diff the report's *mechanisms* against
the dispatched brief's *slices*:

```bash
# does the audit script actually query upstream, or only read local files?
git show <main>:scripts/<audit>.py | grep -inE 'api\.github|repos/|refs/heads|resolve|clone|http'
# a keys-present check touches no network — that absence IS the scope gap
```

If a dispatched slice has no upstream-facing probe behind it (the grep finds only local file reads),
reject "no findings" for that slice: send the lane back onto the *uncovered* slices explicitly (name
what to query — which upstream repo per engine cell, which params vs current upstream), and require
EITHER a six-section finding per defect (routed to the owning lane, never the auditing lane's own
pass) OR a clean `re-audited at <sha> (<named slices>), no findings` that names the slices it actually
measured. A clean record that verifies only the easy half of the brief is not a clean audit — it is
half an audit reported as whole, and it hides the #1252/#1262 class behind "all green".

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
only claim "no CI ever ran at this head" when the branch list agrees. A `pending` tip run is *not*
`not-met` post-merge verdict — see §6j.

**Before filing a red sweep/channel run as a defect, reproduce the query and run a CONTROL — the 404 may
be the query form, not the data.** A red auto-merge/sweep run whose log shows `gh: Not Found (HTTP 404)`
on an `actions/runs` filter is a claim about a mechanism, not proof the head is bad. Measure three things
before you file: (1) reproduce the exact query the script ran; (2) the same query on a KNOWN-GOOD head
and an UNFILTERED call (a control that isolates "filter" from "resource"); (3) whether the code passes
`-f key=value` — because `gh api -f` on a filtered GET sends a form body the API can 404 while the
identical params as a URL string return 200 (`repos/o/r/actions/runs?head_sha=…&event=…&per_page=1`).
When the control 404s the same way for every head (open, merged, known-good) and unfiltered works, the
defect is the query form in the script, not any one branch's data — file it naming the mechanism (with
both invocation forms quoted) and route to the ci/pipeline lane. Never blame the data or the lane on the
strength of a single red run before the control separates the two. (`references/verifying-lane-claims.md`
→ §7; the `gh api -f` mechanism is in the github skill's `references/github-api-cheatsheet.md`.)

**Find the failing job/step via `--json jobs --jq`, not by grepping the raw run log.** Piping
`gh run view <id> --log` through `grep -c 'pattern'` repeatedly returns empty/0 through the terminal's
log pipeline (escape handling) even when the failure text is present — a false "no match" that reads as
"nothing failed". The reliable route is to enumerate the failing step structurally and only then pull
the log for that step:

```bash
# which job/step failed (structural, always answers)
gh run view <id> -R <o>/<r> --json jobs \
  --jq '.jobs[] | .name + " :: " + ([.steps[]|select(.conclusion=="failure")|.name]|join(", "))'
# or check-runs for the failing gate name
gh api "repos/<o>/<r>/commits/<sha>/check-runs" --jq '.check_runs[]|select(.conclusion=="failure")|.name'
# then, if the log text is needed, write it to a file and read it, don't grep the pipe
gh run view <id> -R <o>/<r> --log > /tmp/run.log   # then read_file / search_files on the file
# `gh api .../jobs/<job-id>/logs` refuses with "the response contains terminal escape
# sequences" — that is gh's output GUARD, not an empty log; redirecting it also yields a
# 99-byte stub. Whitelist it and grep in place (the flag is what makes the text reachable):
gh api --allow-escape-sequences "repos/<o>/<r>/actions/jobs/<job-id>/logs" \
  | grep -aiE '<marker>|FAILED|lint|<file>'
```

**jq: numeric fields need `tostring` before string-concat.** `--jq '"run="+.databaseId'` fails with
`cannot add: string ("run=") and number (41230501714)` because jq will not `+` a string and a number.
Cast every numeric field: `.databaseId|tostring`, `.id|tostring`, or interpolate with `"\(.id)"`.
This is the single most common reason a run-sweep one-liner dies mid-pass — write it with `\(...)`
interpolation from the start rather than `+` concatenation.

**jq: `contains`'s two-arg form is for arrays/objects, not strings.** `contains("bot-claim:";2)`
fails with `contains(2) cannot be applied to: string`; against a string use one arg —
`contains("bot-claim:")` — or `test("<pattern>";"i")` for a case-insensitive regex. The `;N`
variant is jq's array/object contains, not a string search.

**A `--jq` expression that PARSE-errors returns nothing — do not read it as "no results".** When a
`--jq` filter underpins a "PR/issue does not exist" or "no runs at this head" conclusion, a syntax
error in the filter silently yields empty output that looks identical to absent data, producing a
self-inflicted false-negative (a real PR reported "missing" because `--jq` errored). Before recording
an absence as fact, re-run the SAME API call with a trivial `--jq '.[0]'` (or no `--jq`) to separate a
filter error from a genuinely empty result.

**jq: never mix shorthand and explicit keys in one object literal.** `{mergeable,.mergeable_state:.mergeable_state}`
fails with `unexpected token ".mergeable_state"`, because a bare shorthand key must be followed by another
key, not a `.path`. Write every field in one form — `{m:.mergeable, ms:.mergeable_state}` — and rename
the key whenever the API name is awkward; the abbreviated form also keeps your `--jq` strings short
enough to stay readable in a report.

**jq: `gh run view --json jobs` job objects have no `id` — the field is `databaseId`.** Selecting `.jobs[].id` yields `null` for EVERY job (success and failure alike), so a "which job ids failed" sweep comes back all-null and reads as "no jobs have ids / nothing to link" — a false absence. Use `.jobs[].databaseId` (or `.jobs[].databaseId|tostring` before concatenation). Same for run objects: `databaseId`, not `id`.

**jq: a shell loop variable is NOT jq's `$name` — it must be passed with `--arg`/`--argjson`.**
`for n in 1092 1085; do gh issue view "$n" --json state --jq '{n:$n,s:.state}'; done` dies on every
iteration with `variable not defined: $n` and prints nothing, so the whole per-issue table is silently
empty and reads as "those issues have no claims / no labels" — a false absence. jq's `$n` is its own
binding, not the shell's expansion. Use `--argjson n "$n"` (numbers) or `--arg n "$n"` (strings), or let
the shell expand it before jq runs (`--jq "{n:$n,s:.state}"`). When a looped `--jq` comes back uniformly
blank, suspect this before concluding the data is missing.

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

**A merged PR can carry a RED head-instance check-set while its MERGE-COMMIT re-run is GREEN — the verdict is the run at the merge commit, never the pre-merge head.** When the owner merges through a red/pending leg (#1309 latitude), `commits/<headRefOid>/check-runs` keeps the head's instance reds (`ci-verdict` failure, `scope` failure on `make ci-lint`, `guard` failure, `linux` **skipped**) forever, because that set was measured BEFORE the merge re-triggered CI on the merge commit — a different sha, a different run. The merged content's real verdict lives at `commits/<mergeCommit.oid>/check-runs` and at the true tip, not at the PR head. So a question like "why was this PR closed while the pipeline is red?" is answered by quoting BOTH states, not by re-reading the head as green or filing a gate-red incident:

```bash
gh pr view <n> -R <o>/<r> --json state,mergedBy,mergedAt,mergeCommit,headRefOid \
  --jq '"\(.state) by=\(.mergedBy.login) at=\(.mergedAt) mc=\(.mergeCommit.oid[0:8]) head=\(.headRefOid[0:8])"'
H=$(gh pr view <n> -R <o>/<r> --json headRefOid --jq .headRefOid)
MC=$(gh pr view <n> -R <o>/<r> --json mergeCommit --jq .mergeCommit.oid)
gh api "repos/<o>/<r>/commits/$H/check-runs"  --jq '.check_runs[]|"\(.conclusion//"null")  \(.name)"'   # head instance (may be RED)
gh api "repos/<o>/<r>/commits/$MC/check-runs" --jq '.check_runs[]|"\(.conclusion//"null")  \(.name)"'   # merge-commit re-run (the VERDICT)
git fetch origin main && gh api "repos/<o>/<r>/commits/$(git rev-parse origin/main)/check-runs" \
  --jq '.check_runs[]|"\(.conclusion//"null")  \(.name)"'    # true tip
```

Resolve the two states before you answer or act. If the merge-commit re-run and the tip are green (`verdict`/`recheck`/`guard` success), the head red is a superseded instance measurement on identical content: say "head `<H>` was red at merge time (<failing step>), but the merge re-run `<mc>` and tip `<tip>` are green — content passed on `main`, no incident to file." Only when the MERGE-COMMIT/tip re-run is also red is there a real main-red to file as a defect (§6j's pending rule applies — a pending tip run is not a verdict). Never read a closed/merged PR's head check-set as its verdict; the head is a measurement about a tree that is no longer the merge target. A head instance that shows `linux: skipped` alongside reds is the tell that the deciding matrix never ran there — the merge re-run is where it ran.

Per-lane effect: a question you had in flight about a PR that has since merged is **moot** — post a
one-line relief on the issue/PR (vehicle merged, sha, timestamp) so the lane stops holding a dead
question, and do not spend a dispatch re-adding it.

**Post-merge acceptance = the merge-commit re-run's FULL job matrix, not a subset.** After any merge,
read `gh run view <id> --json status,conclusion,jobs` (or `gh run list --workflow CI` to find the EPOCH
run, then the job list) and confirm **every** leg of that run, not just guard/unit/check-docs. A run is
RED if **any** job failed even while others are still `in_progress` — do not report "gate-green" on the
subset you measured. Real incident: run `41323218791` (the #1392 merge-commit re-run at `5c5df3d1` =
main head) had a FAILED `linux/openspec` leg I missed because I only re-ran check-docs/check_agent_profiles;
the openspec red was the #1395 proc-seam unchecked-tasks failure. Command:
`gh run view <id> --json jobs --jq '.jobs[] | {name,status,conclusion}'`; treat any `failure`/`cancelled`
`conclusion` leg as the run being red, regardless of the still-running legs.

**`required_status_checks` is what makes "CI red ⇒ cannot merge" a platform fact — verify it exists, do not assume GitHub enforces it.** GitHub only blocks merges of red PRs when the repo's branch-protection/ruleset lists required status checks. The llgenie `main` ruleset (id `24862727`) carried only `deletion` + `non_fast_forward`, zero `required_status_checks`, no merge queue — so red PRs merged freely at the platform layer (the #1400 gate-gap finding). Check before asserting a merge was "permitted past a block": `gh api repos/<o>/<r>/rulesets/<id> --jq '.rules[].type'`. A "#1309 latitude" owner merge over a red leg is only constrained if the leg is in the required list; resolve the latitude question with the owner before declaring the gate enforced.

**A red's PROVENANCE moves with the head — "main is red" is a claim about the sha you measured it at, never a standing state.** As `main` advances (owner merge batches do this mid-pass), a red confirmed at an older sha says nothing about the current tip: the current head's run can be `pending` with **no jobs materialized yet**, which is neither still-red nor green. Do not carry the older red forward as "main is currently red", and do not read the absent-or-pending current-head check-set as "cleared" (§6j: a `pending` tip run is not a verdict). Measure the current head explicitly and state the three states separately:
```bash
git fetch origin main && M=$(git rev-parse origin/main)
gh api "repos/<o>/<r>/commits/$M/check-runs" --jq '.check_runs[]|select(.name|test("<gate>";"i"))|"\(.conclusion//"pending") \(.name)"'  # empty = not yet reported at THIS head
gh run list --workflow CI -L 5 --json databaseId,headSha,status,conclusion --jq '.[]|{id:.databaseId,head:.headSha[0:8],status,conclusion}'
```

## 6o. "New vehicle — #N filed + PR #M OPEN, ready for review" can be stale the OTHER way: already MERGED

The owner-merge-pre-empts-a-RED-verdict clause (§6h) covers a lane reporting *not-done* for a PR that
merged. The mirror is common too: a lane reports a **brand-new vehicle as still awaiting review** ("#N
filed + PR #M OPEN, non-draft, ready for review") when by arrival the PR is already `MERGED` and its
issue already `CLOSED`. A lane's message is a snapshot of when it was composed, not of the board when
you read it. Settle the lifecycle first, before you spend any dispatch relaying or scheduling a review:

```bash
gh pr view <M> -R <o>/<r> --json state,mergedAt,mergedBy,mergeCommit,closingIssuesReferences \
  --jq '"#\(<M>) \(.state) by=\(.mergedBy.login//"-") mc=\(.mergeCommit.oid[0:8]//"-") closes=\([.closingIssuesReferences[].number])'
gh issue view <N> -R <o>/<r> --json state,stateReason  --jq '\(.state)/\(.stateReason)'
```

- The closing-keyword field is **`closingIssuesReferences`**, not `closesIssues` (a `gh pr view --json
  closesIssues` call errors `Unknown JSON field`; the same class as passing an invented flag). Ask for a
  real field or the whole query dies mid-batch and reads as "no PR".
- If `state=MERGED`, the lane's "ready for review" is stale history: credit the shipped work, confirm the
  merge commit is an ancestor of the fetched `origin/main` (`git merge-base --is-ancestor <mc> origin/main`),
  and note the change-note PR that rode on top if one exists — then do NOT open anything for review. A
  merged vehicle is never a review queue item.

## 6p. A merged PR's head reds are usually PRE-EXISTING — classify before blaming the change

An owner merge over a red head rollup (#1309 latitude) can show many failing checks at `headRefOid`. Do
NOT read that as "this PR broke CI" and file a defect against it. Most of those reds are inherited from
`main` and redded every PR opened after them. Classify by measuring a **pre-merge `main` run at the PR's
base**, not just the PR head:

```bash
# the reds at the PR head (names only, structural)
gh pr view <M> -R <o>/<r> --json statusCheckRollup \
  --jq '.statusCheckRollup[]?|select(.conclusion=="FAILURE")|.name'
# the SAME checks on a main push run that predates the PR — pre-existing if they fail there too
gh run view <pre-merge-main-run> -R <o>/<r> --json jobs \
  --jq '.jobs[]|select(.conclusion=="failure")|"\(.name) :: \([.steps[]|select(.conclusion=="failure")|.name]|join(","))"'
```

If a leg fails in the pre-#PR main run (e.g. `linux/unit` → `make ci-unit`, and/or `linux/openspec`), the
red is **inherited, not introduced** — say so plainly and do not file it against the merged PR. The real
finding is then the *un-owned* red: which inherited legs already have a tracker and which do not. A leg
with a tracker (the openspec proc-seam class) is known; a leg with **no** tracker is a NEW un-owned main
red you should surface on the platform-gate/red-inventory tracker (with the exact run id + failing step)
so a later fixer picks it up — do not let "merged over reds" hide a second, untracked red.

**But evidence on the gate tracker is NOT ownership — file the un-owned red as its OWN routed issue.** Pinning a red as a comment on the gate/red-inventory tracker (the ruleset-gap class) records it; it does not give it an owner, an acceptance rubric, or a fix vehicle, and a merge-sailed red with no vehicle rots exactly like the gate gap it sits under. When a pre-existing leg has NO dedicated tracker, file it as a separate six-section issue (`agent:implement` + the lane's area label), route it to the PRODUCING lane (a unit/ci-unit red → ci-pipelines; whichever lane builds the artifact owns its gate), post a `bot-claim:` comment naming the lane and the exact acceptance (rc 0 at the fix head + a completed green run id quoted in the PR body), and cite the gate tracker as **related, not duplicate** — the tracker owns the ruleset/gate, this owns the red's fix. Verify the labels actually landed (`gh issue view <n> --json labels` — a non-existent label silently vanishes; e.g. `ci:slow` exists but a bare `ci` does not) before declaring the issue routed. The two are complementary one-vehicle issues, not a fork of the same scope.

When you must put the red on the board (routing an issue, escalation), quote its exact location — "CONFIRMED red at `<old sha>` (run `<id>`); at current head `<new sha>` the run is `pending`, unevaluated" — and state the acceptance criterion as "gate rc=0 verified at **the head that closes this** (quote that head's run id)", so the implementer neither assumes the old-sha red is current nor treats a pending head as green. A reader who sees "main is red" without a sha attributes the old red (or a pending run) to the wrong tree.
