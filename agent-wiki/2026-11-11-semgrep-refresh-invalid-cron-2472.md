# Semgrep refresh ships a parseable cron; workflow-cron gate (issue #2472, PR #2500)

`.github/workflows/semgrep-rules-refresh.yml` shipped cron `1 6 * * 15` — `15` in the
DAY-OF-WEEK field (max 7). GitHub refuses to COMPILE the whole file for an unparseable
cron: measured, every `workflow_dispatch` to it answers `422 failed to parse workflow:
invalid cron attribute "1 6 * * 15"`. The Actions router still routes every push/PR event
to the registered workflow record, so each one became a 0-job `startup_failure` ghost
named for the file PATH — 186 measured — and each ghost posted a `ci-verdict` check with
`conclusion=failure` on the commit it landed on (check-run `129703887478` @ `5b7b27d4`),
silently polluting PR heads. A control experiment proved the anomaly is unique to this
file: every other schedule+dispatch-only workflow has zero push/PR runs.

## Decision

Fix the cron to `17 6 15 * *` (monthly on the 15th, 06:01 UTC — same odd-minute intent,
written in the field GitHub reads) AND add a `workflow-cron` rule to
`scripts/check_workflows.py`: a stdlib parser over GitHub's five-field grammar
(minute 0-59, hour 0-23, day-of-month 1-31, month 1-12, day-of-week 0-7 or SUN-SAT;
comma-lists of `*`/value/`lo-hi`, optional `/step`). PyYAML and the existing expression
guard both accept the broken file — only GitHub's cron parser rejects it, so the gate must
speak GitHub's grammar, not YAML's.

## Verified

- Control + fix against GitHub itself: dispatch at the broken fork main → `422 invalid
  cron attribute "1 6 * * 15"`; dispatch at the fixed head → accepted, a REAL `refresh`
  job with real steps ran (run `43073777356`) — the first healthy run this workflow ever
  produced (its fast failure is the fork lacking the lane's secrets).
- New rule over the tree: all 29 shipped crons pass; the bad value rejects; fixtures for
  steps/lists/weekday-names/ranges and every out-of-bounds class behave per GitHub's table.
- 122 tests green across every module importing `check_workflows`; `make check-workflows`,
  `check-wiring`, `lint`, `openspec-validate` green; `lane-preflight` OK.

## Current status

Branch `feat/2472-semgrep-ghost-runs` → PR #2500 closes #2472. Post-merge follow-ups
recorded on #2472: re-measure "no push-ghost at a fresh main tip", then rebase the
already-open PR heads cut from the broken main so their heads carry the parseable file.
