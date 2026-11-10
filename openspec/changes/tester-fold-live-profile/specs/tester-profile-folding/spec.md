## ADDED Requirements

### Requirement: The tester profile in the tree is the live profile
The tree copy `agents/llgenie-tester/` SHALL contain every skill script and reference file the live profile carries, so `make sync-agent-profile PROFILE=llgenie-tester CHECK=1` never refuses a truncating file.

#### Scenario: fold completeness
- **Given** a live-profile tester file with no tree counterpart
- **When** the fold is applied and `make sync-agent-profile PROFILE=llgenie-tester CHECK=1` runs
- **Then** the check exits 0 and names no TRUNCATED file

### Requirement: The fold script stays gate-compliant
The folded `scripts/fold-live-profile.py` SHALL be byte-identical to the live copy except a single `# proc-allow:` marker on the line that spawns `git ls-files`, so `check-proc-gate` passes without altering behaviour.

#### Scenario: proc-gate verdict
- **Given** the folded fold-live-profile.py at the PR head
- **When** `check-proc-gate` inspects the subprocess-spawning line
- **Then** the marker is present on that physical line and the gate exits 0
