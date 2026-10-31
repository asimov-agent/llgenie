# The llgenie workflow map (snapshot of `main@7937398`)

This is a SNAPSHOT, not the authority: the repo gains and renames workflows, and this table cannot
notice. Regenerate the parts that matter instead of trusting it —

```bash
ls .github/workflows/*.yml | wc -l        # the row count this table should match
python3 scripts/check_workflows.py check  # the reactor roster must name every one of them
```

— and add a row when you add a workflow, because the map is what tells the next session which legs
exist at all. `consumer` = the `workflow_run.workflows` entry that watches it (the run-failure reactor
unless noted).

| file | trigger | cron / event | consumer |
|---|---|---|---|
| `architecture-bot.yml` | schedule + dispatch | `47 */6 * * *` | reactor (added in #780) |
| `auto-merge.yml` | `workflow_run<CI>` + schedule | `3,33 * * * *` | reactor (added in #780) |
| `ci.yml` | `pull_request`, `push` | — | the merge gate; calls `pipeline.yml` |
| `code-review-bot.yml` | schedule + dispatch | `31 7 * * 1` | reactor |
| `engine-build.yml` | dispatch only | — | reactor (added in #780) |
| `engine-bump-rebase.yml` | schedule + dispatch | `41 5 * * *` | reactor |
| `engine-bump.yml` | schedule + dispatch | `53 6 * * 1` | reactor |
| `fix-bot.yml` | schedule + `workflow_run<CI>` + dispatch | `17 * * * *` | reactor |
| `issue-bot.yml` | `issues: [labeled]` + schedule + dispatch | `23 6 * * *` | reactor |
| `issue-dedupe.yml` | schedule + dispatch | `51 */6 * * *` | reactor (added in #780) |
| `issue-refiner.yml` | schedule + dispatch | `43 * * * *` | reactor |
| `pipeline.yml` | `workflow_call` | — | reusable leg, run counted under `ci.yml` |
| `publish-agent-image.yml` | dispatch only | — | reactor |
| `published.yml` | `workflow_call` | — | reusable leg |
| `queued-alarm.yml` | schedule + dispatch | `7,37 * * * *` | reactor |
| `rebase-bot.yml` | schedule + dispatch | `29 */6 * * *` | reactor (entry was stale until #780) |
| `registry-sync-review.yml` | schedule + dispatch | `55 * * * *` | reactor (added in #780) |
| `registry-sync.yml` | schedule + dispatch | `19 5 * * 1` | reactor |
| `run-failure-reactor.yml` | `workflow_run` on 19 names | — | skips itself (self-trigger loop) |
| `search-smoke.yml` | schedule + dispatch | `11 7 * * *` | reactor (added in #780) |
| `security-bot.yml` | `issues: [labeled]` + schedule + dispatch | `9 5 * * *` | reactor (added in #780) |
| `security-scan.yml` | schedule + dispatch | `5 4 * * *` | **exempt by design** — `make security-issues` + `security-bot` own its red |

## Legs and their owners

- **Implementing:** `issue-bot` (one `agent:implement` issue per run) → `fix-bot` (repairs a red PR) →
  `rebase-bot` (keeps PRs current) → `auto-merge` (squash-merges a green, conflict-free PR).
- **Deciding:** `code-review-bot` (one issue per finding, weekly), `architecture-bot` (rewrites
  `docs/ARCHITECTURE.md`, 6-hourly), `issue-refiner`, `issue-dedupe`.
- **Supply chain:** `security-scan` (daily, gates on `fail_on`), `security-bot` (one auto-fixable
  advisory → PR), Renovate (pins forward), `engine-build` (every engine at its pin).
- **Registry:** `registry-sync` (weekly PR from the vendored store) → `registry-sync-review` (green
  sync PR → one `agent:implement` issue) → `engine-bump` / `engine-bump-rebase`.
- **Watching:** `run-failure-reactor` (routes), `queued-alarm` (queued too long), `search-smoke`
  (real web reach, daily).
