## ADDED Requirements

### Requirement: the home-path gate scans executed shell lines in agents scripts

The profile gate SHALL scan `agents/**/*.sh` for literal home paths (`/home/<user>/…`) on executed
lines, and SHALL NOT flag a line whose first non-blank character is `#`.

#### Scenario: an executed literal home path in a lane script goes red
- **Given** an `agents/<profile>/…/scripts/x.sh` whose executed line embeds `/home/<user>/…`
- **When** `make check-agent-profiles` runs
- **Then** the gate exits non-zero naming that file and line with a `home-path-literal` finding
- **And** the finding tells the writer to use `$HOME` or the `<user>`/`%h` forms

#### Scenario: a comment recounting a defect keeps its absolute path
- **Given** a `.sh` line starting with `#` that quotes a literal `/home/<user>/…` path
- **When** the gate runs
- **Then** no finding is raised for that line

#### Scenario: python literals stay out of scope
- **Given** `scripts/*.py` files that build home paths with `pathlib.Path.home()`
- **When** the gate runs
- **Then** they are not flagged (a Python literal rewritten to `$HOME` never expands)

### Requirement: the rebase lane's stack-replay works on any host

`stack-replay.sh` SHALL derive its fallback home from `$HOME` instead of a hard-coded account path.

#### Scenario: replay on a host without /home/<author-user>
- **Given** a lane host whose home is not the author's `/home/<user>` path
- **When** the rebase lane runs `stack-replay.sh`
- **Then** the script resolves its worktree parent under `$HOME` and proceeds
