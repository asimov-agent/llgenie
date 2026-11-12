## MODIFIED Requirements

### Requirement: The rebase-lane harness names its own branch names
The revert-detector harness (`test-revert-detector.sh`) SHALL create every throwaway repo with an
explicit initial branch and SHALL reference only branch names it created itself in later
checkouts, so its verdicts do not depend on the host's `init.defaultBranch`.

#### Scenario: a modern-git host runs the harness
- **Given** a host whose `git init` defaults to `main`
- **When** `tests/test_rebase_lane_scripts.py::test_the_revert_detector_catches_a_revert_and_clears_a_restored_tree` runs the harness
- **Then** the harness exits 0 and no `pathspec 'master' did not match` error occurs

#### Scenario: the revert control still reds
- **Given** the fixed harness on any host
- **When** the `-X theirs` case rebases away a base line the branch never touched
- **Then** the detector still exits 1 for that case and the harness reports PASS overall
