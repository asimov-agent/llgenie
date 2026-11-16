# check-workflows delta

## ADDED Requirements

### Requirement: check-workflows runs the full actionlint ruleset

`make check-workflows` SHALL additionally run the full `rhysd/actionlint` ruleset — shellcheck and
section syntax included — over `.github/workflows/`, as a chained `check-workflows-shellcheck` step,
and SHALL exit non-zero when actionlint reports any finding. The actionlint image SHALL be referenced
by digest pin, never by a mutable tag.

#### Scenario: a new shellcheck finding reddens the gate

- **GIVEN** a workflow whose `run:` script introduces a double-quote-to-prevent-globbing expansion
- **WHEN** `make check-workflows` runs
- **THEN** the chained step SHALL run actionlint and the gate SHALL exit non-zero naming the finding
- **Test:** `tests/test_workflows_valid.py::test_check_workflows_chains_the_shellcheck_step`

#### Scenario: the actionlint reference is a digest pin

- **WHEN** the gate's image reference is read from the Makefile
- **THEN** it SHALL be an `@sha256:` pin and SHALL NOT name a mutable tag
- **Test:** `tests/test_workflows_valid.py::test_actionlint_reference_is_digest_pinned`

### Requirement: The queue-key exception is one named, narrow ignore

Actionlint's syntax rule on `unexpected key "queue" in "concurrency" section` SHALL be the ONLY
finding the gate ignores, via exactly one regex naming that message: `concurrency.queue: max` in
`engine-build.yml` is load-bearing (issue #2294 — it is what stopped queued producers being cancelled)
and GitHub accepts the key; actionlint 1.7.12 has not catalogued it. The `-ignore` argument SHALL carry
no other pattern.

#### Scenario: the gate carries exactly the queue-key ignore

- **WHEN** the gate recipe is read
- **THEN** its `-ignore` SHALL match the queue-key message and nothing else
- **Test:** `tests/test_workflows_valid.py::test_actionlint_ignore_carries_only_the_queue_key_rule`

### Requirement: Every workflow `run:` script is shellcheck-clean

No `.github/workflows/*.yml` `run:` script SHALL carry a shellcheck finding: expansions in script
text SHALL be double-quoted, consecutive appends to the same file SHALL share one `{ …; } >> file`
group, a `${{ … }}` substitution SHALL NOT sit inside a single-quoted format string, escape-bearing
output SHALL use `printf`, and command-like values SHALL be assigned through `var=$(command)` or a
direct quoted test — never an indirection shellcheck reads as a command assignment.

#### Scenario: actionlint is clean over the tree

- **GIVEN** the workflow tree at this change
- **WHEN** the pinned actionlint runs over `.github/workflows/` with only the queue-key ignore
- **THEN** it SHALL exit zero with no findings
- **Test:** `make check-workflows-shellcheck` (gate step in CI; digest-pinned container)
