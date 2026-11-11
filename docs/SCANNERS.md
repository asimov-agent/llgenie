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

**The rule pack has a refresh path** (issue #2283 criterion 2). The recency floor (`make
check-security-scan` fails when `rules_captured_at` is older than `RULES_BASELINE_DAYS = 30`) would
be a red with no door out without one. `make semgrep-rules-refresh` (wired to the scheduled
`.github/workflows/semgrep-rules-refresh.yml`) re-resolves upstream `p/default` through the pinned
scanner image, re-applies the `\x59` / `\x2e` / `\x2f` credential-shape escapes (a raw fetch would
red `make secret-scan`), rewrites `default.yml`, and re-stamps `rules_sha` / `rules_captured_at` /
`rules_count` in `digests.json`. When the pack changed it opens the re-pin PR — whose
`rules_sha == sha256(rewritten default.yml)` and `rules_captured_at == the refresh date`.

## Targets

| Target | What it does |
|---|---|
| `make scanner-image SCANNER=<id>` | Build one scanner image from its Dockerfile. |
| `make test-scanner-image SCANNER=<id>` | Build it and prove it prints the version its Dockerfile pins. |
| `make scanner-digests` | Rewrite `containers/scanners/digests.json` from the Dockerfiles. |
| `make semgrep-rules-refresh` | Re-resolve the committed semgrep rules pack from upstream `p/default` through the pinned scanner image, re-apply the credential-shape escapes, rewrite `default.yml`, and re-stamp `rules_sha`/`rules_captured_at`/`rules_count` (the scheduled refresh, issue #2283). |
| `make scanner-ref SCANNER=<id>` | Print the published immutable ref. |
| `make publish-scanner-images SCANNER=<id>` | Build linux/amd64 + linux/arm64 and push the content-hash tag (the security-images pipeline uses this per scanner). |
| `make ci-security-images SCANNER=<id>\|all` | **The security-images pipeline command**: for each scanner image, publish its content-hash tag only when GHCR is missing it (FORCE=1 republishes); never runs on a PR. |
| `make security-images-ensure SCANNER=<id>\|all` | Local/one-off: publish each scanner image's content-hash tag only when GHCR is missing it (FORCE=1 to republish). |
| `make check-scanner-images` | **The gate** (inside `make ci-unit`): floating base, missing version pin, or a stale `digests.json` fails (a static lint — it builds nothing). |

## Bumping a scanner

1. Change the exact version in the scanner's Dockerfile.
2. `make scanner-digests && make check-scanner-images`.
3. `make test-scanner-image SCANNER=<id>` — the version the binary prints must be the pin.
4. Commit the Dockerfile **and** `digests.json` together: a Dockerfile alone leaves the scan
   workflow pointing at the previous build, which is the staleness the gate exists to catch.

The publish policy lives in `scripts/scanner_image.py` (`ensure`), not in a workflow `if:`: a
scenario-scoped condition in YAML is how a publish silently stops happening. `ensure` does ONE
registry manifest lookup per scanner (`buildx imagetools inspect`) and builds + pushes both platforms
only when the content-hash tag is absent from GHCR (or FORCE asks), so the pipeline publishes exactly
the tags GHCR is missing — a present tag is an HTTP lookup and a log line, never a build. The
scanners' own pipeline `.github/workflows/security-images.yml` drives it (a daily schedule before the
scan, a path-filtered push to `main` for `containers/scanners/**` and `scripts/scanner_image.py`, and
a `workflow_dispatch`); `ci.yml` builds and publishes no scanner image (issue #745).
