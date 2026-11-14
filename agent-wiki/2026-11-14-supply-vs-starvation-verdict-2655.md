# Supply-vs-starvation: a queue is not a verdict (issue #2655)

This change lands the supply-vs-starvation diagnostic rule that issue #817 proved and that PR #825
carried (closed unmerged by the owner) into the shared docs surface, `docs/BOTS.md`, where every bot
and human reader learns "what does a pending check mean". It is the one artefact of the #817 fix that
never landed: the measurement and path-gating are on `main`, but the written rule that stops the
misread was only ever in lane SOULs.

## What was verified

- Measured at `main` fc39b4180df before the change: `git show origin/main:docs/BOTS.md | grep -c 'A queue is not a verdict'` → 0 (the issue's own measurement, issue #2655).
- After the change: `docs/BOTS.md` carries a new section, **A queue is not a verdict — measure runner supply before any merge, rebase or cancel**, containing the sentence "**a queue is not a verdict on the PR it carries**" and a deliberate equivalent in the heading, so the #817 lesson is greppable at the merge sha.
- The section derives its wording from PR #825's verified measurements (18 runs `queued` / 0 `in_progress` on 2026-10-28; `ci.yml` `cancel-in-progress` on `pull_request` so a push re-queues the matrix) and #817's amendment, not from the issue prose. It is this lane's own proposal, not a revival of #825's exact diff.
- The ghost-queue shape (the issue's third acceptance criterion) is named: runs parked `queued`/`in_progress` **with no linked PR and a deleted head branch** (or expired job records) are a squat, not supply, and the section points at the sibling issue #2656.
- The note trio landed in the same commit: `agent-wiki/2026-11-14-supply-vs-starvation-verdict-2655.md` (this entry), its index row `docs/changes.d/2026-11-14-supply-vs-starvation-verdict-2655.md`, and the re-rendered `CHANGES.md` row (via `make changes-index`). `make check-docs` is green at the change's head.

## Decision taken

- Place the rule in `docs/BOTS.md` beside the existing starvation / `queued-alarm` material rather
  than trying to revive PR #825's exact diff, per the issue's `Not covered` (the owner closed #825,
  wording here is this lane's proposal).
- Do not touch the generated `<!-- dispatch-forms:` block — a paragraph inside it is overwritten by
  `make dispatch-forms-report`, so the note sits outside that block.
- Route was the `llgenie-documentation-maintainer` docs lane, per the #2073/#2270 ownership map, so
  this is a docs-only change; no script, test, make target or workflow is touched.

## Current status

Complete and self-contained: the rule, the note and the index row all landed, and the acceptance
criteria (greppable rule in `docs/BOTS.md`, note trio green under `make check-docs`, ghost-queue
signature named with its sibling issue) are met.

Implements #2655. Complements #817 (the fix whose written rule this is) and #2656 (the ghost-queue
sibling this rule points at).
