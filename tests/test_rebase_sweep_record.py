"""The rebase sweep record (#2950): the sweep names its deferrals, the recorder posts one summary.

Three halves, all real code under test:

  * `scripts/rebase_bot_sweep.py` prints one `deferred=#<n>` line per deferred PR (stdout readout,
    driven through the same kind of argv-recording fake `gh` the sweep tests use);
  * `scripts/rebase_sweep_record.py` assembles the `[rebase-sweep …]` summary and posts it through
    `gh issue comment` exactly once, or stays silent (dry, no target, miscounted);
  * the `rebase-bot` lane wiring: the drain step counts picked/deferrals into `$RUNNER_TEMP` and a
    record step hands the counts to `make rebase-sweep-record … RECORD=2652`.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
from scripts import rebase_bot_sweep as rb
from scripts import rebase_sweep_record as rsr

OWNER, NAME = "asimov-agent", "llgenie"


# ------------------------------------------------------------- a minimal recording fake `gh`

def _fake_gh(tmp_path: Path, prs: list | None = None) -> tuple[Path, Path]:
    """A `gh` that records every argv line; `pr list`/`pr view` answer from fixtures,
    `issue comment` answers like the real command does (the created comment URL)."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    log = tmp_path / "gh.log"
    (tmp_path / "prs.json").write_text(json.dumps(prs or []))
    gh = tmp_path / "gh"
    gh.write_text(f'''#!{sys.executable}
import json, sys, pathlib
args = sys.argv[1:]
here = pathlib.Path(__file__).parent
with open({str(log)!r}, "a") as fh:
    fh.write(json.dumps(args) + "\\n")
if args[:2] == ["pr", "list"]:
    print((here / "prs.json").read_text())
elif args[:2] == ["pr", "view"]:
    print(json.dumps({{"mergeStateStatus": "UNKNOWN", "mergeable": ""}}))
elif args[:2] == ["issue", "comment"]:
    print("https://github.com/o/r/issues/1#issuecomment-1")
''')
    gh.chmod(0o755)
    return gh, log


def _calls(log: Path) -> list[list[str]]:
    if not log.exists():
        return []
    return [json.loads(l) for l in log.read_text().splitlines() if l.strip()]


def _pr(num, state="UNKNOWN"):
    return {"number": num, "title": f"PR {num}", "isDraft": False,
            "mergeStateStatus": state, "mergeable": None, "headRefName": f"feat/{num}",
            "headRepositoryOwner": {"login": OWNER}, "createdAt": "2026-11-01T00:00:00Z",
            "baseRefName": "main"}


# ------------------------------------------------------- sweep: a structured deferral readout

def test_sweep_prints_one_structured_line_per_deferred_pr(tmp_path, capsys):
    """A deferred PR is greppable on stdout, not only prose (the lane counts it from there)."""

    # Given an open PR whose merge state never resolves
    gh, _log = _fake_gh(tmp_path, [_pr(9)])

    # When the CLI sweep runs with bounded re-queries
    rc = rb.main(["--gh", str(gh), "--repo", f"{OWNER}/{NAME}", "--today", "2026-11-19",
                  "--unknown-attempts", "1", "--unknown-delay", "0"])

    # Then the deferral is named both as prose and as a `deferred=#<n>` line
    out = capsys.readouterr().out
    assert rc == 0
    assert "deferred=#9" in out.splitlines()
    assert "#9 has no computed merge state (UNKNOWN)" in out


def test_sweep_prints_no_deferred_lines_when_nothing_is_deferred(tmp_path, capsys):
    """The readout adds lines, it does not invent them."""

    # Given an empty board
    gh, _log = _fake_gh(tmp_path, [])

    # When the sweep runs
    rc = rb.main(["--gh", str(gh), "--repo", f"{OWNER}/{NAME}", "--today", "2026-11-19"])

    # Then no deferral line appears
    out = capsys.readouterr().out
    assert rc == 0
    assert not any(l.startswith("deferred=") for l in out.splitlines())


# ------------------------------------------------------------------- recorder: the summary body

def test_summary_first_line_is_the_fixed_greppable_shape():
    body = rsr.summary(2, 1, ["- PR #605: has no computed merge state — deferred to the next run"])
    assert re.fullmatch(r"\[rebase-sweep \d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\] "
                        r"dispatched=2 rebased=1 deferred=1", body[0])
    assert body[1] == "- PR #605: has no computed merge state — deferred to the next run"


def test_quiet_pass_records_itself_with_zero_counts(tmp_path):
    gh, log = _fake_gh(tmp_path)

    rc = rsr.main(["--gh", str(gh), "--repo", f"{OWNER}/{NAME}", "--record", "2652",
                   "--dispatched", "0", "--rebased", "0", "--failed", "0"])

    assert rc == 0
    comments = [c for c in _calls(log) if c[:2] == ["issue", "comment"]]
    assert len(comments) == 1
    assert comments[0][2] == "2652"
    body = comments[0][comments[0].index("--body") + 1]
    lines = body.splitlines()
    assert len(lines) == 1 and "dispatched=0 rebased=0 deferred=0" in lines[0]


def test_record_posts_one_comment_with_a_line_per_deferred_pr(tmp_path):
    # Given deferral lines the lane collected (the same deferral handed over twice)
    gh, log = _fake_gh(tmp_path)
    lines = tmp_path / "lines.txt"
    lines.write_text("- PR #605: has no computed merge state (UNKNOWN) — deferred to the next run\n"
                     "- PR #605: has no computed merge state (UNKNOWN) — deferred to the next run\n"
                     "- PR #777: picked and not rebased (rebase failed; retried next run)\n")

    # When the recorder runs with the lane's counts
    rc = rsr.main(["--gh", str(gh), "--repo", f"{OWNER}/{NAME}", "--record", "2652",
                   "--dispatched", "1", "--rebased", "0", "--failed", "1",
                   "--lines-file", str(lines)])

    # Then exactly one comment lands, each deferred PR named ONCE, deferred counts the lines
    assert rc == 0
    comments = [c for c in _calls(log) if c[:2] == ["issue", "comment"]]
    assert len(comments) == 1
    body = comments[0][comments[0].index("--body") + 1].splitlines()
    assert len(body) == 3, body
    assert "dispatched=1 rebased=0 deferred=2" in body[0]
    assert body[1].startswith("- PR #605:") and body[2].startswith("- PR #777:")


def test_dry_posts_nothing(tmp_path, capsys):
    gh, log = _fake_gh(tmp_path)

    rc = rsr.main(["--gh", str(gh), "--repo", f"{OWNER}/{NAME}", "--record", "2652",
                   "--dispatched", "2", "--rebased", "2", "--failed", "0", "--dry"])

    out = capsys.readouterr().out
    assert rc == 0
    assert "dispatched=2 rebased=2 deferred=0" in out
    assert _calls(log) == []                      # nothing was asked of gh at all


def test_no_record_target_posts_nothing(tmp_path):
    gh, log = _fake_gh(tmp_path)

    rc = rsr.main(["--gh", str(gh), "--repo", f"{OWNER}/{NAME}",
                   "--dispatched", "1", "--rebased", "1", "--failed", "0"])

    assert rc == 0
    assert _calls(log) == []


def test_a_miscounted_record_is_refused(tmp_path):
    """dispatched must equal rebased + failed: a summary that miscounts is worse than none."""
    gh, log = _fake_gh(tmp_path)

    rc = rsr.main(["--gh", str(gh), "--repo", f"{OWNER}/{NAME}", "--record", "2652",
                   "--dispatched", "3", "--rebased", "1", "--failed", "1"])

    assert rc == 1
    assert _calls(log) == []


# ------------------------------------------------------------------------- the lane wiring

def test_rebase_bot_lane_records_its_sweep_on_2652():
    wf = yaml.safe_load((REPO / ".github" / "workflows" / "rebase-bot.yml").read_text())
    steps = wf["jobs"]["rebase"]["steps"]

    drain = next(s for s in steps if str(s.get("name", "")).startswith("Rebase every eligible PR"))
    record = next(s for s in steps if "Record the sweep summary" in str(s.get("name", "")))

    # the drain collects deferrals structurally and exports the picked count
    assert "deferred=#" in drain["run"]
    assert 'lines_file="$RUNNER_TEMP/rebase-sweep-lines.txt"' in drain["run"]
    assert "picked=$((picked + 1))" in drain["run"]
    assert "echo \"picked=$picked\"" in drain["run"]
    assert "picked and not rebased" in drain["run"]

    # the record step hands the drain's own counts to the wired target, on #2652
    assert "RECORD=2652" in record["run"]
    assert "make rebase-sweep-record" in record["run"]
    assert "steps.drain.outputs.picked" in record["run"]
    assert "rebase-sweep-lines.txt" in record["run"]
    # a crashed decision (no drain outputs) is never recorded as zeros
    assert record["if"] == "steps.drain.outputs.rebased != ''"
    assert record["env"]["GH_TOKEN"] == "${{ github.token }}"


def test_rebase_sweep_record_target_is_wired():
    bots = (REPO / "mk" / "bots.mk").read_text()
    target = next(l for l in bots.splitlines() if l.startswith("rebase-sweep-record:"))
    recipes = bots[bots.index(target):].splitlines()[1:4]
    assert any("scripts/rebase_sweep_record.py" in r for r in recipes)
    assert any("--record $(RECORD)" in r for r in recipes) and any("--lines-file" in r for r in recipes)
    phony = (REPO / "Makefile").read_text()
    assert "rebase-sweep-record" in phony
    layers = json.loads((REPO / "scripts" / "package-layers.json").read_text())
    assert any("rebase_sweep_record" in mods for mods in layers["groups"].values())
