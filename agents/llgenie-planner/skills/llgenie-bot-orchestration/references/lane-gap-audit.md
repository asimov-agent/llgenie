# Lane-gap audit: silent no-ops, unrunnable output, un-retryable aborts

Hunt for these when the owner asks "any other lane gaps?" — a bot that reports `success` while
doing nothing is invisible on the board, so probe the CLASS, not one lane.

## The three gap shapes

### A. Classifier blind spot: a state label masks the real condition
A sweep that classifies on `mergeStateStatus` alone sees only `BEHIND`/`DIRTY`. GitHub reports
**`BLOCKED` — never `BEHIND` — the moment any check reds or a review is pending**, so a stale-AND-red
item classifies as nothing-to-do and is silently skipped, forever. Grep the classifier for
`merge-base|is-ancestor|ahead|behind|rev-list`: **if there is no call site, the bot never measures the
condition it claims to fix** — it only reads the platform's label.

**Detection:** compare `git merge-base --is-ancestor <base-tip> <head>` across every open item. If heads
are uniformly stale while `mergeStateStatus` is uniformly `BLOCKED`, the classifier is blind.
**Proof of the no-op:** the run concludes `success` and its own Report step prints a zero count
(`rebased: 0`, `0 updated`).

**Check the deadlock's second half too.** A coexistence rule written as
`if red and state == "BEHIND": … the other bot owns that` only fires on the literal string a red item
never reports — so the item is owned by NEITHER lane. The second lane typically repairs content, never
branch lineage, so it cannot clear a base-freshness gate however many times it re-runs (`success` every
few minutes, staleness unchanged). Both halves must be fixed together or the deadlock persists.

### B. Output that cannot be acted on: a template field carries the wrong value
A bot that files issues filled its `**run:**` field from `displayTitle` (the commit title) instead of
the run `id`, so the issue's own suggested command was unrunnable and the line duplicated `**workflow:**`.

**Detection:** for any bot that files issues or PRs, open one and actually run the command it prints. A
field that should hold an identifier but reads like prose is the tell; compare against the REST object
(`actions/runs/<id>`) to see which field really carries the id. The failure is self-concealing — the
issue looks complete because the line exists.

### C. One un-actionable item aborts a whole sweep
A requeue sweep skipped un-retryable runs only for one event type, but another event's cancelled runs are
equally un-retryable (`This workflow run cannot be retried`), so `gh run rerun` failed and the sweep died
instead of recording the item as skipped — red on every schedule tick.

**Detection:** pair a lane's failure runs and diff the ids they name. Same message, different ids,
recurring on schedule = a per-item abort, not a one-off. **The fix is always "record it in `skipped`
with a reason", never "retry harder".**

## Negatives worth checking before you file (avoid the false gap)

- **A never-run workflow is often legitimate timing.** A zero-run workflow that merged the previous
evening can look like a dead alarm; compare the merge time against its cron's next slot before filing.
- **`skipped` is usually correct**, not idleness — a repair bot skips when no eligible failing item
  exists.
- **Cancelled runs with 0 jobs** lost no work (killed in the pending slot). They halve throughput but are
  not a dropped task — say which it is.

## Probing method that found all three

Enumerate every workflow (`gh api repos/<o>/<r>/actions/workflows --jq '.workflows[]|…'`), then for each
pull its last 3-5 runs and read the **conclusion distribution**. A lane whose runs are all `success` is
either healthy or a silent no-op — the tiebreaker is its own report step: read the log line that
summarises what it did, and check that summary against the board's actual state. **A summary that
contradicts the board is the gap.**

File each gap as a six-section issue in the owning lane's domain (the pipelines lane owns `scripts/` +
workflows), with the measured run ids and the exact bug line. Where a generic reactor-filed issue
already exists ("failed in job X"), **pin the root cause as a comment there rather than opening a
near-duplicate**.

## Before filing a new issue for a red run: match the failure signature

The owner will hand you a run URL and expect an issue. Sometimes the right answer is **"already dealt
with"** — and the way to know is to match the run's *numeric signature* against open issues, not its title.

1. Read the failing job's **own log** and extract hard numbers plus the assertion: pass/fail counts, the
   failing test id, the `E   At index N diff:` line. A `conclusion` (`failure`) is a verdict, not a cause.
2. Search open issues for those numbers — a well-written issue body quotes its evidence, so
   `gh issue list --state open --search "<n> failed <m> passed"` frequently hits the exact issue. Confirm by
   reading its `## Problem`: same test id, same root cause, same introducing commit.
3. If it matches, report the match with its state and whatever still blocks it (e.g. an armed fix whose
   last gate is pending) and **do not file**. Filing a duplicate of a tracked, proven, in-flight fix is a
   defect, not diligence.
4. If it does not match, file the six-section issue.

A merge-to-main-only gate (network/live suites) reds main invisibly to every PR check, so one failure can
sit unowned across many consecutive main tips while its fix waits armed. Name that monitor gap when you
find it — it is separate from the failure itself.
