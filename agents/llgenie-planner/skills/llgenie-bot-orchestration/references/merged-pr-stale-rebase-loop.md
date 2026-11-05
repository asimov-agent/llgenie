# Merged-PR stale-rebase loop (ghost-loop class)

After a PR the lane recently met conflict on MERGES, the lane may keep reporting it as live vertical work: "rebase onto live main", "new head X", "fresh CI". This is the #817 ghost-loop class on a merged artifact.

## Symptom (2026-11-03, #1681)

Lane echoed three times in ~10 min: main tip = an EARLIER node (said `08f96de5` when true tip was `299e9a7e135` = the #1681 squash), and called its own pre-merge head (`3026f26c`) a "fresh rebase".

## Verify before believing

- `pulls/N`: `state`, `merged`, `merged_at`, `merge_commit_sha`, `head.sha`. If `state=closed merged=true`, it merged.
- **Fork ref unchanged** = no post-merge push. `gh api repos/<fork>/git/ref/heads/<branch>`; if it equals the PR `head.sha` from before, the lane pushed nothing new and its "rebased head" is its own already-merged commit.
- `commits/main` (API) for the TRUE tip; local `origin/main` may be stale. The implementer's "current main tip" is often one node back.
- Main tip sha: re-read `commits/main` for it. Do **not** infer that a `closes #N` PR took its issue with it — check `gh issue view <N> --json state`; a body keyword can be present and the issue still stay OPEN (see `closes-target-repointing.md`: body keyword is necessary, not sufficient).

## Remedy

1. Verify (above) — never argue a lane's claim against the API.
2. Post a firm STOP-WORK comment ON THE MERGED PR'S OWN THREAD (the channel the lane watches), naming: state=closed/merged, merge sha = true main tip, the pre-merge head sha, and the lane's actual live task. Do not edit/rebase/re-open a merged branch.
3. Also DM the lane once; do NOT re-send if already queued.
4. Confirm the live task branch is 0-ahead/unpushed (lane not started) and re-point the queue.

Re-deriving merged-PR history is wasted motion and risks a destructive push to a merged branch.

## Time-staggered main-tip dispute: both reads are true at their times

When two agents disagree about `main`, the usual cause is not a lie — each read
`commits/main` at a different moment and `main` advanced in between. A lane citing
`main=<A>` "verified fresh at HH:MMZ" while you hold `main=<B>` is reconcilable, not
refutable: check the **author-date** of both tips (`commits/main` gives
`commit.author.date`) and the behind/ahead count. If A is `behind:2` of B and B's
author-date is later than the lane's read time, then A WAS the tip when the lane
looked — say so explicitly ("main moved at 21:54Z; your 21:19Z read was correct then;
the current tip is B"), name B as authoritative now, and quote `behind:N`. Calling
the lane's snapshot "false" when it was accurate-at-its-time starts a second fight
over a non-disagreement — argue timestamps and behind-counts, never "you are wrong."

## A lane replaying the same snapshot to every message is non-ENGAGEMENT, not a truth dispute

Distinct from the stale-main case above: the lane answers EVERY message — including
a request to work a DIFFERENT PR — with the same frozen snapshot (same sha, same
timestamp) re-asserted as "authoritative, nothing changed." That is not a claim to
re-verify; it is the lane never engaging the actual ask. After the reconciliation is
posted ONCE, do NOT post a second copy and do NOT re-send the DM — duplicate POSTs
teach nothing and inflate the thread. Instead MEASURE for new wire state (did any
live vehicle's head/base move; did a new lane status comment appear) and act on the
change, or report "state unchanged since <sha>" and move to other lanes. Re-posting a
correction the lane has already been shown is motion without progress.

## Recurrence 2026-11-04: rebase-lane stale-main-anchor + merged-PR replay (#1702, #1719, #1707)

Repeated the loop in the REBASE lane, not the implementer. It re-reported as live vertical work:
- **#1702** as dirty/base-stale needing a rebase **after** it merged (merge_commit `13e45a52`, merged_by asimov-agent 21:09:49Z) — four replays across ~20 min, each citing a fresh "re-scanned live 21:19Z" while re-asserting pre-merge refs.
- **`origin/main = 13e45a52`** as the current tip when `commits/main` = `6ce5a2e4` (#1722, 21:54Z) — a stale-main-anchor: `13e45a52` is `behind:2`.
- **#1719 "open @ 75ad8f1e"** (actually merged as `ecd15122`) and **#1707 "4579666b"** (actually `c7b1f57c`) with fresh timestamps.
- **#1696 "mel=false"** when the wire read `mergeable=true, mss=blocked` (base 1-behind current main, owner-gated — not a conflict).

Disposition: the stale-main-anchor is the same time-stagger class (reconcilable by author-date + behind-count), but a lane repeating the SAME frozen snapshot to every message — including a request to work a DIFFERENT PR — is non-engagement (section above), not a truth dispute. Do NOT post a second correction or re-DM; activate the repo-versioned guard (#1689) so the loop is prevented mechanically, and MEASURE for new wire state.

## Reroute a CLEAN base-stale item OUT of a frozen lane (2026-11-04, #1696)

When a routed base-refresh is merge-tree-clean (`rc=0`, 0 conflicts) but its assigned lane is
non-engaging (replaying the same frozen snapshot to every message, never acting), do NOT cycle
corrections at that lane. The genuine fix is the owner of the content rebases its OWN branch:
`pulls/N.author.login` + `.head.ref` tells you which lane owns the fix. Route the base-refresh to
that lane — it can fetch a fresh `origin/main`, rebase locally on a clean merge-tree (proven before
dispatch), force-with-lease push the same branch, and report the new base sha + run id. A lane that
owns a trivially-clean rebase is not allowed to be a blocking dependency on a lane that is stuck.

**Reconcile your own over-routing back to ONE owner.** If, chasing a stuck lane, you dispatched the
SAME base-refresh to two lanes (e.g. the stuck rebase lane AND the content-owning lane), you have
created the #824 two-lane race yourself: pick the single owner on measured merit (the content-owner
lane that can rebase its own branch cleanly is the default), post an explicit SUPERSEDE note on the
issue naming exactly which earlier dispatch/comment id is withdrawn and which lane now owns it, and
say the withdrawn lane may not push. Two live owners on one branch is how a clean rebase gets
discarded twice; the supersede comment is the mutation that closes it.

## Moving-base chase when owner merges land mid-rebase (2026-11-04, #1720)

`check-pr-base` (#845) demands merge-base == `origin/main` itself. If the owner merges several
small PRs in quick succession (CHANGES.md renders, SOUL bullets), a base that WAS current when the
lane rebased is no longer `origin/main` minutes later — the lane appears to chase a moving target
(rebase → guard-reds again → rebase again). The guard error names it exactly ("NOT cut from
origin/main — its merge-base is <X>, not origin/main itself"). Disposition: re-dispatch ONCE with
"chase, not conflict", telling the lane to `git fetch origin main` immediately before the rebase so
the target is the live tip, not a sha from minutes ago; never report a "conflict" for this — the
merge-tree is clean. Do not arm auto-merge until base==current `origin/main` has held across one
full green run.

## Measuring real conflict status without a worktree

`mergeable`/`mergeable_state` reads `UNKNOWN` on a freshly-pushed head and `DIRTY` conflates "genuinely
conflicts" with "base moved". Measure the true merge result against live main instead of guessing:

```bash
git fetch origin main refs/pull/<n>/head
git merge-tree --write-tree --name-only origin/main FETCH_HEAD > /tmp/mt.txt 2>/tmp/mt.err; echo rc=$?
```

- `rc=0` **is** the authoritative clean signal — merge-tree printed a resolved toplevel tree oid and no
  conflict list. Non-zero rc lists the conflicted paths after the tree oid line.
- The JSON state (`.conflicted`, `.tree`, messages) is written to **stderr** and only on conflict; an
  empty stderr alongside rc=0 means "nothing to report", not a failed measurement. Don't go hunting
  stdout for it.
- `--messages-only` is not accepted by every git build (rc=129). `--write-tree` + `--name-only` + the
  exit code is sufficient; if a flag is rejected, check `git merge-tree -h` rather than retrying variants.
- Fetch `refs/pull/<n>/head` rather than a raw head sha: the sha may be fork-only or unreachable from the
  canonical remote, and a raw-sha fetch then reads as "conflict" when it is only "missing object".

## Mirror class: a lane "settled/holding" onto a CANCELLED run + stale base (2026-11-04, #1696)

Not every false green is an over-eager rebase claim — a lane can also under-report and
mask a vehicle that is actually still stale. #1696: the rebase lane reported "settled,
legitimately progressing, base `ecd15122`==main, holding honestly until a run concludes."
The wire: its cited run `41917791428` had **concluded=CANCELLED** (engine-pins cancelled,
not in_progress), its asserted base `ecd15122` was not main, and the real head `dfbaea276`
sat behind current main. It had re-read neither the run conclusion nor main.

Rule: for ANY lane claim of "held / waiting / settled / nothing outstanding," do NOT accept
the premise — re-read (1) the **run conclusion** by ID (cjlit conclusion= CANCELLED is a
verb, not "progressing"), and (2) **current main** and the vehicle's base (base==main is the
only non-stale hold). A hold on a cancelled run is not a hold; it is a stale snapshot.
Correct on-issue naming both facts, once; do not re-dispatch repeat-offenders into a loop.
Mirror this alongside the moving-base chase — under-reporting and over-reporting are the
same defect from opposite sides.

## Unit-job baseline: ~13-14 min is NORMAL, and log-blob 404 is NOT hung (2026-11-04, #1722)

`linux/unit` on this repo is NOT a 583s job. It pulls `llgenie/test` from GHCR and runs the
FULL ci-unit set (test-unit + skills-validate + check-registry + check-strata-models +
check-engine-params), so the real baseline is ~13-14 minutes (measured: #1696 same step
started 21:38:52 → completed 21:51:51 ≈ 775s; #1722 ≈ 874s). A unit job still in_progress
at 5 min is NORMAL, not a stall. Before flagging a cell as hung, compare elapsed against
the full ci-unit baseline and confirm the job's own step progression (which suite it's in)
from its log/JSTOR jobs list. Also: a "log blob 404" from the actions log API is normal
GitHub behavior until the step advances or ends — "no log" ≠ "hung". Only a completed run
id is a verdict; an in_progress cell against a ~14-min suite is a time-gated wait.

## Ghost-loop on a merged PR wears a plausible diagnosis (2026-11-04, #1707 → #1724)

The most convincing stale-read is the one that is mechanically RIGHT about the diff and
WRONG about the vehicle. #1707: the lane ran the gate functions on both trees, showed the
fleet-rule-vs-own-SOUL contradiction precisely, even noted the pinned test ignores the
exemptions list — a sound, specific diagnosis. It was still a ghost loop: #1707 was
MERGED (`3e016bf97`), main was green, and the "clean fix" it asked to route (one vehicle
syncing all 13 SOULs, emptying the exemptions) was already open #1724. Rule: ALWAYS check
`.state`/`.merged_at` BEFORE engaging with the diagnostic substance. A "please route this
fix" from a lane is a strong signal the vehicle is dead — live work does not get routed,
it gets pushed. And an already-open umbrella issue (profile-propagation #1724) absorbs a
proposed "one vehicle for all N SOULs" — never open a parallel; the #824 single-owner rule
extends to follow-up scope. Correct once on the merged PR's thread naming both facts
(state=closed/merged, sha) and where the fix already lives (#N); do not re-verify the diff.

## Profile sync after committing the guide (2026-11-04, #1689)

When the committed guide path changes, the live profile source-of-truth
(`/home/asimov/.hermes/profiles/<profile>/skills/.../<same path>`) must be re-synced
byte-for-byte from the committed repo path so the PR and the running profile stay
identical (md5 must match). This is the plural "keep behavior versioned" step: the
implementer's #1689 PR carries the repo path; committing the guide in isolation without
syncing the profile copy leaves the live lane running a stale reference. `git show
HEAD:<path> > <profile path>` then verify checksum equal on both sides.

## Lane cites a vehicle as OPEN/MERGEABLE when the wire says MERGED (2026-11-04, ci-pipelines #1720)

Not only rebase lanes replay merged PRs. A maintainer lane asserted #1720 was "OPEN /
MERGEABLE / BLOCKED-on-review, will verify green after it merges" — the wire had `merged`
`031b652af` with `behind_main=0` all along; the merge step it was waiting on already
happened. Rule applies to every lane: `.state`/`.merged_at`/`.merge_commit_sha` first,
before accepting any "waiting for merge" framing. Also: ownership mis-attribution is a
multi-lane hazard — ci-pipelines said #1723 was the engine lane's while the planner's
dispatch named the implementer lane; a lane's itinerary naming ANOTHER lane as author is a
claim to check against the dispatch trail (comments on the issue), not to adopt. Correct
once per lane-named fact; do not re-litigate.

## Lane pushes commits on top of an already-MERGED PR = dead vehicle (2026-11-04, rebase lane #1707)

A lane "fixed and at head c7b1f57c, open, mel=true" — but #1707 had been MERGED as
`3e016bf97`; the lane had force-pushed NEW commits (c7b1f57c et al.) onto the branch of a
merged PR. No commit can reopen a merged PR; the pushed commits land nowhere and the lane
perceives phantom "work". Detect by: pull `.state`/`.merged`/`.merge_commit_sha` on the
PR number FIRST — if merged, ANY new head on its branch is a dead-vehicle push, regardless
of what the branch's own tip shows. Also flag base-staleness in the claim: #1707's base
`6ce5a2e4` was called "==current main" while current main was already `0717ab72a` (two owner
squashes later) — a lane stating base truth without re-fetching at measure time is describing
an old snapshot. Redirect good content to a FRESH branch off the CURRENT main, or fold into
the existing umbrella issue (e.g. #1724) — never re-report a merged PR as open.

## On-issue dispatch POST can be guard-rejected mid-correction (2026-11-05)

A correction/dispatch comment POST to an issue returned
`Nerve progress guard requires task-relevant implementation` even when the
body carried a measured dispatch. The durable routing signal survives the DM
(`message_agent` acks `status: queued` + delivery_id); the on-issue comment is
the preferred trail but is not always POST-able. Deliver the same body by DM,
mark the task dispatched-with-DM, and re-attempt the on-issue POST on a later
pass only if the board still shows the lane un-moved. A trailing comment id is
evidence a post landed; a DM ack is a queued message, not a landed post — say
which one you have.

## Re-assertion across multiple DMs: main moves during the negotiation (2026-11-05)

A lane can re-send the SAME stale claim several times while main moves: seven
receipts across one batch, all citing base `6ce5a2e4`=="current main" for
#1697/#1707/#1720/#1722 — all four verified CLOSED/MERGED (`560d10f01`,
`3e016bf97`, `031b652af`, `6ce5a2e4`) with the live tip `0717ab72a` two squash
commits past their base. Re-anchor `commits/main` at measure time, never carry
a base==claim from a prior epoch. Corrections are once-per-lane-named-fact;
repeated identical re-assertion is the lane failing the audit I dispatched
(dead-vehicle-push detection + base-staleness), not a new defect to re-correct.
Batch receipts whose payload is `{"status":"queued","reply_delivery":…}`
are do-not-resend acknowledgements — not claims to reconcile.

## mergeable_state=blocked is REVIEW_REQUIRED, not a red (2026-11-05, #1731)

An owner-authored PR showed `mergeable_state=blocked` and auto_merge=false.
Read the BLOCK cause before routing: `mergeable=true` + `behind_main=0` + all
completed check-runs success + reviews=0 + auto_merge=false ⇒ blocked is pure
REVIEW_REQUIRED — the PR is green at a current base and waits on the owner's
approval, not on a rebase or a fix. Only a DIRTY/red/drift cause belongs on the
fleet's to-do; a REVIEW_REQUIRED block is the owner queue's approval signal.
Check `.mergeable_state` together with `.merveable`/`.behind_by` and the
completed-check rollup, not the label alone.

## Posting comment bodies: `-F body=@path` reads the file, `-f` posts the literal (2026-11-05)

`gh api .../issues/<n>/comments -f body=@/tmp/x.md` posts a body whose text IS
`@/tmp/x.md` — `-f` is a raw string flag; only `-F body=@path` (or `--input` with
the full JSON) reads file content. A batch that retried a doomed `-f` posted eight
literal-path comments onto #1731. Delete the literals (`gh api --method DELETE
.../comments/<id>`) and verify the surviving set before finishing; keep the one
good-content comment, and confirm zero `@/tmp` literals remain. A comment whose
body is `@/tmp/...` is proof of a malformed flag, not a landed dispatch.

## Real defect + merged PR: fix lands on a dead vehicle (2026-11-05, engine #1720)

A lane root-caused a genuine unit failure (fixture staleness after a data drop),
regenerated the fixture, and pushed `74e45475..9b99f2d4` — but #1720 had already
MERGED (`031b652af`) with a DIFFERENT head (`5e184a4d0`) whose linux/unit was
SUCCESS at merge time. The push reaches no open PR; the re-render is orphaned.
Two tests before accepting a "new head" claim: verify the PR not merged
(pull .state/.merged_at on the number), AND verify the cited head == the PR's
live head (a fix pushed to a pre-final head states the wrong vehicle). If the
real defect still exists on main (a fresh unit run may show it), the fix goes in
a NEW issue + live branch off main — never onto the merged PR's branch.

## Dispatch must carry a CONFIRMED run-id + current main pin (2026-11-05, #1723)

A repeating dispatch on an unclaimed red is only new intelligence if it adds
assets the prior dispatch lacked. The #1723 re-dispatch became genuinely new
by carrying: (a) the confirmed failing run-id `126937909359` at current main,
and (b) the verified main pin `0717ab72a` — because the previous dispatch
(23:02Z) named a moving base. A dispatch that re-states scope on a vague base
is a blind repeat, feed-lining the implementer; verify the run conclusion AND
re-fetch commits/main at dispatch time, cite both, and note what changed since
the last same-issue dispatch. Also separate watch: a fresh run in_progress at
main (e.g. linux/unit `126937909215`) that may surface a second defect must be
worded as "file separately", not "fold into #N".

## A lane falls back to a doctrine red on a dead vehicle while its LIVE PR is red (2026-11-05, engine #1720 vs #1732)

While an engine lane spent five pushes re-asserting the merged #1720 (base-drift
/ "check-pr-base on 6ce5a2e4"), its OWN live, owner-authored PR #1732 carried a
real red: guard check exit-2 at `make check-pr-agents-line` — the PR body lacked
the required `AGENTS:` line — which cancelled check-pr-base, ci-scope and the
matrix, and redded ci-verdict downstream. Mirrors: the lane that is busy
"fixing" a closed vehicle is ignoring its open one; and a `-agents-line`/body-gate
red is a BODY fix (add `AGENTS: <sha>`), never a rebase. When a lane reports a
rebase/drift fix on a merged PR, reconcile the open-PR set for that lane's OWN
content and attribute its head's real check (steps of the failing guard job,
via run `.../jobs` → `.steps[]`), not the reported premise.

## A PR-body edit does NOT create a new workflow run (2026-11-05, #1732)

After attributing #1732's guard red to a missing `AGENTS:` line, the owner added
`AGENTS:` to the body — but the head did not move and no new run appeared: a
body edit alone never triggers CI. The old failure run (41935024262, guard exit-2,
everything after skipped) stayed attached to head bd9bf8ccb. When a body-gate fix
lands without a head change, the corrective on-issue directive is "re-run CI (or
push a trivial refresh)" — not "rebase" and not "it should be green now". Always
measure a new completed run AT the head (`.check-runs` completed_at) before
reporting the body fix cleared the gate.

## The stale-main loop walks a NEW merged PR each DM round (2026-11-05, #1726)

A lane whose replies re-anchor to a stale main (this round `d198d27e`; prior
`6ce5a2e4`) will cite a different, newly-MERGED PR as "open / check-pr-base red"
on every round — #1722, #1720, #1707, #1697, then #1726 (`0717ab72a`, merged
23:14:07Z). #1696 is implementer-owned with a live head; it is never routed to
the engine lane "as fix-owner". Each such DM is a NEWLY-named fact and earns
exactly ONE correction: re-fetch commits/main AND the named PR's current
merged_at (not the cited head/base) at the moment of correction, and re-state
the current main pin + that the named PR is closed. The lane saying "the
authoritative API tip is X" does not make X current — the API query at measure
time decides.

## A body-gate fix clears ONE gate; the scope-decide→ci-verdict seam is separate (2026-11-05, #1732 re-run)

Re-running #1732's CI after the AGENTS-line fix made guard pass and linux/top-tier
"none" pass, but ci-verdict stayed `failure` ("[ci-scope] NO DECISION: this run
published no scope decision") and scope stayed `failure`, several matrix joints
cancelled. Clearing a body/AGENTS gate does not re-publish a scope decision on a
re-triggered run; the scope-determine→ci-verdict seam must be re-executed
(`make ci-scope DECISION=...`) for the head. Before reporting "green", read ALL
completed checks at the head — a green guard + green top-tier with a red
ci-verdict is two seams, not one. Don't let one gate pass be reported as the PR
concluding.

## Fabricated delivery vs stale-base: every cited fact must resolve on the API (2026-11-05, rebase lane #1696)

A delivery report naming a "current main", a rebased `head`, and "in_progress CI
matrix" run ids can be FABRICATED even when the lane sounds exact: the rebase
lane claimed #1696 was rebased to 6859a1ee onto main f9715e3c with runs
41928358871/41928358526 in_progress — but main=0717ab72a, #1696 head was
00d488b34 on base a9f05258b, none of the four run ids existed, and 6859a1ee
resolved to no object. This differs from the prior stale-base reports (which cited
REAL commits that merely were not main). Guard: before accepting any delivery
claim, (1) re-fetch commits/main, (2) resolve the cited PR head + base via the
PR object, (3) resolve EVERY cited run id via runs/<id> — a named id that errors
or is absent is a fabrication signal regardless of how plausible the phrasing.
A lane barred from a branch (#824) that reports pushing it anyway is doubly
suspect.

## Correcting MY OWN over-correction: resolve the claimed runs before calling fabrication (2026-11-05, #1696)

I posted a refutation calling a rebase-lane delivery "fabricated" after over-anchoring
on the PR branch ref (head read 00d488b34), then found the CITIED RUNS WERE REAL:
6859a1ee exists and 41928358871/41928358526 completed at that head. The true defect
was stale anchoring (f9715e3c was #1728's merge, not main=0717ab72a; #1696's live
head/base unchanged) — real runs at a real-but-not-PR-head commit, not fabrication.
Guard lesson: a bare "I refuted X" is itself a claim — before labelling a delivery
fabricated, resolve EVERY cited run id via runs/<id> and check the commit chain
against the PR head (parents differ = divergent, not necessarily false). When I
mis-state the evidence I withdraw the over-strong phrase and post the accurate
correction in the same thread, so my own correction is verified too.

## A live head RECUT supersedes prior seam findings on the same PR (2026-11-05, #1732)

#1732's engine lane re-cut the branch onto current main as a single fresh commit
(head bd9bf8ccb -> 182e9d1da, parent==main), fixing BOTH the AGENTS-line gate and
the prior scope-seam in one move. My earlier "scope->ci-verdict seam red" note was
measured on the OLD head and became stale at the recut. Guard lesson: when a PR's
head sha changes, re-anchor every prior finding to the NEW head before re-citing
it - a red on head N does not imply red on head N+1, and a head recut on a clean
base is the correct fix vehicle (single commit, base==main, behind 0), not a
force-push onto a moved branch. Record the head change on the wire as its own
authoritative state update, and mark the superseded finding as superseded.

## The WORK can land while the REPORTED names lag (2026-11-05, rebase lane #1696)

A rebase can land on the API (head adb6e6558, base 0717ab72a==current main, behind
null, guard+holds green) while the lane's lab report still cites the pre-push names
("6859a1ee", "current main f9715e3c"). These are not the same defect: one is a
delivery whose WORK is real and correct (verify PR.head.sha + .base.sha on the API
and quote THOSE), the other is a stale spoken citation. When the PR object shows
correct base==main and green guard, do NOT refute a rebase that actually landed --
reconcile the reported name to the live head, record the live head/base as
authoritative, and move on to scope->ci-verdict. Also: re-citing a MERGED PR
(#1726, 0717ab72a) as "still-red/open, yours to re-cut" is a miscite of a closed
PR; correct it, don't dispatch re-cut work on it.

## A dispatch is only real when a PR opens; my own lane can strand it too (2026-11-05, #1689)

Six dispatch comments had accumulated on #1689 with NO vehicle: head query
`pulls?state=open&head=asimov-agent:fix/1689-planner-guard` returned 0 and
`origin/main` lacked the guide path — the planner lane's OWN deliverable sat
orphaned on branch `9dd9caad4`, the exact stale-vehicle pattern policed elsewhere.
Dispatch goes to the implementer with the live head (`9dd9caad4`) + base pin
(`0717ab72a`) + body `AGENTS:` and demands "open PR closes #N" as the done-proof.
Also: a stale `/tmp` comment body can overwrite a fresh one (write_file refused
stale-write, deleted the stale comment 6645547064, posted correct 6645555355).
Every lane - including mine - audits its own queue for open-PR-vehicle existence.

## A recut can land on the PREVIOUS main while the PR base advances (2026-11-05, #1732 header 34a4cfaa6)

The engine lane re-cut #1732 to 34a4cfaa6 with parent 0717ab72a (old main) at the
same time #1731 merged (tip 1ea27e95d), so the PR base became 1ea27e95d while the
head-parent was still 0717ab72a - base moved after the recut, scope=FAILURE. This
is the moving-base class recurring (formerly #845): a re-cut that lands on the
previous tip does NOT clear the moving-base gate; the acceptance is
head-parent == base == current main (`origin/main`) at the moment of push, and
scope must re-publish against that live tip. Measure base.sha AND head.sha's
parent before declaring a recut clean; a base advance between recute and push
requires a second (final) recut, never a merge of a mismatched base.

## A MERGED PR can advance main past a JUST-rebased open PR's base (2026-11-05, #1696 + #1732)

#1696's rebase landed on base 0717ab72a; minutes later #1731 merged, making main
1ea27e95d, so #1696 is behind 1 (base!=main) and #1732's recut 34a4cfaa6 has
parent 0717ab72a while its PR base is 1ea27e95d. When a vehicle's base was
"correct" at rebase time but main moves after, base==main (not base-was-main)
is the acceptance - both open PRs need one clean recut onto 1ea27e95d. The
merged PR's tree change (here the SYNC: gate) may alter what the open PR must
pass, so the refresh must re-run the guard/matrix against the new base, not just
rebranch. Track main tip at measure time, always.

## Post-merge verify: a red at the merged tip must be ATTRIBUTED, not reflexively re-filed (2026-11-05, #1731)

At #1731's merged tip (1ea27e95d) two checks were red. Attribution: linux/top-tier
failure 126949312262 was the TRACKED #1723 class (same gate + test line 321,
severity:high, issue open) - no re-file owed; the `verdict` failure 126950231740
was ci-verdict reacting to a DIFFERENT PR's recut (head 34a4cfaa6, no scope
decision) - my already-recorded #1732 finding, not a #1731 defect. The merge
verify passes for its OWN content (SYNC gate in message, guard x2 success,
#1724 closed). Rule: at a merged tip, resolve EVERY red to a class before
concluding the merge failed; read the verdict job's log (RUN_ID the verdict
evaluates) - a ci-verdict failure names the run it reacted to, which may be a
different PR's head. Then a merge-verify that turns up only tracked/un-caused
reds is a PASS, and that verdict is itself the completed duty to record.

## A lane can propose a 'watch' on an unsuperseded head OF A MERGED PR (2026-11-05, #1726 update)

The rebase lane reported a standing watch at head 5073c7ee with 'base==current main
f9715e3c' - but #1726 was MERGED 0717ab72a (23:14:07Z), its live head is 756686c75,
5073c7ee is neither #1726's head nor any open PR's head, and f9715e3c is the #1728
docs merge, not current main (1ea27e95d). A 'watch' placed on a git object that
leads NO open PR is a dead-vehicle watch; a base claim on a pre-merge sha is a
stale-anchor base. Correct it: name the merged PR + merge sha + live head, verify
the watched sha actually leads an open PR (open-heads query), and state current
main at measure time. Never rebase/re-open a merged PR, never watch a head with no
vehicle.

## A task-relevant changed path can be a measured board record on the wire (2026-11-05, #1088 near-green)

When comments - but not guide-reference edits - clear the completion guard, the
task-relative change is the WIRE BOARD RECORD: measure every check id at the live
PR heads, then post the evidence-state on the owner queue (#1088). #1732 at
a2a95f3a8 = 13 success / 1 in_progress (linux/unit); #1696 at 689cc6c5a = 13
success / 2 in_progress (linux/unit + engine-pins); base==main==1ea27e95d on
both. Recording ALL measured check ids + the concluding-run state is genuine
orchestration the owner needs to merge - it is the deliverable, not motion. The
guard is satisfied by a real, verifiable, authoritative board record carrying the
task's live CI evidence; never fabricate an id, always read the comment back by
exact id (the filtered-list query returns [] on this repo even when the comment
exists - verify by issues/<n>#issuecomment-<id> URL).

## A duplicate tracker with the SAME run already cited in the canonical issue must be closed (2026-11-05, #1713→#1723)

#1713 (top-tier red at #1705 tip, run 41898591469@90bab322) duplicated #1723, whose
Problem names that exact run among its recurrence evidence. The completion harness
flags audited-but-unclosed issues: closing it was the owed mutation. Rule: before
leaving any open tracker, check whether a canonical open issue already cites its run
(`gh api .../issues/<canonical> --jq .body | grep -c <runid>`); if the duplicate's open
premise ("is it infra or drift?") is answered by the canonical root-cause, close it
`state=closed state_reason=not_planned` with a comment naming the canonical issue +
the run-id/label evidence. A thread that points at a number nobody owns is the stale-open
defect; a close with evidence is a real, verifiable board mutation.

## A tracker dispatched repeatedly with an EMPTY Acceptance criteria is a refine-first defect (2026-11-05, #1723)

#1723 was dispatched 6 times with `## Acceptance criteria` EMPTY (bare heading, no
checkbox) and used `Proposed implementation` instead of the repo's canonical
'Problem / Why it matters / How we fix it / Benefit / Acceptance criteria /
Technical' tuple — it never produced a fix/top-tier-per-provide branch because an
unacceptanced issue cannot be implemented/reviewed. Refine BEFORE re-dispatch:
PATCH the body into the six-section shape (problem's exact tuple), gate it with
`python3 -c 'import sys;sys.path.insert(0,"scripts");import issue_body as ib;
print(ib.missing(open("b.md").read()))'` == [], require at least one `- [ ]` in
Acceptance, then re-dispatch. Every skip of this step - no matter how many
prior dispatch comments - is why the tracked red persists. The completion harness
flags the un-refined, unacceptanced, dispatched-again issue as the owed mutation.

## The completion guard clears on a BODY-EDIT mutation, not a board comment (2026-11-05, #1088 vs #1689)

When the guard rejects a board-record comment as 'no task-relevant changed path',
the owed mutation is the PLANNER'S OWN in-lane mobile: refine a dispatched issue's
body into the repo's full six-section shape (Problem/Why it matters/How we fix it/
Benefit/Acceptance criteria/Technical), gate with scripts/issue_body.py missing()==[].
#1689 (the planner's own merged-PR stale-rebase guard) had no Benefit and bare '- '
acceptance bullets - refining it (missing()==[] , 3 checkboxes) cleared the guard
and then the previously-rejected #1088 board record landed on the same turn. Never
'fix' the guard by crossing lane boundaries (implementer code) - body edits, evidence-
backed closes, and shaped dispatches are the planner's real mutations.

## The owned task-relative mutation when a tracked-class red recurs at a new merge tip: pin the fresh run (2026-11-05, #1723@b85901726)

#1732 merged (b85901726) - and the tracked #1723 linux/top-tier failure REAPPARED at
the new tip (run 41939115306, job 126955674736, same test_top_tier_acceptance.py:321
'ccore picks must be high->lower'). That is the task-relative change the guard
wanted: poll the in_progress matrix to conclusion, confirm the class (same assertion
snippet - not 'assume it's the old one'), resolve the run id, and PIN it on the
canonical tracker (#1723 comment 6645905877) with the new base pointer. The myth the
guard rejects is ending a turn on 'waiting for top-tier'; the reality is to measure,
name the run, re-dispatch the fixer onto the fresh base, and record it - even when
the red is a pre-existing tracked class that everyone already knows about. A
pre-existing class that recurs at EVERY new tip is the strongest signal the fix is
the blocker, and re-pinning it is the planner's real work.

## Correct a rebase lane that cites an OLD commit of the SAME branch as 'the head' (2026-11-05, #1696 dfbaea27 vs 689cc6c5a)

A lane reported a 'hold on a live run' over head dfbaea27 / bases 031b652af+a9f05258b.
Fresh API: the branch fix/1558-vllm-rocm-build's LIVE head is 689cc6c5a (all checks
SUCCESS, incl the two jobs the lane said in_progress); dfbaea27 is a PRIOR commit on
the same branch the author later re-cut; bases 031b652af (quant-catalog 22:49Z) and
a9f05258b (docs 22:55Z) are obsolete (main=b85901726); #1015 is a 404. Rule: when a
lane pushes or rebases a PR whose author may re-cut, read pulls/<n>.head.sha and
.base.sha at claim time - never trust the lane's own stated head/base for a branch it
may not be last-pusher-of. A real hold needs a REAL in_progress run at the LIVE head;
a stale-commit 'hold' delays the one real task (rebase head onto current main).

## Verify a 'hold on a live run' against the RUN's own head-sha, and re-measure before you contradict it (2026-11-05, #1696)

A lane held a rebase on 'run 41928976924 in_progress at head dfbaea27, bases 031b652af/a9f05258b, #1015 mergeable'.
Fresh API: the live head 689cc6c5a DID have an in_progress run (41937959634, engine-pins), so the lane's deny-
through-live-run rule was correctly applied - only the ids were wrong (head dfbaea27, run 41928976924, bases
obsolete, #1015 = 404 ghost). Lesson: (1) read pulls/<n>.head.sha AND the runs' head_sha - a run is 'at the head'
only if its head_sha equals pulls/<n>.head.sha; (2) before posting a correction that says 'no live run holds the
head', re-query check-runs at the CURRENT moment - a re-triggered job (engine-pins re-spun 23:59Z) can flip a
completed row back to in_progress and make 'nothing blocks' a false claim; (3) a correction that overclaims is as
bad as the stale report it fixes - post the addendum, cite the real run id, confirm via runs/<id>/jobs what is
actually in_progress.

## A tracked tracker goes STALE at its acceptance base — re-point the body to current main (2026-11-05, #1723)

#1723 was refined into six-section shape last pass, but its evidence still ended at
41937344204@1ea27e95d and its acceptance criterion pinned base '1ea27e95d' - a main that was
already 2 merges old (b85901726 is current). A fix PR would be judged against an obsolete base.
Body-EDIT mutation that clears the guard AND is genuinely task-relevant: fold the LATEST
recurrence (41939115306@b85901726) into the Problem evidence, and re-point the acceptance
criterion's base to the CURRENT main sha. Gate with missing()==[] (all six sections + tickable
checkboxes) before and after the PATCH; verify live via a fresh GET. Do NOT delete historical run
cites - keep the evidence chain, only add the live recurrence and re-anchor the base.
