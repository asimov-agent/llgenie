# Proposal: semgrep-spawn-shell-true

## Why

Issue #2577: the daily security pipeline (scan run 43216472585, filed 2026-11-12T12:19:41Z)
reports `javascript.lang.security.audit.spawn-shell-true` at HIGH against
`agents/llgenie-planner/skills/autonomous-ai-agents/pi-delegate/scripts/relay.mjs:558` —
`dispatchToPi` passes `shell: process.platform === "win32"` to `child_process.spawn`. The rule
matches the `shell:` option itself, whatever its value: a code finding stays filed until the
matched region is edited. The win32 `shell: true` is only there because the install is the
`pi.cmd` batch shim and Node >= 18 refuses to spawn `.cmd` shims without a shell.

The finding was reproduced locally on origin/main `ec3ca5af4` with the pinned scanner image
(`ghcr.io/asimov-agent/llgenie/semgrep:5954e2aad609`) and the pinned rules pack: the pinned tag was re-pushed
on GHCR (local digest `sha256:7fd77096…` from 2026-11-08 vs current `sha256:180c3f7e…`), and
`make security-scan TOOL=semgrep` reports the finding with the current image (measured 2026-11-13).

## What Changes

- `dispatchToPi` in `agents/llgenie-planner/skills/autonomous-ai-agents/pi-delegate/scripts/relay.mjs`
  drops the spawn `shell:` option entirely: on win32 it spawns `cmd.exe` with
  `["/d", "/s", "/c", "pi", ...buildArgv(opts)]` — the same command `shell: true` compiles to,
  requested with argv built in code; on POSIX the spawn is unchanged (`pi`, argv, detached).
- No other call site changes: `spawn-shell-true` matches only the `dispatchToPi` spawn in this tree
  (the `runProbe` win32 probe passes `shell` through a spread and is not reported by the scan).
- The profile file is folded to the live profile with `make sync-agent-profile PROFILE=llgenie-planner`;
  the commit and PR carry the `SYNC:` line (tree → live is one-way).

## Goals

- `spawn-shell-true` no longer matches `relay.mjs` in a pinned-pack scan (issue #2577 AC1/AC2);
  the win32 shim resolution behavior is unchanged.

## Out of scope (separate issues)

- The `semgrep:5954e2aad609` scanner ref is a mutable content tag, not an immutable digest: GHCR
  re-pushed it with a different digest and the scan results moved with it. Filed separately.
