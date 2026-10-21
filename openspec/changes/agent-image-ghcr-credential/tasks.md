# Tasks

- [x] 1. `publish-agent-image.yml`: the GHCR login step uses `secrets.GITHUB_TOKEN` as `github.actor` (ci.yml's shape) instead of `secrets.BUMP_TOKEN` as `github.repository_owner`; `permissions: packages: write` stays declared
- [x] 2. `publish-agent-image.yml`: the pre-flight step is handed that same credential (`GHCR_TOKEN: ${{ secrets.GITHUB_TOKEN }}`), so what it proves is what the push will do
- [x] 3. `publish-agent-image.yml` header: the "organization package" justification is replaced with the measured `403 permission_denied: The token provided does not match expected scopes` (runs 39420414201 and 39538405507) and the fact that `asimov-agent` is a user account
- [x] 4. `scripts/ci_images.py pushcheck`: the missing-credential message names `secrets.GITHUB_TOKEN`, and the default Basic user's comment names `github.actor` (the account the job logs in as)
- [x] 5. `README.md`: the `publish-agent-image.yml` paragraph describes `secrets.GITHUB_TOKEN` + `packages: write` and the measured refusal it replaces, with the issue number
- [x] 6. `tests/test_ci_images.py`: a test locks login-secret == pre-flight-secret == `GITHUB_TOKEN`, the `github.actor` login account, and the job's `packages: write` permission
- [x] 7. `agent-wiki/2026-10-21-agent-image-ghcr-credential.md` records the work with the issue and the PR
- [x] 8. Live: `workflow_dispatch` of the fixed job on this branch, run 39540690264 green — pre-flight `empty upload accepted (202)`, `make publish-agent-image` a no-op on the already-published `d70aa12310b4` tag
- [x] 9. Gates green: `make test-unit`, `make lint`, `make check-docs`, `make check-wiring`, `make check-workflows`, `make check-pr-hygiene`, `make openspec-validate NAME=agent-image-ghcr-credential`
