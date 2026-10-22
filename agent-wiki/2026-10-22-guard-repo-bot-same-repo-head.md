# The guard admits the repository's own bot on a same-repo head

Issue: #510. PR: #511.

PR #495 — the architecture bot's own refresh, head `asimov-agent:agent/architecture-20261021T1814`,
author `app/github-actions` — has one run, `39650944430`, and it died in `guard` before any job could
start:

```
ACTOR: github-actions[bot]
TRIGGER: andyholst
Refused: github-actions[bot] is not the owner or a collaborator with write access (permission: none).
```

`github-actions[bot]` is a GitHub App login, so `repos/<repo>/collaborators/github-actions[bot]/permission`
404s and the guard's `|| echo none` turns that into a refusal. The earlier architecture PR (#480) passed
only because it was opened by hand — its bot run lost the `gh pr create` answer (#479/#481) and the owner
turned the stranded branch into a PR, so `github.actor` was `andyholst`. #495 is the first PR the bot
created itself (`make architecture-bot-publish` uses the job token for Issues/PR write, #412), hence the
first refusal. `ci.yml`'s own comment already claimed the bot was allowed.

The guard now takes `HEAD_REPO` (`github.event.pull_request.head.repo.full_name`) and admits the bot only
when that is this repository: a same-repo head can only come from a token with write access, so strangers
gain nothing, and a bot actor on a foreign head (a bot comment on a stranger's PR) or on a non-PR event
stays refused. All thirteen guard sites carry the identical body (the existing byte-identical invariant).

Verified: `pytest tests/test_workflow_guards.py` → 14 passed, six of them executing the real guard script
under bash against a real fake `gh` (owner, write collaborator, stranger on a same-repo head, bot on
same-repo / foreign / missing head). The guard taken from `origin/main` refuses the same-repo bot case
(exit 1, the measured message); the new one admits it (exit 0). `make check-workflows` green.
