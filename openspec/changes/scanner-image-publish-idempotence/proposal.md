# scanner-image-publish-idempotence — proposal

Issues: [#2453](https://github.com/asimov-agent/llgenie/issues/2453) (this change closes it) and
[#2452](https://github.com/asimov-agent/llgenie/issues/2452) (this change implements its criteria
1/3/4; #2452 stays open until its criterion 2 lands with the post-merge main run).

## Why

`make ci-scanner-images` re-pushes every scanner's content-hash tag on every main push without asking
the registry whether the immutable artifact is already published. Measured at main=`954134135`:

- **RED** run `42755279061` (job `129628207406`): `[scanner-image] publish failed: semgrep` →
  `make: *** [Makefile:1299: ci-scanner-images] Error 1` — 1 of 10 jobs, main red at the tip.
- **GREEN 40 minutes earlier**, run `42751641578` (job `129620581092`) published the *identical* tag:
  `2026-11-10T04:02:38.5354462Z [scanner-image] published ghcr.io/asimov-agent/llgenie/semgrep:5954e2aad609`.
  The semgrep Dockerfile behind that 12-hex hash last changed in `16eb9b274` (#2082).

A content-hash tag names one build of one Dockerfile; re-pushing it can only reproduce identical bytes
or fail transiently (multi-arch binfmt / GHCR contention — the same red run ends with `Failed to save
cache ... another job may be creating this cache`). Today that transient failure reds main, makes every
ci-verdict at the head `RED: 1 job(s) FAILED (scanner-images)`, and every later PR inherits it at the
merge gate. Worse, the failure is **undiagnosable**: `publish()` inspects only `returncode` and prints
`publish failed: <scanner>`, discarding the streams `run_ok` captured — the gap issue #2452 names.

## What Changes

1. **Registry probe before publish** — `publish()` first runs
   `docker buildx imagetools inspect <ref>` (via `scripts/proc.py::run_ok`; a missing tag is rc≠0,
   never an exception). When the published manifest list already carries every platform in `PLATFORMS`,
   it prints a skip line naming the ref and returns 0.
2. **Publish still runs when it must** — tag absent, or present without a required platform → the
   multi-arch `buildx build --push` runs exactly as today. The skip never suppresses a real first
   publish.
3. **Failure surfaces its streams** (issue #2452 criterion 4) — a failed build or publish prints the
   command, its exit code, and a bounded tail of the captured stdout+stderr instead of only naming
   the scanner.
4. **Unit proof without Docker** — `tests/test_scanner_images.py` gains the skip path, the missing-
   platform negative control, the absent-tag control, and the failure-stream assertion, all against a
   faked registry probe/push.

## Impact

- Affected specs: `scanner-image-publish` (ADDED requirement)
- Affected code: `scripts/scanner_image.py` (`publish()`, `build()`, new `_published_platforms()`),
  `tests/test_scanner_images.py`
- Gates unchanged: `ci-scanner-images` (Makefile:1299) keeps calling `scanner_image.py ci`; no job,
  secret, or condition moves. `scripts/proc.py` is unchanged — the new probe uses its existing
  `run_ok` policy.
