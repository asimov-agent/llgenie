# When to use the orchestration skill, and the shape of a pass

Moved out of `SKILL.md` to keep its always-on body under the 100,000-character skill-writer limit
(issue #2084). Same rules, verbatim.

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

