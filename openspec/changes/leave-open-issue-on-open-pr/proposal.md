# leave-open-issue-on-open-pr — proposal

Issue: [#2869](https://github.com/asimov-agent/llgenie/issues/2869)

## Why

On 2026-11-16 the issue-bot implementer lane claimed #2048, discovered open PR #2863 already
implemented it, and closed the **issue** with `state_reason=not_planned` instead of leaving it
for that PR. The generic close shape (`gh issue close --reason "not planned"`) was the only
close the triage skill prescribed — there was no way to say "an OPEN PR implements this, so
close nothing." PR #2863 merged 31 minutes later; its `closes #2048` was a no-op and the
implemented issue had been retired as "not planned" (hand-corrected to `completed` the same
evening). AGENTS.md: "NEVER close an issue by hand while a PR implements it. The PR closes it
on merge" — issue state must stay evidence about the code, and `not_planned` must keep meaning
"no plan".

## What Changes

- `scripts/issue_implementer.py`: add a distinct `hold` verdict to the machine-read triage,
  applied to an issue an OPEN implementing PR already covers and is awaiting merge. A `hold`
  does NOT close the issue, does not add `agent:closed`, does not open a PR: it abandons the
  lane's own claim (a `bot-done: ... held` marker) and posts ONE hold comment naming the PR, so
  the PR's own closing keyword closes the issue as `completed` on merge. A `close` now stays for
  the two real close reasons (duplicate / invalid / not-a-plan -> `not_planned`; a MERGED PR ->
  `completed`). A `hold` with no `PR:` block is refused.
- `agents/llgenie-planner/skills/github-issue-triage/SKILL.md` and
  `.hermes/skills/issue-triage/SKILL.md`: name the two close reasons and the leave-open rule
  explicitly, and teach the `hold` verdict shape.
- `scripts/issue_close_backfill.py` + `make issue-close-backfill`: a READ-ONLY report naming
  every issue the bot closed as `not_planned` that a MERGED PR carries a `closes #` reference
  to, so the reason can be corrected to `completed`. It reads GitHub only; it never PATCHes.
- Regression tests lock the `hold` shape hermetically and the backfill read against a fake `gh`.

## Not covered

- An automated PATCH of backfilled `state_reason` to `completed` — the read names the class; the
  correction stays a human or a future deterministic step (as #2048's was done by hand).
- Changing how a MERGED-PR close records its reason in `apply-verdict` (still `close`; the
  two-reason rule is in the skill text and the backfill covers the historical class).

## Acceptance criteria (the issue's, verbatim)

- [ ] An implementer/issue lane that finds an OPEN implementing PR leaves the issue open (claim
      abandoned + hold comment naming the PR), proven by a hermetic lane test
- [ ] The lane skill text names the two close reasons and the leave-open rule explicitly
- [ ] A backfill read names every bot-closed `not_planned` issue that a merged PR closes, and
      #2048 appears in that read with its corrected `completed` reason
- [ ] `make test-unit` passes with the new lane coverage
