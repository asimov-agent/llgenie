# A refresh path for the committed semgrep rule pack

- [x] `scripts/semgrep_rules.py` (new): `refresh` resolves `p/default` through the pinned scanner
      image (`semgrep --config p/default --validate`), fetches the live pack YAML, re-applies the
      credential-shape escapes (`\x59`, `\x2e`/`\x2f`), writes `containers/scanners/semgrep/rules/default.yml`,
      and re-stamps `rules_sha` / `rules_captured_at` / `rules_count` via `scripts/scanner_image.py::write`.
- [x] `Makefile` `semgrep-rules-refresh` target (help line + `.PHONY` + docs).
- [x] `.github/workflows/semgrep-rules-refresh.yml`: `schedule` (own odd cron minute) + `workflow_dispatch`,
      the owner/guard shape, never merges, opens or updates `chore/semgrep-rules-refresh` only on a change,
      body stamped `SYNC:`/`AGENTS:`/`BASE:`.
- [x] `tests/test_semgrep_rules.py`: `write()` records `rules_sha == sha256(rewritten default.yml)` and
      `rules_captured_at == the refresh date`; `neutralise()` removes every gitleaks shape and refuses a
      no-op on a drifted upstream spelling.
- [x] Docs: agent-wiki note + `docs/changes.d/` fragment + `docs/SCANS.md` refresh matrix row.
- [x] Gates: `make openspec-validate NAME=semgrep-rules-refresh`, `make lint`, `make check-docs`,
      `make check-workflows`, `make check-wiring`, `make check-security-scan`, `make bot-preflight` all green.
