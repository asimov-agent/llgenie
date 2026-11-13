# Tasks: test-image-user-fold

- [x] 1. Fold the Dockerfile: `USER 1000:1000` final line, `ENV HOME=/tmp`, git
      `safe.directory '*'` via `--system` (and a test locking the trailing USER).
- [x] 2. `TEST_OPTS`: replace `-u root -e HOME=/root` with
      `-u "$(shell id -u):$(shell id -g)"`; keep `-u root` in `ENGINE_TEST_ARGS`
      with the docker-socket reason stated; update the tests that pin the
      container shape (test_engine_bump token test, test_rebase_bot_gates mount
      test must stay green).
- [x] 3. Local proof: rebuild the test image locally (`make test-image`, never a
      publish), run `make lint` + a real pytest suite through `$(TEST_RUN)` as the
      mapped uid (rc=0), and `make security-scan TOOL=trivy` with zero DS-0002.
- [x] 4. Deferral proof on the fold tree: `make test-image` there builds the moved,
      unpublished tag instead of pulling it (rc=0, "[ci-images] ... not published
      ...: building llgenie/test:latest here"), and the `pull_request` deferral
      branch of `ci_images.py pull` is green in `tests/test_ci_images.py`; the fold
      hash `56fb401e924b` is recorded on #2563 for the PR-run and publish proofs.
- [x] 5. Mirror #2563 + close #2576: issue body updated to the shipped design
      (same-repo PR head — the measured guard policy), docs pair (agent-wiki note +
      changes.d row) committed, openspec validate rc=0.
