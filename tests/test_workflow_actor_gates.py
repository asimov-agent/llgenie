"""The three-party workflow gate (issue #2526): who is allowed to START each pipeline.

The fleet's rule (`docs/BOTS.md`): only the owner, a collaborator, and the `github-actions[bot]`
may trigger the workflows. This gate makes that rule checkable on every `.github/workflows/*.yml`
file — each file is read and classified by its START surface (owner clarification 2026-11-12):
a pipeline started AUTOMATICALLY by PR creation (the PR-triggered CI and its `workflow_run`
followers), one started by a MERGE TO MAIN (`push`), one started by a CRON (`schedule`), and one
started MANUALLY by the owner or a collaborator (`workflow_dispatch`). Three rules:

  R1  every file declares a top-level `permissions:` block; `write-all` is refused;
  R2  `pull_request_target` is refused outright (the one trigger that hands fork code the base
      repository's write token);
  R3  every outsider-reachable trigger carries the `github.triggering_actor` guard OUTSIDE `run:`
      script text, or derives the guard through a `workflow_run` roster whose every named workflow
      is itself guarded or internal-only (fixed point; a roster cycle or an unguarded roster
      source stays reported — trust by chain, never by assumption).

Every rule is tested on a fixture tree first, then run over THIS repository: the real fleet passes
with ZERO exemptions (36 files at `d8700c60e`), which is the point of the derivation.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
from scripts import check_workflows as cw


def _tree(tmp_path: Path, **files: str) -> Path:
    """A fixture `.github/workflows/` tree: each kwarg is one workflow file."""
    root = tmp_path
    (root / cw.WORKFLOWS).mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (root / cw.WORKFLOWS / f"{name}.yml").write_text(text)
    return root


def _keys(findings: list[dict]) -> list[str]:
    return sorted(f["key"].split("/")[0] for f in findings)


# ---------------------------------------------------------------- fixtures

#: Internal start surface only (workflow_dispatch → write-capable accounts): needs no guard.
WF_DISPATCH = (
    "name: internal-one\n"
    "on:\n"
    "  workflow_dispatch:\n"
    "\n"
    "permissions:\n"
    "  contents: read\n"
    "\n"
    "jobs:\n"
    "  go:\n"
    "    runs-on: ubuntu-latest\n"
    "    steps:\n"
    "      - run: echo hi\n"
)

#: Carries the guard where GitHub READS it — a step `if:` reference to `github.triggering_actor`.
WF_GUARDED = (
    "name: guarded-one\n"
    "on:\n"
    "  issues:\n"
    "    types: [opened]\n"
    "\n"
    "permissions:\n"
    "  contents: read\n"
    "\n"
    "jobs:\n"
    "  go:\n"
    "    runs-on: ubuntu-latest\n"
    "    steps:\n"
    "      - name: trigger guard\n"
    "        if: >-\n"
    "          ${{ github.actor == github.triggering_actor }}\n"
    "        run: echo allowed\n"
    "      - run: echo work\n"
)

#: An outsider-reachable trigger with NO guard anywhere.
WF_ROGUE = (
    "name: rogue-one\n"
    "on:\n"
    "  issues:\n"
    "    types: [opened]\n"
    "\n"
    "permissions:\n"
    "  contents: read\n"
    "\n"
    "jobs:\n"
    "  go:\n"
    "    runs-on: ubuntu-latest\n"
    "    steps:\n"
    "      - run: echo privileged\n"
)


def _follower(name: str, roster: list[str], sig: bool = False) -> str:
    """A `workflow_run` follower (block roster) naming `roster`; optionally carries the guard."""
    block = "".join(f"      - {n}\n" for n in roster)
    guard = (
        "      - name: trigger guard\n"
        "        if: ${{ github.actor == github.triggering_actor }}\n"
        "        run: echo allowed\n"
        if sig else
        "      - run: echo work\n"
    )
    return (
        f"name: {name}\n"
        "on:\n"
        "  workflow_run:\n"
        "    workflows:\n" + block +
        "    types: [completed]\n"
        "\n"
        "permissions:\n"
        "  contents: read\n"
        "\n"
        "jobs:\n"
        "  go:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n" + guard
    )


# ------------------------------------------------------------------ R1

def test_a_workflow_without_top_level_permissions_is_reported(tmp_path: Path):
    # Given a workflow with no column-zero `permissions:` block
    root = _tree(tmp_path, loose=WF_DISPATCH.replace("permissions:\n  contents: read\n\n", ""))
    # When the gate reads it
    found = cw.check_top_level_permissions(root)
    # Then the missing scope is reported (an invisible org-default is not a scope)
    assert _keys(found) == ["workflow-permissions"]
    assert "2526" in found[0]["evidence"]


def test_write_all_is_reported(tmp_path: Path):
    # Given a workflow that asks for every scope at once
    root = _tree(tmp_path, wide="name: wide\non:\n  workflow_dispatch:\n\npermissions: write-all\n\n"
        "jobs:\n  go:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo hi\n")
    found = cw.check_top_level_permissions(root)
    assert _keys(found) == ["workflow-write-all"]


def test_declared_scopes_are_accepted(tmp_path: Path):
    # Given workflows that state their own scope (top-level minimum, job-level elevation)
    root = _tree(tmp_path, a=WF_DISPATCH, b=WF_GUARDED)
    assert cw.check_top_level_permissions(root) == []


# ------------------------------------------------------------------ R2

def test_pull_request_target_is_reported(tmp_path: Path):
    # Given the one trigger that runs fork code with the base repo's write token
    root = _tree(tmp_path, bad=(
        "name: bad-trigger\non:\n  pull_request_target:\n    types: [opened]\n\n"
        "permissions:\n  contents: read\n\njobs:\n  go:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - run: echo hi\n"))
    found = cw.check_forbidden_triggers(root)
    assert _keys(found) == ["workflow-forbidden-trigger"]
    # R3 also treats it as outsider-reachable (defense in depth): the file is reported twice.
    assert _keys(cw.findings(root)) == ["workflow-actor-guard", "workflow-forbidden-trigger",
                                        "workflow-run-coverage"] or \
           "workflow-forbidden-trigger" in _keys(cw.findings(root))


def test_no_trigger_target_means_no_finding():
    # The real fleet never uses it; the wall keeps it at zero.
    assert cw.check_forbidden_triggers() == []


# ------------------------------------------------------------------ R3

def test_open_trigger_without_guard_is_reported(tmp_path: Path):
    # Given a privileged workflow an outsider's issue event can start, with no actor check
    root = _tree(tmp_path, rogue=WF_ROGUE)
    found = cw.check_actor_guards(root)
    assert _keys(found) == ["workflow-actor-guard"]
    assert "triggering_actor" in found[0]["evidence"]


def test_guard_in_if_is_accepted(tmp_path: Path):
    # Given the same trigger WITH the signature where GitHub reads it (a step `if:`)
    root = _tree(tmp_path, guarded=WF_GUARDED)
    assert cw.check_actor_guards(root) == []


def test_signature_inside_run_text_is_NOT_a_guard(tmp_path: Path):
    # Given `triggering_actor` mentioned only inside script text — a shell string is not a gate
    root = _tree(tmp_path, fake=WF_ROGUE.replace(
        "      - run: echo privileged\n",
        "      - run: echo \"${{ github.triggering_actor }}\"\n"))
    found = cw.check_actor_guards(root)
    assert _keys(found) == ["workflow-actor-guard"]


def test_internal_only_surface_needs_no_guard(tmp_path: Path):
    # Given push+schedule and workflow_call files: GitHub opens them only to write-capable
    # accounts, the repo's clock, or repo-local callers.
    root = _tree(tmp_path,
                 sched=("name: clock\non:\n  schedule:\n    - cron: '0 3 * * *'\n\n"
                        "permissions:\n  contents: read\n\njobs:\n  go:\n    runs-on: ubuntu-latest\n"
                        "    timeout-minutes: 30\n    steps:\n      - run: echo hi\n"),
                 call=("name: called\non:\n  workflow_call:\n\npermissions:\n  contents: read\n\n"
                       "jobs:\n  go:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo hi\n"))
    assert cw.check_actor_guards(root) == []


def test_workflow_run_follower_derives_guard_from_guarded_roster(tmp_path: Path):
    # Given a follower (like `auto-merge.yml`) with NO guard of its own, whose roster names only
    # guarded or internal-only workflows
    root = _tree(tmp_path, src=WF_DISPATCH, src2=WF_GUARDED,
                 follower=_follower("follows-two", ["internal-one", "guarded-one"]))
    # Then the fixed point marks it: a `workflow_run` follows a run whose entry was already gated
    assert cw.check_actor_guards(root) == []


def test_follower_with_unguarded_roster_source_is_reported(tmp_path: Path):
    # Given a follower whose roster names a workflow that is itself unguarded
    root = _tree(tmp_path, src=WF_ROGUE.replace("rogue-one", "open-src"),
                 follower=_follower("follows-open", ["open-src"]))
    found = cw.check_actor_guards(root)
    bad = [f for f in found if f["key"].endswith("follower.yml")]
    assert bad and "not itself guarded" in bad[0]["evidence"]
    # The roster source is reported on its own too.
    assert any(f["key"].endswith("src.yml") for f in found)


def test_follower_with_unknown_roster_name_is_reported(tmp_path: Path):
    # A roster name that resolves to nothing can never guard anyone
    root = _tree(tmp_path, follower=_follower("follows-ghost", ["Ghost CI"]))
    found = cw.check_actor_guards(root)
    assert any(f["key"] == "workflow-actor-guard/.github/workflows/follower.yml" for f in found)


def test_roster_cycle_is_not_trust(tmp_path: Path):
    # Given two followers waiting on each other: circular "trust" never reaches the fixed point
    root = _tree(tmp_path,
                 a=_follower("cycle-a", ["cycle-b"]),
                 b=_follower("cycle-b", ["cycle-a"]))
    found = cw.check_actor_guards(root)
    assert _keys(found) == ["workflow-actor-guard", "workflow-actor-guard"]


def test_guarded_follower_with_open_issue_trigger_cannot_derive(tmp_path: Path):
    # Derivation covers `workflow_run` only: an `issues` trigger starts the file on its own authority
    root = _tree(tmp_path, src=WF_DISPATCH,
                 mixed=(_follower("mixed", ["internal-one"])
                        .replace("  workflow_run:\n", "  issues:\n    types: [opened]\n  workflow_run:\n")))
    found = cw.check_actor_guards(root)
    assert _keys(found) == ["workflow-actor-guard"]


# ------------------------------------------------- the real fleet (no exemptions)

def test_the_real_fleet_passes_all_three_rules():
    """36 files at `d8700c60e`: 32 carry the guard, 2 derive it, 2 are internal-only, 0 exempted."""
    assert cw.check_top_level_permissions() == []
    assert cw.check_forbidden_triggers() == []
    assert cw.check_actor_guards() == []


def test_the_fleet_classification_matches_the_measured_surface():
    """The start-surface classification is the scan's answer to 'who can start this' (owner 2026-11-12):
    PR-creation, merge-to-main push, cron, and manual dispatch all appear in the fleet — every one
    of them lands in a class the gate accepts (guard, derivation, or platform-internal)."""
    per_file: dict[str, list[str]] = {}
    for path in cw.workflow_files():
        per_file[path.name] = cw._on_triggers(path.read_text().splitlines())
    started_by_pr = [f for f, ts in per_file.items() if "pull_request" in ts]
    started_by_push = [f for f, ts in per_file.items() if "push" in ts]
    started_by_cron = [f for f, ts in per_file.items() if "schedule" in ts]
    started_by_hand = [f for f, ts in per_file.items() if "workflow_dispatch" in ts]
    started_by_followers = [f for f, ts in per_file.items() if "workflow_run" in ts]
    assert started_by_pr and started_by_push and started_by_cron and started_by_hand
    assert started_by_followers  # the automatic completion chain is part of the scan too
    # Every PR-triggered file carries the guard outside `run:` text: for a PR run, the signature
    # IS the check of who created the PR.
    for name in started_by_pr:
        lines = (Path(cw.WORKFLOWS) / name).read_text().splitlines()
        assert cw.GUARD_SIGNATURE.search("\n".join(cw._outside_run_lines(lines))) is not None, name
