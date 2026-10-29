# author-identity-seam — 2026-10-29

## What changed

- `scripts/git_identity.py` (new) — the ONE source of the identity every leg commits as: the bot half
  of `scripts/check_pr_authors.py::ALLOWED` (`Asimov Agent <support@docondee.com>`), derived from the
  policy rather than restated.
  - `identity()` / `pr_author_line()` — the pair, and the `Author:` line a PR body carries.
  - `resolve()` — the identity git would ACTUALLY use for the next commit, honouring git's own
    precedence (`GIT_AUTHOR_NAME`/`GIT_AUTHOR_EMAIL`, then `GIT_AUTHOR_IDENT`) and reading the config
    with `git config --show-origin`, so a finding names the FILE that set it.
  - `check()` — the pre-flight: a pair outside `ALLOWED` is a finding, naming the identity, its source
    and the allowlist.
  - `apply()` — writes the allowlisted pair into the repository's own git config (never the global one).
- `scripts/check_pr_authors.py` — two new legs, `check_seam()`:
  a producer that runs `git commit` must name the seam (or pin an allowed pair itself), and a producer
  that opens a PR must report the author through the seam. `git_identity.py` joins this guard's
  self-exclusion list for the same reason it excludes itself: it names identities as data.
- `.github/workflows/ci.yml` — `guard` (the cheap job) now checks out full history and runs
  `make git-identity-apply`, `make check-git-identity` and `make check-pr-authors` BEFORE the row
  decision, so an off-allowlist author reds in seconds instead of at the end of `linux / unit`.
- Producers source the seam instead of a literal: `engine-bump.yml`, `engine-bump-rebase.yml`,
  `issue-bot.yml`, `registry-sync.yml` (were `git config user.name/email`), `fix-bot.yml` and
  `security_bot.py`/`security_bumps.py` (were `git -c user.name=… -c user.email=…`), `rebase-bot.yml`
  (were four `GIT_AUTHOR_*`/`GIT_COMMITTER_*` env literals), `architecture_bot.py` (was `git config`
  plus its own `AUTHOR_NAME`/`AUTHOR_EMAIL` copies).
- PR bodies report the author first: `issue_implementer.render_pr_body`, `security_bot.pr_body`,
  `security_bumps.pr_body`, `architecture_bot.render_pr`, `engine-bump.yml`, `registry-sync.yml` all
  prefix `Author: Asimov Agent <support@docondee.com>` from the seam.
- `scripts/check_pr_hygiene.py` — two parser corrections the conversion exposed: a quoted `-m`
  argument is read whole (spaces included, `f` prefix stripped), and a MULTI-LINE quoted message is one
  command; `-am`/`-sm` short-flag bundles count as carrying a message.
- `Makefile` — `git-identity-apply`, `check-git-identity`, `git-identity-line`, `git-identity-report`
  (internal plumbing: no `##` help line).
- `tests/test_git_identity.py` (new) — real git repositories: the seam's pair, `apply` then `check`,
  an ambient `andy@asimov.local` (reds, naming `user.email`), a `GIT_AUTHOR_EMAIL` override (reds,
  naming the variable), the PR-body line, the report, the CLI's exit codes, and the guard job's step
  order + `fetch-depth: 0`.
- `tests/test_engine_bump.py`, `tests/test_engine_bump_pr_body.py` — updated to the new behaviour:
  the bump/sync steps source `make git-identity-apply` (and the seam resolves to an allowlisted pair),
  and the body rendering now begins with the seam's author line.

## Why

Measured on `main@88f5d346` (the issue's comment corrects the body's first diagnosis): the wrong
identity did NOT come from config drift — the repo, global and every worktree config already held
`andy.holst@protonmail.com`. It came from explicit `-c user.name=… -c user.email=…` flags, which beat
every config layer by design. Nine producers set the pair in three spellings, so one typo produced
`Asimov Agent <agent@asimov.invalid>` — a correct-LOOKING name with a wrong domain, invisible to
`git log --format='%an'` and caught only by `check_pr_authors`, which ran at the END of
`linux / unit` (30+ minutes), holding PRs for a reason unrelated to their diff.

## Decisions

- **The seam is the only place the bot pair is written.** `ALLOWED` stays the policy in
  `check_pr_authors.py`; `git_identity.py` derives the bot half from it, so the two can never disagree.
- **Fail fast is the SAME check, earlier.** No new policy: `guard` runs the existing commit scan plus
  the ambient-identity assertion, which is what `linux / unit` already ran.
- **The ambient check is not the only guard.** A `-c` flag still beats a correct config, so the
  produced commits are scanned as well — the two halves close both mechanisms.
- **A report, not a block:** `check()` calls it a violation with its source; there is no attempt to
  silently rewrite a leg's identity.

## Verification

- `docker run … python -m pytest tests/test_git_identity.py tests/test_engine_bump.py
  tests/test_engine_bump_pr_body.py tests/test_pr_hygiene.py -q` → `106 passed`.
- `make check-pr-authors` → OK on this branch (static producers + AGENTS.md + the new seam legs).
- `make check-pr-hygiene`, `make check-workflows`, `make check-wiring`, `make check-docs`,
  `make check-dispatch-forms`, `make check-issue-bodies`, `make lint` → OK.
- `make test-unit` (the full discovered suite, in `llgenie/test:latest`) → see the PR's report.

Issue #840.
