# queued-starvation-and-path-gate

## ADDED Requirements

### Requirement: A starved queue is distinguishable from a broken PR, in writing

`docs/BOTS.md` SHALL state that a repo-wide `queued` state with no `in_progress` runs is runner supply,
SHALL give the commands that measure it, SHALL distinguish it from a single PR whose empty rollup is a
conflicting branch, and SHALL state that pushing to drain a queue re-queues the matrix.

#### Scenario: the reader measures supply first

Given every open PR reads `BLOCKED` and no check has completed
When  the reader runs `gh run list --limit 100 --json status`
Then  many `queued` with zero `in_progress` identifies a starved queue, and the documented remedy is to
      wait, not to rebase or merge.

### Requirement: A pull request queues only the base toolchains it changed

`make list-engine-base-images CHANGED=<ref>` SHALL name only the shared base toolchains whose rendered
`Dockerfile.<backend>` differs from `<ref>`, and SHALL emit exactly one `backend: none` row when none
does. `ci.yml`'s `engine-base` job SHALL take its matrix from that output, and every one of its steps
SHALL carry the placeholder-row skip, so no job-level condition and no skipped step is introduced.

#### Scenario: a diff that touches no toolchain queues one placeholder row

Given a branch whose `containers/engines/base/Dockerfile.*` files are identical to `origin/main`
When  `make -s list-engine-base-images JSON=1 CHANGED=origin/main` runs
Then  it prints `{"include": [{"backend": "none"}]}`, and the run shows one `engine-base-none` row that
      skips every step.

#### Scenario: a changed toolchain is still built

Given a branch that changes one backend's toolchain
When  the same command runs
Then  that backend alone appears, so its image is built and its engines still have a base to build FROM.

#### Scenario: an unknown ref keeps the full sweep

Given a push run whose `before` sha is unknown (a new branch)
When  the matrix is computed
Then  all four backends are queued.
