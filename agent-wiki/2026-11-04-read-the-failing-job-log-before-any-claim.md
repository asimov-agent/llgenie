# Read the failing job's actual log before any dispatch or green/reviewable claim (#1721)

A check-run `conclusion` is a verdict, not a cause. On 2026-11-04 the planner pronounced #1719
"one clean re-run from owner-reviewable" while its heavy `linux/unit` row was still `in_progress`
and its log blob was NOT retrievable — it had not read the actual unit output, only the check-name
rollup (`success:13, failure:1, in_progress:1`) and a stale pre-body `ci-verdict`. Claiming
green/red/reviewable, or inventing a fix, without the failing step's own log burns a whole CI cycle
and risks a destructive push.

## The standing rule (owner directive 2026-11-04)

Read the failing job's **actual log** (run id + job id + head sha) and quote its error line **before
ANY dispatch or any "green/red/reviewable" claim**. When the log is unretrievable **mid-run** (run
still `in_progress`, so the endpoint answers "run is still in progress" / `BlobNotFound`), state
exactly *"error line not yet retrievable — unlocks at run completion"* and **never invent a cause**.
Never pronounce a PR reviewable or mergeable while a heavy row is unread; never read a stale
`ci-verdict` (an attempt-1 artifact) as current truth — wait for a fresh verdict at the CURRENT head.

## Why it is a rule, not a habit

A `success:13, failure:1, in_progress:1` rollup looks green enough to dispatch on, but the one
`in_progress` row is the heavy unit row whose result decides everything — and a verdict that has not
published its log cannot be quoted. The rule makes the *cause* the gate: you read the failing step's
own output and quote its error line, or you say the line is not yet retrievable. Either way the
claim is grounded in the log, never in the rollup.

## Where it lives

The rule is a standing rule in the fleet block — `agents/standing-rules.md` is the canonical copy,
and every `agents/<profile>/SOUL.md` carries the same block **verbatim** (issue #873 gate: a bullet
added to the canonical file and not mirrored is a `fleet-block-drift` finding, not a rule that
silently stops existing). It is mirrored into all 13 profile SOULs unchanged.
