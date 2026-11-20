## ADDED Requirements

### Requirement: OpenSpec CLI runs write as the invoking user

The OpenSpec container run (`OS_OPTS`, used by `openspec-new`,
`openspec-validate`, `openspec-validate-all`, `openspec-status`) SHALL execute
with `-u "$(shell id -u):$(shell id -g)"` and a world-writable `HOME=/tmp`, so
every file the CLI writes under the mounted repo lands owned by the user who ran
`make`. `OS_OPTS` SHALL NOT carry `-u root`.

#### Scenario: fresh change tree is invoker-owned

- **WHEN** `make openspec-new NAME=<probe>` runs on a host worktree cut from `origin/main`
- **THEN** the command exits 0 and `find openspec/changes/<probe> -user root` prints 0 entries

#### Scenario: the seam is pinned in a test

- **WHEN** the Makefile's `OS_OPTS` line is read
- **THEN** it names both `id -u` and `id -g` and contains no `-u root`

### Requirement: deliberate root stages stay root and named

The only container runs that mount the repo as root SHALL be the engine-test
stage that must reach the host `docker.sock` (`ENGINE_TEST_ARGS`) and the
root-tree cleaner (`CI_HOME_CLEAN`), and the pinning test SHALL assert exactly
those two carry `-u root`.

#### Scenario: carve-out count is pinned

- **WHEN** the Makefile's non-Darwin root-mounting run definitions are counted
- **THEN** exactly `ENGINE_TEST_ARGS` and `CI_HOME_CLEAN` carry `-u root`
