# A refresh path for the committed semgrep rules pack (#2283 criterion 2)

BASE = `e141cc9b` (origin/main), fetched 2026-11-09.

## What changed

Issue #2283's criteria 1 & 3 (recency floor + negative control) merged as PR #2315
(`RULES_BASELINE_DAYS = 30` in `scripts/security_scan.py`, `rules_captured_at`/`rules_count`
stamped by `scanner_image.write()`). Criterion 2 — the refresh path that actually re-captures
`p/default` so the floor can be satisfied — is delivered here.

- `scripts/semgrep_rules.py` (new): `make semgrep-rules-refresh` runs the **pinned scanner
  image** (`semgrep --config p/default --validate` in `digests.json['semgrep'].ref`), fetches the
  live pack YAML (`https://semgrep.dev/c/p/default`), re-applies #2082's credential-shape escapes
  (`\x59` for the private-key `KEY`, `\x2e`/`\x2f` for the Slack webhook host/path) so the
  committed bytes are not themselves a gitleaks/push-protection finding, writes
  `containers/scanners/semgrep/rules/default.yml`, and re-stamps `rules_sha` /
  `rules_captured_at` / `rules_count` through `scripts/scanner_image.py::write`.
- `.github/workflows/semgrep-rules-refresh.yml` (new, monthly schedule + `workflow_dispatch`,
  owner guard, never merges): runs the refresh; when the pack changed it commits + opens/updates
  the `chore/semgrep-rules-refresh` re-pin PR with the `SYNC:`/`AGENTS:`/`BASE:` stamp.
- `tests/test_semgrep_rules.py` (new, hermetic): `write()` records
  `rules_sha == sha256(rewritten default.yml)` and `rules_captured_at == the refresh date`;
  `neutralise()` removes every gitleaks shape and FAILS a no-op on a drifted upstream spelling
  (so a refresh never silently commits a credential-shaped pack).
- Docs: `docs/SCANNERS.md` documents `make semgrep-rules-refresh`; the new workflow is exempted
  from `workflow_run` coverage with a reason.

## Verification

- `make semgrep-rules-refresh` against the live tree: pinned image reports `1074 rule(s)`,
  fetched `2520189` bytes, wrote `default.yml` (1073 rules, `rules_sha=8695f5d0…`,
  `rules_captured_at=2026-11-09`); reverted before commit so the PR ships the mechanism only.
- `neutralise()` on the live pack: `make secret-scan` (gitleaks) reports 0 leaks; the pinned
  image's `--config <neutralised pack> --validate` reports `1074 rule(s)` — the escapes preserve
  the loaded rule semantics.
- `tests/test_semgrep_rules.py`: 4 passed. `make check-workflows`, `check-wiring`, `check-docs`,
  `check-security-scan`, `check-scanner-images`, `check-renovate` all green.

See PR <pr-in-body>. Implements issue #2283.
