# issue-bot-ghtoken — proposal

Issue: [#364](https://github.com/asimov-agent/llgenie/issues/364) (child of [#357](https://github.com/asimov-agent/llgenie/issues/357))

## Why

`make implement-issue` forwards `-e GH_TOKEN` into the agent image, but the issue-bot job that calls it
never sets `GH_TOKEN` **for that step**: the only `GH_TOKEN` exports in the job belong to the dispatch
step (`github.token`) and to the later push/PR steps (`BUMP_TOKEN`). So the implementer's container
received an **empty** `GH_TOKEN` and any `gh` call the agent made inside that leg ran unauthenticated
— while the step log read exactly like a correctly wired one.

Measured on `main@2649803` by the step-scoped check added here:

```console
pre-fix  step sees GH_TOKEN: False
post-fix step sees GH_TOKEN: True
```

## What Changes

- **`.github/workflows/issue-bot.yml`**: the implement job's `env:` gains
  `GH_TOKEN: ${{ github.token }}` (the job already carries `contents/issues/pull-requests: write`; the
  PUSH keeps the owner PAT, `BUMP_TOKEN`, in its own step), and the agent-shell step's
  `AGENT_SHELL_CHECK_KEYS` gains `GH_TOKEN`, so #358's probe proves the agent's shell can see it.
- **`tests/test_agent_shell_keys.py`**: the defect is now a **rule**, not a one-off — for each bot
  workflow the suite takes the step that actually runs the leg, resolves the keys the leg forwards
  from the Makefile, and fails when that step cannot see one. A SIBLING step's `env:` does not count,
  which is exactly the shape of this bug; a synthetic fixture proves the detector fails a job whose
  only `GH_TOKEN` sits in another step.

## Impact

- The implementer's `gh` calls are authenticated, and the job's credential set is now proven rather
  than assumed.
- The rule applies to every bot leg: a new `-e KEY` on a leg whose workflow step does not export that
  key fails `make test-unit` instead of shipping an empty value.
- Out of scope, filed separately: whether the implementer needs `gh` at all (its prompt forbids
  pushing; reads are enough today) and the `FIRECRAWL_API_KEY` secret definition (#362).
