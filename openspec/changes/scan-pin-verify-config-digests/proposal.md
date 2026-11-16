# Proposal: scan-pin-verify-config-digests

## Why

The daily deterministic scanner lane (`security-scan.yml`, in the sanctioned
`SCHEDULE_ALLOW` roster) has been red on every scheduled run since 2026-11-07
(measured 2026-11-16: 8 consecutive failed `schedule` runs). Since the pinned-digest
verification landed (PR #2611, `main@8cd9973cd`), the failure mode is a FALSE
positive in `scripts/security_scan.py::verify_pinned_digest`:

- the run pulls the pinned ref and its fresh pull reports image id
  `sha256:c585d524…`;
- `containers/scanners/digests.json` records `sha256:12ef938b…` for the same ref;
- measured against the GHCR registry API (2026-11-16): the pinned tag still serves
  index `sha256:12ef938b…` (exactly the recorded pin), whose amd64 child manifest is
  `sha256:ccff82ef…` **whose config-blob digest is `sha256:c585d524…`** — the very id
  the runner reported.

Docker daemons report a pulled image's `.Id` differently by storage backend: a
containerd-snapshotter host reports manifest/index digests, while the classic
`ubuntu-latest` daemon reports the **config blob digest**. `verify_pinned_digest`
only accepts the index digest or a child manifest digest, so it permanently refuses
the runner's correct pull ("delete it so the pinned ref re-pulls" — re-pulling
reproduces the same id).

Consequence: no SARIF has been uploaded to the Security tab since 2026-11-09, so the
tab is frozen and its only two open code-scanning alerts (`#48` DS-0002 root-user on
`containers/test/Dockerfile`, `#11` DS-0001 `:latest` on `containers/agent/Dockerfile`)
stay open even though both findings were fixed on `main` (`USER 1000:1000` via #2563;
the `:latest` default removed via #2617). New vulnerabilities never surface because
the lane dies before completing.

## What Changes

- `scripts/security_scan.py`: `verify_pinned_digest` accepts any content-addressed
  identity the daemon may legitimately report for the pinned ref — the recorded index
  digest, each child manifest digest, **and each child manifest's config-blob digest**
  (read from the registry for the child digests the pinned index names). A moved tag
  or substituted image still fails: its digests differ from the pinned index's family.
- `scripts/security_scan.py`: `registry_manifest_digests` also returns each child's
  `config` digest (registry round-trip for each manifest the index names).
- `tests/test_security_scan.py`: extend the pinned-verification tests — a daemon id
  equal to the pinned index's child **config** digest is accepted (the
  `ubuntu-latest` semantics, measured digests), a foreign id is still refused, and a
  moved tag is still refused.
- Close the two proven-stale code-scanning alerts (`#48`, `#11`) as resolved, with the
  proof recorded in the issue; the re-greened lane re-uploads SARIF and keeps them closed.

No pin changes: `containers/scanners/digests.json` stays as recorded.
