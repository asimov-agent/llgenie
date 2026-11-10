# Scanner publish re-pushed an already-published immutable tag and reds main (issue #2453, PR #2455)

## What was verified

Measured at main=`954134135` (fetched 2026-11-10T06:36Z): main-tip push run `42755279061`
(job `129628207406`) failed with `[scanner-image] publish failed: semgrep` — re-pushing the exact
content-hash tag `ghcr.io/asimov-agent/llgenie/semgrep:5954e2aad609` that run `42751641578`
(job `129620581092`) had published 40 minutes earlier; the semgrep Dockerfile behind that hash last
changed in `16eb9b274` (#2082). A content-hash tag is immutable, so the re-push can only reproduce
identical bytes or fail transiently (the same red log ends with a cache-contention warning), and its
`1 of 10 jobs FAILED` made every ci-verdict at the head red.

## The fix (OpenSpec change `scanner-image-publish-idempotence`)

`scripts/scanner_image.py::publish` now asks the registry first: `docker buildx imagetools inspect`
via the `run_ok` policy (rc≠0 = an empty answer, never an exception). All `PLATFORMS` present →
skip line + rc 0, no `--push`. Tag absent or platform-incomplete → the push runs unchanged. A failed
build/publish prints the exit code and a bounded 25-line tail of the captured streams — closing
issue #2452's diagnosability criterion, which had discarded them. `tests/test_scanner_images.py` grew
five Given/When/Then tests (skip, missing-platform control, absent-tag control, publish-failure
streams, build-failure streams) against a faked `run_ok` seam; unit CI needs no Docker.

## Decisions

- The PR closes #2453 only. #2452 is implemented (criteria 1/3/4) but stays open: its criterion 2 can
  only be proven by the post-merge main push (a `pull_request` run never publishes), so closing it
  from this PR would assert an unproven criterion (`check-pr-acceptance` reads live issue bodies).
- Scope is the scanner image leg (scan pipeline). No engine/serving image or pin moves: inference
  servers continue to run only from engine images published by this repository's owner-side CI.

## Status

PR #2455 (branch `feat/scanner-image-publish-diagnostics`, cut from `954134135`) — judged CI at the
head decides; auto-merge lands it when green+CLEAN. On merge, the main push run proves #2452
criterion 2, its criteria are ticked with that run id, and #2452 closes.
