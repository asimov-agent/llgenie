"""The code-review bot: the checks, the dedup, and the cap (all deterministic).

Everything the bot decides is proven for real — `check_*`, `findings()`, `filed()` and
`file_findings()` are the code under test. Only the GitHub API is a stand-in: a `gh` on PATH that
records its argv and answers `issue list --search` / `issue create`, so the tests assert the EXACT
request the product builds (the same pattern as `tests/test_issue_implementer.py`).

The bot's promise is narrow on purpose, and the tests hold it to it: it files ISSUES and nothing
else, one per NEW finding, never more than the cap, and it stays silent when a check finds nothing.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import code_review as cr  # noqa: E402


def _tree(tmp_path: Path, workflows: dict[str, str]) -> Path:
    """A repo root with exactly these `.github/workflows/*.yml` files."""
    root = tmp_path / "repo"
    (root / cr.WORKFLOWS).mkdir(parents=True, exist_ok=True)
    for name, body in workflows.items():
        (root / cr.WORKFLOWS / name).write_text(body)
    return root


def _fake_gh(tmp_path: Path, opts: dict | None = None):
    """`gh` that records every argv as one JSON line and answers the bot's queries.

    opts:
      filed:  keys whose marker `issue list --search` should find (already-filed findings)
    """
    opts = opts or {}
    tmp_path.mkdir(parents=True, exist_ok=True)
    log = tmp_path / "gh.log"
    gh = tmp_path / "gh"
    gh.write_text(f'''#!{sys.executable}
import json, sys
args = sys.argv[1:]
FILED = {json.dumps(opts.get("filed", []))}
with open({str(log)!r}, "a") as fh:
    fh.write(json.dumps(args) + "\\n")
if args[:2] == ["issue", "list"]:
    hit = [k for k in FILED if k in " ".join(args)]
    print(json.dumps([{{"number": 1, "title": k}} for k in hit]))
elif args[:2] == ["issue", "create"]:
    print("https://github.com/asimov-agent/llgenie/issues/900")
elif args[:2] == ["secret", "list"]:
    print(json.dumps([{{"name": n}} for n in {json.dumps(opts.get("secrets", []))}]))
else:
    print("[]")
''')
    gh.chmod(0o755)
    return gh, log


def _calls(log: Path) -> list[list[str]]:
    return [json.loads(l) for l in log.read_text().splitlines() if l.strip()]


# ---------------------------------------------------------------------------
# workflow-inline-scripts
# ---------------------------------------------------------------------------
def test_a_step_that_calls_a_repo_script_directly_is_a_finding(tmp_path):
    root = _tree(tmp_path, {"a.yml": """
name: A
on:
  workflow_dispatch:
jobs:
  a:
    steps:
      - name: alarm
        run: |
          set -euo pipefail
          python3 scripts/queued_run_alarm.py --repo "${{ github.repository }}"
"""})
    found = cr.check_workflow_inline_scripts(root)
    assert len(found) == 1, found
    assert found[0]["key"] == "workflow-inline-scripts/a.yml"
    assert "queued_run_alarm.py" in found[0]["evidence"]
    assert found[0]["where"] == ".github/workflows/a.yml"


def test_a_step_that_calls_a_make_target_is_not_a_finding(tmp_path):
    root = _tree(tmp_path, {"a.yml": """
name: A
on:
  workflow_dispatch:
jobs:
  a:
    steps:
      - name: alarm
        run: make queued-alarm REPO=x
      - name: unit
        run: make test-unit
"""})
    assert cr.check_workflow_inline_scripts(root) == []


def test_gh_orchestration_may_stay_shell(tmp_path):
    """The documented exemption: a step whose whole job is gh/git orchestration carries no repo
    logic, so it does not have to be a make target (the guards in every bot workflow look like this).
    """
    root = _tree(tmp_path, {"a.yml": """
name: A
on:
  workflow_dispatch:
jobs:
  a:
    steps:
      - name: guard
        run: |
          set -euo pipefail
          who=$(gh api "repos/${{ github.repository}}" --jq .permissions.push)
          if [ "$who" != "true" ]; then exit 1; fi
"""})
    assert cr.check_workflow_inline_scripts(root) == []


# ---------------------------------------------------------------------------
# secrets-not-defined
# ---------------------------------------------------------------------------
def test_a_secret_a_workflow_reads_but_the_repo_does_not_define_is_a_finding(tmp_path):
    root = _tree(tmp_path, {"a.yml": """
name: A
on:
  workflow_dispatch:
jobs:
  a:
    steps:
      - run: make x
        env:
          NOUS_API_KEY: ${{ secrets.NOUS_PORTAL_API_TOKEN }}
          PRESENT: ${{ secrets.PRESENT_SECRET }}
"""})
    found = cr.check_secrets_not_defined(root, {"PRESENT_SECRET"})
    assert len(found) == 1, found
    assert found[0]["key"] == "secrets-not-defined/NOUS_PORTAL_API_TOKEN"
    assert "EMPTY string" in found[0]["evidence"]
    assert found[0]["where"] == "a.yml"


def test_a_defined_secret_and_github_token_are_never_findings(tmp_path):
    root = _tree(tmp_path, {"a.yml": """
name: A
on:
  workflow_dispatch:
jobs:
  a:
    steps:
      - run: make x
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          KEY: ${{ secrets.PRESENT_SECRET }}
"""})
    assert cr.check_secrets_not_defined(root, {"PRESENT_SECRET"}) == []


# ---------------------------------------------------------------------------
# workflow-never-ran / reusable-orphan
# ---------------------------------------------------------------------------
def test_a_scheduled_workflow_with_zero_runs_is_a_finding(tmp_path):
    root = _tree(tmp_path, {"a.yml": """
name: A
on:
  schedule:
    - cron: "23 6 * * *"
  workflow_dispatch:
jobs:
  a:
    steps:
      - run: make x
"""})
    found = cr.check_workflow_never_ran(root, {"a.yml": 0})
    assert len(found) == 1, found
    assert "schedule" in found[0]["evidence"] and "workflow_dispatch" in found[0]["evidence"]


def test_a_reusable_only_workflow_is_not_judged_on_its_run_count(tmp_path):
    """Measured: `ci.yml` calls `pipeline.yml` three times, ci.yml reports 892 runs and pipeline.yml
    reports 0 — GitHub counts a reusable workflow's runs under its CALLER, so 0 there proves nothing.
    """
    root = _tree(tmp_path, {"pipeline.yml": """
name: pipeline
on:
  workflow_call:
    inputs:
      runner:
        type: string
        required: true
jobs:
  a:
    steps:
      - run: make x
""", "ci.yml": """
name: CI
on:
  push:
jobs:
  call:
    uses: ./.github/workflows/pipeline.yml
    with:
      runner: ubuntu-latest
"""})
    assert cr.check_workflow_never_ran(root, {"pipeline.yml": 0, "ci.yml": 892}) == []


def test_a_reusable_workflow_nothing_calls_is_a_finding(tmp_path):
    root = _tree(tmp_path, {"orphan.yml": """
name: orphan
on:
  workflow_call:
jobs:
  a:
    steps:
      - run: make x
"""})
    found = cr.check_reusable_orphan(root)
    assert len(found) == 1, found
    assert found[0]["key"] == "reusable-orphan/orphan.yml"
    assert "nothing runs it" in found[0]["evidence"].lower() or "Nothing runs it" in found[0]["evidence"]


def test_a_reusable_workflow_with_a_caller_is_not_a_finding(tmp_path):
    root = _tree(tmp_path, {"used.yml": """
name: used
on:
  workflow_call:
jobs:
  a:
    steps:
      - run: make x
""", "ci.yml": """
name: CI
on:
  push:
jobs:
  call:
    uses: ./.github/workflows/used.yml
"""})
    assert cr.check_reusable_orphan(root) == []


# ---------------------------------------------------------------------------
# cron-collisions
# ---------------------------------------------------------------------------
def test_two_workflows_in_the_same_slot_on_overlapping_days_collide(tmp_path):
    root = _tree(tmp_path, {"a.yml": """
name: A
on:
  schedule:
    - cron: "23 6 * * 1"
jobs:
  a:
    steps:
      - run: make x
""", "b.yml": """
name: B
on:
  schedule:
    - cron: "23 6 * * *"
jobs:
  b:
    steps:
      - run: make x
"""})
    found = cr.check_cron_collisions(root)
    assert len(found) == 1, found
    assert found[0]["key"].startswith("cron-collisions/6:23-")
    assert "overlapping days" in found[0]["evidence"]


def test_the_same_slot_on_disjoint_weekdays_is_not_a_collision(tmp_path):
    root = _tree(tmp_path, {"a.yml": """
name: A
on:
  schedule:
    - cron: "17 5 * * 1"
jobs:
  a:
    steps:
      - run: make x
""", "b.yml": """
name: B
on:
  schedule:
    - cron: "17 5 * * 3"
jobs:
  b:
    steps:
      - run: make x
"""})
    assert cr.check_cron_collisions(root) == []


def test_a_collision_needs_a_fixed_slot(tmp_path):
    """Hourly/step crons fire many times a day by design; only fixed slots are compared."""
    root = _tree(tmp_path, {"a.yml": """
name: A
on:
  schedule:
    - cron: "43 * * * *"
jobs:
  a:
    steps:
      - run: make x
""", "b.yml": """
name: B
on:
  schedule:
    - cron: "43 * * * *"
jobs:
  b:
    steps:
      - run: make x
"""})
    assert cr.check_cron_collisions(root) == []


# ---------------------------------------------------------------------------
# filing: one issue per NEW finding, capped, issues only
# ---------------------------------------------------------------------------
def _one_finding(key="check/a.yml", title="ci: something is wrong"):
    return [{"key": key, "title": title, "evidence": "measured: 3 of 7", "where": ".github/workflows/a.yml"}]


def test_filing_creates_one_issue_per_new_finding_carrying_the_marker_and_the_evidence(tmp_path):
    gh, log = _fake_gh(tmp_path)
    items = _one_finding() + _one_finding(key="check/b.yml", title="ci: the other thing")
    created = cr.file_findings(str(gh), "asimov-agent/llgenie", items, cap=5)
    assert len(created) == 2

    creates = [c for c in _calls(log) if c[:2] == ["issue", "create"]]
    assert len(creates) == 2
    body = creates[0][creates[0].index("--body") + 1]
    assert cr.MARKER.format(key="check/a.yml") in body          # the memory for the next run
    assert "measured: 3 of 7" in body                            # the evidence travels with the claim
    assert "analysis finding, not a fix" in body


def test_an_already_filed_finding_is_not_filed_again(tmp_path):
    gh, log = _fake_gh(tmp_path, {"filed": ["check/a.yml"]})
    items = _one_finding() + _one_finding(key="check/b.yml")
    created = cr.file_findings(str(gh), "asimov-agent/llgenie", items, cap=5)
    assert [c["key"] for c in created] == ["check/b.yml"]
    assert len([c for c in _calls(log) if c[:2] == ["issue", "create"]]) == 1


def test_the_cap_holds_and_filing_stops_cleanly(tmp_path):
    gh, log = _fake_gh(tmp_path)
    items = [_one_finding(key=f"check/{n}.yml")[0] for n in range(6)]
    created = cr.file_findings(str(gh), "asimov-agent/llgenie", items, cap=3)
    assert len(created) == 3
    assert len([c for c in _calls(log) if c[:2] == ["issue", "create"]]) == 3


def test_dry_run_creates_nothing(tmp_path):
    gh, log = _fake_gh(tmp_path)
    created = cr.file_findings(str(gh), "asimov-agent/llgenie", _one_finding(), cap=3, dry=True)
    assert len(created) == 1 and created[0].get("dry")
    assert not [c for c in _calls(log) if c[:2] == ["issue", "create"]]


def test_the_bot_never_writes_code(tmp_path):
    """Its whole output is issues: no `pr`, no `issue comment`, no `workflow run` from the filer."""
    gh, log = _fake_gh(tmp_path)
    cr.file_findings(str(gh), "asimov-agent/llgenie", _one_finding(), cap=3)
    verbs = {tuple(c[:2]) for c in _calls(log)}
    assert verbs <= {("issue", "list"), ("issue", "create")}, verbs


# ---------------------------------------------------------------------------
# argv the REAL gh accepts
# ---------------------------------------------------------------------------
def test_no_gh_call_combines_comments_with_json(tmp_path):
    """`gh` rejects `--comments` together with `--json`; this bot must not reintroduce that argv."""
    gh, log = _fake_gh(tmp_path)
    cr.file_findings(str(gh), "asimov-agent/llgenie", _one_finding(), cap=3)
    for call in _calls(log):
        assert not ("--comments" in call and "--json" in call), call


def test_the_dedup_search_asks_for_the_marker(tmp_path):
    gh, log = _fake_gh(tmp_path)
    cr.filed(str(gh), "asimov-agent/llgenie", "check/a.yml")
    search = [c for c in _calls(log) if c[:2] == ["issue", "list"]][0]
    assert any(cr.MARKER.format(key="check/a.yml") in arg for arg in search), search
    assert "--state" in search and search[search.index("--state") + 1] == "all"


# ---------------------------------------------------------------------------
# the bot holds itself to its own checks
# ---------------------------------------------------------------------------
def test_the_bots_own_workflow_passes_the_bots_own_checks():
    """Self-consistency: the file this bot ships must not trip the checks it runs on every other
    workflow. (The cron slot it picked is its own, exactly so it does not collide.)
    """
    keys = {f["key"] for f in (cr.check_workflow_inline_scripts(cr.REPO_ROOT)
                              + cr.check_cron_collisions(cr.REPO_ROOT)
                              + cr.check_reusable_orphan(cr.REPO_ROOT))}
    assert not [k for k in keys if "code-review-bot.yml" in k], sorted(keys)
    assert (cr.REPO_ROOT / cr.WORKFLOWS / "code-review-bot.yml").exists()
    # it is a scheduled workflow, so the never-ran check applies to it like any other
    assert cr.check_workflow_never_ran(cr.REPO_ROOT, {"code-review-bot.yml": 0})[0]["key"] == \
        "workflow-never-ran/code-review-bot.yml"


def test_a_refused_api_read_degrades_loudly_instead_of_crashing(tmp_path, capsys):
    """The two API-backed checks need a token with admin. Without one they must SAY SO and let the
    static checks run — a bot that dies on a permission it does not need is a bot that files nothing.
    """
    gh = tmp_path / "gh"
    gh.write_text(f"#!{sys.executable}\nimport sys\nsys.stderr.write('HTTP 403: Must have admin rights\\n')\nsys.exit(1)\n")
    gh.chmod(0o755)

    assert cr.defined_secrets(str(gh), "asimov-agent/llgenie") is None
    assert cr.workflow_run_counts(str(gh), "asimov-agent/llgenie") is None
    err = capsys.readouterr().err
    assert "WARNING" in err and "SKIPPED" in err

    # and the static checks still produce findings with the live ones unavailable
    root = _tree(tmp_path, {"a.yml": """
name: A
on:
  schedule:
    - cron: "23 7 * * 1"
jobs:
  a:
    steps:
      - run: python3 scripts/thing.py
"""})
    found = cr.findings(root, secrets=None, runs=None)
    assert [f["key"] for f in found] == ["workflow-inline-scripts/a.yml"]
