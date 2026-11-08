#!/usr/bin/env python3
"""Findings become TAGGED issues, idempotently (issue #716, parent #713).

A scan that only writes SARIF leaves the work invisible: nobody is assigned it, nothing survives in
the tracker, and the remediation bot (#717) has nothing to read. This module turns the reports
`make security-scan-all` writes into one issue per (advisory, package) — never one per scan run.

The lookup key is an HTML comment marker in the body, so the lookup needs no local state:

    <!-- security-finding: trivy:CVE-2024-1234:numpy -->

Re-running against the same reports **updates** that issue (last-seen, current → fixed, the run
link) and never opens a duplicate; a finding that is no longer reported is commented with the run
that cleared it and closed. Nothing is closed while a remediation PR is open (the bot comments on
it instead — #717 owns that half).

Commands (driven by make, never by hand):

    plan    print what would be created / updated / cleared, mutating nothing   make security-issues DRY=1
    apply   do it through `gh`                                                  make security-issues
    check   the label roster + the policy are sane                              make check-security-issues

`--repo` defaults to `$GITHUB_REPOSITORY`; `--reports` defaults to `security-reports`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import issue_body  # noqa: E402
import security_scan as ss  # noqa: E402
from proc import run_ok  # noqa: E402  the subprocess policy seam (issue #797)

REPORTS = Path(os.environ.get("SECURITY_REPORTS") or (REPO / "security-reports"))
MARKER = "<!-- security-finding: {source}:{advisory}:{package} -->"
MARKER_RE = re.compile(r"<!--\s*security-finding:\s*([^:\s]+):([^:\s]+):([^>\s]+)\s*-->")
#: The acceptance line that turns an issue's close into an evidence round-trip. The security loop
#: only closes an issue by posting this clearing comment on a genuine completed scan (issue #1693):
#: a merged-PR bare `closes #N` closes the issue by reference WITHOUT that evidence, and Git's
#: merge-close must never be treated as satisfying a scan-evidence acceptance box.
SCAN_EVIDENCE_ACCEPTANCE = "the next scan closes this issue with the run that cleared it"
#: The comment the pipeline's own clear loop posts. Its ABSENCE on a closed scan-evidence issue is
#: the distinguishing signal that the issue was closed by a merged PR's reference, not by a scan.
CLEAR_COMMENT = "No longer reported by the latest scan"
#: The labels every issue carries, and the colour/description each is created with.
LABELS: dict[str, tuple[str, str]] = {
    "security": ("b60205", "A vulnerability or a supply-chain finding"),
    "vulnerability": ("d93f0b", "An advisory with a known fix or a tracked exposure"),
    "severity:critical": ("b60205", "Scanner severity: critical"),
    "severity:high": ("e99695", "Scanner severity: high"),
    "severity:medium": ("fbca04", "Scanner severity: medium"),
    "component:python": ("1d76db", "A Python dependency (requirements*.in / tools/)"),
    "component:container": ("5319e7", "A container image or a Dockerfile base"),
    "component:code": ("0e8a16", "Application code, SAST or IaC (a file rule, not a dependency pin)"),
    "auto-fixable": ("0e8a16", "The scanner names a fixed version the bot can apply"),
}


@dataclass
class Finding:
    """One advisory about one component, as the tracker sees it."""

    advisory: str
    package: str
    current: str
    fixed: str
    severity: str
    source: str
    component: str = ""
    labels: list[str] = field(default_factory=list)

    @property
    def marker(self) -> str:
        return MARKER.format(source=self.source, advisory=self.advisory, package=self.package)

    @property
    def key(self) -> str:
        return f"{self.source}:{self.advisory}:{self.package}"

    @property
    def title(self) -> str:
        return f"security({self.severity}): {self.advisory} in {self.package} ({self.source})"


def component_of(package: str, source: str) -> str:
    """Which component a finding belongs to — the label a reviewer filters on.

    SAST findings are code by definition. A package named in the container images is a container
    one; anything else the Python scanners report is a Python dependency.
    """
    if source not in ("trivy", "grype"):
        # anything that is not a CVE scanner over packages is a rule over source
        return "component:code"
    container_markers = ("openssl", "libc", "wolfi", "debian", "ubuntu", "libssl", "zlib", "glibc")
    if any(marker in package.lower() for marker in container_markers):
        return "component:container"
    return "component:python"


def labels_for(severity: str, component: str, fixable: bool) -> list[str]:
    labels = ["security", "vulnerability", f"severity:{severity}", component]
    if fixable:
        labels.append("auto-fixable")
    return labels


def issue_findings(reports: Path = REPORTS, policy: dict | None = None) -> list[Finding]:
    """Every finding that must become an issue: severity in `issue_severities`, fix when required."""
    pol = policy or ss.policy()
    wanted = {str(s).lower() for s in pol.get("issue_severities") or ["critical", "high"]}
    out: list[Finding] = []
    seen: set[str] = set()
    for item in ss.findings(reports):
        if item["severity"] not in wanted:
            continue
        # A committed credential, a SAST finding and an IaC misconfiguration are always actionable
        # (a secret's fix is removal and rotation; a semgrep finding's is editing the matched code; a
        # misconfig finding's is editing the matched IaC), so `require_fix` must not suppress them
        # from the tracker either (issues #1283, #1554, #2234).
        if (pol.get("require_fix") and not item["fixed"]
                and item.get("source") not in (ss.SECRET_SOURCE, ss.SEMGREP_SOURCE,
                                               ss.MISCONFIG_SOURCE)):
            continue
        advisory = item.get("id") or "unknown"
        package = item.get("package") or "unknown"
        finding = Finding(
            advisory=str(advisory), package=str(package), current=str(item.get("current") or ""),
            fixed=str(item.get("fixed") or ""), severity=item["severity"], source=item["source"],
        )
        finding.component = component_of(finding.package, finding.source)
        finding.labels = labels_for(finding.severity, finding.component, bool(finding.fixed))
        if finding.key in seen:  # one issue per (advisory, package), even across scanners
            continue
        seen.add(finding.key)
        out.append(finding)
    return sorted(out, key=lambda f: (f.severity, f.advisory, f.package))


def _technical(finding: Finding, run_url: str) -> list[str]:
    """The `## Technical` section — shared verbatim by both body shapes.

    The marker, advisory id, severity, component and run link are the reader's traceability to the
    scan, so they are identical whether the finding is a code defect or a package advisory: the body
    prose is presentation, the idempotency key and the scan provenance are the memory (issue #1560).
    """
    return [
        f"**Advisory:** `{finding.advisory}` — scanner: `{finding.source}`",
        f"**Affected package:** `{finding.package}`",
        f"**Current → fixed:** `{finding.current}` → `{finding.fixed or '(none named)'}`",
        f"**Severity:** `{finding.severity}`",
        f"**Component:** `{finding.component}`",
        f"**Scan run:** {run_url or '(local `make security-scan-all`)'}",
        "**Idempotency:** the marker on line 1 is the lookup key — `make security-issues` "
        "updates this issue on the next scan, never files a second one for the same "
        "(advisory, package).",
    ]


def _code_body(finding: Finding, run_url: str) -> str:
    """The body for a `component:code` finding (SAST or committed secret) — edit-the-code.

    A code finding has no `fixed` version: its remediation is editing the matched source, never a
    bump in `requirements*.txt`. The `## How we fix it` and `## Acceptance criteria` therefore tell
    the reader the present-tense action that clears it — fix the matched region, commit, let the next
    scan confirm — and never name the generated requirements pin path the CVE template uses.
    """
    return issue_body.render(
        marker=finding.marker,
        problem=(
            f"`{finding.source}` reports `{finding.advisory}` against the matched region "
            f"`{finding.current}` in `{finding.package}`, which this repository ships as a "
            f"{finding.component} finding. Severity: {finding.severity}."
        ),
        why=(
            "The defect is in source code this repository ships, so every build carries it and the "
            "scan re-reports it on every run until the matched code is edited — no package pin "
            "exists that can make it go away by itself."
        ),
        how=[
            f"Edit the matched region in `{finding.package}` so it no longer triggers "
            f"`{finding.advisory}` — fix the code, never try to pin a dependency: a "
            "`component:code` finding lives in a file, not in a dependency pin.",
            "Commit the source fix and let the pipeline re-scan: the next run of the security "
            "pipeline reports whether the matched region still triggers the rule.",
            "Close the loop without a human: when no scanner reports this finding any more, the "
            "next run comments the run that cleared it and closes this issue.",
        ],
        benefit=(
            f"A shipped source defect stops existing at `{finding.severity}` severity, the scan "
            "that reported it has a run it can point at as the clearing run, and the work is "
            "tracked in the issue the remediation path closes instead of in a SARIF file nobody "
            "reads."
        ),
        acceptance=[
            f"`{finding.package}` no longer matches the rule — the matched region is fixed in "
            "source",
            f"`make security-scan TOOL={finding.source}` no longer reports `{finding.advisory}` for "
            f"`{finding.package}`",
            "the next scan closes this issue with the run that cleared it",
        ],
        technical=_technical(finding, run_url),
        not_covered=[
            "Other occurrences of the same rule in other files are separate findings: each gets its "
            "own issue with its own advisory id.",
            "A scanner that could not run (its report is absent) is not a clean result for this "
            "file: `make security-verdict` refuses instead of passing.",
        ],
    )


def body_for(finding: Finding, run_url: str = "") -> str:
    """The issue body: the shape every issue in this repository carries (issue #745).

    The marker stays the first line (`MARKER_RE` reads it back, so a re-scan updates this issue
    instead of opening a duplicate); the advisory detail lives in `## Technical`, where a reviewer
    verifies it, and the four readable sections say what is wrong and what fixing it buys.

    The remediation narrative branches on the finding's component (issue #1560): a `component:code`
    finding (a SAST or committed-secret finding) gets the *edit-the-code* body — the matched source is
    the defect and fixing it is the action; every other finding keeps the *bump-the-pin* template.
    The branch reuses `component_of` (source not in the CVE scanners' vocabulary) so the body matches
    the component label and the verdict's `require_fix` classification.
    """
    if finding.component == "component:code":
        return _code_body(finding, run_url)
    return issue_body.render(
        marker=finding.marker,
        problem=(
            f"`{finding.source}` reports `{finding.advisory}` against `{finding.package}` "
            f"`{finding.current}`, which this repository ships as a {finding.component} dependency. "
            f"Severity: {finding.severity}."
        ),
        why=(
            "The advisory is in a version this repository actually ships, so every build carries a "
            "known-vulnerable dependency and the scan re-reports it on every run until the pin "
            "moves. Nothing in the product can make it go away by itself."
        ),
        how=[
            f"Move `{finding.package}` from `{finding.current}` to "
            f"`{finding.fixed or '(no fixed version named)'}` — or drop the dependency — through the "
            "generated `tools/requirements*.in` -> `requirements*.txt` path, never by editing a "
            "compiled file.",
            "Let the pipeline re-scan: the next run of the security pipeline reports whether the "
            "advisory is gone.",
            "Close the loop without a human: when no scanner reports this advisory any more, the "
            "next run comments the run that cleared it and closes this issue.",
        ],
        benefit=(
            f"A shipped dependency stops being known-vulnerable at `{finding.severity}` severity, "
            "the scan that reported it has a run it can point at as the clearing run, and the work "
            "is tracked in the issue the remediation path closes instead of in a SARIF file nobody "
            "reads."
        ),
        acceptance=[
            f"`{finding.package}` is pinned at `{finding.fixed or '(no fixed version named)'}` or "
            "later in the compiled `requirements*.txt`",
            f"`make security-scan TOOL={finding.source}` no longer reports `{finding.advisory}` for "
            f"`{finding.package}`",
            "the next scan closes this issue with the run that cleared it",
        ],
        technical=_technical(finding, run_url),
        not_covered=[
            "Transitive dependencies this advisory pulls in are separate findings: each gets its own "
            "issue with its own advisory id.",
            "A scanner that could not run (its report is absent) is not a clean result for this "
            "package: `make security-verdict` refuses instead of passing.",
        ],
    )


def _gh(args: list[str], repo: str) -> subprocess.CompletedProcess:
    cmd = ["gh", *args, "--repo", repo]
    print(f"[security-issues] $ {' '.join(cmd)}")
    # policy: run_ok — the caller inspects rc (issue #797, scripts/proc.py is the one seam).
    return run_ok(cmd)


def _gh_api(args: list[str]) -> subprocess.CompletedProcess:
    """`gh api` takes no `--repo` — the full path is the repository, so this runs bare."""
    cmd = ["gh", "api", *args]
    print(f"[security-issues] $ {' '.join(cmd)}")
    # policy: run_ok — the caller inspects rc (issue #797, scripts/proc.py is the one seam).
    return run_ok(cmd)


def labels_of(repo: str, number: int) -> set[str]:
    """The labels the issue ACTUALLY carries, read back from the tracker."""
    res = _gh_api([f"repos/{repo}/issues/{number}/labels", "--jq", ".[].name"])
    if res.returncode != 0:
        raise SystemExit(f"[security-issues] cannot read the labels of #{number}: "
                         f"{res.stderr.strip()}")
    return {name.strip() for line in (res.stdout or "").splitlines()
            for name in line.split(",") if name.strip()}


def set_labels(repo: str, number: int, labels: list[str]) -> None:
    """Label the issue explicitly and PROVE it stuck.

    `gh issue create --label <name>` is silently dropped on the runner path (measured: the
    registry-sync change issues, #724; then again on the four security issues this pipeline filed
    from run 40693161435, #781-#784 — every one of them arrived with zero labels). An issue that
    exists but carries no label is invisible to `security_bot.pick`, which selects on labels, so
    the finding is filed where nobody looks. Two writes (create flag dropped, then this POST) and a
    read-back that FAILS the step instead of warning.
    """
    args = ["-X", "POST", f"repos/{repo}/issues/{number}/labels"]
    for label in labels:
        args += ["-f", f"labels[]={label}"]
    res = _gh_api(args)
    if res.returncode != 0:
        raise SystemExit(f"[security-issues] could not label #{number}: {res.stderr.strip()}")
    have = labels_of(repo, number)
    missing = [label for label in labels if label not in have]
    if missing:
        raise SystemExit(
            f"[security-issues] #{number} is missing {', '.join(missing)} after the label write — "
            "an unlabelled security issue is invisible to the bot that fixes it, so the step fails")
    print(f"[security-issues] labelled #{number}: {', '.join(labels)}")


def existing_issues(repo: str, label: str = "security") -> dict[str, dict]:
    """`{marker key: {number, body, labels}}` for every open security issue."""
    res = _gh(["issue", "list", "--label", label, "--state", "open", "--limit", "200",
               "--json", "number,body,labels,title"], repo)
    if res.returncode != 0:
        raise SystemExit(f"[security-issues] cannot list issues: {res.stderr.strip()}")
    out: dict[str, dict] = {}
    for issue in json.loads(res.stdout or "[]"):
        m = MARKER_RE.search(issue.get("body") or "")
        if m:
            out[f"{m.group(1)}:{m.group(2)}:{m.group(3)}"] = issue
    return out


def _closed_scan_evidence(repo: str) -> list[dict]:
    """CLOSED security issues whose acceptance is a scan-evidence round-trip.

    `apply` only ever reconciles open issues (`existing_issues` filters `--state open`), so an
    issue a merged PR's bare `closes #N` auto-closed disappears from the tracker — and comes back
    as a DUPLICATE on the next scan while the finding persists, or closes silently without the run
    id/sha evidence comment when it has gone. This reads the live tracker (never a blob or a grep)
    for exactly those issues so the guard can reconcile them (issue #1693).
    """
    res = _gh(["issue", "list", "--label", "security", "--state", "closed", "--limit", "200",
               "--json", "number,body,labels,title"], repo)
    if res.returncode != 0:
        raise SystemExit(f"[security-issues] cannot list closed issues: {res.stderr.strip()}")
    out: list[dict] = []
    for issue in json.loads(res.stdout or "[]"):
        body = issue.get("body") or ""
        if MARKER_RE.search(body) and SCAN_EVIDENCE_ACCEPTANCE in body:
            out.append(issue)
    return out


def _has_pipeline_clear(repo: str, number: int) -> bool:
    """Whether the issue was closed by the pipeline's own loop (it posted CLEAR_COMMENT).

    The clear loop (apply) closes with the `No longer reported by the latest scan` comment, so its
    presence is the single reliable marker of a genuine pipeline clear — everything else (a merged
    PR's `closes #N`, a manual close) closed it without the evidence round-trip the acceptance box
    demands (issue #1693).
    """
    res = _gh_api([f"repos/{repo}/issues/{number}/comments", "--jq",
                   "[.[].body] | join(\"\\n\")"])
    if res.returncode != 0:
        raise SystemExit(f"[security-issues] cannot read the comments of #{number}: "
                         f"{res.stderr.strip()}")
    return CLEAR_COMMENT in (res.stdout or "")


def reconcile(findings: list[Finding], repo: str, run_url: str = "", sha: str = "",
              dry: bool = False) -> int:
    """Never treat a merged-PR `closes #N` as satisfying a scan-evidence acceptance box (issue #1693).

    The security pipeline is honest on its own path: it only closes when the next scan no longer
    reports the finding and it comments the run that cleared it. Git's merge-close-by-reference
    bypasses that loop entirely — a PR merged with a bare `closes #N` closes the issue with zero
    scan evidence, so the box reads 'cleared' on a run that never ran.

    For every CLOSED scan-evidence issue that lacks the pipeline's own clearing comment:

      * the finding is STILL in this scan's reports -> the merge-close was premature: reopen it
        (a live finding must not drop off the board and be re-filed as a duplicate) and flag that
        a merged PR's `closes #N` does not clear a scan-evidence box;
      * the finding has genuinely gone -> post the honest clearing comment naming run id + sha,
        the #1646 round-trip the merge-close skipped (the box is now satisfied by a real scan).

    A closed issue that DOES carry the pipeline's clearing comment is a genuine pipeline clear and
    is left untouched (no behaviour change to the honest loop).
    """
    keys = {f.key for f in findings}
    reopened: list[str] = []
    evidenced: list[str] = []
    for issue in _closed_scan_evidence(repo):
        number = int(issue["number"])
        if _has_pipeline_clear(repo, number):
            continue  # the honest loop already closed it with evidence — untouched
        m = MARKER_RE.search(issue.get("body") or "")
        if m is None:  # unreachable: _closed_scan_evidence requires the marker — fail loudly
            raise SystemExit(f"[security-issues] #{number} has no scan-finding marker: "
                             f"{issue.get('body') or ''!r}")
        key = f"{m.group(1)}:{m.group(2)}:{m.group(3)}"
        if key in keys:
            if dry:
                reopened.append(f"#{number} ({key})")
                continue
            res = _gh(["issue", "edit", str(number), "--state", "open"], repo)
            if res.returncode != 0:
                raise SystemExit(f"[security-issues] cannot reopen #{number}: {res.stderr.strip()}")
            _gh(["issue", "comment", str(number), "--body",
                 "A merged PR's bare `closes #N` does not satisfy a scan-evidence acceptance box; "
                 "the latest scan still reports this finding, so it stays OPEN until a real scan "
                 f"clears it ({run_url or 'local run'})."], repo)
            reopened.append(f"#{number} ({key})")
        else:
            if dry:
                evidenced.append(f"#{number} ({key})")
                continue
            _gh(["issue", "comment", str(number), "--body",
                 f"CLEARED by a genuine scan — {CLEAR_COMMENT} {run_url or 'local run'} at "
                 f"`{sha or 'this head'}`."], repo)
            evidenced.append(f"#{number} ({key})")
    if reopened:
        print(f"[security-issues] reopened merge-closed scan-evidence issue(s): {', '.join(reopened)}")
    if evidenced:
        print(f"[security-issues] posted clearing evidence for merge-closed issue(s): "
              f"{', '.join(evidenced)}")
    if not reopened and not evidenced:
        print("[security-issues] reconcile: no merge-closed scan-evidence issue needs action")
    return 0


def plan(findings: list[Finding], existing: dict[str, dict]) -> dict[str, list]:
    """What apply would do: create the new keys, update the known ones, clear the vanished ones."""
    keys = {f.key for f in findings}
    return {
        "create": [f for f in findings if f.key not in existing],
        "update": [f for f in findings if f.key in existing],
        "clear": [k for k in existing if k not in keys],
    }


def apply(findings: list[Finding], repo: str, run_url: str = "") -> int:
    existing = existing_issues(repo)
    actions = plan(findings, existing)
    for label, (colour, description) in LABELS.items():
        _gh(["label", "create", label, "--color", colour, "--description", description,
             "--force"], repo)
    for finding in actions["create"]:
        body = body_for(finding, run_url)
        args = ["issue", "create", "--title", finding.title, "--body", body]
        for label in finding.labels:
            args += ["--label", label]
        res = _gh(args, repo)
        if res.returncode != 0:
            raise SystemExit(f"[security-issues] create failed for {finding.key}: {res.stderr.strip()}")
        number = res.stdout.strip().rstrip("/").rsplit("/", 1)[-1]
        if not number.isdigit():
            raise SystemExit(f"[security-issues] create for {finding.key} printed no issue number: "
                             f"{res.stdout.strip()!r}")
        # The `--label` flags above are not trusted: they are dropped on the runner path (#724,
        # #781-#784). The POST + read-back is what makes the issue routable.
        set_labels(repo, int(number), finding.labels)
        print(f"[security-issues] created: {finding.key} -> {res.stdout.strip()}")
    for finding in actions["update"]:
        issue = existing[finding.key]
        res = _gh(["issue", "edit", str(issue["number"]), "--body", body_for(finding, run_url)], repo)
        if res.returncode != 0:
            raise SystemExit(f"[security-issues] update failed for #{issue['number']}: {res.stderr.strip()}")
        # An existing issue that lost its labels is re-labelled, not left unroutable (#724).
        set_labels(repo, int(issue["number"]), finding.labels)
        print(f"[security-issues] updated: {finding.key} -> #{issue['number']}")
    for key in actions["clear"]:
        issue = existing[key]
        res = _gh(["issue", "close", str(issue["number"]), "--comment",
                   f"No longer reported by the latest scan ({run_url or 'local run'})."], repo)
        if res.returncode != 0:
            # A remediation PR may still reference it (#717); report, never crash the run.
            print(f"[security-issues] WARN: could not close #{issue['number']}: {res.stderr.strip()}")
    print(f"[security-issues] created={len(actions['create'])} updated={len(actions['update'])} "
          f"cleared={len(actions['clear'])}")
    return 0


def dry(findings: list[Finding]) -> int:
    """Print the plan and mutate nothing — the shape a reviewer reads before `apply` runs."""
    for finding in findings:
        print(f"CREATE {finding.title}")
        print(f"       labels: {', '.join(finding.labels)}")
        print(f"       marker: {finding.marker}")
        print(f"       {finding.current} -> {finding.fixed}")
    print(f"[security-issues] DRY: {len(findings)} issue(s) would be created or updated; nothing written")
    return 0


def check() -> int:
    """The label roster and the policy must be sane before an issue is filed."""
    problems: list[str] = []
    pol = ss.policy()
    severities = {str(s).lower() for s in pol.get("issue_severities") or []}
    if not severities:
        problems.append("security-policy.json: `issue_severities` is empty — no finding becomes an issue")
    if not severities <= {str(s).lower() for s in pol.get("fail_on") or []}:
        problems.append("security-policy.json: `issue_severities` is not a subset of `fail_on`")
    for severity in severities:
        if f"severity:{severity}" not in LABELS:
            problems.append(f"LABELS has no `severity:{severity}`: the issue cannot be filtered")
    for component in ("component:python", "component:container", "component:code"):
        if component not in LABELS:
            problems.append(f"LABELS has no `{component}`")
    if "auto-fixable" not in LABELS:
        problems.append("LABELS has no `auto-fixable`: the remediation bot has nothing to select")
    # The marker is the idempotency key: it must round-trip through MARKER_RE.
    # A semgrep SAST finding's package is `path:line`; the marker holds it like any other package.
    for source, advisory, package in (("trivy", "CVE-1", "numpy"), ("grype", "GHSA-1", "openssl"),
                                      ("semgrep", "sqlalchemy-execute-raw-query", "app.sql.py:5")):
        text = MARKER.format(source=source, advisory=advisory, package=package)
        m = MARKER_RE.search(text)
        if not m or (m.group(1), m.group(2), m.group(3)) != (source, advisory, package):
            problems.append(f"the marker does not round-trip for {source}:{advisory}:{package}")
    if problems:
        print(f"[security-issues] {len(problems)} problem(s):")
        for item in problems:
            print(f"  - {item}")
        return 1
    print(f"[security-issues] OK: {len(LABELS)} labels, issue_severities={sorted(severities)}, "
          "marker round-trips")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=("plan", "apply", "check", "reconcile"))
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    ap.add_argument("--reports", default=str(REPORTS))
    ap.add_argument("--run-url", default=os.environ.get("SECURITY_RUN_URL", ""))
    ap.add_argument("--sha", default=os.environ.get("GITHUB_SHA", ""),
                    help="the head sha the scan ran at — named in the clearing comment (issue #1693)")
    ap.add_argument("--dry", action="store_true", help="print what reconcile would do, mutate nothing")
    args = ap.parse_args(argv)
    if args.command == "check":
        return check()
    findings = issue_findings(Path(args.reports))
    if args.command == "plan":
        return dry(findings)
    if not args.repo:
        raise SystemExit("[security-issues] set --repo (or $GITHUB_REPOSITORY) to file issues")
    if args.command == "reconcile":
        return reconcile(findings, args.repo, args.run_url, args.sha, dry=args.dry)
    return apply(findings, args.repo, args.run_url)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
