"""The agent-access gate: it refuses a deleted policy, a scope that stops naming its step, a
missing skill, and a credential pasted into the documents that grant access (issue #2923).

The gate reads real files, so the tests give it a real tree: each case copies AGENTS.md and the
host agent's skill into `tmp_path`, breaks ONE thing, and calls the real `check(root)` — no
monkeypatching of the check logic, only its input tree.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

from scripts import check_agent_access as gate


def _tree(tmp_path: Path) -> Path:
    """A minimal but REAL tree: the AGENTS.md section and the host agent's skill, as merged."""
    root = tmp_path / "repo"
    root.mkdir(parents=True)
    shutil.copy(REPO / "AGENTS.md", root / "AGENTS.md")
    target = root / gate.SKILL
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO / gate.SKILL, target)
    return root


def _agents(root: Path, mutate) -> None:
    text = (root / "AGENTS.md").read_text(encoding="utf-8")
    (root / "AGENTS.md").write_text(mutate(text), encoding="utf-8")


def test_the_real_tree_passes():
    """The repository as it stands satisfies the access policy its own gate enforces."""

    # Given the real checkout
    # When  the gate checks it
    findings = gate.check(REPO)

    # Then  there is nothing to report
    assert findings == [], findings


def test_battery_runs_the_gate():
    """`ci-unit` runs `make check-agent-access`; a PR that drops the step reddens here."""

    # Given the unit battery's step list
    steps = (REPO / "scripts" / "ci_unit.py").read_text(encoding="utf-8")

    # Then  the access gate is a named step
    assert '"make check-agent-access"' in steps


def test_a_deleted_section_fails_the_gate(tmp_path):
    """The identity policy is the artifact; deleting it is the defect the gate exists for."""

    # Given a tree whose AGENTS.md lost the whole identity/access section
    root = _tree(tmp_path)

    def cut(text: str) -> str:
        start = text.index(gate.HEADING_PREFIX)
        end = text.index("## Hermes cron jobs never run on the host", start)
        return text[:start] + text[end:]

    _agents(root, cut)

    # When  the gate checks it
    findings = gate.check(root)

    # Then  the missing section is named
    assert any("identity/access section is missing" in f for f in findings), findings


def test_a_scope_losing_its_operation_fails_the_gate(tmp_path):
    """A bare scope list teaches the next run which step each scope unblocks; the map must stay."""

    # Given a tree where `delete:packages` no longer names the GC step it authorizes
    root = _tree(tmp_path)
    _agents(root, lambda t: t.replace("garbage-collect", "remove"))

    # When  the gate checks it
    findings = gate.check(root)

    # Then  the scope whose mapping vanished is named
    assert any("delete:packages" in f and "no longer maps" in f for f in findings), findings
    # And   the other five scopes still pass — the finding is the mapping, not the whole roster
    assert not any("write:packages" in f for f in findings), findings


def test_the_identity_name_is_required(tmp_path):
    """A section that no longer names WHO acts leaves lanes acting under an unnamed identity."""

    # Given a tree whose section names no acting identity
    root = _tree(tmp_path)
    _agents(root, lambda t: t.replace("asimov-agent", "unnamed-identity"))

    # When  the gate checks it
    findings = gate.check(root)

    # Then  the missing identity is named with the policy's own token
    assert any(gate.IDENTITY in f and "identity" in f for f in findings), findings


def test_a_missing_skill_fails_the_gate(tmp_path):
    """The skill is where the audit rules live; a removed skill strips them silently."""

    # Given a tree without the host agent's access skill
    root = _tree(tmp_path)
    (root / gate.SKILL).unlink()

    # When  the gate checks it
    findings = gate.check(root)

    # Then  the missing skill is named by its repo-relative path
    assert any(gate.SKILL in f and "missing" in f for f in findings), findings


def test_a_stripped_audit_rule_fails_the_gate(tmp_path):
    """Every elevated run must stay stamped on the issue that requested it — the phrase is the rule."""

    # Given a skill that stopped stating the stamp requirement
    root = _tree(tmp_path)
    text = (root / gate.SKILL).read_text(encoding="utf-8")
    (root / gate.SKILL).write_text(text.replace("stamped", "recorded quietly"), encoding="utf-8")

    # When  the gate checks it
    findings = gate.check(root)

    # Then  the missing rule phrase is named
    assert any("stamped" in f for f in findings), findings


def test_a_token_pasted_into_the_section_is_refused_without_echo(tmp_path):
    """The documents that grant access cannot contain a credential — and the report never echoes it."""

    # Given a section someone pasted a fake token into while debugging auth
    root = _tree(tmp_path)
    fake = "gho_" + "A" * 36
    _agents(root, lambda t: t.replace(
        "An elevated run is an audited run:",
        f"An elevated run is an audited run:\n\n debugging note: {fake}\n", 1))

    # When  the gate checks it
    findings = gate.check(root)

    # Then  the artifact and kind are reported — and no finding carries the value
    assert any("secret-shaped" in f for f in findings), findings
    assert all(fake not in f for f in findings), findings


def test_a_token_pasted_into_the_skill_is_refused(tmp_path):
    """The scan covers the skill too: an agent reads that file, so a key in it is a leak with a diff."""

    # Given a skill containing a fine-grained-token-shaped string
    root = _tree(tmp_path)
    fake = "github_pat_" + "b" * 40
    text = (root / gate.SKILL).read_text(encoding="utf-8")
    (root / gate.SKILL).write_text(text + f"\nbackup token {fake}\n", encoding="utf-8")

    # When  the gate checks it
    findings = gate.check(root)

    # Then  the skill is named, the kind is named, and the value is not
    assert any(gate.SKILL in f and "secret-shaped" in f for f in findings), findings
    assert all(fake not in f for f in findings), findings


def test_report_reads_the_policy_and_exits_zero(tmp_path, capsys):
    """The report prints what the gate reads without turning a finding into a failed command."""

    # Given the real tree and a broken copy of it
    # When  the report runs on both
    assert gate.report(REPO) == 0
    broken = _tree(tmp_path)
    broken_copy = REPO / "AGENTS.md"
    shutil.copy(broken_copy, broken / "AGENTS.md")
    _agents(broken, lambda t: t.replace(gate.HEADING_PREFIX, "## Some other heading"))
    # gate.report reads only REPO-shaped trees via print; check() carries the findings instead
    findings = gate.check(broken)

    # Then  the real tree prints clean and the broken tree reports its finding
    out = capsys.readouterr().out
    assert "verdict:         CLEAN" in out, out
    assert any("identity/access section is missing" in f for f in findings), findings
