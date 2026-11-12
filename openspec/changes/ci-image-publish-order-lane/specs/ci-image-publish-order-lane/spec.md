# Spec: a CI-image publish a `pull_request` run cannot perform is deferred, not fatal

## ADDED Requirements

### Requirement: a `pull_request` run defers a genuinely missing CI image tag to a local build

`scripts/ci_images.py::pull` fetches the published tag (`_pull_and_tag`). When the pull fails, the
tag is genuinely absent from the registry (the `published()` manifest lookup answers non-zero), and
the run is a `pull_request` event (`GITHUB_EVENT_NAME == "pull_request"`), the pull DEFERS instead
of failing: it prints a `::warning title=publish deferred::` line stating that this run cannot
publish the CI image its own change moved (the token is read-only, issue #155) and that the run
which lands the change publishes it (issue #2518), then builds `llgenie/<name>:latest` locally from
the same hashed build context `ensure` uses, and exits 0. Consumer jobs then run their real work
inside the built image.

#### Scenario: a pull_request run whose change moved a CI image tag no longer reds at the pull

Given a `pull_request` run whose head moved a CI image's content hash, so the hash tag is not on
the registry (measured shape: PR #2517, four legs red at `pull test`)
When `scripts/ci_images.py pull test` finishes the failed pull
Then it prints a deferral line naming the landing run's publish and issue #2518
And it exits 0 instead of failing the job
And the consumer leg steps (`make test-env`, `make ci-lint`, `make ci-unit`, …) run their real work
against the built `llgenie/test:latest`

#### Scenario: the deferral builds the same Dockerfile and pushes nothing

Given a `pull_request` run deferring a missing test-image tag
When the deferral runs
Then exactly one local `docker build -t llgenie/test:latest <temp context>` runs with the same
build args `ensure` uses
And no `buildx build --push` and no registry write happens
And the temp build context is removed after the build

### Requirement: non-`pull_request` runs never build a CI image

On `push`, `workflow_run`, `schedule` or manual runs, `pull` keeps its existing contract: a missing
tag exits non-zero with the "CI jobs never build a CI image" error on stderr, and no build is
issued — the publish already ran before those consumers.

#### Scenario: a push run with a missing tag still fails loudly

Given a `push` run (`GITHUB_EVENT_NAME == "push"`) and a registry without the test image's hash tag
When `scripts/ci_images.py pull test` runs
Then it exits 1 naming the missing ref on stderr with the never-build contract
And no build command is issued

### Requirement: the deferral is only for genuinely unpublished tags

A `pull_request` run whose pull fails while the tag IS on the registry (a transient pull failure —
network, daemon) fails the job exactly like any other failed pull; the deferral branch requires the
`published()` lookup to confirm the tag's absence.

#### Scenario: a published tag and a failed pull still reds

Given a `pull_request` run, a registry that HAS the test image's hash tag, and a `pull` command
that fails
When `scripts/ci_images.py pull test` runs
Then it exits 1 with the not-published/failure error
And no build command is issued

### Requirement: a `pull_request` run that finds the tag published pulls it

A `pull_request` run whose registry already has the content-hash tag (the same-repo case: the
`ci-images` job published it mid-run — measured: PR #1738) pulls and tags as today, builds nothing,
and prints no deferral line.

#### Scenario: a same-repo PR pulls the mid-run published tag

Given a `pull_request` run and a registry with the test image's hash tag
When `scripts/ci_images.py pull test` runs
Then the hash ref is pulled and tagged `llgenie/test:latest`
And no build command is issued and no deferral line is printed

### Requirement: the Makefile states the event scope of the pull contract

The `test-image-pull` target comment and the `ci-<job>` seam comment state the truth this change
creates: a missing tag fails non-`pull_request` runs and is deferred to a local build inside
`pull_request` runs (issue #2518). No make target body changes.

#### Scenario: the comments match the script's contract

Given a reader opens the `test-image-pull` target or the `ci-<job>` seam comment
When they read what a missing published tag costs a job
Then the text states the push-run failure and the `pull_request` deferral with its issue refs
