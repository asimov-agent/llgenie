# The guard admits the repository's own bot on a same-repo head

## Why

PR #495 (the architecture bot's own refresh, head `asimov-agent:agent/architecture-20261021T1814`,
author `app/github-actions`) has one run, `39650944430`, and it died in `guard`:

```
ACTOR: github-actions[bot]
TRIGGER: andyholst
Refused: github-actions[bot] is not the owner or a collaborator with write access (permission: none).
```

The guard accepts the repo owner, or a login whose `repos/<repo>/collaborators/<login>/permission` is
`admin|maintain|write`. `github-actions[bot]` is a GitHub **App** login, so that endpoint 404s, the
`|| echo none` turns it into `none`, and the loop exits 1. `ci.yml`'s own job comment already claims the
intent — *"only collaborators, the github-actions[bot], and the repo owner"* — the code never allowed the
bot.

It "worked before" only because the earlier architecture PR (#480) was opened by hand: its bot run lost
the `gh pr create` answer (the defect that became #479/#481) and the stranded branch was turned into a PR
by the owner, so `github.actor` was `andyholst`. #495 is the first PR the bot actually created itself
(`make architecture-bot-publish` uses `GH_TOKEN: ${{ github.token }}`, because `secrets.BUMP_TOKEN`
carries no Issues write, #412) — and the first one the guard refuses.

## What Changes

- **`.github/workflows/*.yml` (all 13 guard sites, byte-identical)** — the guard gains a `HEAD_REPO`
  env (`github.event.pull_request.head.repo.full_name`, empty off a pull request) and one allowance: the
  repository's own bot passes **only** when `HEAD_REPO` is this repository. A same-repo head can be
  produced only by a token with write access, so the allowance widens nothing for strangers; the bot as
  the actor of a **foreign** head (a bot comment or label on a stranger's PR) is still refused, and so is
  a bot actor on a non-PR event, where no head repo exists.
- **`tests/test_workflow_guards.py`** — the decision is now executed, not just read: the real guard
  script is extracted from `ci.yml` and run under bash against a real fake `gh` binary, for the owner, a
  write collaborator, a stranger on a same-repo head, and the bot on a same-repo / foreign / missing
  head. One more case pins that every guard site declares `HEAD_REPO`.

## Impact

- A bot-opened same-repo PR can run CI at all: the `guard` job is a `needs:` of every other job, so
  without it the whole pipeline never starts.
- Strangers are still refused, on any head, and the byte-identical invariant (one guard body everywhere)
  is preserved.
