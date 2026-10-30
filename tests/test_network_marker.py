#!/usr/bin/env python3
"""The pin for issue #1000: the unit gate must never execute a network-marked test, and no
unmarked scope really reaches the Hub.

`pytest.ini` registers the `network` marker and `scripts/unit_tests.py` builds the unit gate as
`-m "not network"` (the #1002 network pipeline uses `-m network` on the SAME seam). These tests fail
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

import ast
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

    collected = _collect_marker(REPO, "not network")
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


def test_ci_unit_reaches_the_not_network_seam():
    """Lock the structural wiring so `-m "not network"` cannot silently drop out between the
    Makefile, ci.yml and unit_tests.py: `ci-unit` -> `test-unit` -> `unit_tests.py run` (default
    `-m "not network"`), and `test-unit-network` -> `--marker network`. The hermetic gate excludes
    network-marked tests only if this chain holds end-to-end, not just in unit_tests.py alone."""
    mk = (REPO / "Makefile").read_text()

    def target_recipe(t):
        m = re.search(r"(?m)^%s:.+\n((?:\t[^\n]*\n)+)" % t, mk)
        assert m, f"make target {t} missing"
        return m.group(1)

    ci_unit = target_recipe("ci-unit")
    test_unit = target_recipe("test-unit")
    assert "test-unit" in ci_unit, f"ci-unit must call test-unit:\n{ci_unit}"
    assert "unit_tests.py run" in test_unit, f"test-unit must call unit_tests.py run:\n{test_unit}"
    # the default run() carries `-m "not network"` (asserted by test_the_unit_gate_runs_not_network)
    tn = target_recipe("test-unit-network")
    assert "--marker network" in tn, f"test-unit-network must run the network marker:\n{tn}"
    # the CI unit gate runs `make ci-unit`; ci.yml reuses pipeline.yml's `unit` job to reach it
    ci = (REPO / ".github" / "workflows" / "ci.yml").read_text()
    pl = (REPO / ".github" / "workflows" / "pipeline.yml").read_text()
    assert "pipeline.yml" in ci, "ci.yml must invoke the pipeline reuse for the unit gate"
    assert "make ci-unit" in pl, "pipeline.yml's unit job must run `make ci-unit`"


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


def _net_node_parts(node: str) -> tuple[str, str]:
    """(file, testname) for a collected pytest node id, stripping any [params] suffix."""
    if "::" not in node:
        return ("", "")
    f, t = node.split("::", 1)
    return (f, t.split("[", 1)[0])


def _collect_marker(root: Path, marker: str) -> set[str]:
    """Run the gate's OWN collect as `-m <marker>` over the whole hermetic selection and return the
    collected node ids. ONE invocation in the pin's both directions (`not network` for the unit gate,
    `network` for the network pipeline) so the expression can never drift between them."""
    import subprocess as _sp

    files = ut.select(root)
    argv = [sys.executable, "-m", "pytest", "--collect-only", "-q", "-m",
            marker, "-p", "no:cacheprovider", *files]
    run = _sp.run(argv, cwd=root, capture_output=True, text=True)
    assert run.returncode == 0, run.stdout[-2000:] + run.stderr[-2000:]
    return {ln.strip() for ln in run.stdout.splitlines() if "::" in ln}


def test_the_network_pipeline_owns_the_marks():
    """#1002 ownership proof: every `@pytest.mark.network` test is genuinely MEMBER of the network
    pipeline's set — `pytest --collect-only -m network` (the seam `make test-unit-network` runs)
    must collect every network-marked node. A marker pytest cannot select under `-m network` is not
    membership, it is decoration. (The `-m "not network"` twin is the execution pin; this proves the
    marks are ALSO reachable by the network side, per the owner's #1002 split.)"""
    files = ut.select(REPO)
    marked: dict[str, set[str]] = {}
    for doc in files:
        names = {
            m.group(1)
            for m in re.finditer(
                r"@pytest\.mark\.network\s*\n\s*(?:async\s+)?def\s+(test_\w+)\(", (REPO / doc).read_text()
            )
        }
        if names:
            marked[doc] = names
    assert marked, "no network-marked test — nothing for the network pipeline to own"

    collected = {
        _net_node_parts(ln)
        for ln in _collect_marker(REPO, "network")
    }
    missing = [
        f"{doc}::{name}"
        for doc, names in marked.items()
        for name in sorted(names)
        if (doc, name) not in collected
    ]
    assert not missing, (
        "#1002 ownership: these network-marked tests are NOT collected by the `-m network` seam, "
        "so the network pipeline does not own them:\n" + "\n".join(missing[:8])
    )


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
#: A scope that replaces the `hf_download.py` CHILD (the only thing `mp.download` reaches the
#: Hub through): `subprocess.run` stubbed, or `HF_BIN` pointed at a local script.
_STUBBED_CHILD_RE = re.compile(
    r"monkeypatch\.setattr\(\s*mp\.subprocess|monkeypatch\.setenv\(\s*[\"']HF_BIN"
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
    # a model dict defined at module/test scope that carries a live Hub id (`X = {... "hf": "org/repo" ...}`)
    # is a real-call source: `mp.download(X, ...)` / `mp.gguf_files(X["hf"])` reach the Hub even when
    # the call line itself shows no huggingface.co literal (the model id is the host reference).
    _MODEL_DICT = re.compile(r"([A-Za-z_]\w*)\s*=\s*\{[^}]*?\bhf\b[\"']?\s*:")
    module_hf_models = {m.group(1) for m in _MODEL_DICT.finditer(file_text)}

    def _scan_scope(body: str, name: str) -> None:
        nono = _LOOPBACK_RE.search(body)
        hf_models = dict.fromkeys(module_hf_models) | dict.fromkeys(
            f.group(1) for f in _MODEL_DICT.finditer(body)
        )
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
                to = " ".join(match.group(2) for match in re.finditer(
                    r"([\"'])(.*?)\1", s)) + " " + " ".join(
                    v for k, v in hub_vars.items() if re.search(r"\b%s\b" % re.escape(k), s))
                if _HUB_RE.search(to):
                    problems.append((name, s[:140]))
            # the repo's OWN Hub entry points (no loopback): a real reach, whatever the arg shape —
            # `mp.download`/`mp.gguf_files`/`mp.hf_size` are Hub entry points by construction (they
            # call the Hub API / download via `_hub_json(f"{HF}/api/…")`), so there is no hermetic
            # call form of them. A call in an unmarked scope that binds no loopback server IS a real
            # unmarked Hub reach, whether the arg is a model dict, a `mp.repo_for(...)` call, or a
            # plain repo string. NOT plan_download (planning only — the engine lane's carve-out) and
            # NOT resolve_local (local disk only).
            # EXCEPTION — a call whose download CHILD is replaced makes no reach: `mp.download`
            # never opens the Hub itself, it runs `scripts/hf_download.py` in a child, so a scope
            # that stubs that child (`monkeypatch.setattr(mp.subprocess, "run", …)`) or points it
            # at a local script (`HF_BIN=<tmp stub>`) downloads nothing (#872's bounded-child
            # tests: one records the argv, the other runs a `sleep` script). The tree/stub half
            # of those scopes is separately stubbed as a fixture — same doctrine as the
            # `def urlopen(...)` stub carve-out above.
            if not nono and not _STUBBED_CHILD_RE.search(body) and re.search(
                r"\b(mp\.download|mp\.gguf_files|mp\.hf_size)\s*\(", s
            ):
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
        + "\nRoute each to `@pytest.mark.network` (owned by the #1002 network pipeline), to a "
        "loopback server, or to `hub_probe` liveness; never a silent real call in the unit path."
    )


_MODULE_MARK_RE = re.compile(r"(?m)^pytestmark\s*=\s*pytest\.mark\.network\b")


def test_a_module_level_pytestmark_routes_the_whole_module_off_the_unit_gate():
    """A whole live-Hub module says so ONCE (`pytestmark = pytest.mark.network`) instead of
    decorating 40 cases — and that must still move every case to the network pipeline, on the
    gate's own collect (#872: `tests/test_pick_full_registry.py` resolved the live Hub and its
    429s starved 36 cases in `linux / unit`). A module-level mark that collected nothing, or
    that left a node in `-m "not network"`, is the silent unit-gate leak this pins."""
    files = [d for d in ut.select(REPO) if _MODULE_MARK_RE.search((REPO / d).read_text())]
    assert files, "no module-level `pytestmark = pytest.mark.network` — nothing to route"

    network = {_net_node_parts(ln) for ln in _collect_marker(REPO, "network")}
    hermetic = {_net_node_parts(ln) for ln in _collect_marker(REPO, "not network")}

    for doc in files:
        routed = {p for p in network if p[0] == doc}
        # Then every case in the module is owned by the network pipeline ...
        assert routed, f"{doc}: the module-level network mark selected no test under -m network"
        # ... and none of it is executed by the hermetic gate
        leaked = sorted(p[1] for p in hermetic if p[0] == doc)
        assert not leaked, (
            f"{doc}: {len(leaked)} case(s) with a module-level network mark are still in the "
            f"`-m \"not network\"` set, e.g. {leaked[:5]}"
        )


# --------------------------------------------------------------------------------------------
# issue #1067: the #1000 pin above is Hub-ONLY and same-scope. `_HUB_RE` is the literal
# `(huggingface.co|hf.co)`, and `_hub_opens` scans a test's OWN text — so a live fetch that
#   (a) targets ANOTHER host (`raw.githubusercontent.com`) and
#   (b) happens INSIDE a helper module (`sync_registry.sync` -> `fetch` -> `urlopen`)
# is invisible to it by construction. Measured at `main@36cfa8c1`: `tests/test_registry_sync_trend.py`'s
# module fixture downloaded the live upstream registry on every `ci-unit` run while that file
# was green.
#
# The scan below closes both halves. It resolves, per repo module, which functions can reach a
# REMOTE host (transitively along that module's own call graph, and resolved through module
# constants so `f"{_UPSTREAM_DATA}/data/models.json"` names `raw.githubusercontent.com`), then
# flags a call to one of them from a test or fixture scope that is not `@pytest.mark.network`-
# marked — naming the host it saw.
#
# Argument sensitivity, deliberately: a helper whose URL prefix cannot be resolved at all
# (`load_registry(src)` opens only when `src.startswith("http")`) is CONDITIONAL — it counts only
# when the call site hands it something that resolves to a remote URL. A helper whose resolved
# prefix is already remote (`f"{BASE}/{path}"`) is unconditional. So the hermetic `load_registry`
# / `sync` callers that pass committed paths stay clean, and the one live caller does not.
# --------------------------------------------------------------------------------------------

_URL_HOST_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*://([^/?#]+)")
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]"}
_NET_FUNC_NAMES = {
    "urlopen", "urlretrieve", "snapshot_download", "hf_hub_download",
    "hf_hub_snapshot_download", "repo_download", "download_file",
}
_NET_MODULE_CALL_RE = re.compile(r"^(requests|httpx)\.(get|post|put|head|delete|request|stream)$")
_UNRESOLVED = "<unresolved host>"
#: A scope that REPLACES the transport is not making a real call: `def urlopen(...)` standing in
#: for urllib's, or `monkeypatch.setattr(..., "urlopen", ...)`. This is the rule the #1000 scan
#: above already applies to a re-defined primitive, applied to the module-level transport too.
_STUB_RE = re.compile(
    r"setattr\s*\([^)]*\b(urlopen|urlretrieve|snapshot_download|hf_hub_download)\b"
    r"|def\s+(urlopen|urlretrieve)\s*\("
)
_LOOPBACK_TARGET_RE = re.compile(r"localhost|127\.0\.0\.1|0\.0\.0\.0|::1", re.I)


def _host_of(url: str) -> str | None:
    """The remote host of a URL string, or None for a loopback / non-URL value."""
    m = _URL_HOST_RE.match(str(url or "").strip())
    if not m:
        return None
    host = m.group(1).rsplit("@", 1)[-1]
    host = host.split(":")[0].strip().strip("[]").lower()
    if host in _LOCAL_HOSTS or host.endswith(".localhost"):
        return None
    return host


def _dotted(node: ast.AST) -> str:
    """`a.b.c` for an Attribute/Name chain, else ''."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _is_network_primitive(call: ast.Call) -> bool:
    name = _dotted(call.func)
    if not name:
        return False
    if name.split(".")[-1] in _NET_FUNC_NAMES:
        return True
    return bool(_NET_MODULE_CALL_RE.match(name))


def _resolved(node: ast.AST | None, consts: dict[str, str],
              module_consts: dict[str, dict[str, str]], depth: int = 0) -> tuple[str, bool]:
    """(the longest string this expression can be proven to start with, fully resolved?).

    Resolves literals, f-strings over proven names, `+` concatenation, `Path / "part"` joins,
    module-level constants, and `<alias>.<CONST>` of an imported module. An unresolved part
    contributes "" and marks the result incomplete, so a prefix that already names a host still
    counts (`f"{BASE}/{name}"` names the host of BASE); nothing is invented.
    """
    if node is None or depth > 6:
        return "", False
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value, True
    if isinstance(node, ast.JoinedStr):
        text, complete = "", True
        for part in node.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                text += part.value
            elif isinstance(part, ast.FormattedValue):
                sub, ok = _resolved(part.value, consts, module_consts, depth + 1)
                text += sub
                complete = complete and ok
        return text, complete
    if isinstance(node, ast.Name):
        if node.id in consts:
            return consts[node.id], True
        return "", False
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        found = module_consts.get(node.value.id, {}).get(node.attr)
        return (found, True) if found is not None else ("", False)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Div)):
        left, lok = _resolved(node.left, consts, module_consts, depth + 1)
        right, rok = _resolved(node.right, consts, module_consts, depth + 1)
        sep = "" if isinstance(node.op, ast.Add) else "/"
        return left + sep + right, lok and rok
    if isinstance(node, ast.Call):
        for arg in node.args:  # `str(NAME)`
            text, ok = _resolved(arg, consts, module_consts, depth + 1)
            if text:
                return text, ok
    return "", False


def _module_consts(tree: ast.Module) -> dict[str, str]:
    """Module-level string constants, resolved in source order so `A = f"{B}/x"` works."""
    out: dict[str, str] = {}
    for stmt in tree.body:
        if not isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            continue
        targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
        if len(targets) != 1 or not isinstance(targets[0], ast.Name):
            continue
        text, complete = _resolved(stmt.value, out, {})
        if text:
            out[targets[0].id] = text
    return out


def module_network_reach(path: Path) -> dict[str, tuple[set[str], bool]]:
    """Function name -> (remote hosts it can reach, conditional?).

    A function reaches a host when it calls a network primitive (`urlopen`, `requests.get`, …)
    whose URL argument resolves to that host, or when it calls a sibling function of the same
    module that does. `conditional` is True when the primitive's URL cannot be resolved at all
    from the module itself (it is assembled from an argument), so only the CALL SITE can say
    whether it reaches — `load_registry(src)` is the canonical shape.
    """
    if not path.exists():
        return {}
    text = path.read_text()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {}
    consts = _module_consts(tree)
    module_hosts = {h for h in (_host_of(v) for v in consts.values()) if h}
    funcs = {n.name: n for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    direct: dict[str, tuple[set[str], bool]] = {}
    edges: dict[str, set[str]] = {}
    for name, fn in funcs.items():
        hosts: set[str] = set()
        conditional = False
        calls: set[str] = set()
        fn_source = ast.get_source_segment(text, fn) or ""
        for node in ast.walk(fn):
            if not isinstance(node, ast.Call):
                continue
            if _is_network_primitive(node):
                segment = ast.get_source_segment(text, node) or ""
                values = [_resolved(a, consts, {})[0] for a in
                          list(node.args) + [k.value for k in node.keywords]]
                found = {h for h in (_host_of(v) for v in values) if h}
                if found:
                    hosts |= found
                elif _LOOPBACK_TARGET_RE.search(segment) or _LOOPBACK_TARGET_RE.search(fn_source):
                    continue  # a loopback default (`probe(host="127.0.0.1")`) is not a reach
                elif any(v for v in values):
                    hosts |= {_UNRESOLVED}
                else:
                    conditional = True  # the URL is assembled from an argument
            elif isinstance(node.func, ast.Name) and node.func.id in funcs:
                calls.add(node.func.id)
        direct[name] = (hosts, conditional)
        edges[name] = calls
    reach = {name: (set(h), c) for name, (h, c) in direct.items()}
    for _ in range(len(reach) + 1):  # fixpoint over the intra-module call graph
        grew = False
        for name, calls in edges.items():
            for callee in calls:
                chosts, ccond = reach.get(callee, (set(), False))
                if chosts - reach[name][0]:
                    reach[name] = (reach[name][0] | chosts, reach[name][1])
                    grew = True
                if ccond and not reach[name][1]:
                    reach[name] = (reach[name][0], True)
                    grew = True
        if not grew:
            break
    return {name: (hosts | (module_hosts if cond else set()), cond)
            for name, (hosts, cond) in reach.items() if hosts or cond}


def _scripts_index(root: Path) -> dict[str, Path]:
    """Module name -> its file, for every importable module under `scripts/`."""
    scripts = root / "scripts"
    if not scripts.is_dir():
        return {}
    return {p.stem: p for p in scripts.glob("*.py")}


def _import_bindings(tree: ast.AST, root: Path) -> tuple[dict[str, Path], dict[str, tuple[Path, str]]]:
    """(`alias -> module file`, `local name -> (module file, function)`) for a test module."""
    modules = _scripts_index(root)
    aliases: dict[str, Path] = {}
    names: dict[str, tuple[Path, str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            parts = (node.module or "").lstrip(".").split(".")
            parts = parts[1:] if parts and parts[0] == "scripts" else ([] if not parts else parts)
            for alias in node.names:
                if alias.name in modules:  # `from scripts import sync_registry as sr`
                    aliases[alias.asname or alias.name] = modules[alias.name]
                elif parts and parts[0] in modules:  # `from scripts.sync_registry import sync`
                    names[alias.asname or alias.name] = (modules[parts[0]], alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                leaf = alias.name.split(".")[-1]
                if leaf in modules:  # `import sync_registry as sr`
                    aliases[alias.asname or leaf] = modules[leaf]
    return aliases, names


def _reach_calls(body: ast.AST, consts: dict[str, str], aliases: dict[str, Path],
                 names: dict[str, tuple[Path, str]],
                 reach: dict[str, dict[str, tuple[set[str], bool]]],
                 module_consts: dict[str, dict[str, str]],
                 source: str = "") -> list[tuple[str, str]]:
    """(host, `module.function`) for every call in `body` that reaches a remote host.

    A scope that replaces the transport (`def urlopen(...)`, `monkeypatch.setattr(…, "urlopen")`)
    makes no real call, so it reports nothing — the same carve-out the #1000 scan documents.
    """
    if _STUB_RE.search(source):
        return []
    out: list[tuple[str, str]] = []
    for node in ast.walk(body):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        path: Path | None = None
        fname = ""
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            path = aliases.get(func.value.id)  # `sr.sync(...)`
            fname = func.attr
        elif isinstance(func, ast.Name) and func.id in names:  # `sync(...)`
            path, fname = names[func.id]
        if path is None:
            continue
        hosts, conditional = reach.get(str(path), {}).get(fname, (set(), False))
        if conditional:
            # Only the arguments can say whether this call reaches: a committed path is a read,
            # a live URL is a fetch, and an argument nothing can prove is left alone rather than
            # guessed at (the helper's own default is not visible from here).
            arg_hosts: set[str] = set()
            for arg in list(node.args) + [k.value for k in node.keywords]:
                text, _ok = _resolved(arg, consts, module_consts)
                host = _host_of(text)
                if host:
                    arg_hosts.add(host)
            hosts = arg_hosts
        for host in sorted(hosts):
            out.append((host, f"{path.stem}.{fname}"))
    return out


def remote_reach_opens(root: Path, rel: str,
                       deselect: frozenset[str] | set[str] = frozenset()
                       ) -> list[tuple[str, str, str]]:
    """(scope, host, `module.function`) for every non-network-marked scope in `rel` that can reach
    a remote host through a helper module.

    The scope is a `test_*` function, or a pytest fixture that an UNMARKED test actually requests
    — a fixture no hermetic test takes is not part of the hermetic path. A node id in `deselect`
    (the roster's own record of what the gate does not run) is not part of it either.
    """
    path = root / rel
    if not path.exists():
        return []
    text = path.read_text()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    aliases, names = _import_bindings(tree, root)
    module_paths = set(aliases.values()) | {p for p, _f in names.values()}
    reach = {str(p): module_network_reach(p) for p in module_paths}
    consts = _module_consts(tree)
    module_consts = {alias: _module_consts(ast.parse(p.read_text())) for alias, p in aliases.items()
                     if p.exists()}

    def marked(fn: ast.AST) -> bool:
        return any("pytest.mark.network" in ast.unparse(d)
                   for d in getattr(fn, "decorator_list", []))

    funcs = {n.name: n for n in tree.body
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    fixtures = {name for name, fn in funcs.items()
                if any("fixture" in ast.unparse(d) for d in fn.decorator_list)}

    def with_fixtures(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> list[tuple[str, ast.AST]]:
        """The function plus every fixture it requests, transitively."""
        seen: list[tuple[str, ast.AST]] = [(fn.name, fn)]
        queue = [a.arg for a in fn.args.args if a.arg in fixtures]
        while queue:
            name = queue.pop()
            if any(name == n for n, _ in seen) or name not in funcs:
                continue
            node = funcs[name]
            seen.append((name, node))
            queue += [a.arg for a in node.args.args if a.arg in fixtures]
        return seen

    offenders: list[tuple[str, str, str]] = []
    for name, fn in funcs.items():
        if not name.startswith("test_") or marked(fn) or f"{rel}::{name}" in deselect:
            continue
        for scope, node in with_fixtures(fn):
            source = ast.get_source_segment(text, node) or ""
            for host, via in _reach_calls(node, consts, aliases, names, reach,
                                          module_consts, source):
                label = scope if scope == name else f"{name} (via fixture {scope})"
                if (label, host, via) not in offenders:
                    offenders.append((label, host, via))
    return offenders


def test_no_unmarked_remote_fetch_enters_the_gate():
    """issue #1067: zero live fetches to ANY host from a non-network-marked scope of the hermetic
    selection, including ones reached inside a helper module. Hub-only detection (#1000) is not
    enough: the motivating defect was a `raw.githubusercontent.com` download performed inside
    `sync_registry.fetch` while the test file named no Hub host at all."""
    offenders: list[str] = []
    deselected = set(ut.deselected(REPO))
    for doc in ut.select(REPO):
        for scope, host, via in remote_reach_opens(REPO, doc, deselected):
            offenders.append(f"{doc}::{scope}: live fetch to {host} via {via}")
    assert not offenders, (
        "#1067 pin: the hermetic selection can reach these hosts from non-network-marked scopes "
        "(a fixture a hermetic test requests counts):\n"
        + "\n".join(offenders[:8])
        + ("\n...and %d more" % (len(offenders) - 8) if len(offenders) > 8 else "")
        + "\nMark the owning tests `@pytest.mark.network` (run by `make test-unit-network`), or "
        "assert the same behaviour against a committed fixture."
    )


def test_the_remote_reach_report_names_the_host_it_saw():
    """Acceptance 3 of #1067: the report names the HOST, so a reviewer can tell `huggingface.co`
    from `raw.githubusercontent.com` without reading the regexes. The motivating reach is
    `sync_registry.sync` -> `fetch` -> `urllib.request.urlopen(UPSTREAM)`."""
    reach = module_network_reach(REPO / "scripts" / "sync_registry.py")

    assert "raw.githubusercontent.com" in reach.get("sync", (set(), False))[0], (
        "the per-module reach scan must see sync_registry.sync reaching the live raw host "
        f"through fetch(); got {reach.get('sync')}"
    )
    assert "raw.githubusercontent.com" in reach.get("fetch", (set(), False))[0], reach.get("fetch")


def test_the_remote_reach_scan_reds_on_a_non_hub_fetch_through_a_helper_module(tmp_path):
    """Acceptance 2 of #1067 — the NEGATIVE CONTROL.

    A live fetch to a NON-Hub host, reached through a helper module from an UNMARKED test, must be
    named (with its host and the helper that reaches it). The same call from a
    `@pytest.mark.network` test must not be — otherwise the detector would just be "any call to a
    module", not "a live fetch in the hermetic gate". Nothing is executed: the tree below is
    parsed, not run.
    """
    # Given a helper module that opens a non-Hub URL, and tests that call it
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "livedata.py").write_text(
        "import urllib.request\n"
        "BASE = 'https://raw.githubusercontent.com/example/repo/master'\n"
        "def pull(path):\n"
        "    with urllib.request.urlopen(f'{BASE}/{path}', timeout=5) as r:\n"
        "        return r.read()\n"
        "def load(src):\n"
        "    if src.startswith('http'):\n"
        "        return urllib.request.urlopen(src, timeout=5).read()\n"
        "    return None\n"
    )
    (tmp_path / "tests").mkdir()
    unmarked = "tests/test_unmarked.py"
    (tmp_path / unmarked).write_text(
        "from scripts import livedata\n"
        "def test_pulls_live():\n"
        "    livedata.pull('data/models.json')\n"
    )
    marked_rel = "tests/test_marked.py"
    (tmp_path / marked_rel).write_text(
        "import pytest\n"
        "from scripts import livedata\n"
        "@pytest.mark.network\n"
        "def test_pulls_live():\n"
        "    livedata.pull('data/models.json')\n"
    )
    # And a hermetic twin that only READS what the fetch would have written
    twin_rel = "tests/test_twin.py"
    (tmp_path / twin_rel).write_text(
        "from scripts import livedata\n"
        "COMMITTED = '/repo/data/models.json'\n"
        "def test_reads_the_committed_copy():\n"
        "    assert livedata.load(COMMITTED) is None\n"
    )
    fixture_rel = "tests/test_via_fixture.py"
    (tmp_path / fixture_rel).write_text(
        "import pytest\n"
        "from scripts import livedata\n"
        "@pytest.fixture\n"
        "def live_data():\n"
        "    return livedata.pull('data/models.json')\n"
        "def test_unmarked_uses_live_data(live_data):\n"
        "    assert live_data\n"
    )

    # When  each file is scanned
    offenders = remote_reach_opens(tmp_path, unmarked)
    marked_offenders = remote_reach_opens(tmp_path, marked_rel)
    twin_offenders = remote_reach_opens(tmp_path, twin_rel)
    fixture_offenders = remote_reach_opens(tmp_path, fixture_rel)

    # Then  the unmarked test is named with the host AND the helper that reaches it
    assert ("test_pulls_live", "raw.githubusercontent.com", "livedata.pull") in offenders, offenders
    # And   a network-marked test is not a hermetic-gate defect
    assert marked_offenders == [], marked_offenders
    # And   a conditional helper handed a committed path is a local read, not a fetch
    assert twin_offenders == [], twin_offenders
    # And   an unmarked test that REQUESTS the live fixture is named through it
    assert any("via fixture live_data" in scope and host == "raw.githubusercontent.com"
               for scope, host, _via in fixture_offenders), fixture_offenders
