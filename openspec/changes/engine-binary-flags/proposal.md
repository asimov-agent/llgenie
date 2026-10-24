# Every documented flag must answer, not just one of them

## Why

The engine-bump PR's CI runs `make test-engine-stage … TEST=detect` → `make test-engine-image` →
`scripts/engine_image.py test-image`, whose first check is `binary_file_works`: run the built image's
engine binary with the flags its skill documents (`containers/engines/binaries.json`), plus the
standard trio as a fallback, and pass if **any one of them answers**.

That is the defect (issue #580). The probe is `for flag in "$@"; do if try "$flag"; then exit 0; fi;
done`: a single working flag masks a dead sibling. A release that drops `--help`, or whose binary
answers `--version` but not `--help`, passes the bump's CI and breaks the first user who types
`llama-server --help` or `<engine> -h`.

Measured on this tree: no engine documents `-h`; six document `--help` only (exllamav3, litert, mlx,
sglang, strata, tensorrt-llm) and the rest document `--version` + `--help`. So the naive reading of
the issue — assert `-h` for every engine — would red the whole engine matrix for a flag no engine
declares. The fix has to be strict about what each engine documents and about the *family* of flags a
user types, not blanket about one spelling.

## What changes

`scripts/engine_image.py`:

- **`BINARY_PROBE` reports per flag instead of short-circuiting.** It runs EVERY requested flag and
  prints one machine line each — `LG-FLAG <flag> <rc> <bytes>` — keeping the exit-code contract
  (1 = the binary file is missing, else 0; the verdict belongs to the caller). A `.py` binary keeps
  its `python3` invocation.
- **`parse_probe()` and `decide()` are new, pure and hermetic**, so the decision can be tested without
  docker: `parse_probe` reads the `LG-FLAG` lines, `decide` applies the rules below and returns the
  failure lines.
- **The rules** (`binary_file_works` = run the probe, parse, decide):
  1. **every flag the engine documents must answer**, individually — exit 0 and non-empty output; a
     flag that does not is named in the failure with its own captured output tail;
  2. **every flag a user types is exercised**, including the standard trio members the manifest does
     not document, and each is reported per flag — so a dead `-h` is visible in the log instead of
     being masked by a passing `--version`;
  3. **the help family and the version family must each have an answer** — (`-h` or `--help`) and
     (`--version` or `-V`), each probed for real. This is the assertion that survives engine variance:
     a release that renames `--help` to nothing at all still reds, while an engine whose CLI only
     spells it `--help` (six of them) keeps passing;
  4. **an engine that documents no flags** falls back to the trio and must answer at least one — the
     same guarantee as today, now said out loud;
  5. **`probe: device`** variants (vllm cuda/rocm, tensorllm-llm cuda, mlx cuda, exllamav3 rocm) keep
     their containment: the file must exist and the flags may legitimately all fail on a device-less
     runner, where the image's own `detect` proves the version (`test_image` still asserts it).

`tests/test_engine_version.py` gains a case that asserts the per-flag verdicts of the built image's
binary — every documented flag answered, help family answered, version family answered — driven by
the same `parse_probe`/`decide` pair, so it names the failing flag instead of asserting "a version was
printed".

`tests/test_engine_binary_flags.py` (new, hermetic, no docker) runs the real `BINARY_PROBE` text with
real `bash` against fake binaries on disk: one that answers everything passes; one that answers
`--version` and exits 1 on `--help` reds **naming `--help`**; one that answers neither help spelling
reds the help family; a `probe: device` variant is contained; an empty manifest still requires a trio
answer. Nothing is mocked — the probe is the shipped script text and the binaries are real files.

`tests/fixtures/…` gets the fake binaries (shell scripts that print and exit as each case needs).

## Impact

- `scripts/engine_image.py` — `BINARY_PROBE`, `parse_probe`, `decide`, `binary_file_works`.
- `tests/test_engine_version.py`, `tests/test_engine_binary_flags.py` and its fixtures.
- `README.md` (what the bump's CI actually executes) and `agent-wiki/`.

The existing `test_image` call graph, exit codes and the `probe: device` containment are unchanged;
`make test-engine-image` and `make test-engine-stage TEST=detect` keep their contracts, so no
workflow edit is needed — the bump PR's CI already runs this check.

Not in this change: #583 (a documentation review leg for the derived build params) and every flag
beyond the version/help families the issue names.
