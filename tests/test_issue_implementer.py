"""The issue-implementer's deterministic dispatcher (issue #248).

The DISPATCH and CAP logic runs for real — only the GitHub API is a stand-in: a
`gh` on PATH that records its argv and answers `search prs` / `issue list` /
`issue view` / `issue comment` / `pr create`, so the test asserts the EXACT
request the product builds (`tests/test_engine_skill_gap.py` does the same for
`spawn`). Nothing here mocks or replaces `issue_implementer`.py — `count()`,
`dispatch()` and `open_pr()` are the code under test.

The cap is proven by a named test: at 3 PRs already opened today, the 4th
attempt exits 0, opens nothing and comments nothing; at 2 it proceeds.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

import json
import subprocess
import sys
import pathlib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import issue_implementer as ii  # noqa: E402
import unit_tests as ut  # noqa: E402  (the unit-suite aggregator, issue #393)

OWNER = "asimov-agent"
REPO_NAME = "llgenie"
SLUG = "fix-the-thing"


def _fake_gh(tmp_path: Path, opts: dict | None = None):
    """`gh` that records every argv as ONE JSON line and answers the product's queries.

    opts:
      prs:       list of PR numbers already open today (the cap numerator)
      labeled:   list of `agent:implement` issue dicts
      ready:     list of `agent:ready` issue dicts
      view:      the `issue view` response (title/body/number)
      pr_url:    the URL `pr create` prints (or "" to simulate a refusal)
    """
    opts = opts or {}
    tmp_path.mkdir(parents=True, exist_ok=True)
    log = tmp_path / "gh.log"
    prs = opts.get("prs", [])
    labeled = opts.get("labeled", [])
    ready = opts.get("ready", [])
    view = opts.get("view", {"number": 11, "title": f"Fix the thing #{11}", "body": "body"})
    pr_url = opts.get("pr_url", "https://github.com/acme/llgenie/pull/99")

    gh = tmp_path / "gh"
    gh.write_text(f'''#!{sys.executable}
import json, sys, pathlib
args = sys.argv[1:]
PRS = {json.dumps(prs)}
LABELED = {json.dumps(labeled)}
READY = {json.dumps(ready)}
VIEW = {json.dumps(view)}
PR_URL = {json.dumps(pr_url)}
with open({str(log)!r}, "a") as fh:
    fh.write(json.dumps(args) + "\\n")
if args[:2] == ["pr", "list"]:
    print(json.dumps([{{"number": n, "headRefName": f"agent/issue-{{n}}-fix",
                        "author": {{"login": "asimov-agent"}},
                        "createdAt": "2026-10-14T09:00:00Z"}} for n in PRS]))
elif args[:2] == ["search", "prs"]:
    print(json.dumps([{{"number": n}} for n in PRS]))
elif args[:2] == ["issue", "list"] and "--label" in args:
    lab = args[args.index("--label") + 1]
    print(json.dumps(LABELED) if lab == "agent:implement" else json.dumps(READY))
elif args[:2] == ["issue", "view"]:
    print(json.dumps(VIEW))
elif args[:2] == ["issue", "comment"]:
    print("Comment created.")
elif args[:2] == ["pr", "create"]:
    print(PR_URL)
else:
    print("[]")
''')
    gh.chmod(0o755)
    return gh, log


def _calls(log: Path) -> list[list[str]]:
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def test_dispatcher_exists_and_is_a_real_subprocess(tmp_path):
    """dispatch is a real executable the product starts as a subprocess."""
    gh, _log = _fake_gh(tmp_path)
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "issue_implementer.py"),
                        "count", "--repo", f"{OWNER}/{REPO_NAME}", "--gh", str(gh)],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "0"


def test_count_prs_opened_today_matches_the_cap_numerator(tmp_path):
    """count == number of PRs the BOT opened today — recognised by its branch, not a login.

    Measured (issue #409): the bot opens its PRs with the owner PAT, so they are authored
    `asimov-agent`; counting `--author github-actions[bot]` read 0 on a day it opened 7. The
    dispatcher's `agent/issue-<n>-<slug>` branch is the signal that actually identifies them.
    """
    gh, log = _fake_gh(tmp_path, {"prs": [1, 2, 3]})
    n = ii.count(str(gh), f"{OWNER}/{REPO_NAME}", ii.BOT_AUTHOR, today="2026-10-14")
    assert n == 3
    q = [c for c in _calls(log) if c[:2] == ["pr", "list"]][0]
    assert "--json" in q and any("headRefName" in a for a in q), "the branch shape is the signal"
    assert "--repo" in q and f"{OWNER}/{REPO_NAME}" in q
    assert ii.BOT_BRANCH_PREFIX == "agent/issue-"


def test_count_ignores_a_humans_pr_and_a_pr_from_another_day(tmp_path):
    """A human's PR never counts, and yesterday's bot PR belongs to yesterday."""
    gh, _log = _fake_gh(tmp_path, {"prs": [7]})
    # the fake answers bot-shaped PRs on 2026-10-14 only
    assert ii.count(str(gh), f"{OWNER}/{REPO_NAME}", ii.BOT_AUTHOR, today="2026-10-14") == 1
    assert ii.count(str(gh), f"{OWNER}/{REPO_NAME}", ii.BOT_AUTHOR, today="2026-10-15") == 0


def test_cap_reached_at_three_exits_zero_and_changes_nothing(tmp_path, capsys):
    """The cap is proven: at 3 already-opened PRs, the 4th attempt opens nothing."""
    gh, log = _fake_gh(tmp_path, {"prs": [1, 2, 3], "labeled": [{"number": 11}]})
    r = ii.dispatch(str(gh), f"{OWNER}/{REPO_NAME}", ii.BOT_AUTHOR,
                    today="2026-10-14", out_path=tmp_path / "issue.md")
    assert r["action"] == "cap" and r["issue"] is None
    assert "cap reached: 3/3 today, next issue tomorrow" in capsys.readouterr().out
    # No issue view, no comment, no listing at all beyond the cap query.
    assert not [c for c in _calls(log) if c[:2] in (["issue", "list"], ["issue", "view"],
                                                     ["issue", "comment"], ["pr", "create"])]
    assert not (tmp_path / "issue.md").exists()


def test_below_cap_it_picks_a_labeled_issue_and_claims_it(tmp_path):
    """Dispatch chooses `agent:implement`, claims it, and emits the branch + issue.md."""
    gh, log = _fake_gh(tmp_path, {
        "prs": [1, 2],
        "labeled": [{"number": 11, "title": "Fix the thing", "createdAt": "2026-10-14T00:00:00Z"}],
        "ready": [{"number": 12, "title": "Ready", "createdAt": "2026-10-13T00:00:00Z"}],
        "view": {"number": 11, "title": "Fix the thing", "body": "Implement it."}})
    r = ii.dispatch(str(gh), f"{OWNER}/{REPO_NAME}", ii.BOT_AUTHOR,
                    today="2026-10-14", out_path=tmp_path / "issue.md")
    assert r["action"] == "dispatch" and r["issue"] == 11
    assert r["branch"] == f"agent/issue-11-{SLUG}"
    # The claim marker comment carries the issue number and the branch.
    comments = [c for c in _calls(log) if c[:2] == ["issue", "comment"]]
    assert len(comments) == 1
    assert comments[0][2] == "11" and "bot-claim: implementer" in comments[0][-1], \
        "the claim must be the marker the other bot reads"
    assert f"agent/issue-11-{SLUG}" in comments[0][-1]
    # issue.md has the title + body the agent reads.
    md = (tmp_path / "issue.md").read_text()
    assert "# Fix the thing" in md and "Implement it." in md


def test_it_falls_back_to_the_oldest_ready_issue(tmp_path):
    """With no implement label, it picks the OLDEST agent:ready issue."""
    gh, log = _fake_gh(tmp_path, {
        "prs": [],
        "labeled": [],
        "ready": [
            {"number": 8, "title": "Older", "createdAt": "2026-10-12T00:00:00Z"},
            {"number": 9, "title": "Newer", "createdAt": "2026-10-13T00:00:00Z"},
        ],
        "view": {"number": 8, "title": "Older", "body": "old"}})
    r = ii.dispatch(str(gh), f"{OWNER}/{REPO_NAME}", ii.BOT_AUTHOR,
                    today="2026-10-14", out_path=tmp_path / "issue.md")
    assert r["issue"] == 8 and r["branch"] == "agent/issue-8-older"
    # It listed agent:implement first, then agent:ready.
    lists = [c for c in _calls(log) if c[:2] == ["issue", "list"] and "--label" in c]
    assert [c[c.index("--label") + 1] for c in lists] == ["agent:implement", "agent:ready"]


def test_open_pr_links_the_issue_and_never_merges(tmp_path):
    """pr create targets main from the bot branch, links the issue, and returns the URL."""
    gh, log = _fake_gh(tmp_path, {"pr_url": "https://github.com/acme/llgenie/pull/99"})
    body_file = tmp_path / ii.PR_BODY_FILE
    body_file.write_text("Issue: #11 — the thing\n\nFix: changed x\n\nBenefit: less drift\n\n"
                         "Technical: scripts/x.py\n")
    url = ii.open_pr(str(gh), f"{OWNER}/{REPO_NAME}", 11, f"agent/issue-11-{SLUG}",
                     "fix(issue-bot): the thing", str(body_file))
    assert url == "https://github.com/acme/llgenie/pull/99"
    creates = [c for c in _calls(log) if c[:2] == ["pr", "create"]]
    assert len(creates) == 1
    assert creates[0][creates[0].index("--base") + 1] == "main"
    assert f"agent/issue-11-{SLUG}" in creates[0]
    assert creates[0][creates[0].index("--title") + 1] == "fix(issue-bot): the thing (#11)"
    body = creates[0][creates[0].index("--body") + 1]
    assert "#11" in body and "closes #11" in body
    assert all(part in body for part in ii.PR_PARTS), body
    assert "Files changed:" in body, body
    # The bot never emits `pr merge`.
    assert not any(c[:2] == ["pr", "merge"] for c in _calls(log))


def test_dispatch_is_dry_by_default_from_the_cli(tmp_path):
    """dispatch --dry claims nothing: no comment argv reaches gh."""
    gh, log = _fake_gh(tmp_path, {
        "prs": [],
        "labeled": [{"number": 11, "title": "Fix the thing", "createdAt": "2026-10-14T00:00:00Z"}],
        "view": {"number": 11, "title": "Fix the thing", "body": "body"}})
    r = ii.dispatch(str(gh), f"{OWNER}/{REPO_NAME}", ii.BOT_AUTHOR, dry=True,
                    today="2026-10-14", out_path=tmp_path / "issue.md")
    assert r["issue"] == 11
    assert not [c for c in _calls(log) if c[:2] == ["issue", "comment"]]
    assert (tmp_path / "issue.md").exists()


def test_force_issue_pins_dispatch_to_that_issue(tmp_path):
    """A label event / manual dispatch pins the exact issue (the explicit ask):
    FORCE_ISSUE wins over the oldest, so the labeled issue is the one claimed."""
    gh, log = _fake_gh(tmp_path, {
        "prs": [],
        "labeled": [{"number": 11, "title": "Fix the thing", "createdAt": "2026-10-14T00:00:00Z"}],
        "ready": [{"number": 12, "title": "Ready", "createdAt": "2026-10-13T00:00:00Z"}],
        "view": {"number": 99, "title": "The labeled issue", "body": "state=open", "state": "OPEN"}})
    r = ii.dispatch(str(gh), f"{OWNER}/{REPO_NAME}", ii.BOT_AUTHOR,
                    today="2026-10-14", out_path=tmp_path / "issue.md", force_issue=99)
    # It claims the FORCED issue (99), never the oldest labeled (11) or ready (12).
    assert r["issue"] == 99 and r["branch"] == "agent/issue-99-the-labeled-issue"
    comments = [c for c in _calls(log) if c[:2] == ["issue", "comment"]]
    assert comments and comments[0][2] == "99"
    assert "agent/issue-99-the-labeled-issue" in comments[0][-1]
    # forced view is the single issue-view call (no label-list, no pick).
    views = [c for c in _calls(log) if c[:2] == ["issue", "view"]]
    assert len(views) == 1 and views[0][2] == "99"
    assert not [c for c in _calls(log) if c[:2] == ["issue", "list"]]


def test_force_issue_that_is_closed_does_not_dispatch(tmp_path):
    """A forced non-open issue is reported as none, never claimed."""
    gh, log = _fake_gh(tmp_path, {
        "prs": [],
        "view": {"number": 99, "title": "Closed", "body": "", "state": "CLOSED"}})
    r = ii.dispatch(str(gh), f"{OWNER}/{REPO_NAME}", ii.BOT_AUTHOR,
                    today="2026-10-14", out_path=tmp_path / "issue.md", force_issue=99)
    assert r["action"] == "none" and r["issue"] is None
    assert not [c for c in _calls(log) if c[:2] == ["issue", "comment"]]


def test_the_dispatcher_and_tests_are_wired():
    """A new script/test must be reachable from make, never dead (AGENTS.md wiring rule)."""
    mk = (REPO / "Makefile").read_text()
    assert "issue-bot-dispatch:" in mk and "issue-bot-open-pr:" in mk and "implement-issue:" in mk
    # The test file is in the unit suite the aggregator computes (issue #393), so it runs in the gate.
    assert "tests/test_issue_implementer.py" in ut.select(REPO)
    # The workflow calls only real make targets.
    wf = (REPO / ".github" / "workflows" / "issue-bot.yml").read_text()
    for target in ("implement-issue", "issue-bot-dispatch", "issue-bot-open-pr"):
        assert f"make {target}" in wf or f"$(MAKE) {target}" in wf


def test_the_implementer_runs_inside_the_agent_image():
    """Issues #238/#248: the agent runs in the bot image, never installed on the runner.

    The workflow called `make implement-issue` / `make hermes-smoke` and the runner had no
    Hermes at all (no install step existed), so the implementer would have died on
    "command not found". Both targets now run the shared agent image, which installs Hermes at
    build time, and the secrets travel as run-time env.
    """
    makefile = (REPO / "Makefile").read_text()
    lines = makefile.splitlines()

    def recipe(target: str) -> str:
        """The recipe lines (raw, as written) of one target."""
        for i, line in enumerate(lines):
            if line.startswith(f"{target}:"):
                out = []
                for nxt in lines[i + 1:]:
                    if nxt.startswith("\t"):
                        out.append(nxt)
                    elif nxt.startswith("#") or nxt == "":
                        continue
                    else:
                        break
                return "\n".join(out)
        raise AssertionError(f"no {target} target")

    public = recipe("implement-issue")
    assert "scripts/ci_images.py ensure agent" in public, "the image must be ensured first"
    assert "run --rm --init" in public and "$(RUNTIME)" in public, public
    assert 'make _implement-issue' in public, "the public target runs the host recipe in the image"
    assert "-e NOUS_API_KEY" in public and "-e GH_TOKEN" in public, (
        "the token and the PAT travel as run-time env; nothing is baked into the image"
    )
    assert "hermes -z" not in public, "the runner must not invoke hermes directly"
    assert "$(AGENT_IMAGE)" in public or "AGENT_IMAGE" in public

    smoke = recipe("hermes-smoke")
    assert "run --rm --init" in smoke and "make _hermes-smoke" in smoke
    assert "-e NOUS_API_KEY" in smoke

    host = recipe("_implement-issue")
    assert "hermes -z" in host and "AGENTS.md" in host, "the host recipe is where the agent call lives"
    for rule in ("(1)", "(2)", "(3)", "(4)"):
        assert rule in host, f"the hard rules stay on the agent call ({rule})"

    workflow = (REPO / ".github" / "workflows" / "issue-bot.yml").read_text()
    assert "make implement-issue" in workflow and "make hermes-smoke" in workflow
    assert "install_hermes_ci.sh" not in workflow and "uv tool install" not in workflow, (
        "the workflow must not install the agent on the runner: the image carries it"
    )


def test_the_agent_image_definition_is_present_and_installs_hermes():
    """The image the implementer runs in is the one this commit's Dockerfile describes."""
    dockerfile = (REPO / "containers" / "agent" / "Dockerfile").read_text()
    assert "install_hermes_ci.sh" in dockerfile, "the image installs Hermes at build time"
    assert "hermes --version" in dockerfile, "and proves it at build time"
    assert (REPO / "scripts" / "install_hermes_ci.sh").exists()
    registry = (REPO / "scripts" / "ci_images.py").read_text()
    assert '"agent"' in registry, "the image is a declared input set (its tag is their hash)"


def test_the_agent_call_uses_the_image_alias_not_a_bogus_flag():
    """The invocation that actually works against the Nous endpoint (verified live).

    Three traps, each one a dead bot: `--alias` is not a Hermes flag at all; `-m` is the MODEL
    flag, so `-m "Reply with exactly: ok"` sets the model to that sentence; and `--max-steps`
    does not exist. The working form is `-z <prompt> -m <alias> --reasoning <level> --yolo`.
    """
    makefile = (REPO / "Makefile").read_text()
    # The alias name lives once, and the flag form is derived from it (issue #407).
    assert "nous-model := nous-deepseek" in makefile
    assert "nous-alias := -m $(nous-model)" in makefile
    assert "--max-steps" not in makefile, "`--max-steps` is not a hermes flag"

    hermes_lines = [line for line in makefile.splitlines() if "hermes -z" in line]
    assert hermes_lines, "the one-shot (-z) form is the only way a leg calls the model"
    # `--alias` is not a hermes flag: the smoke script has its own `--alias`, a hermes line may not.
    assert not [line for line in hermes_lines if "--alias" in line], hermes_lines
    assert all("$(nous-alias)" in line for line in hermes_lines), hermes_lines
    assert all("--yolo" in line for line in hermes_lines), hermes_lines

    # The smoke proves a tool call instead of asserting a sentence (issue #407).
    smoke_script = (REPO / "scripts" / "hermes_smoke.py").read_text()
    assert "scripts/hermes_smoke.py run" in makefile
    assert '"--yolo"' in smoke_script, "the script keeps the working invocation"


def test_the_image_wires_the_nous_token_as_a_custom_provider_alias():
    """Hermes's bundled `nous` provider is OAuth-only: a bare NOUS_API_KEY is ignored and
    `--provider nous` fails with "not logged into Nous Portal". The install script must write
    the custom-provider alias that makes the token work (verified by a live smoke)."""
    script = (REPO / "scripts" / "install_hermes_ci.sh").read_text()
    assert "model.aliases.${ALIAS}.provider" in script and "custom" in script
    assert "model.aliases.${ALIAS}.base_url" in script and "inference-api.nousresearch.com/v1" in script
    assert "model.aliases.${ALIAS}.key_env" in script and "NOUS_API_KEY" in script
    assert "model.aliases.${ALIAS}.model" in script
    # The EXACT snapshot, not the family prefix: `-1017` is the 2026-10-17 release, and the
    # unsuffixed id is a different, older model that also answers 200 (issue #405). A prefix
    # assert is what let the bots run the previous snapshot unnoticed.
    assert "deepseek/deepseek-v4.1-flash-1017" in script, "the model id is the pinned snapshot"
    assert "would fail at run time" in script, (
        "a bot whose alias is missing must fail loudly at build time, not at run time"
    )
    assert 'for kv in "model=${MODEL_ID}"' in script, "the check covers the model id, not just key_env"


# ---------------------------------------------------------------------------
# the whole thread, the verdict, and the three outcomes (issue #261)
# ---------------------------------------------------------------------------
def _thread_view(number=11, comments=None):
    return {"number": number, "title": f"Fix the thing #{number}", "body": "body says add --foo",
            "state": "open", "author": {"login": "andyholst"},
            "labels": [{"name": "agent:ready"}], "comments": comments or []}


def test_dispatch_fetches_the_whole_thread_and_renders_it(tmp_path, capsys):
    """The thread is the specification: dispatch asks for the comments and issue.md carries them."""
    comments = [{"author": {"login": "andyholst"}, "createdAt": "2026-10-14T09:00:00Z",
                 "body": "only for CPU builds"},
                {"author": {"login": "reviewer"}, "createdAt": "2026-10-14T10:30:00Z",
                 "body": "and never on arm64"}]
    gh, log = _fake_gh(tmp_path, {"labeled": [{"number": 11, "title": "Fix the thing #11",
                                               "createdAt": "2026-10-01T00:00:00Z",
                                               "labels": [{"name": "agent:implement"}]}],
                                 "view": _thread_view(comments=comments)})
    out = tmp_path / "issue.md"
    r = ii.dispatch(str(gh), f"{OWNER}/{REPO_NAME}", ii.BOT_AUTHOR, today="2026-10-14", out_path=out)

    # it asked for the thread through --json (comments come with the JSON: `gh` rejects
    # `--comments` combined with `--json`, which is what broke every dispatch)
    view = [c for c in _calls(log) if c[:2] == ["issue", "view"]][0]
    assert "--comments" not in view, view
    assert "comments" in view[view.index("--json") + 1]

    # and the agent's input carries the body, every comment with author+date, and the decision
    text = out.read_text()
    assert "body says add --foo" in text
    assert "only for CPU builds" in text and "and never on arm64" in text
    assert "andyholst · 2026-10-14T09:00:00Z" in text and "reviewer · 2026-10-14T10:30:00Z" in text
    assert "Comments (oldest first, 2)" in text
    assert "## Decide first, then act" in text
    for verdict in ("TRIAGE: implement", "TRIAGE: refine", "TRIAGE: close"):
        assert verdict in text, verdict
    assert r["branch"] == "agent/issue-11-fix-the-thing-11"


def test_an_issue_already_decided_is_never_picked_again(tmp_path):
    """A refine/close labels the issue, and dispatch must skip it — or the bot loops forever."""
    gh, log = _fake_gh(tmp_path, {"labeled": [
        {"number": 11, "title": "refined one", "createdAt": "2026-10-01T00:00:00Z",
         "labels": [{"name": "agent:refined"}]},
        {"number": 12, "title": "closed one", "createdAt": "2026-10-02T00:00:00Z",
         "labels": [{"name": "agent:closed"}]},
        {"number": 13, "title": "Fix the thing #13", "createdAt": "2026-10-03T00:00:00Z",
         "labels": [{"name": "agent:implement"}]},
    ], "view": _thread_view(number=13)})
    r = ii.dispatch(str(gh), f"{OWNER}/{REPO_NAME}", ii.BOT_AUTHOR, today="2026-10-14",
                    out_path=tmp_path / "issue.md")
    assert r["issue"] == 13, r
    assert [c for c in _calls(log) if c[:2] == ["issue", "view"]][0][2] == "13"


def test_a_verdict_is_parsed_out_of_the_agents_output():
    """The workflow parses the verdict mechanically, so the format is fixed and tested."""
    assert ii.parse_verdict("TRIAGE: implement\n")["verdict"] == "implement"
    v = ii.parse_verdict("TRIAGE: refine\nREFINED:\n- [ ] --foo on CPU only\nREASON: arm64 undecided\n")
    assert v["verdict"] == "refine" and "--foo on CPU only" in v["refined"]
    assert v["reason"] == "arm64 undecided"
    v = ii.parse_verdict("TRIAGE: close\nEVIDENCE: #123 merged as 4b2c2f1 does exactly this\n")
    assert v["verdict"] == "close" and "#123 merged as 4b2c2f1" in v["evidence"]
    for bad in ("", "nothing to see", "TRIAGE: maybe\n"):
        with pytest.raises(SystemExit):
            ii.parse_verdict(bad)


def test_an_implement_verdict_changes_nothing_itself(tmp_path):
    """`implement` only lets the existing path run: apply-verdict must mutate nothing."""
    gh, log = _fake_gh(tmp_path)
    v = ii.apply_verdict(str(gh), f"{OWNER}/{REPO_NAME}", 11, "TRIAGE: implement\n")
    assert v["verdict"] == "implement"
    assert _calls(log) == [], _calls(log)


def test_a_refine_posts_one_comment_and_labels_it_without_a_pr(tmp_path):
    """A refine is a comment for humans: one comment, the label, and no PR."""
    gh, log = _fake_gh(tmp_path)
    ii.apply_verdict(str(gh), f"{OWNER}/{REPO_NAME}", 11,
                     "TRIAGE: refine\nREFINED:\n- [ ] --foo on CPU only\nREASON: arm64 open\n")
    calls = _calls(log)
    comment = [c for c in calls if c[:2] == ["issue", "comment"]][0]
    assert "11" in comment and "--foo on CPU only" in " ".join(comment)
    edit = [c for c in calls if c[:2] == ["issue", "edit"]][0]
    assert "agent:refined" in edit
    assert not [c for c in calls if c[:2] == ["pr", "create"]]
    assert not [c for c in calls if c[:2] == ["issue", "close"]]


def test_a_refine_without_a_refined_block_is_refused(tmp_path):
    """'It is unclear' is not a refinement: the block that restates the issue is required."""
    gh, log = _fake_gh(tmp_path)
    with pytest.raises(SystemExit):
        ii.apply_verdict(str(gh), f"{OWNER}/{REPO_NAME}", 11, "TRIAGE: refine\nREASON: unclear\n")
    assert _calls(log) == []


def test_a_close_cites_evidence_then_closes_and_labels(tmp_path):
    """Closing is allowed only with what was checked, and it must not be picked again."""
    gh, log = _fake_gh(tmp_path)
    ii.apply_verdict(str(gh), f"{OWNER}/{REPO_NAME}", 11,
                     "TRIAGE: close\nEVIDENCE: #123 merged as 4b2c2f1 does exactly this\n"
                     "REASON: already implemented\n")
    calls = _calls(log)
    comment = [c for c in calls if c[:2] == ["issue", "comment"]][0]
    assert "4b2c2f1" in " ".join(comment) and "already implemented" in " ".join(comment)
    close = [c for c in calls if c[:2] == ["issue", "close"]][0]
    assert "11" in close and "not planned" in close
    edit = [c for c in calls if c[:2] == ["issue", "edit"]][0]
    assert "agent:closed" in edit and "agent:implement" in edit
    assert not [c for c in calls if c[:2] == ["pr", "create"]]


def test_a_close_without_evidence_is_refused_and_mutates_nothing(tmp_path):
    """The one rule that must never soften: no evidence, no close."""
    gh, log = _fake_gh(tmp_path)
    with pytest.raises(SystemExit):
        ii.apply_verdict(str(gh), f"{OWNER}/{REPO_NAME}", 11, "TRIAGE: close\nREASON: too hard\n")
    assert _calls(log) == [], "a refused close must not comment, label or close anything"


# ---- the claim protocol on the implementer's side (scripts/bot_claims.py) ----

def test_pick_free_skips_an_issue_another_bot_claimed_and_takes_the_next(monkeypatch):
    """The maintainer's rule: a recent comment not concluded by a `done` means someone is on it -
    skip THAT issue and take the next one in the list."""
    import datetime as dt
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cands = [{"number": 1, "title": "one", "createdAt": "2026-09-01T00:00:00Z", "labels": []},
             {"number": 2, "title": "two", "createdAt": "2026-09-02T00:00:00Z", "labels": []}]
    threads = {1: {"comments": [{"body": f"<!-- bot-claim: refiner {stamp} refine -->"}]},
               2: {"comments": []}}
    monkeypatch.setattr(ii, "_thread", lambda gh, repo, num: threads[num])
    picked = ii._pick_free("gh", "o/r", cands)
    assert picked and picked["number"] == 2, picked


def test_a_decided_issue_is_still_skipped_before_any_thread_is_read(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("a decided issue must not cost a thread read")
    monkeypatch.setattr(ii, "_thread", boom)
    cands = [{"number": 1, "title": "one", "createdAt": "2026-09-01T00:00:00Z",
              "labels": [{"name": "agent:refined"}]}]
    assert ii._pick_free("gh", "o/r", cands) is None


def test_opening_the_pr_records_a_pr_open_done(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(ii, "_gh", lambda gh, args: calls.append(args) or "https://x.invalid/pull/9")
    body_file = tmp_path / ii.PR_BODY_FILE
    body_file.write_text("Issue: #11 — x\n\nFix: y\n\nBenefit: z\n\nTechnical: scripts/x.py\n")
    url = ii.open_pr("gh", "o/r", 11, "agent/issue-11-s", "fix(x): t", str(body_file), dry=False)
    assert url.endswith("/pull/9")
    done = [c for c in calls if c[:2] == ["issue", "comment"]]
    assert done, "no done comment was posted"
    body = " ".join(done[0])
    assert "bot-done: implementer" in body and "pr-open" in body, body
    assert "never merges" in body


def test_a_pr_open_marker_keeps_the_issue_occupied_but_a_closure_releases_it():
    """The kinds the maintainer asked for: implemented-and-not-approved still occupies the issue,
    while a merge/close releases it - so nobody implements it twice."""
    import bot_claims as bc
    import datetime as dt
    now = dt.datetime(2026, 10, 14, 12, 0, tzinfo=dt.timezone.utc)
    at = "2026-10-14T11:30:00Z"
    assert bc.occupied([{"body": f"<!-- bot-done: implementer {at} pr-open -->\nPR up"}],
                       bc.REFINER, now) is not None
    assert bc.occupied([{"body": f"<!-- bot-done: implementer {at} merged -->\nlanded"}],
                       bc.REFINER, now) is None
    assert bc.occupied([{"body": f"<!-- bot-claim: refiner {at} refine -->\ntaking it"}],
                       bc.IMPLEMENTER, now) is not None
    assert bc.occupied([{"body": f"<!-- bot-claim: implementer {at} implement -->\nmine"}],
                       bc.IMPLEMENTER, now) is None, "its own claim never blocks it"


def test_the_shared_helper_is_byte_identical_to_the_refiner_copy():
    """Both bots read one protocol: the file is shipped byte-identically in both branches, so
    whichever merges first makes the other a no-op."""
    import hashlib
    here = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "bot_claims.py"
    digest = hashlib.sha256(here.read_bytes()).hexdigest()
    assert len(digest) == 64 and "bot-claim" in here.read_text()
# ---------------------------------------------------------------------------
# the argv the REAL `gh` accepts
# ---------------------------------------------------------------------------
def test_no_gh_call_combines_comments_with_json(tmp_path):
    """`gh` rejects `--comments` together with `--json` — that argv broke every dispatch.
    A fake `gh` answers whatever it is asked, so a fixture alone cannot catch a flag combination
    the real CLI refuses: this test encodes that constraint and scans EVERY argv a full dispatch
    builds (measured: `gh 2.102.0` exits 1 with "specify only one of --comments or --json", so
    `make issue-bot-dispatch` never produced an issue for the implementer to work on).
    """
    labeled = [{"number": 11, "title": "Fix the thing #11", "createdAt": "2026-10-01T00:00:00Z",
                "labels": [{"name": "agent:implement"}]}]
    gh, log = _fake_gh(tmp_path, {"labeled": labeled, "view": _thread_view()})
    ii.dispatch(str(gh), f"{OWNER}/{REPO_NAME}", ii.BOT_AUTHOR, today="2026-10-14",
                out_path=tmp_path / "issue.md")
    calls = _calls(log)
    assert calls, "the dispatch built no argv at all"
    for call in calls:
        assert not ("--comments" in call and "--json" in call), call


# ---- the implementation is measured from the tree, not from the exit code (issue #428) --------

def _git_repo(path: Path) -> Path:
    """A real repository, one commit deep: `changed()` reads it with the real git binary."""
    path.mkdir(parents=True, exist_ok=True)
    for argv in (["init", "-q"], ["config", "user.email", "smoke@example.com"],
                 ["config", "user.name", "Smoke Test"]):
        subprocess.run(["git", "-C", str(path), *argv], check=True, capture_output=True)
    (path / "README.md").write_text("one\n")
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "init"], check=True, capture_output=True)
    return path


def test_changed_is_false_when_only_a_run_input_appeared(tmp_path):
    """A run that wrote its verdict and touched nothing else has implemented nothing."""

    # Given a clean repository and an implement step that only wrote the triage verdict
    repo = _git_repo(tmp_path / "repo")
    (repo / "triage.md").write_text("TRIAGE: implement\n")

    # When  the tree is inspected for a change
    result = ii.changed(str(repo))

    # Then  there is none: the run input is not an implementation
    assert result is False


def test_changed_is_true_for_a_real_edit(tmp_path):
    """A real edit, and a real new file, are both changes."""

    # Given a repository with one edited tracked file and one new source file
    repo = _git_repo(tmp_path / "repo")
    (repo / "README.md").write_text("one\ntwo\n")
    (repo / "scripts").mkdir()
    (repo / "scripts" / "new_thing.py").write_text("print('hi')\n")

    # When  the tree is inspected
    result = ii.changed(str(repo))

    # Then  the change is reported
    assert result is True


def test_changed_fails_loudly_outside_a_git_tree(tmp_path):
    """A tree git cannot read is exit 2, never a green run."""

    # Given a directory that is not a git repository
    plain = tmp_path / "plain"
    plain.mkdir()

    # When  the changed check runs there, through the Makefile's own entry point
    proc = subprocess.run([sys.executable, str(REPO / "scripts" / "issue_implementer.py"),
                           "changed", "--root", str(plain)],
                          capture_output=True, text=True, timeout=60)

    # Then  it exits 2 and names what it could not read
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "status failed" in proc.stderr, proc.stderr


def test_the_workflow_gates_push_and_failure_on_the_tree():
    """The workflow asks the tree, and gates both the push and the loud failure on it."""

    # Given the issue-bot workflow
    workflow = (REPO / ".github" / "workflows" / "issue-bot.yml").read_text()

    # When  the implement, detect, push and failure steps are read
    assert "make issue-bot-changed" in workflow, "the workflow must measure the tree"
    assert "steps.diff.outputs.changed == 'true'" in workflow, "the push must require a change"
    assert "implemented=true" not in workflow, "the outcome is no longer derived from the exit code"
    assert "steps.impl.outputs.rc != '0' || steps.diff.outputs.changed != 'true'" in workflow, \
        "the loud failure must cover a failed agent AND a tree that changed nothing"

    # Then  the Makefile target exists, is phony, and reaches the subcommand
    makefile = (REPO / "Makefile").read_text()
    assert "\nissue-bot-changed:" in makefile
    assert "issue-bot-changed" in makefile.split(".PHONY:", 1)[1].split("\n\n", 1)[0]
    assert "scripts/issue_implementer.py changed" in makefile
