# PR completion-step: the gates a "fix the closing keyword" misses

Context: a bot PR lands red on `check-pr-closing` only, and the implementer resumes to fix it.
The guard/scope job runs its gates SEQUENTIALLY and STOPS at the first red, so the later gates
never run and stay masked. Fix every one that applies before rerunning, or the rerun stops at
the next gate. These gates read the PR body (and the linked issue) LIVE via `gh api`
(issue #1589), so a body-only fix clears on `gh run rerun` of the SAME job — no push, no new run.

## The gates, in the order the guard job runs them

1. `check-pr-closing` — the claimed issue needs the same adjacent `closes #N` in the commit
   (squash text) AND the PR body. A subject ending `(issue #N)` or an `Issue: #N` line is a CLAIM,
   not a close: amend the commit message to append `closes #N`, not just edit the body.
   Verify: `check_pr_closing.py check --body-file <body> --base origin/main --rev <head> --head <br>`.
2. `check-pr-acceptance-form` — a bot PR body must carry its own `## Acceptance criteria` with
   `- [ ]` items. Missing section = red.
3. `check-pr-acceptance` (merge-time) — reads the LINKED ISSUE's LIVE body and requires each
   criterion ticked with provable evidence. Unticked issue criteria = red even with a green body.
   Tick via the sanctioned seam, never a hand-edit:
   `python3 scripts/acceptance_writeback.py writeback --issue N --proven 1,2,3 --verdict-ref '<cmd> rc=<n> <sha>'`
   (the `check` mode of `acceptance_writeback` requires BOTH a ticked and an unticked box — use
   `writeback`). The verdict-ref must carry `rc=<n>` + a `/^[0-9a-f]{7,40}$/` sha OR a `run=<id>`
   to satisfy `_is_provable_tick`.
4. `check-pr-agents-line` — a bot PR body must carry `AGENTS: <sha> <bytes>b <lines>l` + `BASE: <sha> (== origin/main at open)`
   where `<sha>` is reachable from BOTH head and base. `make bot-preflight` prints the exact lines.
5. `check-pr-sync-line` — a bot PR whose diff changes `agents/<profile>/` must carry
   `SYNC: <profile> make sync-agent-profile PROFILE=<profile>`.

All five (plus `check-pr-authors`) verify EXIT=0 locally against a saved copy of the live PR body
and the live issue — run them that way BEFORE rerunning the job.

## `check-pr-acceptance` reds guard/scope, and a red guard means NO heavy row ever runs

A PR that closes an issue whose `## Acceptance criteria` still carries `- [ ]` items reds
`check-pr-acceptance` in BOTH `guard` and `scope` — and `linux` / `ci-images` are `skipped` because guard
failed first. So **every CI run at every head is red and no `make test-unit` row exists**: say "the heavy row
never ran at any head of this PR", never "the tests pass in CI". The tick is verdict-gated (#1644), so an
implementing lane cannot self-certify: post the measured evidence per criterion on the PR, then route a
review card. If a criterion genuinely cannot be met, declare it under `## Not covered` — but the matcher is
narrow: the exemption must be a bullet LINE that both starts `-` and ENDS with `#N` (`^-.*\s*#\d+\s*$`) and
contains the criterion's leading three normalised words (``make sync-agent-profile …`` → `make sync agent`).
A prose bullet with the reference mid-sentence does not count — verify with
`check_pr_acceptance._declared_out_of_scope(body, criterion)` before pushing.

A deliberately red push is NOT a cheap sabotage proof: `run-failure-reactor` reacts to any failed run and
Route A dispatches the fix-bot onto the branch (a 4-hour `bot-claim` that tells every other bot to leave it
alone). Prove a gate with a local negative control (plant the bug, show the finding, restore) plus a unit
test, and cite those — do not manufacture a red run.

## A kanban PR task cannot complete while the PR is red

A card whose `completion_contract` is a repo refuses `kanban_complete` twice over: PR acceptance needs
`metadata.published_pr`, and the repo's exact-head CI must pass. When the red needs another lane (a review
verdict, a rebase), do not sit on it: `kanban_create` the follow-up **without** `parents` (a card gated on
your own task deadlocks — it never promotes while you are blocked), then `kanban_link(parent_id=<follow-up>,
child_id=<your task>)` and `kanban_block(kind="dependency")`. The task then auto-resumes the moment the
verdict lands, and the board shows the real blocker instead of an abandoned PR.

## Fast-advancing main: expect repeated stale-base reds before auto-merge lands
The unit job runs ~13 min and `check-pr-base` re-fetches LIVE `origin/main`, so every squash-merge
of another PR during the run makes the branch stale (`merge-base == base` fails, `base..rev`
non-empty) and reds it. This is the repo's own auto-merge working, not a defect. Rebase the branch
onto the newest `origin/main` (`git rebase origin/main`) and re-push with `--force-with-lease`;
repeat until a run goes green. The unit suite PASSING inside the red job's log is the evidence the
red is pure staleness — quote that when routing/reporting.
