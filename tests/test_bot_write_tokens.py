#!/usr/bin/env python3
"""A bot's write uses the credential that can make it (issue #412).

Two bot legs were red or dead for a credential reason, not a code reason:

* `issue-refiner` (every scheduled run): its claim comment was refused —
  `GraphQL: Resource not accessible by personal access token (addComment)`.
* `fix-bot`'s sweep: `gh workflow run` was refused —
  `HTTP 403: Resource not accessible by personal access token .../dispatches`.

Both steps were handed `secrets.BUMP_TOKEN`, an owner PAT scoped for pushing a branch and opening a PR,
while the job's own `permissions:` block already granted the write they needed (`issues: write`,
`actions: write`). `github.token` is scoped to this repository and those permissions; the PAT is not.

These tests lock the split that must hold:
  * a step that WRITES an issue/PR comment, a label, or dispatches a workflow -> `github.token`,
    and its workflow/job must declare the write it uses;
  * a step that PUSHES a branch -> the owner PAT (a `GITHUB_TOKEN` push does not re-trigger CI).
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

WF = Path(__file__).resolve().parent.parent / ".github" / "workflows"
TOKEN = "${{ github.token }}"

#: (workflow, a phrase that identifies the writing step, the permission it needs)
ISSUE_WRITE_STEPS = [
    ("issue-refiner.yml", "make issue-refiner-pick", "issues"),
    ("issue-refiner.yml", "make issue-refiner-apply", "issues"),
    ("issue-refiner.yml", "issue-refiner reviewed this issue", "issues"),
    ("issue-bot.yml", "make issue-bot-verdict", "issues"),
    ("queued-alarm.yml", "make queued-alarm", "issues"),
    ("run-failure-reactor.yml", "make run-failure-reactor", "issues"),
]

DISPATCH_STEPS = [
    ("fix-bot.yml", "make fix-bot-sweep", "actions"),
    ("run-failure-reactor.yml", "make run-failure-reactor", "actions"),
]


def workflow(name: str) -> dict:
    return yaml.safe_load((WF / name).read_text())


def steps_of(wf: dict) -> list[tuple[str, dict, dict]]:
    """(job name, job, step) for every step in the workflow."""
    out = []
    for job_name, job in (wf.get("jobs") or {}).items():
        for step in job.get("steps") or []:
            out.append((job_name, job, step))
    return out


def find_step(name: str, phrase: str):
    for job_name, job, step in steps_of(workflow(name)):
        if phrase in (step.get("run") or "") or phrase in (step.get("name") or ""):
            return job_name, job, step
    raise AssertionError(f"{name}: no step mentions {phrase!r}")


def permission(job: dict, wf: dict, key: str) -> str:
    job_perm = ((job.get("permissions") or {}) or {}).get(key)
    wf_perm = ((wf.get("permissions") or {}) or {}).get(key)
    return job_perm or wf_perm or "none"


def test_every_issue_writing_step_uses_the_repo_scoped_token():
    """The comment/label steps must use github.token — the PAT cannot comment at all."""
    for name, phrase, _need in ISSUE_WRITE_STEPS:
        # Given the workflow that owns the writing step
        wf = workflow(name)
        job_name, job, step = find_step(name, phrase)

        # When  the credential that step is handed is read
        token = ((step.get("env") or {}) or {}).get("GH_TOKEN", "")

        # Then  it is the repository-scoped token, never the owner PAT
        assert token == TOKEN, (
            f"{name}:{job_name} ({phrase}) is handed {token!r}; an issue write needs {TOKEN} "
            f"(secrets.BUMP_TOKEN has no Issues write — issue #412)"
        )


def test_every_writing_step_has_the_permission_it_uses():
    """A step handed github.token fails unless its job declares the write it performs."""
    for name, phrase, need in ISSUE_WRITE_STEPS + DISPATCH_STEPS:
        # Given a writing step and the permission it needs
        wf = workflow(name)
        job_name, job, _step = find_step(name, phrase)

        # When  the job's effective permissions are resolved
        granted = permission(job, wf, need)

        # Then  the permission is write, so github.token can actually do it
        assert granted == "write", (
            f"{name}:{job_name} needs `{need}: write` for {phrase!r}, has {granted!r}"
        )


def test_a_push_still_uses_the_owner_pat():
    """A GITHUB_TOKEN push does not re-trigger CI, so a pushing job keeps the PAT.

    The credential a `git push` actually uses is the one `actions/checkout` persisted in the repo's
    remote URL — `GH_TOKEN` only authenticates the `gh` CLI. So the check accepts either: the step/job
    env carries the PAT, or the job's checkout step was given it.
    """
    pushes = []
    for name in ("issue-bot.yml", "fix-bot.yml", "rebase-bot.yml", "engine-bump.yml", "registry-sync.yml"):
        wf = workflow(name)
        for job_name, job, step in steps_of(wf):
            if re.search(r"git push", step.get("run") or ""):
                pushes.append((name, job_name, job, step))

    # Then  at least one push exists per pushing workflow, and each is backed by the PAT
    assert pushes, "no pushing step found — the check would pass vacuously"
    for name, job_name, job, step in pushes:
        step_token = (step.get("env") or {}).get("GH_TOKEN") or ""
        job_token = (job.get("env") or {}).get("GH_TOKEN") or ""
        checkout = [s for s in (job.get("steps") or []) if "actions/checkout" in (s.get("uses") or "")]
        checkout_token = ((checkout[0].get("with") or {}).get("token") if checkout else "") or ""
        backing = step_token or job_token or checkout_token
        assert "BUMP_TOKEN" in backing or "BUMP_TOKEN" in checkout_token, (
            f"{name}:{job_name} pushes and nothing in the job carries the owner PAT "
            f"(step={step_token!r}, job={job_token!r}, checkout={checkout_token!r})"
        )
