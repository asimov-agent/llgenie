# secret-scan — proposal

Issue: [#360](https://github.com/asimov-agent/llgenie/issues/360) (child of [#357](https://github.com/asimov-agent/llgenie/issues/357))

## Why

llgenie has **no scan for a committed credential VALUE**. Its only secret gate,
`make check-secret-output`, is a static scan of source *text*: it catches the shapes a script leaks
at run time (a printed value, a value in argv, an xtrace, an env dump) and only sees a
credential-shaped literal as a second alarm. A key written in another provider's shape — a PAT, a
JWT, an AWS-style key, a bearer inside a URL — is invisible to it.

Measured on `main@6338fc6`:

```
$ ls .gitleaks.toml                      # No such file or directory
$ grep -n 'secret-scan' Makefile         # no hits
$ grep -rn 'gitleaks' . | grep -v '^./.git/'   # no hits
```

The sibling repo closes it with a real scanner in its own pinned image **and a self-test that proves
the scanner works**: `make secret-scan` (working tree), `secret-scan-history` (refuses a worktree,
where `.git` is a file), `secret-scan-self-test` (a planted fake credential MUST be caught), all run
before the build in CI.

## What Changes

- **`.gitleaks.toml`**: `[extend] useDefault = true` (a config without it scans *nothing* and exits
  zero — the false green this change is about), allowlisting only documented non-live fixtures.
- **Makefile**: `GITLEAKS_IMAGE` pinned, `secret-scan` (working tree, `--redact`), `secret-scan-history`
  (loud refusal in a worktree), `secret-scan-self-test` (`scripts/secret_scan_self_test.py`).
- **`scripts/secret_scan_self_test.py`**: plants a `ghp_`-shaped fake in a temp dir, requires the same
  image + config to exit non-zero, then requires the same tree to be clean once the plant is removed —
  a scanner stuck at either exit code fails the test.
- **`tests/test_secret_scan.py`** in `make test-unit`: the config extends the defaults and allowlists
  no live value; the three targets name the real inputs; the history scan refuses a worktree; CI runs
  both on Linux only (the macOS job has no container engine).
- **`.github/workflows/pipeline.yml`**: the linux job runs `make secret-scan` and
  `make secret-scan-self-test` beside `make ci-lint`.
- **README.md** + **`agent-wiki/2026-10-19-secret-scan.md`**.

## Impact

- A committed key now fails the build with a path, instead of living in the tree until someone reads
  the diff. A finding's remediation is stated: remove it, rotate it, never allowlist a live value.
- One real finding surfaced and was allowlisted **by path, not by value**:
  `tests/test_agent_nerve.py` writes fake `jev-…` provider values to a temp home; the file is a
  fixture generator, and the allowlist entry names it explicitly so a reviewer sees the decision.
- Out of scope, filed separately: the run-time log rules ([#361](https://github.com/asimov-agent/llgenie/issues/361),
  PR #367) and the redacted transcript ([#359](https://github.com/asimov-agent/llgenie/issues/359), PR #366).
