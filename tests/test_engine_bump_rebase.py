"""Hermetic unit tests for scripts/engine_bump_rebase.py (issue #208).

The CI rebase entrypoint lists open chore/engine-bump-* PRs and calls the shared
sync logic for each behind one. These tests stub the GitHub API and the shared
sync so no real network or push happens.
"""
from __future__ import annotations

import datetime as dt

import os
import re
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("GITHUB_TOKEN", "test-token-hermetic")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import scripts.engine_bump_rebase as ebr  # noqa: E402


def _pr(n, ref="chore/engine-bump-tensorfold", behind=True, repo="asimov-agent/llgenie"):
    return {
        "number": n,
        "head": {"ref": ref, "sha": "h" * 40,
                 "repo": {"full_name": repo}},
        "base": {"ref": "main", "sha": "b" * 40},
        "_behind": behind,
    }


class TestOpenEngineBumpPrs:
    def test_filters_to_engine_bump_refs(self, monkeypatch):
        # Given open PRs including engine-bump and worker PRs
        monkeypatch.setattr(ebr, "api", lambda path: [
            _pr(202, "chore/engine-bump-tensorfold"),
            _pr(203, "chore/engine-bump-llama.cpp"),
            _pr(205, "feat/engine-push-requires-binary", repo="andyholst/llgenie"),
        ])
        # When the open engine-bump PRs are listed
        prs = ebr.open_engine_bump_prs()
        # Then only the chore/engine-bump-* PRs are returned
        assert [p["number"] for p in prs] == [202, 203]

    def test_api_error_returns_empty(self, monkeypatch):
        # Given the API fails
        monkeypatch.setattr(ebr, "api", lambda path: None)
        # Then no PRs are returned (fail closed)
        assert ebr.open_engine_bump_prs() == []


class TestPrIsBehind:
    def test_behind_is_true(self, monkeypatch):
        monkeypatch.setattr(ebr, "api", lambda path: {"status": "behind"})
        assert ebr.pr_is_behind(_pr(1)) is True

    def test_ahead_is_false(self, monkeypatch):
        monkeypatch.setattr(ebr, "api", lambda path: {"status": "ahead"})
        assert ebr.pr_is_behind(_pr(1)) is False

    def test_identical_is_false(self, monkeypatch):
        monkeypatch.setattr(ebr, "api", lambda path: {"status": "identical"})
        assert ebr.pr_is_behind(_pr(1)) is False

    def test_api_error_is_behind(self, monkeypatch):
        monkeypatch.setattr(ebr, "api", lambda path: None)
        assert ebr.pr_is_behind(_pr(1)) is True


class TestMain:
    def _patch(self, monkeypatch, prs, sync_result=True, comments=None, post_ok=True):
        monkeypatch.setattr(ebr, "open_engine_bump_prs", lambda: prs)
        monkeypatch.setattr(ebr, "pr_is_behind", lambda pr: pr.get("_behind", True))
        synced = []
        monkeypatch.setattr(ebr, "sync_pr_with_main",
                            lambda pr, repo, run_git, log: synced.append(pr["number"]) or sync_result)
        # the claim protocol: the comments are read through the same api(), the claim goes out
        # through post() (issues #279/#285). Both are patched so no test touches the network.
        monkeypatch.setattr(ebr, "api", lambda path: comments if comments is not None else [])
        self.posted = []
        monkeypatch.setattr(ebr, "post", lambda path, body: self.posted.append((path, body)) or post_ok)
        return synced

    def test_dry_run_reports_without_pushing(self, monkeypatch, capsys):
        # Given open engine-bump PRs, one behind
        synced = self._patch(monkeypatch, [_pr(202, behind=True)])
        # When a dry run happens
        monkeypatch.setattr(ebr.sys, "argv", ["engine_bump_rebase.py", "--dry"])
        rc = ebr.main()
        # Then it reports what it would do and performs no sync
        assert rc == 0
        assert synced == [], f"dry run must not sync: {synced}"
        out = capsys.readouterr().out
        assert "would forward-merge" in out, out

    def test_behind_engine_bump_pr_is_rebased(self, monkeypatch, capsys):
        # Given an open engine-bump PR that is behind main
        synced = self._patch(monkeypatch, [_pr(202, behind=True)])
        monkeypatch.setattr(ebr.sys, "argv", ["engine_bump_rebase.py"])
        # When the entrypoint runs
        rc = ebr.main()
        # Then it calls the shared sync for that PR
        assert rc == 0
        assert synced == [202], f"behind PR must be synced: {synced}"

    def test_up_to_date_pr_is_skipped(self, monkeypatch, capsys):
        # Given an engine-bump PR that is NOT behind
        synced = self._patch(monkeypatch, [_pr(202, behind=False)])
        monkeypatch.setattr(ebr.sys, "argv", ["engine_bump_rebase.py"])
        rc = ebr.main()
        # Then it is skipped (not synced)
        assert rc == 0
        assert synced == [], f"up-to-date PR must be skipped: {synced}"

    def test_it_claims_the_pr_before_rebasing_and_releases_it_after(self, monkeypatch, capsys):
        """Issue #279: the engine-bump PRs belong to another bot, so this one announces itself
        before it force-pushes, and says when it has finished."""
        synced = self._patch(monkeypatch, [_pr(202, behind=True)])
        monkeypatch.setattr(ebr.sys, "argv", ["engine_bump_rebase.py"])
        rc = ebr.main()
        assert rc == 0 and synced == [202]
        kinds = [b["body"].split()[1] for _path, b in self.posted]
        assert kinds == ["bot-claim:", "bot-done:"], self.posted
        assert "engine-bump-rebase" in self.posted[0][1]["body"]
        assert self.posted[0][0] == "/issues/202/comments"

    def test_a_pr_another_bot_holds_is_left_alone(self, monkeypatch, capsys):
        """A claim on the PR means someone is on it: a fresh one blocks, whatever bot posted it."""
        when = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        held = [{"body": f"<!-- bot-claim: fix-bot {when} fix -->\n`fix-bot` is fixing this now.",
                 "createdAt": when, "author": {"login": "github-actions[bot]"}}]
        synced = self._patch(monkeypatch, [_pr(202, behind=True)], comments=held)
        monkeypatch.setattr(ebr.sys, "argv", ["engine_bump_rebase.py"])
        rc = ebr.main()
        assert rc == 0 and synced == [], f"a held PR must not be synced: {synced}"
        assert self.posted == [], self.posted
        assert "claimed by fix-bot" in capsys.readouterr().out

    def test_it_does_not_touch_a_pr_whose_claim_it_could_not_post(self, monkeypatch, capsys):
        """Fail closed: an unannounced push is exactly what the protocol exists to prevent."""
        synced = self._patch(monkeypatch, [_pr(202, behind=True)], post_ok=False)
        monkeypatch.setattr(ebr.sys, "argv", ["engine_bump_rebase.py"])
        rc = ebr.main()
        assert rc == 0 and synced == [], f"no claim, no push: {synced}"

    def test_no_open_prs_is_clean(self, monkeypatch, capsys):
        # Given no open engine-bump PRs
        synced = self._patch(monkeypatch, [])
        monkeypatch.setattr(ebr.sys, "argv", ["engine_bump_rebase.py"])
        rc = ebr.main()
        # Then it exits 0 and syncs nothing
        assert rc == 0
        assert synced == []


class TestWorkflowYaml:
    def test_workflow_runs_the_rebase_entrypoint(self):
        # Given the workflow file and the make target behind its step
        root = Path(__file__).resolve().parent.parent
        text = (root / ".github/workflows/engine-bump-rebase.yml").read_text()
        makefile = (root / "Makefile").read_text()
        # Then it runs on its OWN daily minute (the minute moved with issue #275: every bot owns a
        # slot, and pinning one here would just go stale again), checks out with BUMP_TOKEN, and
        # reaches the entrypoint through `make` (a workflow step calls a make target and nothing
        # else) — with the `dry` input the dispatch form offers wired to the script's own `--dry`.
        assert "cron:" in text, "must be scheduled"
        assert re.search(r'cron:\s*"\S+ \S+ \* \* \*"', text), "must have a DAILY cron"
        assert "17 5 * * *" not in text, "the old SHARED minute (05:17 UTC) must stay gone (#275)"
        assert "secrets.BUMP_TOKEN" in text, "must use the owner PAT"
        assert "make engine-bump-rebase" in text, "the step must call the make target"
        assert "engine_bump_rebase.py" not in text.split("on:", 1)[1], \
            "the run block must not call the script directly (issue #270's rule)"
        assert re.search(r"^engine-bump-rebase:.*\n\tpython3 scripts/engine_bump_rebase\.py", makefile,
                         re.M), "the make target must run the entrypoint"
        assert "inputs.dry" in text, "the documented `dry` input must reach the target"
        assert "workflow_dispatch" in text, "must allow manual dispatch"

    def test_guard_sends_the_token_variable(self):
        """The collaborator check authenticates with $TOKEN, not a literal.

        Run 38315109038 refused a write collaborator because the rebase guard
        sent the header as the three characters '***'.
        """

        # Given every workflow that calls the collaborators endpoint
        root = Path(__file__).resolve().parent.parent / ".github/workflows"
        names = (
            "ci.yml",
            "engine-bump.yml",
            "engine-bump-rebase.yml",
            "registry-sync.yml",
        )

        # When each guard job is read
        for name in names:
            text = (root / name).read_text()

            # Then the header is the default token variable
            assert "TOKEN: ${{ secrets.GITHUB_TOKEN }}" in text
            assert 'Authorization: Bearer $TOKEN' in text
            assert "Bearer ***" not in text

    def test_file_invocation_imports_the_scripts_package(self):
        """The workflow command can import scripts.engine_bump_sync.

        Run 38318141627 ran `python3 scripts/engine_bump_rebase.py` and died
        with ModuleNotFoundError: No module named 'scripts'.
        """

        # Given the workflow command and a token that cannot list PRs
        env = os.environ.copy()
        env["GITHUB_TOKEN"] = "test-token-hermetic"
        env["GH_TOKEN"] = "test-token-hermetic"
        root = Path(__file__).resolve().parent.parent

        # When the entrypoint is run as a file
        proc = subprocess.run(
            [sys.executable, "scripts/engine_bump_rebase.py", "--dry"],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=40,
        )

        # Then the scripts package imports and no rebase is attempted
        assert "No module named 'scripts'" not in proc.stderr
        assert proc.returncode == 0
        assert "[engine-bump-rebase] no open engine-bump PRs" in proc.stdout
