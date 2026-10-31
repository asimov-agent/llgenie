# Verifying PR state before you believe or dispatch

Every rule here exists because a lane (including the planner) acted on a flag that had outlived what it described.

## `state` and `mergedAt` go beside every status claim

`cross=true`, `DIRTY`, `CONFLICTING`, `BLOCKED` all **survive a merge** and keep reading like live verdicts. A briefing that says "re-cut this fork head, it's dirty" can therefore describe a PR that merged an hour ago.

```
gh pr view <n> --json state,mergedAt,mergeCommit,baseRefName,headRefOid
```

- **A branch behind `main` is not a branch needing a re-cut** — it is a branch whose work already landed. Proof: `git merge-base --is-ancestor <mergeCommit> origin/main` and `git diff --stat <oldHead> origin/main` (a five-thousand-line deletion count means the "conflict" is a superseded head, not a conflict).
- Two PRs tonight were re-cut conversations away from producing a PR that only deletes work.

## Arming a stacked PR is a merge, not an arm

`gh pr merge <n> --auto` on a PR whose base is not the default branch has **no required checks to wait for**, so it merges within seconds into another lane's branch. Two instances eight minutes apart (#958, #954); the second was later erased when the base branch was rewritten, so the merge appeared in no history.

- Arm only on a base of `main`. A stacked PR states `auto=none (stacked base: arms into <base>)` and arms on retarget.
- `autoMergeRequest` is **cleared when a PR merges**, so a null read-back proves *merged*, not *not-armed*: read `state` first.

## A count is not a content check

`16 bullets == 16 bullets` passed a SOUL that paraphrased four rules. Compare the whole text:

```
blk = re.search(r"```\n(## Standing rules.*?)\n```", issue_body, re.S).group(1).strip()
assert blk in soul            # and: for each rule, occurrences == 1 (a second copy drifts)
```

Duplicate the canonical text anywhere — a numbered list below the fence is enough — and the copies diverge on punctuation, then on substance.

The **superset check wears the same trap**: a tree-vs-live profile gate that asserts `tree ⊇ live` (no live line would be lost) reports OK on a tree SOUL carrying *duplicated* canonical rules — superset is the right rule for a list, the wrong rule for a canonical text. "It is a superset, so nothing to deliberate" is how a duplicated rule survives review; the content check (fence verbatim, occurrences == 1) must be asserted independently of the drift check, and a tree that is "a superset" of a deduped live file deserves a diff, not a pass.

**The content check needs the canonical the GATE actually reads.** A `block in soul` verdict is only as good as the canon it compares against. When a canonical is duplicated — a fenced block in an issue body AND the checked-in file the checker's `fleet_block()` reads from — they drift on wording, and comparing against the wrong copy gives a false verdict in BOTH directions: a SOUL that matches the checked-in file but not the issue fence reads "block in soul False" when the gate would pass it, and vice versa. Before trusting a missing/duplicated verdict, read the checker's code for which source it reads (the constant the gate imports, not the one a doc tells you to copy), compare against THAT, and treat two differing authorities as a defect to file (pick ONE), not a reason to re-take the SOUL.

**Replicate the gate's exact functions, including its STRING ANCHORS, from the checker file — never reconstruct them from memory.** "I ran the same compare" with a guessed section heading (e.g. `## Standing rules`) is not the gate's compare when the checker splits on `## Standing rules (fleet, learned 2026-10-28)`. The wrong anchor silently changes the extracted block (a couple lines and bytes), flips `MATCH` True→False, and starts a three-way argument where your measured FALSE is your own artifact and the lane quoting TRUE is right. Before arguing a gate verdict, `base64`-decode the checker's source at the head and copy its heading constant, its split separators, and its `fleet_block()` extraction verbatim into the probe. A shipped wrong `FALSE` is worse than a slow probe.

**A measurement is only about the ref you read — do not generalise it to a PR.** A fix carried on a STACKED branch (e.g. a SOUL dedupe on the child) is not in the PARENT PR's tree until the child actually lands on it. Two lanes can therefore measure the same page number and get one `MATCH TRUE` (child's fixed branch) and one `MATCH FALSE` (parent's tree still carrying the retired bullet) — both correct, both about different objects. State which ref you read (`<head>:<path>` on the parent PR vs the child branch tip) and check ancestry (`merge-base --is-ancestor <fixTip> <parentHead>`) before claiming the parent is green or red on that item.

## Measure the whole tree, not a sample

Spot-checking three files turned "six lanes missing the rules" into a wrong "0 of 7". A full sweep is one loop: every `SOUL.md`/`SKILL.md`/`references/*.md` under `agents/`, tree blob size vs live file size, plus a live-ahead/live-behind sign.

Both directions matter: **live-ahead** means unversioned work exists only on this host; **live-behind** (or tree-longer) means the live rulebook was overwritten. Neither is a sync — each is a decision, and the tree is the source.

A `live-longer` finding is **owned by the lane whose live file moved**, not "foreign". Split the list by owner before calling any of it someone else's blocker: each owner re-takes its own file into the tree by allowlist. The single correct live→tree commit is when the live file carries behaviour the tree has not yet recorded (accumulated lessons); the tree→live direction is the sync, and a hostile overwrite either way is the defect.

A **well-meant edit to another lane's file is how a live-longer appears**: touching a lane's tree copy (a lint tweak, a sync) makes that file drift against its owner's live profile, creating the report you were trying to avoid — and the lane then rightly refuses re-take of work it did not author. When a lane's live-longer is caused by another lane's file being stale, the fix is to FILE the finding for its owner, never to edit the file yourself.

## Arming is only valid on a green, mergeable base

`auto=true` on a `MERGEABLE` PR is **not** terminal while the PR's own gate reports fail. Arming a branch whose own guard is red is "done, except the thing that decides done" — the arm-when-done trigger is *gates pass on a mergeable base*, not *no more work on my side*. Before calling a PR "handed to the merger", re-read `gh pr view <n> --json statusCheckRollup` and confirm every gate is green at the current head; a lane citing 'armed' against a red guard is reading its own terminal state as the vehicle's.

Arming does not survive a **base move**: an arm on a clean base becomes `mergeStateStatus: DIRTY` if `main` advances before the merge, and an armed-DIRTY PR merges nothing until its branch is rebased. A rebase resets the arm, so push, re-run `gh pr merge <n> --squash --auto`, and read `autoMergeRequest` back — armed-DIRTY is why "I armed it" and "it is waiting" are not the same sentence.

**"Clean at last tick" is a snapshot, and a sibling merge re-conflicts it between measurement and dispatch.** A mid-sweep merge that advances `main` under an already-measured PR flips a `BLOCKED`/`MERGEABLE` read to genuine `CONFLICTING` — GitHub recomputes only once the base moves. A pass that measured the tree clean and then dispatches only the PRs it *already knew* were conflicting misses the ones a merge just re-broke, so "no conflicts outstanding" is stale the moment another lane's PR merges. Re-read `gh pr view <n> --json mergeStateStatus,mergeable` in the SAME turn you dispatch (or close a pass as conflict-free), and treat a just-landed merge as a trigger to re-measure the whole affected set — an armed, approved, clean root can be CONFLICTING by the time the next lane acts on it.

## "Blocked on an external decision" is a claim to disprove first

When a lane says a gate needs an owner call (an allowlist, a policy, a ruleset), first check that the fix is not merely **unmerged**: a green PR sitting at `auto=none` is not a deferred design decision, it is an arm forgotten. Quote the fix's merge state on `main` (the old gate still in the tree means the fix has not landed) and the arm state of its PR before agreeing any owner decision is outstanding.

## A lane's "gates green" is the gates it RAN, not the required set

A lane reporting `check-docs=0, check-workflows=0, check-wiring=0` can still leave the PR red because it never ran `make ci-lint` (the linefeed/editorconfig gate: an edited file with no trailing newline reds it, and `write_file` trims trailing newlines). The subset a lane chose to run is not the required-check set. Read every required check's conclusion at the actual head before believing "gates green":

```
gh api repos/<o>/<r>/commits/<head>/check-runs \
  --jq '[.check_runs[]|select(.conclusion=="failure")|.name]|join(",")'
```

**The conclusion strings are lowercase — `.conclusion=="FAILURE"` matches nothing and prints an empty red list.** A zero-red read from a case-wrong filter looks exactly like a green PR, and it is how a planner or lane reports "0 failures" for a head that is red. Empty output is not "no reds": print `length` and the full name/conclusion pairs once per head, and only then conclude. Rows carrying `status` with no `conclusion` are *pending*, never pass.

The dangerous case is an **armed PR with one failed required check**: it sits BLOCKED forever and the lane's "done" silently stalls every PR queued behind it. Name the failed check and hand it back; never accept the lane's local subset as the verdict.

## A reviewer's APPROVE comment is not a GitHub review approval

A review lane that posts "APPROVE, clear to land once CI concludes" as a **comment** does not satisfy `REVIEW_REQUIRED` — bot reviews are not approvals here, and `reviewDecision` stays `REVIEW_REQUIRED` with the PR's `reviews:` list empty. Its independent verification (executed claims, run ids, 0 failures) is excellent *evidence*, but it is not the gate. Never upgrade "the reviewer said APPROVE" into "review satisfied": read `gh pr view <n> --json reviewDecision,reviews` and report that the merge still needs the OWNER's approval on top of any pending run.

## A held PR must read `armed=NO`, or the hold is decorative

"Held for <gate fix>" is an intention; an armed PR merges on green regardless of intent. When you accept a lane's "I'm holding it", verify the hold is enforced: `gh pr view <n> --json autoMergeRequest` is null. If it is still armed, the PR can land before the gate fix and re-break `main` — a hold you cannot prove by `armed=NO` is not a hold.

## A lane's local `CHECK=1 OK` proves its WORKTREE, not the PR tree

`make sync-agent-profile CHECK=1 → OK 6/6` run against a lane's local worktree proves the **worktree** matches live; it says nothing about the PR's tree, and the commit may be local-only (not on the PR head, on no origin branch). The verification that counts is against the remote PR object: `git show <pr-head>:<path>` must equal the source, and `git merge-base --is-ancestor <commit> <pr-head>` must be YES. A local green that never reached the branch is the recurring "verified against the wrong object" error — the same trap as a stale sha in a different disguise.

**A divergence report's DIRECTION must be measured, not taken from the reporting lane.** A lane claiming "the tree is richer than live" may have the sign backwards (live 10406b > tree 9574b is live-ahead; tree 7592b < live 8095b is tree-behind). Measure both sides' byte sizes and remember the safe direction: live-ahead ⇒ re-take live into the tree (never shrink live from a truncated tree, which loses behaviour); a tree that is a superset of a deduped live file deserves a diff, not a pass.

## Route an implementation fix to the lane with implement authority, not the nearest monitor

A lane re-scoped to monitor+route will correctly decline to author a code change (a Python script fix belongs to the implementer), and its refusal is right even when the item is the fleet's highest-leverage blocker. When a fix needs authoring, dispatch it to the lane that owns implementation — a monitor can hand you the confirmed defect and an exact fix spec, but asking it to implement yields a correct refusal and a lost cycle. Route by authority first; a monitor is the wrong recipient for `fix <script>.py`.

## A gate-loosening PR proves its negative control

A PR that widens an allowlist, raises a ceiling, or relaxes any gate **passes its own gate trivially** — the gate was loosened by this PR, so green on it shows only the relaxed path works. The evidence must show the previously-failing case **still fails** (e.g. the typo email not in the alias map, an unknown email still rejected), or the body is not a verdict. Deriving one representation from the other (name→email map built from an alias set) is the pattern that stops them drifting apart.

## A reproduced test red is data staleness, not a flake

If attempt N reproduces attempt N-1's failure shape, it is not flaky and a rerun is pointless — rerun is how a lane burns a night on a defect it could have named. Attribute from the job log (`gh api repos/<o>/<r>/actions/jobs/<job>/logs --allow-escape-sequences`, ANSI-strip) and name the class (a committed matrix diverged from its source, a store test vs pristine main). A red that reproduces on the BASE of a docs-only PR is a main-level defect, not the PR's. "Stop looping and report on the data side" after the second reproduction is a decision, not a failure.

## A timeout ceiling is measured, never intuited

`timeout-minutes` is a hang guard, not a budget: set it from the measured step time plus headroom, never from a belief about how long the job "should" take. A ceiling below the measured duration reds/cancels passing runs — one PR pinned 60 minutes on a suite that measures 1:45 and would have killed a run at 60 of 105 minutes with zero failures. If a ceiling reds a passing job, the ceiling (or its asserting test) is the defect, not the job.

## The head you quote must be the head you read

Three-quarters of the stale claims in a night are shas, not facts. `gh pr view <n> --json headRefOid` (or `pulls/<n>.head.sha` on the API) **in the same turn as the claim** costs one line and retires the whole class.

**Use the PR's own head field, never `git ls-remote` of a branch name.** A branch name is per-remote: a fork PR's branch commonly exists on BOTH the fork and upstream with different tips, and the upstream copy is a stale leftover from when the work moved to the fork. Reading `git ls-remote origin refs/heads/<branch>` then reports the old sha and manufactures a phantom "the PR head diverged from the branch / two non-related histories" alarm — when nothing diverged and the fork branch already equals `pulls/<n>.head.sha`. Settle it with:

```
gh api repos/<owner>/<repo>/pulls/<n> --jq '.head.sha, .head.repo.full_name'
gh api repos/<fork-owner>/<repo>/branches/<branch> --jq .commit.sha   # the PR's own branch, when head.repo is a fork
```

Corollary for a multi-PR sweep: the PRs' branches may live on DIFFERENT remotes (one on the fork, the rest upstream). Push each to its own `head.repo.full_name`, then confirm `pulls/<n>.head.sha` moved — a push to the wrong remote either fails or silently feeds the stale same-named branch, and `git ls-remote` will show that stale sha as if it were current.

## A lane that loses its tool stream mid-operation is verified from the remote, not aborted blind

When a lane reports it stops mid-rebase because its terminal/read stream stopped surfacing — an honest "I cannot see my own worktree, I will not fire --continue/--abort/push" — the API terminates the ambiguity without touching its box:

```
gh pr view <n> --json headRefOid,mergeStateStatus   # is the remote head still the last-good push?
git fetch -q origin refs/pull/<n>/head
git merge-base --is-ancestor <currentMain> <remoteHead>   # NO ⇒ the mid-op is local-only, never reached the remote
```

If the remote head is NOT on the current base, the paused rebase is **local-only** — nothing half-landed, no stray push, and the last-good remote push is the safe restore point. The lane's hold cost nothing; do not tell it to `--abort` (or to resume into a conflict) until its stream returns, and give it the remote facts so it resumes safely. A lane that says "cov: unable to read, holding" is cooperating, not broken — the correct response is to confirm its remote is intact and let it recover, never to panic it into a blind reset of the one good push.

A literal local branch `refs/heads/origin/main` can exist and sit far behind real remote main, so every `git fetch origin main` + `rev-parse origin/main` reads THE SHADOW, not upstream. This silently corrupts every quoted `main@<sha>` in a session and strands rebases targeting a stale base. Defeat it two ways:
- read the head the API tells you: `gh api repos/<owner>/<repo>/commits/main -q .sha`, or
- fetch with an explicit refspec so the remote-tracking ref is updated, not the shadow: `git fetch origin +refs/heads/main:refs/remotes/origin/main` then `git rev-parse refs/remotes/origin/main`.
If the shadow is an ancestor of real main (contained, no unique work), deleting the branch is a safe owner-call cleanup that ends preflight corruption for good; until then every un-explicit main read is suspect. The fix is in the reads, never "main didn't move" — when two lanes quote different heads, resolve with the API.

## Resolve a disputed head sha via the API, not a local ref

Two lanes disagreeing on the current `main` head (one quotes a fork's stale tracking, the other the canonical) is a fact dispute, not a judgement. Settle it with the API, which reads the canonical remote directly and bypasses every local `refs/remotes` that may lag:

```
gh api repos/<owner>/<repo>/commits/<branch> -q '.sha'    # canonical, no local ref involved
```

A lane that quoted a stale sha was nearly always reading a **fork's** `origin` (the "a fork named origin is not upstream" trap): `git remote -v` names the canonical remote explicitly, and a rebase/action cut from the fork's head rebases onto the wrong base. When the fork head and canonical head disagree, the canonical wins and the objecting lane withdraws once it sees the API sha. Never let a "your resume is factually wrong about the head" objection stand on a local-ref reading when the API settles it in one call.

**A sha existing locally is not the PR head.** A commit you see in a worktree or on a `tmp/*` or sibling stack branch was not necessarily pushed to the PR you are tracking — `merge-base --is-ancestor <sha> origin/<pr-branch>` is the check that decides it. Attributing a local scratch-branch head to a PR is how a "the PR advanced" flag is born for a PR that never moved: verify the disputed shas' ANCESTRY against the remote PR branch (and list which refs actually contain them) before carrying any "advanced/moved during halt" claim to the owner. A stale-head accusation and a stale-sha quotation are the same error source — the local read — in two disguises.

**A pushed branch is not a shipped PR.** "I created the PR" with a degraded render is a claim; verify against the remote: does a PR exist with that `headRefName` (`gh pr list --state all`), and is the branch tip NOT the bare base (`git log <base>..<branch>` must be non-empty — a tip equal to the base means the push carried no commit, `sync-agent-profile`/skill/`agents/` work never reached it, and `gh pr create` had nothing to attach). A branch pushed at its base reads as "pushed" but carries none of the work; confirm the commit rode it and the PR number reads back from `gh pr view` before reporting it landed.

## The protected-SOUL write wall gates a lane's OWN SOUL too

A lane landing its own SOUL-text change (an orchestration block, a rule) still hits the protected-agent-instruction harness: `patch` on `agents/*/SOUL.md` is refused with "silence is not consent" / approval-timeout even for the file the lane owns. Do not route around it (no terminal edit, no second path) — the sanctioned vehicle is issue + PR under `agents/<profile>/` plus `make sync-agent-profile PROFILE=<lane> CHECK=1`, and the write only lands when the owner or platform grants the approval. Draft the block and queue it; "prepared but blocked at the wall, will land when granted" is the honest terminal state, and re-attempting by another path is the failure.

## A branch rewrite orphans every sha you quoted — verify content, not ancestry

A rebase or force-push replaces the branch's history, so every sha from before it is off-lineage: `git merge-base --is-ancestor <oldSha> <newHead>` answers NO for work that is fully intact, and a branch can be rewritten several times in one session (five heads in one night is normal on a hot stack root). Do not read that NO as "work was dropped", and do not keep quoting the old sha. The check that survives a rewrite is **content at the new head**: `git show <newHead>:<path> | wc -c` against the expected size for each file a lane claims. Report "rewritten head `<sha>`, content byte-identical at it" — that is the fact; "shas changed" is not a finding.

## A stray `Co-authored-by:` trailer reds the author gate — dropping one is not re-authoring

`check-pr-authors` allowlists author AND co-author identity: a PR commit carrying `Co-authored-by: <name> <addr>` outside the allowed addresses fails with "a co-author's name is attribution too". The gate names its own remedies: drop the trailer, or make the co-author an allowlisted address.

Dropping a trailer is **not** "rewriting another lane's commit" when the commits' author and committer are the allowlisted owner — the anti-re-authoring rule protects authorship, and removing a stray attribution from the owner's own commit leaves authorship untouched. Check before refusing:

```
gh api repos/<o>/<r>/commits/<head> --jq '.commit.author, .commit.committer'
git log --format='%h | %an <%ae>' <base>..<head> | grep -ci '<co-author-addr>'
```

If the authors are the owner's, the fix is yours on the correct remote (then confirm `pulls/<n>.head.sha` moved, and re-stack any child PR onto the new head). If the commit really is another lane's, do not rewrite it — report the trailer and the sha to that lane. Widening the allowlist instead is a policy change and belongs to the owner.

## Two lanes on one shared branch must cut from the SAME base

When two lanes push to one shared branch for a collaborative issue, a split base silently forks the branch: each lane's worktree can read a different `main` (one fetched before a merge, one after), and the "same branch" then conflicts for the two who are supposed to push to it. Align before any shared push:
- every contributor re-cuts / rebases its worktree to the **same** current `origin/main` sha, announced on the issue;
- confirm one contributor's move did not span a code-visible merge: `git diff <oldBase> <newBase> -- <dir>` empty means the baseline measured on the old base is still valid — no restart;
- name the branch with the lead before anyone cuts it; both push to it; only the lead reconciles the acceptance criteria.
This is rule 14 ("announce where the work lives") applied to a shared vehicle: each contributor declares its claimed files on the issue before editing, so no two pick the same file.

## Rebase communication is a standing directive (issue #994, owner 2026-10-29)

Two rules every lane owns, plus a third added by the owner the same day:
- **The PR-rebase lane must message the owning lane BEFORE rebasing an ongoing PR** — id, measured head sha, what it is about to do — then post the conclusion on the PR. A decision that exists only in a DM does not exist for the next reader.
- **All lanes rebase their ongoing PRs onto the latest asimov-agent/llgenie `main` ON CONFLICT ONLY** (owner refinement superseding the original every-move rule): fetching `main` fresh before any work stays mandatory, but DO NOT rebase a PR onto every main move — let `main` advance under the armed branch and rebase only when the PR is actually `CONFLICTING` (or its base merges and it must). A PR that reads `MERGEABLE` is not a rebase target, no matter how many merges landed on `main`; the sweep is the genuinely-`CONFLICTING` set, measured fresh. Continuous rebase-every-move is the churn that piles up redundant commits and add/add conflicts.
- **Before starting ANY new issue/PR work, every lane must fetch + align its worktree to the latest asimov-agent/llgenie `main`, then report to the planner** so the planner relays the assignment across the fleet and no two bots pick one issue (no two picks: check `bot-claim:` comments and `agent/issue-<n>-*` branches before dispatching). Fetch-and-align stays standing; "align" means pull-to-friendly, rebase only when actually conflicting.

## "It is already on main" must be a COVERAGE check, not an existence check

A PR marked "superseded by a merge" is only closed when the merged work actually delivers the same COVERAGE — a check, not a path. Files existing on `main` is an existence fact; whether the routing marks / pin / enforcement are present on main is the coverage question. Minutes-long apparent agreement ("everything is on main, close the PR") can be overturned by measuring the marks: a test that was supposed to be deselected runs for real in CI because its MARKER is missing on main while the file is present. Before closing anything as superseded, verify the merged equivalent is functionally equivalent (same marks, same pin reach, same gate wiring), not merely name-present. "Exists on main" is the trap; "the directive is satisfied on main" is the check.

## Fleet orchestration symmetry: audit every lane's SOUL before you delegate a per-lane mandate

When the owner directs a fleet-wide process rule (report-back-to-inbox, rebase-only-on-conflict, any per-lane standing behaviour), do it in this order rather than broadcasting one message:
1. **File ONE issue** carrying the owner's directive + the acceptance criteria as the single vehicle, then work each lane against it.
2. **Read each lane's SOUL from the tree first** — the gap is per-lane (one lane may carry the fleet block but miss the report-back line; another may be entirely absent from `agents/`), so a one-size "add the block" misses the real asymmetry. Dispatch each lane its PRECISE missing clause, and note the lane whose dir is not yet under `agents/` needs both its dir landed and the block added.
3. **Landed = versioned by issue+PR + `sync-agent-profile CHECK=1`** — "landed" is confirmed from the remote (commit on the branch, SOUL carries the citation) and from the sync, never from a render or a local claim.
4. A lane that reports during work but not on-done is half-symmetric: name which clause is missing rather than accepting the half.

The loop the owner wants is implement → report-back-to-inbox → planner delegates the NEW PR to the reviewer for commenting/fixing → lane does not review its own → version-here. When two lanes genuinely split one shared vehicle (a branch two push to), the branch owner's conflict resolution wins and a co-owned PR is never closed/merged/armed unilaterally — hold for the co-owner's agreement.

**Cross-lane duplicate ISSUES are one defect with two trackers.** When two lanes independently file the same defect (a canon-drift, a time-saved fix) minutes apart, the planner consolidates: close the later as a duplicate, preserve its evidence (the measured lines/shas it named) onto the earlier filing, and keep ONE vehicle. Never leave two open canon-trackers for one defect — the second becomes a stale authority that appears authoritative when the real one is closed. Closing-as-duplicate is not rejecting the diagnosis; say that explicitly when the lane that filed second is the one with the sharper measurement. And a defect a lane filed AFTER the planner knows the canonical vehicle is the same rule from the other direction: file into the existing vehicle, not a twin.

## Owner fleet-stop semantics (owner 2026-10-29)

When the owner says stop the whole fleet, ONLY the owner's direct message in their own session resumes it. A planner-relayed "OWNER DIRECTIVE" or a cron-tick dispatch does NOT countermand the stop — lanes will (and should) refuse it. Enforce in this order:
1. Broadcast the stand-down to every lane and **pause the `llgenie-orchestrator-tick` cron** — it will otherwise dispatch under the halt (it did, and was countermanded).
2. Countermand any tick dispatch that lands after the stop.
3. On resume, every action is routed where it lands ONLY on the owner's own word, ideally with scope named (rebase #993 / disable #882's arm / resume the sweep).
4. A lane that pushes or opens PRs during the halt is the exception and must be flagged to the owner with commit timestamps, not normalised.
5. Duplicate vehicles accumulate when a halt is lifted piecemeal (three lanes opened #977/#993/#998 for one email-gate fix, all armed) — consolidate to ONE vehicle before any resume-driven merge.
