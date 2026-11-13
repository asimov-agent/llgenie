# Spec delta: pi-delegate relay dispatch (semgrep-spawn-shell-true)

## ADDED Requirements

### Requirement: relay dispatch spawns without the shell option
The `dispatchToPi` spawn in
`agents/llgenie-planner/skills/autonomous-ai-agents/pi-delegate/scripts/relay.mjs`
SHALL NOT pass a `shell` option to `child_process.spawn`, so the pinned-pack
`javascript.lang.security.audit.spawn-shell-true` scan reports no finding for the file.

#### Scenario: win32 shim resolution is preserved
- WHEN the platform is win32
- THEN `dispatchToPi` spawns `cmd.exe` with argv `["/d", "/s", "/c", "pi", ...buildArgv(opts)]`
- AND the brief still rides stdin, never argv
- AND argv still carries only buildArgv()'s fixed flags plus token-validated
  provider/model/session values

#### Scenario: POSIX dispatch is unchanged
- WHEN the platform is not win32
- THEN `dispatchToPi` spawns `pi` with `buildArgv(opts)` exactly as before
- AND the child still leads a new process group (`detached: true`) so `killChild` can fell the tree

#### Scenario: the scanner is clean at the head
- WHEN `make security-scan TOOL=semgrep` runs against the tree with the pinned image and pinned rules pack
- THEN `security-reports/semgrep.json` contains no `spawn-shell-true` result for `relay.mjs`
