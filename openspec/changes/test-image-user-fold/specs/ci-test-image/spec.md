## ADDED Requirements

### Requirement: The test image serves non-root

The `llgenie/test` image SHALL declare a non-root default identity (`USER
1000:1000` as its final instruction), and the Makefile SHALL run the plain
test-container stages as the uid that owns the bind-mounted checkout
(`-u "$(shell id -u):$(shell id -g)"`), so the gate neither runs as root nor
writes files the checkout's owner cannot own. Engine-driven stages that mount the
host docker socket MAY keep the root override, and SHALL say why in the Makefile.

#### Scenario: the tree is DS-0002 clean

- **WHEN** `make security-scan TOOL=trivy` runs against the tree after the fold
- **THEN** the scan reports zero `DS-0002` findings tree-wide (rc=0)

#### Scenario: the fold rides the publish-deferral lane

- **WHEN** a `pull_request` run whose change moved the `llgenie/test` content hash
  pulls the tag in any test-env job
- **THEN** `pull` prints `::warning title=publish deferred::`, builds the moved
  tag locally, exits 0, and the test-env legs run green against the built image

#### Scenario: container stages keep working as the mapped uid

- **WHEN** `make lint` and a pytest suite run through `$(TEST_RUN)` after the fold
- **THEN** `git ls-files` succeeds in the lint stage (the system gitconfig holds
  `safe.directory *`), and the container writes its bytecode/cache as the mapped
  uid without permission errors
