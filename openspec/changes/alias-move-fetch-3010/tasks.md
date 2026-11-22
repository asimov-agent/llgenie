# Tasks — alias-move-fetch-3010

## Implementation

- [x] `scripts/engine_alias_move.py`: default fetch seam of `move_alias` switched from `proc.run_live` to `proc.run_ok`; empty/None captured stdout refused with the named FAIL `the fetch seam captured nothing` before any hashing or manifest write. (proven: pytest tests/test_engine_alias_move.py 15 passed rc=0)

## Tests

- [x] `tests/test_engine_alias_move.py`: regression test that the default fetch seam is the capture policy `proc.run_ok`; test that a `run_live`-shaped seam (`stdout=None`) is refused with the named FAIL and ZERO manifest writes; end-to-end test driving the REAL `proc.run_ok` against a stub inspect command emitting the manifest bytes — byte gate passes, PUT body byte-identical. (proven: pytest tests/test_engine_alias_move.py tests/test_check_engine_pins_published.py 62 passed rc=0)

## Verification (tick each with its replayable proof)

- [x] `make -s check-wiring` exits 0. (rc=0)
- [x] `make -s check-package-layers` exits 0. (rc=0)
- [x] targeted pytest of `tests/test_engine_alias_move.py` and `tests/test_check_engine_pins_published.py` exits 0. (62 passed, rc=0)
- [x] `make openspec-validate NAME=alias-move-fetch-3010` exits 0. (rc=0)
- [ ] full unit battery `make test-unit` exits 0 at the final branch head. (rc=0)
