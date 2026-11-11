#!/usr/bin/env python3
"""Measure the `main` ruleset's required status checks and fail when they are missing (issue #1400).

The repository's only branch protection is the `main` ruleset. GitHub applies `required_status_checks`
as a merge block ONLY when the ruleset lists them; a ruleset that lists none lets a red CI run land on
`main` entirely authorised at the platform layer. Nothing in the repo reads that state, so the gap
rots silently. This guard is the measure-and-alarm control: it reads the live ruleset and fails when
the gate is missing or under-pinned, so the gap becomes a visible red run with a consumer instead of a
definition nobody runs.

The pinned context floor is additive, measured from this repo's own pipeline (a merged pull-request
run's emitted check-runs), never an assumed enum. A ruleset whose `required_status_checks` lists every
pinned context is green; an extra listed context is NOT a finding — the pin is a floor, not an exact
match, so a legitimate addition never reds the guard.

Commands (driven by make, never by hand):

    check [--ruleset-id ID] [--fixture FILE]    exit 1 on missing/under-pinned; 2 on unreadable
    report [--ruleset-id ID] [--fixture FILE]   print the measured state, always exit 0
    apply [--ruleset-id ID] [--apply]           print the add-only PUT body (default DRY); --apply PUTs it
    pins                                        print the pinned context floor (the apply body's source)

`--fixture FILE` runs every command offline against a JSON file shaped like the ruleset API response,
so `make test-unit` can prove the guard catches the bug without touching the live API.

The apply is owner-admin-only: a non-admin token receives 404 on a ruleset PUT (measured on this
repo). The command defaults to DRY so the exact add-only body is always inspectable before any
mutation; `--apply` with an admin token performs it. This lane never sends the PUT itself.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = "asimov-agent/llgenie"

#: The pinned context floor — every context the repo's own pipeline emits and must be green before a
#: merge. Measured 2026-11-07 from the check-runs a real merged pull request emitted on its head
#: (PR #2001 head 1025cdad, PR #2012 head 72ec659b, PR #1392 head dfd1be94): every run carried exactly
#: these names. This set is the ADDITIVE FLOOR the guard requires; extra listed contexts are not a
#: finding. When the pipeline's job set grows, ADD a context here — the guard must not red on a
#: legitimate addition.
#:
#: `linux / top-tier` is deliberately NOT pinned: its check-run name is label-dependent — a PR without
#: the `ci:slow` label emits `linux / top-tier (none)`, a labelled one emits `linux / top-tier (run)`
#: (measured), so pinning either spelling would deadlock the other side (#1400 sub-question 1: "only
#: checks the PR actually receives may be listed, or merges deadlock").
REQUIRED_CONTEXTS: tuple[str, ...] = (
    "guard",
    "ci-images",
    "linux / agents-read",
    "linux / cpu-health",
    "linux / install",
    "linux / lint",
    "linux / openspec",
    "linux / unit",
    "ci-verdict",
)

DEFAULT_RULESET_ID = "24862727"


def _gh_api(args: list[str]) -> tuple[int, str]:
    """Run `gh api ...`; returns (returncode, stdout). The policy seam (issue #797)."""
    r = subprocess.run(  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
        ["gh", "api", *args], capture_output=True, text=True)
    return r.returncode, (r.stdout or "")


def live_ruleset(ruleset_id: str = DEFAULT_RULESET_ID, repo: str = REPO) -> dict:
    """The live ruleset for `--ruleset-id` in `repo`. Raises RuntimeError with the gh error on a failed read."""
    code, out = _gh_api([f"repos/{repo}/rulesets/{ruleset_id}"])
    if code != 0:
        raise RuntimeError(f"gh api rulesets/{ruleset_id} failed (exit {code})")
    try:
        return json.loads(out)
    except ValueError as e:
        raise RuntimeError(f"ruleset {ruleset_id} response was not JSON: {e}") from e


def fixture_ruleset(path: Path) -> dict:
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError) as e:
        raise RuntimeError(f"cannot read fixture {path}: {e}") from e
    return data


def _rule_type(rule: dict) -> str:
    return rule.get("type", "")


def required_contexts(rs: dict):
    """The contexts of the ruleset's `required_status_checks` rule, or None when that rule is absent."""
    for rule in rs.get("rules", []):
        if _rule_type(rule) == "required_status_checks":
            params = rule.get("parameters") or {}
            return list(params.get("contexts", []) or [])
    return None


def check(rs: dict) -> list[str]:
    """Every finding about the ruleset's gate: [] means the gate covers the pin."""
    findings: list[str] = []
    found = required_contexts(rs)
    if found is None:
        findings.append(f"missing `required_status_checks` rule (rules: "
                        f"{[_rule_type(r) for r in rs.get('rules', [])]})")
        return findings
    pinned = set(REQUIRED_CONTEXTS)
    have = set(found)
    for ctx in REQUIRED_CONTEXTS:
        if ctx not in have:
            findings.append(f"required status check `{ctx}` is not listed "
                            f"(found {sorted(have)})")
    return findings


def render(rs: dict, findings: list[str]) -> str:
    name = rs.get("name") or f"ruleset {rs.get('id')}"
    enforcement = rs.get("enforcement", "?")
    rules = [_rule_type(r) for r in rs.get("rules", [])]
    lines = [f"{name} (enforcement={enforcement}) rules={rules}"]
    found = required_contexts(rs)
    if found is None:
        lines.append("  required_status_checks: ABSENT")
    else:
        lines.append("  required_status_checks contexts:")
        for c in sorted(found):
            lines.append(f"    - {c}")
    lines.append("  pinned floor (all required before a merge):")
    for c in REQUIRED_CONTEXTS:
        lines.append(f"    - {c}")
    if findings:
        lines.append("  FINDINGS:")
        for f in findings:
            lines.append(f"    - {f}")
    return "\n".join(lines)


def apply_body(rs: dict) -> dict:
    """The add-only PUT body: keep the existing non-destructive rules, append required_status_checks.

    The ruleset's meaningful job-merge rule is `required_status_checks`; we APPEND it to whatever the
    ruleset already has. Non-destructive rules (`deletion`, `non_fast_forward`, and any other present
    rule) are preserved verbatim so this is a pure additive change, never a rewrite that weakens a rule.
    If a `required_status_checks` rule already exists, its contexts are REPLACED with the pin (the
    guard wants the floor; re-sending is the idempotent repair).
    """
    body = {
        "name": rs.get("name"),
        "enforcement": rs.get("enforcement"),
        "conditions": rs.get("conditions"),
        "rules": [r for r in rs.get("rules", [])
                  if _rule_type(r) != "required_status_checks"],
    }
    body["rules"].append({
        "type": "required_status_checks",
        "parameters": {"contexts": list(REQUIRED_CONTEXTS)},
    })
    return body


def _apply(ruleset_id: str, rs: dict, send: bool, repo: str = REPO) -> str:
    body = apply_body(rs)
    payload = json.dumps(body, indent=2)
    if not send:
        return payload
    with _TmpJSON(body) as path:
        code, out = _gh_api([f"repos/{repo}/rulesets/{ruleset_id}",
                             "-X", "PUT", "--input", path])
    if code != 0:
        raise RuntimeError(f"ruleset PUT failed (exit {code}): {out.strip()}")
    return f"PUT {ruleset_id} HTTP {code}"


class _TmpJSON:
    def __init__(self, obj: dict):
        self._obj = obj
        self._path: Path | None = None

    def __enter__(self) -> str:
        import tempfile
        fd, name = tempfile.mkstemp(suffix=".json")
        with open(fd, "w") as f:
            json.dump(self._obj, f)
        self._path = Path(name)
        return name

    def __exit__(self, *_):
        if self._path:
            self._path.unlink(missing_ok=True)


def _load(a: argparse.Namespace) -> dict:
    return fixture_ruleset(Path(a.fixture)) if a.fixture else live_ruleset(a.ruleset_id, a.repo)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Measure the main ruleset's required status checks (issue #1400)")
    ap.add_argument("cmd", choices=("check", "report", "apply", "pins"))
    ap.add_argument("--repo", default=REPO, help=f"owner/repo (default {REPO})")
    ap.add_argument("--ruleset-id", default=DEFAULT_RULESET_ID,
                    help=f"ruleset id to read (default {DEFAULT_RULESET_ID})")
    ap.add_argument("--fixture", help="read ruleset JSON from FILE (offline, no gh)")
    ap.add_argument("--apply", action="store_true",
                    help="with `apply`: perform the PUT (needs an admin token); default prints the body only")
    a = ap.parse_args(argv)

    if a.cmd == "pins":
        for c in REQUIRED_CONTEXTS:
            print(c)
        return 0

    try:
        rs = _load(a)
    except RuntimeError as e:
        print(f"[main-ruleset] read failed: {e}", file=sys.stderr)
        return 2

    if a.cmd == "apply":
        try:
            print(_apply(a.ruleset_id, rs, send=a.apply, repo=a.repo))
        except RuntimeError as e:
            print(f"[main-ruleset] {e}", file=sys.stderr)
            return 2
        if not a.apply:
            print("\n[main-ruleset] DRY — body printed, nothing PUT. Re-run with --apply and an "
                  "admin token to perform the update (owner-admin-only, issue #1400).",
                  file=sys.stderr)
        return 0

    findings = check(rs)
    print(render(rs, findings))
    if a.cmd == "report":
        return 0
    # check
    if findings:
        print("[main-ruleset] RED: the main ruleset will not block a red merge", file=sys.stderr)
        return 1
    print("[main-ruleset] GREEN: main's ruleset requires each pinned status check",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
