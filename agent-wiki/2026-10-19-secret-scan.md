# 2026-10-19 — a committed credential VALUE is scanned, and the scanner is tested (#360)

Implements [#360](https://github.com/asimov-agent/llgenie/issues/360) (PR [#368](https://github.com/asimov-agent/llgenie/pull/368)),
a child of the bot-fleet parent
[#357](https://github.com/asimov-agent/llgenie/issues/357). OpenSpec change: `openspec/changes/secret-scan`.

## What was wrong (measured)

No `.gitleaks.toml`, no `secret-scan*` target, no gitleaks anywhere in the tree. `check-secret-output`
reads the shapes a script *prints* — a key written in another provider's shape (a PAT, a JWT, an
AWS-style key, a bearer in a URL) was invisible to it, and nothing read the working tree or the history
for a committed value.

## What changed

- `.gitleaks.toml` with `[extend] useDefault = true` and allowlists only for reviewed non-live
  fixtures (the guard's own patterns, the bot-log fixtures, the JEV provider-value fixture in
  `tests/test_agent_nerve.py`) — **by path**, so the decision is visible.
- `make secret-scan` (working tree, `--redact`, remediation text), `make secret-scan-history` (refuses
  a worktree rather than reporting an unread history), `make secret-scan-self-test`
  (`scripts/secret_scan_self_test.py`).
- CI: the linux job runs the scan and its self-test beside `make ci-lint`; macOS does not (no container
  engine).
- `tests/test_secret_scan.py` in `make test-unit`: config extends the defaults, allowlists reviewed
  paths only, targets name real inputs, history scan refuses a worktree, the self-test commits no
  credential-shaped literal, CI wiring on Linux.

## Measured

```
$ make secret-scan
2026-10-19 INF scanned ~5.46 MB in 288ms
2026-10-19 INF no leaks found
$ make secret-scan-self-test
[secret-scan-self-test] planted credential caught (exit 1), value never printed
[secret-scan-self-test] OK: the planted credential is caught and the clean tree is green.
```

One real finding appeared on the first run — `tests/test_agent_nerve.py:456` (`generic-api-key`, a
fake `jev-…` provider value in a fixture). It is allowlisted **by path**, not by value or by a
credential-shaped regex, and the self-test proves the scanner still catches a genuine shape (its plant
lives outside the repository, so no allowlist applies).

## Follow-ups

- #358 (credential seam, merged as #365), #359 (redacted transcript, PR #366), #361 (whole-stdout and
  `github.token` rules, PR #367), #362 (masked web reach), #363 (loud missing key), #364 (empty `GH_TOKEN`).
