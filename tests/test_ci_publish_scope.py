"""A fork PR builds and tests its engine image, and never fails on a write it cannot be granted (#155).

`make push-engine` is a step of every `engine-image-*` job, and a `pull_request` run carries a token
scoped to the BASE repository: a same-repo head can write this repository's packages, a FORK head
cannot, and GitHub REFUSES the write. Measured on PR #651 (`andyholst:feat/sglang-version-not-pin`,
run 40339517705), both engine-image jobs, on a branch whose build and post-build test had passed:

    denied: installation not allowed to Write organization package
    [engine-image] FAIL push ghcr.io/asimov-agent/llgenie/sglang:35ce3132-5d1a4f11-cuda

The job then went red on a permission GitHub will never grant a fork PR. The policy lives in
`scripts/engine_image.py::push` — not in a workflow `if:`, because a scenario-scoped step condition
is exactly what `tests/test_ci_images.py::test_no_ci_step_or_job_is_skipped` forbids. So: a
`pull_request` run whose push is DENIED for that reason skips the publish with a loud named warning;
a push run, or any other failure, still fails.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

from scripts import engine_image as ei

REGISTRY = "ghcr.io/asimov-agent"
#: The exact line GHCR answered on PR #651 (run 40339517705, engine-image-sglang-cuda).
DENIED = ("ae8a69caad45: Waiting\n"
          "denied: installation not allowed to Write organization package")
SPEC = {"id": "sglang", "tag": "llgenie/sglang:35ce3132-5d1a4f11-cuda", "variant": "cuda",
        "params_file": "containers/engines/params/sglang.json"}


def _push(monkeypatch, event: str, push_output: str, push_rc: int) -> tuple[int, list[list[str]]]:
    """Run the real `push()` with a runtime that builds, tests and then answers `push_output`."""
    monkeypatch.setattr(ei, "REGISTRY", REGISTRY)
    monkeypatch.setenv("GITHUB_EVENT_NAME", event)
    monkeypatch.setattr(ei, "image_exists", lambda tag: True)
    monkeypatch.setattr(ei, "test_image", lambda spec: 0)
    monkeypatch.setattr(ei, "publish_refs", lambda spec: [f"{REGISTRY}/{spec['tag']}",
                                                          f"{REGISTRY}/llgenie/sglang:cuda"])
    calls: list[list[str]] = []

    def fake_sh(cmd, **kw):
        calls.append(cmd)
        if cmd[1] == "push":
            return subprocess.CompletedProcess(cmd, push_rc, "", push_output)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(ei, "_sh", fake_sh)
    return ei.push(dict(SPEC)), calls


def test_a_fork_pr_skips_the_publish_it_cannot_be_granted(monkeypatch, capsys):
    """`denied: … Write organization package` inside a pull_request run is a skip, not a failure."""

    # Given a pull_request run whose push is refused exactly as GHCR refused PR #651
    rc, calls = _push(monkeypatch, event="pull_request", push_output=DENIED, push_rc=1)

    # When  the real push() has run
    out = capsys.readouterr().out

    # Then  it exits 0 — the job stays green — and the skip is a warning that names the ref and #155
    assert rc == 0, out
    assert "::warning title=publish skipped::" in out
    assert "SKIP publish" in out and "issue #155" in out
    assert "FAIL push" not in out
    assert any(c[1] == "push" for c in calls)  # it did try: the refusal is real, not assumed


def test_a_push_run_that_is_denied_still_fails(monkeypatch, capsys):
    """A push run's token CAN write, so a denial there is a real failure and must stay one."""

    # Given a push run whose publish is refused
    rc, _ = _push(monkeypatch, event="push", push_output=DENIED, push_rc=1)

    # When  the real push() has run
    out = capsys.readouterr().out

    # Then  it fails loudly, and never calls it a skip
    assert rc == 1, out
    assert "FAIL push" in out
    assert "SKIP publish" not in out and "::warning" not in out


def test_a_pull_request_denied_for_another_reason_still_fails(monkeypatch, capsys):
    """Only the write-permission denial is a skip: a network error or a bad tag is a defect."""

    # Given a pull_request run whose push fails for a reason that is not the fork permission
    rc, _ = _push(monkeypatch, event="pull_request",
                  push_output="error: unauthorized: authentication required", push_rc=1)

    # When  the real push() has run
    out = capsys.readouterr().out

    # Then  it fails: a permission we cannot prove is the fork case is never silently forgiven
    assert rc == 1, out
    assert "FAIL push" in out
    assert "SKIP publish" not in out


def test_a_successful_publish_is_unchanged(monkeypatch, capsys):
    """The happy path still tags and pushes every ref and reports each one."""

    # Given a run whose pushes are accepted
    rc, calls = _push(monkeypatch, event="pull_request", push_output="", push_rc=0)

    # When  the real push() has run
    out = capsys.readouterr().out

    # Then  both refs are pushed and reported, with no skip and no warning
    assert rc == 0, out
    assert sum(1 for c in calls if c[1] == "push") == 2
    assert out.count("[engine-image] pushed ") == 2
    assert "SKIP" not in out and "::warning" not in out
