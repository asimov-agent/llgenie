# ci-security-images — the scanner images get their own pipeline

Issue: [#745](https://github.com/asimov-agent/llgenie/issues/745)

## Why

The images the security scanners run from are built by the main CI pipeline
(`.github/workflows/ci.yml`, job `scanner-images` -> `make ci-scanner-images` ->
`scripts/scanner_image.py ci`), on every pull request and every push to `main`.
Main CI is not supposed to do security work at all: since PR #740 the scanning
itself is its own daily pipeline, but the thing that builds the scanners is still
wired into the pipeline that runs on every PR and every merge. A PR run builds
and version-tests three scanner images it can never publish (a fork head cannot
write this repository's packages), and a push to `main` rebuilds all three on two
platforms whether or not the pin moved. And the build is not in one place:
`scripts/security_scan.py::ensure_image` carries a second inline `docker build`
path. This is the half of #738's own-pipeline rule that never landed.

## What Changes

- A new `.github/workflows/security-images.yml` pipeline owns the scanner images:
  its own daily `schedule` (an odd minute before the scan), a `push` to `main`
  path-filtered to `containers/scanners/**` and `scripts/scanner_image.py`, and
  `workflow_dispatch`. It never runs on a `pull_request`.
- `scripts/scanner_image.py` replaces `ci()` with `ensure(scanner="all",
  force=False)` and adds `published(ref)` (one `buildx imagetools inspect`).
  `ensure` builds + pushes a scanner only when its content-hash tag is absent from
  GHCR (or `force` asks), and prints `present <ref> (skipped)` / `publishing <ref>`.
- The `scanner-images` job is deleted from `ci.yml`, removing the `packages: write`
  permission from the every-PR pipeline. `make check-scanner-images` stays in
  `ci-unit` (a static lint that builds nothing).
- `security_scan.ensure_image` stops carrying its own `docker build`: pull -> on a
  miss, delegate to `scanner_image.ensure(scanner=tool)` and use the ref it returns.
- `Makefile` renames `ci-scanner-images` to `ci-security-images`, adds a local
  `security-images-ensure` target, updates `.PHONY` and the `##` help lines.
- Docs (`docs/SCANNERS.md`, `docs/SCANS.md`, `docs/BOTS.md` dispatch table),
  `CHANGES.md` and an `agent-wiki/` note name the new pipeline and the tag-absent rule.

## Impact

- Affected: `.github/workflows/ci.yml`, `.github/workflows/security-images.yml` (new),
  `scripts/scanner_image.py`, `scripts/security_scan.py`, `Makefile`, `docs/BOTS.md`,
  `docs/SCANS.md`, `docs/SCANNERS.md`, `CHANGES.md`, `agent-wiki/`, and the hermetic
  tests in `tests/test_scanner_images.py`.
- Nothing in the scanning itself changes: `security-scan.yml`,
  `data/security-policy.json`, `security_verdict`/`security_issues`/`security-bumps`
  and #740's `enforce_events` rule stay exactly as they are. `make check-security-scan`
  reads `security-scan.yml`'s `on:` block only, so its "no push, no pull_request" rule
  still holds with the new workflow present.
- There is no branch protection rule naming `scanner-images` (the main branch has no
  ruleset), so deleting the job strands no required status check.
