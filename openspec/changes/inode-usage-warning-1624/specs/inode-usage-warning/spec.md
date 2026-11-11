## ADDED Requirements

### Requirement: inode-utilisation-warning

`scripts/check_host_space.py` SHALL measure the inode utilisation of the filesystem hosting a given
mount as the percentage of inodes in use via `os.statvfs` (`f_files` and `f_favail`; used =
`f_files - f_favail`) — distinct from the df-based free-inode count — SHALL print a structured WARNING
naming the mount point, the measured percentage and the configured threshold when utilisation is at
or above the threshold (default **85**, configurable via `--inodes-use-max` / module constant
`DEFAULT_INODES_USE_MAX_PCT`), and SHALL route the finding to an OWNER DECISION POINT without any
remediation side effect (the check reads/measures only; it never deletes, prunes or removes files,
and never spawns a deleting subprocess).

#### Scenario: inode utilisation below threshold is an INFO line, not a warning

- **Given** a tmpfs-identified mount whose inode utilisation is below the threshold
- **When** the preflight reports on it
- **Then** it prints an INFO line and no `WARNING` (the check stays green)
- **Test:** `tests/test_check_host_space.py::test_inode_usage_below_threshold_no_warning`

#### Scenario: inode utilisation at or above threshold emits a WARNING naming mount, percentage, threshold

- **Given** a tmpfs-identified mount whose inode utilisation is at/above the threshold
- **When** the preflight reports on it
- **Then** it prints a `WARNING` naming the mount point, the measured percentage and the threshold,
  and routes to an OWNER DECISION POINT, while the check never deletes or prunes
- **Test:** `tests/test_check_host_space.py::test_inode_usage_at_threshold_warns`
- **Test:** `tests/test_check_host_space.py::test_inode_usage_above_threshold_warns_and_names_fields`

#### Scenario: the warning threshold is tunable

- **Given** the `--inodes-use-max` flag (or `DEFAULT_INODES_USE_MAX_PCT` module constant)
- **When** the threshold is lowered below the measured utilisation
- **Then** the WARNING fires at the configured threshold
- **Test:** `tests/test_check_host_space.py::test_inode_usage_warns_with_owner_decision_update_pct`

#### Scenario: a statvfs failure on a tmpfs-identified real mount surfaces as an error

- **Given** a tmpfs-identified mount whose `os.statvfs` raises
- **When** the preflight runs on it
- **Then** it raises `HostSpaceError` (a real measurement that cannot be read surfaces, never
  silently passes)
- **Test:** `tests/test_check_host_space.py::test_inode_usage_statvfs_failure_on_tmpfs_raises`

#### Scenario: a non-tmpfs or missing /tmp is a graceful INFO skip, never an abort

- **Given** an `-identified mount that is not the shared tmpfs, or is absent from the mount table
- **When** the preflight runs on it
- **Then** it prints an INFO skip line and does not fail the preflight
- **Test:** `tests/test_check_host_space.py::test_inode_usage_non_tmpfs_and_missing_mount_skip`
