# Docs and architecture: two lanes that must be nudged every pass

Nudge the documentation maintainer and the architect every pass, so they update the docs and refine them to
fill any gap — not only when a gate reds.

Neither lane has a cron. Turn-based lanes act only when messaged, so **a pass that does not nudge them is a
pass in which the written truth of the repository cannot move** — however busy the board looks.

## Why "no red gate" is not "nothing to do"

`check-docs` fires only on a PR that touches a behaviour file. So these gaps are **invisible to CI**:

- a note that was written thin in a PR whose gate was satisfied by its presence, not its content;
- a doc that drifted because two separate merges combined into behaviour neither described;
- a skill that is two releases stale but whose file nobody touched;
- a structural change (lane boundary, `agents/` layout, pipeline shape, a gate's contract) merged with no
  `docs/ARCHITECTURE.md` or openspec update at all.

**Gaps exist between the gates.** That is the entire reason the lane exists; measure the window, do not wait
for a red.

## Nudge 1 — llgenie-documentation-maintainer, every pass

Measure first, then message. The message carries the numbers, not the instruction to go look.

```bash
make check-docs
git -C <repo> log --oneline origin/main -20          # the window since the last audit
```

For every merged behaviour change in that window, verify a **matching trio** exists:
`agent-wiki/<stem>.md`, `docs/changes.d/<stem>.md`, and the `CHANGES.md` index row. Then check alignment —
do `docs/BOTS.md`, `docs/ARCHITECTURE.md`, `docs/VISION.md` still describe what the tree does? — and
skill-freshness (any skill 2+ releases stale).

Report **counts**: merged changes N, notes present M, gaps N−M. Dispatch the gaps to be written. A clean
pass is recorded explicitly as `docs audited at <sha>, no gaps` — a silent pass is indistinguishable from a
skipped one.

## Nudge 2 — llgenie-architect, every pass

Ask whether a merged change altered a **cross-lane boundary**, the `agents/` layout, the pipeline shape, or
a gate's contract, without a matching `docs/ARCHITECTURE.md` update or openspec change. Enumerate open PRs
against open issues; file the structural gap it finds as a refined six-section issue and route the
implementation to the **owning lane** (the architect does not implement).

## Both, recorded on the board

A nudge is recorded as an **issue comment or a new refined issue**, never only in a DM — a DM is not a plan
(the same rule the parked-initiative planning follows). When a lane reports a clean audit, restate it with
the sha it measured and the counts, so the next pass can tell "audited and clean" from "never looked".

## A nudge is not compliance — verify the lane actually ran

Sending the message proves nothing about the audit. After nudging, measure whether the lane started, and
record which of three states it is in rather than counting the nudge as done:

| measured state | meaning | next action |
|---|---|---|
| a task exists and its worktree shows edits | working | wait for the counts |
| a task exists but is `blocked` | it needs a human (a protected write, a crash) | report the gate, do not re-nudge |
| no task exists at all | the message never became work | create the task, or use the board channel |

A lane blocked on a consent prompt has **not** audited anything, and re-sending the same nudge produces a
second identical block. Say so explicitly and name the unblock condition, so the next reader does not read a
blocked lane as a clean audit. "Nudged" and "audited" are different facts and only the second one discharges
the obligation.
