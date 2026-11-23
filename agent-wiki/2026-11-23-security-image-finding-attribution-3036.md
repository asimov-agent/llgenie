# A finding inside a published image is attributed to its digest and owner, not to a dependency pin (issue #3036)

Date: 2026-11-23. Issue: #3036. OpenSpec change: `security-image-finding-attribution`.

## What was verified
- The misroute is measured, not inferred: main run `45190665275` wrote `image-agent.trivy.json` for the
  agent image, Syft died mid-chain, and the surviving trivy report reached the tracker as **#3025** — a
  `component:python` issue whose acceptance criterion asked for a `requirements*.txt` entry for a Go
  module (`github.com/gin-gonic/gin`) that no requirements file in this repository contains. An
  unattributed image report is indistinguishable from a tree report once it is in the report directory.
- `scripts/security_scan.py::scan_image` writes `image-<slug>.meta.json` (the exact `ref@sha256:<64>`
  scanned) **before** the trivy → Syft → Grype chain, so the attribution survives a scanner that dies
  halfway (pinned by a test in which Syft raises after trivy succeeded: the meta is there, the trivy
  report is still attributed, Grype never ran).
- `scripts/security_scan.py::findings` refuses an `image-*.trivy.json` / `image-*.grype.json` whose
  `image-<slug>.meta.json` is absent or names no ref: it names the report, the missing record and
  issue #3036 instead of yielding an unattributed finding (no-skip policy — a missing prerequisite is
  a loud failure, never a quiet drop).
- `scripts/security_scan.py::image_owner(ref)` maps a scanned digest back to its
  `containers/scanned-images.json` entry — by exact `ref`, by `name`, or by resolving the entry's
  `engine` + `variant` to its committed tag — and answers `None` for a ref the allow-list does not
  carry. Engine entries whose tag suffix cannot be this ref skip the resolve (the resolve reads the
  committed engine params each time).
- `scripts/security_issues.py::body_for` routes a finding that carries an image to `_container_body`:
  the body names the exact image digest, the owner file its allow-list entry points at
  (`containers/agent/Dockerfile` for the shipped agent entry), and the rebuild/re-scan loop — and
  names NO `tools/requirements*.in` → `requirements*.txt` path anywhere. An image with no allow-list
  entry says "names no owner" and points at the allow-list instead of inventing one. The six-section
  `issue_body.render` shape and the marker (the idempotency key) are unchanged.
- `scripts/security_issues.py::set_labels` now RECONCILES labels: POST the labels the finding earns,
  read them back, DELETE every `component:*` label the finding no longer earns, read back again, and
  fail when a stale component label is still carried. Only `component:*` is removable — marker,
  severity and `auto-fixable` labels stay.
- Tests: `tests/test_security_issues.py`'s `gh` stub got a per-issue label STORE (POST merges, DELETE
  removes, GET answers with what that issue then carries, `GH_STUB_LABEL_WRITE=ignore` models a write
  that did not stick) and hands each `issue create` its own number, so label claims are proven against
  state instead of a constant. New tests: mid-scan attribution, unattributed-report refusal, empty-meta
  refusal, `image_owner` mapping, the image body (owner named, no pin path), stale-label removal with
  read-back proof, and the removal-failure path. Targeted battery `pytest tests/test_security_issues.py
  tests/test_security_scan.py` rc=0, 101 passed, zero skips.

## Key decision
Attribution is recorded at scan time, not inferred from a report's filename: the scan writes the record
of what it pulled before any scanner runs, and the reader refuses image reports that have no record.
That is what makes an image finding's ISSUE body possible at all — remediation for an artifact lives in
the Dockerfile its allow-list entry names, and a dependency-bump lane has nothing to move. Labels follow
the same discipline as their write: the removal is proven by reading it back, because a stale
`component:` label routes the issue to an owner who cannot act on it.

## Current status
Implementation, tests, OpenSpec change and docs on branch `feat/security-image-finding-attribution`;
`make openspec-validate`, `make check-docs`, `make security-scan-fixture`, the full unit battery and
`make lane-preflight` are run at the branch head. Live proof — the next agent-image security lane run
filing an image finding whose body names the image owner instead of a pin path — lands through the
pipeline (engine/agent image builds belong to CI).
