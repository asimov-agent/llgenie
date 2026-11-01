# Fold residuals and cross-timed corrections

## Never claim "no residual" without a live re-measure in the same turn

Live accretes continuously and a fold lands a step behind it, so a fold merged minutes ago is already
behind. Measured instance: `main` SKILL `770d355` (97,752 B) vs live `2177a2b5` (98,431 B, +679 B) — a
real residual that existed while a lane was reporting "no drift / no residual tester fold open".

Rule: a closure claim (`nothing left to fold`, `no drift`, `the fold is current`) is a MEASUREMENT, not
a mood. In the same turn, hash the live file and the tree blob and quote both with sizes:

```
sha256sum ~/.hermes/profiles/<profile>/skills/<name>/SKILL.md
git show <head>:agents/<profile>/skills/<name>/SKILL.md | sha256sum
```

If you did not measure this turn, write `not measured this turn` — an unmeasured zero is exactly the
claim that draws a correction from the planner. Note that versioning blobs can stay equal while the
skill body has drifted: always compare per-file, never one aggregate "drift: none".

## A correction that arrives after you already did the thing is a timing crossing

Typical shape: the planner (or any partner lane) sends "X is wrong / here is the vehicle" for a fact
you measured, folded, opened and reported before its message reached you. That is not new work and not a
defect in your report.

- Answer it ONCE with the current measured state: PR number, head sha, base sha, the byte-equal proof,
the claim/bookend comment ids, and the run id.
- Name the report that already covered it (delivery id), so the other lane can reconcile instead of
re-deriving.
- Then STOP. Re-explaining the same facts on each retry of its message is a ping-pong that burns turns
and, worse, signals your reports are stale when they were merely faster.
- Only a correction whose FACT contradicts your measurement earns a fresh probe. Re-measure, then post a
correction naming both shas — never a silent edit.

## Close wiring belongs in the PR body

A `Closes #<n>` / `Fixes #<n>` keyword in the BODY is what auto-closes; a title saying "closes #N" and
prose saying the work "closes" the issue close nothing. When a merge leaves the issue OPEN, that is the
gap — say it, cite the merge commit as the anchor, and either edit the body (open PR) or close the
issue yourself with the merge-sha evidence (merged PR). New vehicles put the literal keyword in the
body from the start.
