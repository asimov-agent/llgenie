## ADDED Requirements

### Requirement: the alias mover's live fetch seam captures the manifest and an empty capture is a named refusal
The alias mover's default fetch seam SHALL be the capturing proc policy `proc.run_ok` — the seam that streams (`proc.run_live`, whose returned process has `stdout`/`stderr` = `None`) SHALL NOT be the default, because hashing a non-capturing fetch always hashes the empty string and fails the byte-identity gate of `alias-move-digest-3006` on the live path. When the fetch seam returns `stdout` of `None` or an empty string, the mover SHALL print FAIL naming `the fetch seam captured nothing`, exit non-zero, and issue ZERO manifest writes and ZERO hashing of a body — so a wrong seam can never masquerade as a digest mismatch.

#### Scenario: the default seam captures
- **WHEN** `move_alias` is invoked without an injected fetch seam
- **THEN** the manifest fetch runs through `proc.run_ok` (both streams captured, never raises), and the fetch command itself stays `docker buildx imagetools inspect --raw <registry>/<engine>@<pin-digest>`

#### Scenario: a non-capturing seam is refused by name
- **WHEN** the fetch seam returns a completed process whose captured `stdout` is `None` or empty (the `run_live` shape)
- **THEN** the mover prints FAIL naming `the fetch seam captured nothing`, exits non-zero, hashes nothing, and issues ZERO manifest writes

#### Scenario: the real capture seam passes the byte gate end-to-end
- **WHEN** the mover fetches through the real `proc.run_ok` policy against an inspect command that emits the pin manifest bytes
- **THEN** `sha256(captured bytes)` equals the requested pin digest, the byte gate passes, and the manifest PUT body is byte-identical to the captured bytes
