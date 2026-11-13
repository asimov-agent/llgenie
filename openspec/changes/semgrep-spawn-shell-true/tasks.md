# Tasks: semgrep-spawn-shell-true

- [x] Baseline: reproduce the finding locally — `make security-scan TOOL=semgrep` on the base
      tree reports `spawn-shell-true` for `relay.mjs:558` (pinned image + pinned pack).
- [x] Rewrite `dispatchToPi` in `relay.mjs`: no `shell:` option; win32 → explicit
      `cmd.exe /d /s /c pi <argv>`, POSIX unchanged; `node --check` passes.
- [x] Re-scan: `make security-scan TOOL=semgrep` rc=0 with no `spawn-shell-true` result for
      `relay.mjs`; no new findings introduced.
- [x] Fold the changed profile file to the live profile (`make sync-agent-profile
      PROFILE=llgenie-planner`); commit + PR carry the `SYNC:` line.
- [x] Mirror issue #2577 (fix shape + measured scan evidence), file the scanner-tag mutability
      out-of-scope issue, docs pair + change index, `make openspec-validate` rc=0.
