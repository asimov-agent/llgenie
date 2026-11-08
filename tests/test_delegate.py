"""Hermetic tests for agents/llgenie-planner/scripts/delegate.sh (issue #2159).

delegate.sh performs one dispatch mechanically and proves it landed: it validates
the brief, refuses a second vehicle for the same lane+issue, creates the task,
dispatches, and CONFIRMS by reading the board back. Its four required gates (from
the #2159 ACs) are:

- rejects a brief lacking the AGENTS: stamp / the $HOME rule / a branch / the
  BOT <lane> · … report line (exit 1, naming what is missing);
- FATAL on a missing brief file (exit 1);
- refuses a duplicate vehicle for the same lane+issue (exit 0, ALREADY DELEGATED);
- distinguishes running / ready (queued on capacity) / BLOCKED on confirmation.

These tests run the REAL script against a REAL fake `hermes` binary (the repo's
pattern: no mocks of the product, only the external CLI is a stand-in). The fake
drives `kanban list --json / create / dispatch` from a scripted board JSON file.
"""

import json
import os
import subprocess
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "agents"
    / "llgenie-planner"
    / "scripts"
    / "delegate.sh"
)

GOOD_BRIEF = """# impl #1234

AGENTS: 7ef346c8 91766b 1363l
Branch fix/1234 off origin/main@7ef346c8
BOT llgenie-issse-implementer · #1234 · branch fix/x · since 06:00Z · next fix
$HOME never /home/asimov (systemd carve-out stays absolute).
Scope: the failing check; done-means: PR green.
"""


def _make_fake_hermes(tmp_path, board_json, spawn=0, create_rc=0, fail_list=False,
                      created_status="ready"):
    """Write an executable fake `hermes` honouring kanban list/create/dispatch.

    board_json is the literal JSON list of tasks. create appends a made-up task
    (id t_created1, status `created_status`) to the board so a follow-up list and
    the confirm read it back exactly as created. When create_rc != 0 the fake
    create exits with that code and writes no task id. fail_list makes the list
    command exit non-zero (a board read failure).
    """
    board_path = tmp_path / "board.json"
    board_path.write_text(json.dumps(board_json))  # bare task array, like kanban list --json
    fake = tmp_path / "hermes"
    template = """#!/usr/bin/env bash
BOARD="@BOARD@"
case "$1" in
  kanban)
    cmd="$2"
    case "$cmd" in
      list)
        [ "@FAIL_LIST@" = "1" ] && { echo "board read failed" >&2; exit 1; }
        cat "$BOARD"
        ;;
      create)
        [ "@CREATE_RC@" != "0" ] && { echo "create rejected" >&2; exit "@CREATE_RC@"; }
        python3 -c "import json,sys;d=json.load(open(sys.argv[1]));d.append({'id':'t_created1','assignee':'llgenie-issse-implementer','status':'@CSTATUS@','title':'llgenie-issse-implementer #1234: T'});open(sys.argv[1],'w').write(json.dumps(d))" "$BOARD"
        echo "created task t_created1"
        ;;
      dispatch)
        echo "Spawned: @SPAWN@"
        ;;
      edit)
        echo "edited"; exit 0
        ;;
      *) exit 0;;
    esac
    ;;
  *) exit 0;;
esac
"""
    template = (
        template
        .replace("@BOARD@", str(board_path))
        .replace("@FAIL_LIST@", "1" if fail_list else "0")
        .replace("@CREATE_RC@", str(create_rc))
        .replace("@SPAWN@", str(spawn))
        .replace("@CSTATUS@", created_status)
    )
    fake.write_text(template)
    fake.chmod(0o755)
    return board_path, fake


def _run(argv, hermes):
    env = {**os.environ, "HERMES_BIN": str(hermes)}
    return subprocess.run(["bash", str(SCRIPT)] + argv, capture_output=True,
                          text=True, env=env, timeout=60)


def _write_brief(tmp_path, text):
    p = tmp_path / "brief.md"
    p.write_text(text)
    return p


def test_rejects_incomplete_brief(tmp_path):
    board, hermes = _make_fake_hermes(tmp_path, [])
    brief = _write_brief(tmp_path, "# impl #1\nno stamp no branch")
    r = _run(["--lane", "x", "--issue", "1", "--brief", str(brief)], hermes)
    assert r.returncode == 1, r.stdout
    assert "brief is incomplete" in r.stdout


def test_missing_brief_fatal(tmp_path):
    board, hermes = _make_fake_hermes(tmp_path, [])
    r = _run(["--lane", "x", "--issue", "1", "--brief", str(tmp_path / "nope.md")], hermes)
    assert r.returncode == 1
    assert "FATAL: brief not found" in r.stdout


def test_good_brief_dry_run_creates_nothing(tmp_path):
    board, hermes = _make_fake_hermes(tmp_path, [])
    brief = _write_brief(tmp_path, GOOD_BRIEF)
    r = _run(["--lane", "llgenie-issse-implementer", "--issue", "1234",
              "--brief", str(brief), "--dry-run"], hermes)
    assert r.returncode == 0, r.stdout
    assert "DRY RUN" in r.stdout
    # nothing was added to the board (bare task array, like kanban list --json)
    assert json.loads(board.read_text()) == []


def test_duplicate_vehicle_refused(tmp_path):
    board, hermes = _make_fake_hermes(
        tmp_path, [{"id": "t_exist", "assignee": "llgenie-x", "status": "ready",
                    "title": "llgenie-x #9: already there"}])
    brief = _write_brief(tmp_path, GOOD_BRIEF)
    r = _run(["--lane", "llgenie-x", "--issue", "9", "--brief", str(brief)], hermes)
    assert r.returncode == 0, r.stdout
    assert "ALREADY DELEGATED: t_exist" in r.stdout


def test_confirm_ready_queued_on_capacity(tmp_path):
    # create succeeds, dispatch reports Spawned: 0, board reads back status ready
    board, hermes = _make_fake_hermes(tmp_path, [], spawn=0)
    brief = _write_brief(tmp_path, GOOD_BRIEF)
    r = _run(["--lane", "llgenie-issse-implementer", "--issue", "1234",
              "--brief", str(brief), "--no-message"], hermes)
    assert r.returncode == 0, r.stdout
    assert "ready (queued on capacity" in r.stdout


def test_confirm_blocked(tmp_path):
    # create succeeds but the confirm reads the created task back as BLOCKED ->
    # the script exits 2 and says BLOCKED.
    board, hermes = _make_fake_hermes(tmp_path, [], spawn=0, created_status="blocked")
    brief = _write_brief(tmp_path, GOOD_BRIEF)
    r = _run(["--lane", "llgenie-issse-implementer", "--issue", "1234",
              "--brief", str(brief), "--no-message"], hermes)
    assert r.returncode == 2, r.stdout
    assert "BLOCKED" in r.stdout


def test_message_channel_required_by_default(tmp_path):
    # without --no-message, after a successful create the script must remind the
    # planner to send message_agent (task + message = ONE assignment).
    board, hermes = _make_fake_hermes(tmp_path, [], spawn=1)
    brief = _write_brief(tmp_path, GOOD_BRIEF)
    r = _run(["--lane", "llgenie-issse-implementer", "--issue", "1234",
              "--brief", str(brief)], hermes)
    assert r.returncode == 0, r.stdout
    assert "message_agent" in r.stdout
