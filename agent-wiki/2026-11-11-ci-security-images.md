# 2026-11-11 — the scanner images get their own pipeline (issue #745)

The images the security scanners run from are built and published by their own pipeline now:
`.github/workflows/security-images.yml`, instead of the `scanner-images` job in `ci.yml`.

## Why

The images were built by main CI on every PR and every push to `main` — a PR run built and
version-tested three scanner images it could never publish (a fork head cannot write this
repository's packages), and a merge path rebuilt all three on two platforms whether or not the pin
moved. Main CI is not supposed to do security work; the scan itself has been its own daily pipeline
since PR #740, but the builder was still wired into the every-PR pipeline. And the build was in two
places: `security_scan.ensure_image` carried its own inline `docker build`, a second code path for
the same image tag.

## What was verified against the spec

- New pipeline triggers on a daily schedule (03:49 UTC, an odd minute before the 04:05 scan), a
  `push` to `main` path-filtered to `containers/scanners/**` and `scripts/scanner_image.py`, and a
  `workflow_dispatch` (`scanner` + `force`). It carries no `pull_request` trigger, and gates nothing.
- `scanner_image.ensure` does one registry manifest lookup (`published`, the same `buildx imagetools
  inspect` probe `ci_images.py::published` uses) and builds + pushes both platforms only when the
  content-hash tag is absent, or `FORCE` asks. `ci()` is gone — the event name is not the policy,
  the tag's existence is.
- The `scanner-images` job and its `packages: write` permission are gone from `ci.yml`.
  `check-scanner-images` (a static lint that builds nothing) stays in `ci-unit`.
- `security_scan.ensure_image` no longer hand-rolls a `docker build`: a pull miss delegates to
  `scanner_image.ensure(scanner=tool)`. One implementation, proven by test.
- `Makefile` gains `ci-security-images` + `security-images-ensure`; `ci-scanner-images` is gone.
- The scope classifier (`ci_scope.JOBS`) and the main-ruleset required-contexts floor
  (`check_main_ruleset.REQUIRED_CONTEXTS`) drop the removed job; their fixtures and tests follow.

## Tests

`tests/test_scanner_images.py` gained the `ensure` skip/publish/force cases, the no-scanner-job /
never-a-PR workflow assertions, and the single-build-path assertion; `tests/test_security_scan.py`
rewrote the build-miss tests to assert delegation to `scanner_image.ensure`. `check_ci_verdict`,
`ci_scope`, `check_main_ruleset` and the ruleset fixtures were updated for the removed job.

Implements #745 (the scanner-images half of the own-pipeline rule #738).
