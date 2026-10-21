#!/usr/bin/env python3
"""The smoke proves a tool call, not a sentence (issue #407).

`make hermes-smoke` used to ask for the sentence `ok` and assert it came back, so a model whose tool
calling is broken passed the smoke and then failed the 120-180 minute job it guards. These cases lock
the replacement at both ends:

* the prompt — it names the terminal tool and one exact command, and it does NOT carry the value the
  smoke asserts (the nonce lives in a file, so only a real tool call can produce it);
* the verdict — a real `sessions`/`messages` store is read and judged: a text-only transcript fails, a
  `terminal` result carrying the nonce passes, another tool does not count, a tool counter is not
  evidence, and a missing transcript is a named failure instead of a pass;
* the wiring — `_hermes-smoke` runs the script, `issue-bot.yml` still runs `make hermes-smoke`, and the
  old text-echo prompt is gone from every file that can carry a prompt.

NO-SKIP POLICY: every case runs the real loader, the real sqlite store and the real recipe text.
"""
from __future__ import annotations

import re
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "hermes_smoke.py"
MAKEFILE = REPO / "Makefile"
WORKFLOW = REPO / ".github" / "workflows" / "issue-bot.yml"
sys.path.insert(0, str(REPO / "scripts"))

import hermes_smoke as smoke  # noqa: E402  (the module under test, loaded for real)

#: The value the old recipe asked the model to echo. Built from pieces so THIS file does not carry it
#: literally — the tree scan below must be able to fail on a real prompt, not on its own assertion.
OLD_PROMPT = "Reply with " + "exactly: ok"

NONCE = "0f1e2d3c4b5a69788796a5b4c3d2e1f0"


def _store(path: Path, rows: list[tuple[str, str | None, str | None]],
           session: str = "sess-1", tool_call_count: int = 0) -> Path:
    """A real sqlite store with the two tables the smoke reads, holding `rows` as a transcript."""
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE sessions (id TEXT PRIMARY KEY, started_at REAL, tool_call_count INTEGER);"
        "CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, tool_name TEXT,"
        " content TEXT);"
    )
    conn.execute("INSERT INTO sessions VALUES (?, ?, ?)", (session, 1000.0, tool_call_count))
    for i, (role, tool_name, content) in enumerate(rows, start=1):
        conn.execute("INSERT INTO messages VALUES (?, ?, ?, ?, ?)", (i, session, role, tool_name, content))
    conn.commit()
    conn.close()
    return path


def _evaluate(path: Path, expected: str) -> list[str]:
    conn = smoke.connect(path)
    try:
        return smoke.evaluate(conn, "sess-1", expected)
    finally:
        conn.close()


def test_a_text_only_transcript_is_a_failure(tmp_path):
    """A model that answers in text, with no tool call, fails the smoke."""

    # Given a transcript with an answer that echoes the marker and no tool call at all
    expected = smoke.expected_value(NONCE)
    db = _store(tmp_path / "state.db",
                [("user", None, "run the command"), ("assistant", None, expected)])

    # When  the smoke evaluates it
    problems = _evaluate(db, expected)

    # Then  it fails, naming the missing tool call
    assert problems, "a text-only answer must not pass the smoke"
    assert any("without calling a tool" in p for p in problems), problems


def test_a_terminal_call_carrying_the_nonce_passes(tmp_path):
    """The terminal tool ran the command, so the run is a real tool-calling proof."""

    # Given a terminal tool result carrying the nonce, and a final answer carrying it too
    expected = smoke.expected_value(NONCE)
    db = _store(tmp_path / "state.db", [
        ("user", None, "run the command"),
        ("assistant", None, None),
        ("tool", "terminal", '{"output": "smoke-ok:' + NONCE + '\\n", "exit_code": 0}'),
        ("assistant", None, expected),
    ], tool_call_count=1)

    # When  the smoke evaluates it
    problems = _evaluate(db, expected)

    # Then  there is nothing to report
    assert problems == [], problems


def test_a_non_terminal_tool_call_does_not_count(tmp_path):
    """Another tool is not the terminal: the legs need commands, so it cannot pass."""

    # Given a write_file result that carries the nonce (a tool ran, but not a shell)
    expected = smoke.expected_value(NONCE)
    db = _store(tmp_path / "state.db", [
        ("user", None, "run the command"),
        ("assistant", None, None),
        ("tool", "write_file", '{"ok": true, "content": "' + expected + '"}'),
        ("assistant", None, expected),
    ], tool_call_count=1)

    # When  the smoke evaluates it
    problems = _evaluate(db, expected)

    # Then  it fails, naming the terminal tool as the one that had to run
    assert problems, "a non-terminal tool must not satisfy the smoke"
    assert any("terminal" in p for p in problems), problems


def test_a_tool_count_without_the_terminal_result_is_a_failure(tmp_path):
    """`tool_call_count` is a summary counter, never evidence."""

    # Given a session that claims tool calls but whose transcript carries no terminal result
    expected = smoke.expected_value(NONCE)
    db = _store(tmp_path / "state.db", [
        ("user", None, "run the command"),
        ("assistant", None, expected),
    ], tool_call_count=3)

    # When  the smoke evaluates it
    problems = _evaluate(db, expected)

    # Then  it fails on the missing tool evidence
    assert problems, "a tool counter must not stand in for the terminal result"
    assert any("without calling a tool" in p or "terminal" in p for p in problems), problems


def test_a_missing_transcript_is_a_named_failure(tmp_path):
    """Absence of evidence is a loud failure, never a pass."""

    # Given a state.db that is not a readable sessions store
    db = tmp_path / "state.db"
    db.write_text("this is not a sqlite database")

    # When  the smoke runs against it
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "run", "--state-db", str(db), "--timeout", "1"],
        capture_output=True, text=True, timeout=60,
    )

    # Then  it exits non-zero naming the transcript it could not read, without calling the model
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert "no readable sessions store" in proc.stderr, proc.stderr


def _hermes_stub(tmp_path: Path, *, writes_store: bool) -> Path:
    """A real `hermes` executable: it writes the session a passing smoke needs, or nothing at all.

    The nonce is read from the token file the PROMPT names (argv), so the stub proves the same rule
    the real model faces: the value can only come from that file (issue #471).
    """
    db = tmp_path / "home" / "state.db"
    script = tmp_path / "hermes"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import os, re, sqlite3, sys\n"
        f"DB = {str(db)!r}\n"
        "WRITES = " + ("True" if writes_store else "False") + "\n"
        "prompt = sys.argv[sys.argv.index('-z') + 1]\n"
        "m = re.search(r'(\\S*/hermes-smoke-[^/]+/token)', prompt)\n"
        "nonce = open(m.group(1)).read().strip() if m else 'no-nonce-found'\n"
        "if not WRITES:\n"
        "    print('answered without a transcript')\n"
        "    sys.exit(0)\n"
        "os.makedirs(os.path.dirname(DB), exist_ok=True)\n"
        "c = sqlite3.connect(DB)\n"
        "c.executescript('CREATE TABLE sessions (id TEXT PRIMARY KEY, started_at REAL,"
        " tool_call_count INTEGER); CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT,"
        " role TEXT, tool_name TEXT, content TEXT);')\n"
        "c.execute('INSERT INTO sessions VALUES (?, ?, ?)', ('sess-fresh', 1.0, 1))\n"
        "rows = [('user', None, 'run the command'), ('assistant', None, None),\n"
        "        ('tool', 'terminal', '{\"output\": \"smoke-ok:' + nonce + '\"}'),\n"
        "        ('assistant', None, 'smoke-ok:' + nonce)]\n"
        "for i, r in enumerate(rows, start=1):\n"
        "    c.execute('INSERT INTO messages VALUES (?, ?, ?, ?, ?)', (i, 'sess-fresh', *r))\n"
        "c.commit(); c.close()\n"
        "print('smoke-ok:' + nonce)\n"
    )
    script.chmod(0o755)
    return script


def test_a_fresh_home_with_no_store_passes_when_the_session_proves_the_call(tmp_path):
    """The image ships without a state.db; the run creates it, and only what it leaves is judged."""

    # Given a fresh HERMES_HOME (no state.db at all) and a hermes that writes the proving session
    db = tmp_path / "home" / "state.db"
    assert not db.exists()
    stub = _hermes_stub(tmp_path, writes_store=True)

    # When  the smoke runs against that store path
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "run", "--state-db", str(db), "--hermes", str(stub),
         "--timeout", "5"],
        capture_output=True, text=True, timeout=60,
    )

    # Then  it passes, having run the agent, and the store exists because the run wrote it
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "OK: session sess-fresh" in proc.stdout, proc.stdout
    assert db.exists(), "the smoke must accept the store its own run created"


def test_a_run_that_writes_no_store_is_a_named_failure(tmp_path):
    """A run that exits 0 and writes nothing is still a failure, and it names the store."""

    # Given a fresh HERMES_HOME and a hermes that writes no store
    db = tmp_path / "home" / "state.db"
    stub = _hermes_stub(tmp_path, writes_store=False)

    # When  the smoke runs
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "run", "--state-db", str(db), "--hermes", str(stub),
         "--timeout", "2"],
        capture_output=True, text=True, timeout=60,
    )

    # Then  it exits non-zero, naming the transcript the run did not write
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert "wrote no transcript at" in proc.stderr, proc.stderr
    assert str(db) in proc.stderr


def test_the_prompt_names_the_command_and_never_the_value(tmp_path):
    """The prompt states the command and the file, never the nonce it asks for."""

    # Given a token file holding the nonce the smoke will assert
    token = tmp_path / "token"
    token.write_text(NONCE + "\n")

    # When  the prompt is built for that path
    prompt = smoke.prompt_for(str(token))

    # Then  the command and the path are there, and the value is not
    assert NONCE not in prompt, "the prompt must not carry the value it asserts"
    assert str(token) in prompt, "the prompt must name the token file"
    assert "terminal tool" in prompt, "the prompt must name the terminal tool"
    assert "printf 'smoke-ok:%s" in prompt, "the prompt must name the exact command"
    assert smoke.expected_value(NONCE) not in prompt


def test_the_recipe_and_the_workflow_run_the_proof():
    """The proof runs where the bots run it, through the Makefile."""

    # Given the Makefile and the issue-bot workflow
    makefile = MAKEFILE.read_text()
    workflow = WORKFLOW.read_text()

    # When  the smoke recipe and the workflow's smoke step are read
    lines = makefile.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("_hermes-smoke:")), None)
    assert start is not None, "_hermes-smoke recipe not found"
    body_lines = []
    for line in lines[start + 1:]:
        if line.startswith("\t"):
            body_lines.append(line)
        elif line.startswith("#") or not line.strip():
            continue
        else:
            break
    body = "\n".join(body_lines)

    # Then  the recipe runs the script with the alias variable, and the workflow calls the target
    assert "scripts/hermes_smoke.py run" in body, body
    assert "--alias $(nous-model)" in body, body
    assert "make hermes-smoke" in workflow, "issue-bot.yml must still run make hermes-smoke"
    assert re.search(r"(?m)^nous-model := nous-deepseek$", makefile), "one place the alias name lives"


def _prompt_carriers() -> list[Path]:
    """The files that can carry a bot prompt: recipes, workflows, scripts, image files."""
    out = [MAKEFILE]
    out += sorted((REPO / ".github" / "workflows").glob("*.yml"))
    out += sorted((REPO / "scripts").rglob("*.py"))
    out += sorted((REPO / "scripts").rglob("*.sh"))
    out += sorted((REPO / "containers").rglob("*"))
    return [p for p in out if p.is_file()]


def test_the_text_echo_prompt_is_gone_from_the_tree():
    """A future edit cannot turn the smoke back into a sentence assertion."""

    # Given every file that can carry a bot prompt
    carriers = _prompt_carriers()

    # When  they are searched for the old sentence assertion
    offenders = [str(p.relative_to(REPO)) for p in carriers
                 if OLD_PROMPT in p.read_text(errors="replace")]

    # Then  none carries it
    assert offenders == [], f"the text-echo prompt is back in: {offenders}"
