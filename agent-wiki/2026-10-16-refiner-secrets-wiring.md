# refiner-secrets-wiring — remove the never-used OPENROUTER/OPENCODE keys (issue #311)

## The finding

Issue #311: the issue-refiner's `refine` job read `secrets.OPENROUTER_API_KEY` and
`secrets.OPENCODE_API_KEY`. Neither name exists in the repository's secret list
(`BUMP_TOKEN`, `HF_TOKEN`, `NOUS_PORTAL_API_TOKEN`, `TYPESAFE_API_KEY`, plus GitHub's own
`GITHUB_TOKEN`). GitHub substitutes an **empty string** for an undefined secret, so the job ran
with a blank key instead of failing at the point of use — the wiring looked real and did nothing.

The same two names were repeated in every place a provider key is forwarded:

- `.github/workflows/issue-refiner.yml` — the `refine` job's `env:` block.
- `scripts/agent_jev_preflight.sh` — the provider `case` mapped `openrouter` → `OPENROUTER_API_KEY`
  and `opencode` → `OPENCODE_API_KEY` alongside `typesafe`.
- `scripts/install_nerve_ci.sh` — the build guard looped over all three names.
- `Makefile` — four agent recipes forwarded `-e OPENROUTER_API_KEY -e OPENCODE_API_KEY`.
- `scripts/check_secret_output.py` — `SECRET_VARS` named both, so the guard scanned for a leak of a
  variable that can never carry a value.
- `README.md` — the secret list repeated both names.

## The fix

Remove the two names from every **wiring** site — the places that read or forward a credential —
so a workflow reads only the secrets the repo defines:

- the refiner workflow's `env` block,
- the preflight's provider `case` (only `typesafe` remains; any other value is refused loudly),
- the four `Makefile` recipes,
- `SECRET_VARS`,
- the README secret list.

## What was deliberately NOT narrowed: the build guard

`containers/agent/Dockerfile` and the build-guard loop in `scripts/install_nerve_ci.sh` keep naming
the whole provider-key namespace — `^(TYPESAFE|OPENROUTER|OPENCODE)_API_KEY=`. That guard is the
opposite of a wiring reference: it *refuses* a provider key that appears in the build environment,
so a token can never be baked into an image layer. The `agent-nerve-jev` spec requires the guard to
cover all three names so a future provider key is caught by the same guard. Narrowing it would
weaken the defence the user asked to keep intact. The spec added by this change states this
explicitly, so a reader does not mistake the guard for a live reference.

## The tests (rule 6c)

Seven tests, each named in the new capability spec `bot-secret-wiring`:

- `tests/test_issue_refiner.py::test_the_refine_job_does_not_read_undefined_secrets`
- `tests/test_issue_refiner.py::test_the_refiner_recipe_forwards_only_defined_keys`
- `tests/test_workflow_guards.py::test_no_workflow_reads_an_undefined_secret`
- `tests/test_agent_nerve.py::test_an_unsupported_provider_is_refused_loudly`
- `tests/test_agent_nerve.py::test_the_typesafe_provider_selects_its_key`
- `tests/test_agent_nerve.py::test_a_provider_key_in_the_build_environment_fails_the_build`
- `tests/test_secret_output.py::test_the_secret_list_matches_the_repo_secrets`

Proof on the pre-fix tree (`git worktree add --detach /tmp/llgenie-prefix origin/main`, new tests
overlaid): **5 fail, 1 pass** — the five fix-proving tests fail on `origin/main`; the
typesafe-provider test is a regression pin (typesafe was always mapped) and passes both sides.
Post-fix: **7 pass**. No mocks: the tests run the real `agent_jev_preflight.sh` and
`install_nerve_ci.sh` as subprocesses and read the real workflow/Makefile/Dockerfile text.

## Gates

`make lint`, `make openspec-validate NAME=refiner-secrets-wiring`, `make check-wiring`,
`make check-docs`, and the unit suite via `llgenie/test:latest` — all green (see the PR's CI run).
