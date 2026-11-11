# Diagnosing a bot run that is red, green-but-idle, or not firing

Use when a scheduled/dispatched bot in this repo misbehaves. Read the run's own output
before forming a theory: the decision line the bot prints (`action=busy`, `action=cap`,
`nothing to do`, `Refused: …`) names the cause in one line, and it is usually the same line
on every run.

## Read the failing step

```bash
gh run view <run> --job <job-id> --log-failed        # the failing step only
gh run view <run> --log | grep -E "\[bot-name\]|Refused:|Unknown|::error" | grep -v "36;1m"
```

The `grep -v "36;1m"` drops the echoed script from `##[group]`, which otherwise matches every
keyword you are filtering for and buries the real output.

## Read the bot's DECISION across runs, not one run

A bot that is green and does nothing prints its reason every time. Loop the last N runs and
extract that line:

```bash
for r in $(gh run list --workflow <wf>.yml --limit 20 --json databaseId -q '.[].databaseId'); do
  echo "$r: $(gh run view $r --log 2>&1 | grep -E '\[bot-name\]' | grep -v '36;1m' | head -2)"
done
```

If one condition appears in every run, it is a global gate, not bad luck: a bot that stands
down because *some* issue/label/PR exists is a permanent no-op as soon as that backlog is
permanent. Fix by scoping the yield to the specific subject (a live claim marker) and picking
the next candidate, never by loosening the schedule.

A queued label is not occupancy. Yield on a live claim (a marker carrying a run id that
`bot_claims.run_is_live` can check), otherwise a queued-but-untouched item starves the bot
forever.

## `workflow_run` workflows run the DEFAULT branch's copy

A `workflow_run` workflow executes the base branch's version of itself, so a fix to that
workflow cannot validate or land itself, and every earlier fix to it stays broken until it is
merged. Expect "the gate is still the old gate" when reading such a run, and say so in the
report instead of treating it as a failed fix.

## A fork run reports NO PR

For a fork `pull_request` run the REST run object's `pull_requests` array is EMPTY. Resolve the
PR from the run's `head_branch` + `head_repository.owner.login` (owner-scoped `gh pr list
--search "head:<branch>"`, matched on `headRepositoryOwner.login`) — `gh pr list --head
owner:branch` matches same-repo branches only and silently finds nothing.

## A 404 is not a value

`gh api` prints the error BODY on stdout when it exits non-zero, so
`n=$(gh api ... --jq '.x // empty' || true)` yields `{"message": "Not Found", ...}` — non-empty,
so a `[ -z ]` guard passes and the fallback never runs. Always:

```bash
n=$(gh api ... --jq '.x // empty' 2>/dev/null || true)
case "$n" in ''|*[!0-9]*) n="" ;; esac      # only digits are an id
```

and never append a value you have not proven to be one line to `$GITHUB_OUTPUT` — GitHub
refuses the file (`Invalid format '  "message": "Not Found",'`) and the step dies before the
real work starts.

## Validate `--json` field lists against real `gh`

A field `gh` does not have fails the whole call (`Unknown JSON field: "authorAssociation"`),
and a fake-`gh` test stub that ignores the requested field list hides it forever. When adding
or changing a `gh <cmd> --json` call, run it once against the live API before trusting tests,
and make the stub reject a field it does not know.

## A dispatch is made as the token's identity

`gh workflow run` creates a run whose `github.actor` is the identity of the token `gh` carried.
With the job token (`github.token`) that is `github-actions[bot]`, which the repo's trigger
guard refuses — the dispatched job dies in its own guard and repairs nothing. Pass the owner
PAT by environment variable name only (never argv, never a log line), and make an empty token a
LOUD failure (non-zero, name the variable) rather than a red no-op run.

## Cron is not cadence

`cron: "43 * * * *"` in the file does not mean the workflow fires hourly. Measure:

```bash
gh run list --workflow <wf>.yml --limit 20 --json createdAt,event -q '.[]|select(.event=="schedule")|.createdAt'
```

Compare the times to the cron minute and to the spacing. If runs land at random minutes with
multi-hour gaps, GitHub is delaying/coalescing the queue — report the measured cadence as a
fact and do not "fix" the cron to chase it.

## Every completed run of every listed workflow spawns the reactor

A `workflow_run: types: [completed]` reactor that decides in code (not in a job `if:`) also
runs on `success` and `cancelled`, printing "nothing to do". That is one wasted runner minute
per completed workflow. Gating the job on `conclusion == 'failure'` cannot silently skip a
failure, so it is compatible with the "decisions in code" rule.
