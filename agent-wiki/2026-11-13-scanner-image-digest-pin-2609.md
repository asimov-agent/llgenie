# 2026-11-13 — scanner images carry a registry-verified digest pin (issue #2609, PR #pending)

- Problem: a content-hash tag (`ghcr.io/.../semgrep:5954e2aad609`) is re-pushable, so what the
  registry serves under it can drift while `digests.json` keeps the old record. Measured live:
  the semgrep tag moved `sha256:7fd77096…` → `sha256:180c3f7e…`, and the local copy answered
  semgrep 1.121.0 while the Dockerfile pins 1.165.0-r0 — a scan ran a tool the pin never promised.
- Fix: `make pin-scanner-image-digests` (`scripts/scanner_image.py pin`) asks GHCR via
  `docker buildx imagetools inspect` and writes the manifest digest into each scanner entry as
  `image_digest`; `make check-scanner-images` refuses an entry without the pin, and
  `scripts/security_scan.py` verifies the image a scan actually runs against it — a tag whose
  registry digest moved, or a local copy whose id is neither the manifest nor one of its children,
  exits non-zero naming both digests. `write()` carries the pin forward when the tag is unchanged.
- Pinned digests (live, 2026-11-13): trivy `sha256:88490910…`, grype `sha256:12ef938b…`,
  semgrep `sha256:180c3f7e…` — the semgrep value equals the drifted digest the issue measured.
- Tests: `tests/test_security_scan.py` gained 6 digest tests over a docker stub that answers
  `buildx inspect` with a manifest consistent with `digests.json` (moved-tag and stale-copy
  refusals constructed via per-tool overrides, no real registry); `tests/test_scanner_images.py`
  gained the carry-forward and missing-pin checks. Targeted run rc=0 (65 passed).

Current status: implementation + live pin + tests written in `feat/scanner-digest-pin`; full
unit battery, docs gates and CI pending.
