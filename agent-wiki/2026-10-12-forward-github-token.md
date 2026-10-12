# Forward GITHUB_TOKEN into the test containers

Issue #199. Run 38247208919 (`linux / unit`) failed `make test-engine-bump-live`
because `_release_assets` called `api.github.com` with no token. The container
was started with `-e HF_TOKEN` only, and every lookup error became an empty
asset list. TensorFold v1.0.5 still publishes its six archives.

Workflows that export `HF_TOKEN` now also export `secrets.GITHUB_TOKEN`.
Linux `TEST_OPTS` and `ENGINE_TEST_ARGS` forward `GITHUB_TOKEN` and `GH_TOKEN`
by name. The lookup sends `Bearer` for the first non-empty of those two. A
401 or 403 is retried once with no `Authorization` header, because an
installation token cannot read another public repository.

`make openspec-validate NAME=forward-github-token` passed. The seven new
cases passed in `llgenie/test`. `make lint` passed.
