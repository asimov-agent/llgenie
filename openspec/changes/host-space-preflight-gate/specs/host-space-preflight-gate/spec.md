## ADDED Requirements

### Requirement: host-space-headroom-gate

`scripts/check_host_space.py` SHALL measure both the space and the inode headroom of a mount from
`df` (`-h` and `-i`), SHALL refuse (exit 1) when the space free is below a threshold (default 20%) OR
the free inodes are below a threshold (default 50,000), naming the offending axis, and SHALL never
silently pass when `df` cannot be read (an unreadable measurement is an error). A `report` mode SHALL
print the measurement and the verdict and exit 0.

#### Scenario: a healthy tmpfs is green

- **Given** a mount with ≥20% space free and ≥50k free inodes
- **When** `check_host_space.py check` runs on it
- **Then** it exits 0 and prints the OK verdict naming both axes
- **Test:** `tests/test_check_host_space.py::test_healthy_tmpfs_exits_0_and_reports_both_axes`

#### Scenario: below-threshold space is refused

- **Given** a mount with <20% space free (inodes fine)
- **When** `check_host_space.py check` runs
- **Then** it exits 1 and names the space axis
- **Test:** `tests/test_check_host_space.py::test_low_space_free_is_refused`

#### Scenario: below-threshold inodes are refused

- **Given** a mount with <50k free inodes (space fine)
- **When** `check_host_space.py check` runs
- **Then** it exits 1 and names the inode axis
- **Test:** `tests/test_check_host_space.py::test_low_inodes_free_is_refused`

#### Scenario: an unreadable df is an error, not a pass

- **Given** a `df` that exits non-zero
- **When** the gate runs
- **Then** it raises/refuses rather than silently proceeding
- **Test:** `tests/test_check_host_space.py::test_a_df_that_cannot_be_read_is_an_error_not_a_pass`

### Requirement: host-space-gate-is-a-make-preflight

The repo SHALL expose `make check-host-space` that runs the host-space gate, and the planner's
standing behaviour (under `agents/llgenie-planner/`) SHALL require it be run before dispatching a lane
onto a `/tmp` worktree or container build, refusing below the threshold while leaving occupant
attribution and cleanup owner-gated.

#### Scenario: the planner refuses a doomed dispatch

- **Given** `make check-host-space` exits 1 (tmpfs below threshold)
- **When** the planner is about to dispatch a lane onto a `/tmp` container build
- **Then** it does not dispatch the doomed run and says the tmpfs is below the headroom threshold
- **Test:** the standing-behaviour text under `agents/llgenie-planner/SOUL.md` + `make check-host-space`
  exit-1 behaviour (`tests/test_check_host_space.py`)
