"""The engine-bump lane's PR body comes from `make engine-bump-pr-body`, and it satisfies the PR gates (issue #3050).

Two generations of defects live in this file.

Generation one (issues #144, #583): the body was composed in inline bash inside
`.github/workflows/engine-bump.yml`, and the regression was `\\n` arriving in the body as literal text —
every `printf` in the composition had to be single-quoted in the YAML so bash, not the YAML parser, read
the escapes. Those tests extracted the run block's bash, ran the composition in `bash -c`, and compared the
bytes.

Generation two (issue #3050): the same composer appended the optional hard-fail / dependencies lines and the
params documentation review (issue #583) with

    body="$(printf '%b' "${body}" '\\n')$(cat params-review-section.md)"

Command substitution strips TRAILING newlines, so the review glued onto the OpenSpec reference. Measured on
the live body of PR #3030 (head `20b3f030`):

    OPENSPEC: publish-changed-pin-images## Documentation review

`scripts/check_pr_hygiene.py::OPENSPEC_REF` is `^OPENSPEC:\\s+([A-Za-z0-9_-]+)\\s*$` — a name with text glued
after it matches nothing, so `make check-pr-openspec-change` (mk/gates.mk:139) reported "names no existing
change" on 7/7 lanes of the 2026-11-23 wave although `openspec/changes/publish-changed-pin-images/` is ACTIVE
on `main`. The same bodies carried no `## Acceptance criteria`, so `make check-pr-acceptance-form`
(mk/gates.mk:142, issue #1796) redded `scope` on the same 7/7, and their commit messages carried no ticked
mirror for `make check-pr-commit-checkboxes` (mk/gates.mk:135, issue #2519).

The composition therefore moved into `scripts/engine_bump_pr_body.py` behind `make engine-bump-pr-body`. The
regressions are asserted against the seams the workflow now runs: the renderer's bytes, the gate's own
findings functions, and the workflow text that wires them (no inline composer may come back).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from scripts import acceptance_writeback  # one import root, issue #1101; paths via tests/conftest.py

from scripts import check_pr_acceptance as ca
from scripts import check_pr_closing as cpc
from scripts import check_pr_hygiene as hy
from scripts import engine_bump_pr_body as rend

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github/workflows/engine-bump.yml"
MK_ENGINES = REPO_ROOT / "mk/engines.mk"

_OS_ENV = (
    "ID=ollama\n"
    "OLD=02480ca2a47153e1f9c31cbe1e05536da97ce1ba\n"
    "NEW=02480ca2a47153e1f9c31cbe1e05536da97ce1ba\n"
    "REF=v0.40.15\n"
)
_REPO = "acme/llgenie"
_RUN = "45242589912"
_AUTHOR = "Author: Asimov Agent <support@docondee.com>"  # the value `make -s git-identity-line` emits (issue #840)
_ENGINE = "ollama"

#: The facts block, unchanged from the composer this seam replaces (issue #144's shape: real newlines,
#: `**bold**` markers rendered for real).
_EXPECTED_FACTS = (
    f"{_AUTHOR}\n\n"
    "Automated engine pin bump (issue #107).\n\n"
    "- **Engine:** `ollama`\n"
    "- **Pin:** `02480ca2` -> `02480ca2` (`v0.40.15`)\n"
    "- **Compare:** https://github.com/acme/llgenie/compare/"
    "02480ca2a47153e1f9c31cbe1e05536da97ce1ba...02480ca2a47153e1f9c31cbe1e05536da97ce1ba\n"
    "- CI builds and tests ONLY this engine's images. A red PR means the new commit needs a manual skill fix."
)

_REVIEW_SECTION = "## Documentation review\n\n### docs/build.md\n\nflag table\n"


def _render(**kw) -> str:
    kw.setdefault("engine", _ENGINE)
    kw.setdefault("ref", "v0.40.15")
    kw.setdefault("old_sha", "02480ca2a47153e1f9c31cbe1e05536da97ce1ba")
    kw.setdefault("new_sha", "02480ca2a47153e1f9c31cbe1e05536da97ce1ba")
    kw.setdefault("run_id", _RUN)
    kw.setdefault("author", _AUTHOR)
    kw.setdefault("repo_slug", _REPO)
    return rend.render_body(**kw)


def _messages(body_made_of_newlines: bool = True) -> list[str]:
    """The bump commit's own messages (issue #1588), plus the renderer's acceptance mirror."""
    msg = (
        "Automated engine pin bump (weekly rolling pin; closes no issue): found v0.40.15 at 02480ca2, "
        "pinned at 02480ca2.\n\n"
        "Fix: re-derived the install recipe at v0.40.15 and applied it to SKILL.md, the frozen per-arch "
        "Dockerfiles, the params and the Strata model list.\n\n"
        "Benefit: llgenie builds and serves this engine at the upstream release instead of a stale pin.\n\n"
        "Technical: make engine-bump ENGINE=ollama (derive -> pin -> apply -> make generate-engine-params). "
        "CI builds and tests the images of this engine only; a red PR means the new upstream commit needs a "
        "manual skill fix."
    )
    out = ["chore(engine): bump ollama to v0.40.15@02480ca2", msg]
    if body_made_of_newlines:
        out.append(rend.acceptance_block(_ENGINE, _RUN, heading=rend.COMMIT_ACCEPTANCE_HEADING))
    return out


# ---------- generation one: the body's shape ----------

def test_pr_body_has_real_newlines_not_literal_backslash_n():
    body = _render()
    assert body.startswith(_EXPECTED_FACTS), body[:600]
    assert "\\n" not in body, "double-quoted YAML printf put a literal \\n in the body (issue #144)"
    assert "\n\n- **Engine:** `ollama`\n" in body, "bold markers were not rendered"
    assert "- **Pin:** `02480ca2` -> `02480ca2` (`v0.40.15`)" in body
    assert "Automated engine pin bump (issue #107)." in body
    assert body.endswith("OPENSPEC: publish-changed-pin-images\n")


def test_hard_fail_appends_a_warning_paragraph():
    body = _render(hard_fail="cuda flag --x was not advertised")
    assert body.startswith(_EXPECTED_FACTS)
    assert (
        "> ⚠️ **Manual review required:** a build parameter could not be auto-derived — "
        "cuda flag --x was not advertised. The pin is bumped and the PR is open; CI will go red on the "
        "build until the skill is fixed by hand."
    ) in body
    # the reference stays last, after the appended warning
    assert body.endswith("OPENSPEC: publish-changed-pin-images\n")


def test_no_hard_fail_no_warning():
    assert "Manual review required" not in _render()


def test_dependency_line_appends():
    body = _render(deps="llama.cpp moved to 0.13.0")
    assert body.startswith(_EXPECTED_FACTS)
    assert "- **Dependencies:** llama.cpp moved to 0.13.0" in body
    assert body.endswith("OPENSPEC: publish-changed-pin-images\n")


def test_generated_commit_message_does_not_trip_the_closing_gate():
    """Issue #1588's rule, now including the acceptance mirror paragraph."""
    title = "chore(engine): bump ollama to v0.13.0"
    messages = _messages()
    claims = cpc.claims_in(messages, None, title)
    assert claims == set(), f"the generated commit claims issue(s) {sorted(claims)}"
    findings = cpc.check_squash(messages, "", title)
    assert findings == [], findings


# ---------- generation two: the gate findings the inline composer produced ----------

def test_the_openspec_reference_survives_the_documentation_review():
    body = _render(review_section=_REVIEW_SECTION)
    # the exact measured defect: the heading glued onto the change name
    assert "publish-changed-pin-images##" not in body
    assert "\n\n## Documentation review\n" in body
    lines = [ln for ln in body.splitlines() if ln.startswith("OPENSPEC:")]
    assert lines == ["OPENSPEC: publish-changed-pin-images"], lines
    # and the gate's OWN regex reads the name back out of the composed body
    assert hy.OPENSPEC_REF.findall(body) == ["publish-changed-pin-images"], body[-200:]


def test_the_body_carries_the_acceptance_checklist_the_scope_gate_reads():
    body = _render(review_section=_REVIEW_SECTION)
    # `acceptance_writeback.acceptance_items` is the parser `pr_acceptance_form_findings` reuses (#1796)
    items = acceptance_writeback.acceptance_items(body)
    assert items, "the composed body has no tickable acceptance checklist (issue #1796)"
    for line in items:  # `acceptance_items` returns the checkbox lines themselves
        assert line.lstrip().startswith("- [x]"), line
        assert ca._is_provable_tick(line), line
    # every tick names a CI run or a command+rc+sha, or the self-tick audit (#745) reddens it
    assert all(ca._is_provable_tick(ln) for ln in items), items


def test_the_commit_text_mirrors_the_body_ticks():
    body = _render(review_section=_REVIEW_SECTION)
    assert hy.commit_text_findings(_messages(), body) == []


def test_a_commit_without_the_mirror_is_refused():
    body = _render()
    findings = hy.commit_text_findings(_messages(body_made_of_newlines=False), body)
    assert [i["key"] for i in findings] == ["commit-acceptance-unmirrored"], findings


def test_the_cli_writes_the_body_and_the_commit_mirror(tmp_path):
    out, commit_out = tmp_path / "pr-body.md", tmp_path / "commit-acceptance.md"
    rc = rend.main(
        [
            "--engine", _ENGINE, "--ref", "v0.40.15",
            "--old", "02480ca2a47153e1f9c31cbe1e05536da97ce1ba",
            "--new", "02480ca2a47153e1f9c31cbe1e05536da97ce1ba",
            "--run", _RUN, "--author", _AUTHOR, "--repo-slug", _REPO,
            "--review-file", str(tmp_path / "params-review-section.md"),
            "--out", str(out), "--commit-out", str(commit_out),
        ]
    )
    assert rc == 0
    body = out.read_text()
    mirror = commit_out.read_text().strip()
    assert body.endswith("OPENSPEC: publish-changed-pin-images\n")
    assert mirror.splitlines()[0] == rend.COMMIT_ACCEPTANCE_HEADING
    # a missing review file is not a failure: the lane's review step is optional
    assert acceptance_writeback.acceptance_items(body)
    assert hy.commit_text_findings(_messages()[:2] + [mirror], body) == []


# ---------- the seams the workflow actually runs ----------

def _step_run(job_name: str, step_name: str) -> str:
    wf = yaml.safe_load(WORKFLOW.read_text())
    steps = wf["jobs"][job_name]["steps"]
    try:
        return next(s["run"] for s in steps if s.get("name") == step_name)
    except StopIteration:
        raise AssertionError(f"step {step_name!r} not found in job {job_name!r}") from None


def test_the_body_renderer_is_wired_through_make():
    """AGENTS.md: a workflow runs a make target, never a raw script; every script is wired to a target."""
    run = _step_run("bump", "Open / update the bump PR")
    assert "make engine-bump-pr-body" in run, run[:800]
    assert "OUT=/tmp/pr-body.md" in run
    assert "COMMIT_OUT=/tmp/commit-acceptance.md" in run
    target = MK_ENGINES.read_text()
    assert "engine-bump-pr-body:" in target
    assert "scripts/engine_bump_pr_body.py" in target


def test_the_inline_body_composer_is_gone():
    """The bug was in the composition, so the composition is not allowed back into the YAML.

    Only executable lines are inspected: the step's own comment names the old composer so a reader
    knows why the seam exists.
    """
    run = _step_run("bump", "Open / update the bump PR")
    code = "\n".join(ln for ln in run.splitlines() if not ln.lstrip().startswith("#"))
    for banned in (
        "body=$(printf",
        "body=\"$(printf",
        "$(cat params-review-section.md)",
        "scripts/engine_bump_pr_body.py",  # only through the make target
    ):
        assert banned not in code, f"{banned!r} came back into the workflow"


# ---------- measured evidence path (issue #3054) ----------
#
# The composer used to ASSUME the acceptance boxes were true: it always ticked three items naming
# `run_id`. The restamp leg (#3054) measures the evidence at the PR head first and hands the composer
# exactly the items it proved, so a box exists only when its proof was read.

_MEASURED_HEAD = "4958f3953a01cc6da8893044842c3dec4b1fd2c2"
_MEASURED = [
    f"- [x] the bump commit changes only this engine's pinned paths "
    f"(proven: git show --name-only {_MEASURED_HEAD} rc=0 at head {_MEASURED_HEAD})",
    f"- [x] the engine skill file and the params file name the new pin at the head "
    f"(proven: gh api repos/acme/llgenie/git/blobs/deadbeef rc=0 at head {_MEASURED_HEAD})",
]
_NOT_COVERED = (
    f"the ollama image gap (engine-build-cpu conclusion=failure, head {_MEASURED_HEAD[:12]}) "
    "— tracked in #3065"
)


def _measured_cli(tmp_path):
    items = tmp_path / "items.md"
    items.write_text("\n".join(_MEASURED) + "\n")
    out, commit_out = tmp_path / "pr-body.md", tmp_path / "commit-acceptance.md"
    rc = rend.main(
        [
            "--engine", _ENGINE, "--ref", "v0.40.15",
            "--old", "02480ca2a47153e1f9c31cbe1e05536da97ce1ba",
            "--new", "02480ca2a47153e1f9c31cbe1e05536da97ce1ba",
            "--run", _RUN, "--author", _AUTHOR, "--repo-slug", _REPO,
            "--head", _MEASURED_HEAD, "--image-run", "cpu=45242586633",
            "--items-file", str(items), "--not-covered", _NOT_COVERED,
            "--out", str(out), "--commit-out", str(commit_out),
        ]
    )
    return rc, out.read_text(), commit_out.read_text().strip()


def test_measured_items_replace_the_assumed_ones_and_stay_provable(tmp_path):
    rc, body, _mirror = _measured_cli(tmp_path)
    assert rc == 0
    items = acceptance_writeback.acceptance_items(body)
    assert items == _MEASURED, items
    assert all(ca._is_provable_tick(line) for line in items), items
    # every clause is head-flagged: a later commit cannot leave an earlier tick describing a stale head
    assert all(_MEASURED_HEAD in line for line in items), items
    assert "## Not covered" in body and "#3065" in body
    assert body.endswith("OPENSPEC: publish-changed-pin-images\n")


def test_the_commit_mirror_carries_the_same_measured_items(tmp_path):
    _rc, body, mirror = _measured_cli(tmp_path)
    assert mirror.splitlines()[0] == rend.COMMIT_ACCEPTANCE_HEADING
    for line in _MEASURED:
        assert line in mirror, mirror
    assert hy.commit_text_findings(_messages()[:2] + [mirror], body) == []


def test_an_items_file_leaves_no_assumed_image_box_behind(tmp_path):
    _rc, body, _mirror = _measured_cli(tmp_path)
    # the assumed third item ("CI builds and tests ... run=<id>") must not survive next to measured ones
    assert "built and tested by CI run" not in body, body
    assert body.count("## Acceptance criteria") == 1


def test_composer_run_block_is_valid_bash(tmp_path):
    """REQ-3 of issue #144 still holds for the step: the run block parses as bash."""
    run = _step_run("bump", "Open / update the bump PR")
    script = _OS_ENV + "\n" + run.replace("${{ github.repository }}", _REPO).replace(
        "${{ github.run_id }}", _RUN
    ) + "\n"
    path = tmp_path / "composer.sh"
    path.write_text(script)
    r = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
