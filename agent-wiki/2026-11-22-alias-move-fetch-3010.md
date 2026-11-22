# The alias-heal fetch seam must capture: run_live streamed the manifest and the byte gate hashed the empty string (issue #3010)

Date: 2026-11-22. Issue: #3010. OpenSpec change: `alias-move-fetch-3010`.

## What was verified
- Registry-liveness run `45040752698` on main `a3384331d` (post-#3009): the heal step failed with `the fetched bytes hash to sha256:e3b0c442…` — the SHA-256 of the EMPTY string — while the fetched manifest JSON was visibly streamed in the same step log.
- Mechanism: `move_alias`'s default fetch seam was `proc.run_live`, whose own docstring states "`stdout`/`stderr` on the returned process are `None` (they were not captured)": the live path hashed `(r.stdout or "").encode()` = `b""`, 100% of runs. Host proof the contract itself is sound when the fetch captures: `docker buildx imagetools inspect --raw …@sha256:1e74e680…` emits 8487 bytes whose `sha256sum` equals exactly the pin digest.
- Fix: the default seam is now `proc.run_ok` (captures both streams, never raises), and a `None`/empty capture is refused BEFORE hashing with the named FAIL `the fetch seam captured nothing`, so a non-capturing seam can never masquerade as a digest mismatch again.
- Tests added: default seam IS `proc.run_ok` (signature + no `= proc.run_live` default left in the module); a `run_live`-shaped seam (`stdout=None` and `stdout=""`) is refused by name with zero hashes/PUTs/probes; an end-to-end test drives the REAL `proc.run_ok` against a stub inspect command emitting the exact manifest bytes — byte gate passes, PUT byte-identical. Targeted battery: 62 passed.
- `make -s check-wiring`, `make -s check-package-layers`, `make openspec-validate NAME=alias-move-fetch-3010` all rc=0.

## Key decision
This lane fixes only the seam (#3006 proved the byte-identity contract; its live path never captured). The landing proof is the next `registry-liveness` green on `main` whose head carries the fix — tracked with the sweep issue #3004, not asserted here.

## Current status
Seam fix + 3 regression tests on `feat/alias-move-fetch-3010`; full unit battery run at the branch head; PR opened against `main`.
