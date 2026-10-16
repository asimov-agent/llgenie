# PR bodies and commit messages carry the issue, the fix and the benefit

## Why

`AGENTS.md` required a PR body to reference its issue and end with `closes #N`, and every commit to
be a typed Conventional Commit — but nothing said what the body or the message must *contain*, and
nothing enforced it. The repo's own producers therefore ship messages a reviewer cannot read:

- `.github/workflows/engine-bump.yml` commits `chore(engine): bump <id> to <ref>@<sha>` with **no
  body**; `.github/workflows/issue-bot.yml` commits `feat(issue-bot): implement #<n>` with **no
  body**; `.github/workflows/registry-sync.yml` commits a subject-only sync line. A `git log` reader
  gets a subject and nothing else — not the issue, not the fix, not the benefit.
- A `gh pr create` could be opened with no body at all (or `--body ""`) and no gate would notice.

The information a reviewer needs — what the issue was, how the change solves it, and why it matters
— must live in the commit and the PR, not only in an issue they have to go find.

## What changes

- **`AGENTS.md`** gains a durable, mandatory section: every commit message and PR body SHALL carry
  three labelled parts — the **Issue** (the problem/goal, with `#N`), the **Fix** (the mechanism that
  solves it) and the **Benefit** (why it matters, what it prevents) — followed by a **Technical**
  extension (the files, tests, gates and measured numbers that let a reviewer verify it without
  re-deriving anything). The subject stays a Conventional Commit summary. Empty or placeholder
  bodies/messages are forbidden.
- **`make check-pr-hygiene`** (`scripts/check_pr_hygiene.py check`), wired into `make ci-unit`, is
  the deterministic guard: it reads every producer the repo owns (`.github/workflows/*.yml`,
  `Makefile`, `scripts/**`) and fails on
  - a `gh pr create` with no body, or a body that is empty/placeholder;
  - a `git commit` whose message is missing, is a placeholder, is not a Conventional Commit
    subject, or carries no body (a bare subject);
  - an `AGENTS.md` that no longer carries the mandate, so the rule cannot be deleted silently.
  `make pr-hygiene-report` is the human view.
- The three producers above emit a real body in the same change, so the guard is proven to fire on
  the real tree and then pass on the fixed one.

## Impact

A bodiless commit or an empty PR body becomes a red `ci-unit`, not a habit. A reviewer opening any
bot's commit or PR reads the issue it answers, the mechanism that fixes it and the benefit it buys,
plus the technical detail to verify it — the same substance a hand-written change carries.
