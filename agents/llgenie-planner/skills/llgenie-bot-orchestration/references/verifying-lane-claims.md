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
observation (no push, no cancel, no re-arm) on a PR whose `state` you have not read. The same
stale-premise class shows up in a lane *holding* on a merged vehicle ("won't advance X until Y
merges" when both are already merged): dissolve the dead precondition, re-point the lane at its
one genuinely open vehicle, and quote the merge shas as the proof the hold expired.

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
none will start — re-read once before reporting "no CI".
