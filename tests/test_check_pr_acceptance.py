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


# --- CLI: live issue read at merge time ---------------------------------------------------------------


def _fake_gh(tmp_path: Path, issue_body: str, monkeypatch) -> None:
    """A `gh` on PATH answering `issue view N --json body` from a sidecar file.

    The sidecar keeps the issue body's real newlines out of the script source, so the detector cannot
    misread an f-string/escaping artifact for a live response.
    """
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "issue.json").write_text(json.dumps({"body": issue_body}))
    gh = bindir / "gh"
    gh.write_text(
        "#!/usr/bin/env python3\nimport json, sys, os\n"
        "if sys.argv[1:3] == ['issue', 'view']:\n"
        "    here = os.path.dirname(os.path.abspath(__file__))\n"
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
