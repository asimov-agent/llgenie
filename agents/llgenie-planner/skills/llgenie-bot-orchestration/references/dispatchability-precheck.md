# Dispatchability precheck: is this issue routable, and is this gate one blocker or many?

Measure before you dispatch. A vague issue burns a full implementer run and returns a PR nobody can review; a
partly-red gate declared "waiting" parks a lane that had work available.

## 1. The four-point structural probe (run it, do not eyeball the title)

An issue is dispatchable only if all four hold. One `gh api` + one `git ls-remote` answers all of it:

```python
import re, subprocess
b = i['body'] or ''
print('sections:', re.findall(r'^##\s+(.+)$', b, re.M))          # six-section shape?
print('boxes:', re.findall(r'^- \[([ xX])\]', b, re.M))         # acceptance criteria?
print('assignees:', [a['login'] for a in i.get('assignees', [])])
print('labels:', [l['name'] for l in i['labels']])
print('comments:', len(comments))
subprocess.run(['git','ls-remote','--heads','origin','*<n>*'])   # branch already started?
```

Zero `##` sections and zero `- [ ]` boxes means **refine, never dispatch**. A branch that already exists means
the lane has started (check for a PR too — commits without a PR is the common stall, not "unstarted"). Zero
comments plus an old `updated_at` means nobody has touched it, so any "someone has that one" belief is your
inference, not a fact.

## 2. Owner-assigned is not unassigned

An issue assigned to the owner, or carrying owner-authored text, is not yours to re-scope. Refine it **as a
comment** in the six-section shape — never rewrite their body — and close the comment with the escape hatch:
if they intend it to stay owner-held rather than dispatched, say so and you leave it untouched. That keeps the
refine a refinement instead of a takeover.

## 3. A gate criterion of "the sweep is green" is a SET of blockers, not one

When an acceptance box reads "the whole matrix passes", enumerate **every** failing cell and route each
separately; fixing one is not the gate. Record the blockers as a named set on the tracking issue so the next
reader sees "needs A and B" rather than "needs a fix". A criterion that silently absorbs a second known red is
exactly how a PR sits green-looking and unmergeable.

Corollary: a blocker you find late is presumed *unrouted* until measured. Check its actual board state
(open/assigned/labelled/branch/comments) before assuming "someone has that one" — long-lived blocker issues
are often structurally undispatchable precisely because everyone assumed they were being handled.

## 4. Route by the failing LEG, not by the workflow name

One matrix workflow carries several unrelated red classes that fail at different points, with different owners
and different remedies:

| failure leg | signature | owner class |
|---|---|---|
| build, registry/cache | cache image `not found` + `403 Forbidden` on pull,push | pipeline/CI config lane |
| build, resources | `exit 143` / OOM / SIGTERM mid-build | engine or builder lane |
| serve readiness | `... not ready after Ns`, fires from a `test-published-*` make target | implementation lane (runtime/product) |
| build, timeout | cell cancelled after a multi-hour cap | builder lane (bound/probe question) |

Assign from the leg. Posting "the build is red" at the CI lane when the build succeeded and the *serve* leg
timed out sends a lane to edit the wrong file.

## 5. Aggregate conclusion is never a cell verdict

A run concluding `failure` says nothing about a specific in-progress cell, and a workflow that routes to a
sweep matrix reports the matrix's aggregate, not per-cell truth. Read the job's own `conclusion` by job id.
A job that fails *by design* on a wait/timeout (a poll with a fixed ceiling) makes the aggregate CI conclusion
meaningless for every other cell on that run. Two live consequences:

- When a lane reports "run concluded failure", ask which **job** it read. If the answer is the run, the finding
  is not yet a finding.
- Before accepting a lane's red or finding, confirm its **head epoch**: if the branch has moved, the run it
  policed may no longer exist on that branch, so the finding is about a superseded tree. Measure the current
  head, list its own runs, and correct the lane with the live channel rather than relaying a stale red upward.

## 6. Reactive diagnostic work supersedes a continuous-improvement audit

When an operational lane (CI, security, docs) is running its own-domain audit and a reactive defect in that
same domain is found, the reactive defect wins. Word the switch as **"the audit is paused, not cancelled"** and
name when it resumes — otherwise the lane treats the audit as abandoned and its findings go stale.

## 7. State the hand-back boundary in the dispatch

An operational lane fixing a defect often has the right to act but not the right file. Name the in-scope
surface and the exact condition under which it must stop and hand back — e.g. "if the cause lives in the
product script rather than the workflow config, hand it back with file:line instead of editing product code
from the pipeline lane". Without that clause, a config lane edits a module it does not own and the diff arrives
unreviewable.

## 8. When evidence overturns your own posted record, retract it on the wire

A correction that exists only in chat does not exist for the next reader. Post an explicit retraction naming
your own comment id and the measurement that overturned it. Never edit or delete the wrong comment — the trail
is the point, and lanes may already have acted on it.

## 9. Say which red you are NOT fixing

The dispatch that names the neighbouring defect and its owner ("the serve leg is a different issue with a
different owner; fixing this alone does not green the sweep") is what stops a lane reporting a gate closed it
did not close.
