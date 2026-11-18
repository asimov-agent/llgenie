## ADDED Requirements

### Requirement: edge0 is a dated decision, not a gap
The vendored registry SHALL carry the upstream engine `edge0` and its model `edge0-145b` verbatim as
published upstream, and `data/unsupported-engines.json` SHALL carry a `deferred` decision entry for
`edge0` with a date, the tracking issue, and a reason read from the upstream repository's own
README/releases/engine docs. `make check-engine-skill-gap` SHALL pass with `edge0` covered by that
entry, and `make skills-validate` SHALL be green.

#### Scenario: the gap gate sees edge0 and accepts the decision
- **WHEN** `make check-engine-skill-gap` runs against the vendored store carrying the `edge0` records
- **THEN** it exits 0 naming `edge0` as a recorded decision, not as an unresolved gap

#### Scenario: the decision reason is upstream-sourced
- **WHEN** the `edge0` entry in `data/unsupported-engines.json` is read
- **THEN** its `reason` states the model-pack serving contract (single-GGUF launch vs multi-file pack
  directory) and the CUDA 13 / Metal-only platform facts, and its `upstream` field is
  `https://github.com/Edge0-AI/Edge0`

### Requirement: the model-pack serving gap is a separate linked issue
Out-of-scope work discovered by this decision — teaching the model store and the engine launch
contract to fetch and serve a multi-file model pack — SHALL exist as its own GitHub issue, named by
`#2903`'s `Not covered` section and linking back to `#2903` from its own body.

#### Scenario: both directions carry the link
- **WHEN** the new issue and `#2903` bodies are read
- **THEN** each names the other (`#2903` lists the new issue in `Not covered`; the new issue names
  `#2903` as its origin)
