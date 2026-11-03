# The #792 AGENTS-preflight gate is now wired into CI (issue #1675)

`make check-pr-hygiene`'s `agents-line` subcommand — the gate that refuses a bot PR whose body
omits or mis-cites the `AGENTS:` line (and its `BASE:` companion) that the issue-#845 contract
requires — existed but was **invoked nowhere**: the hermetic `ci-unit` chain runs `check` +
`changes-index`, and `agents-line` needs the LIVE PR body (`--head`/`--base`/`--body-file`) that no
hermetic step passes. So a bot PR whose body lacked an `AGENTS:` line merged green (measured on the
PR for #1673, emitted by a bot email `support@docondee.com` ∈ `BOT_EMAILS`, green with no line).

The fix wires the gate the way `check-pr-closing` is already wired: a new `check-pr-agents-line`
make target drives the subcommand, and both the full pipeline's `guard` job (`.github/workflows/ci.yml`)
and the always-present docs gate (`.github/workflows/scope.yml`, which is what a docs-only bot PR
lands on) run it beside `check-pr-closing`, fetching the PR body LIVE via `gh api` (issue #1589) so
a body-only fix clears on rerun. A push to main has no PR number and no body, so the step prints a
loud "nothing to validate" note instead of failing. `tests/test_pr_hygiene_agents_line.py` proves
the gate is wired (removing the step reds the test) on top of the existing ancestry tests.
