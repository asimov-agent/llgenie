# #1463 — landing the missing change-record trio for the merged #1413/#1460 (#1123)

Planner reroute (2026-11-01) filed #1463 and dispatched it to the ci-pipelines lane. Gap: #1413's
code merged as #1460 (`2ae46fb8`, closes #1413, COMPLETED) but the merged head `2c7cbac3` lacked the
change-record trio — CI scope redded the change->note rule (#1123) because the behavioural
`docs/BOTS.md` help-text edit carried no agent-wiki note. **LANDED + CLOSED 2026-11-01:** PR #1466
MERGED (auto-merge, asimov-agent, 21:52:35Z), scope run `41354112931` SUCCESS at head `096302ca`
(ci-lint + check-docs + check-wiring + check-issue-bodies + check-pr-closing + openspec all green),
merge commit `c2d118d4` = exactly the trio. #1413 stays COMPLETED; merged #1460 untouched.

## Root cause of the first scope red (important)

The FIRST red (run `41352907444`) was NOT check-docs — it was `make ci-lint` (the markdown linefeed
gate): `LINT FAIL — files missing a trailing newline` on the two new .md files, and lint failure
SKIPS check-docs/check-wiring. Remedy: `python3 scripts/lint_linefeeds.py --fix` (host, bare, no
args), verify `LINT OK`, amend the single atomic commit, re-push. This is the recurring `write_file`
drops-trailing-newline trap surfacing as a CI lint red, distinct from the change->note rule.

## Wrong-remote push near-miss (never repeat)

- `origin` = fork `andyholst/llgenie` (where PR-head branches push). `upstream` = canonical
  `asimov-agent/llgenie`. `git remote -v` before any force-push.
- Force-pushing the WORK branch to `upstream` creates a stray canonical branch AND does NOT move the
  PR (the PR head reads the fork). If done: re-push to `origin` (`--force-with-lease` after a fresh fetch
  ), and `git push upstream --delete <branch>` the stray.

## Acceptance (planner reroute 6564149046)

sole PR `Closes #1463`; trio lands GREEN at PR head on main; #1413 stays COMPLETED; no rebase of
merged #1460; bot-claim first line + PR number named back. Arm auto-merge only when done (#1088).
