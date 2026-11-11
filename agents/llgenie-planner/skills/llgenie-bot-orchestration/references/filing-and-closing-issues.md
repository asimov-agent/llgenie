# Filing and closing issues via gh CLI

Mechanics that cost a retry or two every time they are re-derived.

## `gh issue create` prints a URL, never JSON

This gh version has **no `--json`** on `issue create` (it errors with `unknown flag: --json` and dumps the help).
Capture the number from the printed URL instead:

```bash
url=$(gh issue create --repo asimov-agent/llgenie --title "$T" --body "$B" --label agent:refined --label component:container)
num=${url##*/}; echo "created #$num"
```

If the command returns without a URL, nothing was created — do not assume a silent success; re-list recent open
issues (`gh issue list --limit 5 --json number,title`) to confirm before filing a duplicate.

## Validate every `--label` before creating

A single nonexistent label **aborts the whole create**: `could not add label: 'component:engine' not found`
(exit 1, no issue). Label names vary per repo and drift — `component:engine` may not exist where
`component:container` does. Check first:

```bash
gh label list --repo asimov-agent/llgenie --limit 200 --json name --jq '.[].name' | grep -i '^component:'
```

The set that has existed: `agent:refined`, `agent:implement`, `component:container`. Confirm rather than guess.

## Long bodies: use `-F -` or a body file, not an inline quoted string

Backticks and `$(...)` inside `--body "..."` are evaluated by the shell. For a multi-section body use
`--body-file body.md` or `-F -` with a heredoc (quoted delimiter disables expansion).

## Auto-filed alarm issues: measure the named run, then close with evidence

Bots (`github-actions[bot]`) auto-file issues from alarms — e.g. `queued_run_alarm` files
"run <id> instantiates zero jobs and stays pending — no runner matched the labels". The alarm records a
**transient** state at filing time. Before acting on it:

1. Re-measure the exact run it names on the API:
   `gh api repos/OWNER/REPO/actions/runs/<id> --jq '{status,conclusion,head_sha}'` and
   `gh api repos/OWNER/REPO/actions/runs/<id>/jobs --jq '.total_count'`.
2. If the run has since **concluded with jobs**, the trigger condition has resolved and the issue's own
   acceptance criterion ("the run named below instantiates its jobs and concludes") is **met**.
3. Close it **with an evidence comment** naming the measured status/conclusion/job count and pointing at the
   issue that carries the real follow-up (the red cells, if any) — never close silently.

Do **not** treat a stale zero-job alarm as a live runner-capacity defect; the run usually outgrew the alarm
(capacity freed, queue drained). If the zero-job state is genuinely still true at measurement, route it to the
CI-pipelines lane as that lane's class rather than acting on it yourself.

## Separate the alarm from the real finding

A red acceptance matrix and a fired alarm are two different issues. The alarm ("run instantiated nothing")
can be closed as resolved while the matrix's failing cells are filed (or already tracked) as the real finding.
Keep them distinct so closing the alarm does not bury the finding, and filing the finding does not leave a
phantom pending-run issue on the board.
