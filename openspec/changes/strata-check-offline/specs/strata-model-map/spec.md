# Strata model map — the vendored download map and its hermetic gate

## ADDED Requirements

### Requirement: the pinned Strata source is a committed vendor tree with a manifest

`data/vendor/strata/setup.py` (Strata's `setup.py` verbatim at the skill's pinned commit) plus the
`strata_control` import surface that setup.py's module-level imports need, and
`data/vendor/strata/manifest.json` (fields `url`, `ref`, `pinned`, and `files`: every vendored
file with its sha256) SHALL be committed, and SHALL be written only by `make sync-strata-models`.
A bump of the skill's pin regenerates vendor, manifest, and `data/strata_models.json` in the same
step, and the engine-bump lane's commit carries `data/vendor/strata/` alongside the map.

#### Scenario: a Strata bump regenerates the whole chain

Given a Strata bump updates the skill's `pinned` sha
When `make sync-strata-models` runs
Then vendor, manifest, and `data/strata_models.json` are rewritten from the newly pinned source
And `make check-strata-models` passes hermetically at the new pin

### Requirement: `make check-strata-models` proves the map without the network

`make check-strata-models` SHALL compare `data/strata_models.json` to `extract()` re-derived from
the vendored pinned source, and SHALL first assert the vendor chain: manifest `pinned` equals the
skill's `pinned`; every file the manifest records hashes to its recorded sha256; the vendor tree
carries no file the manifest did not record. The step SHALL NOT run `git` or reach the network. A
missing vendor or manifest reddens the step naming `make sync-strata-models`.

#### Scenario: the check runs with git and sockets unavailable

Given a tree where every `subprocess` spawn raises and network access is refused
When `make check-strata-models` runs at the committed pin
Then the step exits 0 with the same match verdict as a networked run

#### Scenario: a hand-edited map is refused

Given `data/strata_models.json` carries a value the vendored setup.py does not produce
When `make check-strata-models` runs
Then the step exits 1 naming the difference and pointing at `make sync-strata-models`

#### Scenario: a stale vendor is refused

Given the skill's `pinned` names a commit whose vendor has not been regenerated
When `make check-strata-models` runs
Then the step exits 1 naming the manifest-vs-skill pin mismatch

#### Scenario: a tampered vendor is refused

Given the bytes of `data/vendor/strata/setup.py` no longer hash to the manifest's `sha256`
When `make check-strata-models` runs
Then the step exits 1 naming the digest mismatch

### Requirement: the live upstream compare survives as its own named target

`make check-strata-models-live` SHALL exist and run the fetch-then-compare path (`check-live`), and
`make check-strata-models` SHALL NOT fetch. The unit battery SHALL keep running only the hermetic
target; the live target is documented in the make help line as the explicit upstream audit.

#### Scenario: the ci-unit sequence keeps its name but not its fetch

Given `scripts/ci_unit.py` runs `make check-strata-models`
When the unit stage executes
Then that step makes no `git` call, and the step list still contains the same target name

#### Scenario: the live audit is addressable

When `make check-strata-models-live` runs with GitHub reachable
Then it shallow-fetches the pinned commit and compares the live setup.py to the committed map,
exiting 1 on drift
