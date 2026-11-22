## ADDED Requirements

### Requirement: the alias manifest move is byte-preserving so the moved alias carries the pin digest
The alias mover SHALL move a lagging `:<variant>` alias by transferring the pin manifest BYTE-FOR-BYTE, not by re-serializing it. It SHALL fetch the pin manifest verbatim with `docker buildx imagetools inspect --raw <registry>/<engine>@<pin-digest>`, SHALL verify locally that `sha256(fetched bytes)` equals the requested pin digest BEFORE publishing anything, and SHALL publish those exact bytes to `https://ghcr.io/v2/<name>/manifests/<variant>` with `Content-Type` equal to the manifest's own `mediaType`, authenticated by a GHCR token exchange using `GHCR_LOGIN_TOKEN` and `GHCR_LOGIN_USER` from the environment. It SHALL NOT use `docker buildx imagetools create` for the move, because that command re-publishes the input as a manifest list and the new tag can never equal the pin digest. After the PUT it SHALL verify exactly as before — re-resolve `:<variant>` through `engine_image._digest_http` and print MOVED only when the resolved digest equals the pin digest.

#### Scenario: the move publishes the pin's exact bytes
- **WHEN** the mover runs for a valid contract and the fetched manifest hashes to the requested pin digest
- **THEN** the only write it issues is a manifest PUT whose body is byte-identical to the fetched manifest and whose `Content-Type` equals the manifest's `mediaType`, and the tag it writes is `<name>/manifests/<variant>`

#### Scenario: a fetch that is not the pin is never published
- **WHEN** the fetched bytes hash to something other than the requested pin digest
- **THEN** the mover prints FAIL naming both digests, exits non-zero, and issues ZERO manifest writes

#### Scenario: no imagetools create is used for the move
- **WHEN** the mover moves any alias
- **THEN** no `docker buildx imagetools create` invocation takes place, and no engine build, engine container, or engine execution takes place

#### Scenario: the moved alias resolves to the pin digest
- **WHEN** the registry accepted the byte-identical manifest and the post-move probe resolves `:<variant>`
- **THEN** the mover prints `[alias-move] MOVED <alias-ref> -> <pin-digest>` only when the resolved digest equals the pin digest; a mismatch prints FAIL and exits non-zero

#### Scenario: a refused manifest write is loud and is not re-probed
- **WHEN** the registry refuses the PUT (non-2xx)
- **THEN** the mover prints FAIL naming the status, exits non-zero, and does not re-probe the alias

#### Scenario: the credential comes from the environment like every other registry secret
- **WHEN** the mover needs its push-capable GHCR token
- **THEN** it reads `GHCR_LOGIN_TOKEN` and `GHCR_LOGIN_USER` from the environment, and the registry-liveness heal step exports both through `env:` (`GHCR_LOGIN_USER: "${{ github.actor }}"` beside `GHCR_LOGIN_TOKEN`), never inline in `run:` text

#### Scenario: the mover stays hermetic to tests
- **WHEN** the unit suite exercises the mover
- **THEN** the fetch subprocess and the manifest PUT are injected seams, so no test contacts a registry or the network, and the contract refusals (four fields, `sha256:<64 hex>`, committed-suffix agreement) still exit non-zero with ZERO registry calls of any kind
