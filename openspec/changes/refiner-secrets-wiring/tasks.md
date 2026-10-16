# Tasks — refiner-secrets-wiring

All items are done: the change is implemented, the tests that pin it run in `ci-unit`, and the
loop gate (`make loop`) is green on the branch. Every box is checked because the work is on disk and
verified, not planned.

## Wiring: stop reading secrets the repo does not define

- [x] Drop `secrets.OPENROUTER_API_KEY` / `secrets.OPENCODE_API_KEY` from the `refine` job's `env:`
      block in `.github/workflows/issue-refiner.yml` (it keeps `NOUS_API_KEY` + `TYPESAFE_API_KEY`).
- [x] Restrict the provider case in `scripts/agent_jev_preflight.sh` to `typesafe`; name the supported
      provider in the refusal for any other value.
- [x] Check `TYPESAFE_API_KEY` alone in the build-time key loop in `scripts/install_nerve_ci.sh`.
- [x] Stop forwarding `-e OPENROUTER_API_KEY -e OPENCODE_API_KEY` in the four agent recipes in the
      `Makefile` (`issue-refiner`, `rebase-bot-agent`, `agent-jev-preflight`, `implement-issue`).
- [x] Drop the two names from `SECRET_VARS` in `scripts/check_secret_output.py`.
- [x] Drop the two names from the secret list in `README.md`.
- [x] Keep the build-time guard in `containers/agent/Dockerfile` naming the whole provider-key
      namespace (`TYPESAFE|OPENROUTER|OPENCODE`), so the `agent-nerve-jev` spec stays satisfied and a
      future provider key is caught by the same guard.

## Tests (no mocks; the product runs)

- [x] `tests/test_issue_refiner.py::test_the_refine_job_does_not_read_undefined_secrets` — reads the
      workflow's `env:` block and asserts the two names are absent and the defined keys are present.
- [x] `tests/test_issue_refiner.py::test_the_refiner_recipe_forwards_only_defined_keys` — reads the
      `Makefile` recipes and asserts the two names are not forwarded.
- [x] `tests/test_workflow_guards.py::test_no_workflow_reads_an_undefined_secret` — walks every
      workflow and asserts no `secrets.OPENROUTER_API_KEY` / `secrets.OPENCODE_API_KEY` reference
      survives.
- [x] `tests/test_agent_nerve.py::test_an_unsupported_provider_is_refused_loudly` — runs the real
      preflight with `HERMES_NERVE_PROVIDER=openrouter` and asserts a non-zero exit naming `typesafe`.
- [x] `tests/test_agent_nerve.py::test_the_typesafe_provider_selects_its_key` — runs the real
      preflight with `HERMES_NERVE_PROVIDER=typesafe` and asserts it checks `TYPESAFE_API_KEY`.
- [x] `tests/test_agent_nerve.py::test_a_provider_key_in_the_build_environment_fails_the_build` —
      runs the real `install_nerve_ci.sh` with a provider key set and asserts a loud failure.
- [x] `tests/test_secret_output.py::test_the_secret_list_matches_the_repo_secrets` — asserts
      `SECRET_VARS` no longer names the two keys and still names the keys the repo defines.

## OpenSpec

- [x] Write `proposal.md` (this change's why/what/impact).
- [x] Write `specs/bot-secret-wiring/spec.md` (the ADDED requirements, each with a test).
- [x] Write `tasks.md` (this file).
- [x] Write the work record `agent-wiki/2026-10-16-refiner-secrets-wiring.md`.
- [x] `make openspec-validate NAME=refiner-secrets-wiring` passes.

## Gates (all run on this branch)

- [x] `make lint` passes.
- [x] `make test-unit` passes (4643 passed; the 2 failures are HuggingFace `HTTP 429` network
      flakes in `test_trend_pick.py` / `test_model_engine_pick.py`, unrelated to this change).
- [x] `make check-wiring` passes (every workflow step maps to a Makefile target).
- [x] `make check-docs` passes (every user-facing target is in README.md; every work record cites
      an issue/PR).
- [x] The rest of the loop (`test-health`, `test-install`) runs in CI on this branch.
