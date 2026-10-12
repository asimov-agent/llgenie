"""Hermetic tests for the watch-loop removal (issue #210).

The watch-loop host crontab and dispatcher are removed; only the CI engine-bump
rebase stays. These tests assert the removal is complete and the rebase remains.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("GITHUB_TOKEN", "test-token-hermetic")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class TestNoCronMakeTargets:
    def test_no_cron_make_targets(self):
        # Given the Makefile
        mk = (ROOT / "Makefile").read_text()
        # Then it has no cron-install / cron-uninstall / cron-snapshot targets
        assert "cron-install:" not in mk, "cron-install target must be removed"
        assert "cron-uninstall:" not in mk, "cron-uninstall target must be removed"
        assert "cron-snapshot:" not in mk, "cron-snapshot target must be removed"
        # And no ci-cron / ci-watch-report / ci-dispatch-e2e / test-agents-e2e jobs
        assert "ci-cron:" not in mk, "ci-cron job must be removed"
        assert "ci-watch-report:" not in mk, "ci-watch-report job must be removed"
        assert "ci-dispatch-e2e:" not in mk, "ci-dispatch-e2e job must be removed"
        assert "test-agents-e2e:" not in mk, "test-agents-e2e target must be removed"


class TestDispatcherFilesRemoved:
    def test_dispatcher_files_removed(self):
        # Given the repo
        # Then the dispatcher + crontab + report scripts are gone
        for f in ("scripts/watchloop_dispatch.py",
                  "scripts/install_watchloop_cron.py",
                  "scripts/watch_report.py",
                  "scripts/serialized-make.py",
                  "scripts/worker-model.template"):
            assert not (ROOT / f).exists(), f"{f} must be removed"
        # And their tests are gone
        for f in ("tests/test_watchloop_dispatch.py",
                  "tests/test_install_watchloop_cron.py",
                  "tests/test_watch_report.py",
                  "tests/test_watchloop_dispatch_e2e.py"):
            assert not (ROOT / f).exists(), f"{f} must be removed"

    def test_no_pipeline_jobs_for_watchloop(self):
        # Given the pipeline workflow
        wf = (ROOT / ".github/workflows/pipeline.yml").read_text()
        # Then the cron / watch-report / dispatch-e2e jobs are gone
        assert "  cron:" not in wf, "cron job must be removed from pipeline.yml"
        assert "  watch-report:" not in wf, "watch-report job must be removed"
        assert "  dispatch-e2e:" not in wf, "dispatch-e2e job must be removed"

    def test_loop_harness_has_no_agents_e2e_stage(self):
        # Given the loop harness
        lh = (ROOT / "scripts/loop_harness.py").read_text()
        # Then it has no agents-e2e stage
        assert "agents-e2e" not in lh, "loop harness must not run test-agents-e2e"


class TestEngineBumpRebaseRemains:
    def test_engine_bump_rebase_remains(self):
        # Given the repo
        # Then the engine-bump rebase CI path stays (issue #208)
        assert (ROOT / "scripts/engine_bump_sync.py").exists(), "sync module must remain"
        assert (ROOT / "scripts/engine_bump_rebase.py").exists(), "rebase entrypoint must remain"
        assert (ROOT / ".github/workflows/engine-bump-rebase.yml").exists(), \
            "engine-bump-rebase workflow must remain"
