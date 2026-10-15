# The queued-run alarm now reports somewhere a human reads (#294)

## Why

The alarm exists because a job whose label matches no runner does not fail — it stays `queued` forever,
the run never concludes, and every PR sits BLOCKED with no signal (#254). The sweep found those jobs
correctly, but its `--comment` half posted to `/repos/{repo}/issues/{run_id}/comments`, and **a
workflow run id is not an issue number**: the POST 404'd, the result was discarded, and the job exited 0.
The alarm reported into the void while looking green, and the dedupe read failed the same way, so
"comment once per run" could not hold.

Measured on `main@472de9f`: `gh api /repos/asimov-agent/llgenie/issues/<run id>` →
`{"message":"Not Found","status":404}`.

## What landed

- **A real subject.** Run → the PR its HEAD BRANCH belongs to, commented through the issues-comments
  endpoint (which serves a PR number); a run no PR tracks (schedule/push) falls back to **one open issue
  per stuck runner label**, because a missing runner is a property of the label. Both shorter routes were
  measured live and do not work: `gh run view --json` has no `pullRequests` field ("Unknown JSON field"),
  and the REST run object's `pull_requests` is EMPTY for a fork-PR run — the shape this repo's runs have.
- **Markers that name their subject.** `<!-- queued-run-alarm: run <id> -->` on the PR (a NEW stuck run
  is still news) and `<!-- queued-run-alarm: label <label> -->` on the fallback issue.
- **A loud delivery.** Every POST/create checks its return code; failures print `DELIVERY FAILED: …` and
  the process exits **3** — the old exit 1 could not be told apart from a successful report.
- **`--dry`** (and `make queued-alarm DRY=1`) prints what would be posted and posts nothing.
- The make help line, the README alarm line and the workflow step name now state the delivery.

Exit codes: 0 nothing stuck · 1 stuck · 2 the GitHub read failed · 3 stuck AND the report did not land.

## Verification

- `tests/test_queued_run_alarm.py` — **19 passed** in `llgenie/test:latest`; the stub `gh` answers the
  REST run object and `pr list --head`, and records every mutating call so the TARGET is asserted, not
  just the count.
- **Falsified first**: the same tests against the pre-fix script (`git show origin/main:scripts/…`) give
  **8 failed, 11 passed** — the PR target, the head-branch resolution, the fallback issue, the loud exit 3,
  `--dry` and the marker contract all fail on the old code. A test that passes on both trees proves nothing.
- **Live**: `run_prs('asimov-agent/llgenie', 38761102690)` → `[277]` and `…, 38731475236` → `[170]`, and
  `make queued-alarm REPO=asimov-agent/llgenie DRY=1` reports the live queue (nothing stuck right now)
  without posting anything.
- `make openspec-validate NAME=queued-alarm-delivery`, `make lint`, `make check-docs`, `make check-wiring`.

## Still open

- **#254**: this change makes the stuck queue visible; it does not add the missing runner (a
  repo-settings/hosted-runner decision).
- **#296**: the code-review bot's inline-script check exempts a whole step block, so `registry-sync.yml`'s
  inline script still is not reported by any gate.
