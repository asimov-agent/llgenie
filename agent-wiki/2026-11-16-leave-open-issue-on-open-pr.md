# An OPEN implementing PR holds the issue open instead of closing it (issue #2869, PR _this branch_)

## What was verified against the spec

- `scripts/issue_implementer.py`: a distinct `hold` verdict (a new `PR: #<n>` block in the
  machine-read triage) applied to an issue an OPEN implementing PR already covers and is awaiting
  merge. A `hold` does NOT close the issue, does NOT add `agent:closed`, opens no PR: it abandons
  the lane's own claim (a `bot-done: … held` marker, added to `bot_claims.DONE_RELEASES`) and
  posts ONE hold comment naming the PR, so the PR's own closing keyword closes the issue as
  `completed` on merge. A `hold` with no `PR:` block is refused loudly and mutates nothing; a
  `close` is reserved for the two real reasons (duplicate / invalid / discontinued ->
  `not_planned`; a MERGED PR -> `completed`). Dry-run holds comment nothing.
- Hermetic lane tests in `tests/test_issue_implementer.py` (hold leaves open + names the PR +
  releases the claim; hold without `PR:` refused; `parse_verdict` reads `PR:`; dry hold writes
  nothing) and `tests/test_bot_claims.py` (the new `held` release) — green at the change head.
- `scripts/issue_close_backfill.py` + `make issue-close-backfill`: a READ-ONLY report naming
  every issue the bot closed as `not_planned` that a MERGED PR carries a `closes #` for, so the
  reason can be corrected to `completed`. Tests in `tests/test_issue_close_backfill.py` prove it
  names a not_planned closed-by-merged-PR issue (`NEEDS-CORRECTION`), reports an already-corrected
  issue (e.g. #2048) as corrected, skips human-closed and still-open issues, reads every closing
  reference, and exits 0 with nothing to correct — green at the change head.
- Lane playbook text names the two close reasons and the leave-open rule explicitly:
  `agents/llgenie-planner/skills/github-issue-triage/SKILL.md` and
  `.hermes/skills/issue-triage/SKILL.md` (both now carry the `hold` shape). `make
  check-agent-skills` OK.
- Gates at the change head: `openspec validate leave-open-issue-on-open-pr` rc=0;
  `openspec-tasks-check` rc=0 (all tasks ticked); `make check-wiring` OK (446 documents);
  `make check-docs` OK (355 user-facing targets documented); `scripts/lint_linefeeds.py` OK
  (the containerized `make lint` cannot run here — no docker daemon — so the lint script itself
  was run on the host). `make test-unit` green for the touched modules (57 tests across the
  implementer and backfill modules; the aggregate suite runs the ordinary test-unit path in CI).

## Key decisions

- A `hold` is a third outcome beside `refine` and `close`, not a third close reason: closing
  anything while an OPEN PR implements it is the defect (AGENTS.md: "never close by hand while a
  PR implements it"), so the verdict name and the deterministic action both say "do not close."
- The claim is released via a `bot-done: … held` marker inside the hold comment itself — one
  comment both tells the reader and frees the picker's TTL, matching how `refine`/`close`
  release through their own done markers.
- The backfill is a READ only: naming the class is the lane's first obligation, and correcting
  the reason stays a human or a future deterministic step (as #2048's correction was done by
  hand). It flags `not_planned`; an already-`completed` issue is reported as corrected so the
  read proves the remedy landed.

## Current status

Change uncommitted in the agent tree, PR body at `pr-body.md`, OpenSpec change
`leave-open-issue-on-open-pr` validated. This change fixes the closed loop; issues #2088, #2090
remain open work from the earlier sweep, and any backfilled mis-reason surfaced by
`make issue-close-backfill` is corrected by a human (`PATCH state_reason`) as #2048 was.
