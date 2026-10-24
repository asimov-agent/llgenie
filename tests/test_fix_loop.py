"""The PR fix-bot loop: bounded rounds, early stop, loud failure, no git (issue #222).

The loop itself runs for real; only the *external* CLIs it drives are stubbed (the agent on
PATH), the same allowance `tests/test_engine_skill_gap.py` uses for `gh`. What is asserted is
the contract `fix-bot.yml` depends on: it checks, hands the agent the failure output under the
preloaded `pr-fix`/`bot-unattended` skills (issue #577: the rules are a Hermes project skill, not a
paragraph pasted into the prompt), re-checks, stops as soon as it is green, gives up loudly after
`FIX_ROUNDS`, and never commits, pushes, merges or touches `main`.
"""
from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LOOP = REPO / "scripts" / "fix_loop.sh"
RULES = REPO / ".hermes" / "skills" / "pr-fix" / "SKILL.md"

sys.path.insert(0, str(REPO / "scripts"))
import fix_bot_report  # noqa: E402


def stub_agent(tmp_path: Path, *, fixes_after: int | None = None, exit_code: int = 0) -> Path:
    """A stand-in for the Hermes CLI: records its stdin, optionally "fixes" the failure.

    `fixes_after=n` makes the agent create the marker file the check looks for on its n-th
    call, which is how the early-stop behaviour is exercised deterministically.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    calls = tmp_path / "agent-calls"
    calls.write_text("")
    marker = tmp_path / "fixed"
    body = f"""#!/usr/bin/env bash
cat >> "{calls}"
printf '\\n__CALL__\\n' >> "{calls}"
n=$(grep -c __CALL__ "{calls}" || true)
"""
    if fixes_after is not None:
        body += f'if [ "$n" -ge {fixes_after} ]; then touch "{marker}"; fi\n'
    body += f"exit {exit_code}\n"
    agent = bin_dir / "hermes"
    agent.write_text(body)
    agent.chmod(agent.stat().st_mode | stat.S_IEXEC)
    return agent


def run_loop(tmp_path: Path, check: str, env: dict | None = None, rules: Path | None = None):
    """Run the real loop in `tmp_path` with a stub agent first on PATH."""
    base = dict(os.environ)
    base["PATH"] = f"{tmp_path / 'bin'}:{base['PATH']}"
    base.update({
        "FIX_CHECK": check,
        "FIX_RULES": str(rules or RULES),
        "FIX_REPORT": str(tmp_path / "report.txt"),
        "FIX_PROMPT": str(tmp_path / "prompt.txt"),
    })
    base.update(env or {})
    return subprocess.run(["bash", str(LOOP)], cwd=str(tmp_path), env=base,
                          capture_output=True, text=True, timeout=120)


def calls(tmp_path: Path) -> str:
    return (tmp_path / "agent-calls").read_text()


# --------------------------------------------------------------------------
# the contract fix-bot.yml relies on
# --------------------------------------------------------------------------

def test_a_green_check_never_invokes_the_agent(tmp_path):
    stub_agent(tmp_path)
    r = run_loop(tmp_path, "true")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "GREEN on the first check" in r.stdout
    assert calls(tmp_path) == "", "a green check must not spend an agent round"


def test_the_loop_stops_as_soon_as_it_is_green(tmp_path):
    stub_agent(tmp_path, fixes_after=1)
    r = run_loop(tmp_path, f"test -f {tmp_path / 'fixed'}")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "GREEN after 1 repair attempt" in r.stdout
    assert calls(tmp_path).count("__CALL__") == 1, "it must not keep repairing a green tree"


def test_it_repairs_twice_when_the_first_round_does_not_stick(tmp_path):
    stub_agent(tmp_path, fixes_after=2)
    r = run_loop(tmp_path, f"test -f {tmp_path / 'fixed'}", env={"FIX_ROUNDS": "3"})
    assert r.returncode == 0, r.stdout + r.stderr
    assert calls(tmp_path).count("__CALL__") == 2
    assert "GREEN after 2 repair attempt(s)" in r.stdout


def test_it_gives_up_loudly_after_five_rounds(tmp_path):
    """Issue #538: the default is five attempts, not three."""
    stub_agent(tmp_path)                      # never fixes anything
    r = run_loop(tmp_path, "false")
    assert r.returncode == 1
    assert calls(tmp_path).count("__CALL__") == 5, "the default is five attempts"
    assert "still RED after 5 repair attempt(s)" in r.stdout
    assert "leaving the PR for a human" in r.stdout


def test_fix_rounds_is_honoured(tmp_path):
    stub_agent(tmp_path)
    r = run_loop(tmp_path, "false", env={"FIX_ROUNDS": "1"})
    assert r.returncode == 1
    assert calls(tmp_path).count("__CALL__") == 1


def test_the_agent_gets_the_failure_output_under_the_preloaded_skills(tmp_path):
    """The prompt carries the RUN; the rules are preloaded as a skill, never inlined again."""

    # Given a failing check
    # When  the loop asks the agent to repair it
    # Then  the prompt points at the preloaded skills and carries the real failure text
    stub_agent(tmp_path)
    r = run_loop(tmp_path, "echo 'boom: assertion failed on line 7'; false")
    assert r.returncode == 1
    prompt = (tmp_path / "prompt.txt").read_text()
    assert "Follow the preloaded skills pr-fix and bot-unattended" in prompt
    assert "boom: assertion failed on line 7" in prompt, "the actual failure must be there"
    # And the rules are NOT copied in: the skill file is the only copy
    assert "Rules for the PR fix-bot agent" not in prompt
    assert "Business logic is never mocked" not in prompt


def test_a_bad_round_count_is_a_loud_misconfiguration(tmp_path):
    stub_agent(tmp_path)
    for bad in ("0", "abc", "-1", "3x"):
        r = run_loop(tmp_path, "false", env={"FIX_ROUNDS": bad})
        assert r.returncode == 2, f"FIX_ROUNDS={bad!r} must be refused"
    assert calls(tmp_path) == "", "nothing may be attempted when the configuration is wrong"


def test_an_empty_round_count_means_the_default(tmp_path):
    """Absent and empty are the same thing for a knob (the sibling repo's convention)."""
    stub_agent(tmp_path)
    r = run_loop(tmp_path, "false", env={"FIX_ROUNDS": ""})
    assert r.returncode == 1
    assert calls(tmp_path).count("__CALL__") == 5, "empty must fall back to the default (5)"


def test_a_missing_agent_binary_is_a_loud_misconfiguration(tmp_path):
    r = run_loop(tmp_path, "false", env={"FIX_AGENT_CMD": "definitely-not-installed-xyz"})
    assert r.returncode == 2
    assert "not found on PATH" in r.stderr


def test_a_missing_contract_file_is_refused(tmp_path):
    """A checkout without the skill must fail before a round is spent, not run blind."""

    # Given FIX_RULES pointing at a file that is not there
    # When  the loop starts
    # Then  it exits 2 and names the missing contract
    stub_agent(tmp_path)
    r = run_loop(tmp_path, "false", rules=tmp_path / "nope.md")
    assert r.returncode == 2
    assert "contract file" in r.stderr


def test_a_non_zero_agent_exit_does_not_skip_the_recheck(tmp_path):
    """A crashed agent must not be treated as a fix: the loop re-checks and still gives up."""
    stub_agent(tmp_path, exit_code=1)
    r = run_loop(tmp_path, "false", env={"FIX_ROUNDS": "1"})
    assert r.returncode == 1
    assert "exited non-zero" in r.stderr


def test_the_loop_never_touches_git(tmp_path):
    """The workflow commits and pushes; the loop must leave the repository alone."""
    stub_agent(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit",
                    "-q", "--allow-empty", "-m", "base"], cwd=tmp_path, check=True)
    before_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path,
                                 capture_output=True, text=True).stdout
    before_status = subprocess.run(["git", "status", "--porcelain"], cwd=tmp_path,
                                   capture_output=True, text=True).stdout
    r = run_loop(tmp_path, "false", env={"FIX_ROUNDS": "1"})
    assert r.returncode == 1
    after_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path,
                                capture_output=True, text=True).stdout
    after_status = subprocess.run(["git", "status", "--porcelain"], cwd=tmp_path,
                                  capture_output=True, text=True).stdout
    assert after_head == before_head, "the loop must not commit"
    assert after_status.split("\n")[0:1] == before_status.split("\n")[0:1], "nor stage anything"
    assert "push" not in r.stdout.lower() and "commit" not in r.stdout.lower()


# --------------------------------------------------------------------------
# the PR comment the workflow posts when it gives up
# --------------------------------------------------------------------------

def test_the_summary_names_the_command_and_fences_the_tail(tmp_path):
    report = tmp_path / "report.txt"
    report.write_text("line 1\nline 2\nassertion failed on line 3\n")
    out = fix_bot_report.summarize(report, "make ci-unit", lines=2)
    assert "make ci-unit" in out
    assert "assertion failed on line 3" in out and "line 1" not in out, "only the tail"
    assert "```" in out, "the log goes in a fence, so a PR comment stays readable"
    assert "does not merge" in out, "the comment must say the bot leaves it for a human"


def test_the_summary_survives_a_missing_report(tmp_path):
    out = fix_bot_report.summarize(tmp_path / "nope.txt", "make ci-unit")
    assert "make ci-unit" in out and "(the report file was empty)" in out


def test_the_bot_runs_in_the_agent_image_not_on_the_runner():
    """The loop must run in the pinned image (issues #222/#238), not on the runner's toolchain.

    The image ref is resolved from THIS commit's Dockerfile hash, so the workflow cannot name a
    tag that drifts from the image it builds, and the secrets travel as run-time env — never
    baked into the image. The workflow drives the loop through make targets (agent-image-ref,
    fix-loop-image) so the same commands are reusable locally and by the pipeline.
    """
    wf = (REPO / ".github" / "workflows" / "fix-bot.yml").read_text()
    mk = (REPO / "Makefile").read_text()
    assert "make agent-image-ref" in wf, "resolve the agent image from the commit via make"
    assert "make fix-loop-image" in wf and "AGENT_IMAGE=" in wf, "the loop runs inside the image via make"
    assert "-e NOUS_API_KEY" in mk and "-e GH_TOKEN" in mk, "secrets pass as run-time env (in the fix-loop-image target)"
    assert "install_hermes_ci.sh" not in wf, (
        "the runner must not install Hermes: the image carries it, which is the whole point"
    )
    dockerfile = (REPO / "containers" / "agent" / "Dockerfile").read_text()
    assert "install_hermes_ci.sh" in dockerfile and "hermes --version" in dockerfile, (
        "the image installs Hermes at build time and proves it"
    )


def test_the_pr_fix_skill_forbids_what_the_issue_forbids():
    """The preloaded skill is the contract with the agent; these are the lines it must carry."""
    rules = RULES.read_text()
    for required in ("mock", "never", "Do not commit, push, merge", "make check-wiring",
                     "AGENTS.md"):
        assert required in rules, f"the skill must state: {required}"
    # And it is a real Hermes project skill, not a bare rules file
    assert rules.startswith("---\nname: pr-fix\n"), "the contract must be a loadable skill"


def test_the_new_make_targets_run_the_exact_commands():
    """The make targets the fix-bot workflow calls must run the exact script commands, so a
    local `make` and the pipeline stay identical (issue #222). `make -n` prints the recipe
    without executing it."""

    def recipe(target: str, **vars) -> str:
        # pass vars as make command-line args (they override the Makefile's own
        # definitions, e.g. REPO := $(shell pwd)); env vars would be ignored
        args = [f"{k}={v}" for k, v in vars.items()]
        r = subprocess.run(["make", "-n", target, *args], cwd=str(REPO),
                           capture_output=True, text=True)
        assert r.returncode == 0, f"make -n {target} failed: {r.stderr}"
        return r.stdout

    # fix-bot-sweep: repo + check + attempts, and --dry when asked
    out = recipe("fix-bot-sweep", REPO="asimov-agent/llgenie", CHECK="make ci-unit", ATTEMPTS=3)
    assert "python3 scripts/fix_bot_sweep.py --repo asimov-agent/llgenie" in out
    assert '--check "make ci-unit"' in out and "--max-attempts 3" in out
    assert "--dry" not in out
    out = recipe("fix-bot-sweep", REPO="asimov-agent/llgenie", DRY=1)
    assert "--dry" in out

    # fix-bot-report: the report path and the check command
    out = recipe("fix-bot-report", REPORT="/tmp/fix-report.txt", CHECK="make ci-unit")
    assert 'python3 scripts/fix_bot_report.py "/tmp/fix-report.txt"' in out
    assert '--command "make ci-unit"' in out

    # agent-image-ref: the agent ref from ci_images
    out = recipe("agent-image-ref")
    assert "python3 scripts/ci_images.py ref agent" in out

    # fix-loop-image: runs the loop inside the agent image, secrets as run-time env
    out = recipe("fix-loop-image", AGENT_IMAGE="ghcr.io/asimov-agent/llgenie/agent:abc123")
    assert "docker run" in out and "scripts/fix_loop.sh" in out
    assert "-e NOUS_API_KEY" in out and "-e GH_TOKEN" in out
    assert "ghcr.io/asimov-agent/llgenie/agent:abc123" in out


def test_the_default_agent_command_reads_the_prompt_through_z():
    """The prompt arrives on STDIN, so the default agent command must consume it with `-z`
    (and name the image's alias; `--provider nous` cannot work with a secret)."""
    script = (REPO / "scripts" / "fix_loop.sh").read_text()
    assert 'FIX_AGENT_CMD:-hermes -z' in script, "the default must be a one-shot"
    assert "$(cat)" in script, "it reads the prompt from stdin"
    assert "-m ${FIX_AGENT_ALIAS:-nous-deepseek}" in script
    assert "--yolo" in script
    cmd_line = next(l for l in script.splitlines() if l.startswith("AGENT_CMD="))
    assert "--provider nous" not in cmd_line, "OAuth-only: a key cannot satisfy it"


def test_a_captured_run_log_is_repaired_and_marked_unverified(tmp_path):
    """A failure taken from the RUN cannot be re-checked here: one attempt, marked UNVERIFIED (#538)."""

    # Given the failed run's captured log (a check this runner cannot reproduce)
    stub_agent(tmp_path)
    log = tmp_path / "failed.log"
    log.write_text("FAILED tests/test_engine_skills.py::test_digest… — AssertionError\n")

    # When  the loop runs with that report
    r = run_loop(tmp_path, "true", env={"FIX_REPORT_FILE": str(log), "FIX_ROUNDS": "2"})

    # Then  it repairs from the log, pushes nothing itself, and says the result is unverified
    assert r.returncode == 0, r.stdout + r.stderr
    assert "UNVERIFIED" in r.stdout, r.stdout
    assert "captured failure log" in r.stdout, r.stdout
