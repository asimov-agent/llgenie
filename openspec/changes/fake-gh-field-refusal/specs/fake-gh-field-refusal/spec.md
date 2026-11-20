# fake-gh-field-refusal

## ADDED Requirements

### Requirement: the shared fake-gh seam refuses `--json` field names the real gh rejects

`tests/gh_fake.py` MUST expose `enforce(argv)`: when `argv` contains `--json` for one of the seven
subcommands the static guard attributes (`pr view|list|checks`, `issue view|list`, `run view|list`),
every requested field name MUST appear in that subcommand's allowlist in
`tests/fixtures/gh-json-fields.json`; on violation the seam MUST print
`Unknown JSON field: "<name>"` on stderr and exit 1, reproducing the real gh failure mode. When the
subcommand is not attributable or no `--json` is present, `enforce` MUST stay silent (it answers the
same attribution scope as the static guard). `preamble(tests_dir)` MUST return a one-line importable
snippet that calls `enforce(sys.argv[1:])` for heredoc'd fake scripts.

#### Scenario: the #513 shape is refused end-to-end

- **Given** a migrated bot test whose leg requests `authorAssociation` from `gh pr view --json`
- **When** the test runs the bot against its fake gh
- **Then** the fake exits 1 with `Unknown JSON field: "authorAssociation"` on stderr and the test observes the failure
- **Test:** `tests/test_gh_fake.py::test_author_association_is_refused_like_real_gh` plus one red pin per migrated family

#### Scenario: valid field lists pass through unchanged

- **Given** a migrated fake gh answering a leg that requests the fields its canned blob answers
- **When** the bot test runs unchanged
- **Then** the guard line is inert and every existing assertion in that file still passes
- **Test:** the unchanged green run of each migrated test file

### Requirement: every bot test whose fake gh answers a `--json` request routes through the seam

Each of the 17 test files pairing a fake gh with `--json` handling MUST install the guard — the
embedded `preamble` line for heredoc'd fakes, a direct `gh_fake.enforce` call for function-shaped
fakes — and MUST carry one red pin exercising the refusal at its own call site.
`tests/test_auto_merge.py`'s existing inline validation MUST be re-homed onto the seam with its
pinned behaviour (field-set assertion) preserved.

#### Scenario: a regression at one leg fails that leg's own test

- **Given** any migrated test file
- **When** its leg's requested field list is perturbed with an invalid name
- **Then** that test goes red at the fake, not merely the static gate
- **Test:** the per-family red pin named in each file

#### Scenario: the seam's allowlist is the static guard's fixture

- **Given** `tests/fixtures/gh-json-fields.json` captured from the real CLI
- **When** `tests/test_gh_fake.py` runs
- **Then** the seam validates against that exact fixture (no second, parallel allowlist exists)
- **Test:** `tests/test_gh_fake.py::test_the_seam_reads_the_static_guard_fixture`
