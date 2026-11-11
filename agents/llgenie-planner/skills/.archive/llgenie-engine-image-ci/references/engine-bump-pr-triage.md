# Engine-bump (chore) PR triage — red checks, by real cause

A red check on an engine-bump PR is almost never The Pin. Classify by reading
the failing job's log, not by the engine bumped or the diff on the pin. Read the
job output first; the pin is the last suspect.

## The taxonomy (in rough frequency order)

1. **Install-order (`not published in ghcr.io/<owner>`).** The `install` job runs
   alongside `engine-image-*` and pulls the bump's new `pin8-hash-arch` tag
   before that job has built, tested and pushed it. Fix lives in CI (make the
   install job wait for the engine-image jobs), not in the pin. Every bump PR
   hits this until that fix merges.
2. **Hub throttle (`429 Too Many Requests ... Retry after <N> seconds`).** A
   model-fetch path that still shelled out to a bare `hf download` dies on the
   throttle-capped job while the image itself built fine. Don't re-roll CI; fix
   the fetch to go through the one downloader which honours the Hub's own
   wait-and-retry (throttle wait, capped). Also surfaces as live-Hub flakiness
   on GETs that retry a 429 only twice (and never a 5xx).
3. **Stale generated manifests (`containers/engines/binaries.json`, params).**
   The install job errored `missing binary file: <id>` or the flag-manifest
   test red, because the archive/skill install changed and the generated
   manifest wasn't regenerated. Fix: `make generate-engine-params ENGINE=<id>`
   in the branch, then `make check-engine-params` + the manifest test must go
   green. Never hand-edit `binaries.json` — regenerate it.
4. **Derive-shape issue.** The upstream changed HOW it ships (pip → native
   release archives), a kind bump the derive encodes wrongly (see below). Fix on
   the derivation + the tests, and carry it to every branch that followed the
   old shape.

## The `{prefix}/{version}`-in-path rule (why `outdated` is undetectable)

If the derived install puts the version IN the binary path
(`binary: {prefix}/{version}/bin/{id}`), the native state check can only ever
see `missing` or `current` — the installed binary's own `--version` is never
asked, so a stale installed version reads as `current` and `outdated` is
unreachable. A bump PR that reds the whole `*_seamless` lane with `0.6.4`
showing as missing and `9.9.9` as current is this, not a flaky test.

Rule: derive a version-less, symlinked alias. As the LAST install step emit
`ln -sfn {prefix}/{version} {prefix}/current`, set
`binary: {prefix}/current/bin/{id}` (detect stays `{binary} --version`), and
make sure `--version` is actually among the documented `binary_flags` (write
`["--help", "--version"]` when `--help` is already there) — else the
flag-manifest test reds even though `detect` is correct.

## Install-kind-agnostic tests (pip/archive both reach the three states)

When an engine changes install kind, the *whole* native-status / picker suite
must keep working — that is the seam, not the old kind. Fake only the EXTERNAL
tools the skill shells out to: a fake `uv` for pip installs, and for a release
archive a fake `curl` (writes the archive), `shasum` (exit 0), `tar` (reads
`-C <dir>`, materialises `<dir>/bin/<id>-native` that prints a version from a
state file, writes `<dir>/VERSION`). Both kinds must reach `missing` /
`outdated` / `current` through the REAL `native_status`/`ensure_native` and the
real picker labels. Product code is never mocked (repo rule); a test that stood
in one install kind is a defect the moment the kind changes.

## Workflow notes

- Rebase the chore branch onto `main` tips before judging it; the top-of-main
  tips carry the repairs. Shared test files that both the merged tip and the
  branch touch need a union resolve (merge both engines' expected values), not
  a take-theirs.
- GitHub reports mergeability asynchronously: a branch that shows
  `CONFLICTING` right after a rebase push clears to `MERGEABLE` a few seconds
  later once GitHub recomputes — re-query, don't assume stale.
- Regenerate and verify in the branch BEFORE pushing: `generate-engine-params`,
  `check-engine-params`, and the skills manifest/image-matrix tests must go
  green there, independent of the unrelated harness work on `main`.
- Post a triage comment on each chore PR naming the real cause and which fix
  unblocks it — a reviewer should not have to re-derive it from the log.
