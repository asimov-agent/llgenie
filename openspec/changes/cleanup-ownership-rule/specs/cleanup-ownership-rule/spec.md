# cleanup-ownership-rule

## ADDED Requirements

### Requirement: cleanup commands name their own lane's paths, never a shared /tmp wildcard

Every cleanup/reclaim action a lane runs MUST name the lane-owned path(s) it is cleaning — a specific
file or directory the lane created itself (e.g. `$HOME/repository/git/llgenie-wt/<lane>`, a named
`$HOME/.cache` scratch file) — and MUST NOT use a wildcard over shared `/tmp`. No prompt, script, agent
instruction, or make target in this repo may carry an `rm -rf /tmp/*`-shaped command. `/tmp` occupants
owned by the system or by other tenants are never fleet cleanup targets. Reclaiming `/tmp` worktrees
stays the safe collector's job (`make reclaim-tmp-worktrees`, issue #2141).

#### Scenario: a lane cleans its own scratch by name

- **Given** a lane that created `$HOME/repository/git/llgenie-wt/verify2127` and a named scratch file it wrote itself
- **When** the lane cleans up after its measurement work
- **Then** the cleanup command names exactly those lane-owned paths, and no glob over `/tmp` appears in the command

#### Scenario: a shared /tmp glob is refused

- **Given** a proposed cleanup that would run `rm -rf /tmp/*` or any `/tmp` wildcard variant
- **When** the fleet rule is applied to that proposal (in review, in a prompt, or in a make target edit)
- **Then** the command is rejected as a rule violation, and the lane is pointed at named paths or at `make reclaim-tmp-worktrees`

#### Scenario: other-tenant occupants are never touched

- **Given** `/tmp` occupants owned by systemd, the display manager, or another tenant (X sockets, private service dirs, session caches)
- **When** any fleet lane performs cleanup
- **Then** those occupants are left in place, untouched, by design
