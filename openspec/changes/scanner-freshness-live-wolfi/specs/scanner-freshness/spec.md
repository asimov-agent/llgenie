# scanner-freshness

## ADDED Requirements

### Requirement: A scanner pin that lags the live Wolfi index reddens the freshness gate, naming the delta

The security freshness gate SHALL compare each pinned scanner version in `containers/scanners/digests.json`
against the newest build the live Wolfi x86_64 APKINDEX publishes, not against the frozen
`SCANNER_BASELINE` dict. When a pin is not the newest the index publishes, the gate SHALL fail and name the
package, the pinned version and the live newest version in its message, together with the index snapshot
date it measured against. The comparison SHALL need no credential. The hermetic `make check-security-scan`
gate SHALL keep no network call.

#### Scenario: a pin lags the live index

- **WHEN** `freshness` is run against a Wolfi index whose newest grype build is newer than the pinned
  grype version in `digests.json`
- **THEN** it SHALL exit non-zero, naming `grype`, the pinned version and the live newest version, and
  the index snapshot date
- **Test:**
  `tests/test_security_scan.py::test_freshness_reds_a_stale_pin_against_the_live_index`

#### Scenario: every pin matches the live index

- **WHEN** `freshness` is run against a Wolfi index whose newest build for every pinned scanner equals
  the pinned version
- **THEN** it SHALL exit 0 and print the index snapshot date it measured against
- **Test:**
  `tests/test_security_scan.py::test_freshness_is_green_when_pins_match_the_index`

#### Scenario: the freshness command fetches the index through the make target

- **WHEN** `make check-security-freshness` runs (`python3 scripts/security_scan.py freshness`)
- **THEN** it SHALL fetch the Wolfi index (a local fixture file stands in for the index) and produce the
  freshness verdict
- **Test:** `tests/test_security_scan.py::test_freshness_command_fetches_the_index`, and the live lane
  step in `CI security-scan.yml scan job -> make check-security-freshness`

### Requirement: A pin lag reddens the scheduled security lane last, never skipping the scan's other work

The scheduled security lane SHALL run the live freshness check as a step whose failure is captured, and
SHALL fold a freshness failure into the run's final exit step — so the day's scan, its issue-filing and
its floor bump PR still happen, and a pin lag reddens the run only at the very end.

#### Scenario: a lag reddens the run after the pipeline's work

- **WHEN** `check-security-freshness` fails on a lagging pin while the day's verdict is otherwise clean
- **THEN** the run SHALL be red by its final step, after the scan, issue-filing and bump steps have run
- **Test:** `CI security-scan.yml scan job` final step gate
  (`git diff .github/workflows/security-scan.yml`)
