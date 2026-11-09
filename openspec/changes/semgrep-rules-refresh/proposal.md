# A refresh path for the committed semgrep rule pack (issue #2283 criterion 2)

## Why

The committed semgrep pack (`containers/scanners/semgrep/rules/default.yml`) got a recency floor and a
negative control (criteria 1 & 3 of #2283, merged as PR #2315): `make check-security-scan` reds when
`rules_captured_at` is older than `RULES_BASELINE_DAYS = 30`. But there is no way to satisfy that floor --
no renovate `regexManagers` entry, no make target, no scheduled workflow re-resolves upstream `p/default`,
rewrites `default.yml` + `rules_sha`, and re-stamps the recency fields. A pack that trips the floor today is
a red run with no re-pin path; criterion 2 (the refresh path) is the undelivered half of #2283.

## What changes (task checklist)

- [ ] A refresh path (`make semgrep-rules-refresh`, driven by `scripts/semgrep_rules.py` and the new
      `.github/workflows/semgrep-rules-refresh.yml` scheduled workflow) that:
      1. re-resolves upstream `p/default` through the pinned scanner image (`semgrep --config p/default
         --validate` inside `containers/scanners/digests.json['semgrep'].ref`),
      2. fetches the live pack YAML,
      3. re-applies the credential-shape escapes the committed pack carries (`\x59` for the PGP /
         private-key `KEY`, `\x2e`/`\x2f` for the Slack webhook host/path, issue #1284/#2105) so a raw
         fetch does not red `make secret-scan`,
      4. rewrites `containers/scanners/semgrep/rules/default.yml` and re-stamps `rules_sha`,
         `rules_captured_at` (the refresh date) and `rules_count` through the existing
         `scripts/scanner_image.py::write` discipline (`make scanner-digests`),
      5. opens the re-pin PR (never merges, never a draft).
- [ ] The refresh `write` discipline locks `rules_sha == sha256(rewritten default.yml)` and
      `rules_captured_at == the refresh date` (testable hermetically; the workflow's PR body carries the
      measured run/command as evidence).
- [ ] `neutralise()` is self-guarding: it FAILS whenever an upstream spelling it must escape is absent,
      so a drifting upstream rule body cannot silently commit a credential-shaped pack.
- [ ] Docs: agent-wiki note + changes.d fragment + `docs/SCANS.md` (and the refresh target is documented).
