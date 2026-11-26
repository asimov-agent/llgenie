## ADDED Requirements

### Requirement: A proven clause with a draft stub token is not evidence

The acceptance tick readers SHALL treat a `(proven: …)` clause that contains a literal draft stub
token (`PLACEHOLDER`, `HEADSHA`, or `MAINSHA`, case-sensitive whole word) as unproven, even when the
clause also carries an `rc=` token and a 7-40-hex sha.

#### Scenario: A blob-sha clause ending in the stub is refused

- **WHEN** a ticked criterion reads `(proven: gh api repos/<repo>/git/blobs/<40-hex> rc=0 PLACEHOLDER)`
- **THEN** `make check-pr-acceptance` reports the criterion unproven (red) rather than accepting the
  blob sha as the measured tree sha

#### Scenario: The commit-text mirror with the stub is refused

- **WHEN** a bot range's commit text carries a `- [x]` acceptance mirror line ending in
  `(proven: rc=0, engine-build run at head PLACEHOLDER)`
- **THEN** `make check-pr-commit-checkboxes` fails the range naming the draft-stub clause

#### Scenario: A real proof still passes

- **WHEN** a ticked criterion carries `(proven: make <target> rc=0 at head <40-hex>)` or
  `(proven: run=<id> …)` with no draft stub token
- **THEN** both gates keep accepting it exactly as before
