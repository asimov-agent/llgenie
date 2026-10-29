#!/usr/bin/env python3
"""The pin for issue #1000: the unit gate must never execute a network-marked test, and no
unmarked scope really reaches the Hub.

`pytest.ini` registers the `network` marker and `scripts/unit_tests.py` builds the unit gate as
`-m "not network"` (the `ci-network` pipeline uses `-m network` on the SAME seam). These tests fail
closed: if the marker is renamed, if the gate drops the exclusion, if a network-marked test appears
without the marker, or if a NON-marked scope makes a real Hub reach, something here goes red rather
than the real call sneaking into the default runtime path.

A "real Hub reach" is judged two ways, and only the OR matters — a line that merely names the
domain is not a call, and a download call aimed at a loopback server is offline by construction:
  (a) a literal hub-host URL passed to a network primitive (`urlopen("https://huggingface.co/…")`);
  (b) a call to a network-reach ENTRY point (`mp.download`, `snapshot_download`, `requests.get`,
      `hf_hub_download`, `urlretrieve`, …) inside a scope that is NOT network-marked AND does not
      bind/target a loopback address (localhost / 127.0.0.1 / TestClient / in-process server).
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import unit_tests as ut  # noqa: E402


def tracked_markdown() -> set[str]:
    """Every markdown path git tracks in this checkout."""
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files"], check=True, capture_output=True, text=True
    ).stdout
    return {p for p in out.splitlines() if p.endswith(".md")}


def pull_request_ignore_globs(ci: str) -> list[str]:
    """The `paths-ignore:` globs declared under the `pull_request:` trigger (now: none)."""
    pr_block = ci.split("pull_request:", 1)[1].split("\n  push:", 1)[0]
    globs: list[str] = []
    if "paths-ignore:" in pr_block:
        tail = pr_block.split("paths-ignore:", 1)[1]
        for line in tail.splitlines():
            line = line.strip()
            if line.startswith("- "):  # block style: - "**/*.md"
                globs.append(line[2:].strip().strip('"').strip("'"))
            elif "[" in line and "]" in line:  # flow style: paths-ignore: ["**/*.md"]
                for a, b in re.findall(r'"([^"]+)"|\'([^\']+)\'', line):
                    globs.append(a or b)
            elif line and not line.startswith("#"):
                break
    return globs


def _pure_doc(rel: str) -> bool:
    return (
        rel.startswith("docs/")
        or rel.startswith("agent-wiki/")
        or rel.startswith("openspec/")
        or rel in {"README.md", "CHANGES.md"}
    )


def test_the_deferred_contract_keeps_branches_guarded():
    """No filter YET (deferral) — but the trigger must stay `pull_request` on `main` only."""
    ci = (REPO / ".github" / "workflows" / "ci.yml").read_text()
    pr = ci.split("pull_request:", 1)[1].split("\n  push:", 1)[0]
    assert "branches:" in pr and '"main"' in pr, (
        "#824 deferral: ci.yml must keep the pull_request trigger scoped to [main]; a silent "
        "widening to other branches/events re-opens the full-matrix cost without measurement"
    )


def test_any_paths_ignore_cannot_drop_a_non_doc_markdown_role():
    """A `paths-ignore` that skips markdown must only skip PURE docs — never a .md that carries a
    second role (skills, tests/fixtures, data, agents rules). Red on a `**/*.md`-style widen."""
    ci = (REPO / ".github" / "workflows" / "ci.yml").read_text()
    globs = pull_request_ignore_globs(ci)
    if not globs:
        return  # deferral: no filter yet, vacuously correct
    wide = [g for g in globs if g in ("**/*.md", "*.md", "**/*.markdown")]
    if not wide:
        return  # a specific filter (e.g. docs/**) is a separate review, not this drift
    offenders = sorted(p for p in tracked_markdown() if not _pure_doc(p))
    assert not offenders, (
        f"#824 drift reintroduced: paths-ignore {wide} skips {len(offenders)} tracked markdown "
        f"files that are NOT pure docs (e.g. {offenders[:5]}...). These carry a second role whose "
        "stages the wide ignore would drop — name doc LOCATIONS (docs/**, agent-wiki/**, "
        "openspec/**, README.md, CHANGES.md), never **/*.md"
    )


def test_the_unit_gate_executes_zero_network_marked_tests():
    """Execution-level half of the owner's stronger pin (#1000): the unit gate command must not
    EXECUTE a single network-marked node — proven at the collection level, not by file existence.
    Runs pytest --collect-only under the exact `-m "not network"` argv the gate uses and asserts
    that no collected node belongs to a @pytest.mark.network-decorated test."""
    import subprocess as _sp

    files = ut.select(REPO)
    # node ids that would be taken OFF the executable set by -m "not network":
    net_names: dict[str, set[str]] = {}
    for doc in files:
        text = (REPO / doc).read_text()
        names = {
            m.group(1)
            for m in re.finditer(
                r"@pytest\.mark\.network\s*\n\s*(?:async\s+)?def\s+(test_\w+)\(", text
            )
        }
        if names:
            net_names[doc] = names
    assert net_names, "no network-marked test to exclude — the seam excludes nothing"

    argv = [sys.executable, "-m", "pytest", "--collect-only", "-q", "-m",
            "not network", "-p", "no:cacheprovider", *files]
    run = _sp.run(argv, cwd=REPO, capture_output=True, text=True)
    assert run.returncode == 0, run.stdout[-2000:] + run.stderr[-2000:]
    collected = {ln.strip() for ln in run.stdout.splitlines() if "::" in ln}

    leaked = [
        f"{doc}::{name}"
        for doc, names in net_names.items()
        for name in names
        if any(ln.startswith(f"{doc}::{name}") for ln in collected)
    ]
    assert not leaked, (
        "#1000 execution pin: these network-marked nodes are in the unit gate's collect set, so "
        "-m \"not network\" does not exclude them:\n" + "\n".join(leaked[:8])
    )


def test_the_network_marker_is_registered_in_pytest_ini():
    cfg = (REPO / "pytest.ini").read_text()
    markers = cfg.split("markers =", 1)[1]
    assert "network:" in markers, "the `network` marker must be registered in pytest.ini"


def test_the_unit_gate_runs_not_network():
    args = ut.argv(REPO)
    assert "-m" in args, args
    assert "not network" in args, args


def test_the_network_pipeline_runs_on_the_same_seam():
    args = ut.argv(REPO, marker="network")
    assert "-m" in args and "network" in args and "not network" not in args, args


def test_network_marked_tests_exist_and_are_inside_the_gate():
    """`-m "not network"` only excludes something if the marker is actually on real tests in the
    selection — an exclusion that excludes nothing is that marker name rusting away."""
    marked = []
    for doc in ut.select(REPO):
        hits = re.findall(r"@pytest\.mark\.network", (REPO / doc).read_text())
        if hits:
            marked.append((doc, len(hits)))
    assert marked, "no selected test carries @pytest.mark.network — the marker excludes nothing"


_OPEN_RE = re.compile(
    r"\b(urlopen|urlretrieve|snapshot_download|hf_hub_download|hf_hub_snapshot_download|"
    r"repo_download|download_file|requests[._](get|post|put|head|delete|request|stream)|"
    r"httpx[._](get|post|put|head|delete|stream))\s*\("
)
_HUB_RE = re.compile(r"(huggingface\.co|hf\.co)", re.I)
_ENTRY_RE = re.compile(
    r"\b(mp\.download|hub_probe\.probe|snapshot_download|hf_hub_download|"
    r"hf_hub_snapshot_download|repo_download|download_file|urlretrieve|urlopen|"
    r"requests[._][a-z_]+|httpx[._][a-z_]+)\s*\("
)
_LOOPBACK_RE = re.compile(
    r"localhost|127\.0\.0\.1|0\.0\.0\.0|::1|TestClient|make_server|server|thread",
    re.I,
)


def _hub_opens(file_text: str) -> list[tuple[str, str]]:
    """Scopes in the file that really reach the Hub from a NON-network-marked site.

    Real reach is judged on the HOST of a URL actually handed to a network primitive, exactly as
    #1000's acceptance states ("zero unmarked real urllib/requests calls TO huggingface.co/hf.co"):
      - a network primitive (`urlopen`, `requests.get`, `urlretrieve`, `snapshot_download`, …)
        whose URL resolves to a Hub host — inline literal, or a variable assigned a Hub-host literal
        earlier in the scope;
      - at module level, the same.

    A line that merely names the domain without opening it, or that re-defines a primitive as a
    stub (`def urlopen(...)`) to monkeypatch, or that opens a LOOPBACK/hub_probe server URL, is NOT
    a real Hub call and must not flag. Returns (test_scope_name, line).
    """
    tests = list(
        re.finditer(
            r"^(?P<dec>(?:@[A-Za-z_][\w.]*\s*\n)*)\s*(?:async\s+)?def\s+(?P<name>test_\w+)\(",
            file_text, re.M,
        )
    )
    problems: list[tuple[str, str]] = []

    def _scan_scope(body: str, name: str) -> None:
        nono = _LOOPBACK_RE.search(body)
        hub_vars: dict[str, str] = {}
        non_def = [
            ln for ln in body.splitlines()
            if not re.match(r"^\s*def\s+[\w.]+\s*\(", ln)
        ]
        for line in non_def:
            s = line.strip()
            if s.startswith(("#", '"', "'")):
                continue
            # variable assigned a hub-host literal: name = "…huggingface.co…"
            m = re.match(r"([A-Za-z_]\w*)\s*=\s*([\"'])(.*?)\2", s)
            if m and _HUB_RE.search(m.group(3)):
                hub_vars[m.group(1)] = m.group(3)
            # a primitive call whose URL (literal or tracked var) is a hub host
            if _OPEN_RE.search(s):
                to = " ".join(match.group(3) for match in re.finditer(
                    r"([\"'])(.*?)\1", s)) + " " + " ".join(
                    v for k, v in hub_vars.items() if re.search(r"\b%s\b" % re.escape(k), s))
                if _HUB_RE.search(to):
                    problems.append((name, s[:140]))
            elif _HUB_RE.search(s):
                pass  # a mention with no open is not a call

    if not tests:
        _scan_scope(file_text, "<module>")
        return problems

    for i, t in enumerate(tests):
        if "@pytest.mark.network" in (t.group("dec") or ""):
            continue
        body = file_text[t.end() : (tests[i + 1].start() if i + 1 < len(tests) else len(file_text))]
        _scan_scope(body, t.group("name"))

    seen: list[tuple[str, str]] = []
    for p in problems:
        if p not in seen:
            seen.append(p)
    return seen


def test_no_unmarked_real_open_reaches_the_hub():
    """The #1000 acceptance pin: zero REAL opens to a Hub host from the hermetic selection's
    default path. Ground truth is a call reaching a Hub host, not a line that merely mentions the
    domain (the string-only files must not flag), and an offline loopback call must not flag. A
    non-network test, or the module level, that really opens the Hub fails this test."""
    offenders: list[str] = []
    for doc in ut.select(REPO):
        for test_name, line in _hub_opens((REPO / doc).read_text()):
            offenders.append(f"{doc}::{test_name}: {line[:150]}")
    assert not offenders, (
        "#1000 pin: the hermetic selection really reaches the Hub from these non-network sites:\n"
        + "\n".join(offenders[:8])
        + ("\n...and %d more" % (len(offenders) - 8) if len(offenders) > 8 else "")
        + "\nRoute each to `@pytest.mark.network` (owned by the ci-network pipeline), to a "
        "loopback server, or to `hub_probe` liveness; never a silent real call in the unit path."
    )
