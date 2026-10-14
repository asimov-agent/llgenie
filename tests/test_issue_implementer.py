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
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import issue_implementer as ii  # noqa: E402

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
if args[:2] == ["search", "prs"]:
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
    """count == number of PRs the bot opened in the current UTC day (from GitHub)."""
    gh, log = _fake_gh(tmp_path, {"prs": [1, 2, 3]})
    n = ii.count(str(gh), f"{OWNER}/{REPO_NAME}", ii.BOT_AUTHOR, today="2026-10-14")
    assert n == 3
    q = [c for c in _calls(log) if c[:2] == ["search", "prs"]][0]
    assert "--author" in q and ii.BOT_AUTHOR in q
    assert "--created" in q and ">=2026-10-14 00:00Z" in q
    assert "--repo" in q and f"{OWNER}/{REPO_NAME}" in q


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
    assert comments[0][2] == "11" and "issue-implementer: claiming" in comments[0][-1]
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
    url = ii.open_pr(str(gh), f"{OWNER}/{REPO_NAME}", 11, f"agent/issue-11-{SLUG}",
                     "Fix the thing", "Implements X", "")
    assert url == "https://github.com/acme/llgenie/pull/99"
    creates = [c for c in _calls(log) if c[:2] == ["pr", "create"]]
    assert len(creates) == 1
    assert creates[0][creates[0].index("--base") + 1] == "main"
    assert f"agent/issue-11-{SLUG}" in creates[0]
    assert creates[0][creates[0].index("--title") + 1] == "Fix the thing (implements #11)"
    body = creates[0][creates[0].index("--body") + 1]
    assert "#11" in body and "closes #11" in body
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
        "view": {"number": 99, "title": "The labeled issue", "body": "state=open", "state": "open"}})
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
        "view": {"number": 99, "title": "Closed", "body": "", "state": "closed"}})
    r = ii.dispatch(str(gh), f"{OWNER}/{REPO_NAME}", ii.BOT_AUTHOR,
                    today="2026-10-14", out_path=tmp_path / "issue.md", force_issue=99)
    assert r["action"] == "none" and r["issue"] is None
    assert not [c for c in _calls(log) if c[:2] == ["issue", "comment"]]


def test_the_dispatcher_and_tests_are_wired():
    """A new script/test must be reachable from make, never dead (AGENTS.md wiring rule)."""
    mk = (REPO / "Makefile").read_text()
    assert "issue-bot-dispatch:" in mk and "issue-bot-open-pr:" in mk and "implement-issue:" in mk
    # The test file is named by make test-unit so it actually runs in the gate.
    unit = mk.split("\ntest-unit:", 1)[1].split("\n\n", 1)[0]
    assert "tests/test_issue_implementer.py" in unit
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
    assert "nous-alias := -m nous-deepseek" in makefile
    assert "--alias nous-deepseek" not in makefile, "`--alias` is not a hermes flag"
    assert "--max-steps" not in makefile, "`--max-steps` is not a hermes flag"
    smoke = [l for l in makefile.splitlines() if l.strip().startswith("hermes -z")]
    assert smoke, "the smoke must be a one-shot (-z), not an interactive start"
    assert any('hermes -z "Reply with exactly: ok"' in l for l in smoke), smoke
    assert any("--yolo" in l and "$(nous-alias)" in l for l in smoke), smoke


def test_the_image_wires_the_nous_token_as_a_custom_provider_alias():
    """Hermes's bundled `nous` provider is OAuth-only: a bare NOUS_API_KEY is ignored and
    `--provider nous` fails with "not logged into Nous Portal". The install script must write
    the custom-provider alias that makes the token work (verified by a live smoke)."""
    script = (REPO / "scripts" / "install_hermes_ci.sh").read_text()
    assert "model.aliases.${ALIAS}.provider" in script and "custom" in script
    assert "model.aliases.${ALIAS}.base_url" in script and "inference-api.nousresearch.com/v1" in script
    assert "model.aliases.${ALIAS}.key_env" in script and "NOUS_API_KEY" in script
    assert "model.aliases.${ALIAS}.model" in script
    assert "deepseek/deepseek-v4.1-flash" in script, "the model id is provider-prefixed"
    assert "the alias ${ALIAS} was not configured" in script, (
        "a bot whose alias is missing must fail loudly at build time, not at run time"
    )
