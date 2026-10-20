# secret-scan

## ADDED Requirements

### Requirement: The working-tree scan reads only content that could be committed

`make secret-scan` SHALL scan the committable set of the working tree — the tracked files plus the
untracked files that are not ignored (`git ls-files -c -o --exclude-standard`) — and SHALL NOT report
a finding for content inside a `.gitignore`d path. It SHALL exit non-zero when a credential VALUE is
present in that set, and zero when it is not.

WHEN a file is ignored by `.gitignore`
THEN a credential-shaped literal inside it is not reported by `make secret-scan`.

#### Scenario: a gitignored build artifact is not scanned

Given a checkout that has run the test suite, so `tests/__pycache__/*.pyc` exists and is ignored,
When  `make secret-scan` runs,
Then  it exits zero and reports no finding for those bytecode files.

- **Test:** `tests/test_secret_scan.py::test_the_committable_set_excludes_ignored_paths`
  (the real tree: `::test_no_ignored_path_is_in_the_real_committable_set`;
  live end-to-end: CI job `linux / unit` → `make secret-scan`)

#### Scenario: a credential in a tracked file is still caught

Given a tracked file carrying a credential-shaped literal,
When  the committable set is computed,
Then  the file is in the set, so the scanner reads it and the scan fails.

- **Test:** `tests/test_secret_scan.py::test_the_committable_set_includes_tracked_and_fresh_untracked_files`
  (the planted-value proof: `make secret-scan-self-test`)

#### Scenario: a fresh untracked file is scanned

Given an untracked file that `.gitignore` does not match,
When  the committable set is computed,
Then  the file is in the set — `git add` would take it, so a secret in it is still a leak.

- **Test:** `tests/test_secret_scan.py::test_the_committable_set_includes_tracked_and_fresh_untracked_files`

#### Scenario: the scan runs the pinned scanner and config

Given the committable set is exported,
When  the scanner runs,
Then  it is the pinned gitleaks image with the repository's `.gitleaks.toml`, and the exported tree
      carries that config, so the rules and allowlists are the ones under review.

- **Test:** `tests/test_secret_scan.py::test_the_scan_uses_the_pinned_image_and_the_repo_config`
