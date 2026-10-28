#!/usr/bin/env python3
"""The TRIGGER half of #824: whichever check `ci.yml` skips, the docs workflow must prove.

`tests/test_ci_scope.py` proves the classifier, that each workflow exists, and that the two path lists
are the same SET. This file covers what a finite sample cannot: it compares the trigger against the
REPOSITORY (`git ls-files`), and it exercises the one code path `scope.yml` runs.
"""
from __future__ import annotations

import fnmatch
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import ci_scope  # noqa: E402


def _on(doc: dict, event: str) -> dict:
    on = doc.get("on") if "on" in doc else doc.get(True)
    return (on or {}).get(event) or {}


def _wf(name: str) -> dict:
    return yaml.safe_load((REPO / ".github" / "workflows" / name).read_text())


def _ignore() -> list[str]:
    return list(_on(_wf("ci.yml"), "pull_request").get("paths-ignore") or [])


def _docs_paths() -> list[str]:
    return list(_on(_wf("docs.yml"), "pull_request").get("paths") or [])


def _subset_glob(path: str, pattern: str) -> bool:
    """GitHub's filter semantics: `*` stops at `/`, a bare pattern is ROOT-only, `**/` is any depth."""
    if pattern.endswith("/**"):
        base = pattern[:-3]
        return path == base or path.startswith(base + "/")
    if pattern.startswith("**/"):
        rest = pattern[3:]
        return fnmatch.fnmatch(path, rest) or fnmatch.fnmatch(path, "*/" + rest)
    if "/" in pattern:
        return fnmatch.fnmatch(path, pattern)
    return "/" not in path and fnmatch.fnmatch(path, pattern)


def _tracked() -> list[str]:
    """Every tracked path, and it FAILS LOUDLY rather than yielding an empty list.

    An empty list would make both invariants below vacuously true — the same silent pass this file
    exists to prevent. A worktree's `.git` is a pointer OUTSIDE the tree, so a container that mounts
    only the worktree has no index: `make test-unit` mounts the parent repo for exactly this reason.
    """
    proc = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True)
    paths = [line for line in proc.stdout.splitlines() if line]
    assert proc.returncode == 0, f"git ls-files failed in {REPO}: {proc.stderr.strip()}"
    assert len(paths) > 500, f"git ls-files returned {len(paths)} paths: the index is unreadable here"
    return paths


def _docs_jobs() -> set[str]:
    """The job families `docs.yml` actually runs, from its own `make` steps."""
    run = " ".join(step.get("run", "") for step in _wf("docs.yml")["jobs"]["docs"]["steps"])
    targets = {token for token in run.split() if token.startswith("ci-") or token.startswith("check-")}
    targets |= {token for token in run.split() if token.startswith("make") and token != "make"}
    return targets


def test_no_ignored_path_needs_a_job_the_docs_workflow_does_not_run():
    """THE invariant, per tracked file: `paths-ignore` may only swallow a diff docs.yml proves.

    `test_ci_scope.py` names four sample paths. This walks all of `git ls-files`, so a markdown file
    added later under a code directory (a skill, a fixture, a contract) cannot silently lose the stage
    its class selects — the failure mode `**/*.md` had for 43 tracked files on #832.
    """
    ignore = _ignore()
    served = {"linux/lint", "macos/lint", "linux/openspec", "macos/openspec", "guard"}
    offenders: list[tuple[str, list[str]]] = []
    for path in _tracked():
        if not any(_subset_glob(path, pattern) for pattern in ignore):
            continue  # ci.yml runs for this path: nothing can be hidden
        classes = set(ci_scope.classify([path]))
        needs = set(ci_scope.jobs_for(classes)) - served
        if needs:
            offenders.append((path, sorted(needs)))

    assert not offenders, (
        "these tracked paths are ignored by ci.yml but their class selects stages the docs workflow "
        f"does not run: {offenders[:10]} ({len(offenders)} total)"
    )


def test_the_two_filters_are_one_decision_over_every_tracked_path():
    """Set equality is pinned in `test_ci_scope.py`; this proves the two lists AGREE on real paths.

    Equality of two pattern lists is not equality of what they match: one glob can shadow another, so
    the pairing is checked path by path, in both directions.
    """
    ignore, docs = _ignore(), _docs_paths()
    unmatched: list[str] = []
    for path in _tracked():
        in_ci = any(_subset_glob(path, p) for p in ignore)
        in_docs = any(_subset_glob(path, p) for p in docs)
        if in_ci != in_docs:
            unmatched.append(path)

    assert not unmatched, (
        "these tracked paths are ignored by one workflow and not the other, so either the matrix or "
        f"the docs gates are missing for them: {unmatched[:10]} ({len(unmatched)} total)"
    )


def test_every_ci_job_and_pipeline_stage_is_named_by_the_classifier():
    """A job added to `ci.yml` that the classifier never names is a family it can never select.

    The classifier names CHECK families (what a reviewer reads in the rollup), so compare against each
    job's `name:` prefix where it has one and the job id otherwise.
    """
    covered = set(ci_scope.ALWAYS) | set(ci_scope.JOBS) | {"ci-images"}

    for stage in (_wf("pipeline.yml")["jobs"] or {}):
        for job in (f"linux/{stage}", f"macos/{stage}"):
            assert job in covered, (job, sorted(covered))

    for job, spec in _wf("ci.yml")["jobs"].items():
        if job in ("linux", "macos"):
            continue  # the reusable pipeline, covered by the stage loop above
        family = str(spec.get("name") or job).split("${{")[0].rstrip("-") or job
        assert family in covered or job in covered, (
            f"ci.yml job {job!r} (check family {family!r}) is named by no classifier entry: "
            f"{sorted(covered)}")


def test_the_cli_diff_path_the_scope_workflow_runs_is_exercised(tmp_path, monkeypatch):
    """`scope.yml` runs `make ci-scope` → `jobs --from <ref>`; every other case passes `--paths`.

    Built in a throwaway repo, so it needs no `origin/main` and can never be skipped (AGENTS.md: a
    skipped test means a broken prerequisite is being masked). The three-dot merge-base read and the
    `git diff` plumbing are what break silently in a real run.
    """
    repo = tmp_path / "r"
    (repo / "docs").mkdir(parents=True)

    def git(*args):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)

    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    (repo / "README.md").write_text("# base\n")
    git("add", "-A")
    git("commit", "-qm", "base")
    (repo / "docs" / "ARCHITECTURE.md").write_text("# docs\n")
    (repo / "scripts").mkdir()
    (repo / "scripts" / "llgenie_serve.py").write_text("x = 1\n")
    git("add", "-A")
    git("commit", "-qm", "docs and a script")

    monkeypatch.chdir(repo)
    assert sorted(ci_scope._paths_from_diff("HEAD~1")) == ["docs/ARCHITECTURE.md", "scripts/llgenie_serve.py"]
    # and the CLI the workflow runs turns that into the union, not the docs subset
    assert ci_scope.main(["jobs", "--from", "HEAD~1"]) == 0
    assert set(ci_scope.scope(ci_scope._paths_from_diff("HEAD~1"))["classes"]) == {"docs", "scripts"}


def test_a_docs_plus_code_diff_selects_the_union():
    """The acceptance criteria's last row: a mixed diff must not lose the code gates to docs."""
    result = ci_scope.scope(["docs/ARCHITECTURE.md", "scripts/llgenie_serve.py"])

    assert {"docs", "scripts"} <= set(result["classes"])
    for job in ("linux/unit", "macos/unit", "linux/install", "linux/openspec"):
        assert job in result["jobs"], job
