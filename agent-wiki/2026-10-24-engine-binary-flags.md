# 2026-10-24 — every engine-binary flag must answer, not just one (#580)

Issue: **#580** (implemented here). Related, filed separately: **#583** (a documentation review leg for
the derived build params — the next change, not this one). PR: this branch's PR against
`asimov-agent/llgenie:main`.

## What was measured

The bump PR's CI already runs the engine binary — `engine-image` job → `make test-engine-stage …
TEST=detect` → `make test-engine-image` → `scripts/engine_image.py test-image` → `binary_file_works`.
So the wiring the issue asks for exists; the defect is the **rule** inside it:

```bash
for flag in "$@"; do
  if try "$flag" >/tmp/llgenie-bin.out 2>&1; then
    echo "binary file $path accepts $flag"
    exit 0            # ← one answer vouches for every flag
  fi
done
```

A binary that answers `--version` and exits 1 on `--help` passed. The bump PR's "CI builds and tests
this engine" claim was true only for whichever spelling happened to work.

## The data that shaped the fix

`containers/engines/binaries.json` (generated from each skill's `binary_flags`), 32 variants:

- **no engine documents `-h`**;
- six document `--help` **only** (exllamav3, litert, mlx, sglang, strata, tensorrt-llm);
- the rest document `--version` + `--help`.

So the issue's literal reading — assert `-h` for every engine — would have reddened the whole matrix
for a flag no engine declares. The check therefore asserts what is true per engine and still catches
a dropped spelling:

1. **every documented flag answers individually** (exit 0 + non-empty output), the failing flag named
   with its own output tail;
2. **every flag a user types is executed** (`--version`, `-h`, `--help`, `-V`) and reported per flag,
   so a dead `-h` is visible instead of masked;
3. **the help family (`-h`/`--help`) and the version family (`--version`/`-V`) must each be answered** —
   a release that drops a whole family reds; an engine that only spells help as `--help` passes;
4. an engine whose manifest documents **no** flags falls back to the trio and needs one answer;
5. `probe: device` variants stay contained (vllm cuda/rocm, mlx cuda, tensorrt-llm cuda, exllamav3
   rocm): the file must exist, the flags may legitimately fail on a device-less runner, and the
   version is proven by `entrypoint.sh detect`, which `test_image` still asserts.

The probe no longer decides: it prints `LG-FLAG <flag> <rc> <bytes>` plus a bounded output block per
flag and exits 0 (1 remains "the binary file is missing"). `parse_probe()` and `decide()` are pure, so
the rule is testable without docker — the repo's rule that a test must run the thing it tests.

## Verification

- `tests/test_engine_binary_flags.py` — 7 pass, hermetic: the **shipped** `BINARY_PROBE` text run with
  real `bash` against real executable files, parsed by the shipped `parse_probe`, decided by the
  shipped `decide`. Includes a dead `--help` red naming `--help`, a family red naming `-h` and
  `--help`, an empty manifest still requiring an answer, a `device` variant contained, and "the probe
  reports every flag instead of stopping at the first".
- `tests/test_engine_version.py` gains `test_engine_binary_answers_the_flags_a_user_types`, which runs
  the same probe inside the BUILT image and asserts the documented flags plus both families, naming
  the flag that failed.
- Proven against the base: with `origin/main`'s `engine_image.py` swapped in, **6 of the 7** tests fail
  (the seventh is the "missing file is exit 1" contract guard, true on both).
- `make test-unit`, `make openspec-validate NAME=engine-binary-flags`, `make lint`, `make check-docs`.

## Status

The bot never merges; CI's `auto-merge` owns landing.
