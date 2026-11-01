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

## A git blob id and a content sha256 are different namespaces — byte-compare, never cross-hash

A fold is verified by BYTES, not by putting two 8-hex strings side by side. `git rev-parse <ref>:<path>`
returns the blob's git object id (SHA-1 of `blob <size>\0<content>`); `sha256sum <file>` returns a SHA-256
of the content. The same file yields two unrelated tokens — a recorded content sha256 like `93ab714e` and
the git blob `8527504c` are equal content that merely hash differently. Do NOT read that as drift.

Prove equality the one way that is real: `git cat-file blob <blob>` piped against `cat <LIVE>/<path>`
compared as bytes (or run `sha256sum` on BOTH sides — the same function). If bytes match, the fold is
correct regardless of which short token each side printed.

## Fold the CURRENT live content, not the sha the dispatch quoted

Live accretes between when a dispatch measures it and when you branch. Measured shape: a dispatch named
`ae92d0b8`/29,525 B for a reference file, but at branch time live was already `93ab714e`/30,082 B (+557 B).
A blob cannot be partially folded, so fold the live content you hash AT BRANCH TIME and report the drift
to the planner — binding to the stale dispatch sha would push a truncated copy that reds `CHECK=1`.

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

## A `CHECK=1` rc=1 during a fold usually names a DIFFERENT file — attribute it, do not widen the PR

You fold your vehicle's files live→tree byte-identical, re-hash both sides (they match), yet
`make sync-agent-profile PROFILE=<n> CHECK=1` still exits rc=1. Do NOT read that as "my fold is wrong"
and do NOT pull the extra file into this PR. The check compares EVERY tracked file, so the rc=1 is
naming some OTHER file that is live-ahead — it is a separate residual and belongs to its own vehicle.

Measure which file before deciding anything: run the check verbosely (or
`python3 scripts/agent_profile_sync.py --profile <n> --check`) and read the `TRUNCATED?`/`live-longer`
line — it names the diverging path and both sizes. Then confirm YOUR files are clean at the head
you will push (`git cat-file blob <head>:<path> | sha256sum` == `sha256sum < "$LIVE/<path>"` for each
path you folded). If your files match and the rc names a file outside your fileset, that file is the
NEXT round's vehicle: record its size delta, keep ONE fold vehicle in flight (live is monotone
accretion, so folding it here duplicates what a later PR carries), and say in the PR body which file
the residual is and that it is out of this vehicle's scope.

Measured shape: a versioning-only fold of two SKILL/reference files matched live exactly, while
`CHECK=1` red on a third, unrelated doc that had grown live-ahead — correct move, leave the third doc
for the next vehicle and report it as such.

## Close wiring belongs in the PR body

A `Closes #<n>` / `Fixes #<n>` keyword in the BODY is what auto-closes; a title saying "closes #N" and
prose saying the work "closes" the issue close nothing. When a merge leaves the issue OPEN, that is the
gap — say it, cite the merge commit as the anchor, and either edit the body (open PR) or close the
issue yourself with the merge-sha evidence (merged PR). New vehicles put the literal keyword in the
body from the start.
