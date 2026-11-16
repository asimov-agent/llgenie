#!/usr/bin/env python3
"""One scan, from the pinned scanner images (issue #715, parent #713).

Every scanner runs from the image `containers/scanners/digests.json` names, by its immutable
content-hash ref — never a floating tag, never an install step. This module is the ONE place a
scanner is invoked, so the workflow, a developer and CI run the identical command.

Commands (driven by make, never by hand):

    ref <tool>        print the immutable image ref for a scanner   make scanner-ref
    sbom              Syft -> security-reports/sbom.cdx.json        make sbom
    scan <tool>       syft | trivy | grype | semgrep                make security-scan TOOL=<id>
    all               sbom + every scanner, in dependency order     make security-scan-all
    scan-images       every published image in containers/scanned-images.json,
                      scanned BY DIGEST (issue #2706)               make security-scan-images
    scan-image <ref>  one <ref>@sha256:<64 hex> image               make security-scan-image REF=<ref>
    scan-published    the just-built ENGINE/ARCH image by its pushed digest   (engine-build lane)
    scan-fixture      known-vulnerable fixture image, report-only proof       make security-scan-fixture
    verdict [--mode]  apply data/security-policy.json               make security-verdict [MODE=pr]
    findings          print every finding in one normalised shape   (diagnostics)
    check             policy + digests are sane                     make check-security-scan

**Failure policy** (`data/security-policy.json`): a finding fails the run when its severity is in
`fail_on` AND (when `require_fix` is true) the report carries a fixed version. WHICH events may fail
is data too: `enforce_events` names them (`schedule`, `workflow_dispatch`), and every other event is
report-only. That is why this workflow carries no `pull_request:` and no `push:` trigger at all
(issue #738): a pre-existing advisory must never red a pull request or a push to `main`, and `check`
refuses both the trigger and a policy that would gate such an event.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

try:  # package-relative first, then the flat scripts/ layout CI imports it with
    from . import scanner_image as _scanner_image
except ImportError:
    import scanner_image as _scanner_image  # type: ignore

REPO = Path(__file__).resolve().parent.parent
RUNTIME = os.environ.get("RUNTIME") or "docker"
DIGESTS = REPO / "containers" / "scanners" / "digests.json"
POLICY = REPO / "data" / "security-policy.json"
#: The workflow this module's policy protects. `check` reads its `on:` block: a scan that a pull
#: request or a push to `main` gates is the defect issue #738 removed, and it must not come back.
WORKFLOW = REPO / ".github" / "workflows" / "security-scan.yml"
#: The events that must NEVER gate. A policy that names one of them is refused by `check`.
NEVER_GATING = ("push", "pull_request")
KNOWN_EVENTS = ("schedule", "workflow_dispatch", "push", "pull_request", "issues", "release")
REPORTS = Path(os.environ.get("SECURITY_REPORTS") or (REPO / "security-reports"))
#: What a scan runs by DEFAULT: the three scanners that need no account, no token and no telemetry.
#: Trivy covers OS/language vulnerabilities, committed secrets, and IaC misconfigurations;
#: Syft writes the CycloneDX SBOM and Grype matches it, Semgrep covers SAST. Between them they answer
#: "is anything in this tree known-vulnerable" from data shipped/downloaded to the runner.
TOOLS = ("trivy", "grype", "semgrep")
#: Syft is a tool id without an image of its own: it writes the SBOM through the Grype image
#: (`--entrypoint syft`), so it is in the tool set a caller may ask for but not in the roster
#: `containers/scanners/digests.json` has to carry an image for.
SBOM_TOOL = "syft"
#: Syft is a first-class tool id: `make security-scan TOOL=syft` writes the SBOM, and the default
#: sweep runs it first because Grype matches exactly that file. It is reached through the Grype
#: image (`--entrypoint syft`), so the stack builds one image per CVE scanner and none per SBOM.
#: No tool in ALL_TOOLS reads a credential: each judges the tree from data the runner downloads
#: itself, so no scan is ever skipped for a missing secret.
ALL_TOOLS = (SBOM_TOOL,) + TOOLS
#: The source a committed-credential finding carries (a trivy `secret`-class match, issue #1283).
#: It is distinct from the plain `trivy` source so the issue path can label a secret a
#: `component:code` finding (it lives in a file, not a dependency) and so `blocking()` knows a
#: secret is ALWAYS actionable: a committed credential's remediation is removal, not "wait for a
#: patched version", so `require_fix` must not suppress it while it still honours `fail_on`.
SECRET_SOURCE = "trivy-secret"
#: The source a Trivy IaC misconfiguration finding carries (a `misconfig`-class match, issue
#: #2234). Distinct from the plain `trivy` source so the issue path labels a Dockerfile / workflow
#: drift a `component:code` finding (it lives in a file, not a dependency). A misconfiguration has
#: no package or fixed version — its remediation is editing the matched IaC — so it is ALWAYS
#: actionable and `require_fix` must not suppress it while it still honours `fail_on`.
MISCONFIG_SOURCE = "trivy-misconfig"
#: The source a Semgrep SAST finding carries. Like a committed secret, a SAST finding's remediation
#: is editing the code (the matched region), NOT awaiting a patched package version — so it has no
#: `fixed` version and `require_fix` must not suppress it. `source` distinguishes it from the CVE
#: scanners so the issue path labels it `component:code` (issue #1554).
SEMGREP_SOURCE = "semgrep"
#: Semgrep lacks the policy's severity vocabulary: rules declare ERROR / WARNING / INFO. Map them
#: into the policy's known set so `verdict()` / `blocking()` count SAST findings against `fail_on`
#: (ERROR is a definite vuln pattern, the top of Semgrep's scale → gated; issue #1554).
SEMGREP_SEVERITY = {"ERROR": "high", "WARNING": "medium", "INFO": "low"}
#: The declared current-release baseline per scanner (issue #1284): the newest version the Linux
#: apk repo publishes for the scanner's `apk add` — the honest "current" the Dockerfile can reach.
#: `make check-security-scan` fails when digests.json records an older one, so a pinned engine
#: cannot silently lag the releases it should cover. Measured against packages.wolfi.dev (x86_64
#: APKINDEX) on 2026-11-15 (issue #2707 bump); bump with the Dockerfile via `make scanner-digests`
#: + PR.
SCANNER_BASELINE: dict[str, str] = {
    "semgrep": "1.165.0-r0",
    "trivy": "0.70.0-r5",
    "grype": "0.121.3-r2",
    # The SBOM tool rides the grype image (`--entrypoint syft`); its pin lives in that
    # Dockerfile's `ARG SYFT_VERSION` and in digests.json as `grype.syft_version`, so the
    # cataloger that writes the SBOM gets the same freshness floor as the CVE scanners
    # (issue #2708).
    "syft": "1.57.1-r2",
}

#: The recency floor for the committed semgrep rules pack (issue #2283). `digests.json` records
#: `semgrep.rules_captured_at` — the ISO date the pack was last resolved from upstream `p/default`.
#: A pack whose `rules_captured_at` is older than this many days fails `make check-security-scan`,
#: so a frozen rule set reds instead of silently aging behind upstream. 30 days = one upstream
#: refresh cycle plus slack; the renovate/manual capture path re-resolves p/default and rewrites
#: `rules_captured_at` (and `rules_count`) alongside `rules_sha`. Widening this number to dodge a
#: red is a deliberate weakening (issue #2283).
RULES_BASELINE_DAYS = 30

#: The Wolfi x86_64 APKINDEX the LIVE freshness comparison measures against (issue #2709).
#: `SCANNER_BASELINE` above only catches pins older than what a human measured on one date
#: (2026-11-07); it never consults what Wolfi publishes today. `make scanner-freshness`
#: resolves the newest published build of every pinned package from the index itself.
#: `WOLFI_APKINDEX` names a local APKINDEX snapshot (text or .tar.gz) for hermetic runs —
#: tests set it and never touch the network.
WOLFI_INDEX_URL = "https://packages.wolfi.dev/os/x86_64/APKINDEX.tar.gz"

#: The grace a lagging pin gets (issue #2709). Wolfi republishes builds constantly
#: (toolchain churn, epoch rebuilds), so a pin lagging a build published yesterday is not yet
#: debt. A lag reds when the newest published build is older than this many days: a persistent
#: lag becomes loud without forcing a bump per upstream heartbeat. Lowering this number is a
#: deliberate weakening, same discipline as `RULES_BASELINE_DAYS` (#2283).
FRESHNESS_GRACE_DAYS = 7

#: The packages whose pins the live comparison resolves: the image-backed scanners from
#: digests.json, plus Syft — which has no image entry of its own — from the
#: `ARG SYFT_VERSION=` default baked into the Grype image (issue #2709).
FRESHNESS_PACKAGES = TOOLS + (SBOM_TOOL,)


def scanner_baseline(tool: str) -> str:
    return SCANNER_BASELINE.get(tool, "")


def _version_sort_key(version: str) -> tuple:
    """A sortable key for an apk build string `X.Y.Z[-rN]` (issue #1284 freshness gate)."""
    nums, _, rev = version.partition("-")
    return (tuple(int(x) for x in re.split(r"[+.~]", nums) if x.isdigit()),
            int(rev.lstrip("r").partition("_")[0] or 0))


def _wolfi_stanzas(index_text: str) -> dict[str, list[tuple[str, int]]]:
    """An apk APKINDEX parsed into `{package: [(version, build epoch), …]}`.

    APKINDEX is stanzas separated by blank lines: `P:` names the package, `V:` is its build
    string, `t:` is the build timestamp (first integer; a package without one records 0 and the
    grace math treats 0 as out-of-grace — an undated lag is not a fresh lag).
    """
    out: dict[str, list[tuple[str, int]]] = {}
    for block in index_text.split("\n\n"):
        name = version = ""
        epoch = 0
        for line in block.splitlines():
            if line.startswith("P:"):
                name = line[2:].strip()
            elif line.startswith("V:"):
                version = line[2:].strip()
            elif line.startswith("t:"):
                fields = line[2:].strip().split()
                epoch = int(fields[0]) if fields and fields[0].isdigit() else 0
        if name and version:
            out.setdefault(name, []).append((version, epoch))
    return out


def _apkindex_from_tar(blob: Path) -> str:
    """The APKINDEX member text out of an APKINDEX.tar.gz."""
    import tarfile

    with tarfile.open(blob) as tar:
        for member in tar.getmembers():
            if member.name.endswith("APKINDEX"):
                handle = tar.extractfile(member)
                if handle is None:
                    raise SystemExit(f"[scanner-freshness] {blob} carries no readable APKINDEX "
                                     "member — a missing index is not a verdict (issue #2709)")
                return handle.read().decode("utf-8", "replace")
    raise SystemExit(f"[scanner-freshness] {blob} carries no APKINDEX member — "
                     "a missing index is not a verdict (issue #2709)")


def _index_from_snapshot(path: Path) -> str:
    """The APKINDEX text from a local snapshot file (plain text or .tar.gz). Never touches
    the network: tests and air-gapped runners use this path exclusively (issue #2709)."""
    if not path.is_file():
        raise SystemExit(f"[scanner-freshness] WOLFI_APKINDEX names {str(path)!r}, which does "
                         "not exist — a comparison against a missing index is not a verdict "
                         "(issue #2709)")
    return _apkindex_from_tar(path) if path.suffix == ".gz" else path.read_text(
        encoding="utf-8", errors="replace")


def _fetch_wolfi_index() -> str:
    """Wolfi's x86_64 APKINDEX text, fetched once, fresh — the comparison's whole point is
    consulting what is published TODAY. The only network reach in this lane (issue #2709);
    keep every hermetic comparison on `_evaluate_freshness`/`_index_from_snapshot` so the
    hermetic selection can never trace a reach to `packages.wolfi.dev` (issue #1067)."""
    import tempfile
    import urllib.request

    with tempfile.TemporaryDirectory() as tmp:
        blob = Path(tmp) / "APKINDEX.tar.gz"
        with urllib.request.urlopen(WOLFI_INDEX_URL, timeout=60) as resp:
            blob.write_bytes(resp.read())
        return _index_from_snapshot(blob)


def _pinned_scanner_versions() -> dict[str, str]:
    """The version this repo pins for each compared package (issue #2709).

    The image-backed scanners take their `version` from digests.json; Syft's pin is the
    `ARG SYFT_VERSION=` default baked into the Grype image — digests.json carries no entry for
    a tool that has no image of its own.
    """
    recorded = digests()
    pins = {tool: str((recorded.get(tool) or {}).get("version") or "") for tool in TOOLS}
    dockerfile = REPO / "containers" / "scanners" / "grype" / "Dockerfile"
    match = (re.search(r"^ARG\s+SYFT_VERSION=(\S+)", dockerfile.read_text(encoding="utf-8"), re.M)
             if dockerfile.is_file() else None)
    pins[SBOM_TOOL] = match.group(1) if match else ""
    return pins


def _evaluate_freshness(text: str, source: str) -> int:
    """Compare every pinned scanner version against the newest build in the given APKINDEX text.

    The frozen `SCANNER_BASELINE` (#1284) catches pins older than a human's last measurement;
    this consults a real index. A pin that lags the newest published build gets
    `FRESHNESS_GRACE_DAYS` of grace — Wolfi churns builds faster than the repo should chase —
    and a lag past that window fails, naming package, pinned version and live newest. A pin for
    a package the index does not carry fails too: unresolvable is never silently passing. Pure:
    takes the index text, never fetches it (issue #1067).
    """
    index = _wolfi_stanzas(text)
    pins = _pinned_scanner_versions()
    problems: list[str] = []
    within_grace: list[str] = []
    now = _dt.datetime.now(_dt.timezone.utc)
    for package in FRESHNESS_PACKAGES:
        pin = pins.get(package) or ""
        builds = index.get(package) or []
        if not pin:
            problems.append(f"{package}: no pinned version found — the comparison cannot judge "
                            "a pin it cannot read (issue #2709)")
            continue
        if not builds:
            problems.append(f"{package}: pinned {pin!r} but the Wolfi index carries no "
                            f"`{package}` package — an unresolvable pin is never a silent pass")
            continue
        newest, epoch = max(builds, key=lambda b: (_version_sort_key(b[0]), b[1]))
        if _version_sort_key(pin) >= _version_sort_key(newest):
            continue
        age_days = ((now - _dt.datetime.fromtimestamp(epoch, _dt.timezone.utc)).days
                    if epoch else FRESHNESS_GRACE_DAYS + 1)
        if age_days > FRESHNESS_GRACE_DAYS:
            problems.append(f"{package}: pinned {pin} but Wolfi published {newest} "
                            f"{age_days} days ago (grace is {FRESHNESS_GRACE_DAYS}) — bump the "
                            "Dockerfile ARG and `make scanner-digests` (issue #2709)")
        else:
            within_grace.append(f"{package}: pinned {pin} lags {newest} ({age_days}d old) — "
                                f"inside the {FRESHNESS_GRACE_DAYS}d grace")
    print(f"[scanner-freshness] measured against {source}")
    for note in within_grace:
        print(f"  ~ {note}")
    if problems:
        print(f"[scanner-freshness] {len(problems)} stale-pin problem(s):")
        for item in problems:
            print(f"  - {item}")
        return 1
    print(f"[scanner-freshness] OK: {len(FRESHNESS_PACKAGES)} pins checked against {source}; "
          f"none lags the newest published build beyond the {FRESHNESS_GRACE_DAYS}d grace")
    return 0


def scanner_freshness() -> int:
    """CLI entry for `make scanner-freshness`: resolve the index, then evaluate.

    `WOLFI_APKINDEX` names a local snapshot (plain text or .tar.gz) and the comparison runs
    with no network at all; otherwise this fetches Wolfi's x86_64 index once, fresh.
    """
    local = (os.environ.get("WOLFI_APKINDEX") or "").strip()
    if local:
        return _evaluate_freshness(_index_from_snapshot(Path(local)), f"local snapshot {local}")
    return _evaluate_freshness(_fetch_wolfi_index(), WOLFI_INDEX_URL)


DEFAULT_POLICY = {
    "fail_on": ["critical", "high"],
    "pr_fail_on": [],
    "require_fix": True,
    "issue_severities": ["critical", "high"],
    #: Only these events may fail the run. Everything else — a pull request, a push — reports.
    "enforce_events": ["schedule", "workflow_dispatch"],
}


def digests() -> dict:
    if not DIGESTS.is_file():
        raise SystemExit(f"[security-scan] {DIGESTS} is missing — run `make scanner-digests`")
    return json.loads(DIGESTS.read_text(encoding="utf-8"))


def image_ref(tool: str) -> str:
    """`<registry>/llgenie/<tool>:<content hash>` — the immutable ref from the digests file."""
    entry = digests().get(tool)
    if not entry:
        raise SystemExit(f"[security-scan] no scanner image recorded for `{tool}`")
    registry = os.environ.get("LLGENIE_REGISTRY", "ghcr.io/asimov-agent").rstrip("/").lower()
    return f"{registry}/llgenie/{tool}:{entry['tag']}"


def policy() -> dict:
    merged = dict(DEFAULT_POLICY)
    if POLICY.is_file():
        merged.update(json.loads(POLICY.read_text(encoding="utf-8")))
    return merged


#: A manifest digest as GHCR reports it (`sha256:<64 hex>`); the shape `image_digest` must carry
#: so a scan can prove which image it runs (issue #2609).
DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")
#: The allow-list of published images the security lane scans (issue #2706). Engine entries name
#: `(engine, variant)` and resolve their CURRENT pinned tag through scripts/engine_image.py, so
#: the manifest never carries a stale digest literal; the registry digest is read at scan time and
#: the scan runs against `ref@sha256:…` — issue #2609's digest proof applied to the images a scan
#: TARGETS, not just the scanners it runs.
SCANNED_IMAGES = REPO / "containers" / "scanned-images.json"
#: The lane that scans each engine image right after it is published (issue #2706). `check`
#: requires both lane wirings so neither can silently drop the image scan.
ENGINE_WORKFLOW = REPO / ".github" / "workflows" / "engine-build.yml"
#: The report names the image scan writes; the slug is the manifest entry's `name`.
IMAGE_SLUG_RE = re.compile(r"[a-z0-9][a-z0-9-]*")


def registry_manifest_digests(image_ref: str) -> dict:
    """The manifest digests the registry serves for a ref: the index digest, its per-platform
    children (issue #2609), and each child manifest's CONFIG-blob digest (issue #2727 — a
    classic, non-containerd daemon reports a pulled image's `.Id` as the config digest, so the
    family of ids a correct pull legitimately reports includes it). `{}` when the registry
    cannot answer for this ref; a child whose manifest cannot be read is simply absent from
    `configs`, never a silent pass of a foreign id."""
    res = subprocess.run([RUNTIME, "buildx", "imagetools", "inspect", image_ref,  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
                          "--format", "{{json .Manifest}}"], capture_output=True, text=True)
    if res.returncode != 0:
        return {}
    try:
        man = json.loads((res.stdout or "").strip())
    except json.JSONDecodeError:
        return {}
    if not isinstance(man, dict):
        return {}
    children = [str(m.get("digest")) for m in (man.get("manifests") or man.get("children") or [])
                if isinstance(m, dict) and m.get("digest")]
    return {"index": str(man.get("digest") or ""), "children": children,
            "configs": _child_config_digests(image_ref, children)}


def _child_config_digests(image_ref: str, children: list[str]) -> list[str]:
    """Ask the registry for each manifest the index names and read its `config.digest`.

    The child digest is content-addressed, so re-inspecting it at `name@<child>` is exact.
    The child read uses `--raw`, not `--format {{json .Manifest}}`: the format form
    normalizes a single-manifest (non-index) ref and DROPS the `config` field entirely —
    the defect that reddened dispatch run 43784224774 while every stubbed test stayed
    green. `--raw` serves the manifest exactly as the registry stored it, `config.digest`
    included. All pinned refs are `ghcr.io/<path>:<tag>` (no registry port), so dropping
    everything from the last `:` is the repository name (issue #2727).
    """
    base = image_ref.split("@", 1)[0].rsplit(":", 1)[0]
    out: list[str] = []
    for child in children:
        res = subprocess.run([RUNTIME, "buildx", "imagetools", "inspect",  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
                              f"{base}@{child}", "--raw"],
                             capture_output=True, text=True)
        if res.returncode != 0:
            continue
        try:
            man = json.loads((res.stdout or "").strip())
        except json.JSONDecodeError:
            continue
        config = man.get("config") if isinstance(man, dict) else None
        digest = config.get("digest") if isinstance(config, dict) else config
        if isinstance(digest, str) and DIGEST_RE.fullmatch(digest):
            out.append(digest)
    return out


def _local_image_digest(image_ref: str) -> str:
    """What the daemon reports as the id of the image a run would execute."""
    res = subprocess.run([RUNTIME, "image", "inspect", image_ref, "--format", "{{.Id}}"],  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
                         capture_output=True, text=True)
    return (res.stdout or "").strip()


def verify_pinned_digest(tool: str, ref: str, *, built: bool) -> None:
    """Prove the image about to run IS the image `digests.json` pinned (issue #2609).

    A content-hash tag is re-pushable, and a re-build of the SAME Dockerfile resolves whatever the
    package repository publishes that day (measured 2026-11-13: `semgrep:5954e2aad609` served
    `sha256:180c3f7e…` while the same tag cached on a host ran `sha256:7fd77096…`), so the tag
    alone does not pin what a scan runs. The recorded index digest must equal what the registry
    serves, and the image the daemon holds must belong to that index's own family: a classic
    (non-containerd) daemon reports a pulled image's id as the CONFIG digest of the child it ran
    (measured 2026-11-15, run 43710607827: `grype:a607057cfd07` reported `sha256:c585d524…` — the
    config digest of the child `sha256:ccff82ef…` of the pinned index `sha256:12ef938b…`), while a
    containerd daemon reports the index/manifest digest; all of those ids are accepted, and none
    outside that family is (issue #2727). A mismatch exits non-zero naming BOTH digests; the
    locally built deferral image (issue #2518) prints its built digest and says the registry pin
    is not registry-verifiable for an unpublished ref.
    """
    recorded = str((digests().get(tool) or {}).get("image_digest") or "")
    if not DIGEST_RE.fullmatch(recorded):
        raise SystemExit(f"[security-scan] {tool}: digests.json has no `image_digest` for the pinned "
                         "image — the scan cannot prove which scanner it runs (issue #2609); "
                         "run `make pin-scanner-image-digests`")
    actual = _local_image_digest(ref)
    if built:
        print(f"[security-scan] {tool}: executed {ref} built locally (deferral, issue #2518) at "
              f"digest {actual}; the registry pin {recorded} is not registry-verifiable for an "
              "unpublished ref")
        return
    man = registry_manifest_digests(ref)
    index = man.get("index") or ""
    if not index:
        raise SystemExit(f"[security-scan] {tool}: the registry cannot answer for {ref}, so the "
                         f"pinned image {recorded} cannot be verified (issue #2609)")
    if index != recorded:
        raise SystemExit(f"[security-scan] {tool}: the pinned ref {ref} serves {index} but "
                         f"digests.json records {recorded} — the tag moved (issue #2609); the scan "
                         "refuses the moved image")
    accepted = {index, *man.get("children", []), *man.get("configs", [])}
    if actual and actual not in accepted:
        raise SystemExit(f"[security-scan] {tool}: the local copy of {ref} is {actual}, not the "
                         f"pinned image (recorded {recorded}) — a stale local scanner image "
                         "(issue #2609); delete it so the pinned ref re-pulls")
    print(f"[security-scan] {tool}: executed image digest {actual or index} for {ref} "
          f"(pinned {recorded})")


def ensure_image(tool: str) -> str:
    """The pinned image, from the registry when it is published, else built from its Dockerfile.

    A pull is the normal path. It fails for a `pull_request` run before the first publish (the
    `scanner-images` job publishes on a push to main only), and for a fork run, whose token cannot
    write the base repo's packages. That is not a reason to skip a scan, and it is not a second
    implementation: the SAME Dockerfile — digest-pinned base, exact versions — is built and tagged
    with the SAME immutable ref the workflow asked for, and the log says which path was taken.

    #2609: every pull-path resolution then runs `verify_pinned_digest`, which proves the registry
    still serves the manifest digest `digests.json` recorded for that ref; a mismatch exits
    non-zero naming both digests. The deferral build prints its built digest instead.
    """
    ref = image_ref(tool)
    if subprocess.run([RUNTIME, "image", "inspect", ref],  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
                      capture_output=True).returncode == 0:
        verify_pinned_digest(tool, ref, built=False)
        return ref
    pull = subprocess.run([RUNTIME, "pull", ref], capture_output=True, text=True)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
    if pull.returncode == 0:
        print(f"[security-scan] pulled {ref}")
        verify_pinned_digest(tool, ref, built=False)
        return ref
    context = REPO / "containers" / "scanners" / tool
    print(f"[security-scan] {ref} is not published yet — building it through "
          "scripts/scanner_image.py build (issue #744: the same one builder the publish job "
          "uses, the same Dockerfile, tagged with the ref the scan asked for; a scan deferral "
          "NEVER pushes)")
    built = _scanner_image.build(tool, tag=ref)  # local `docker build` only — never a push
    if not built:
        raise SystemExit(f"[security-scan] build of {tool} from {context} failed")
    verify_pinned_digest(tool, ref, built=True)
    return ref


def _run(argv: list[str], image: str, entrypoint: str | None = None,
         volumes: list[str] | None = None) -> int:
    """Run one scanner from its image, with the checkout mounted so it writes its reports.

    `volumes` overrides the mount (published-image scans, issue #2706: the target is a registry
    ref, not the tree — only the reports dir needs to be writable from inside the container).
    """
    REPORTS.mkdir(parents=True, exist_ok=True)
    # The image's own USER is a non-root one, but the mounted checkout belongs to the RUNNER user:
    # without `--user` the scanner cannot create its report ("permission denied") and would leave
    # root-owned files in the worktree (issue #433). Running as the invoking user fixes both.
    extra = ["--entrypoint", entrypoint] if entrypoint else []
    mounts = volumes if volumes is not None else [f"{REPO}:/work:rw"]
    cmd = [RUNTIME, "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}", *extra,
           *(item for vol in mounts for item in ("-v", vol)), "-w", "/work",
           "-e", "HOME=/tmp", ensure_image_for(image), *argv]
    print(f"[security-scan] $ {' '.join(cmd)}")
    return subprocess.run(cmd).returncode  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)


def ensure_image_for(ref: str) -> str:
    """`_run` is handed a ref; resolve it to an available image (see `ensure_image`)."""
    tool = ref.rsplit("/", 1)[-1].split(":")[0]
    if tool in TOOLS:
        return ensure_image(tool)
    return ref


def sbom() -> int:
    """Syft writes the CycloneDX SBOM; Grype matches against exactly this file."""
    # The Grype image's ENTRYPOINT is `grype`, so Syft is reached with `--entrypoint syft`; passing
    # `syft` as an argument makes grype read it as a second positional and refuse ("accepts at most
    # 1 arg(s), received 2") — measured on the first real CI run.
    return _run(["-o", "cyclonedx-json=/work/security-reports/sbom.cdx.json", "dir:."],
                image_ref("grype"), entrypoint="syft")


def scan(tool: str) -> int:
    if tool not in ALL_TOOLS:
        raise SystemExit(f"[security-scan] unknown tool `{tool}`; known: {', '.join(ALL_TOOLS)}")
    if tool == "syft":       # the SBOM step, addressable as a tool id
        return sbom()
    if tool == "trivy":
        # One format per invocation (trivy takes one `--format`), so JSON for the verdict and SARIF
        # for the Security tab are two runs over the same tree.
        #
        # The `secret` scanner is the committed-credential half of the SECURITY ADMISSION GATE
        # (issue #1283): `--scanners vuln,secret` makes the SAME digest-pinned trivy image also flag a
        # committed credential (a `ghp_`/`sk-…`/cloud key in a trackable file), so a secret is a
        # first-class finding — it flows through `security-verdict` and `security-issues` with the
        # report/sha annotation, appears in the uploaded SARIF (`category: trivy`), and (because it
        # carries a `fail_on` severity and is always actionable) makes the daily security-scan run
        # red — which the all-pipelines sweep reads as the admission gate red. No new image, no new
        # network, no fixed-version games: the same scanner, just asked for its secret ruleset.
        #
        # The `misconfig` scanner (issue #2234) is the IaC half of the same gate: `--scanners
        # vuln,secret,misconfig` asks the SAME image for its built-in Dockerfile/Compose/Terraform/K8s
        # rule set, so a hardening drift (a Dockerfile missing its non-root `USER`, a workflow with
        # an unsafe privilege shape) becomes a first-class finding too. The rule set is the pinned
        # version's own (trivy 0.70.0-r5 ships the misconfig checks; the image is content-addressed
        # by digest — see `containers/scanners/trivy/Dockerfile` and `digests.json`), so no separate
        # rule pack needs pinning and the scanner cannot silently drift.
        base = ["fs", "--severity", "CRITICAL,HIGH,MEDIUM", "--scanners", "vuln,secret,misconfig"]
        rc = _run([*base, "--format", "json", "--output", "security-reports/trivy.json", "."],
                  image_ref(tool))
        rc |= _run([*base, "--format", "sarif", "--output", "security-reports/trivy.sarif", "."],
                   image_ref(tool))
        return rc
    if tool == "grype":
        if not (REPORTS / "sbom.cdx.json").is_file():
            raise SystemExit("[security-scan] grype needs the Syft SBOM: run `make sbom` first")
        return _run(["sbom:/work/security-reports/sbom.cdx.json", "-o", "json",
                     "--file", "/work/security-reports/grype.json"], image_ref(tool))
    if tool == "semgrep":
        # A COMMITTED, content-addressed rule snapshot, not a floating registry pack: the pipeline's
        # immutability promise (issue #714) must cover the SAST rules a scan runs too, else the same
        # tree re-scanned a week apart can give different results with zero tree change. The pack is
        # pinned in `containers/scanners/semgrep/rules/default.yml` (baked when the image is built)
        # and its sha256 is recorded in `digests.json` (`semgrep.rules_sha`) — the same digests
        # mechanism that pins the scanner binaries (issue #1284). An explicit local pack also means
        # no `--config auto` (Semgrep refuses `auto` when metrics are off — measured on the 4th CI
        # run of this job), no registry fetch at scan time, and no per-run decision.
        pack = REPO / "containers" / "scanners" / "semgrep" / "rules" / "default.yml"
        if not pack.is_file():
            raise SystemExit("[security-scan] the pinned semgrep rules pack is missing — "
                             "make scanner-digests / commit containers/scanners/semgrep/rules/default.yml")
        rc = _run(["scan", "--config", f"/work/{pack.relative_to(REPO)}",
                   "--exclude", "security-reports",
                   "--exclude", "containers/scanners/semgrep/rules",
                   "--json", "--output",
                   "/work/security-reports/semgrep.json", "--metrics", "off", "."], image_ref(tool))
        # Two scans of the same tree must be byte-identical (issue #1284): semgrep embeds a `time`
        # (and `profiling_results`) block of wall-clock measurements, which differs every run. Strip
        # it so `semgrep.json` is reproducible from the tree + the pinned pack. The report directory
        # itself is excluded from the scan, or the second run would scan the first run's own output
        # and `paths.scanned` would grow — measured by the review of PR #2082, where the naive
        # two-run differed at exactly that key. The rule pack lives inside the scan root and is
        # itself excluded too (issue #2105): the pack's own bytes are detector patterns, so scanning
        # them reports a finding whose only "fix" would weaken the scanner; the pack is what the scan
        # RUNS, not what it audits. Excluding it removes the self-reference and nothing else.
        out = REPORTS / "semgrep.json"
        if out.is_file() and rc == 0:
            _strip_semgrep_timing(out)
        return rc
    raise SystemExit(f"[security-scan] unknown tool `{tool}`; known: {', '.join(ALL_TOOLS)}")


def all_scans() -> int:
    """Syft first (Grype matches exactly that SBOM), then the CVE scanners."""
    rc = sbom()
    for tool in TOOLS:
        rc = scan(tool) or rc
    return rc


# ---------------------------------------------------------------------------
# Published-image scans (issue #2706): the runtime package set the product SHIPS
# ---------------------------------------------------------------------------
# The tree scans above judge sources. An engine image's installed wheel set and its base-image OS
# packages exist only in the built artifact — `trivy fs .` never sees them (issue #2608's audit).
# The image scans here run the SAME digest-pinned scanner images against a published image, and
# every target is addressed BY DIGEST: an undigested ref is refused, so a scan can always name the
# exact manifest it judged (issue #2609's rule, turned onto the scan target).

def scanned_images() -> dict:
    """The allow-list of images the lane scans (`containers/scanned-images.json`)."""
    if not SCANNED_IMAGES.is_file():
        raise SystemExit(f"[security-scan] {SCANNED_IMAGES} is missing — the published-image "
                         "allow-list must exist (issue #2706)")
    return json.loads(SCANNED_IMAGES.read_text(encoding="utf-8"))


def scan_image(ref: str, slug: str = "target") -> int:
    """ONE published image, scanned BY DIGEST with the pinned trivy/syft/grype (issue #2706).

    `ref` MUST carry `@sha256:<64 hex>`. Trivy scans the image's vulnerability set (`vuln` only:
    committed secrets and IaC misconfigurations are the tree scans' domain), Syft writes the image
    SBOM, Grype matches exactly that SBOM — the same three-stage shape as the tree scan. The target
    is a registry ref, so the mount the containers need is the reports dir (`/reports`), not the
    checkout. The exact ref scanned is recorded in `image-<slug>.meta.json` so `findings()` can
    name the image.
    """
    if not re.search(r"@sha256:[0-9a-f]{64}$", ref or ""):
        raise SystemExit(f"[security-scan] image scan target {ref!r} is not digest-pinned — pass "
                         "<ref>@sha256:<64 hex>; a target without a digest is refused (issue #2706)")
    if not IMAGE_SLUG_RE.fullmatch(slug):
        raise SystemExit(f"[security-scan] image slug {slug!r} is not a lowercase slug")
    REPORTS.mkdir(parents=True, exist_ok=True)
    volumes = [f"{REPORTS.resolve()}:/reports:rw"]
    rc = _run(["image", "--severity", "CRITICAL,HIGH,MEDIUM", "--scanners", "vuln",
               "--timeout", "30m",  # CUDA-scale base layers exceed trivy's default 10m analysis
               "--format", "json", "--output", f"/reports/image-{slug}.trivy.json", ref],
              image_ref("trivy"), volumes=volumes)
    rc |= _run(["-o", f"cyclonedx-json=/reports/image-{slug}.cdx.json", ref],
               image_ref("grype"), entrypoint="syft", volumes=volumes)
    rc |= _run([f"sbom:/reports/image-{slug}.cdx.json", "-o", "json",
                "--file", f"/reports/image-{slug}.grype.json"], image_ref("grype"),
               volumes=volumes)
    (REPORTS / f"image-{slug}.meta.json").write_text(
        json.dumps({"ref": ref, "scanned_at": _dt.date.today().isoformat()}, indent=2) + "\n",
        encoding="utf-8")
    return rc


def _resolve_engine_ref(engine: str, variant: str) -> str:
    """`<registry>/<name>:<pinned-hash>-<variant>` for an engine entry — resolved at call time
    from the committed engine params, so the manifest never carries a stale tag (issue #2706).
    Imported lazily: the security lane must not pay the engine stack's import cost to read a ref."""
    try:
        from . import engine_image as _ei
    except ImportError:
        import engine_image as _ei  # type: ignore
    spec = _ei.resolve(engine, None, variant)
    return f"{_ei.REGISTRY}/{spec['tag']}"


def resolve_scan_targets(manifest: dict | None = None) -> list[tuple[str, str]]:
    """`(slug, ref@sha256:<64 hex>)` for every manifest entry. The registry must answer for the
    ref: an image that is not published yet is a hard failure, never a silent skip."""
    manifest = manifest or scanned_images()
    out: list[tuple[str, str]] = []
    for entry in manifest.get("images") or []:
        slug = str(entry.get("name") or "")
        if entry.get("engine"):
            ref = _resolve_engine_ref(str(entry["engine"]), str(entry.get("variant") or ""))
        else:
            ref = str(entry.get("ref") or "")
        index = (registry_manifest_digests(ref) or {}).get("index") or ""
        if not DIGEST_RE.fullmatch(index):
            raise SystemExit(f"[security-scan] scanned-images.json: the registry serves no index "
                             f"digest for {ref} — the image is not published (or the ref is wrong); "
                             "an image scan never proceeds undigested (issue #2706)")
        out.append((slug, f"{ref}@{index}"))
    return out


def scan_images_all() -> int:
    """The lane step: every image the manifest allows, each resolved to its current ref and
    scanned by the digest the registry serves for it (issue #2706)."""
    rc = 0
    for slug, ref in resolve_scan_targets():
        print(f"[security-scan] image scan: {slug} -> {ref}")
        rc |= scan_image(ref, slug=slug)
    return rc


def scan_published_image(engine: str, variant: str) -> int:
    """The engine-build lane step (issue #2706): scan the image this cell JUST pushed, addressed
    by the digest the registry now serves for its pinned tag — the published artifact is measured,
    not assumed."""
    ref = _resolve_engine_ref(engine, variant)
    index = (registry_manifest_digests(ref) or {}).get("index") or ""
    if not DIGEST_RE.fullmatch(index):
        raise SystemExit(f"[security-scan] {engine}/{variant}: no registry digest for {ref} — the "
                         "push did not land where the scan can reach it (issue #2706)")
    slug = f"{ref.rsplit('/', 1)[-1].replace(':', '-').replace('.', '-')}"
    print(f"[security-scan] published-image scan: {slug} -> {ref}@{index}")
    return scan_image(f"{ref}@{index}", slug=slug)


def scan_image_fixture() -> int:
    """The loud AC proof (issue #2706): a deliberate known-vulnerable image, scanned report-only
    into the current SECURITY_REPORTS. It never flows into the lane's verdict/issues reports and it
    FAILS when the fixture produces no findings — a fixture the scanners cannot see is a broken
    proof, not a clean run."""
    fx = scanned_images().get("fixture") or {}
    ref = str(fx.get("ref") or "")
    slug = str(fx.get("name") or "fixture")
    index = (registry_manifest_digests(ref) or {}).get("index") or ""
    if not DIGEST_RE.fullmatch(index):
        raise SystemExit(f"[security-scan] fixture {ref}: the registry serves no index digest — "
                         "the fixture image must be pullable by digest (issue #2706)")
    rc = scan_image(f"{ref}@{index}", slug=slug)
    items = findings()
    by_source: dict[str, int] = {}
    for item in items:
        by_source[item["source"]] = by_source.get(item["source"], 0) + 1
    print(f"[security-scan] fixture {ref}@{index}: {len(items)} normalized finding(s) "
          f"({', '.join(f'{k}: {v}' for k, v in sorted(by_source.items())) or 'NONE'})")
    for item in items[:20]:
        print(f"  {item['source']}: {item['id']} {item['package']} {item['current']} -> "
              f"{item['fixed']} ({item['severity']}) image={item.get('image', '')}")
    if not items:
        print("[security-scan] FIXTURE PROVED NOTHING — the image-scan path is broken "
              "(issue #2706); this is a failure, never a clean result")
        return 1
    return rc


def _trivy_findings(report: dict) -> list[dict]:
    return [{
        "id": vuln.get("VulnerabilityID"),
        "package": vuln.get("PkgName"),
        "current": vuln.get("InstalledVersion"),
        "fixed": vuln.get("FixedVersion") or "",
        "severity": str(vuln.get("Severity", "")).lower(),
        "source": "trivy",
    } for result in report.get("Results") or []
        for vuln in result.get("Vulnerabilities") or []]


def _strip_semgrep_timing(path: Path) -> None:
    """Remove the wall-clock `time`/`profiling_results` blocks so semgrep.json is byte-identical
    across re-scans of the same tree (issue #1284). Semgrep always embeds them; the findings live
    in `results`, which the timings do not change."""
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("time", None)
    data.pop("profiling_results", None)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _trivy_secret_findings(report: dict) -> list[dict]:
    """Trivy's committed-credential matches, normalised into the same finding shape (issue #1283).

    A `secret`-class result carries `Results[].Secrets[]` (RuleID, Category, Severity, Title,
    Match). There is no package version or fixed version for a committed secret — its remediation
    is removal and rotation, never a bump — so `package` names the file that holds it and `current`
    is the redacted match. `source` is `SECRET_SOURCE` so the issue path labels it `component:code`
    and `blocking()` treats it as actionable regardless of `require_fix`.
    """
    return [{
        "id": sec.get("RuleID"),
        "package": result.get("Target"),
        "current": sec.get("Match") or "",
        "fixed": "",
        "severity": str(sec.get("Severity", "")).lower() or "unknown",
        "source": SECRET_SOURCE,
    } for result in report.get("Results") or []
        for sec in result.get("Secrets") or []]


def _trivy_misconfig_findings(report: dict) -> list[dict]:
    """Trivy's IaC misconfiguration matches, normalised into the shared finding shape (issue #2234).

    A `misconfig`-class result carries `Results[].Misconfigurations[]` (ID, Title, Severity,
    Message) under a result whose `Class` is `config` — measured against the pinned trivy image on
    a planted bad Dockerfile. There is no package version or fixed version for a misconfiguration
    — its remediation is editing the matched IaC (a Dockerfile `USER`, a workflow privilege), never
    a bump — so `package` names the file and `current` is the message from the fired check.
    `source` is `MISCONFIG_SOURCE` so the issue path labels it `component:code` and `blocking()`
    treats it as actionable regardless of `require_fix`, exactly like a committed secret or a SAST
    finding.
    """
    return [{
        "id": cfg.get("ID") or cfg.get("AVDID"),
        "package": result.get("Target"),
        "current": cfg.get("Message") or cfg.get("Title") or "",
        "fixed": "",
        "severity": str(cfg.get("Severity", "")).lower() or "unknown",
        "source": MISCONFIG_SOURCE,
    } for result in report.get("Results") or []
        if result.get("Class") == "config"
        for cfg in result.get("Misconfigurations") or []]


def _grype_findings(report: dict) -> list[dict]:
    return [{
        "id": (match.get("vulnerability") or {}).get("id"),
        "package": (match.get("artifact") or {}).get("name"),
        "current": (match.get("artifact") or {}).get("version"),
        "fixed": ", ".join((match.get("fix") or {}).get("versions") or []),
        "severity": str((match.get("vulnerability") or {}).get("severity", "")).lower(),
        "source": "grype",
    } for match in report.get("matches") or []]


def _semgrep_findings(report: dict) -> list[dict]:
    """The SAST matches from semgrep.json, normalised into the shared finding shape (issue #1554).

    A result carries a `check_id` (the rule that fired), a `path`, a start/end line and the matched
    source region in `extra.lines`. There is no package version or fixed version — a SAST finding's
    remediation is editing the code, never a bump — so `package` names the file (path:line) and
    `current` is the matched region. `source` is `SEMGREP_SOURCE` so `blocking()` and the issue
    path treat it as always actionable (like a committed secret) and label it `component:code`.
    Semgrep severity (ERROR/WARNING/INFO) is mapped into the policy vocabulary (see `SEMGREP_SEVERITY`).
    """
    return [{
        "id": result.get("check_id"),
        "package": f"{result.get('path')}:{(result.get('start') or {}).get('line')}",
        "current": (result.get("extra") or {}).get("lines") or "",
        "fixed": "",
        "severity": SEMGREP_SEVERITY.get(
            str((result.get("extra") or {}).get("severity", "")).upper(), "unknown"),
        "source": SEMGREP_SOURCE,
    } for result in report.get("results") or []]


def findings(reports: Path | None = None) -> list[dict]:
    """Every finding from every report that exists, in one shape."""
    reports = reports or REPORTS  # resolved at call time: `SECURITY_REPORTS`/a test can move it
    out: list[dict] = []
    for name, reader in (("trivy.json", _trivy_findings),
                         ("trivy.json", _trivy_secret_findings),
                         ("trivy.json", _trivy_misconfig_findings),
                         ("grype.json", _grype_findings),
                         ("semgrep.json", _semgrep_findings)):
        path = reports / name
        if not path.is_file():
            continue
        try:
            out.extend(reader(json.loads(path.read_text(encoding="utf-8"))))
        except json.JSONDecodeError:
            raise SystemExit(f"[security-scan] {path} does not parse — the run is not green")
    # Published-image reports (issue #2706): `image-<slug>.trivy.json` and `image-<slug>.grype.json`
    # are read by the SAME normalisers, and every finding is tagged with the exact `ref@digest` the
    # scan recorded in `image-<slug>.meta.json`. From here on the pipeline does not distinguish an
    # image finding from a tree finding: `verdict()`, `blocking()` and `security-issues` judge them
    # under one policy, and the issue body names the image the advisory lives in.
    for path in sorted(reports.glob("image-*.trivy.json")) + sorted(reports.glob("image-*.grype.json")):
        reader = _trivy_findings if path.name.endswith(".trivy.json") else _grype_findings
        meta = reports / f"{path.name.split('.')[0]}.meta.json"
        image = ""
        if meta.is_file():
            try:
                image = str(json.loads(meta.read_text(encoding="utf-8")).get("ref") or "")
            except json.JSONDecodeError:
                raise SystemExit(f"[security-scan] {meta} does not parse — the run is not green")
        try:
            for item in reader(json.loads(path.read_text(encoding="utf-8"))):
                if image:
                    item["image"] = image
                out.append(item)
        except json.JSONDecodeError:
            raise SystemExit(f"[security-scan] {path} does not parse — the run is not green")
    return out


def blocking(items: list[dict], pol: dict, mode: str = "full") -> list[dict]:
    """The findings that must fail the run, for the mode's severity set."""
    severities = pol.get("pr_fail_on") if mode == "pr" else pol.get("fail_on")
    fail_on = {str(s).lower() for s in severities or []}
    if not fail_on:  # report-only mode: the run writes SARIF + the artifact and never gates
        return []
    out = []
    for item in items:
        if item["severity"] not in fail_on:
            continue
        if item.get("source") in (SECRET_SOURCE, SEMGREP_SOURCE, MISCONFIG_SOURCE):
            # A committed credential, a SAST finding and an IaC misconfiguration are ALWAYS
            # actionable: their remediation is removal/masking (secret), editing the matched code
            # (semgrep) or editing the matched IaC (misconfig), never "await a patched version", so
            # `require_fix` — which exists to stop an unfixable advisory from stalling the pipeline
            # — must not suppress them. `fail_on` still gates: a `medium`/`unknown` SAST, secret or
            # misconfig finding is recorded, never a red (issues #1283, #1554, #2234).
            out.append(item)
        elif pol.get("require_fix") and not item["fixed"]:
            continue
        else:
            out.append(item)
    return out


def mode_for(event: str, pol: dict | None = None) -> str:
    """`full` (gate) when the event may fail the run, `pr` (report-only) for every other event.

    The set of events that may gate is data (`enforce_events`), never a literal in a workflow step,
    and `push` / `pull_request` are never in it — `check` refuses a policy that puts them there.
    """
    pol = pol or policy()
    enforce = {str(e).lower() for e in pol.get("enforce_events") or []}
    return "full" if str(event).lower() in enforce else "pr"


def triggers(text: str) -> set[str]:
    """The event names in a workflow's `on:` block (top-level keys only)."""
    lines = text.splitlines()
    out: set[str] = set()
    inside = False
    for raw in lines:
        if raw.startswith("on:"):
            inside = True
            inline = raw.split(":", 1)[1].strip()
            for name in re.findall(r"[A-Za-z_]+", inline):
                out.add(name.lower())
            continue
        if inside:
            if raw and not raw.startswith((" ", "\t", "#")):
                break                      # the next top-level key ends the block
            m = re.match(r"^\s{2}([A-Za-z_]+):", raw)
            if m:
                out.add(m.group(1).lower())
    return out


def verdict(mode: str = "", event: str = "") -> int:
    pol = policy()
    if not mode:
        mode = mode_for(event, pol) if event else "full"
    items = findings()
    bad = blocking(items, pol, mode)
    severities = pol.get("pr_fail_on") if mode == "pr" else pol.get("fail_on")
    where = f"event={event or 'local'}, mode={mode}"
    if not severities:
        print(f"[security-scan] REPORT-ONLY ({where}): {len(items)} finding(s) recorded; this run "
              "does not gate — only an event in `enforce_events` may fail the pipeline")
        for item in items:
            print(f"  {item['source']}: {item['id']} {item['package']} "
                  f"{item['current']} -> {item['fixed'] or '(no fix named)'} ({item['severity']})")
        return 0
    if bad:
        print(f"[security-scan] FAIL ({where}): {len(bad)} finding(s) at {severities}"
              f"{' with a fix available' if pol.get('require_fix') else ''}")
        for item in bad[:40]:
            print(f"  {item['source']}: {item['id']} {item['package']} "
                  f"{item['current']} -> {item['fixed']} ({item['severity']})")
        return 1
    print(f"[security-scan] OK ({where}): {len(items)} finding(s) recorded, none blocking "
          f"(fail_on={severities}, require_fix={pol.get('require_fix')})")
    return 0


def _display(path: Path) -> str:
    """A path as the log should name it: repo-relative when it can be, absolute otherwise."""
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def check() -> int:
    """The policy, the digests and the workflow's triggers must be sane before a scan is trusted."""
    problems: list[str] = []
    pol = policy()
    known = {"critical", "high", "medium", "low", "negligible", "unknown"}
    # Which events may gate is data with a hard floor: the scan is its own daily pipeline (#738).
    enforce = {str(e).lower() for e in pol.get("enforce_events") or []}
    if not enforce:
        problems.append("security-policy.json: `enforce_events` is empty — no event could ever gate")
    for event in sorted(enforce):
        if event not in KNOWN_EVENTS:
            problems.append(f"security-policy.json: `{event}` in `enforce_events` is not a known event")
        if event in NEVER_GATING:
            problems.append(f"security-policy.json: `{event}` in `enforce_events` — a scan must "
                            "never gate a push or a pull request (issue #738)")
    workflow = WORKFLOW.read_text(encoding="utf-8") if WORKFLOW.is_file() else ""
    if not workflow:
        problems.append(f"{_display(WORKFLOW)} is missing: the pipeline this policy protects "
                        "cannot be checked")
    else:
        fired = triggers(workflow)
        for event in NEVER_GATING:
            if event in fired:
                problems.append(f"{_display(WORKFLOW)}: `{event}:` trigger must not exist — "
                                "the scan is its own daily pipeline (issue #738)")
    for key in ("fail_on", "issue_severities"):
        values = pol.get(key)
        if not values:
            problems.append(f"security-policy.json: `{key}` is empty")
            continue
        for severity in values:
            if str(severity).lower() not in known:
                problems.append(f"security-policy.json: `{severity}` in `{key}` is not a severity")
    for severity in pol.get("pr_fail_on") or []:
        if str(severity).lower() not in known:
            problems.append(f"security-policy.json: `{severity}` in `pr_fail_on` is not a severity")
    if set(map(str.lower, pol.get("pr_fail_on") or [])) - set(map(str.lower, pol.get("fail_on") or [])):
        problems.append("security-policy.json: `pr_fail_on` is not a subset of `fail_on`")
    recorded = digests()
    # Only the image-backed scanners carry a digest entry: the SBOM tool runs through the Grype
    # image (`--entrypoint syft`), so requiring an entry for it would demand an image that does
    # not exist — and a gate that cannot pass is not a gate.
    if "grype" in recorded and not SBOM_TOOL:
        problems.append("no SBOM tool: Grype would have nothing to match")
    for tool in TOOLS:
        entry = recorded.get(tool) or {}
        for key in ("version", "tag", "ref", "image_digest"):
            if not entry.get(key):
                problems.append(f"digests.json: `{tool}` has no `{key}` (issue #2609: the scan "
                                "cannot prove which image it runs without it)")
        if entry.get("image_digest") and not DIGEST_RE.fullmatch(str(entry["image_digest"])):
            problems.append(f"digests.json: `{tool}` image_digest is not `sha256:<64 hex>`")
        if entry.get("tag") and f":{entry['tag']}" not in image_ref(tool):
            problems.append(f"digests.json: `{tool}` tag is not the ref's tag")
    # The SAST rule set is immutability too (issue #1284): the rules a scan runs are pinned by sha in
    # the SAME digests.json that pins the binaries, and the pinned engine versions must not lag the
    # declared current-release baseline. `make check-security-scan` fails on either, so a scan that
    # is not reproducible (or that silently runs an old set) cannot be trusted.
    sem = recorded.get("semgrep") or {}
    if not sem.get("rules_sha"):
        problems.append("digests.json: `semgrep` has no `rules_sha` — the SAST rule set a scan "
                        "runs is not content-pinned (issue #1284)")
    pack = REPO / "containers" / "scanners" / "semgrep" / "rules" / "default.yml"
    if not pack.is_file():
        problems.append("containers/scanners/semgrep/rules/default.yml is missing — the scan "
                        "would run an uncommitted rule set (issue #1284)")
    elif sem.get("rules_sha") and hashlib.sha256(pack.read_bytes()).hexdigest() != sem["rules_sha"]:
        problems.append("digests.json: `semgrep.rules_sha` does not match the committed "
                        "containers/scanners/semgrep/rules/default.yml — run `make scanner-digests`")
    # The pack must also not silently age: `rules_captured_at`/`rules_count` record when the pack
    # was last resolved from upstream `p/default` (#2283). A pack older than the recency floor
    # reds here, so a frozen rule set cannot pass green while upstream adds rules it never sees.
    captured = sem.get("rules_captured_at")
    count = sem.get("rules_count")
    if not captured:
        problems.append("digests.json: `semgrep` has no `rules_captured_at` — the SAST rule set "
                        "has no recency floor (issue #2283)")
    else:
        try:
            captured_dt = _dt.date.fromisoformat(str(captured))
        except ValueError:
            problems.append(f"digests.json: `semgrep.rules_captured_at` {captured!r} is not an "
                            "ISO date (issue #2283)")
        else:
            age = (_dt.date.today() - captured_dt).days
            if age > RULES_BASELINE_DAYS:
                problems.append(f"digests.json: `semgrep.rules_captured_at` is {captured} — the "
                                f"committed semgrep rule pack is {age} days old, older than the "
                                f"declared recency baseline {RULES_BASELINE_DAYS} days — re-resolve "
                                "p/default and re-pin (issue #2283)")
    if not count:
        problems.append("digests.json: `semgrep` has no `rules_count` — the SAST rule set has no "
                        "parity target against upstream p/default (issue #2283)")
    for tool in TOOLS:
        baseline = scanner_baseline(tool)
        version = (recorded.get(tool) or {}).get("version")
        if baseline and version and _version_sort_key(version) < _version_sort_key(baseline):
            problems.append(f"digests.json: `{tool}` records {version!r}, older than the declared "
                            f"current-release baseline {baseline!r} — bump the Dockerfile and "
                            "`make scanner-digests` (issue #1284)")
    # The SBOM tool gets the same freshness floor (issue #2708): its version is baked into the
    # grype image and recorded as `grype.syft_version`. A lagging cataloger narrows SBOM coverage
    # invisibly — grype can only match what syft wrote — so the record is mandatory and the lag
    # reds here instead of narrowing the scan silently.
    if SBOM_TOOL and "grype" in recorded:
        grype_entry = recorded.get("grype") or {}
        syft_version = grype_entry.get("syft_version")
        syft_baseline = scanner_baseline(SBOM_TOOL)
        if not syft_version:
            problems.append(f"digests.json: `grype` has no `syft_version` — the SBOM tool "
                            f"`{SBOM_TOOL}` it bakes has no freshness record (issue #2708)")
        elif not syft_baseline:
            problems.append(f"SCANNER_BASELINE has no `{SBOM_TOOL}` entry — the SBOM tool has no "
                            "declared current-release baseline to check against (issue #2708)")
        elif _version_sort_key(syft_version) < _version_sort_key(syft_baseline):
            problems.append(f"digests.json: `grype.syft_version` records {syft_version!r}, older "
                            f"than the declared current-release baseline {syft_baseline!r} — bump "
                            "the grype Dockerfile's `ARG SYFT_VERSION` and `make scanner-digests` "
                            "(issue #2708)")
    # The published-image allow-list (issue #2706) must exist, carry a shape the resolver can use,
    # and be wired into BOTH lanes: the scheduled security lane and the engine publish cell. An
    # empty allow-list or a dropped step is the silent-skip this issue exists to prevent.
    manifest = {}
    if not SCANNED_IMAGES.is_file():
        problems.append("containers/scanned-images.json is missing — no published image would "
                        "ever be scanned (issue #2706)")
    else:
        try:
            manifest = json.loads(SCANNED_IMAGES.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"containers/scanned-images.json does not parse: {exc}")
        entries = manifest.get("images") or []
        if not entries:
            problems.append("containers/scanned-images.json: `images` is empty — the published-"
                            "image scan would scan nothing (issue #2706)")
        seen_slugs: set[str] = set()
        for entry in entries:
            slug = str(entry.get("name") or "")
            if not IMAGE_SLUG_RE.fullmatch(slug):
                problems.append(f"scanned-images.json: entry name {slug!r} is not a lowercase slug")
            elif slug in seen_slugs:
                problems.append(f"scanned-images.json: duplicate slug {slug!r} — two entries would "
                                "overwrite each other's reports")
            else:
                seen_slugs.add(slug)
            if entry.get("engine"):
                if not entry.get("variant"):
                    problems.append(f"scanned-images.json: engine entry {slug!r} has no `variant`")
                try:
                    _resolve_engine_ref(str(entry["engine"]), str(entry.get("variant") or ""))
                except SystemExit as exc:
                    problems.append(f"scanned-images.json: engine entry {slug!r} does not resolve "
                                    f"to a pinned image: {exc}")
            elif not entry.get("ref"):
                problems.append(f"scanned-images.json: entry {slug!r} has neither `engine`+`variant` "
                                "nor `ref`")
        fixture = manifest.get("fixture") or {}
        if not fixture.get("ref") or not fixture.get("name"):
            problems.append("scanned-images.json: `fixture` needs a `name` and a `ref` — the "
                            "known-vulnerable proof image must be declared (issue #2706)")
    if manifest.get("images") and "security-scan-images" not in workflow:
        problems.append(f"{_display(WORKFLOW)}: no `make security-scan-images` step — the lane "
                        "would never scan the published images the manifest allows (issue #2706)")
    engine_workflow = ENGINE_WORKFLOW.read_text(encoding="utf-8") if ENGINE_WORKFLOW.is_file() else ""
    if manifest.get("images") and "security-scan-published" not in engine_workflow:
        problems.append(f"{_display(ENGINE_WORKFLOW)}: no `make security-scan-published` step — a "
                        "published engine image would never be scanned at publish time (issue #2706)")
    if problems:
        print(f"[security-scan] {len(problems)} problem(s):")
        for item in problems:
            print(f"  - {item}")
        return 1
    print(f"[security-scan] OK: fail_on={pol['fail_on']} pr_fail_on={pol['pr_fail_on']} "
          f"enforce_events={sorted(enforce)} require_fix={pol.get('require_fix')}, "
          f"{len(TOOLS)} pinned scanner refs "
          f"(sweep: {', '.join(ALL_TOOLS)}; the SBOM tool rides the grype image; no secret needed; "
          f"the workflow triggers only on {', '.join(sorted(triggers(workflow))) or 'nothing'})")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command",
                    choices=("ref", "sbom", "scan", "all", "scan-images", "scan-image",
                             "scan-published", "scan-fixture", "verdict", "findings", "check",
                             "freshness"))
    ap.add_argument("tool", nargs="?", default="")
    ap.add_argument("--mode", default="", choices=("", "full", "pr"),
                    help="force a mode; empty resolves it from --event via `enforce_events`")
    ap.add_argument("--event", default="", help="the event the run is for (schedule|pull_request|push|…)")
    args = ap.parse_args(argv)
    if args.command == "ref":
        print(image_ref(args.tool))
        return 0
    if args.command == "scan":
        return scan(args.tool)
    if args.command == "scan-image":
        return scan_image(args.tool)
    if args.command == "scan-images":
        return scan_images_all()
    if args.command == "scan-published":
        engine, _, variant = args.tool.partition("/")
        if not variant:
            raise SystemExit("usage: scan-published <engine>/<variant>")
        return scan_published_image(engine, variant)
    if args.command == "scan-fixture":
        return scan_image_fixture()
    if args.command == "findings":
        print(json.dumps(findings(), indent=2))
        return 0
    if args.command == "verdict":
        return verdict(args.mode, args.event)
    if args.command == "freshness":
        return scanner_freshness()
    return {"sbom": sbom, "all": all_scans, "check": check}[args.command]()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
