"""Hermetic tests for scripts/verify_lane_contract.py (issues #2260, #2316).

The real script is run against scratch fixture profiles built in tmp_path via
`--root`, so no live ~/.hermes profile is touched; the lane roster is driven by
a scratch `--manifest` (the manifest is the ONE source of truth for which lanes
exist — #2316), never by the repository's real agents/manifest.json. The points
proven:

- a complete contract SOUL + materialised skill PASSES;
- an EMPTY SOUL FAILS (no contract at all);
- a SOUL that has every OTHER contract element but no `BOT … working on #`
  report line FAILS the report-line axis;
- a SOUL that reports to nobody FAILS the communicate axis;
- a SOUL whose skills/ holds only .archive stubs FAILS skills-materialised;
- removing a lane's own-duty marker makes the checker red for that lane;
- a manifest lane with NO DUTY entry FAILS naming `manifest-lane-without-duty`
  (the #2316 negative control: a NEW lane silently added to the manifest must
  not green-light a SOUL that never commits to its duty);
- the real manifest's lane set is a SUBSET of the DUTY roster (subset assertion,
  never equality, so a legitimate new DUTY entry does not red the suite).
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parent.parent / "scripts" / "verify_lane_contract.py"
)
REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "agents" / "manifest.json"

# A complete live-identical SOUL: every CONTRACT element + the lane's own duty.
GOOD_SOUL = """# llgenie-planner
BOT llgenie-planner · working on #100 · branch x · since 01:00Z · blocked on none · next y
Never merge, never push to main.
Bookend: start comment on the issue, finish comment with the head sha.
Behaviour changes land by issue+PR under agents/<profile>/, never a private edit.
I triage the board and dispatch every idle lane to its owning PR.
Report to the planner via message_agent and recall the failure class.
"""

LANE = "llgenie-planner"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "verify_lane_contract", str(SCRIPT)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_scratch_profile(root, lane=LANE, soul=GOOD_SOUL, skills=True,
                           archived_only=False):
    """Build a scratch profile: SOUL.md (+ optional skills dir). Returns root."""
    prof = root / lane
    (prof / "SOUL.md").parent.mkdir(parents=True, exist_ok=True)
    (prof / "SOUL.md").write_text(soul)
    if skills:
        base = prof / "skills" / (".archive" if archived_only else "security")
        (base / "SKILL.md").parent.mkdir(parents=True, exist_ok=True)
        (base / "SKILL.md").write_text("# Duty skill\nDo security.\n")
    return root


def _write_manifest(root, lanes):
    """Write a scratch agents/manifest.json whose roster is `lanes`."""
    manifest = root / "manifest.json"
    manifest.write_text(json.dumps(
        {"note": "scratch roster", "profiles": [{"name": l, "rules": []} for l in lanes]},
        indent=2,
    ))
    return manifest


def _run(root):
    """Run the checker against the scratch root, driven by a scratch manifest that
    lists exactly the llgenie-* profiles present under dead root."""
    present = sorted(p.parent.name for p in root.glob("llgenie-*/SOUL.md"))
    manifest = _write_manifest(root, present or [LANE])
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root),
         "--manifest", str(manifest)],
        capture_output=True,
        text=True,
        env={**__import__("os").environ},
        timeout=60,
    )


def test_all_pass_with_complete_contract(tmp_path):
    _write_scratch_profile(tmp_path)
    r = _run(tmp_path)
    assert r.returncode == 0, r.stdout
    assert "1/1 lanes pass the behavioural contract" in r.stdout, r.stdout


def test_empty_soul_fails(tmp_path):
    _write_scratch_profile(tmp_path, soul="")
    r = _run(tmp_path)
    assert r.returncode == 1, r.stdout
    assert "FAIL" in r.stdout
    assert "report-line" in r.stdout


def test_missing_report_line_fails(tmp_path):
    # every OTHER element present, but no `BOT … working on #` line
    no_report = GOOD_SOUL.replace(
        "BOT llgenie-planner · working on #100 · branch x · since 01:00Z · blocked on none · next y\n",
        "",
    )
    _write_scratch_profile(tmp_path, soul=no_report)
    r = _run(tmp_path)
    assert r.returncode == 1, r.stdout
    assert "report-line" in r.stdout, r.stdout


def test_no_communication_fails(tmp_path):
    # a SOUL that reports to nobody must fail the communicate axis
    no_comm = GOOD_SOUL.replace(
        "Report to the planner via message_agent and recall the failure class.\n",
        "",
    )
    _write_scratch_profile(tmp_path, soul=no_comm)
    r = _run(tmp_path)
    assert r.returncode == 1, r.stdout
    assert "communicate" in r.stdout, r.stdout


def test_archived_only_skills_fail(tmp_path):
    _write_scratch_profile(tmp_path, skills=True, archived_only=True)
    r = _run(tmp_path)
    assert r.returncode == 1, r.stdout
    assert "skills-materialised" in r.stdout, r.stdout


def test_removing_own_duty_marker_reds(tmp_path):
    # remove the own-duty marker; nothing else changes. `llgenie-planner`'s duty
    # regex (triag|dispat|orchestrat|idle) never collides with its own name, so
    # removing the marker genuinely reds rather than matching the lane title.
    no_duty = GOOD_SOUL.replace(
        "I triage the board and dispatch every idle lane to its owning PR.\n", ""
    )
    _write_scratch_profile(tmp_path, soul=no_duty)
    r = _run(tmp_path)
    assert r.returncode == 1, r.stdout
    assert "own-duty" in r.stdout, r.stdout


def test_new_manifest_lane_without_duty_fails(tmp_path):
    # #2316 negative control: a NEW lane in the manifest that has no DUTY entry
    # must FAIL naming the lane — never silently PASS on a SOUL that has every
    # other CONTRACT marker but no committed duty. The scratch manifest lists
    # `llgenie-data-archival` (not in the DUTY dict); its SOUL is otherwise
    # complete, so the ONLY reason to red is the missing DUTY entry.
    new_lane = "llgenie-data-archival"
    soul = GOOD_SOUL.replace("llgenie-planner", new_lane) + "I archive the data.\n"
    _write_scratch_profile(tmp_path, lane=new_lane, soul=soul)
    manifest = _write_manifest(tmp_path, [new_lane])
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path),
         "--manifest", str(manifest)],
        capture_output=True, text=True,
        env={**__import__("os").environ}, timeout=60,
    )
    assert r.returncode == 1, r.stdout
    assert "FAIL" in r.stdout, r.stdout
    assert new_lane in r.stdout, r.stdout
    assert "manifest-lane-without-duty" in r.stdout, r.stdout


def test_real_manifest_lanes_are_subset_of_duty(tmp_path):
    # #2316 referent: every lane in agents/manifest.json must have a DUTY entry.
    # Asserted as a SUBSET (manifest <= DUTY), never equality, so a legitimate
    # extra DUTY entry (e.g. a lane mid-rollout) does not red the suite. A
    # manifest lane missing from DUTY is exactly the regression #2316 fixes.
    mod = _load_module()
    with MANIFEST.open() as fh:
        manifest_lanes = {p["name"] for p in json.load(fh)["profiles"]}
    assert manifest_lanes <= set(mod.DUTY), (
        "manifest lane(s) with no DUTY entry: "
        + ", ".join(sorted(manifest_lanes - set(mod.DUTY)))
    )
