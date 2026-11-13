#!/usr/bin/env python3
"""One immutable image per scanner (issue #714, parent #713).

A scanner installed at scan time is a mutable tool on a mutable base, with network access during
the scan. Each scanner therefore ships as its own image, built only by this repository from
`containers/scanners/<id>/Dockerfile`, whose base is pinned by DIGEST and whose scanner is pinned to
EXACT versions. The published tag is a hash of the Dockerfile, so `<registry>/llgenie/<id>:<hash>`
names one build of one file — the same convention `scripts/ci_images.py` uses for `llgenie/test`.

Commands (driven by make, never by hand):

    digest <id>     print the Dockerfile's content hash (the immutable tag)   make scanner-digests
    ref <id>        print the published ref                                   make scanner-ref
    build <id>      build the image from its Dockerfile                       make scanner-image
    test <id>       build + run the image's version command and compare it with the pin
                                                                              make test-scanner-image
    publish <id>    build linux/amd64 + linux/arm64 and push the hash tag     make publish-scanner-images
    write           rewrite containers/scanners/digests.json from the files   make scanner-digests
    check <id>|all  fail when a Dockerfile floats, or when digests.json is stale
                                                                              make check-scanner-images
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

try:  # the subprocess policy seam (issue #797)
    from .proc import run_ok  # type: ignore
except ImportError:  # pragma: no cover - script mode
    from proc import run_ok  # type: ignore

REPO = Path(__file__).resolve().parent.parent
RUNTIME = os.environ.get("RUNTIME") or "docker"
DEFAULT_REGISTRY = "ghcr.io/asimov-agent"
PLATFORMS = "linux/amd64,linux/arm64"
SCANNER_DIR = "containers/scanners"
DIGESTS = f"{SCANNER_DIR}/digests.json"
#: id -> the ARG that pins the scanner, and the command whose output carries the version.
SCANNERS: dict[str, dict[str, str]] = {
    "trivy": {"arg": "TRIVY_VERSION", "cmd": "version"},
    "grype": {"arg": "GRYPE_VERSION", "cmd": "version"},
    "semgrep": {"arg": "SEMGREP_VERSION", "cmd": "--version"},
}
#: A base image must be pinned by digest: `FROM image@sha256:<64 hex>`.
FROM_DIGEST = re.compile(r"^FROM\s+(\S+)@sha256:([0-9a-f]{64})\s*$", re.M)
#: A floating base: a `FROM` with a tag but no digest (the digest form is matched above, so a
#: lazy `\S+?` plus the negative lookahead keeps `image@sha256:<hex>` out of this rule).
FROM_FLOAT = re.compile(r"^FROM\s+(?!\S*@sha256:)(\S+?):(\w[\w.-]*)\s*$", re.M)
#: The declared current-release baseline per scanner (issue #1284): the newest version the Linux
#: apk repo publishes for the scanner's `apk add` — the honest "current" the Dockerfile can reach.
#: `make check-scanner-images` (and check-security-scan) fail when digests.json records an older
#: one, so a pinned engine cannot silently lag the releases it should cover. Measured against
#: packages.wolfi.dev (x86_64 APKINDEX) on 2026-11-07; bump with the Dockerfile via
#: `make scanner-digests` + PR whenever apk publishes a newer build.
RELEASE_BASELINE: dict[str, str] = {
    "semgrep": "1.165.0-r0",
    "trivy": "0.70.0-r5",
    "grype": "0.121.2-r1",
}


def _older(version: str, baseline: str) -> bool:
    """True when `version` sorts older than `baseline` (both `X.Y.Z[-rN]` apk build strings)."""

    def key(v: str) -> tuple:
        nums, _, rev = v.partition("-")
        return (tuple(int(x) for x in re.split(r"[+.~]", nums) if x.isdigit()),
                int(rev.lstrip("r").partition("_")[0] or 0))

    return key(version) < key(baseline)


def registry() -> str:
    return os.environ.get("LLGENIE_REGISTRY", DEFAULT_REGISTRY).rstrip("/").lower()


def dockerfile(scanner: str) -> Path:
    path = REPO / SCANNER_DIR / scanner / "Dockerfile"
    if not path.is_file():
        raise SystemExit(f"[scanner-image] no Dockerfile for scanner `{scanner}` ({path})")
    return path


def pinned_version(scanner: str) -> str:
    """The exact version the Dockerfile pins (no range, no `latest`)."""
    arg = SCANNERS[scanner]["arg"]
    text = dockerfile(scanner).read_text(encoding="utf-8")
    m = re.search(rf"^ARG\s+{arg}=(\S+)\s*$", text, re.M)
    if not m:
        raise SystemExit(f"[scanner-image] {scanner}: no `ARG {arg}=<version>` pin")
    return m.group(1)


def content_hash(scanner: str) -> str:
    """A tag that names one build of one Dockerfile — the immutability the scans rely on."""
    return hashlib.sha256(dockerfile(scanner).read_bytes()).hexdigest()[:12]


def ref(scanner: str) -> str:
    return f"{registry()}/llgenie/{scanner}:{content_hash(scanner)}"


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    print(f"[scanner-image] $ {' '.join(cmd)}")
    # policy: run_ok — the caller inspects rc (issue #797, scripts/proc.py is the one seam).
    return run_ok(cmd, **kw)


# How many stream lines a failure prints (issue #2452 criterion 4): a bounded tail,
# never the discarded-entirety of the old `publish failed: <scanner>` one-liner.
FAILURE_TAIL_LINES = 25


def _report_failure(scanner: str, res: subprocess.CompletedProcess, action: str) -> None:
    """A failed command prints its exit code and a tail of what it actually said.
    The streams were already captured by `run_ok`; the defect was discarding them."""
    print(f"[scanner-image] {action} failed: {scanner} (exit {res.returncode})")
    lines = [ln for ln in f"{res.stdout or ''}\n{res.stderr or ''}".splitlines() if ln.strip()]
    for line in lines[-FAILURE_TAIL_LINES:]:
        print(f"[scanner-image] | {line}")


def _published_platforms(ref: str) -> set[str]:
    """Which platforms the registry ALREADY carries for this ref (issue #2453).

    `docker buildx imagetools inspect` needs no build and no layer pull; a tag the
    registry does not have exits non-zero, which `run_ok` returns as a value. That is
    a question about the registry, not a failure of the leg: rc != 0 is an empty
    answer — never an exception, never a red.
    """
    res = _run([RUNTIME, "buildx", "imagetools", "inspect", ref])
    if res.returncode != 0:
        return set()
    text = f"{res.stdout or ''}\n{res.stderr or ''}"
    return set(re.findall(r"Platform:\s*(linux/\S+)", text))


def _published_digest(scanner: str) -> str:
    """The index digest the scanner's ref currently resolves to in the registry (issue #2609).

    `make scanner-digests` records it beside the ref so a scan can verify the image it is about to
    run (`scripts/security_scan.py::verify_digest`). The measurement is the same one CI publishes:
    `docker buildx imagetools inspect <ref>` names the index `Digest:`. A tag the registry has not
    yet published exits non-zero → empty string (a first import has no published digest yet, which
    is a scan-time refusal, not a write-time one).
    """
    res = _run([RUNTIME, "buildx", "imagetools", "inspect", ref(scanner)])
    if res.returncode != 0:
        return ""
    m = re.search(r"^Digest:\s+(sha256:[0-9a-f]{64})\s*$",
                  f"{res.stdout or ''}\n{res.stderr or ''}", re.M)
    return m.group(1) if m else ""


def build(scanner: str, tag: str | None = None) -> str:
    tag = tag or f"llgenie/scanner-{scanner}:{content_hash(scanner)}"
    res = _run([RUNTIME, "build", "-t", tag, str(dockerfile(scanner).parent)])
    if res.returncode != 0:
        _report_failure(scanner, res, "build")
        raise SystemExit(f"[scanner-image] build failed: {scanner}")
    return tag


def version_line(scanner: str, image: str) -> str:
    """Run the image's version command and return everything it printed."""
    res = subprocess.run([RUNTIME, "run", "--rm", image, SCANNERS[scanner]["cmd"]],  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
                         capture_output=True, text=True)
    out = (res.stdout + res.stderr).strip()
    if res.returncode != 0:
        raise SystemExit(f"[scanner-image] {scanner}: version command failed: {out}")
    return out


def test(scanner: str) -> int:
    """Build, then prove the binary answers with the pinned version."""
    image = build(scanner)
    pin = pinned_version(scanner)
    out = version_line(scanner, image)
    numeric = pin.split("-")[0]  # apk revision suffix (-r5) is not part of the upstream version
    if numeric not in out:
        raise SystemExit(f"[scanner-image] {scanner}: expected version {numeric}, got: {out}")
    print(f"[scanner-image] OK {scanner} {numeric} ({image})")
    return 0


def publish(scanner: str) -> int:
    """Publish the content-hash tag, unless the registry already carries it.

    GHCR cannot hold a multi-arch image as a plain `docker build -t …` + push, so
    this leg uses `docker buildx build --platform … --push` like the engine legs.

    A content-hash tag is immutable, so the registry is asked FIRST (issue #2453):
    when it already carries every platform in `PLATFORMS`, the re-push is skipped —
    a transient multi-arch failure on an artifact that already exists must not red
    main (measured: run 42755279061 reds main re-pushing the tag run 42751641578
    published 40 minutes earlier). A tag absent, or present without a required
    platform, publishes exactly as before; the skip never suppresses a real publish.
    """
    target = ref(scanner)
    wanted = {p.strip() for p in PLATFORMS.split(",") if p.strip()}
    already = _published_platforms(target)
    if wanted and wanted <= already:
        print(f"[scanner-image] already published ({', '.join(sorted(wanted))}), "
              f"skipping re-push: {target}")
        return 0
    res = _run([RUNTIME, "buildx", "build", "--platform", PLATFORMS, "--push",
                "-t", target, str(dockerfile(scanner).parent)])
    if res.returncode != 0:
        _report_failure(scanner, res, "publish")
        raise SystemExit(f"[scanner-image] publish failed: {scanner}")
    print(f"[scanner-image] published {target}")
    return 0


def write() -> int:
    """Rewrite digests.json: the version pin and the immutable tag per scanner, plus the
    content-addressed sha256 of the semgrep rules pack a scan actually runs (issue #1284). Each
    scanner also records the index `digest` of the image CI publishes (issue #2609) so the file
    regenerates with its immutability proof, not without it."""
    semgrep_pack = REPO / SCANNER_DIR / "semgrep" / "rules" / "default.yml"
    rules_sha = ""
    if semgrep_pack.is_file():
        rules_sha = hashlib.sha256(semgrep_pack.read_bytes()).hexdigest()
    digest = _published_digest
    data = {
        scanner: {
            "version": pinned_version(scanner),
            "tag": content_hash(scanner),
            "ref": ref(scanner),
            "digest": digest(scanner),
            "dockerfile": f"{SCANNER_DIR}/{scanner}/Dockerfile",
        }
        for scanner in SCANNERS
    }
    if rules_sha:
        data["semgrep"]["rules_sha"] = rules_sha
        data["semgrep"]["rules_file"] = f"{SCANNER_DIR}/semgrep/rules/default.yml"
        data["semgrep"]["rules_captured_at"] = _dt.date.today().isoformat()
        data["semgrep"]["rules_count"] = str(sum(
            1 for line in semgrep_pack.read_text(encoding="utf-8").splitlines()
            if line.startswith("- id: ")))
    path = REPO / DIGESTS
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[scanner-image] wrote {DIGESTS} ({len(data)} scanners"
          + (f"; semgrep rules {rules_sha[:12]}" if rules_sha else "; NO semgrep rules pack!") + ")")
    if "semgrep" in data and not rules_sha:
        raise SystemExit("[scanner-image] no committed semgrep rules pack — "
                         f"{SCANNER_DIR}/semgrep/rules/default.yml is required (issue #1284)")
    return 0


def check(scanner: str = "all") -> int:
    """Fail when a Dockerfile floats, digests.json disagrees with the files, the semgrep rules pack
    is absent or its recorded sha is wrong (issue #1284), or a scanner *_VERSION is older than the
    declared current-release baseline (issue #1284)."""
    problems: list[str] = []
    ids = list(SCANNERS) if scanner == "all" else [scanner]
    semgrep_pack = REPO / SCANNER_DIR / "semgrep" / "rules" / "default.yml"
    for sid in ids:
        text = dockerfile(sid).read_text(encoding="utf-8")
        if not FROM_DIGEST.search(text):
            problems.append(f"{sid}: base image is not pinned by digest (`FROM image@sha256:<64 hex>`)")
        for image, tag in FROM_FLOAT.findall(text):
            problems.append(f"{sid}: floating base `{image}:{tag}` — pin it by digest")
        if "latest" in re.sub(r"#.*", "", text):
            problems.append(f"{sid}: the Dockerfile names `latest`")
    path = REPO / DIGESTS
    if not path.is_file():
        problems.append(f"{DIGESTS} is missing — run `make scanner-digests`")
    else:
        recorded = json.loads(path.read_text(encoding="utf-8"))
        for sid in SCANNERS:
            entry = recorded.get(sid)
            if not entry:
                problems.append(f"{DIGESTS} does not name `{sid}`")
                continue
            if entry.get("version") != pinned_version(sid):
                problems.append(f"{sid}: digests.json records version {entry.get('version')!r}, "
                                f"the Dockerfile pins {pinned_version(sid)!r}")
            if entry.get("tag") != content_hash(sid):
                problems.append(f"{sid}: digests.json records tag {entry.get('tag')!r}, "
                                f"the Dockerfile hashes to {content_hash(sid)!r}")
            if not (entry.get("ref") or "").endswith(f"/{sid}:{content_hash(sid)}"):
                problems.append(f"{sid}: digests.json ref does not end with the content-hash tag")
            if not entry.get("digest"):
                problems.append(f"{sid}: digests.json omits `digest` — the image's index digest is "
                                "required beside the ref (issue #2609)")
            elif not re.fullmatch(r"sha256:[0-9a-f]{64}", entry["digest"]):
                problems.append(f"{sid}: digests.json digest {entry['digest']!r} is not a "
                                "`sha256:<64 hex>` index digest (issue #2609)")
            # A scanner version older than the declared current-release baseline is a freshness
            # finding (issue #1284): the engines must advance through `make scanner-digests` + PR.
            baseline = RELEASE_BASELINE.get(sid)
            if baseline and entry.get("version") and _older(entry["version"], baseline):
                problems.append(f"{sid}: digests.json records {entry['version']!r}, older than the "
                                f"declared current-release baseline {baseline!r} — bump the Dockerfile "
                                "and `make scanner-digests`")
        sem = recorded.get("semgrep")
        if sem:
            if not sem.get("rules_sha"):
                problems.append("semgrep: digests.json omits `rules_sha` — the rule set a scan runs "
                                "is not content-pinned (issue #1284)")
            if not semgrep_pack.is_file():
                problems.append("semgrep: containers/scanners/semgrep/rules/default.yml is missing — "
                                "the scan would run an uncommitted rule set (issue #1284)")
            elif sem.get("rules_sha") and hashlib.sha256(semgrep_pack.read_bytes()).hexdigest() != sem["rules_sha"]:
                problems.append("semgrep: digests.json `rules_sha` does not match the committed "
                                "containers/scanners/semgrep/rules/default.yml — run "
                                "`make scanner-digests`")
    if problems:
        print(f"[scanner-image] {len(problems)} problem(s):")
        for item in problems:
            print(f"  - {item}")
        return 1
    print(f"[scanner-image] OK: {len(ids)} scanner image(s) pinned by digest, exact version, and "
          "matching digests.json (semgrep rules pack content-pinned)")
    return 0


def ci() -> int:
    """Every scanner: build + prove its version. Publish only on a push (never a PR run).

    The policy lives here, not in a workflow `if:` — a scenario-scoped condition in YAML is how a
    publish silently stops happening (AGENTS.md).
    """
    published = os.environ.get("GITHUB_EVENT_NAME", "workflow_dispatch") != "pull_request"
    for sid in SCANNERS:
        test(sid)
        if published:
            publish(sid)
        else:
            print(f"[scanner-image] build+test only for {sid} (a pull_request run does not publish)")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=("digest", "ref", "build", "test", "publish", "write", "check", "ci"))
    ap.add_argument("scanner", nargs="?", default="all")
    args = ap.parse_args(argv)
    sid = args.scanner
    if args.command in ("digest", "ref", "build", "test", "publish") and sid not in SCANNERS:
        raise SystemExit(f"[scanner-image] unknown scanner `{sid}`; known: {', '.join(SCANNERS)}")
    if args.command == "digest":
        print(content_hash(sid))
        return 0
    if args.command == "ref":
        print(ref(sid))
        return 0
    return {"build": lambda: 0 if build(sid) else 0, "test": lambda: test(sid),
            "publish": lambda: publish(sid), "write": write,
            "check": lambda: check(sid), "ci": ci}[args.command]()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
