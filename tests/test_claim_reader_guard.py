"""The claim-reader guard refuses a live file that re-opens the run-liveness read."

A live file that re-opens `gh run view <id> --json status,conclusion` outside
`scripts/bot_claims.py` is the drift issue #799 deleted — three byte-identical copies plus a per-leg
cache, so two legs in one run could disagree. The guard is the CI gate (`make check-claim-reader`,
inside `ci-unit`); these tests pin its discriminator: the exact `--json status,conclusion` shape
with no `--repo`, so a repo-scoped CI reader is NOT caught.
"""

from __future__ import annotations

from pathlib import Path

from scripts import claim_reader_guard as guard

REPO = Path(__file__).resolve().parent.parent


def test_the_claim_probe_is_the_exact_run_view_status_read():
    """`--json status,conclusion` with no `--repo` is the claim reader's sign."""
    assert guard.is_claim_read('gh_call(["run", "view", str(rid), "--json", "status,conclusion"])')
    assert not guard.is_claim_read(
        'gh_call(["run", "view", str(rid), "--repo", repo, "--json", "status,conclusion"])')
    assert not guard.is_claim_read(
        'return std("%s", "run", "view", rid, "--json", "databaseId,status,conclusion,attempt")')
    assert not guard.is_claim_read(
        'run_gh(["api", f"repos/{repo}/actions/runs", "--paginate"])')


def test_the_real_tree_is_clean():
    """No live file outside the allow-list opens the claim read; the four legs are gone (issue #799)."""
    found = guard.hits(REPO)
    assert found == [], f"claim-reader guard would red on: {found}"


def test_every_bot_claim_reader_delegates_to_bot_claims():
    """The four legs carry no run_is_live/_LIVE; only bot_claims defines the probe."""
    for f in ("scripts/issue_implementer.py", "scripts/issue_refiner.py",
              "scripts/rebase_bot_sweep.py", "scripts/fix_bot_sweep.py"):
        text = (REPO / f).read_text()
        assert "def run_is_live" not in text, f"{f} re-implements run_is_live (issue #799)"
        assert "_LIVE: dict" not in text, f"{f} carries its own _LIVE cache (issue #799)"
        # ...but each still reaches the claim reader through bot_claims.
        assert "bot_claims.run_is_live" in text, f"{f} no longer calls the shared reader"
