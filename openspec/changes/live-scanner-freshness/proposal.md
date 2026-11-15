# Live freshness: the scanner gate compares pins against the Wolfi index, not a frozen dict (issue #2709)

## Why

`make check-security-scan`'s freshness floor (issue #1284) compares `containers/scanners/digests.json`
versions against `SCANNER_BASELINE` — a hardcoded dict last re-measured 2026-11-07. It never consults
what Wolfi publishes today. Measured consequence at main `6a56fc94f0` (security-lane audit, #2661):
Wolfi publishes grype `0.121.3-r2` and syft `1.57.1-r2` while the pins sit at `0.121.2-r1` and
`1.57.0-r1` — and the gate reads green because it is only ever comparing itself to itself. A pin that
lags upstream is invisible until a human re-measures by hand.

## What changes (task checklist)

- [ ] `scripts/security_scan.py`: add a live comparison — parse a Wolfi x86_64 APKINDEX (fetched
      from `packages.wolfi.dev` via `APKINDEX.tar.gz`, or read from a local snapshot named by
      `WOLFI_APKINDEX` for hermetic tests), compute the newest published build per package
      (`trivy`, `semgrep`, `grype`, `syft`), and fail with a delta report (package, pinned version,
      live newest) when a pin names anything other than the newest published build.
- [ ] `make scanner-freshness` (in `mk/security.mk`): the new live step, alongside
      `make check-security-scan` — the offline gate stays hermetic (no network inside `check`);
      the live comparison is its own explicit target/step so CI wiring stays a lane decision.
- [ ] syft enters the comparison even though it has no image of its own: its pin lives in
      `containers/scanners/grype/Dockerfile` (`ARG SYFT_VERSION=`), parsed by the same step.
- [ ] Tests in `tests/test_security_scan.py`: a fixture index proves a stale pin reds the step
      naming the delta, a current pin passes, and a missing package in the index fails loudly
      (no silent pass).
- [ ] Docs: agent-wiki entry + `docs/changes.d/` fragment.

Out of scope (its own issues, from #2661): bumping the actual pins (#2707 grype, #2708 syft),
image-scan coverage (#2706).
