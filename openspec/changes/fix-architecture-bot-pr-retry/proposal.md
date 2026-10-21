# fix-architecture-bot-pr-retry

## Why

The bot's second real run (`39620798522`, 15:00Z) did everything right — smoke proved the tool
call, the doc was rewritten, issue #478 was filed, the branch `agent/architecture-20261021T1500`
was pushed — and then GitHub's gateway answered the PR create with **504**:

```
pull request create failed: HTTP 504: 504 Gateway Timeout (https://api.github.com/graphql)
```

The run went red, and the refresh was stranded: an open issue, a pushed branch, no PR. A lost
response is not a refusal; the create may even have succeeded on GitHub's side.

Issue: [#479](https://github.com/asimov-agent/llgenie/issues/479).

## What Changes

- `scripts/architecture_bot.py`: `_gh_retry` retries a GitHub write on a transient
  502/503/504/timeout (bounded, default 3 attempts), and `publish` recovers a lost create by
  looking for an open PR whose head is the branch (`open_pr_for_branch`). A genuinely failed
  create still raises, and the error names the issue and branch it already made so a human can
  finish it.
- Tests: a transient 504 then success; a create that never answers but a PR that exists; a real
  failure naming the orphans.

## Impact

- Affected specs: `architecture-bot` (modified).
- Affected code: `scripts/architecture_bot.py`, `tests/test_architecture_bot.py`, README,
  `agent-wiki/`.

## Not covered

- The already-stranded run was finished by hand: PR #480 carries branch
  `agent/architecture-20261021T1500` and closes #478.
