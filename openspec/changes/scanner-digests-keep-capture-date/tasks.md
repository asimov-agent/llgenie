# Tasks

- [x] 1. `scripts/scanner_image.py::write` keeps the committed `semgrep.rules_captured_at` when the
      recomputed `rules_sha` equals the prior entry's, and stamps today only when `rules_sha`
      changes (or no prior entry exists). Verified: unit tests exercise the new branch with a
      fixture tree + committed record; `scripts/scanner_image.py` parses clean.
- [x] 2. Regression test pair in `tests/test_scanner_images.py` proves both directions: unchanged
      pack + rewrite preserves `2026-11-08`; changed pack + rewrite advances to today (plus a
      first-capture case). Verified:
      `python3 -m pytest tests/test_scanner_images.py -q` -> `25 passed` (2026-11-15).
- [x] 3. The committed `containers/scanners/digests.json` needs no manifest edit: it already records
      `rules_captured_at` `2026-11-08` for the unchanged pack, which `write()` now preserves.
      Verified: the real `digests.json` `rules_sha` equals the committed `default.yml` content hash
      (the `make check-scanner-images` recorded-sha match).
- [ ] 4. `make openspec-validate NAME=scanner-digests-keep-capture-date` exits 0. **Not verifiable in
      this agent container** — no docker daemon (dockerd fails unprivileged on overlay/iptables)
      and no npm, so the `@fission-ai/openspec` CLI and the dockerized openspec image both cannot
      run here. The change dir mirrors the CLI's schema (one `proposal.md`, one `tasks.md`, one
      `specs/<cap>/spec.md` with Given/When/Then scenarios and `- **Test:**` lines) from the
      verified `scanner-image-publish-idempotence` change; CI's `ci-unit` must run the validate
      gate at the PR head.
- [x] 5. Documentation in the same change: `agent-wiki/2026-11-15-scanner-digests-keep-capture-date.md`
      note + `docs/changes.d/2026-11-15-scanner-digests-keep-capture-date.md` index row. Verified:
      the note references the #2707/#2708 verification and is indexed; `make changes-index` renders
      it into `CHANGES.md`.
- [x] 6. Unit gate green: the hermetic scanner suite passes with the extended module (`24 passed`),
      and the aggregated suite selection is judged by `make test-unit` / CI's `ci-unit` at the head.
