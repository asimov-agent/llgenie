"""Hermetic unit tests for scripts/engine_bump_sync.py (issue #208).

The shared engine-bump sync logic is used by BOTH the watch-loop dispatcher and
the CI rebase entrypoint. These tests lock the pure logic: classification,
upstream-remote resolution, and the forward-merge sync (clean merge => True,
conflict => False, never force-push on failure).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("GITHUB_TOKEN", "test-token-hermetic")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import scripts.engine_bump_sync as ebs  # noqa: E402


class _R:
    def __init__(self, rc=0, stdout="", stderr=""):
        self.returncode = rc
        self.stdout = stdout
        self.stderr = stderr


class TestIsEngineBumpPr:
    def test_by_ref_prefix(self):
        # Given a PR whose head ref starts with chore/engine-bump-
        pr = {"head": {"ref": "chore/engine-bump-tensorfold"}}
        # When classified
        # Then it is an engine-bump PR even without head.repo
        assert ebs.is_engine_bump_pr(pr) is True

    def test_by_head_repo(self):
        # Given a PR whose head repo is the upstream
        pr = {"head": {"ref": "x", "repo": {"full_name": "asimov-agent/llgenie"}}}
        assert ebs.is_engine_bump_pr(pr) is True
        # And a PR whose head repo is the fork
        pr2 = {"head": {"ref": "x", "repo": {"full_name": "andyholst/llgenie"}}}
        assert ebs.is_engine_bump_pr(pr2) is False

    def test_worker_pr_is_false(self):
        # Given a worker feat/* PR on the fork
        pr = {"head": {"ref": "feat/x", "repo": {"full_name": "andyholst/llgenie"}}}
        # Then it is NOT an engine-bump PR
        assert ebs.is_engine_bump_pr(pr) is False


class TestUpstreamRemote:
    FORK = "origin\thttps://github.com/andyholst/llgenie.git (fetch)\n" \
           "origin\thttps://github.com/andyholst/llgenie.git (push)\n"
    UPSTREAM = "upstream\thttps://github.com/asimov-agent/llgenie.git (fetch)\n" \
               "upstream\thttps://github.com/asimov-agent/llgenie.git (push)\n"

    def _runner(self, stdout, add_rc=0):
        calls = []

        def run_git(*args, **k):
            calls.append(args)
            if args[:1] == ("remote",) and "-v" in args:
                return _R(stdout=stdout)
            if "add" in args:
                return _R(rc=add_rc)
            return _R()

        return run_git, calls

    def test_resolved_from_url_not_name(self):
        # Given a fork-origin + upstream layout, in either order
        for remotes in (self.FORK + self.UPSTREAM, self.UPSTREAM + self.FORK):
            run_git, _ = self._runner(remotes)
            # When the upstream remote is resolved
            # Then it is the remote whose URL matches the upstream slug
            assert ebs.upstream_remote("/repo", run_git) == "upstream"

    def test_ssh_style_url_recognised(self):
        run_git, _ = self._runner("origin\tgit@github.com:asimov-agent/llgenie.git (fetch)\n")
        assert ebs.upstream_remote("/repo", run_git) == "origin"

    def test_origin_that_is_upstream_used_directly(self):
        run_git, _ = self._runner(
            "origin\thttps://github.com/asimov-agent/llgenie.git (fetch)\n"
            "origin\thttps://github.com/asimov-agent/llgenie.git (push)\n")
        assert ebs.upstream_remote("/repo", run_git) == "origin"
        assert ebs.upstream_main("/repo", run_git) == "origin/main"

    def test_missing_upstream_remote_is_added(self):
        run_git, calls = self._runner(self.FORK)
        assert ebs.upstream_remote("/repo", run_git) == "upstream"
        adds = [c for c in calls if "add" in c]
        assert adds, f"must add the upstream remote: {calls}"
        assert adds[0][-1] == ebs.UPSTREAM_URL
        assert ebs.upstream_main("/repo", run_git) == "upstream/main"

    def test_cannot_add_falls_back_to_origin(self):
        run_git, _ = self._runner(self.FORK, add_rc=128)
        assert ebs.upstream_remote("/repo", run_git) == "origin"


class TestSyncPrWithMain:
    FORK = "origin\thttps://github.com/andyholst/llgenie.git (fetch)\n" \
           "origin\thttps://github.com/andyholst/llgenie.git (push)\n"
    UPSTREAM = "upstream\thttps://github.com/asimov-agent/llgenie.git (fetch)\n" \
               "upstream\thttps://github.com/asimov-agent/llgenie.git (push)\n"

    def _env(self, merge_rc=0, push_rc=0, fetch_rc=0, branch_rc=0):
        calls = []
        logs = []

        def run_git(*args, **k):
            calls.append(args)
            if args[:1] == ("remote",) and "-v" in args:
                return _R(stdout=self.FORK + self.UPSTREAM)
            if args[0] == "fetch":
                return _R(rc=fetch_rc)
            if args[0] == "branch" and "-D" in args:
                return _R()
            if args[0] == "branch":
                return _R(rc=branch_rc)
            if args[0] == "merge":
                return _R(rc=merge_rc)
            if args[0] == "push":
                return _R(rc=push_rc)
            return _R()

        return run_git, calls, logs

    def test_engine_bump_pr_merges_upstream_main_and_pushes_back(self):
        # Given an engine-bump PR behind main on a fork-origin clone
        run_git, calls, logs = self._env()
        pr = {"number": 202, "head": {
            "ref": "chore/engine-bump-tensorfold", "sha": "deadbeef",
            "repo": {"full_name": "asimov-agent/llgenie"}}}
        # When the shared sync runs
        ok = ebs.sync_pr_with_main(pr, "/repo", run_git, logs.append)
        # Then it returns True and forward-merges the upstream main
        assert ok is True
        merges = [c for c in calls if c[0] == "merge"]
        assert merges and "upstream/main" in merges[0], f"merge source: {calls}"
        assert "origin/main" not in merges[0], f"must not merge the fork main: {calls}"
        # And pushes the synced branch back to the upstream remote, lease-pinned
        pushes = [c for c in calls if c[0] == "push"]
        assert pushes and pushes[0][1] == "upstream", f"push target: {calls}"
        assert any(a.startswith("--force-with-lease=chore/engine-bump-tensorfold:deadbeef")
                   for a in pushes[0]), f"lease-pinned: {pushes[0]}"

    def test_worker_pr_keeps_origin_behaviour(self):
        # Given a NON-engine-bump (fork) PR
        run_git, calls, _ = self._env()
        pr = {"number": 205, "head": {
            "ref": "feat/x", "sha": "deadbeef",
            "repo": {"full_name": "andyholst/llgenie"}}}
        # When the shared sync runs
        ok = ebs.sync_pr_with_main(pr, "/repo", run_git, lambda *a: None)
        # Then it merges origin/main and pushes to origin (unchanged)
        assert ok is True
        merges = [c for c in calls if c[0] == "merge"]
        assert merges and "origin/main" in merges[0], f"merge source: {calls}"
        assert "upstream/main" not in merges[0], f"worker PR must not merge upstream: {calls}"
        pushes = [c for c in calls if c[0] == "push"]
        assert pushes and pushes[0][1] == "origin", f"push target: {calls}"

    def test_conflict_returns_false_and_never_pushes(self):
        # Given a merge conflict
        run_git, calls, _ = self._env(merge_rc=1)
        pr = {"number": 202, "head": {
            "ref": "chore/engine-bump-tensorfold", "sha": "deadbeef",
            "repo": {"full_name": "asimov-agent/llgenie"}}}
        # When the sync hits the conflict
        ok = ebs.sync_pr_with_main(pr, "/repo", run_git, lambda *a: None)
        # Then it returns False and never pushes
        assert ok is False
        assert not any(c[0] == "push" for c in calls), f"must not push on conflict: {calls}"
        # And aborts the merge
        assert any(c[0] == "merge" and "--abort" in c for c in calls), f"must abort: {calls}"

    def test_fetch_failure_returns_false(self):
        # Given a failed branch fetch
        run_git, calls, _ = self._env(fetch_rc=1)
        pr = {"number": 202, "head": {
            "ref": "chore/engine-bump-tensorfold", "sha": "deadbeef",
            "repo": {"full_name": "asimov-agent/llgenie"}}}
        # When the sync cannot fetch the branch
        ok = ebs.sync_pr_with_main(pr, "/repo", run_git, lambda *a: None)
        # Then it returns False and never pushes
        assert ok is False
        assert not any(c[0] == "push" for c in calls)
