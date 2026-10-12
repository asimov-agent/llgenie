# Tasks

- [x] 1. Export `GITHUB_TOKEN` from `secrets.GITHUB_TOKEN` in every workflow that already exports `HF_TOKEN`.
- [x] 2. Forward `GITHUB_TOKEN` and `GH_TOKEN` by name into the Linux test container and the Linux engine-test container. Do not put the value on the command line.
- [x] 3. Send that token on the release lookup. Retry a 401 or 403 once with no `Authorization` header. Leave every other failure as no assets.
- [x] 4. Lock the workflow env, the container flags, the header, and the 401/403 retry in `tests/test_engine_bump.py` with Given / When / Then.
- [x] 5. Note the forwarding in `README.md`.
- [x] 6. `make openspec-validate NAME=forward-github-token` exits 0. The seven new cases passed in `llgenie/test`. `make lint` is green.
