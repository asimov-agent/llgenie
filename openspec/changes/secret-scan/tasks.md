# Tasks

- [x] 1. `.gitleaks.toml`: `[extend] useDefault = true`, allowlists only reviewed non-live fixtures (the guard's own patterns, the bot-log fixtures, the JEV provider-value fixture) — never a live value, never a credential-shaped pattern
- [x] 2. `scripts/secret_scan_self_test.py`: plant a `ghp_`-shaped fake in a temp dir built from parts, require the real scanner to catch it, keep the value out of every output, and require the same tree to be clean once the plant is removed
- [x] 3. Makefile: `GITLEAKS_IMAGE` (pinned) + `secret-scan` (working tree, `--redact`, remediation text) + `secret-scan-history` (worktree refusal) + `secret-scan-self-test`; `.PHONY`, `##` help lines
- [x] 4. `.github/workflows/pipeline.yml`: the linux job runs `make secret-scan` and `make secret-scan-self-test` (Linux only — the macOS job has no container engine)
- [x] 5. `tests/test_secret_scan.py` in `make test-unit`: the config extends the defaults, allowlists only reviewed paths, the three targets name the real inputs, the history scan refuses a worktree, the self-test commits no credential-shaped literal, CI runs both on Linux
- [x] 6. Verified against the real scanner: `make secret-scan` green on the tree (after allowlisting the `tests/test_agent_nerve.py` fixture by PATH), `make secret-scan-self-test` catches the plant and the tree is clean once removed
- [x] 7. `README.md`: the three targets in the secrets section; `agent-wiki/2026-10-19-secret-scan.md`
- [x] 8. Verification: `pytest tests/test_secret_scan.py` (5 passed), `make check-wiring`, `make check-docs`, `make check-secret-output`, `make check-workflows`, `make lint`, `make openspec-validate NAME=secret-scan`
