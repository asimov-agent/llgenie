# Tasks

- [x] 1. File the issue with measured evidence (issue #301): the guard passes at 3/3 while the same logic with the three later bots added fails.
- [x] 2. Derive the guard's scope from `.github/workflows/` (any workflow with a `schedule:` is a bot) and derive the reserved minutes from the every-hour crons.
- [x] 3. Add the scope regression test so a hand-narrowed `BOT_WORKFLOWS` fails the suite.
- [x] 4. Re-stagger the colliding crons: `rebase-bot` `23 */6 * * *` -> `29 */6 * * *`, `code-review-bot` `23 7 * * 1` -> `31 7 * * 1`.
- [x] 5. Prove the guard fails on the pre-fix tree and passes after (rule 6c).
- [x] 6. Update the two workflow header comments, `README.md`, and add an `agent-wiki/` entry citing #301.
- [ ] 7. Run `make lint`, `make test-unit`, `make check-docs`, `make openspec-validate NAME=bot-slot-guard-derives-its-scope`; commit, push, open the PR (closes #301).
