# secret-scan — spec delta

Capability: `secret-scan`
Issue: [#360](https://github.com/asimov-agent/llgenie/issues/360)

## ADDED Requirements

### Requirement: the working tree is scanned for a committed credential VALUE

`make secret-scan` SHALL run gitleaks from its own pinned image over the working tree with the
repository's config and `--redact`, and SHALL exit non-zero on a finding with the remediation
(remove the value, rotate the key, never allowlist a live value).

WHEN a credential VALUE is committed in the working tree,
THEN the scan SHALL fail and name the file and rule, never the value.

#### Scenario: a committed value fails the scan
Given a working tree with a credential-shaped value in a file the config does not allowlist,
When   `make secret-scan` runs,
Then   it exits non-zero and prints the remediation instead of passing.
- **Test:** `CI job `linux` -> `make secret-scan`` (the scan needs a container engine; the hermetic half pins the target and its inputs: `tests/test_secret_scan.py::test_the_three_targets_exist_and_name_real_inputs`)

#### Scenario: the repository as it stands is clean
Given the tracked tree and its fixtures,
When   `make secret-scan` runs,
Then   it reports no leak and exits zero.
- **Test:** `CI job `linux` -> `make secret-scan``

### Requirement: the scanner is proven able to catch a value

`make secret-scan-self-test` SHALL plant a fake credential in a temporary directory and SHALL fail
unless the same image and config catch it, and SHALL also require the same tree to be clean once the
plant is removed.

WHEN the scanner silently does nothing,
THEN the self-test SHALL fail — a scanner that exits zero on a planted key is a false green.

#### Scenario: the planted credential is caught and the value never printed
Given a temporary directory holding a fake `ghp_`-shaped value,
When   the self-test runs the real scanner on it,
Then   the scan exits non-zero, the planted value appears in no output, and the same directory is
       clean after the plant is removed.
- **Test:** `CI job `linux` -> `make secret-scan-self-test``

### Requirement: the configuration cannot silently scan nothing

`.gitleaks.toml` SHALL extend gitleaks' default rule set, and every allowlist path SHALL be a
reviewed, non-live fixture — never a live value and never a credential-shaped pattern.

WHEN the config is read,
THEN it extends the defaults, defines no replacement rule set, and allows only the documented files.

#### Scenario: the config extends the defaults
Given `.gitleaks.toml`,
When   the suite reads it,
Then   it carries `[extend]` with `useDefault = true` and no `[[rules]]` block.
- **Test:** `tests/test_secret_scan.py::test_the_config_extends_the_default_rule_set`

#### Scenario: only reviewed non-live paths are allowlisted
Given the allowlist entries,
When   the suite reads them,
Then   every path is one of the documented fixtures and no entry names a credential prefix.
- **Test:** `tests/test_secret_scan.py::test_every_allowlist_entry_is_a_documented_non_live_path`

### Requirement: the history scan refuses a worktree

`make secret-scan-history` SHALL refuse (exit 1, with a reason) in a git worktree, where `.git` is a
file and a history scan would report a clean history it never read, and SHALL scan the history in a
real clone.

WHEN the checkout is a worktree,
THEN the history scan SHALL stop and say why.

#### Scenario: a worktree is refused, not reported clean
Given a worktree checkout,
When   `make secret-scan-history` runs,
Then   it exits 1 and says it needs a real clone.
- **Test:** `tests/test_secret_scan.py::test_the_three_targets_exist_and_name_real_inputs`

### Requirement: the self-test commits no credential-shaped literal

The self-test script SHALL assemble its plant from parts, so the repository carries no
credential-shaped literal and `check-secret-output`'s shape rule does not match the script.

WHEN the guard's shape pattern runs over the self-test script,
THEN it finds nothing.

#### Scenario: the shape guard does not match the self-test
Given the self-test script,
When   the guard's credential-shape pattern runs over its source,
Then   it finds no credential-shaped literal, because the plant is assembled at run time.
- **Test:** `tests/test_secret_scan.py::test_the_self_test_plants_a_value_without_committing_one`

