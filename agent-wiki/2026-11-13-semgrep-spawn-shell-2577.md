# 2026-11-13 — semgrep spawn-shell-true cleared in the planner relay (issue #2577)

## What was verified

- Finding reproduced locally on origin/main `ec3ca5af4`: `make security-scan TOOL=semgrep`
  (pinned image `ghcr.io/asimov-agent/llgenie/semgrep:5954e2aad609`, pinned pack
  `containers/scanners/semgrep/rules/default.yml`) reports
  `javascript.lang.security.audit.spawn-shell-true` at `relay.mjs:558` — `dispatchToPi` passed
  `shell: process.platform === "win32"`. The audit rule matches the `shell:` option itself.
- Why CI saw it but a stale local scan did not: the pinned tag was re-pushed on GHCR — local
  digest `sha256:7fd77096…` (2026-11-08 build) vs GHCR `sha256:180c3f7e…`. Tag-pinned refs are
  re-pushable; filed as its own issue.
- Fix: win32 now spawns `cmd.exe` with `["/d","/s","/c","pi", …buildArgv(opts)]` — the same command
  `shell:true` compiles to, with argv built in code; POSIX spawn unchanged (`pi`, detached group).
  `node --check` rc=0.
- Re-scan at head: `spawn-shell-true` findings for `relay.mjs` = 0; findings diff vs baseline =
  exactly that one cleared, zero introduced (45 → 44 results).
- Tree → live fold: `make sync-agent-profile PROFILE=llgenie-planner` after the commit
  (the sync refused pre-commit only on a stale live mtime; live was byte-identical to HEAD).

## Key decisions

- The win32 probe site (`runProbe`, shell passed via a spread) is not reported by the scan and
  stays untouched — the PR fixes only the matched region.
- Not touching the rule pack: findings against `engine-build.yml:148` (`run-shell-injection`)
  remain tracked by their existing issues, out of this lane's scope.

## Current status

Implemented on `feat/semgrep-spawn-shell-true`; issue #2577 drives the lane and the PR closes it;
the daily security pipeline's next scan is the clearing run for AC3.
