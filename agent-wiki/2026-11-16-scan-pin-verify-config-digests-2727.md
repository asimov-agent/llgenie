# Scan lane pinned-digest check accepts the daemon's config-digest image id (#2727)

Issue: #2727. OpenSpec change: scan-pin-verify-config-digests.

## What was verified
- Root cause measured against the GHCR manifest API (2026-11-16): tag `grype:a607057cfd07`
  serves OCI index `sha256:12ef938b…` (== the pin recorded when the 9-red streak ran);
  its amd64 child manifest is `sha256:ccff82ef…` and that child's config-blob digest is
  `sha256:c585d524…` — exactly the image id the `ubuntu-latest` runner daemon reported in
  the failing runs (newest 43710607827, job 132801143308). A classic (non-containerd)
  Docker daemon reports a pulled image's `.Id` as the CONFIG digest; this host's
  containerd-snapshotter daemon reports the index digest. `verify_pinned_digest` accepted
  only index + child manifest digests, so it refused the runner's fresh pull as a "stale
  local scanner image" on every scheduled run since the check landed (no SARIF uploaded
  since 2026-11-09).
- `scripts/security_scan.py`: `registry_manifest_digests` now also reads each child
  manifest's `config.digest` from the registry (`_child_config_digests`, re-inspecting the
  content-addressed `name@<child>` with `--raw`); `verify_pinned_digest` accepts index digest,
  child manifest digest, or child config digest — an id outside that family is still refused, a
  moved registry index is still refused. The second measured chain (dispatch run 43784224774,
  branch head 45f774ece): tag `grype:c52ac5da0f5c` -> index `sha256:806d7ac2…` -> child
  `sha256:022b1f83…` -> config `sha256:8b0f527c…` — and why `--raw` is mandatory for the child
  read: `docker buildx imagetools inspect --format {{json .Manifest}}` normalizes a
  single-manifest (non-index) ref and DROPS the `config` field, so the first helper version
  returned an empty config family and the dispatch re-failed with the same refusal against the
  new pin; `--raw` serves the manifest as stored, `config.digest` included (proven live: the
  helper now names `sha256:8b0f527c…`, the exact id run 43784224774 rejected).
- `tests/test_security_scan.py`: the docker stub answers a `name@<child>` inspect with faithful
  buildx semantics — child `config` is served only at `--raw` — so the suite pins the seam;
  `test_the_daemon_reported_child_config_digest_is_accepted` proves the measured runner
  semantics (and asserts the child read happened at `--raw`);
  `test_a_config_digest_of_a_foreign_manifest_is_still_refused` proves the accepted family
  cannot launder a substituted image. Module: 74 passed rc=0; full `make test-unit` 3889
  passed rc=0.
- Real daemon: `make security-scan-all` rc=0 end-to-end (2026-11-16): 5 pinned scanner
  images verified + executed (Syft SBOM, Trivy, Grype, Semgrep), reports written.
- Alert staleness: that same pinned trivy 0.70.0 report shows `containers/agent/Dockerfile`
  and `containers/test/Dockerfile` scanned with 0 misconfigurations (no DS-0001/DS-0002):
  the fixes (#2563 `USER 1000:1000`, #2617 no `:latest` default) hold. Code-scanning alerts
  #48 and #11 closed as resolved with that evidence recorded on issue #2727.

## Current status
Done on branch feat/scan-verify-config-digests (PR opened for issue #2727). No pins changed;
the daily 04:05 UTC lane re-uploads SARIF on `main` after merge and keeps the alerts closed.
