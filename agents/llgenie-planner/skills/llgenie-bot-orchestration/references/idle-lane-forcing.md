# Measuring lane quiescence and forcing own-domain audits

## The invisible idleness

The recurring orchestration failure is declaring "no idle-capable lane" while operational lanes sit with
empty reactive queues. The mistake is conflating *"no open implementable issue exists"* with *"no lane is
idle."* Those are different facts. A security/docs/ci/engine/reviewer/rebase lane whose reactive queue is
empty is **idle-capable right now** — and per the continuous-improvement contract an empty queue is not
done, it is the trigger to force the lane onto a bounded audit of its own domain.

## The per-pass measurement

On every pass, answer "which lane is idle-capable RIGHT NOW" — not only "which lanes are busy." For each
operational lane, ask whether its reactive queue has been empty for 2+ consecutive passes:

```bash
# reactive work for a lane = open agent:implement issues routed to it + its own open versioning PRs
gh issue list -R <o>/<r> --label agent:implement --state open --json number,title,assignees
gh pr list -R <o>/<r> --state open --json number,author,headRefName   # the lane's own lanes-version-their-rules PRs
# a lane's own vehicle lives on ITS tracking issue (agents/<lane>/ tree mirrors), not necessarily agent:implement:
gh pr list -R <o>/<r> --head 'fix/<lane-tracking-issue>-*'
```

Sweep the bot workflows too — `gh run list` per workflow, compare the newest run to the workflow's own cron.
A bot with no run in its slot, or all `skipped`, is idle regardless of what the board looks like.

## The forcing dispatch

For each lane measured empty, dispatch its own-domain audit — the lane's own domain, never another lane's,
and implementation always routes back through the normal queue:

- security: scan-coverage (vulnerability classes the scanner misses), dependency-pin validity
  (silently-unsatisfiable pins before they blow up), scan-rule-set freshness, admission-gate coverage.
- documentation: main-vs-docs alignment, skill-freshness (2+ releases old), change-note coverage.
- ci-pipelines: gate-coverage (failures current gates cannot see), workflow robustness
  (cancelled-mid-flight, stale-head races), step-sharpening.
- engine: engine-cell pin validity + serving drift.
- reviewer: review-process gaps.

Dispatch shape: name main at the sha you measured, list the audit axes for that lane's domain, require each
finding be filed as a refined six-section `agent:implement` issue (routed through the normal queue, NEVER the
auditing lane's own pass), and require a clean audit be recorded as `re-audited at <sha>, no findings` on the
lane's tracking issue. This does not override real reactive work — the sweep runs only when the queue is empty.

## Pitfalls

- **"Parked on a real gate" is not the same as "idle-capable."** A lane blocked on a producer's direct word
  or an un-merged base is *parked* on that one item; it is still idle-capable for any other unassigned,
  gate-free work in its own domain. Do not let "this waits on the gate" cover "so I do nothing." The audit
  is exactly the gate-free work it can do while parked.
- **Do not wait for the lane's own timer to fire.** The contract says force it, not hope its cron notices.
  A lane whose queue emptied hours ago and has posted nothing since is your under-delegation, not quiescence.
- **A clean audit is a valid outcome, but only stated explicitly** (`re-audited at <sha>, no findings`). Silence
  is indistinguishable from idleness on the board.
