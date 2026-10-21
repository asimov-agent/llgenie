# issue-bot-manual-pick — proposal

Issue: [#472](https://github.com/asimov-agent/llgenie/issues/472)

## Why

`issue-bot.yml`'s only manual input is declared required:

```yaml
  workflow_dispatch:
    inputs:
      issue_number:
        description: "Issue to implement (owner only)"
        required: true
        default: ""
```

so a maintainer cannot start it without already knowing which issue is next — the dispatch is refused
before a run exists:

```
$ gh workflow run issue-bot.yml --repo asimov-agent/llgenie
could not create workflow dispatch event: HTTP 422: Required input 'issue_number' not provided
```

The bot is designed for exactly the opposite. `scripts/issue_implementer.py::dispatch()` takes
`force_issue: int | None`; when it is `None` the dispatcher applies the 3/day cap and picks the
**oldest** `agent:implement` issue (then the oldest `agent:ready`), claims it, writes `issue.md` and a
branch, and the verdict leg routes that one issue — `implement` (a PR that closes it), `refine` (one
comment, no PR), `close` (cited evidence). The workflow already passes an empty `FORCE_ISSUE` through
to that path (`$(if $(FORCE_ISSUE),--force-issue $(FORCE_ISSUE),)` omits the flag), and the daily
schedule relies on it. Only the dispatch form makes it unreachable.

`rebase-bot.yml` shows the intended shape: its `max_prs` input is `required: false` with a default, so
"run it by hand" means "sweep the backlog".

## What Changes

- **`.github/workflows/issue-bot.yml`**: `issue_number` becomes optional (`required: false`,
  `default: ""`) and its description says what blank does — the bot picks the oldest
  `agent:implement` issue itself, one per run. The header's `Trigger surface` paragraph says the same,
  so the file reads as the contract before you dispatch it. A number still pins exactly that issue.
- **`README.md`**: the generated dispatch table (from `make dispatch-forms-report`) and the issue-bot
  section state the blank-means-pick contract.
- **`tests/test_issue_bot_manual_pick.py`** (new): parses the workflow and pins the contract — the
  input is not required and defaults empty, the dispatch step derives `FORCE_ISSUE` from
  `inputs.issue_number` with an empty fallback, the dispatcher's `--force-issue` is omitted when
  `FORCE_ISSUE` is empty (so `dispatch()` receives `None` and picks), and the README states it.
  `make check-dispatch-forms` stays green.
- **`agent-wiki/2026-10-21-issue-bot-manual-pick.md`** records the change against issue #472.

## Not covered

- The gate that killed every bot run before this became reachable — `make hermes-smoke` refusing a
  missing `state.db` before it calls Hermes — is #471; that change is what lets a manual run survive
  its first step.
- The 3/day cap, the claim protocol, the verdict routing and the token seams are unchanged.
