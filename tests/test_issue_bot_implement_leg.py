"""The issue-bot's implement leg must not die between "the work is done" and "the PR exists" (#770).

Two measured runs died at that seam, for two different reasons, and each one manufactured a phantom
claim: the leg reported `changed=true (make implement-issue rc=0)` and `PR: none opened`, so the issue
looked implemented while its branch 404'd.

* **run 40673131217, head `ea80ab49` (#769)** — `git add -A` died with
  `error: insufficient permission for adding an object to repository database .git/objects` /
  `fatal: updating files failed` / exit 128. The agent leg runs in a container as root, so the objects
  it writes into the mounted checkout are root-owned and the runner's `git add` cannot insert into them.
  Nothing to do with the commit-author allowlist or `BUMP_TOKEN` — the identity block ran fine.
* **run 40591197166, head `b06f606d` (#759)** — the branch pushed, then the LAST step refused the PR:
  `[issue-implementer] pr-body.md cannot become a PR body: `Technical:` states nothing` (exit 2). The
  gate was right; the leg had no way to notice until the whole gate suite had already passed.

So this file locks three things: the ownership repair (in the make target AND defensively in the
workflow step, before `git add`), and the pr-body check running where the leg can still act on it.

The ownership repair's end-to-end proof is a real `issue-bot` run (the unit suite has no container
engine); what is provable here is the recipe and the step ORDER, which is what was wrong.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import issue_implementer as ii  # noqa: E402

from conftest import makefiles_text  # noqa: E402  (the include-resolving Makefile reader)
MAKEFILE = makefiles_text()
WORKFLOW = (REPO / ".github" / "workflows" / "issue-bot.yml").read_text()
STEPS = {s.get("name"): s for s in yaml.safe_load(WORKFLOW)["jobs"]["implement"]["steps"] if s.get("name")}


def _recipe(target: str) -> str:
    """One target's recipe, from the Makefile text."""
    marker = f"\n{target}:"
    assert marker in MAKEFILE, f"{target} is not a target"
    return MAKEFILE.split(marker, 1)[1].split("\n\n", 1)[0]


# ---- the pr-body check: fail where the leg can still act -------------------------

GOOD = """Issue: #770 was chosen as actionable by the issue-bot.

Fix: the implement leg repairs ownership of the checkout and validates its PR body before pushing.

Benefit: a leg that finished its work lands a reviewable PR instead of a phantom claim.

Technical: make agent-repo-ownership chowns the mount; make issue-bot-pr-body-check runs check-body.
"""

#: The rulebook measurement the PR body is stamped from at open (issues #792/#845/#2050).
RECORD = {
    "main": "cb6c56a955124d58818d595bca34c4d60745c0ab",
    "agents_bytes": 91766,
    "agents_lines": 1363,
    "agents_headings": 42,
    "agents_headings_sha256": "0" * 64,
}


def test_a_body_with_an_empty_technical_part_is_refused_by_name(tmp_path):
    # Given the #759 shape: every part present, `Technical:` empty
    body = tmp_path / "pr-body.md"
    body.write_text(GOOD.replace(
        "Technical: make agent-repo-ownership chowns the mount; make issue-bot-pr-body-check runs check-body.",
        "Technical:"))

    # When  the check the implement leg now runs reads it
    proc = subprocess.run([sys.executable, str(REPO / "scripts" / "issue_implementer.py"),
                           "check-body", "--body-file", str(body), "--issue", "770"],
                          capture_output=True, text=True)

    # Then  it exits non-zero and names the part, not the whole file
    assert proc.returncode == 1
    assert "`Technical:` states nothing" in proc.stderr, proc.stderr


def test_a_complete_body_passes_and_a_missing_file_is_loud(tmp_path):
    # Given a complete body, and no body at all
    good = tmp_path / "pr-body.md"
    good.write_text(GOOD)
    missing = tmp_path / "nope.md"

    # When  each is checked
    ok = subprocess.run([sys.executable, str(REPO / "scripts" / "issue_implementer.py"),
                         "check-body", "--body-file", str(good), "--issue", "770"],
                        capture_output=True, text=True)
    absent = subprocess.run([sys.executable, str(REPO / "scripts" / "issue_implementer.py"),
                             "check-body", "--body-file", str(missing)],
                            capture_output=True, text=True)

    # Then  the complete one passes, and the absent one says the leg must write it
    assert ok.returncode == 0, ok.stderr
    assert absent.returncode == 1
    assert "does not exist" in absent.stderr and "must write it" in absent.stderr


def test_body_problems_is_the_one_rule_both_paths_share():
    # Given one body with an empty `Benefit:` and one complete body
    empty_benefit = "Issue: #1\nFix: x\nBenefit:\nTechnical: y\n"

    # When  the helper (the leg's pre-check) and the renderer (the open-pr path) read them
    problems = ii.body_problems(empty_benefit)

    # Then  the same rule fires in both callers, naming the part that states nothing
    assert problems == ["`Benefit:` states nothing"]
    assert ii.body_problems(GOOD) == []
    with pytest.raises(SystemExit) as exc:
        ii.render_pr_body(empty_benefit, 1, "a | 1 +", RECORD)
    assert "`Benefit:` states nothing" in str(exc.value)


# ---- the ownership repair, in the recipe and in the step that stages the work ----

def test_the_implement_recipe_repairs_ownership_and_checks_the_body_before_returning():
    # Given the implement leg's recipe
    recipe = _recipe("implement-issue")

    # When  the containerized agent step has returned
    # Then  the ownership repair runs, then the pr-body check — in that order, both via make
    assert "$(MAKE) --no-print-directory agent-repo-ownership" in recipe, recipe
    assert "$(MAKE) --no-print-directory issue-bot-pr-body-check" in recipe, recipe
    assert recipe.index("agent-repo-ownership") < recipe.index("issue-bot-pr-body-check")


def test_agent_repo_ownership_chowns_the_mount_to_the_invoking_user():
    # Given the repair target
    recipe = _recipe("agent-repo-ownership")

    # When  it runs in the pinned agent image (as root, which is what the leg left behind)
    # Then  it chowns the whole mount back to the uid/gid that invoked make
    assert "--entrypoint chown" in recipe
    assert "$(AGENT_IMAGE)" in recipe
    assert "-R $(shell id -u):$(shell id -g) /repo" in recipe
    assert '$(OWNERSHIP_DIR):/repo' in recipe
    # And it is a declared .PHONY target, so a file named after it cannot shadow it
    assert "agent-repo-ownership" in MAKEFILE.split(".PHONY:", 1)[1].split("\n\n", 1)[0]


def test_the_push_step_repairs_ownership_before_it_stages_anything():
    # Given the workflow step that commits and pushes the branch
    run = STEPS["Commit + push the feature branch"]["run"]

    # When  it runs on a checkout a root-owned container leg has touched
    # Then  the repair comes BEFORE `git add`, or the add dies with exit 128 (issue #770)
    assert "sudo chown -R" in run, run
    assert run.index("sudo chown -R") < run.index("git add -A"), run


def test_the_pr_body_check_is_wired_into_make_and_documented():
    # Given the new gate
    recipe = _recipe("issue-bot-pr-body-check")

    # When  a reader runs `make help` / a workflow calls it
    # Then  it is phony, it calls the one script that owns the rule, and it fails when no body exists
    assert "issue-bot-pr-body-check" in MAKEFILE.split(".PHONY:", 1)[1].split("\n\n", 1)[0]
    assert "scripts/issue_implementer.py check-body" in recipe
    assert "exit 1" in recipe
