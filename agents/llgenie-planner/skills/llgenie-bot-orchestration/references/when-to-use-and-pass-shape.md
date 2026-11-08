# When to use the orchestration skill, and the shape of a pass

Moved out of `SKILL.md` to keep its always-on body under the 100,000-char skill-writer limit. Same rules, verbatim.

Not a code task. Use it on every llgenie pass, and whenever the owner asks "what are the bots doing?": a bot is
idle (no run in its cron slot, or runs all `skipped`), a claim looks live but no branch exists, or a branch carries
work with no PR. It ends in a dispatch with evidence, never in an implementation.

The planner never implements. This is the loop that keeps the fleet working: measure quiescence, measure the
backlog, dispatch, report the evidence.

**Idleness is the defect.** Every pass ends in a dispatch, a close with evidence, or a written reason nothing could
move — never in "waiting". A recurring tick (a cron job running this skill, every 30–45 min) is the mechanism that
makes the rule true rather than aspirational; when it fires, run the whole pass and report what changed. A stalled PR
is the same failure as an idle bot: a conflicted PR gets no CI run at all, so nobody will fix it unless you dispatch
the rebase bot or the host implementer.

**Per-tick sweep size: 12 issues AND 12 PRs (owner 2026-11-02).** Every 30-minute tick must walk at least 12 open
issues and 12 open PRs — measure the full lists (`gh issue list --state open --limit 100`, `gh pr list --state open
--limit 50`), pick the 12 highest-value items from each that are not already claimed, and dispatch/refine/close each
one with a board trail. Do not stop at "everything idle is handled" using a short list; the sweep at the owner's
"more work" demand found the hidden backlog (8 engine-bump PRs) only because it enumerated the full list. If open
actionable items in a category number fewer than 12, say so in the pass report and double the other category. A tick
that dispatches fewer than 12+12 must name why (fewer exist, all claimed, all gated).

**Triggering is the act of the pass, not a consequence of it.** On every tick, after measuring quiescence, do NOT
stop at "lane X shows no run in its slot". For every bot that is idle OR idle-capable (no held-gate blocker + an open
unassigned issue it can do without that gate), send the `message_agent` dispatch to it naming a fit issue — even when
the lane has previously been told. A bot that is never messaged cannot start; "I reported it idle last tick" leaves it
idle the next. Only a lane with NO open gate-free issue in its whole domain is left untriggered, and then the pass
must say which lanes that was and why (the drive-by "nobody told me" is a planner defect, issue #1030).

**A lane that answers the SAME correction twice is a signal, not a reason to re-ack.** When a lane rejects a dispatch with
the same measured facts multiple times (stale tip, no rebase owed, already-mergable), the ACKs are the loop — stop replying,
anchor the agreed facts on the vehicle, and only re-touch the lane when its stated next event lands (CI concluding, ms flipping
dirty). Dispatches that cite a stale base/tip NAME are the common trigger: base and parent are different facts, re-measure the
canonical tip each pass, never instruct a rebase onto a base that is the PR's current parent (that's already a no-op; #1015
rebase only on real conflict). A lane re-litigating an issue that is ALREADY CLOSED (`gh api …/issues/<n> --jq '.state,.state_reason,.closed_at'`) while its own open `agent:implement` claim sits untouched is deflecting: one final evidence-complete close (state/reason/closed_at + the resolving merge sha + re-run the gate yourself on a canonical archive) plus a redirect to the active vehicle, then no further reply on the closed issue. If the lane accuses you of measuring the wrong remote (e.g. fork vs canonical), prove it once with `git remote get-url origin` and `git rev-parse origin/main` in YOUR clone and do not re-prove it. (owner 2026-11-01, loop-escape + deflection lesson)

**An EMPTY queue is still not "done" — dispatch the own-domain continuous-improvement audit (owner 2026-11-01).**
An operational lane (security, documentation-maintainer, ci-pipelines-maintainer, engine-improver, reviewer,
rebase-conflicts) with no open gate-free issue is never parked as "nothing to do": dispatch it onto a bounded,
measurable audit of its own domain that produces its own next finding. Per-lane audit definitions: security —
scan-coverage (which vulnerability classes the scanner misses), dependency-pin validity (silently-unsatisfiable
pins before they blow up, the #1252/#1262 class), scan-rule-set freshness, admission-gate coverage; documentation —
main-versus-docs alignment, skill-freshness (2+ releases old), change-note coverage; ci-pipelines — gate-coverage
(which failures current gates cannot see), workflow robustness (cancelled-mid-flight, stale-head races, the #1250
class), step-sharpening; engine — engine-cell pin validity + serving drift; reviewer — review-process gaps. Every
finding filed as a refined six-section issue; implementation routes through the normal queue, never the auditing
lane's own pass. A clean audit is recorded `re-audited at <sha>, no findings`. The sweep runs only when the queue
is empty and never overrides real reactive work. Report the audit's output artifact (findings issue(s) or the
clean-audit record) back on-record so the pass can record the disposition. (structuring issue #1245, per-lane
behavior folded via #791)

**The planner is the propagation hub — a finish is a trigger, not a log line.** The moment a lane's finish comment
lands (or a PR reaches fresh-head / merges to main), read it as evidence (branch, head sha, run id — never the
prose alone), and in the SAME pass route the dependent lanes onto that PR: post the routing comment naming which
lane(s) look now and why, then `message_agent` each named lane. A lane finish that ends the pass with nobody told
to look is a missed propagation, the same defect as an untriggered idle lane. Record the disposition on the issue
so the next pass does not re-dispatch a lane already on the vehicle. (issue #1194, owner 2026-10-31.)

**Security and architect opinions are solicited, never silently skipped.** On a fresh-head or a merge, classify
the change: touches a security boundary (auth, network egress, file/pipe writes, credentials, downloads /
`hub_open`) → `llgenie-security`; an architecture surface (pipeline shape, admittance/gates, engine-variant
coherence) → `llgenie-architect`; both → both. Write the classification into the routing comment (a reader must
see it was assessed, not assumed), dispatch the advisory lane(s) by `message_agent`, and they answer on-record
with a verdict or a reason they cannot — no unrecorded silence. The advisory is not a merge gate; approval stays
the owner's (#1088). (issue #1195, owner 2026-10-31.)

## Versioned from the live profile (issue #2084)

**"Why is this PR not merged?" has one wrong answer: "waiting on the owner."** Before you ever say that,
prove the merge machinery fires (find a recent `APPROVED` review plus its merge commit) and measure the
sweep's real cron rate, its cancelled share, and its per-run cap against the open-PR count. A green, armed
PR that sits unmerged is a **starved or blind retry path**, owned by the CI-pipelines lane — not an approval
gate. Reporting it as an owner gate both misleads the owner and hides a defect for hours. The measurement
commands live in `references/auto-merge-approve-and-handle-throttle.md`.
> Pointers: `references/board-work-cadence.md`, `references/merged-pr-stale-rebase-loop.md`, `references/merged-over-red-gate.md`, `references/actions-run-attempt-reconciliation.md`, `references/verifying-lane-claims.md`+`references/false-green-claim-check.md`+`references/red-signal-triage.md`, `references/board-binding-assignees-field.md`, `references/protected-instruction-write-approval.md` (the gate no dispatch can satisfy; the active profile's own home is EXEMPT — live is writable, the repo tree copy is not; never copy live→tree, the subset check; the 100k skill-writer cap), `references/ci-gate-vs-live-pipeline.md`+`references/ceiling-config-verdict-vs-defect.md`, `references/pr-closing-gate.md`, `references/pr-body-hygiene.md`, `references/pr-head-location-and-base-gates.md`, `references/domain-ownership-dispatch.md`, `references/incident-closure-and-board-mutation.md`, `references/actions-job-log-reading-midrun.md`, `references/second-gate-stale-base-and-stuck-run.md`, `references/pipeline-verify-matrix.md`, `references/settled-run-void-vehicle.md`, `references/byte-identity-verification.md`, `references/auto-merge-approve-and-handle-throttle.md`, `references/orchestrator-tick-contract.md` (tick = fleet's only scheduler: overdue `next_run`, ordered pass, failure-class table, stale-base treadmill, **both disk axes** (`df -i` can be 0 while `df -h` looks empty → every write fails), fork-vs-canonical poll trap, lane skill/SOUL drift audit, prompt-is-unversioned), `references/docs-and-architect-nudge.md` (nudge docs+architect EVERY pass; gaps live between the gates), `references/host-lane-precedence-over-ci.md` (host lanes first; red CI is evidence, never a repair target), `references/lane-gap-audit.md` (silent no-ops, unrunnable output, un-retryable aborts), `references/pass-contract-and-sweep.md` (12+12 sweep, triggering is the act of the pass, loop-escape, empty-queue audit, propagation hub), `references/change-note-gate.md`, `references/change-proposal-task-gates.md`, `references/nerve-guard-ghost-loop.md`, `references/measurement-hygiene.md`, `references/never-pushed-lane-audit.md`, `references/concurrent-red-classification.md` (before dispatching a second vehicle, `comm -12` the open PRs' file
sets — an all-`agents/*/SOUL.md` rule mirror collides with every open per-profile SOUL change; post a land order,
never cancel), `references/write-verification.md` (read back by exact id; never re-POST — dedupe by body prefix, DELETE extras), `references/engine-verification-binary-not-serving.md`, `references/acceptance-form-rule.md` (every issue AND every PR carries `## Acceptance criteria` as markdown checkboxes; CI validates both — owner directive 2026-11-05, carriers #1796/#1792), `references/rebase-at-worktree-start.md` (fetch+rebase before first edit; PROVE ancestry with `merge-base --is-ancestor`, a new sha is not a rebase; batch sweeps lose to a fast merge cadence — rebase-then-merge one at a time) (mandatory lane pre-flight: fetch canonical upstream main + rebase origin/main the worktree before first edit of every task, new issue/PR or update of existing, no exceptions — #1891; and re-judge-a-red-ci-verdict via workflow_dispatch vs the expired-job-record trap — #1886/#1889).
> A pass hands out the **open PRs** as well as the issues; a queued item is claimed with its place in line: `references/dispatch-and-handoff.md` (a `message_agent` ack is a CHAT hand-off and creates no board task — the durable dispatch is `hermes kanban create`; verify a spawn by its worktree branch, not by `running`). A freshly pushed head shows only its first wave of checks, and a red at a fixed sha flips on a re-run: `references/ci-state-and-queue.md`.
> Dedicated-issue repoint: `references/closes-target-repointing.md`. Report integrity: `references/report-integrity.md` — ids re-fetched, output pasted. Branch state: `references/branch-state-classification.md`.
move — never in "waiting".
**Check the tick itself FIRST.** Lanes are turn-based: they act on a dispatch then exit, so a disabled tick or an
overdue `next_run` on a live scheduler means the whole fleet is silent and looks identical to laziness. Probe it
before concluding any lane is idle — `orchestrator-tick-contract.md`.
The full pass contract lives in `references/pass-contract-and-sweep.md`: the 12-issue/12-PR sweep size, "triggering
is the act of the pass", the same-correction-twice loop escape, the empty-queue continuous-improvement audit, the
propagation-hub rule (a lane finish routes dependents in the SAME pass), and the solicited security/architect
advisory. Read it on any pass where the board looks quiet.
Then re-read `AGENTS.md` at that sha — ~90 KB / ~1,360 lines and growing; take the count from `git show origin/main:AGENTS.md | wc -c`, never from memory.
- **"No vehicle after N dispatches" usually means the vehicle exists and is red, not that the lane is dead.** Before
  dispatching a fix issue a fourth time, search for the branch/PR (`gh pr list --search '<issue-keyword>' --state all`,
  `gh pr list --limit 100 --json number,headRefName,title`) — a PR opened late under a differently-worded branch
  (`fix/<symptom-phrase>`) is the vehicle, and it is nearly always blocked on a cheap body/change-note gate rather than
  on the substantive code. The productive move is then an **attribution pass on that PR's head** (`ci-failure-attribution.md`
  §1/§1.5: step-list attribution, cheap-gate-skips-matrix) followed by one precise amend dispatch — not another
  issue-level dispatch that produces the same red a second time.
worktrees.** "They were mine" is not an exemption: a lane cannot read what a delete takes. Its "already merged" test
reads the branch REF, so a tree holding uncommitted work looks stale and the bot destroys the run it is standing in;
root-owned debris makes it exit non-zero having deleted only what it could reach. Two dangerous trees look like
housekeeping — one that needed `sudo`, one whose PR is **closed** ("PR closed" is not "tree empty"). Say which paths
are stale and stop there.

## A \"verdict=failure\" check-run on a main commit is not the main tip
When a commit's check-run list shows `verdict = failure` (or any bare check name), resolve the run's `details_url`/`HEAD_SHA` before treating it as a main-tip gate red. The `verdict`/`ci-verdict` workflow posts its check-run at the head it validates, which can be an **open PR's head whose base is that main commit** — not main itself. In the #1810 post-merge pass, three `verdict=failure` check-runs at tip `dde5c9ec` were ci-verdict reds on PR #1804's own head `91bc978` (a rebased vehicle), while the tip's push matrices (`42097055492`/`42097055412`) and its own ci-verdict (`42099122153`) were green. Attribute any verdict failure by reading the run's `pull_requests`/`head_sha` first, never conclude "main is red" from a bare check name in the commit list.
**A zero-count is a scan failure, not a fact — on contested attribution, read the full comment bodies.** At least once a grep/gh count returned `0`/empty on bodies that visibly contained the word, and the durable correction built on that zero was itself wrong (posted "no planner comment used phantom|fabricat" when the planner's *own* 23:45Z refutation had done exactly that a minute before withdrawing it). Attribution between two lanes posting under the same `andyholst` login cannot be settled by the author field — read the body verbatim and trust the self-identification inside it ("(planner, re-measured)"). Never post a correction that proves the *absence* of a thing from a probe that also returned empty for a thing that exists. **A correction against a lane's report is itself a claim and owes the same evidence bar: before flagging a reported fact as wrong, re-measure the *same fact* the lane names — on the surface that actually populates it, not merely a second surface.** A field that is null on one API while the fact is live on another is the same trap: REST `.auto_merge_request` reads null for an *armed-and-waiting* PR (it populates only as a merge fires), so "arm null ⇒ not armed" flags a healthy state; read the GraphQL `autoMergeRequest` before contradicting an "armed" report.
A successful API call is not a landed document: check shape and length, and never trust `.[-1]` as "the newest
comment". Recipes, the exact commands, and the failure modes: `references/write-verification.md`.
**Preflight shared-space before dispatch, every time — not reactively.** `df -h /tmp` + `df -i /tmp` before dispatching or placing a heavy worktree; below ~20% space OR ~50k free inodes, refuse to spawn a /tmp consumer and escalate to the owner with the df figures. Heavy worktrees go on real disk not /tmp; a large probe tree is its owner's to clean, never hostage the shared tmpfs. Cleanup of /tmp is an OWNER decision (educate via `du -sh /tmp/*` + df), but identifying the occupant is the planner's job. See `references/host-space-hygiene.md`. The lesson dropped the implementer's wedge + reviewer ENOSPC on 2026-11-02 — this is a real, gated-less hazard.
