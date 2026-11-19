# 2026-11-19 — registry GC digest parse accepts the real imagetools alignment (issue #2924, PR #<TBD>)

`make registry-cache-gc` listed all 8 superseded fixed-name cache tags and then deleted zero:
`digest_of()` scanned for a line starting exactly `digest: sha256:` while
`docker buildx imagetools inspect` prints `Digest:    sha256:<hex>` — colon plus padding spaces —
so every orphan failed at the digest step before the guarded delete (measured 2026-11-19 on main
`c564764c5645`: 8 `FAILED … no digest for …` lines, rc=2, `deleted 0; remaining verified orphans: 8`).

## What was verified

- The failure reproduced live with the sweep tool on the asimov-agent identity; the GHCR versions
  API downstream of the parse is sound (version `1480025823` is named exactly the digest
  `sha256:c5299a4136c4…` that imagetools prints, tag `buildcache`), so only the line scan was wrong.
- The hermetic suite injected `digest_resolver` everywhere — the real parser had zero coverage
  against its only real-world input format, which is why #2914's landing stamp left AC2 open.
- Fix: module-level `_DIGEST_RE = digest:\s*(sha256:[0-9a-fA-F]{16,})` (case-insensitive) consulted
  through `_extract_digest(ref, text)`; refusal wording unchanged.
- Tests now drive the REAL `digest_of` through a monkeypatched `run_ok` with the imagetools output
  captured verbatim from GHCR (padded alignment), the legacy single-space line, and a no-digest
  refusal — 11 passed.

## Decision

- Update-not-add: the injected-resolver gc tests stay as-is; the new cases put the real parser
  behind the seam instead of replacing the gc-flow coverage.
- Sweep execution stays #2914's acceptance item and runs after this fix merges, stamped there with
  the zero-orphan re-measure.

## Current status

Issue #2924 open with the measured run; the sweep + #2914 closure follow this PR's merge.
