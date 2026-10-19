# 2026-10-19 — the implementer leg's GH_TOKEN is set, and the rule that catches the next one (#364)

Implements [#364](https://github.com/asimov-agent/llgenie/issues/364) (PR [#371](https://github.com/asimov-agent/llgenie/pull/371)),
a child of the bot-fleet parent
[#357](https://github.com/asimov-agent/llgenie/issues/357). OpenSpec change:
`openspec/changes/issue-bot-ghtoken`.

## What was wrong (measured)

`make implement-issue` forwards `-e GH_TOKEN`; the ISSUE-BOT job only exported `GH_TOKEN` in the
dispatch step and in the later push/PR steps, so the implementer's container got an EMPTY token. Any
`gh` call inside that leg ran unauthenticated while the log looked wired. Found while implementing
#358; filed as its own issue and fixed here.

## What changed

- `issue-bot.yml`: `GH_TOKEN: ${{ github.token }}` on the implement job's `env:` (permissions already
  cover contents/issues/pull-requests write; the PUSH keeps `BUMP_TOKEN`), and `GH_TOKEN` added to that
  job's `AGENT_SHELL_CHECK_KEYS`, so #358's probe proves the AGENT's shell sees it.
- `tests/test_agent_shell_keys.py`: a step-scoped rule — for each bot workflow it takes the step that
  runs the leg, resolves the keys the leg forwards from the Makefile, and fails when that step cannot
  see one. A SIBLING step's env does not count, which is the exact shape of this bug.

## Verified (the fix is real, not a loosened test)

```
pre-fix  step sees GH_TOKEN: False
post-fix step sees GH_TOKEN: True
pytest tests/test_agent_shell_keys.py -q   -> 9 passed
```

The pre-fix value is read from `git show HEAD:.github/workflows/issue-bot.yml` through the same
functions the suite uses, so the detector is proven against the actual defect rather than a fixture —
and a synthetic fixture pins the sibling-step case on its own.

## Decisions

- `github.token`, not the owner PAT: the implementer reads the issue and the repo, and its prompt
  forbids pushing. Least privilege, and the push step keeps the PAT it needs.
- The rule lives in the existing #358 suite rather than a new file: it is the same question ("can the
  thing that runs see the credential?"), one level up from the agent's shell.

## Follow-ups

- Whether the implementer needs `gh` at all is a separate question (its prompt forbids pushing), and
  the `FIRECRAWL_API_KEY` secret definition belongs to #362's follow-up.
