# security-image-finding-attribution — proposal

Issue: [#3036](https://github.com/asimov-agent/llgenie/issues/3036)

## Why

The published-image scan records **which image it scanned only after its three scanner stages finish**
(`scripts/security_scan.py::scan_image` writes `image-<slug>.meta.json` on line 642, after trivy, Syft
and Grype), and `findings()` (lines 855-864) emits an image report's findings with **no image tag at
all** when that meta is absent. Measured on the failed scheduled run `45190665275`
(`security-scan.yml`, 2026-11-23T14:06:37Z): trivy wrote `image-agent.trivy.json` for
`ghcr.io/asimov-agent/llgenie/agent:latest@sha256:cfcafa0a494d…`, the Syft stage then refused the
unpublished scanner pin `ghcr.io/asimov-agent/llgenie/syft:1844da087d23` (issue #2609), the step exited
1 at `mk/security.mk:62`, and `security-issues` filed **issue #3025** for `CVE-2026-17106` in
`github.com/moby/go-archive` v0.2.0 — a Go module in the agent image — as "a `component:python`
dependency" labelled `security,vulnerability,severity:high,component:python,auto-fixable`, with an
acceptance criterion (`pinned at 0.3.0 or later in the compiled requirements*.txt`) that no file in
this repository can satisfy and no `@sha256` ref naming the artifact it actually lives in.

## What Changes

- `scan_image()` writes `image-<slug>.meta.json` (the exact `ref@digest` it is about to scan) **before**
  the first scanner container runs, so the attribution survives a stage that dies mid-scan.
- `findings()` refuses instead of guessing: an `image-*.trivy.json` / `image-*.grype.json` whose
  `image-<slug>.meta.json` is missing or names no ref fails the step, naming the report.
- New `security_scan.image_owner(ref)` resolves a scanned ref back to its
  `containers/scanned-images.json` entry (a `ref` entry directly, an `engine`+`variant` entry through
  the same `_resolve_engine_ref` the scan used) and returns its `owner`.
- `security_issues.body_for()` renders an image finding's remediation around the **image**: the ref it
  lives in plus the allow-list entry's `owner` (its Dockerfile / params file), never the generated
  `tools/requirements*.in` → `requirements*.txt` path.
- `security_issues.set_labels()` reconciles the `component:*` family: labels the finding no longer
  earns are deleted from the issue after the POST + read-back, so a re-labelled finding stops routing
  to the wrong owner.
- Tests extended in `tests/test_security_scan.py` / `tests/test_security_issues.py`: meta-before-the-
  scanners under a mid-scan failure, refusal on a report without its meta, the container body shape,
  the owner lookup, and stale-component removal.

## Impact

- Affected: `scripts/security_scan.py`, `scripts/security_issues.py`, `tests/test_security_scan.py`,
  `tests/test_security_issues.py`, `agent-wiki/`, `docs/changes.d/`.
- The next `security-issues` run re-renders #3025's body (it carries the marker, so it is updated, not
  duplicated) and removes its stale `component:python` label. The advisory itself stays open until the
  agent image is rebuilt (#2836 / #2935).
- Not covered (each already its own issue): the red scheduled lane itself — GHCR re-ownership of
  `llgenie/syft` (#2967) — the agent-image rebuild that actually clears #3025 (#2836, publish dispatch
  #2935), and the gate-semantics question of whether an image scan should defer-and-build an
  unpublished scanner image (#2518) instead of refusing it (#2609), which stays with #2967's owner.
