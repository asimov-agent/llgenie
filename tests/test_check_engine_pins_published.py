"""The gate that stops a pin-bump PR merging before its image is published (#1622).

`ci.yml` builds/publishes no engine since issue #1027 — publishing is the
engine-build PRODUCER's job, and happens only when it is dispatched `push=true`.
Before #1622 nothing else verified the image: the PR's own
`test_every_image_install_pulls_is_published` DEFERS the repinned engine, because
that check was written for the pre-#1027 world where the same CI run published it.
So a bump could merge with its new tag never on GHCR, unseen until a scheduled run
tripped on the 404 (#1365/#1587 recurring class).

`scripts/check_engine_pins_published.py` closes it at the PR: an engine whose
committed params differ from the base is repinned by THIS change, so its exact tag
must resolve a manifest before merge. Hermetic: the repin set and the digest probe
are stubbed (the real diff is exercised against a real git base in one live test);
nothing touches the network.

Mirrors the fake-digest pattern of tests/test_ci_publish_order.py (issue #169).
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

import scripts.check_engine_pins_published as cpp  # noqa: E402  (the repo's one import root, issue #796)
import scripts.engine_image as ei  # noqa: E402

REGISTRY = "ghcr.io/asimov-agent"


def _head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def _fake_digest(resolve_map: dict[str, str]) -> tuple[object, list[str]]:
    """Digest probe answering from `resolve_map` ('' = 404); logs every lookup."""
    calls: list[str] = []

    def fake(ref: str):
        calls.append(ref)
        d = resolve_map.get(ref, "")
        return (d, "") if d else ("", "404 Not Found")

    return fake, calls


def test_no_engine_repinned_is_green_and_hermetic(monkeypatch):
    """A PR that repins nothing queries nothing: green, zero network."""
    monkeypatch.setattr(cpp, "repinned_engine_ids", lambda base, root=None: [])
    fake, calls = _fake_digest({})
    rc = cpp.check(_head(), digest=fake, registry=REGISTRY)
    assert rc == 0
    assert calls == [], "nothing repinned must not touch the registry"


def test_a_repinned_engines_exact_tag_must_resolve(monkeypatch):
    """A repinned engine's exact content-address tag is looked up; a 404 reds with the ref named."""
    engine, variant = "mlx", "cpu"
    monkeypatch.setattr(cpp, "repinned_engine_ids", lambda base, root=None: [engine])
    tag = ei.resolve(engine, None, variant)["tag"]
    ref = f"{REGISTRY}/{tag}"
    fake, calls = _fake_digest({ref: ""})     # 404 for the exact tag
    rc = cpp.check(_head(), digest=fake, registry=REGISTRY)
    assert rc == 1
    assert ref in calls, f"the exact tag {ref} must be looked up"


def test_green_only_when_the_exact_tag_resolves(monkeypatch):
    """Once the same tag resolves, the identical check is green."""
    engine = "mlx"
    monkeypatch.setattr(cpp, "repinned_engine_ids", lambda base, root=None: [engine])
    # mlx declares cuda + cpu — every non-disabled variant must resolve for green
    import json as _json
    params = _json.loads(
        (REPO / "containers" / "engines" / "params" / f"{engine}.json").read_text())
    variants = [v for v in params["variants"] if not ei.disabled(engine, v)]
    resolve_map = {}
    for v in variants:
        ref = f"{REGISTRY}/{ei.resolve(engine, None, v)['tag']}"
        resolve_map[ref] = "sha256:" + "0" * 64
    fake, calls = _fake_digest(resolve_map)
    rc = cpp.check(_head(), digest=fake, registry=REGISTRY)
    assert rc == 0
    assert len(calls) == len(variants), f"every variant queried, got {calls}"


def test_every_variant_of_a_repinned_engine_must_resolve(monkeypatch):
    """A repinned engine's whole published set reds if ANY variant is absent, not just cpu."""
    engine = "llama.cpp"
    monkeypatch.setattr(cpp, "repinned_engine_ids", lambda base, root=None: [engine])
    # resolve every non-disabled variant the committed params declare
    import json as _json
    params = _json.loads(
        (REPO / "containers" / "engines" / "params" / f"{engine}.json").read_text())
    variants = [v for v in params["variants"] if not ei.disabled(engine, v)]
    assert len(variants) >= 2, f"{engine} should declare more than one buildable variant"
    resolve_map = {}
    for v in variants:
        ref = f"{REGISTRY}/{ei.resolve(engine, None, v)['tag']}"
        # all but the LAST variant resolve; the last 404s -> the gate must red
        resolve_map[ref] = "sha256:" + "0" * 64
    last_ref = f"{REGISTRY}/{ei.resolve(engine, None, variants[-1])['tag']}"
    resolve_map[last_ref] = ""
    fake, calls = _fake_digest(resolve_map)
    rc = cpp.check(_head(), digest=fake, registry=REGISTRY)
    assert rc == 1, "an unresolved variant of a repinned engine must red the PR"
    assert last_ref in calls
    # and every variant was checked, not just cpu
    assert len(calls) == len(variants), f"looked up {calls}, expected one per variant"


def test_the_real_diff_detects_a_repin_and_checks_the_registry():
    """Live: with the tree at its own base (nothing repinned) the gate is green and
    probes nothing beyond the diff. A params file that differs from the base is named.
    Genuinely runs (no skip) exactly as the live registry tests of
    tests/test_ci_publish_order.py do — CI is always a full clone, so git resolves."""
    engine = "mlx"
    base = _head()
    assert base, f"git must resolve the base (full clone): got {base!r}"
    orig = (REPO / "containers" / "engines" / "params" / f"{engine}.json").read_text()
    ids = cpp.repinned_engine_ids(base)
    assert engine not in ids, f"{engine} should be at its base pin (repinned: {ids})"
    assert not ids, f"a clean branch repins nothing, got {ids}"
    assert (REPO / "containers" / "engines" / "params" / f"{engine}.json").read_text() == orig


# --- Tag identity is the unit of a repin (issue #2559) ------------------------------------------
# The merged retag of #2517: 36 Dockerfiles changed, no params file touched, both repin consumers
# saw an empty diff, and 28 committed tags merged unpublished. These fixtures replay that shape
# with a real git tree holding one engine `demo` — the full input set the tag digest hashes.
# Git-only: nothing here touches the registry.


def _fixture(tmp_path, base_text: str | None = None) -> str:
    """A committed git tree: engine `demo` x cpu with the params, Dockerfile, entrypoint and
    runner bytes the published tag hashes. Returns the base commit sha."""
    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)
    params = {"id": "demo", "pinned": "cafe1234deadbeef", "variants": {"cpu": {"model": "m1"}}}
    (tmp_path / "containers" / "engines" / "params").mkdir(parents=True)
    (tmp_path / "containers" / "engines" / "params" / "demo.json").write_text(
        base_text if base_text is not None else json.dumps(params) + "\n")
    (tmp_path / "containers" / "engines" / "dockerfiles" / "demo").mkdir(parents=True)
    (tmp_path / "containers" / "engines" / "dockerfiles" / "demo" / "Dockerfile.cpu").write_text(
        "FROM base\nUSER 1000\n")
    (tmp_path / "containers" / "engines" / "entrypoint.sh").write_text("#!/bin/sh\nexec launch\n")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/engine_runner.py").write_text("# runner\n")
    git("init", "-q")
    git("config", "user.email", "gate@example.com")
    git("config", "user.name", "gate")
    git("add", "-A")
    git("commit", "-qm", "base")
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path,
                          capture_output=True, text=True).stdout.strip()


def _commit_against(tmp_path, rel: str, content: str, msg: str) -> None:
    (tmp_path / rel).write_text(content)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", msg], cwd=tmp_path, check=True, capture_output=True)


def test_a_dockerfile_only_change_is_detected_as_a_repin(tmp_path):
    """The #2517 shape, on a fixture: params byte-identical to the base, only Dockerfile.cpu
    moved — the tag digest differs, so the tag-identity diff names it and the union names it."""
    base = _fixture(tmp_path)
    _commit_against(tmp_path, "containers/engines/dockerfiles/demo/Dockerfile.cpu",
                    "FROM base\nUSER 1001\n", "dockerfile-only retag")
    assert cpp.retagged_engine_ids(base, tmp_path) == ["demo"]
    assert cpp.repinned_engine_ids(base, tmp_path) == ["demo"]


def test_a_params_text_diff_is_still_named_even_with_an_unchanged_tag(tmp_path):
    """The #1622 behaviour is never loosened: a params file whose TEXT differs from the base is
    named even when the variant bytes the tag hashes are unchanged — only the file's trailing
    newline moved, so the tag stayed put."""
    base = _fixture(tmp_path)
    _commit_against(tmp_path, "containers/engines/params/demo.json",
                    json.dumps({"id": "demo", "pinned": "cafe1234deadbeef",
                                "variants": {"cpu": {"model": "m1"}}}),
                    "whitespace-only params edit")
    assert cpp.retagged_engine_ids(base, tmp_path) == []
    assert cpp.repinned_engine_ids(base, tmp_path) == ["demo"]


def test_a_tree_equal_to_its_base_repins_and_probes_nothing(tmp_path):
    """The hermetic gate rule survives the union: a branch identical to its base names nothing,
    so the gate would probe nothing beyond the empty diff."""
    base = _fixture(tmp_path)
    assert cpp.retagged_engine_ids(base, tmp_path) == []
    assert cpp.repinned_engine_ids(base, tmp_path) == []


def test_a_first_import_counts_immediately(tmp_path):
    """An engine with no params copy at the base never had a published image: both diffs count
    it from its first commit, and the engine that stayed put is not named."""
    base = _fixture(tmp_path)
    params = json.dumps({"id": "second", "pinned": "feed5678cafe0000", "variants": {"cpu": {}}})
    (tmp_path / "containers" / "engines" / "params" / "second.json").write_text(params + "\n")
    (tmp_path / "containers" / "engines" / "dockerfiles" / "second").mkdir(parents=True)
    (tmp_path / "containers" / "engines" / "dockerfiles" / "second" / "Dockerfile.cpu").write_text(
        "FROM base\nUSER 1000\n")
    _commit_against(tmp_path, "IMPORTS.md", "second engine imported\n", "import second engine")
    ids = cpp.retagged_engine_ids(base, tmp_path)
    assert ids == ["second"]
    assert cpp.repinned_engine_ids(base, tmp_path) == ["second"]


def test_the_gate_is_wired_into_ci_unit_and_phony():
    """The gate runs in the PR pipeline (ci-unit) and is .PHONY, else it is a defect."""
    mk = (REPO / "Makefile").read_text()
    assert "$(MAKE) check-engine-pins-published" in mk, "ci-unit must run the gate"
    # .PHONY spans backslash-continuation lines (issue #883): read the whole block
    phony = re.search(r"^\.PHONY:.*?^\S", mk, re.MULTILINE | re.DOTALL)
    assert phony and re.search(r"\bcheck-engine-pins-published\b", phony.group(0)), \
        "check-engine-pins-published is not .PHONY"
    assert re.search(r"\bengine-pins-published-report\b", phony.group(0)), \
        "engine-pins-published-report is not .PHONY"
    target = re.search(r"^check-engine-pins-published:.*(?=^\S)", mk, re.MULTILINE | re.DOTALL)
    assert target and "python3 scripts/check_engine_pins_published.py check" in target.group(0)
    assert target and "--base" in target.group(0), "the gate must diff against the base"


# --- committed-set pin-validity guard (issue #2190) --------------------------
# The repin diff (above) catches an engine a PR moves. The committed-set sweep
# catches the recurring publish-gap where a bumped pin's image was NEVER rebuilt:
# tensorfold/cuda at b392ffce sat committed on main with no PR re-pinning it, so
# the repin-only gate never fired while `ghcr.io/.../tensorfold:b392ffce-*` 404'd.
# check_committed sweeps the FULL params matrix (every enabled cell, all backends).

COMPANY_REGISTRY = "ghcr.io/example/llgenie"


def test_committed_red_when_a_committed_tag_is_absent(monkeypatch):
    """`check --all`: a committed cell whose exact tag resolves no manifest reds."""
    # tensorfold/cuda declares a cuda cell; its exact tag must exist for a fresh install
    engine, variant = "tensorfold", "cuda"
    params = json.loads(
        (REPO / "containers" / "engines" / "params" / f"{engine}.json").read_text())
    assert variant in params["variants"], f"{engine} must declare a {variant} cell"
    tag = ei.resolve(engine, None, variant)["tag"]
    ref = f"{COMPANY_REGISTRY}/{tag}"
    fake, calls = _fake_digest({ref: ""})     # the exact committed tag 404s
    rc = cpp.check_committed(digest=fake, registry=COMPANY_REGISTRY,
                             cells=[(engine, variant)])
    assert rc == 1, "a committed cell with no published image must red the sweep"
    assert ref in calls, f"the committed tag {ref} must be looked up"


def test_committed_green_when_the_same_committed_tag_resolves(monkeypatch):
    """The identical committed cell is GREEN once its exact tag resolves the registry."""
    engine, variant = "tensorfold", "cuda"
    tag = ei.resolve(engine, None, variant)["tag"]
    ref = f"{COMPANY_REGISTRY}/{tag}"
    fake, calls = _fake_digest({ref: "sha256:" + "0" * 64})
    rc = cpp.check_committed(digest=fake, registry=COMPANY_REGISTRY,
                             cells=[(engine, variant)])
    assert rc == 0, "a committed cell whose image IS published must pass"
    assert ref in calls


def test_committed_sweeps_every_non_disabled_cell(monkeypatch):
    """The sweep enumerates every committed (engine, variant) cell the matrix builds."""
    cells = cpp.committed_cells()
    assert cells, "the committed params matrix must declare at least one cell"
    assert ("sglang", "rocm") in cells, "committed_cells must include all-backend cells"
    for engine, variant in cells:
        params = json.loads(
            (REPO / "containers" / "engines" / "params" / f"{engine}.json").read_text())
        assert variant in params["variants"]
        assert not ei.disabled(engine, variant), \
            f"committed_cells must skip disabled cells, got ({engine}, {variant})"


def test_committed_wired_into_make_and_phony():
    """The committed-set sweep has its own runnable make target and is .PHONY."""
    mk = (REPO / "Makefile").read_text()
    target = re.search(r"^check-engine-pins-valid:.*(?=^\S)", mk, re.MULTILINE | re.DOTALL)
    assert target and "check --all" in target.group(0), \
        "check-engine-pins-valid must invoke the committed-set sweep"
    phony = re.search(r"^\.PHONY:.*?^\S", mk, re.MULTILINE | re.DOTALL)
    assert phony and re.search(r"\bcheck-engine-pins-valid\b", phony.group(0)), \
        "check-engine-pins-valid is not .PHONY"


@pytest.mark.network
def test_every_committed_engine_cell_tag_is_published_live():
    """Real GHCR (ci-network, issue #1000): every committed enabled engine cell's
    exact tag resolves a manifest. Reds the class #2190 caught — a committed pin
    whose image was never rebuilt. Runs live because the answer depends on what
    CI actually published, never a committed snapshot."""
    rc = cpp.check_committed()
    assert rc == 0, "every committed engine cell's published image must resolve a manifest"



def test_the_liveness_workflow_hard_fails_on_a_committed_manifest_unknown():
    """The registry-liveness scheduled gate must FAIL (exit the gate's rc), not exit 0 and
    file issues (the #2190 silent-recurrence: tensorfold/cuda printed NOT PUBLISHED but the
    run concluded success and the fuzzy dedup filed nothing, so no one saw it). ALL=1's
    exit is the job's exit, and the issue-filer runs after regardless."""
    from pathlib import Path as _P
    wf = (_P(__file__).resolve().parents[1] / ".github/workflows/registry-liveness.yml").read_text()
    assert "check-engine-pins-published ALL=1" in wf, "the fleet gate must run ALL=1"
    assert 'exit "$rc"' in wf and "fleet_rc=" in wf, "the fleet gate's rc must fail the job"
    assert 'id: fleet' in wf and 'if: always()' in wf, "the issue-filer must still run after a red gate"
    assert 'check-engine-launchers CHECK_REGISTRY=1 ARCH=all' in wf, \
        "the #1652 per-backend sweep must still run (ARCH=all)"
    assert '--search "\\\"$tag\\\""' in wf or '--search "$tag"' in wf, \
        "the issue-filer dedup must match the exact tag, not a fuzzy engine search"


def test_the_liveness_workflow_dispatches_the_publish_not_just_names_it():
    """Issue #2259: the gate must CAUSE the producer to publish a missing committed tag, not
    just file an issue and stay red. The dispatch step runs after the ALL=1 check (always, so a
    red fleet gate still fires it), names engine+arch from the NOT PUBLISHED tag, and calls
    `engine-build` with `push=true`. This is the live-proof piece: a repin that the sweep aborted
    on is now self-dispatched instead of 404-red for five days."""
    from pathlib import Path as _P
    wf = (_P(__file__).resolve().parents[1] / ".github/workflows/registry-liveness.yml").read_text()
    assert "dispatch engine-build push=true" in wf, "the gate must have a dispatch step"
    # The dispatch parses engine+arch from the NOT PUBLISHED tag and needed the repo's dispatch
    # right (`actions: write`), which must be granted or `gh workflow run` cannot start the producer.
    assert "actions: write" in wf, "the dispatch step needs actions:write to run gh workflow run"
    assert "workflow run engine-build.yml" in wf, "the dispatch must start the engine-build producer"
    assert "-f push=true" in wf or "--field push=true" in wf, "the dispatch must publish (push=true)"
    # Issue #2561: the dispatch takes engine+arch ONLY from the gate's `[select]`
    # contract lines (committed ids, dots intact). The old parse cut the engine out of
    # the ghcr package URL, where dots are illegally replaced by dashes — llama.cpp
    # arrived as `llama-cpp` and nine runs published nothing while reporting success.
    assert "[select]" in wf, "the dispatch must consume the [select] contract lines"
    assert "missing-tags.txt" not in wf and "cut -d: -f1" not in wf, \
        "the dispatch must not reverse-parse an engine id from a ghcr package URL"
    # Keep the ALL=1 hard-fail: the dispatch step may not weaken or bypass the fleet gate's exit.
    assert 'exit "$rc"' in wf, "ALL=1 hard-fail must be untouched by the dispatch wiring"


def test_the_dispatch_read_loop_binds_the_select_contract_positionally():
    """Issue #2567: the gate prints FOUR-token contract lines "[select] <engine> <variant>
    <tag-suffix>" (the format test above locks the gate side), but the dispatch loop read
    THREE variables from them, so every field shifted one slot right: $engine was the
    literal "[select]", $variant the engine id, $tag the variant+suffix. All 22 dispatches
    made on e6b9b4b4f (runs 43187181181..43187252711) therefore started engine-build with
    engine="[select]" — no committed params id matched, the matrix synthesized its none/none
    placeholder, and the runs "succeeded" publishing nothing (same class as the nine runs on
    aa700cf27, #2561). The read loop must bind the marker in its OWN field and reject a
    line that violates the contract loudly, never dispatch it.
    """
    from pathlib import Path as _P
    wf = (_P(__file__).resolve().parents[1] / ".github/workflows/registry-liveness.yml").read_text()
    lines = wf.splitlines()
    ends = [i for i, ln in enumerate(lines) if ln.strip() == "done < select.txt"]
    assert len(ends) == 1, f"select.txt must be consumed by exactly one loop, found {len(ends)}"
    starts = [i for i, ln in enumerate(lines[: ends[0]]) if "while read -r " in ln]
    assert starts, "the dispatch loop must read select.txt with named fields"
    fields = lines[starts[-1]].split("while read -r ", 1)[1].split(";")[0].split()
    assert fields[:4] == ["sel", "engine", "variant", "tag"], (
        f"the loop binds {fields}; the contract line has four tokens and $engine must be "
        "the committed engine id, never the literal '[select]'"
    )
    assert '"$sel" != "[select]"' in wf, "a line whose first token is not [select] must be refused, not dispatched"
    assert "UNRECOGNIZED select line" in wf, "a refused line must be printed, not swallowed"
    assert "bad_line" in wf and "malformed dispatch refused" in wf, \
        "a refused line must fail the step after the loop, not just print"
    assert '-f engine="$engine"' in wf and '-f arch="$variant"' in wf, \
        "engine/arch must be passed from the named contract fields"


def test_the_dispatch_coalesces_a_multi_cell_wave_into_one_sweep():
    """Issue #2579: per-cell dispatches are a WAVE. On 2026-11-12 eight one-cell runs
    queued at 1s intervals in the single engine-build-push concurrency group
    (43211663538..43211688780), each holding a group slot and a runner for its whole
    wait while the sweep already running starved — the same mechanism that killed
    43203422414 (#2570), repeated as 663/664 and 666-671 pairs after every main merge.
    The consumer must coalesce: MORE than one contract-valid [select] cell dispatches
    exactly ONE full-matrix sweep (engine-build's documented empty-input sweep,
    push=true; fleet #645 published 27 cells that way); EXACTLY ONE missing cell keeps
    the #2567 named-field per-cell dispatch. Contract validation runs before either
    shape, so a malformed gate report dispatches nothing, sweep included.
    """
    import re as _re
    from pathlib import Path as _P
    wf = (_P(__file__).resolve().parents[1] / ".github/workflows/registry-liveness.yml").read_text()
    assert "coalescing" in wf and "push=true sweep (#2579)" in wf, \
        "the multi-cell path must announce the coalesced sweep"
    assert 'n=$(wc -l < validated.txt)' in wf and '[ "$n" -gt 1 ]' in wf, \
        "the dispatch shape must be chosen from the validated [select] line count"
    sweep = _re.search(r'gh workflow run engine-build\.yml --repo "\$REPO" --ref main -f push=true', wf)
    assert sweep, "the multi-cell path must dispatch ONE sweep with push=true and no engine/arch fields"
    assert '-f engine="$engine"' in wf and '-f arch="$variant"' in wf, \
        "the exactly-one-cell path must keep the #2567 per-cell named-field dispatch"
    assert 'elif [ "$n" = "1" ]' in wf, "per-cell dispatch is the single-cell branch only"
    assert wf.index("malformed dispatch refused") < wf.index("wc -l < validated.txt"), \
        "contract validation must complete before either dispatch shape is chosen"
    assert wf.count('gh workflow run engine-build.yml') == 2, \
        "exactly two dispatch shapes: the sweep and the single-cell dispatch"


def test_the_gate_names_every_missing_cell_with_a_canonical_select_line(capsys):
    """Issue #2561: the gate's own machine-readable line is `[select] <engine-id>
    <variant> <tag-suffix>` with the COMMITTED id — dots intact. The registry-liveness
    dispatch used to reverse-parse ids out of ghcr package URLs, where dots are
    legally replaced by dashes, and dispatched `llama-cpp` for `llama.cpp`: matrix
    matched nothing, synthesized none/none, and nine runs "succeeded" publishing
    nothing (runs 43149732453…43149757005 on aa700cf27). The selection line is now
    the contract, and it may never carry the package spelling.

    Hermetic: the digest probe is a 404 stub — the ids/variants come from the real
    committed params (llama.cpp exists with dotted id), the registry is stubbed.
    """
    engine = "llama.cpp"
    rc = cpp.check_committed(
        digest=lambda ref: ("", "404 Not Found"), registry=REGISTRY,
        cells=[(engine, v) for v in cpp._enabled_variants(engine)])
    assert rc == 1
    out = capsys.readouterr().out
    select = [ln.split() for ln in out.splitlines() if ln.startswith("[select]")]
    assert select, "a red fleet gate must name every cell with a [select] line"
    assert {parts[1] for parts in select} == {engine}, \
        "the select line carries the committed engine id, dots intact"
    assert not any("llama-cpp" in parts[1] for parts in select), \
        "the package spelling must never appear as an engine id"
    variants = {parts[2] for parts in select}
    assert variants == set(cpp._enabled_variants(engine))
    for parts in select:
        assert len(parts) == 4 and re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{8}-[a-z]+", parts[3]), \
            f"[select] line names the committed tag suffix: {parts}"


def test_a_published_cell_names_no_select_line(capsys):
    """Green gate: PUBLISHED lines print, no [select] selection is made."""
    rc = cpp.check_committed(
        digest=lambda ref: ("sha256:deadbeef", ""), registry=REGISTRY,
        cells=[("llama.cpp", "cpu")])
    assert rc == 0
    out = capsys.readouterr().out
    assert "[select]" not in out

