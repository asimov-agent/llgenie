# Tasks

- [x] 1. Proposal + spec for the alias rule (issue #971).
- [x] 2. `scripts/check_pr_authors.py`: `ALIASES` (allowlisted email → its display names) with
      `ALLOWED` derived from it; `_identity_finding` matches on the email and its alias list; the
      finding's evidence names the email; the docstring records why the name alone cannot be the key.
- [x] 3. `tests/test_pr_authors.py`: alias-name pass, typo-email fail, unknown-author negative control,
      one-address-per-name map test, and the existing vocabulary tests updated to the new policy.
- [x] 4. `AGENTS.md` + `docs/BOTS.md`: the rule as it now is (email is the identity, alias names are a
      name list, never an email list).
- [x] 5. `agent-wiki/2026-10-29-author-alias-emails.md` + the `CHANGES.md` row (`make changes-index`).
- [x] 6. Prove the rule against #919's real range (`check --base 5338bc6d --head 4fb3bf3a`): the six
      `Andy` commits pass and `fd31640d`'s typo email still fails as the one remaining violation.
- [x] 7. Run the gates via make (`lint`, `check-docs`, `check-wiring`, `check-workflows`,
      `check-pr-authors`, `check-pr-hygiene`, `test-unit`), `make openspec-validate NAME=author-alias-emails`,
      and tick every task before the PR is ready.
