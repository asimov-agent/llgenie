"""Test the main-ruleset required-status-checks guard (issue #1400).

The guard measures GitHub's OWN `main` ruleset rather than this tree, so these tests drive it
offline through `--fixture` — the exact ruleset JSON shapes the live API returns (one the gap
fixture copies from the measured live ruleset id 24862727; the covered fixture adds the
`required_status_checks` rule the owner-admin apply writes). The live read itself is exercised by
the scheduled monitor workflow, not by a hermetic unit (this suite has no network).
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts import check_main_ruleset as rs

FIX = Path(__file__).resolve().parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIX / name).read_text())


def test_missing_rule_is_red():
    """A ruleset with no required_status_checks is a red finding (the measured gap)."""

    # Given the live `main` ruleset's exact two-rule shape (gap fixture)
    ruleset = _load("main-ruleset-gap.json")

    # When  the guard checks it
    findings = rs.check(ruleset)

    # Then  it names the missing required_status_checks rule and nothing else covers it
    assert any("missing `required_status_checks`" in f for f in findings)
    assert len(findings) == 1


def test_covered_ruleset_is_green():
    """A ruleset listing every pinned context passes (the state the owner-admin apply writes)."""

    # Given a ruleset whose required_status_checks covers the full pinned floor
    ruleset = _load("main-ruleset-covered.json")

    # When  the guard checks it
    findings = rs.check(ruleset)

    # Then  there are no findings
    assert findings == []


def test_partial_rule_names_each_missing_context():
    """A required_status_checks rule missing one pinned context names exactly it."""

    # Given a ruleset missing the `ci-verdict` context from the pinned floor
    ruleset = _load("main-ruleset-partial.json")

    # When  the guard checks it
    findings = rs.check(ruleset)

    # Then  it names the missing context, and only the missing one
    assert any("`ci-verdict` is not listed" in f for f in findings)
    assert len(findings) == 1


def test_pin_is_additive_not_exact():
    """An extra context beyond the pin is not a finding (the floor, not an exact match)."""

    # Given a covered ruleset that ALSO lists one new context the pipeline added
    ruleset = _load("main-ruleset-covered.json")
    ruleset["rules"][2]["parameters"]["contexts"].append("linux / brand-new-job")

    # When  the guard checks it
    findings = rs.check(ruleset)

    # Then  there are no findings — a legitimate addition never reds the guard
    assert findings == []


def test_apply_body_is_add_only():
    """apply_body keeps deletion/non_fast_forward and appends required_status_checks."""

    # Given the gap ruleset
    ruleset = _load("main-ruleset-gap.json")

    # When  the add-only body is built from it
    body = rs.apply_body(ruleset)

    # Then  it keeps the two originals and appends required_status_checks over the pinned floor,
    #       and re-running on an already-covered ruleset is idempotent
    types = [r["type"] for r in body["rules"]]
    assert types == ["deletion", "non_fast_forward", "required_status_checks"]
    assert body["rules"][2]["parameters"]["contexts"] == list(rs.REQUIRED_CONTEXTS)
    assert body["name"] == "main" and body["enforcement"] == "active"
    again = rs.apply_body(_load("main-ruleset-covered.json"))
    assert [r["type"] for r in again["rules"]].count("required_status_checks") == 1


def test_apply_cli_defaults_to_dry_and_prints_add_only_body():
    """apply without --apply prints the payload and never PUTs (no network in the DRY path)."""

    # Given the gap fixture and an apply that does NOT pass --apply
    code, out, err = _run(["apply", "--ruleset-id", "24862727",
                           "--fixture", str(FIX / "main-ruleset-gap.json")])

    # Then  it exits 0, prints a body with required_status_checks, and says DRY
    assert code == 0
    body = json.loads(out)
    assert [r["type"] for r in body["rules"]] == \
        ["deletion", "non_fast_forward", "required_status_checks"]
    assert "DRY" in err


def test_report_exits_zero_on_a_red_finding():
    """report prints the measured state and exits 0 even when the rule is missing."""

    # Given the gap ruleset
    ruleset = _load("main-ruleset-gap.json")

    # When  report runs (the subprocess path through main())
    code, out, err = _run(["report", "--fixture", str(FIX / "main-ruleset-gap.json")])

    # Then  it exits 0 and names the missing rule in the output
    assert code == 0
    combined = out + err
    assert "required_status_checks: ABSENT" in combined


def test_check_subprocess_exits_1_for_the_gap_and_0_for_the_covered_state():
    """The check command's exit contract: red on the gap, green on the covered state."""

    # When  check runs on the gap fixture and on the covered fixture
    gap_code, _, _ = _run(["check", "--fixture", str(FIX / "main-ruleset-gap.json")])
    cov_code, _, _ = _run(["check", "--fixture", str(FIX / "main-ruleset-covered.json")])

    # Then  gap is red (1), covered is green (0)
    assert gap_code == 1
    assert cov_code == 0


def _run(args: list[str]):
    import subprocess
    import sys
    r = subprocess.run(  # proc-allow: direct subprocess call site, tracked remainder for issue #797
        [sys.executable, str(Path(__file__).resolve().parent.parent / "scripts" / "check_main_ruleset.py"), *args],
        capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr
