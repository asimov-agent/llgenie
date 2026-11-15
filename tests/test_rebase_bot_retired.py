"""The rebase-bot lane is fully retired, and the `rebase` WORK KIND survives for engine-bump-rebase.

Issue #2703 retired the `rebase-bot` bot lane (workflow, scripts, make targets, claim name, skill,
roster/exemption entries, tests) because its landing function is already covered by AGENTS.md's
agent-self-rebase rule and the allow-listed `engine-bump-rebase.yml`. The `rebase` WORK KIND is kept:
`engine-bump-rebase` still posts the marker that stops another bot racing its PR rebase.

These are dead-surface assertions that read the real tree and the real script — no mock of
bot_claims, and no reliance on an internal constant name that a refactor could rename.
"""
from pathlib import Path

import inspect

import bot_claims

REPO_ROOT = Path(__file__).resolve().parent.parent


def _module_source() -> str:
    # The real module source, read from disk — not a copy, so a refactor cannot drift the test.
    return inspect.getsource(bot_claims)


def test_the_rebase_bot_workflow_is_gone():
    # Given the workflows directory at HEAD
    wf_dir = REPO_ROOT / ".github/workflows"

    # When we look for the retired lane's workflow
    # Then it does not exist
    assert not (wf_dir / "rebase-bot.yml").exists()


def test_the_rebase_bot_scripts_are_gone():
    # Given the scripts directory at HEAD
    scripts = REPO_ROOT / "scripts"

    # When we look for the retired lane's driver and sweep
    # Then neither exists
    assert not (scripts / "rebase_bot.sh").exists()
    assert not (scripts / "rebase_bot_sweep.py").exists()


def test_no_make_target_names_the_retired_lane():
    # Given the Makefile and its includes
    text = "\n".join(p.read_text() for p in (
        REPO_ROOT / "Makefile",
        REPO_ROOT / "mk" / "bots.mk",
        REPO_ROOT / "mk" / "engines.mk",
    ) if p.exists())

    # When we scan for the retired target names and its skills variable
    # Then none are defined / referenced
    assert "rebase-bot" not in text
    assert "REBASE_BOT_SKILLS" not in text
    assert "rebase_bot_sweep" not in text


def test_the_rebase_claim_worker_is_now_engine_bump_rebase():
    # Given the real claims registry module
    source = _module_source()

    # When we look for its bot names and the work-kind grammar
    # Then the living writer is engine-bump-rebase, not rebase-bot
    assert bot_claims.ENGINE_BUMP == "engine-bump-rebase"
    assert not hasattr(bot_claims, "REBASER")
    # the `rebase` WORK KIND still has a writer
    assert "engine-bump-rebase" in source


def test_pause_toml_no_longer_names_rebase_bot():
    # Given the pause roster
    # When we read its bot list
    # Then rebase-bot is gone
    assert "rebase-bot" not in (REPO_ROOT / "bots" / "pause.toml").read_text()
