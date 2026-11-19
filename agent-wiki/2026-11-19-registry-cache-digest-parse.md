# registry-cache-gc digest parse fix (issue #2924)

## What changed

`make registry-cache-gc` could list an orphan but never delete it: the digest step failed with
`[registry-cache-orphans] no digest for ...` on every human-side sweep (all 8 orphans, rc=2) because
`scripts/registry_cache_orphans.py::digest_of()` only matched a line starting exactly
`digest: sha256:` (single space), while `docker buildx imagetools inspect` publishes its header as
`Digest:    sha256:...` (colon, then padding spaces — Go's text/tabwriter alignment).

The fix replaces the exact-prefix line scan with one tolerant regex over the inspect output:
module-level `_DIGEST_RE = re.compile(r"digest:\s*(sha256:[0-9a-fA-F]{16,})", re.IGNORECASE)`,
consulted via a new `_extract_digest(ref, text)`. Both the real padded alignment and the legacy
single-space form resolve to the same digest; the SystemExit wording keeps its exact prior shape so
the gc failure output is unchanged. `digest_of` still parses `out.stdout + out.stderr` through the
`run_ok` seam.

## Verified

- Hermetic tests `tests/test_registry_cache_orphans.py` — `pytest ...` rc=0, 11 passed: the three
  pre-existing sampled checkers remain (now 8 total include the gc seams' injected `digest_resolver`),
  plus three NEW cases driving the REAL `digest_of` via a monkeypatched `run_ok`: the three-line
  imagetools header captured verbatim from GHCR (`Digest:    sha256:c5299a4136...`), a test_digest_of
  for the legacy single-space form, and a no-digest refusal (SystemExit, message contains
  `no digest for`).
- The GC failure output shape is unchanged — `_extract_digest` reuses the exact
  `[registry-cache-orphans] no digest for {ref}` message.

## Decisions

- One regex, not two branches: `\s*` after `digest:` and `IGNORECASE` cover both real-world spellings
  with a single tolerant parse.
- The injected `digest_resolver` seam in `run_gc` stays (unchanged tests); `digest_of` does its own
  parsing and is now covered against the tool's only real output format.

## Status

Change `registry-cache-digest-parse` in tree, uncommitted for the job to commit. The sweep execution
itself (deleting the 8 orphans, re-report printing zero) is #2914's remaining acceptance item and is
stamped there — this change is the tool fix that makes it possible.

Implements: #2924. Complements / unblocks: #2914 (AC2) and #2923.
