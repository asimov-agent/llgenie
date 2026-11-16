# Tasks: scan-pin-verify-config-digests

- [x] 1. `registry_manifest_digests` also reports each child manifest's config-blob
      digest (registry round-trip per child), keeping the index/children contract.
- [x] 2. `verify_pinned_digest` accepts the index digest, a child manifest digest, OR
      a child config digest as the daemon-reported id; moved tag and foreign id stay red.
- [x] 3. Unit tests: config-digest id accepted (measured `ubuntu-latest` digests);
      foreign id refused; moved tag refused; stale-copy test updated.
      (proven: `pytest tests/test_security_scan.py` -> 74 passed rc=0, 2026-11-16)
- [x] 4. Local proof: `make security-scan-all` green end-to-end with the pinned refs.
      (proven: `make security-scan-all` rc=0 on the host daemon 2026-11-16; 5 pinned scanner
      images verified+executed, log security-reports/ + scan-all-local.log)
- [x] 5. Local proof: a config scan of the current `containers/` tree shows DS001/DS002
      do not fire — code-scanning alerts #48 and #11 are stale; close both via the API
      as resolved and record the proof in the issue.
      (proven: security-reports/trivy.json 2026-11-16 - agent+test Dockerfiles scanned with
      pinned trivy 0.70.0, 0 misconfigurations each, no DS001/DS002 firings; alerts 48+11
      -> dismissed/mitigated via gh api, evidence recorded on issue #2727)
- [x] 6. Issue filed via `scripts/issue_body.py::render`; PR body drafted mapping
      Problem/Fix/Benefit/Technical and carrying `closes #2727`.
      (proven: issue #2727 filed via render rc=0; PR body drafted with `closes #2727`)
- [x] 7. Verification proof on the final tree: `make test-unit` green, `make
      openspec-validate NAME=scan-pin-verify-config-digests` green, and the live helper names
      the config digest the runner daemon reported for the current pin.
      (proven: `make test-unit` rc=0 (3889 passed, 2026-11-16); `make openspec-validate` rc=0;
      live `registry_manifest_digests('grype:c52ac5da0f5c')` rc=0 -> configs incl.
      sha256:8b0f527c…, the exact id dispatch run 43784224774 rejected)
