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


def test_no_workflow_filters_markdown_by_extension():
    """`**/*.md` is this bug's signature (#824): markdown here is not documentation by extension.

    A filter that matches every markdown file swallows `data/trending-README.md` (read by
    `sync_registry.py`), `.hermes/skills/**/SKILL.md` (the legs' contracts),
    `skills/engines/**/SKILL.md` (what `generate-engine-params` reads) and `tests/fixtures/**/*.md`
    (unit fixtures). This fails on ANY workflow that tries it again, not just on `ci.yml`.
    """

    import yaml

    base = REPO / ".github" / "workflows"
    offenders: list[str] = []
    for path in sorted(base.glob("*.yml")):
        doc = yaml.safe_load(path.read_text()) or {}
        on = doc.get("on") if "on" in doc else doc.get(True)
        if not isinstance(on, dict):
            continue
        for event, cfg in on.items():
            if not isinstance(cfg, dict):
                continue
            for key in ("paths", "paths-ignore"):
                for entry in cfg.get(key) or []:
                    if str(entry).strip().strip('"').strip("'") in ("**/*.md", "*.md"):
                        offenders.append(f"{path.name}:{event}:{key}: {entry}")
    assert not offenders, offenders

def test_scope_runs_on_every_event_and_falls_back_to_main():
    """The reporting check must EXIST on the refs where the diff is least ordinary (issue #824).

    A merge-queue ref, a force-push and a manual dispatch are the runs where nobody knows the diff
    shape, so a `scope` trigger limited to `pull_request` silently removes the one artifact that says
    which stages were skipped and why. `github.base_ref` is EMPTY on `merge_group` and
    `workflow_dispatch`, so the step must fall back to `main` — without it the classifier diffs against
    `origin/` and dies before the widening in `ci_scope.py` can run.
    """

    # Given the scope workflow
    doc = _wf("scope.yml")
    on = doc.get("on") if "on" in doc else doc.get(True)

    # Then  it listens to the three events …
    assert {"pull_request", "merge_group", "workflow_dispatch"} <= set(on), sorted(on)
    # … and NONE of them is path-filtered, or the check vanishes when it is most needed
    for event, cfg in on.items():
        assert not (cfg or {}).get("paths"), (event, cfg)
        assert not (cfg or {}).get("paths-ignore"), (event, cfg)

    # And every step that runs the classifier falls back to `main` for the empty base ref. TWO spellings
    # are legitimate — `${{ github.base_ref || 'main' }}` and a shell default `${EVENT_BASE_REF:-main}`
    # — so this asserts the BEHAVIOUR, not one spelling: checking the expression alone false-reds a
    # correct implementation that uses the shell form, which is what this test did when first written.
    runs = [s for s in doc["jobs"]["scope"]["steps"] if "ci-scope" in (s.get("run") or "")]
    assert runs, [s.get("name") for s in doc["jobs"]["scope"]["steps"]]
    for step in runs:
        env_blob = " ".join(str(v) for v in (step.get("env") or {}).values())
        body = step.get("run") or ""
        assert ("|| 'main'" in env_blob) or (":-main" in body) or (":-main" in env_blob), (
            step.get("name"), env_blob, body[:200])
        # … and the fallback must be USED when fetching/diffing, not merely declared
        assert "main" in body, (step.get("name"), body[:200])

    # And the exemption the dispatch-form gate demands is present at column 0 of the raw file
    raw = (REPO / ".github" / "workflows" / "scope.yml").read_text().splitlines()
    assert any(l.startswith("# dispatch: no inputs") for l in raw), "missing `# dispatch: no inputs` line"
