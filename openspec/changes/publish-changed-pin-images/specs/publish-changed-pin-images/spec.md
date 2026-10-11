# publish-changed-pin-images

## ADDED Requirements

### Requirement: the matrix keeps only images whose tag changed
When the matrix is scoped to a ref, an engine×arch image MUST be included
only when its image tag differs from that ref. The tag is
`llgenie/<id>:<pin8>-<image-hash>-<arch>`: it moves when the pin hash moves,
when that variant's params or its committed Dockerfile change, or when a file
every image is built from changes (`entrypoint.sh`, `engine_runner.py`). An
unchanged tag MUST be left out. A scope that matches nothing MUST still emit
the `none` placeholder row.

#### Scenario: only the engine whose pin moved is built
- **Given** two engines, and a ref where only one engine's `pinned` differs
- **When** the matrix is scoped to that ref
- **Then** only that engine's variants are included
- **And** the other engine's variants are not
- **Test:** `tests/test_engine_image_matrix.py::test_matrix_keeps_only_the_engine_whose_pin_changed`

#### Scenario: a shared build file rebuilds every image
- **Given** a ref where no pin changed but `scripts/engine_runner.py` did
- **When** the matrix is scoped to that ref
- **Then** every engine's variants are included
- **Test:** `tests/test_engine_image_matrix.py::test_matrix_rebuilds_all_when_a_shared_build_file_changes`

#### Scenario: no change publishes nothing
- **Given** a ref where every image tag is identical
- **When** the matrix is scoped to that ref
- **Then** the only row is the `none` placeholder
- **Test:** `tests/test_engine_image_matrix.py::test_matrix_placeholder_when_no_tag_changed`

#### Scenario: the committed tree compared with itself builds nothing
- **Given** a scratch repo holding this repo's committed params, Dockerfiles,
  `entrypoint.sh` and `engine_runner.py`, its working tree untouched
- **When** the matrix is scoped to that repo's own commit
- **Then** the only row is the `none` placeholder
- **Test:** `tests/test_engine_image_matrix.py::test_unchanged_committed_tree_publishes_nothing`

#### Scenario: one moved pin on the real engine tree builds only that engine
- **Given** the committed build inputs of all 13 engines, with `ollama`'s pin
  moved in the working tree
- **When** the matrix is scoped to the untouched commit
- **Then** only ollama's CI variants are rows
- **Test:** `tests/test_engine_image_matrix.py::test_a_moved_pin_builds_only_that_engine`

#### Scenario: one moved frozen variant param builds only that row
- **Given** the committed build inputs, with `vllm`'s cpu `port` changed
- **When** the matrix is scoped to the untouched commit
- **Then** only the `vllm`×`cpu` row is included, not its cuda/rocm rows
- **Test:** `tests/test_engine_image_matrix.py::test_a_variant_param_builds_only_that_variant`

#### Scenario: a shared build file on the real tree rebuilds every CI engine
- **Given** the committed build inputs, with `scripts/engine_runner.py` edited
- **When** the matrix is scoped to the untouched commit
- **Then** every engine the unscoped CI matrix would build is included
- **Test:** `tests/test_engine_image_matrix.py::test_a_shared_build_file_rebuilds_every_ci_engine`

### Requirement: the tag hash stays the published scheme
The bytes an image tag hashes MUST stay `variant params + committed Dockerfile
+ entrypoint.sh + engine_runner.py`, concatenated in that order. The tag is the
image `make install` pulls from the registry, so a change to what is hashed —
or to how the parts are joined — moves every engine's tag at once, leaves every
image already published unreachable, and fails every install job with
`not published` while the scoped matrix rebuilds nothing.

#### Scenario: the tag digest is pinned
- **Given** a fixed fixture (variant params, Dockerfile, entrypoint, runner)
- **When** its tag bytes are hashed
- **Then** the digest is the one the published tags were built with
- **Test:** `tests/test_engine_image_matrix.py::test_tag_digest_is_the_published_scheme`

#### Scenario: every input the tag claims to cover moves it
- **Given** the same fixture
- **When** the pin, a variant param, the Dockerfile, `entrypoint.sh` or
  `engine_runner.py` is changed one at a time
- **Then** each change moves the digest, and the untouched fixture does not
- **Test:** `tests/test_engine_image_matrix.py::test_tag_hash_follows_every_input_it_claims`

#### Scenario: the matrix's tag is the tag install pulls
- **Given** every committed engine×variant params file
- **When** the matrix's tag and `engine_skills.image_spec`'s tag are computed
- **Then** they are the same tag for every engine×variant
- **Test:** `tests/test_engine_image_matrix.py::test_matrix_tag_is_the_tag_install_pulls`

### Requirement: every matrix row is an image make build-engine can build
When the CI matrix emits an engine×arch row, that row MUST resolve to the
committed params file and the generated Dockerfile that
`make build-engine ENGINE=<id> ARCH=<arch>` builds, under a real tag.

#### Scenario: each row resolves to a buildable engine
- **Given** the unscoped CI matrix (every engine×arch CI builds)
- **When** each row is resolved the way `make build-engine` resolves it
- **Then** its params file and its Dockerfile exist, and its tag names the image
- **Test:** `tests/test_engine_image_matrix.py::test_every_matrix_row_is_an_engine_make_build_engine_can_build`

### Requirement: the matrix tests run in the make gate
The tests that lock this behaviour MUST be driven by a `make` target CI runs, so
a matrix that skips an image the install path later asks for turns the gate red
instead of shipping.

#### Scenario: the matrix tests are part of the hermetic unit gate
- **Given** `make test-unit`, the command the CI `unit` job runs
- **When** the gate runs
- **Then** `tests/test_engine_image_matrix.py` runs inside it
- **Test:** `Makefile` target `test-unit` (CI job `unit` → `make ci-unit`)

### Requirement: a push publishes only changed images
The CI push path MUST scope the engine matrix the same way a pull request
does. On a push to `main` the scope is the parent commit. A push whose
parent is unknown (the all-zero before sha of a new branch) MUST keep the
full matrix.

#### Scenario: the push workflow scopes the matrix
- **Given** the CI workflow
- **When** a push event builds the engine matrix
- **Then** it passes `CHANGED` set to `github.event.before`
- **And** it falls back to the full matrix when that sha is all zeros
- **Test:** `tests/test_engine_image_matrix.py::test_push_workflow_scopes_the_matrix`

#### Scenario: a changed image is built, tested and published
- **Given** the engine-image job, shared by a pull request and a push to main
- **When** CI runs a matrix row
- **Then** it builds, tests and publishes that row's engine and arch
- **And** the placeholder row is skipped, so an unchanged tag is not published
- **Test:** `tests/test_engine_image_matrix.py::test_every_changed_image_is_built_tested_and_published`

#### Scenario: each bumped engine is built, tested and published with its make arguments
- **Given** the committed engines, and one engine whose pin differs from the parent commit
- **When** the CI matrix is scoped to that parent
- **Then** the make commands CI runs are `build-engine`, `test-engine-stage` and `push-engine` for that engine and each of its CI variants, with `ENGINE`, `ARCH` and `TEST` taken from that row
- **And** doing this for every engine yields only that engine's commands
- **Test:** `tests/test_engine_image_matrix.py::test_each_bumped_engine_gets_its_make_calls`

### Requirement: Hub calls send the Actions token
Every Hugging Face request MUST send `Authorization: Bearer` when a token
resolves. The token is `HF_TOKEN` or `HUGGING_FACE_HUB_TOKEN` in the
environment, otherwise the `HF_TOKEN=` line in `~/.zshrc` or `~/.bashrc`.
CI MUST set `HF_TOKEN` from the `HF_TOKEN` Actions secret on every workflow,
and MUST pass that secret into `pipeline.yml` and `published.yml` with
`secrets: inherit`. A URL that is not `huggingface.co` MUST NOT receive the
token.

#### Scenario: the environment token is sent only to the Hub
- **Given** `HF_TOKEN` is set in the environment
- **When** a request is built for `huggingface.co` and another for `github.com`
- **Then** only the Hub request carries `Authorization: Bearer <token>`
- **Test:** `tests/test_hf_auth.py::test_env_token_is_sent_only_to_the_hub`

#### Scenario: a login rc supplies the token when the environment is empty
- **Given** the environment has no Hub token and `~/.bashrc` sets `HF_TOKEN`
- **When** the token is resolved for the `hf` CLI
- **Then** the rc value is the token the CLI receives
- **Test:** `tests/test_hf_auth.py::test_bashrc_token_is_used_when_the_environment_is_empty`

#### Scenario: CI injects the Actions secret
- **Given** the CI workflows
- **When** a job can call the Hub
- **Then** `HF_TOKEN` is `${{ secrets.HF_TOKEN }}` and the reusable workflows use `secrets: inherit`
- **Test:** `tests/test_hf_auth.py::test_workflows_inject_the_actions_secret`
