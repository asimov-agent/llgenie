# Security lane: the semgrep scan excludes its own rule pack (issue #2105)

Folds into PR #2082 (implementing #1284) the scan-coverage defect this issue names: the daily SAST
gate was walking into a detector-shaped red where the finding's only "fix" would weaken the scanner.

## The gap

The semgrep rule pack is committed at `containers/scanners/semgrep/rules/default.yml` and lives
inside the scan root. Many rules in the pack are detection *patterns* written as literal text, so
the pack's own bytes matched its own rules. Measured on PR #2082's head `2e0d9a2a` with the pinned
image: 7 self-findings, of which 1 is ERROR (`generic.secrets.security.detected-ssh-password`,
`containers/scanners/semgrep/rules/default.yml:1867`) which maps to policy `high` under
`fail_on=['critical','high']` — so the scheduled `security-scan` run went red on the rule pack
itself and `security-issues` filed a finding whose remediation was "edit the code at
`default.yml:1867`" (i.e. delete the detector).

## The fix

The semgrep scan leg now passes a second `--exclude containers/scanners/semgrep/rules` next to the
existing `--exclude security-reports`, in `scripts/security_scan.py::scan(tool=="semgrep")`. The
pack is what the scan RUNS (`--config <pack>`), not what it audits; excluding it removes the
self-reference and nothing else — every rule still applies to every scanned project file. The
argv assertion in `tests/test_security_scan.py::test_semgrep_scan_excludes_the_report_directory`
now asserts both exclusions.

## Verification

- `tests/test_security_scan.py` passes: the docker-stub argv carries both `security-reports` and
  `containers/scanners/semgrep/rules` under `--exclude`.
- A real semgrep run over the repo at the fixed argv (pinned image, committed pack) reports **no
  finding whose path is under `containers/scanners/semgrep/`** (the 7 self-findings are gone: 7→0),
  and a planted injection in application code still reports — the exclusion removed the self-match
  and nothing else.
- `make check-security-scan` and the security-scan unit tests pass at the head.

This is not a suppression of a real class: the detector stays fully live against project code; the
exclusion only stops the scanner from auditing its own configuration bytes.
