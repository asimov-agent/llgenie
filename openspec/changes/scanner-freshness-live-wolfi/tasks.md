# Scanner freshness gate reads the live Wolfi index (issue #2709)

- [x] `scripts/security_scan.py`: `WOLFI_APKINDEX_URL`, `fetch_apkindex`, `parse_apkindex`,
      `index_snapshot_date`, `freshness`, and a `freshness` subcommand that exits non-zero naming the
      package/pinned/live newest + the index snapshot date when a pinned scanner version is not the
      newest the Wolfi index publishes. The hermetic `check` gate keeps no network call.
- [x] `mk/security.mk` + Makefile `.PHONY`: a `check-security-freshness` target
      (`python3 scripts/security_scan.py freshness`).
- [x] `.github/workflows/security-scan.yml`: a `make check-security-freshness` step in the `scan` job
      (`continue-on-error`, `id: freshness`) and the final exit step reddening the run when either
      `steps.verdict` or `steps.freshness` failed — the scan/issues/PR work is never skipped.
- [x] Tests in `tests/test_security_scan.py`: a stale pin against a fixture index reds naming
      package/pinned/newest + snapshot date; matching pins are green; `main(["freshness"])` fetches a
      local fixture index.
- [x] Docs: `docs/SCANS.md` row for `make check-security-freshness`, an `agent-wiki/` note, and a
      `CHANGES.md` index row.
- [x] Verify: the security unit suite (`tests/test_security_scan.py`), `make check-wiring`,
      `make check-docs`, the lint linefeed gate (`scripts/lint_linefeeds.py`), `make check-workflows`,
      `make check-security-scan` (hermetic, still green with no network), and `make changes-index` all
      green; the live `python3 scripts/security_scan.py freshness` command reddens the existing grype
      lag (0.121.2-r1 -> 0.121.3-r2, snapshot 2026-11-15). The full `make test-unit` / `make lint`
      run inside the docker test container, which this bot container lacks; CI's `ci-unit` job runs
      them identically after the merge.
