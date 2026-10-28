"""The JEV preflight's failure is readable, and tracked once per class (issue #802).

`make agent-jev-preflight NERVE_REQUIRE=1` is a bot job's first step, and its failure used to be a step
name and a `[require-env] FATAL` line: measured on issue-dedupe runs 40697636784 / 40702295009, the
duplicate sweep decided nothing, and no issue tracked it. `scripts/jev_preflight_tracker.py` classifies
the preflight's own output, prints the class and its fix, and files ONE issue per class — deduped by a
body marker so a second run of the same class creates nothing.

`gh` is the external system here: the stand-in below is a real executable the production code calls
through `subprocess`, and the assertions are on the request it built (title, marker, body) — the
classifier, the marker and the issue shape all run for real.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import issue_body
import jev_preflight_tracker as tracker

#: The exact line the preflight's `require_env.py` guard printed in the two failing runs.
KEY_MISSING_LOG = (
    "dedup\tProve the JEV engine is active \u2014 the decision does not start without it (issue\t"
    "\ufeff2026-10-28T14:10:43.7085994Z [require-env] FATAL: TYPESAFE_API_KEY is missing or empty "
    "\u2014 refusing to start. Set the repository secret (the value stays in the environment and is "
    "never printed).\n"
    "dedup\tProve the JEV engine is active \u2014 the decision does not start without it (issue\t"
    "2026-10-28T14:10:43.7122689Z make: *** [Makefile:661: agent-jev-preflight] Error 2\n"
)

PLUGIN_MISSING_LOG = (
    "[jev-preflight] ERROR: the nerve plugin is not installed in /root/.hermes "
    "(plugins/nerve/plugin.yaml is missing) — the agent image was not built with "
    "containers/agent/Dockerfile (NERVE_REQUIRE=1 — the JEV layer is required here: a bot run does "
    "not start without it, and an image check fails without it)\n"
)


FAKE_GH = '''#!{python}
import json, os, pathlib, re, sys

state = pathlib.Path(os.environ["FAKE_GH_STATE"])
calls = pathlib.Path(os.environ["FAKE_GH_CALLS"])
args = sys.argv[1:]
with calls.open("a") as fh:
    fh.write(json.dumps(args) + "\\n")
existing = json.loads(state.read_text()) if state.exists() else []
if args[:2] == ["issue", "list"]:
    query = " ".join(a for a in args if "in:body" in a)
    print(json.dumps([{{"number": row["number"]}} for row in existing
                      if row["class"] in query]))
elif args[:2] == ["issue", "create"]:
    body = args[args.index("--body") + 1]
    cls = re.search(r"<!-- jev-preflight: ([a-z-]+) -->", body).group(1)
    number = 901 + len(existing)
    state.write_text(json.dumps(existing + [{{"number": number, "class": cls}}]))
    print(f"https://github.com/acme/widgets/issues/{{number}}")
else:
    sys.stderr.write("fake gh: unsupported " + " ".join(args) + "\\n")
    sys.exit(2)
'''


@pytest.fixture()
def fake_gh(tmp_path, monkeypatch):
    """A real `gh` executable on PATH that records every request the tracker builds."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    gh = bindir / "gh"
    gh.write_text(FAKE_GH.format(python=sys.executable))
    gh.chmod(0o755)
    state = tmp_path / "state.json"
    calls = tmp_path / "calls.jsonl"
    monkeypatch.setenv("PATH", f"{bindir}:{__import__('os').environ['PATH']}")
    monkeypatch.setenv("FAKE_GH_STATE", str(state))
    monkeypatch.setenv("FAKE_GH_CALLS", str(calls))
    return state, calls


def _calls(path: Path) -> list[list[str]]:
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def test_the_missing_provider_key_is_its_own_class_and_names_the_fix():
    """The measured failure of both issue-dedupe runs classifies as `key-missing`, with the fix."""

    # Given the exact output the two failing runs printed
    # When  the tracker classifies it
    name, reason = tracker.classify(KEY_MISSING_LOG)

    # Then  it is its own class, the measured line is carried, and the fix names the secret AND
    #       the place it has to be passed — not "see the log"
    assert name == "key-missing"
    assert reason.startswith("[require-env] FATAL: TYPESAFE_API_KEY is missing or empty")
    assert "2026-10-28T" not in reason and "\ufeff" not in reason
    fix = tracker.fix_for(name)
    assert "TYPESAFE_API_KEY" in fix
    assert "secrets.TYPESAFE_API_KEY" in fix


def test_each_failure_class_is_read_from_the_preflights_own_words():
    """Every class the preflight can report is recognised, and an unreadable failure is `unknown`."""

    # Given one output per preflight failure the script can print
    samples = {
        "plugin-missing": PLUGIN_MISSING_LOG,
        "plugin-disabled": "[jev-preflight] ERROR: nerve is 'disabled' in /root/.hermes: an "
                           "installed-but-disabled plugin does nothing for the run\n",
        "hermes-missing": "[jev-preflight] ERROR: no hermes on PATH\n",
        "provider-unreachable": "[jev-preflight] ERROR: the typesafe provider did not answer a live "
                                "decision call\n",
        "provider-no-payload": "[jev-preflight] ERROR: the smoke returned no decision payload\n",
        "unknown": "[jev-preflight] something nobody has seen before\n",
    }

    # When  each is classified
    got = {expected: tracker.classify(text)[0] for expected, text in samples.items()}

    # Then  the class is the preflight's own vocabulary, never a guess
    assert got == {expected: expected for expected in samples}


def test_the_first_failure_files_one_tracker_in_the_issue_shape(fake_gh):
    """The first failure of a class files ONE issue, in the repository's shape, marked for dedupe."""

    # Given a repo with no open tracker for this class
    state, calls = fake_gh

    # When  the tracker reports the preflight failure of a real run
    rc = tracker.report("acme/widgets", KEY_MISSING_LOG,
                        run_url="https://github.com/acme/widgets/actions/runs/40702295009")

    # Then  it exits clean (the step's own exit status stays the caller's) and filed exactly one issue
    assert rc == 0
    creates = [c for c in _calls(calls) if c[:2] == ["issue", "create"]]
    assert len(creates) == 1
    create = creates[0]
    title = create[create.index("--title") + 1]
    body = create[create.index("--body") + 1]
    assert "key-missing" in title
    assert "agent:implement" in create

    # And   the marker is the body's FIRST line, the sections are the one shape, in order, and the
    #       evidence a reader needs (run, measured line, class) is in the technical section
    assert body.splitlines()[0] == tracker.marker("key-missing")
    assert issue_body.headings(body) == list(issue_body.SECTIONS)
    assert "TYPESAFE_API_KEY is missing or empty" in body
    assert "40702295009" in body
    assert issue_body.section_body(body, "Acceptance criteria").count("- [ ]") >= 3
    assert [row["number"] for row in json.loads(state.read_text())] == [901]


def test_a_second_run_of_the_same_class_files_nothing(fake_gh):
    """One tracker per class, not per run: the second failure finds the issue and creates nothing."""

    # Given a tracker already open for this class
    state, calls = fake_gh
    tracker.report("acme/widgets", KEY_MISSING_LOG, run_url="https://example.test/run/1")
    first = [c for c in _calls(calls) if c[:2] == ["issue", "create"]]

    # When  a later run fails the same way
    rc = tracker.report("acme/widgets", KEY_MISSING_LOG, run_url="https://example.test/run/2")

    # Then  no second issue is created, the first is what the run points at, and the exit stays clean
    assert rc == 0
    creates = [c for c in _calls(calls) if c[:2] == ["issue", "create"]]
    assert len(first) == 1 and len(creates) == 1
    assert [row["number"] for row in json.loads(state.read_text())] == [901]


def test_two_classes_are_two_trackers(fake_gh):
    """Per class, not per bot: a different class is a different work item."""

    # Given a `key-missing` tracker already filed
    state, calls = fake_gh
    tracker.report("acme/widgets", KEY_MISSING_LOG)

    # When  the preflight later fails for a different reason
    tracker.report("acme/widgets", PLUGIN_MISSING_LOG)

    # Then  that class has its own issue, so a fix for one is not read as a fix for the other
    assert len([c for c in _calls(calls) if c[:2] == ["issue", "create"]]) == 2
    assert [row["number"] for row in json.loads(state.read_text())] == [901, 902]


def test_an_unset_repo_is_loud_and_files_nothing(fake_gh):
    """A step that names no repo cannot track anything, and says so instead of passing silently."""

    # Given a tracker invoked without a repository
    _state, calls = fake_gh

    # When  it reports
    rc = tracker.report("", KEY_MISSING_LOG)

    # Then  it is a non-zero result with no gh write attempted
    assert rc == 1
    assert _calls(calls) == []


def test_a_gh_failure_is_reported_not_swallowed(fake_gh, monkeypatch, capsys):
    """A tracker that cannot file says so on stderr and returns non-zero — never a silent pass."""

    # Given a gh that refuses the write
    _state, _calls = fake_gh
    monkeypatch.setattr(tracker, "_gh", lambda args: (_ for _ in ()).throw(RuntimeError("boom")))

    # When  the tracker reports
    rc = tracker.report("acme/widgets", KEY_MISSING_LOG)

    # Then  the failure is loud, and the step's own red is not replaced by a green tracker
    assert rc == 1
    assert "could not file the tracker" in capsys.readouterr().err


def test_the_dedupe_job_passes_the_key_the_preflight_requires():
    """The measured cause: the job never set the provider key the preflight requires (issue #802)."""

    # Given the issue-dedupe workflow
    import yaml
    workflow = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / ".github/workflows/issue-dedupe.yml").read_text())

    # When  the dedup job and its preflight step are read
    job = workflow["jobs"]["dedup"]
    step = next(s for s in job["steps"] if "JEV engine is active" in (s.get("name") or ""))

    # Then  the provider key reaches the step (job env) and the step runs the target that tracks a
    #       failure — never the bare target whose only output was a step name
    assert job["env"]["TYPESAFE_API_KEY"] == "${{ secrets.TYPESAFE_API_KEY }}"
    assert "make jev-preflight-required" in step["run"]
    assert step["env"]["GH_TOKEN"] == "${{ github.token }}"
    assert "RUN_URL" in step["env"]


def test_a_local_run_reports_and_writes_nothing(fake_gh):
    """Only the CI step files. A person running the target on a host writes nothing (issue #809)."""

    # Given a local run on a host whose preflight cannot start (no Docker daemon here)
    _state, calls = fake_gh
    local_log = ("[jev-preflight] ERROR: Cannot connect to the Docker daemon at "
                 "unix:///var/run/docker.sock. Is the docker daemon running?\n")

    # When  the tracker reports with --local
    rc = tracker.report("acme/widgets", local_log, local=True)

    # Then  the class and the fix are printed, no gh call is made, and the run is not a failure of
    #       the tracker — the repository is untouched by a local invocation
    assert rc == 0
    assert _calls(calls) == []


def test_the_dedupe_leg_receives_the_provider_key_like_the_refiner_does():
    """The same omission existed one layer down: the dedup container got no JEV key (issue #802)."""

    # Given the Makefile the workflow drives
    makefile = (Path(__file__).resolve().parents[1] / "Makefile").read_text()

    # When  the `issue-dedup` recipe (up to its internal `_issue-dedup` target) is read
    recipe = makefile.split("\nissue-dedup:", 1)[1].split("\n_issue-dedup:", 1)[0]

    # Then  it forwards the provider key to the agent image, exactly as `issue-refiner` does — the
    #       job-level secret alone reaches the HOST step, not the decision leg's container
    assert "-e TYPESAFE_API_KEY" in recipe
