# A manual `issue-bot` run with no issue number picks one itself

Issue #472. OpenSpec change: `issue-bot-manual-pick`.

## What was wrong

`issue-bot.yml` declared its only manual input as required:

```yaml
      issue_number:
        description: "Issue to implement (owner only)"
        required: true
        default: ""
```

so the dispatch was refused before a run existed:

```
$ gh workflow run issue-bot.yml --repo asimov-agent/llgenie
could not create workflow dispatch event: HTTP 422: Required input 'issue_number' not provided
```

Everything behind that form already supported choosing: the workflow's dispatch step derives
`FORCE_ISSUE: ${{ github.event.issue.number || inputs.issue_number || '' }}`, the Makefile recipe runs
`$(if $(FORCE_ISSUE),--force-issue $(FORCE_ISSUE),)` — so an empty value passes no flag — and
`scripts/issue_implementer.py::dispatch()` takes `force_issue: int | None`, where `None` means "apply the
3/day cap, then pick the oldest `agent:implement` issue (then the oldest `agent:ready`), claim it,
write `issue.md` and a branch". The verdict leg then routes that one issue: **implement** (a PR that
closes it), **refine** (one comment, no PR), **close** (cited evidence). The daily schedule uses that
path; a maintainer could not.

## What changed

- `.github/workflows/issue-bot.yml` — `issue_number` is `required: false` with `default: ""`, and both
  its description and the file's `Trigger surface` paragraph say what blank does: the bot picks the
  oldest `agent:implement` issue itself, one per run, exactly like the schedule. A number still pins
  that issue.
- `README.md` — the generated dispatch table (`make dispatch-forms-report`) plus a usage block in the
  issue-implementer section: `gh workflow run issue-bot.yml` with no input starts one issue's worth of
  work; `-f issue_number=<n>` pins one.
- `tests/test_issue_bot_manual_pick.py` — 4 cases: the form (not required, empty default, description
  names the label), the blank path (`FORCE_ISSUE` falls back to empty, `make -n issue-bot-dispatch`
  with an empty value passes no `--force-issue`, and `dispatch()`'s default is `None`), the pinned path
  (`FORCE_ISSUE=1234` → `--force-issue 1234`), and the header/README agreement with
  `check_dispatch_forms.check` exit 0.

## Verified

- `tests/test_issue_bot_manual_pick.py` — 4 passed in `llgenie/test:latest`.
- `make check-dispatch-forms`, `make check-wiring`, `make check-docs`, `make lint`,
  `make openspec-validate NAME=issue-bot-manual-pick`, `make openspec-tasks-check`,
  `make check-pr-hygiene`, `make check-pr-authors`, `make test-unit` (**4969 passed, 6 deselected, 1036 s**) — exit 0.
- The before-state is measured, not assumed: the same command against `main` returns the HTTP 422
  above. A dispatch from this branch cannot be exercised before merge — `workflow_dispatch --ref` only
  accepts a ref that exists in the upstream repo, and this branch lives on the fork. After merge,
  `gh workflow run issue-bot.yml` (no input) is the acceptance check.

## Related

- #471 — `make hermes-smoke` refused a missing `state.db` before calling Hermes, which killed every
  bot run in seconds; a manual dispatch would have died at the same gate.
- The 3/day cap, the claim protocol, the verdict routing and the token seams are unchanged.
