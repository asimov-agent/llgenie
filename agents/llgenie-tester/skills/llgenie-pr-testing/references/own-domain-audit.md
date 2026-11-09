# Own-domain audit dispatch (the tester's continuous-improvement round)

When the planner dispatches "audit your own domain" (an idle-capable lane must not wait), the
deliverable is a **ready-for-review PR that closes the audit tracker issue**, not a comment.

The tracker issue's acceptance criteria are fixed and identical each round:

1. every open `agent:refined`/`agent:implement` issue's criteria carry an executable verification
   path (a workflow/run id, a `make` target, or a unit test) named **on that issue's thread**;
2. the last ~10 merged PRs' ticked criteria are measured, with the count **ticked without a named
   run id** reported;
3. genuine findings filed as refined six-section issues, or the record `re-audited at <sha>, no findings`.

## Procedure

1. **Claim on the issue, then branch off fresh `origin/main`.** Post a `bot-claim:` comment naming
   the branch and the plan; cut a worktree with `git worktree add -b agent/issue-<n>-<slug> <path> origin/main`.
2. **AC1 — measure the real thread text, not a guess.** For each open issue, pull the body plus all
   comments and count occurrences of `make <target>`, `tests/test_*.py`, `run=<id>`. An issue with
   zero hits is the genuine gap: annotate it with **targets that exist** (`make sync-registry`,
   `tests/test_registry_keys.py`, …) — verify each name in the tree first; inventing a target is a
   false criterion. Note which issues already carry a prior round's annotation and say so instead of
   re-annotating.
3. **AC2 — measure, do not sample.** For each of the last ~10 merged PRs, read the linked issue's
   body and count `- [x]` ticks vs ticks carrying `run=`/`proven:`/a workflow-run citation. Report a
   table and the single number: `ticked-without-named-run-id = N / total ticks`. State the counting
   rule beside the number so a reader can reproduce it.
4. **AC3 — file, or record clean.** One genuine class of gap per issue; if none, the clean line is
   `re-audited at <sha>, no findings` naming the sha you measured at.
5. **Ship the record.** A docs-only PR: `agent-wiki/<date>-<slug>.md` note + `docs/changes.d/<stem>.md`
   fragment + regenerated `CHANGES.md` (`make changes-index`), gates `check-docs`/`check-wiring`/`lint`.

## Pitfalls

- **The scope gate will red on this PR by design, and that is the correct state.** The PR closes the
  tracker issue whose boxes the audit itself satisfied, but ticking is reviewer-gated — a tester never
  self-ticks. `check-pr-acceptance` therefore reds with "closes the issue whose acceptance criterion is
  unchecked". Report it as the expected pre-review hold naming the reviewer write-back that clears it;
  do **not** hand-tick the issue to go green.
- **"No findings" is a real outcome, and re-listing an already-closed finding is a stale-record bug.**
  Before listing a prior finding as "still open", re-read its state — a merged vehicle closes it, and
  the pass must record it closed rather than repeat it.
- **A prior round's annotation is evidence, not a fresh gap.** Search each thread for the earlier
  audit's marker before counting it missing; re-annotating doubles the comment trail and reads as work.
- **The audit produces issues, never fixes.** Filing a finding is in scope; changing a script, test or
  workflow is not — that belongs to the owning lane's queue through the normal issue.

## Reporting

Bookend start and finish on the tracker issue with the main sha; report `audited sha + outcome +
issue number(s) or the clean line` to the planner. Verdict posts name the run id and head sha.
