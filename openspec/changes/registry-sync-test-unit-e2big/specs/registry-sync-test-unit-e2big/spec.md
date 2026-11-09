# registry-sync-test-unit-e2big — spec of record

## ADDED Requirements

### Requirement: the change-path test-unit does not inherit the large job-secret env

The `sync` job of `.github/workflows/registry-sync.yml` MUST keep `HF_TOKEN` and
`GITHUB_TOKEN` at the job level (issue #1594), but the change-path
`make check-registry + check-quant-catalog + engine-skill-gap report + test-unit` step
MUST NOT forward the job-level secret VALUES into the test image: it re-points `HF_TOKEN`
to an empty string and `GITHUB_TOKEN`/`GH_TOKEN` to `${{ github.token }}` at the step
level, so the spawned gh-subprocesses inherit a small env (the runner's automatic small
token, non-empty for `engine_bump_rebase.load_token()`) and fit under the kernel
`ARG_MAX`. This is exactly the environment push CI's `linux / unit` runs the same suite
in; it MUST not remove or relax any gate, check or permission, and MUST not skip the
gh-spawning tests.

#### Scenario: a large secret env reaches the change path
- **WHEN** the change-path test-unit step inherits the job-level `HF_TOKEN`/`GITHUB_TOKEN`
  and the gh-spawning tests spawn a subprocess with `env=dict(os.environ)`
- **THEN** the spawn fails `OSError: [Errno 7] Argument list too long` and the sync PR
  never opens (the pre-fix state, runs 42608937982/42612274355 @ ffac222)

#### Scenario: the change-path step scopes the secrets to the automatic token
- **WHEN** the step re-points the three forwarded vars at the step level (`HF_TOKEN` empty,
  `GITHUB_TOKEN`/`GH_TOKEN` = `${{ github.token }}`)
- **THEN** `make test-unit` in the change path completes green (the E2BIG is gone, and
  `engine_bump_rebase.load_token()` still finds a non-empty token) and the
  `Open / update the sync PR` leg can fire on a real registry change

### Requirement: the fix is proven in the exact test image

The fix MUST be demonstrated in `ghcr.io/asimov-agent/llgenie/test:7df351360413`: the
large-env case reproduces the E2BIG, the scoped-env case shows the same three formerly-red
tests passing — the bug and the cure on the same image and suite.

#### Scenario: proving the bug and the cure in the test image
- **WHEN** the three formerly-red tests run in the test image with a large `HF_TOKEN` in
  the environment
- **THEN** they fail `Argument list too long`; when the same tests run with the env scoped
  small they pass (`3 passed`)
