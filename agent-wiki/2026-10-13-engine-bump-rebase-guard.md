# engine-bump-rebase guard

Issue #212. Run 38315109038 refused `andyholst` because
`engine-bump-rebase.yml` sent `Authorization: Bearer ***`. `TOKEN` was set
to `secrets.GITHUB_TOKEN` and unused. `engine-bump.yml` sends
`Authorization: Bearer $TOKEN`, which returned 204 for the same account
(run 38285390832). The header is now `$TOKEN`. Checkout and push stay on
`BUMP_TOKEN`.
