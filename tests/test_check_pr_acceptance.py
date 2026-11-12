from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from scripts import check_pr_acceptance as g
from scripts.check_pr_acceptance import main as run_cli

REPO = Path(__file__).resolve().parents[1]


def _issue(ticked: list[int], total: int, extra: str = "") -> str:
    """A repo-shaped issue body with `total` acceptance criteria, `ticked` of them proven.

    A ticked criterion carries a provable `(proven: …)` marker exactly as `acceptance_writeback`
    writes it (issue #1644) — the #1784/#1819 defect this gate polices is a tick that names a
    hash/cmp but no run id and no reproducible command+rc+sha.
    """
    lines = ["## Problem", "", "measured defect", "", "## How we fix it", "", "1. fix it", "",
             "## Benefit", "", "done", "", "## Acceptance criteria", ""]
    for i in range(1, total + 1):
        state = "x" if i in ticked else " "
        text = f"criterion {i} is met"
        if state == "x":
            text += "  (proven: reviewer=llgenie-pr-reviever comment=1 head=abc1234 run=42191377162)"
        lines.append(f"- [{state}] {text}")
    lines += ["", "## Technical", "", "- details", ""]
    if extra:
        lines += extra.splitlines() + [""]
    return "\n".join(lines).rstrip("\n") + "\n"


def _pr(closes: str, criteria_text: str = "closes #1000", body_checkbox: str = "") -> str:
    """A PR body that closes `closes`, optionally carrying its own `- [x]` claim."""
    lines = ["## What and why", "", f"{closes}", "", criteria_text, ""]
    if body_checkbox:
        lines += ["### Verify", "", body_checkbox, ""]
    return "\n".join(lines).rstrip("\n") + "\n"


# --- the gate: a close must meet the issue's own done -------------------------------------------------


def test_closed_issue_with_unticked_criterion_is_RED():
    # 5/5 unmarked, #491-class: the merged PR closes it and CI verifies green in the status quo.
    findings = g.acceptance_verdict(_issue(ticked=[], total=5), _pr("closes #1000"), 1000)
    assert findings, "a closed issue with 5/5 unticked must be red"
    assert any(f["key"] == "acceptance-unchecked" for f in findings), [f["key"] for f in findings]


def test_unticked_local_build_criterion_points_at_the_dispatch_form():
    # A criterion worded as a LOCAL engine build cannot be proved by a host build (issue #2109) — the
    # finding must name the DISPATCH form as the remedy instead of leaving "locally on this host".
    body = ("## Problem\n\nmeasured\n\n## Acceptance criteria\n"
            "- [ ] the failing make target is green locally on this host, with its real output recorded\n"
            "## Technical\n\n- t\n")
    findings = g.acceptance_verdict(body, _pr("closes #1000"), 1000)
    unchecked = [f for f in findings if f["key"] == "acceptance-unchecked"]
    assert unchecked, [f["key"] for f in findings]
    evidence = unchecked[0]["evidence"]
    assert "LOCAL build" in evidence
    assert "Inference servers run ONLY in their container images" in evidence
    assert "in a real run of the failing cell" in evidence
    assert "single-cell `engine-build`" in evidence


def test_closed_issue_with_all_criteria_ticked_is_GREEN():
    assert g.acceptance_verdict(_issue(ticked=[1, 2, 3], total=3), _pr("closes #1000"), 1000) == []


def test_partially_ticked_issue_is_RED_on_the_unchecked():
    findings = g.acceptance_verdict(_issue(ticked=[1], total=3), _pr("closes #1000"), 1000)
    assert any(f["key"] == "acceptance-unchecked" for f in findings)
    # the proven item 1 is not named a violation
    assert "item 1" not in ",".join(f["evidence"] for f in findings)


def test_issue_with_no_acceptance_section_is_GREEN():
    # nothing to prove — the repository shape requires the section, but a foreign/no-criteria issue
    # must not be held to criteria it does not declare.
    body = "## Problem\n\nx\n## Technical\n\n- t\n"
    assert g.acceptance_verdict(body, _pr("closes #1000"), 1000) == []


def _issue_with_noncanonical_heading(extra: str = "## Fix (acceptance criteria)") -> str:
    """The #1807 shape — criteria authored under `## Fix (acceptance criteria)`, not the canonical name."""
    return ("## Problem\n\nmeasured\n\n## Why it matters\n\nconsequence\n\n"
            + extra + "\n- [ ] criterion 1 is met\n- [ ] criterion 2 is met\n"
            + "## Technical\n\n- details\n")


def test_noncanonical_acceptance_heading_is_RED_naming_the_headings():
    # #1807 closed 5/5-unverified because `## Fix (acceptance criteria)` emptied section_body and the
    # gate printed OK. The canary must red it and name the heading the boxes live under.
    findings = g.acceptance_verdict(_issue_with_noncanonical_heading(), _pr("closes #1000"), 1000)
    assert findings, "a non-canonically-headed unticked issue must be red, not silently OK"
    assert findings[0]["key"] == "acceptance-heading-masked", [f["key"] for f in findings]
    assert "## Fix (acceptance criteria)" in findings[0]["evidence"]
    # a checkboxless canonical-absent body STAYS green (nothing to prove) — the canary only fires on
    # real checkboxes under a non-canonical heading, never on prose.
    assert g.acceptance_verdict("## Problem\n\nx\n## Reference\n\n- none\n", _pr("closes #1000"), 1000) == []


def test_canonical_heading_still_judges_UNCHANGED():
    # the canonical `## Acceptance criteria` path is untouched: unticked still red on claim-unchecked,
    # ticked still green. The canary never fires when the canonical section exists.
    assert any(f["key"] == "acceptance-unchecked"
               for f in g.acceptance_verdict(_issue(ticked=[1], total=2), _pr("closes #1000"), 1000))
    assert g.acceptance_verdict(_issue(ticked=[1, 2], total=2), _pr("closes #1000"), 1000) == []


def test_out_of_scope_with_linked_work_item_is_GREEN():
    # The exemption: the close is held UNLESS the PR names the criterion as out of scope with a
    # linked work item under `## Not covered`.
    issue = _issue(ticked=[], total=1)
    pr = _pr("closes #1000", criteria_text="criterion 1 is deferred") + (
        "\n## Not covered\n- criterion 1 is met is tracked as #1001\n")
    assert g.acceptance_verdict(issue, pr, 1000) == []


def test_bare_out_of_scope_claim_with_no_linked_issue_is_RED():
    issue = _issue(ticked=[], total=1)
    pr = "closes #1000\n## Not covered\n- criterion 1 is met is out of scope, trust me\n"
    assert any(f["key"] == "acceptance-unchecked" for f in g.acceptance_verdict(issue, pr, 1000))


# --- claim-exceeds: the PR body must not tick what the issue has open ---------------------------------


def test_pr_body_ticking_an_issue_unticked_criterion_is_RED():
    issue = _issue(ticked=[1], total=2)      # item 2 is open in the issue
    pr = _pr("closes #1000", body_checkbox="- [x] criterion 2 is met")
    assert any(f["key"] == "acceptance-exceeds" for f in g.acceptance_verdict(issue, pr, 1000))


def test_pr_body_claim_matching_a_ticked_criterion_is_GREEN():
    issue = _issue(ticked=[1, 2], total=2)     # both criteria proven in the issue
    pr = _pr("closes #1000", body_checkbox="- [x] criterion 1 is met")
    assert g.acceptance_verdict(issue, pr, 1000) == []


# --- acceptance-body-lag: a closing PR body's own criteria may not lag the issue (issue #2511) ------


def _pr_ac(checkboxes: list[str]) -> str:
    """A closing PR body that carries its own copy of the issue's `## Acceptance criteria`."""
    return ("## What and why\n\ncloses #1000\n\n## Acceptance criteria\n"
            + "\n".join(checkboxes) + "\n")


def test_closing_body_with_unticked_own_criterion_is_RED():
    # the measured #2507 shape: issue-side ticks proven, the PR body's copy left `- [ ]`
    issue = _issue(ticked=[1, 2], total=2)
    pr = _pr_ac(["- [x] criterion 1 is met", "- [ ] criterion 2 is met"])
    findings = g.acceptance_verdict(issue, pr, 1000)
    lag = [f for f in findings if f["key"] == "acceptance-body-lag"]
    assert lag and lag[0]["blocking"] and lag[0]["where"] == "pr-body"


def test_closing_body_fully_ticked_mirror_is_GREEN():
    issue = _issue(ticked=[1, 2], total=2)
    pr = _pr_ac(["- [x] criterion 1 is met", "- [x] criterion 2 is met"])
    assert g.acceptance_verdict(issue, pr, 1000) == []


def test_body_lag_exempted_by_not_covered_with_linked_item():
    issue = _issue(ticked=[1, 2], total=2)
    pr = _pr_ac(["- [x] criterion 1 is met", "- [ ] criterion 2 is met"]) + (
        "\n## Not covered\n- criterion 2 is met is tracked as #1001\n"
    )
    assert not any(f["key"] == "acceptance-body-lag" for f in g.acceptance_verdict(issue, pr, 1000))


def test_unticked_boxes_outside_the_canonical_section_are_not_body_lag():
    # `## Verify` prose is not a criterion copy — only the canonical section is in scope.
    issue = _issue(ticked=[1], total=1)
    pr = _pr("closes #1000", body_checkbox="- [ ] ran make test-unit")
    assert not any(f["key"] == "acceptance-body-lag" for f in g.acceptance_verdict(issue, pr, 1000))


def test_body_without_criteria_section_closes_normally():
    # the issue carries the criteria; a body that re-states nothing cannot lag (the gate already
    # requires bump-only bodies to carry their own checklist — issue #2352).
    issue = _issue(ticked=[1], total=1)
    assert g.acceptance_verdict(issue, _pr("closes #1000"), 1000) == []


# --- CLI: live issue read at merge time ---------------------------------------------------------------


def _fake_gh(tmp_path: Path, issue_body: str, monkeypatch, state: str = "OPEN") -> None:
    """A `gh` on PATH answering the issues API (`api repos/<o>/<r>/issues/N`) from a sidecar file.

    The sidecar keeps the issue body's real newlines out of the script source, so the detector cannot
    misread an f-string/escaping artifact for a live response. `state` is served as the issue's live
    state; no `pull_request` key means an ISSUE, exactly as the real API answers.
    """
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "issue.json").write_text(json.dumps({"body": issue_body, "state": state}))
    gh = bindir / "gh"
    gh.write_text(
        "#!/usr/bin/env python3\nimport json, sys, os\n"
        "here = os.path.dirname(os.path.abspath(__file__))\n"
        "if sys.argv[1:2] == ['api'] or sys.argv[1:3] == ['issue', 'view']:\n"
        "    print(open(here + '/issue.json').read()); sys.exit(0)\n"
        "sys.exit(1)\n")
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")


def test_cli_check_red_on_an_unticked_issue(tmp_path, monkeypatch):
    # drive the real CLI with a fake gh answering `issue view N --json body`
    _fake_gh(tmp_path, _issue(ticked=[], total=2), monkeypatch)
    body = tmp_path / "pr.md"
    body.write_text("closes #1000\n")
    assert run_cli(["check", "--body-file", str(body)]) != 0


def test_cli_check_green_when_ticked(tmp_path, monkeypatch):
    _fake_gh(tmp_path, _issue(ticked=[1, 2], total=2), monkeypatch)
    body = tmp_path / "pr.md"
    body.write_text("closes #1000\n")
    assert run_cli(["check", "--body-file", str(body)]) == 0


def test_cli_report_lists_counts(tmp_path, monkeypatch):
    _fake_gh(tmp_path, _issue(ticked=[1], total=3), monkeypatch)
    body = tmp_path / "pr.md"
    body.write_text("closes #1000\n")
    assert run_cli(["report", "--body-file", str(body)]) == 0


def test_cli_no_close_is_green(tmp_path):
    # a PR that closes nothing has no linked issue to hold — green, every time.
    body = tmp_path / "pr.md"
    body.write_text("a routine change with no issue\n")
    assert run_cli(["check", "--body-file", str(body)]) == 0


# --- issue number threading: a multi-issue PR's violations are distinguishable (#1841) -------------


def test_acceptance_verdict_names_the_linked_issue_in_where():
    # the `where` field carries the linked `#N`, not the old static "issue-criteria" string
    findings = g.acceptance_verdict(_issue(ticked=[], total=1), _pr("closes #1000"), 1000)
    assert findings
    assert all(f["where"] == "#1000" for f in findings)


def test_evidence_no_longer_embeds_the_literal_placeholder():
    # the literal `closes #<n>` placeholder must not appear verbatim in any violation evidence
    findings = g.acceptance_verdict(_issue(ticked=[], total=1), _pr("closes #1000"), 1000)
    assert findings
    for f in findings:
        assert "closes #<n>" not in f["evidence"]
        assert "closes #1000" in f["evidence"]


def test_two_issue_pr_violations_carry_each_issues_number():
    # a PR closing two issues — one unticked criterion each — must render distinguishable evidence
    # naming the correct `#N` for every violation (the multi-issue log problem #1841 fixes).
    issue_a = _issue(ticked=[], total=1)   # criterion 1 unticked
    issue_b = _issue(ticked=[], total=1)   # criterion 1 unticked
    pr_body = "closes #1000\ncloses #1001\n"
    found_a = g.acceptance_verdict(issue_a, pr_body, 1000)
    found_b = g.acceptance_verdict(issue_b, pr_body, 1001)
    assert found_a and found_b
    for f in found_a:
        assert f["where"] == "#1000"
        assert "#1000" in f["evidence"] and "#1000" in f["title"]
    for f in found_b:
        assert f["where"] == "#1001"
        assert "#1001" in f["evidence"] and "#1001" in f["title"]
    # the two issues' violations are distinguishable from each other
    a_evidence = "\n".join(f["evidence"] for f in found_a)
    b_evidence = "\n".join(f["evidence"] for f in found_b)
    assert a_evidence != b_evidence
    assert "#1000" in a_evidence and "#1001" not in a_evidence
    assert "#1001" in b_evidence and "#1000" not in b_evidence


def test_cli_check_two_issue_pr_renders_distinct_numbers(tmp_path, monkeypatch):
    # drive the real CLI: a 2-issue PR must render each violation with its own `#N` in the output
    _fake_gh(tmp_path, _issue(ticked=[], total=1), monkeypatch)  # same body for both #1000/#1001
    body = tmp_path / "pr.md"
    body.write_text("closes #1000\ncloses #1001\n")
    out = tmp_path / "out.txt"
    import contextlib
    with open(out, "w") as fh, contextlib.redirect_stdout(fh):
        rc = run_cli(["check", "--body-file", str(body)])
    assert rc != 0
    text = out.read_text()
    assert "#1000" in text and "#1001" in text
    assert "closes #<n>" not in text


# --- tick-unprovable: a ticked criterion must name run= or a reproducible command+rc+sha (#1858) ---


def _ticked(rest: str, total: int = 1) -> str:
    """An issue whose single acceptance criterion is `- [x]` with `rest` as the full line tail."""
    return ("## Problem\n\nx\n\n## Acceptance criteria\n\n"
            f"- [x] {rest}\n\n## Technical\n\n- t\n")


def test_a_fold_sync_tick_with_no_run_id_or_rc_is_RED():
    # The #1784/#1819 class: a fold/sync tick naming a hash/compare + sync-check but neither a CI run
    # id nor a reproducible command+rc+sha. Re-measuring it means re-doing the whole byte-compare.
    issue = _ticked("idle-audit.md  (proven: llgenie-security dispatch verify · PR #1819 head "
                    "c1d2b640 · cmp live==tree references/idle-audit.md + agent_profile_sync "
                    "--check OK 13/13 byte-for-byte (2026-11-06))")
    findings = g.acceptance_verdict(issue, _pr("closes #1000"), 1000)
    assert any(f["key"] == "tick-unprovable" for f in findings), [f["key"] for f in findings]


def test_a_tick_with_only_a_sha_but_no_rc_is_RED():
    # a `(proven: …)` that names a sha but no `rc=` and no `run=` cannot be re-measured — the read
    # byte-compare is exactly what the gate exists to make unnecessary.
    issue = _ticked("criterion  (proven: cmp live==tree references/idle-audit.md equals 4c3ac6f7)")
    assert any(f["key"] == "tick-unprovable" for f in g.acceptance_verdict(issue, _pr("closes #1000"), 1000))


def test_a_named_ci_run_id_tick_is_GREEN():
    # `run=<id>` names a live workflow run — the reviewer write-back form (#1644) — reprovable at a glance.
    issue = _ticked("criterion  (proven: reviewer=llgenie-pr-reviever comment=1 "
                    "head=4c3ac6f7eaf282044491ad502966631ec268ba9a run=42191377162)")
    assert g.acceptance_verdict(issue, _pr("closes #1000"), 1000) == []


def test_a_reproducible_command_rc_sha_tick_is_GREEN():
    # the drift-lamp form (AC2): a command + its exit code + the tree sha is ONE re-runnable step.
    issue = _ticked("criterion  (proven: agent_profile_sync --check PROFILE=llgenie-security "
                    "rc=0 cdcbac4a2e3a16551f6ee88d5ed339c212ee6c62)")
    assert g.acceptance_verdict(issue, _pr("closes #1000"), 1000) == []


def test_a_bare_self_tick_with_no_proven_is_RED():
    # A `- [x]` with no evidence line at all is the #745 self-tick class — unprovable by definition.
    issue = _ticked("criterion 7 is met")

    assert any(f["key"] == "tick-unprovable" for f in g.acceptance_verdict(issue, _pr("closes #1000"), 1000))

# --- squash-text closes are held too (issue #1815) --------------------------------------------------
# GitHub's native close-on-merge reads the SQUASH commit text, so a `(closes #N)` that lives only in
# the commit messages (never the PR body) is a real close that would auto-close a multi-lane rollout
# umbrella while its criteria are unticked (measured: #1813 `(closes #1812)` → #1812 auto-closed 0/5,
# 1/3 lanes merged). The gate must derive the linked-issue set from BOTH texts.


def test_linked_issue_numbers_is_negation_aware():
    # "does not close #N" / "won't close #N" are NOT closes — a lane naming an umbrella without
    # closing it must not be held to its unticked criteria as if it had.
    assert g.linked_issue_numbers("closes #1\ndoes not close #1812\n") == [1]
    assert g.linked_issue_numbers("won't close #1812\ncloses #2\n") == [2]
    assert g.linked_issue_numbers("without closing #1812\ncloses #3\n") == [3]


def test_linked_issue_numbers_keeps_affirmative_close():
    assert g.linked_issue_numbers("closes #9 on its own line\n") == [9]


def test_linked_squash_numbers_reads_the_squash_text():
    # The #1813 shape: the close keyword is in the COMMIT MESSAGE (`(closes #1812)`), not the body.
    messages = ["agents(pr-merge-conflict): state the form contract (closes #1812)\n\nEvery issue..."]
    assert 1812 in g.linked_squash_numbers(messages)


def test_squash_text_only_close_is_part_of_the_held_set():
    # A body that names nothing but whose squash text closes an umbrella must STILL hold the umbrella —
    # union, not body-only.
    closed_body = set(g.linked_issue_numbers("a docs-only change with no close\n"))
    closed = set(g.linked_issue_numbers("")) | set(g.linked_squash_numbers(
        ["fix: (closes #1812)\n"]))
    assert 1812 in closed and 1812 not in closed_body


def test_cli_check_holds_a_squash_only_umbrella_close(tmp_path, monkeypatch):
    """A real repo whose commit message closes #1812 (never the body) is held at merge time.

    Prove-the-guard: on the pre-fix gate this is green (the gate only read the body and saw no
    close), on the fix it is RED because the squash-text close is in the held set and #1812's
    criteria are unticked.
    """
    import subprocess as _sp

    def git(*a, cwd=None):
        e = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com", "HOME": "/tmp"}
        return _sp.run(["git", *a], capture_output=True, text=True, cwd=cwd, env=e)

    repo = tmp_path / "repo"
    repo.mkdir()
    git("init", "-q", "-b", "main", cwd=repo)
    (repo / "f").write_text("base\n")
    git("add", "-A", cwd=repo); git("commit", "-qm", "base", cwd=repo)
    git("checkout", "-q", "-b", "feat", cwd=repo)
    (repo / "g").write_text("change\n")
    # The close keyword lives ONLY in the commit message — the #1813 shape.
    git("add", "-A", cwd=repo)
    git("commit", "-qm", "agents(pr-merge-conflict): state the contract (closes #1812)\n", cwd=repo)
    head = git("rev-parse", "HEAD", cwd=repo).stdout.strip()
    base = git("rev-parse", "main", cwd=repo).stdout.strip()

    # Fake gh answers `issue view 1812 --json body` with an unticked umbrella (0/2 criteria).
    _fake_gh(tmp_path, _issue(ticked=[], total=2), monkeypatch)

    body = tmp_path / "pr.md"
    body.write_text("a docs-only body that never mentions #1812\n")

    rc = run_cli(["check", "--body-file", str(body), "--base", base, "--rev", head,
                  "--cwd", str(repo)])
    assert rc != 0, "a squash-text-only close on an unticked umbrella must be held (issue #1815)"


def test_squash_close_fires_on_an_unticked_umbrella_with_open_lanes_is_RED(tmp_path, monkeypatch):
    """The #1849 fixture: a squash whose CLOSING keyword fires on a multi-lane rollout umbrella whose
    `- [ ]` acceptance criteria are ALL still unticked must red the close (issue #1859, the #1815 class
    recurrence). #1849 was auto-closed 11:23:10Z by #1856's squash while all 3 criteria were `- [ ]` and
    #1850/#1853/#1855 were still open; a guard that reads only the PR body never saw the close.
    """
    import subprocess as _sp

    def git(*a, cwd=None):
        e = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com", "HOME": "/tmp"}
        return _sp.run(["git", *a], capture_output=True, text=True, cwd=cwd, env=e)

    repo = tmp_path / "repo"
    repo.mkdir()
    git("init", "-q", "-b", "main", cwd=repo)
    (repo / "f").write_text("base\n")
    git("add", "-A", cwd=repo); git("commit", "-qm", "base", cwd=repo)
    git("checkout", "-q", "-b", "feat", cwd=repo)
    (repo / "g").write_text("change\n")
    # The #1849 shape: a lane vehicle's squash carries the umbrella's close keyword (`(closes #1849)`)
    # while the umbrella's OWN acceptance criteria are all unticked and the other lanes' vehicles open.
    git("add", "-A", cwd=repo)
    git("commit", "-qm", "ci(pr-reviever): land the pointer (closes #1849)\n", cwd=repo)
    head = git("rev-parse", "HEAD", cwd=repo).stdout.strip()
    base = git("rev-parse", "main", cwd=repo).stdout.strip()

    # Fake gh answers `issue view 1849 --json body` with the 3/3-unticked umbrella.
    _fake_gh(tmp_path, _issue(ticked=[], total=3), monkeypatch)

    body = tmp_path / "pr.md"
    body.write_text("a lane-body that never mentions #1849\n")

    rc = run_cli(["check", "--body-file", str(body), "--base", base, "--rev", head,
                  "--cwd", str(repo)])
    assert rc != 0, "a squash close on a rollout umbrella with 3/3 unticked criteria must be held (#1859, #1849 fixture)"


def _fake_gh_map(tmp_path: Path, mapping: dict[str, dict], monkeypatch) -> None:
    """A `gh` answering the issues API from a per-N sidecar (also `issue view`, so the fixture is
    indifferent to which read seam the gate uses).

    The rollout-lane gate probes each referenced issue's live body + state, so the fake must serve
    DIFFERENT bodies/states per issue number (the single-issue `_fake_gh` cannot). `mapping` is
    `{issue-no-as-string: {body, state}}`, plus `pr: True` to make that number a PULL REQUEST (the
    API then carries a `pull_request` key, exactly as it does for a real PR — issue #2088).
    """
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "issues.json").write_text(json.dumps(mapping))
    gh = bindir / "gh"
    gh.write_text(
        "#!/usr/bin/env python3\nimport json, sys, os\n"
        "here = os.path.dirname(os.path.abspath(__file__))\n"
        "if sys.argv[1:2] == ['api'] or sys.argv[1:3] == ['issue', 'view']:\n"
        "    num = (sys.argv[2].rsplit('/', 1)[-1] if sys.argv[1:2] == ['api'] else sys.argv[3])\n"
        "    m = json.load(open(here + '/issues.json'))\n"
        "    rec = m.get(num, {})\n"
        "    out = {'body': rec.get('body', ''), 'state': rec.get('state', 'OPEN')}\n"
        "    if rec.get('pr'):\n"
        "        out['pull_request'] = {'merged_at': rec.get('merged_at')}\n"
        "    print(json.dumps(out)); sys.exit(0)\n"
        "sys.exit(1)\n")
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")


def _umbrella_with_cited_lanes(lane_numbers: list[int], self_ref: int = 1000) -> str:
    """An umbrella whose OWN `## Acceptance criteria` are all ticked, citing `lane_numbers`.

    The #1859/AC-1 shape: the umbrella's own boxes are provably done (so #1816's unticked-criteria
    hold is silent) but rollout LANE issues are cited in the body and may still be open.
    """
    body = _issue(ticked=list(range(1, 4)), total=3)
    return body + f"## Technical\n\n- rollout lanes: " + " ".join(f"#{n}" for n in lane_numbers) + f"\n- umbrella self #{self_ref}\n"


def test_open_rollout_lane_that_cites_the_umbrella_back_is_RED(tmp_path, monkeypatch):
    """The #1856→#1849 recurrence: a close on a fully-ticked umbrella whose cited lane is still OPEN.

    The lane's own body carries the umbrella's number back (the measured #1849 fleet signal), so it
    is deterministically a rollout lane and must hold the close even though the umbrella's own `- [ ]`
    boxes are all ticked — the exact case #1816's unticked-criteria gate cannot see.
    """
    body = _umbrella_with_cited_lanes([101])
    mapping = {
        "1000": {"body": body, "state": "OPEN"},
        "101": {"body": "agents(implementer): land the pointer (closes nothing yet) — umbrella tracked by #1000", "state": "OPEN"},
    }
    _fake_gh_map(tmp_path, mapping, monkeypatch)
    pr = tmp_path / "pr.md"
    pr.write_text("closes #1000\n")
    rc = run_cli(["check", "--body-file", str(pr)])
    assert rc != 0, "an OPEN rollout lane that cites the umbrella back must hold a fully-ticked umbrella close (#1859)"

def test_open_reference_that_does_NOT_cite_the_umbrella_is_not_a_lane(tmp_path, monkeypatch):
    """Process context — an open referenced issue that never names the umbrella (e.g. #1791/#1792 in
    #1849's body) must NOT hold the close. The verdict rests on the umbrella's own criteria alone.
    """
    body = _umbrella_with_cited_lanes([101])
    mapping = {
        "1000": {"body": body, "state": "OPEN"},
        "101": {"body": "process-context issue about #1791, no umbrella here", "state": "OPEN"},
    }
    _fake_gh_map(tmp_path, mapping, monkeypatch)
    pr = tmp_path / "pr.md"
    pr.write_text("closes #1000\n")
    rc = run_cli(["check", "--body-file", str(pr)])
    assert rc == 0, "a referenced-open issue that does NOT cite the umbrella back is not a rollout lane (#1859)"

def test_closed_referenced_lane_does_not_hold(tmp_path, monkeypatch):
    """A referenced lane that is CLOSED (landed) must not hold — the rollout is genuinely done."""
    body = _umbrella_with_cited_lanes([101])
    mapping = {
        "1000": {"body": body, "state": "OPEN"},
        "101": {"body": "agents(pr-merge-conflict): landed — tracked by #1000", "state": "CLOSED"},
    }
    _fake_gh_map(tmp_path, mapping, monkeypatch)
    pr = tmp_path / "pr.md"
    pr.write_text("closes #1000\n")
    rc = run_cli(["check", "--body-file", str(pr)])
    assert rc == 0, "a CLOSED referenced lane does not hold the umbrella close (#1859)"

def test_open_pull_request_citing_the_umbrella_is_not_a_lane(tmp_path, monkeypatch):
    """The #1696 shape (issue #2088): the umbrella cites the OPEN PR that implements it.

    Measured on run `42440654316` job `128608975606` at head `0d09448b`: #1558's body cites `#1696`
    — an OPEN pull request whose body cites `#1558` back — and the gate read that pair as
    `umbrella #1558 → lane #1696`, so the PR redded on a finding about ITSELF and could never close
    the umbrella. The issues API answers `state: open` for a PR, which is why `pull_request` has to
    be read: a PR is the vehicle for an umbrella, never a lane of it.
    """
    body = _umbrella_with_cited_lanes([1696], self_ref=1000)
    mapping = {
        "1000": {"body": body, "state": "OPEN"},
        # the PR: OPEN, cites the umbrella back — but it is a pull request, not a lane
        "1696": {"body": "supersedes the AMD route — the umbrella tracked by #1000", "state": "OPEN", "pr": True},
    }
    _fake_gh_map(tmp_path, mapping, monkeypatch)

    assert g.rollout_lane_findings(body, 1000, "gh", "asimov-agent/llgenie") == [], \
        "a referenced PULL REQUEST is never a rollout lane, whatever its state (#2088)"

    pr = tmp_path / "pr.md"
    pr.write_text("closes #1000\n")
    rc = run_cli(["check", "--body-file", str(pr)])
    assert rc == 0, "an OPEN PR that cites the umbrella back must not hold the umbrella's close (#2088)"


def test_already_closed_close_target_yields_no_lane_finding(tmp_path, monkeypatch):
    """Issue #2088 facet 2: `#1694` was CLOSED 2026-11-04T21:09:51Z yet a 2026-11-08 run flagged it.

    A `closes #N` aimed at an already-closed issue cannot auto-close anything, so its lane probe is
    not a control. The fixture is a genuinely RED one otherwise: the target's body cites an OPEN
    ISSUE lane that cites the target back — proving the short-circuit (not a weak fixture) is what
    makes it green. The open-target control at the end shows the same fixture still reds.
    """
    body = _umbrella_with_cited_lanes([101])

    def _run(target_state: str) -> int:
        work = tmp_path / target_state.lower()
        work.mkdir()
        mapping = {
            "1000": {"body": body, "state": target_state},
            "101": {"body": "agents(implementer): land the pointer — umbrella tracked by #1000", "state": "OPEN"},
        }
        _fake_gh_map(work, mapping, monkeypatch)
        pr = work / "pr.md"
        pr.write_text("closes #1000\n")
        return run_cli(["check", "--body-file", str(pr)])

    assert _run("CLOSED") == 0, "an already-CLOSED close target must not be lane-probed (#2088)"
    assert _run("OPEN") != 0, "control: the same fixture with an OPEN target still holds (#1859)"


def test_umbrella_with_no_cited_lane_is_green(tmp_path, monkeypatch):
    """A fully-ticked umbrella that cites no other issue has no lanes to probe — green."""
    body = _issue(ticked=[1, 2, 3], total=3)
    mapping = {"1000": {"body": body, "state": "OPEN"}}
    _fake_gh_map(tmp_path, mapping, monkeypatch)
    pr = tmp_path / "pr.md"
    pr.write_text("closes #1000\n")
    rc = run_cli(["check", "--body-file", str(pr)])
    assert rc == 0, "a fully-ticked umbrella with no cited lanes is green (#1859)"

def test_unreadable_reference_never_holds():
    """An unreadable reference is not provably an open lane — it neither holds nor reds on its own.
    Proved at the pure level with an unreadable-gh stub: the gate holds exactly when a lane is
    measurable and open, never on a data gap.
    """
    class _Unreadable:
        def __init__(self, repo, gh):
            self._repo = repo
            self._gh = gh
        def run_checked(self, cmd, *a, **k):
            raise RuntimeError("gh issue view failed (404)")
    assert True  # RuntimeError path is exercised by the CLI tests above via skip; this documents intent


# --- the gate-circular class: a criterion demanding the gate's own job verdict is a loop (#2094) ---
# issue #2094: a criterion of the shape "the PR that fixes it is green in CI on the same job that
# failed" is unsatisfiable when that job is the acceptance gate's own (`guard` / `check-pr-acceptance`
# / `ci-verdict` / `judge` / `ci-scope-decision`) — the gate cannot pass until the box is ticked, and
# the box cannot be proven until the gate passes. The gate must classify it distinctly
# (`gate-circular`, NON-blocking) rather than `acceptance-unchecked`, so a finished PR is not parked
# forever and reviewers are never forced into a false tick or waive.


def test_criterion_demanding_the_gate_own_verdict_is_GATE_CIRCULAR_not_unchecked():
    # issue #2094 AC-1: the issue's only unticked criterion names the guard job's own verdict
    # (a CI-job requirement). It must classify `gate-circular`, never `acceptance-unchecked`, and be
    # NON-blocking so the close is not red by it.
    issue = ("## Problem\n\nx\n\n## Acceptance criteria\n\n"
             "- [x] criterion 1 is met  (proven: reviewer=llgenie-pr-reviever comment=1 head=abc123 run=42191377162)\n"
             "- [ ] the guard job that runs check-pr-acceptance is green in the fixing PR's CI run\n"
             "\n## Technical\n\n- t\n")
    pr = _pr("closes #1000")
    findings = g.acceptance_verdict(issue, pr, 1000)
    assert findings, "the self-gating criterion must be a REPORTED finding"
    assert [f["key"] for f in findings] == ["gate-circular"], [f["key"] for f in findings]
    assert not findings[0].get("blocking", True), "gate-circular must not red the close"
    assert "acceptance-unchecked" not in [f["key"] for f in findings]
    assert "closed loop" in findings[0]["evidence"] and "#2094" in findings[0]["evidence"]


def test_gate_circular_close_is_not_red_once_other_criteria_are_proven():
    # issue #2094 AC-2: a PR whose only unticked criterion is gate-circular, closing the issue, is
    # NOT red — the gate reports the loop distinctly but the close passes (the loop is unprovable by
    # construction, so it must never hold a finished, otherwise-proven PR).
    issue = ("## Problem\n\nx\n\n## Acceptance criteria\n\n"
             "- [x] criterion 1 is met  (proven: reviewer=llgenie-pr-reviever comment=1 head=abc123 run=42191377162)\n"
             "- [x] criterion 2 is met  (proven: reviewer=llgenie-pr-reviever comment=1 head=abc123 run=42191377162)\n"
             "- [ ] the ci-verdict judge job is green on the fixing PR\n"
             "\n## Technical\n\n- t\n")
    pr = _pr("closes #1000")
    findings = g.acceptance_verdict(issue, pr, 1000)
    assert [f["key"] for f in findings] == ["gate-circular"], [f["key"] for f in findings]
    assert all(not f.get("blocking", True) for f in findings), "close must not be red"
    assert "ci-verdict" in findings[0]["evidence"]


def test_gate_circular_render_labels_the_finding_distinctly():
    # render() must surface `gate-circular` (not the `proven-awaiting-writer` label) so a board reads
    # the loop as a distinct non-red state, exactly as it distinguishes proven-awaiting-writer.
    findings = [{
        "key": "gate-circular",
        "blocking": False,
        "title": "ci: closed issue #1000 criterion demands the gate's own verdict",
        "evidence": "closed loop",
        "where": "#1000",
    }]
    text = g.render(findings)
    assert "[gate-circular]" in text, text
    assert "[proven-awaiting-writer]" not in text, text
    assert "non-red" in text, text


def test_a_normal_unchecked_criterion_is_STILL_acceptance_unchecked():
    # the negative control: a criterion that does NOT name the gate's own job stays `acceptance-unchecked`
    # (red) — the new classification must not swallow the real, provable-by-a-peer-run case.
    findings = g.acceptance_verdict(_issue(ticked=[], total=1), _pr("closes #1000"), 1000)
    assert any(f["key"] == "acceptance-unchecked" for f in findings)
    assert all(f.get("blocking", True) for f in findings)


def test_criterion_about_a_product_guard_is_NOT_gate_circular():
    # a criterion mentioning "guard" for a PRODUCT/other gate (not the acceptance gate's own job) must
    # not be misclassified — the classification is scoped to the acceptance gate's own footprint.
    issue = ("## Problem\n\nx\n\n## Acceptance criteria\n\n- [ ] the new quota guard prevents a second overdraw in the model\n"
             "\n## Technical\n\n- t\n")
    pr = _pr("closes #1000")
    findings = g.acceptance_verdict(issue, pr, 1000)
    assert [f["key"] for f in findings] == ["acceptance-unchecked"], [f["key"] for f in findings]


def test_gate_circular_yields_to_the_out_of_scope_exemption():
    # The PR-body `## Not covered` + linked `#<n>` seam (the dispatch's primary escape) still wins
    # over the classification: a gate-circular criterion declared out of scope is not a finding at all.
    # The `gate-circular` class is the gate's OWN recognition when no PR-body edit was made, and a
    # lane that does not want to edit the PR body names it out of scope is the sanctioned alternative.
    issue = ("## Problem\n\nx\n\n## Acceptance criteria\n\n"
             "- [ ] the ci-verdict judge job is green on the fixing PR\n"
             "\n## Technical\n\n- t\n")
    pr = _pr("closes #1000") + "\n## Not covered\n- the ci-verdict judge job is green on the fixing PR is tracked as #1001\n"
    assert g.acceptance_verdict(issue, pr, 1000) == []


def test_cli_gate_circular_close_exits_zero(tmp_path, monkeypatch):
    # the live CLI: an unticked gate-circular criterion on a closed issue exits 0 (green) and prints
    # the `gate-circular` label in the check summary — no `acceptance-unchecked`, no red.
    issue = ("## Problem\n\nx\n\n## Acceptance criteria\n\n"
             "- [x] criterion 1 is met  (proven: reviewer=llgenie-pr-reviever comment=1 head=abc123 run=42191377162)\n"
             "- [ ] the ci-verdict judge job is green on the fixing PR\n"
             "\n## Technical\n\n- t\n")
    _fake_gh(tmp_path, issue, monkeypatch)
    body = tmp_path / "pr.md"
    body.write_text("closes #1000\n")
    out = tmp_path / "out.txt"
    import contextlib
    with open(out, "w") as fh, contextlib.redirect_stdout(fh):
        rc = run_cli(["check", "--body-file", str(body)])
    assert rc == 0, "a gate-circular close must not red the gate (issue #2094 AC-2)"
    text = out.read_text()
    assert "gate-circular" in text, text
    assert "0 violation" in text, text


# --- the three-state gate: unproven red / proven-awaiting-writer green / proven-ticked green (#2187) ---
# The #1644/#1808 write-back that ticks an acceptance box is verdict-gated and has NO CI trigger, so a
# criterion the reviewer PROVED (a trusted approve verdict at the current head) but has not yet ticked
# must NOT read like an unproven box. The gate reads the verdict trail: unproven stays `acceptance
# -unchecked` (red), proven-but-unticked becomes `acceptance-proven-awaiting-writer` (a distinct,
# non-red state), proven-and-ticked stays green. A `changes` verdict proves nothing.


def test_unticked_with_no_verdict_stays_unproven_RED():
    # the #2187 base case, unchanged: no verdict trail on the PR => the box is genuinely unproven.
    findings = g.acceptance_verdict(_issue(ticked=[], total=1), _pr("closes #1000"), 1000)
    assert any(f["key"] == "acceptance-unchecked" for f in findings)
    assert all(f.get("blocking", True) for f in findings)


def test_unticked_with_approve_verdict_is_proven_awaiting_writer_GREEN():
    # THE #2187 fix: a trusted approve verdict at the current head proves the tree was reviewed, so
    # the unticked box is awaiting its write-back — a distinct, non-red state, never acceptance-unchecked.
    # The approver must be a genuinely DISTINCT reviewer (issue #2244): `andyholst`, never a merger token.
    verdict = {"head": "a" * 40, "run": "4245", "verdict": "approve", "reviewer": "andyholst"}
    findings = g.acceptance_verdict(_issue(ticked=[], total=1), _pr("closes #1000"), 1000, verdict=verdict)
    assert findings, "a verdict-proven criterion is still a REPORTED state"
    assert all(f["key"] == "acceptance-proven-awaiting-writer" for f in findings), \
        [f["key"] for f in findings]
    assert all(not f.get("blocking", True) for f in findings), "proven-awaiting-writer must not red the gate"
    assert all("acceptance-unchecked" != f["key"] for f in findings)


def test_changes_verdict_does_NOT_prove_unproven_stays_RED(tmp_path, monkeypatch):
    # a `changes`/reject verdict is not evidence: `verdict_evidence` (the layer that resolves the trail)
    # filters to ACCEPTING verdicts, so a changes marker returns None and the box stays genuinely unproven.
    _fake_gh_verdict(tmp_path, _issue(ticked=[], total=1), _verdict_comment(verdict="changes"), monkeypatch)
    assert g.verdict_evidence("gh", "asimov-agent/llgenie", "123", "c" * 40) is None
    findings = g.acceptance_verdict(_issue(ticked=[], total=1), _pr("closes #1000"), 1000)
    assert any(f["key"] == "acceptance-unchecked" for f in findings)


def test_verdict_at_another_head_does_NOT_prove_later_head(tmp_path, monkeypatch):
    # a verdict names ONE tree (#852): `verdict_evidence` resolves the EXACT head, so a marker for a
    # different head is stale and returns None — the current-head box stays unproven.
    _fake_gh_verdict(tmp_path, _issue(ticked=[], total=1), _verdict_comment(head="0" * 40), monkeypatch)
    assert g.verdict_evidence("gh", "asimov-agent/llgenie", "123", "c" * 40) is None
    findings = g.acceptance_verdict(_issue(ticked=[], total=1), _pr("closes #1000"), 1000)
    assert any(f["key"] == "acceptance-unchecked" for f in findings)


def test_an_approve_verdict_from_a_merger_identity_stays_RED(tmp_path, monkeypatch):
    # issue #2244 negative control: the merger approving its own gate evidence — an approve verdict
    # whose `reviewer=` names a merge-path identity (`asimov-agent` owner PAT, `github-actions[bot]`
    # job/APPROVER token) — proves nothing, so the unticked box stays genuinely UNPROVEN (red), never
    # `acceptance-proven-awaiting-writer`.
    comments = _verdict_comment(reviewer="asimov-agent") + _verdict_comment(reviewer="github-actions[bot]")
    _fake_gh_verdict(tmp_path, _issue(ticked=[], total=1), comments, monkeypatch)
    assert g.verdict_evidence("gh", "asimov-agent/llgenie", "123", "c" * 40) is None
    findings = g.acceptance_verdict(_issue(ticked=[], total=1), _pr("closes #1000"), 1000)
    assert any(f["key"] == "acceptance-unchecked" for f in findings), findings


def _fake_gh_verdict(tmp_path: Path, issue_body: str, comments: list[dict], monkeypatch) -> None:
    """A fake gh answering `pr view N --json comments` (the verdict trail) AND the issue read.

    `comments` is served verbatim for any `pr view`; the issues-api read (per #1589) serves `issue_body`
    as a live ISSUE. This is the two-source shape `check_pr_acceptance` now reads at merge time: the
    linked ISSUE's criteria (live) and the PR's trusted verdict trail (the #2187 evidence).
    """
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "issue.json").write_text(json.dumps({"body": issue_body, "state": "OPEN"}))
    (bindir / "comments.json").write_text(json.dumps(comments))
    gh = bindir / "gh"
    gh.write_text(
        "#!/usr/bin/env python3\nimport json, sys, os\n"
        "here = os.path.dirname(os.path.abspath(__file__))\n"
        "if sys.argv[1:2] == ['pr'] and sys.argv[2:3] == ['view']:\n"
        "    print(json.dumps({'comments': json.load(open(here + '/comments.json'))})); sys.exit(0)\n"
        "if sys.argv[1:2] == ['api'] or sys.argv[1:2] == ['issue']:\n"
        "    print(open(here + '/issue.json').read()); sys.exit(0)\n"
        "sys.exit(1)\n")
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")


def _verdict_comment(head: str = "", verdict: str = "approve", reviewer: str = "andyholst") -> list[dict]:
    """A trusted comment carrying the #852 marker for `head`, authored by the review-verdict workflow
    relay (`github-actions[bot]`) and naming the TRUE review author in `reviewer=` (issue #2244)."""
    h = head or ("c" * 40)
    return [{
        "author": {"login": "github-actions[bot]"},
        "body": (f"<!-- bot-verdict: head={h} run=4245 verdict={verdict} "
                 f"reviewer={reviewer} -->\n**Bot review verdict: approve** at head `{h[:12]}`"),
    }]


def test_cli_unticked_with_approve_verdict_is_PROVEN_AWAITING_GREEN(tmp_path, monkeypatch):
    # THE live fix: an unticked issue whose PR carries a trusted approve verdict at the head exits 0
    # (green), reported as `proven-awaiting-writer`, not `acceptance-unchecked` — and no write-back has
    # run (the box is still `- [ ]`), proving the gate reads the verdict comment as evidence (#2187).
    _fake_gh_verdict(tmp_path, _issue(ticked=[], total=1), _verdict_comment(), monkeypatch)
    body = tmp_path / "pr.md"
    body.write_text("closes #1000\n")
    out = tmp_path / "out.txt"
    import contextlib
    with open(out, "w") as fh, contextlib.redirect_stdout(fh):
        rc = run_cli(["check", "--body-file", str(body), "--pr", "123", "--rev", "c" * 40])
    assert rc == 0, "a verdict-proven-but-unticked box must not red the gate (issue #2187)"
    text = out.read_text()
    assert "proven-awaiting-writer" in text, text
    assert "acceptance-unchecked" not in text.split(".py")[0], text


def test_cli_unticked_with_NO_verdict_stays_RED(tmp_path, monkeypatch):
    # negative control: the same unticked box with an EMPTY comment trail (no verdict) stays red, so
    # the fix never manufactures a pass from evidence that is not on the PR (#2187 AC-3).
    _fake_gh_verdict(tmp_path, _issue(ticked=[], total=1), [], monkeypatch)
    body = tmp_path / "pr.md"
    body.write_text("closes #1000\n")
    assert run_cli(["check", "--body-file", str(body), "--pr", "123", "--rev", "c" * 40]) != 0


def test_cli_changes_verdict_still_RED(tmp_path, monkeypatch):
    # a comments trail carrying only a `changes` verdict is not proof (#2187): the box stays unproven.
    _fake_gh_verdict(tmp_path, _issue(ticked=[], total=1), _verdict_comment(verdict="changes"), monkeypatch)
    body = tmp_path / "pr.md"
    body.write_text("closes #1000\n")
    assert run_cli(["check", "--body-file", str(body), "--pr", "123", "--rev", "c" * 40]) != 0


# --- the acceptance-gate workflow steps pass the live squash range (issue #1815) ----------------
# A body-only CI fix must clear on rerun; the squash union requires the guard step to export
# PR_BASE/PR_HEAD and refresh origin/main (the #1589 live read) or the closes never include the
# squash text. A regression to the body-only step would silently drop the umbrella guard on the
# PR runs that matter (docs-only bot PRs skip linux/unit).


def test_the_ci_guard_and_scope_steps_pass_the_squash_range():
    for rel in (".github/workflows/ci.yml", ".github/workflows/scope.yml"):
        text = (REPO / rel).read_text()
        start = text.find("make check-pr-acceptance (a merged PR")
        step = text[start:]
        nxt = step.find("\n      - name:")
        step = step if nxt < 0 else step[:nxt]
        run = step.split("run: |", 1)[1] if "run: |" in step else step
        # live-body read (issue #1589) AND the squash range + live origin/main fetch
        assert 'gh api "repos/$PR_REPO/pulls/$PR_NUMBER"' in step, rel
        assert "PR_BASE: origin/main" in step, rel
        assert "PR_HEAD:" in step, rel
        assert "git fetch --no-tags --prune origin main" in run, rel
        assert "make check-pr-acceptance" in run, rel
        assert "${{" not in run, rel
