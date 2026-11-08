# Scanner images — one immutable image per scanner

Every vulnerability scan in this repository runs from an image built here, from
`containers/scanners/<id>/Dockerfile`. Nothing is installed at scan time: a scanner fetched during
a scan is a mutable tool on a mutable base, with network access while it is judging the repository.

| Scanner | Image | What it does |
|---|---|---|
| Trivy | `containers/scanners/trivy/` | OS/language vulnerabilities, committed secrets, and IaC misconfigurations (Dockerfile / Compose / Terraform / K8s / GitHub Actions) |
| Grype + Syft | `containers/scanners/grype/` | Syft writes the CycloneDX SBOM, Grype matches it |
| Semgrep | `containers/scanners/semgrep/` | SAST over the application code |

## The immutability rules (enforced, not conventions)

- **The base is pinned by digest** — `FROM cgr.dev/chainguard/wolfi-base@sha256:<64 hex>`. A tag is
  a moving pointer inside Chainguard's registry.
- **The scanner is pinned to an exact version** — `ARG TRIVY_VERSION=0.70.0-r5` and
  `apk add "trivy=${TRIVY_VERSION}"`. An apk range would compile to a different scanner on the
  next build.
- **The published tag is a content hash** — `ghcr.io/<owner>/llgenie/trivy:<12-hex>` where the hash
  is the Dockerfile's sha256, the same convention `llgenie/test` uses. A changed Dockerfile is a
  different tag, so a published tag can never mean two builds.
- **No scanner needs a secret** — every scanner is an apk package, so a scan is reproducible from
  its Dockerfile alone: there is no credential to provision and none to leak into a scan run.
- **The SAST rule set is immutable too** (issue #1284) — Semgrep does not resolve its rule pack at
  scan time. The `p/default` registry pack is fetched once, committed as
  `containers/scanners/semgrep/rules/default.yml` (baked into the image by the Dockerfile `COPY`),
  and its sha256 is recorded next to the scanner version in `digests.json` (`semgrep.rules_sha`).
  A scan runs `--config <committed pack>`, so the same tree at the same sha scans byte-identically;
  `make check-security-scan` fails when the sha is omitted or the committed file is changed.
- **The pack's own bytes are not a credential shape** (PR #2082) — gitleaks' `private-key` rule reads
  any `-----BEGIN … PRIVATE KEY-----` header in a committable file as a leaked key, and a rule pack
  made of secret-detection patterns is full of them. Every such header in the pack writes the `KEY`
  with a YAML `\x59` escape: the bytes carry no header, while the pattern semgrep loads is unchanged
  and still matches a real key (proved by `tests/test_security_scan.py` against a fixture, and by the
  scanner image still reporting the fixture). Re-vendoring the pack must re-apply the escape; if it is
  dropped, `make secret-scan` reds the PR at the header's line.

`containers/scanners/digests.json` is the file the scan workflow reads: one entry per scanner with
the pinned version and the content-hash ref. It is generated — `make scanner-digests` — and
`make check-scanner-images` fails when it disagrees with a Dockerfile (a stale entry points a scan
at a build that no longer matches the tree).

**The engines advance through the same bump path** (issue #1284): `containers/scanners/` Dockerfile
`*_VERSION` pins are a declared current-release baseline, so `make check-scanner-images` (and
`make check-security-scan`) fail when a pinned engine is older than the current apk release — a pin
cannot silently straggle. Renovate also manages the scanner version ARGs, so the engines move with
`make scanner-digests` + a PR.

## Targets

| Target | What it does |
|---|---|
| `make scanner-image SCANNER=<id>` | Build one scanner image from its Dockerfile. |
| `make test-scanner-image SCANNER=<id>` | Build it and prove it prints the version its Dockerfile pins. |
| `make scanner-digests` | Rewrite `containers/scanners/digests.json` from the Dockerfiles. |
| `make scanner-ref SCANNER=<id>` | Print the published immutable ref. |
| `make publish-scanner-images SCANNER=<id>` | Build linux/amd64 + linux/arm64 and push the content-hash tag (CI). |
| `make ci-scanner-images` | The CI job: build + version-test every scanner; publish on a push run only. |
| `make check-scanner-images` | **The gate** (inside `make ci-unit`): floating base, missing version pin, or a stale `digests.json` fails. |

## Bumping a scanner

1. Change the exact version in the scanner's Dockerfile.
2. `make scanner-digests && make check-scanner-images`.
3. `make test-scanner-image SCANNER=<id>` — the version the binary prints must be the pin.
4. Commit the Dockerfile **and** `digests.json` together: a Dockerfile alone leaves the scan
   workflow pointing at the previous build, which is the staleness the gate exists to catch.

The publish policy lives in `scripts/scanner_image.py` (`ci`), not in a workflow `if:`: a
scenario-scoped condition in YAML is how a publish silently stops happening.
