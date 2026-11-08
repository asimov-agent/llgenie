# Pin the semgrep rule set and floor the scanner engines (issue #1284)

## Why

Semgrep is invoked with `--config p/default`, a registry alias that resolves at scan time, so the
same tree re-scanned a week apart can give different results with no tree change. The scanner
binaries are digest-pinned but the rules they run (and the engine versions) are not — a
reproducibility gap in the pipeline's own immutability promise.

## What changes (task checklist)

- [ ] Add `scripts/scanner_image.py` and `scripts/security_scan.py` a declared current-release
      baseline per scanner and gate `make check-scanner-images` / `make check-security-scan` on it.
- [ ] Bake the content-addressed semgrep `p/default` rules pack into
      `containers/scanners/semgrep/rules/default.yml` and record its sha256 as `semgrep.rules_sha`
      in `containers/scanners/digests.json`; the semgrep scan leg runs the committed pack.
- [ ] docs (SCANNERS.md, SCANS.md), renovate scanner-version manager, agent-wiki + changes.d.
