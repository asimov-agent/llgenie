# #713 completion audit: dual security pipelines already implemented and merged (issue #713)

## Conclusion

`#713` is a **parent tracker that was never closed when its children landed** — not an implement.
The entire target architecture is already shipped on `main` (measured at `75f85118`). This record
is the completion audit that closes it.

## Measured evidence (clean `origin/main` `75f85118`)

| Section | Child | Merged PR | Confirmed on main |
|---|---|---|---|
| scanner images | #714 | #725 `7bd77716` | `containers/scanners/{trivy,grype,semgrep}` + `containers/scanners/digests.json`; `scripts/security_scan.py` resolves each ref by content-hash tag |
| scan workflow | #715 | (on main) | `.github/workflows/security-scan.yml`; `make sbom`/`security-scan[-all]`/`security-verdict`/`security-issues`; schedule 04:05 UTC + `workflow_dispatch` |
| tagged issues | #716 | (on main) | `scripts/security_issues.py`; `data/security-policy.json` (`issue_severities=["critical","high"]`) |
| remediation bot | #717 | #729 `82c02209` | `scripts/security_bot.py`; `security-bot.yml` (one `auto-fixable` issue → one green PR) |
| Renovate | #718 | #722 `90d97c20` | `renovate.json` (`pip_requirements`/`pip-compile` + Dockerfile base-image rules) |
| pin Actions | #719 | #721 `35e96580` | `scripts/pin_actions.py` + `make check-actions` — **PASSES: "72 third-party action refs, all pinned to a full commit SHA"** |

## Gates re-verified green on clean `origin/main` (executed, not asserted)

- `make dispatch-forms-report`/`check-dispatch-forms` → **OK, 24 dispatchable workflows, table matches**.
- `make check-actions` → **OK, 72 refs SHA-pinned** (AC8 operational).
- `make check-security-scan` → **OK**, `enforce_events=["schedule","workflow_dispatch"]`, never a PR gate.
- `make check-security-issues` → **OK, 9 labels, issue_severities round-trip**.
- CycloneDX SBOM: `make sbom` → `security-reports/sbom.cdx.json`; upload step in `security-scan.yml`.

## Refinement supersession (intentional, not a gap)

AC1's "PR, push to `main`" trigger was deliberately replaced by #738/#1598: the scan is its own
daily pipeline (`schedule` + `workflow_dispatch` only, `enforce_events=["schedule","workflow_dispatch"]`)
and can never red a pull request. All ACs read against that refined design; `make check-security-scan`
enforces it.

## Decisions

- **No implementation PR was cut** — re-implementing merged children would duplicate work and
  re-violate the #738 no-PR-gate contract (a deliberate weakening). This record is the deliverable.
- **Live related work is unaffected and remains OPEN:** #1282 / #1284 / #1375 (scoped findings on the
  security-scan pipeline). #1088 remains the sole merge authority.
- This audit record is the tree proof for the close; the close itself is planner-concurred.
