# Tasks — workflow-flow-targets

## The defect (issue #323)

- [x] Correct `publish-agent-image.yml`'s `Flow:` line to the real stages (guard, then
      `make publish-agent-image` — the GHCR "already there?" decision lives inside
      `scripts/ci_images.py publish` — then `make ci-image-refs`).
- [x] Correct the `README.md` paragraph that documented `make agent-image-push-check` as a real
      pre-flight and claimed a default-token login the job does not do.

## The rule

- [x] Add `MAKE_IN_FLOW` + `flow_lines()` + `makefile_targets()` to `scripts/check_dispatch_forms.py`.
- [x] Fail when a `Flow:` stage (or a continuation line) names a target the `Makefile` does not
      define; skip when there is no `Makefile` to judge against (a scratch tree).
- [x] Count only STAGE positions (`->` / line start) so prose (`a make target`) is not a finding, and
      skip placeholders (`make ci-<job>`).

## Tests (no mocks; the real guard and the real files)

- [x] `tests/test_dispatch_forms.py::test_a_flow_naming_a_target_that_does_not_exist_is_a_violation`
- [x] `tests/test_dispatch_forms.py::test_a_continuation_of_the_flow_line_is_scanned`
- [x] `tests/test_dispatch_forms.py::test_a_flow_naming_only_real_targets_passes`
- [x] `tests/test_dispatch_forms.py::test_prose_that_merely_says_make_target_is_not_a_violation`
- [x] `tests/test_dispatch_forms.py::test_a_placeholder_stage_is_not_a_violation`
- [x] `tests/test_dispatch_forms.py::test_the_repository_flows_name_only_real_targets`
- [x] Rule-6c proof: 2 of the tests fail on the pre-fix guard (`origin/main` + the new test file),
      all 30 pass after.

## Out of scope, filed

- [x] #335 — implementing the promised push pre-flight (`make agent-image-push-check`) is its own
      change; named in the README paragraph and in `Not covered` in the proposal.

## OpenSpec

- [x] `proposal.md`, `specs/workflow-flow-targets/spec.md`, `tasks.md` written.
- [x] `make openspec-validate NAME=workflow-flow-targets` passes.

## Gates

- [x] `make lint` passes.
- [x] `make check-dispatch-forms` passes (and is NOT vacuous: the negative proof above).
- [x] `make check-wiring` and `make check-docs` pass.
- [x] The rest of the loop runs in CI on this branch.
