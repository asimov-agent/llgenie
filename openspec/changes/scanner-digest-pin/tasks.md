# Tasks: scanner-digest-pin

- [x] 1. Measure the three published manifest digests from GHCR (`docker buildx imagetools
      inspect`) and record them via the new `pin` path into `containers/scanners/digests.json`.
- [x] 2. Implement `scanner_image.py`: `pin <id>|all` command, `write` carries `image_digest`
      forward per unchanged tag, `check` requires the field; add `make pin-scanner-image-digests`.
- [x] 3. Implement `security_scan.py`: verify the pulled image's registry manifest digest against
      the recorded one (mismatch -> non-zero naming both digests); print the executed digest on
      pull and build paths; `check` requires `image_digest`.
- [x] 4. Tests green: `tests/test_security_scan.py` (digest present, mismatch names both, run
      output names digest) + `tests/test_scanner_images.py` (carry-forward, missing-field gate);
      negative control: a head scan with a deliberately wrong recorded digest exits non-zero naming
      both digests.
- [x] 5. Live proof: `make security-scan TOOL=semgrep` at head prints the executed digest
      `sha256:180c3f7e…`; gates `make check-security-scan` + `make check-scanner-images` rc=0.
