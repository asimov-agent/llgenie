# Tasks — squash-close umbrella guard

- [x] Extend `scripts/check_pr_acceptance.py` to read the linked-issue set from the PR body AND the
      joined squash commit messages (union), so a squash-text-only `(closes #N)` on a rollout
      umbrella is held to that umbrella's acceptance criteria.
- [x] Add negation-awareness: `does not close #N` / `won't close #N` / `(not closing #N)` is not a
      close reference in the acceptance gate's linked-issue derivation.
- [x] Wire both guard workflows (`ci.yml`, `scope.yml`) to pass PR_BASE/PR_HEAD to the
      check-pr-acceptance step and export them into the make target, reading live (issue #1589).
- [x] Add test(s) proving red-on-old / green-on-fixed: a squash-text-only umbrella close with
      unticked criteria is RED; a negated close is not a close; a normal affirmative close stays
      checked.
- [x] Change-note triad (agent-wiki + docs/changes.d fragment + CHANGES.md row) per #1123.
- [x] Validate: `make openspec-validate NAME=umbrella-close-guard`, `make check-docs`, `make lint`.
