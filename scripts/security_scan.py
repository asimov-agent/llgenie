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
import json
import os
import re
import subprocess
import sys
from pathlib import Path

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
#: Trivy covers OS/language vulnerabilities (and secrets/misconfigs when asked), Syft writes the
#: CycloneDX SBOM and Grype matches it, Semgrep covers SAST. Between them they answer "is anything in
#: this tree known-vulnerable" from data shipped/downloaded to the runner.
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


def ensure_image(tool: str) -> str:
    """The pinned image, from the registry when it is published, else built from its Dockerfile.

    A pull is the normal path. It fails for a `pull_request` run before the first publish (the
    `scanner-images` job publishes on a push to main only), and for a fork run, whose token cannot
    write the base repo's packages. That is not a reason to skip a scan, and it is not a second
    implementation: the SAME Dockerfile — digest-pinned base, exact versions — is built and tagged
    with the SAME immutable ref the workflow asked for, and the log says which path was taken.
    """
    ref = image_ref(tool)
    if subprocess.run([RUNTIME, "image", "inspect", ref],
                      capture_output=True).returncode == 0:
        return ref
    pull = subprocess.run([RUNTIME, "pull", ref], capture_output=True, text=True)
    if pull.returncode == 0:
        print(f"[security-scan] pulled {ref}")
        return ref
    context = REPO / "containers" / "scanners" / tool
    print(f"[security-scan] {ref} is not published yet — building {context} (the same Dockerfile "
          "the publish job builds) and tagging it with the ref the scan asked for")
    build = subprocess.run([RUNTIME, "build", "-t", ref, str(context)],
                           capture_output=True, text=True)
    if build.returncode != 0:
        raise SystemExit(f"[security-scan] cannot build {tool}: {build.stderr.strip()[-400:]}")
    return ref


def _run(argv: list[str], image: str, entrypoint: str | None = None) -> int:
    """Run one scanner from its image, with the checkout mounted so it writes its reports."""
    REPORTS.mkdir(parents=True, exist_ok=True)
    # The image's own USER is a non-root one, but the mounted checkout belongs to the RUNNER user:
    # without `--user` the scanner cannot create its report ("permission denied") and would leave
    # root-owned files in the worktree (issue #433). Running as the invoking user fixes both.
    extra = ["--entrypoint", entrypoint] if entrypoint else []
    cmd = [RUNTIME, "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}", *extra,
           "-v", f"{REPO}:/work:rw", "-w", "/work",
           "-e", "HOME=/tmp", ensure_image_for(image), *argv]
    print(f"[security-scan] $ {' '.join(cmd)}")
    return subprocess.run(cmd).returncode


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
        base = ["fs", "--severity", "CRITICAL,HIGH,MEDIUM", "--scanners", "vuln,secret"]
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
        # An EXPLICIT registry pack, not `--config auto`: Semgrep refuses `auto` when metrics are
        # off ("Cannot create auto config when metrics are off"), and sending telemetry from CI is
        # not something this run should require. `p/default` is the curated ruleset and needs no
        # per-run decision (measured on the 4th CI run of this job).
        return _run(["scan", "--config=p/default", "--json", "--output",
                     "/work/security-reports/semgrep.json", "--metrics", "off", "."], image_ref(tool))
    raise SystemExit(f"[security-scan] unknown tool `{tool}`; known: {', '.join(ALL_TOOLS)}")


def all_scans() -> int:
    """Syft first (Grype matches exactly that SBOM), then the CVE scanners."""
    rc = sbom()
    for tool in TOOLS:
        rc = scan(tool) or rc
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


def _grype_findings(report: dict) -> list[dict]:
    return [{
        "id": (match.get("vulnerability") or {}).get("id"),
        "package": (match.get("artifact") or {}).get("name"),
        "current": (match.get("artifact") or {}).get("version"),
        "fixed": ", ".join((match.get("fix") or {}).get("versions") or []),
        "severity": str((match.get("vulnerability") or {}).get("severity", "")).lower(),
        "source": "grype",
    } for match in report.get("matches") or []]


def findings(reports: Path | None = None) -> list[dict]:
    """Every finding from every report that exists, in one shape."""
    reports = reports or REPORTS  # resolved at call time: `SECURITY_REPORTS`/a test can move it
    out: list[dict] = []
    for name, reader in (("trivy.json", _trivy_findings),
                         ("trivy.json", _trivy_secret_findings),
                         ("grype.json", _grype_findings)):
        path = reports / name
        if not path.is_file():
            continue
        try:
            out.extend(reader(json.loads(path.read_text(encoding="utf-8"))))
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
        if item.get("source") == SECRET_SOURCE:
            # A committed credential is ALWAYS actionable: its remediation is removal and rotation,
            # not "await a patched version", so `require_fix` — which exists to stop an unfixable
            # advisory from stalling the pipeline — must not suppress it. `fail_on` still gates: a
            # `medium`/`unknown` secret is recorded, never a red (issue #1283).
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
        for key in ("version", "tag", "ref"):
            if not entry.get(key):
                problems.append(f"digests.json: `{tool}` has no `{key}`")
        if entry.get("tag") and f":{entry['tag']}" not in image_ref(tool):
            problems.append(f"digests.json: `{tool}` tag is not the ref's tag")
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
                    choices=("ref", "sbom", "scan", "all", "verdict", "findings", "check"))
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
    if args.command == "findings":
        print(json.dumps(findings(), indent=2))
        return 0
    if args.command == "verdict":
        return verdict(args.mode, args.event)
    return {"sbom": sbom, "all": all_scans, "check": check}[args.command]()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
