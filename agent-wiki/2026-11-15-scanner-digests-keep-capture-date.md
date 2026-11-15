# `make scanner-digests` keeps the semgrep capture date when the rules pack is unchanged

Found while verifying #2707 (whose branch had to revert the field by hand); the sibling tracking
issue from that verification is #2708. Marker: `rules-captured-at-silent-advance`.

## What was verified

- `scripts/scanner_image.py::write` (the body of `make scanner-digests`) no longer stamps
  `semgrep.rules_captured_at` to `datetime.date.today()` on every rewrite. It reads the committed
  record before rewriting and carries the prior date forward whenever the recomputed `rules_sha`
  equals the prior entry's; it stamps today only when `rules_sha` changes (or no prior entry
  exists). The committed record is already read for the `image_digest` carry-forward (issue #2609),
  so this reuses one read of `containers/scanners/digests.json`.
- The regression pair in `tests/test_scanner_images.py` locks both directions on a fixture tree +
  committed record: unchanged pack + rewrite preserves `2026-11-08`; changed pack + rewrite
  advances to today (plus a first-capture case). `python3 -m pytest tests/test_scanner_images.py -q`
  -> `25 passed` (2026-11-15).
- No manifest edit needed: the committed `containers/scanners/digests.json` already records the
  correct `2026-11-08` capture for the unchanged pack, which the fix now preserves.

## Current status

Done in the agent container, uncommitted for the implement job to commit. `make
openspec-validate` could not run here (no docker daemon — dockerd fails unprivileged on
overlay/iptables — and no npm), so the openspec CLI gate runs on CI at the PR head; the change dir
mirrors the CLI schema from the verified `scanner-image-publish-idempotence` change.
