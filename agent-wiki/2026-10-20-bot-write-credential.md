# A bot's write now uses the credential that can make it

Issue #412. OpenSpec change: `bot-write-credential`. PR: (this branch, opened against `asimov-agent/llgenie:main`).

## What was wrong

Two legs were red or dead for a credential reason while the job's own `permissions:` block already
granted the write:

- `issue-refiner`, **every** scheduled run for at least five runs: the claim comment is refused —
  `GraphQL: Resource not accessible by personal access token (addComment)` (run 39419748051 and the four
  before it).
- `fix-bot`'s sweep: `gh workflow run` refused —
  `HTTP 403: Resource not accessible by personal access token (…/dispatches)` (run 39371245146).

Both steps were handed `secrets.BUMP_TOKEN`, an owner PAT scoped for the push (branch / PR), not for
Issues or Actions. `github.token` is scoped to this repository *and* the job's permissions — and the
refiner job already declares `issues: write`, the sweep job already declares `actions: write`.

## What changed

| workflow | step | token now | permission it relies on |
|---|---|---|---|
| `issue-refiner.yml` | claim (pick), apply, report | `github.token` | `issues: write` |
| `issue-bot.yml` | verdict (comment + label) | `github.token` | `issues: write` (push step keeps the PAT) |
| `fix-bot.yml` | sweep `gh workflow run` | `github.token` | `actions: write` |
| `run-failure-reactor.yml` | file issue / dispatch fix-bot | `github.token` | `actions: write`, `issues: write` |
| `queued-alarm.yml` | PR comment / deduped issue | `github.token` | `issues: write` |

Untouched: every pushing job (`issue-bot` push, `fix-bot`, `rebase-bot`, `engine-bump`,
`engine-bump-rebase`, `registry-sync`) keeps `BUMP_TOKEN`, because a `github.token` push does not
re-trigger CI (issue #136).

`tests/test_bot_write_tokens.py` locks it: the token on each issue-writing step, the permission on each
job, and the PAT on every pushing job — read from the step env, the job env, or the `actions/checkout`
token that `git push` actually uses. Run against the OLD workflows it fails
(`test_every_issue_writing_step_uses_the_repo_scoped_token`), which is how the fix is proven real.

## Verification

- `pytest tests/test_bot_write_tokens.py` → 3 passed; the same file against `main`'s workflows → 1 failed
  (the old wiring), 2 passed.
- A real `workflow_dispatch` of `issue-refiner` on this branch → the claim comment lands (see the PR).
- `make check-workflows`, `make check-dispatch-forms`, `make lint`,
  `make openspec-validate NAME=bot-write-credential`, `make test-unit`.

## Honest limits

- `secrets.BUMP_TOKEN`'s scopes are still the owner's to set; this change stops *depending* on it for
  writes it cannot make, and it narrows what a compromised step can reach (`github.token` is limited to
  this repository and these permissions).
- The fork-PR selection in `fix-bot`'s sweep (#340) is separate: the sweep can now dispatch, but it still
  skips a PR whose head lives on a fork.
- `issue-bot`'s daily cap (#409) is unaffected.
