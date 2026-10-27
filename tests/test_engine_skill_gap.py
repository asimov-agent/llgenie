"""The unskilled-engine gap (issue #229): which registry engines llgenie cannot
serve, why, and which models that hides.

The business logic runs for real — the REAL vendored registry, the REAL skills, the
REAL dated decisions, the REAL `rank_engines` ranking and the REAL `matrix()`
permutation grid. The two stand-ins AGENTS.md allows are used:

- **the GitHub API**: a `gh` on PATH that records its argv and answers `issue list`
  / `issue create`, so the test asserts the exact request the product builds
  (`tests/test_ci_images.py` does the same for `docker`);
- **the architecture / RAM / VRAM grid**: the permutation cases drive
  `matrix()` through its real code path; only the engine registry (which images
  exist) and the Hub tree are stubbed, the way the other permutation tests do it.

Nothing here replaces the product: `gap()`, `check()`, `spawn()`, `validate()`,
`matrix()` and `rank_engines()` are the code under test.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import engine_skill_gap as gap_mod  # noqa: E402
import issue_body  # noqa: E402  (the one issue shape, issue #745)
import engine_skills as es  # noqa: E402
import model_engine_pick as mp  # noqa: E402
import unit_tests as ut  # noqa: E402  (the unit-suite aggregator, issue #393)

REGISTRY = REPO / "data" / "models.json"
MANIFEST = REPO / "data" / "unsupported-engines.json"
RENDERED = REPO / "data" / "engine-skill-gap.json"
WORKFLOW = REPO / ".github" / "workflows" / "registry-sync.yml"
GB = 2**30


def _run(*args: str, env=None, timeout=120) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(REPO / "scripts" / "engine_skill_gap.py"), *args],
                          capture_output=True, text=True, timeout=timeout, env=env)


def _registry(engines: dict, models: list) -> dict:
    return {"generated_utc": "2026-10-14T00:00:00Z", "engines": engines, "models": models}


def _model(id_, name, vram, hf, engine_names: list, tps=120):
    return {"id": id_, "name": name, "type": "LLM", "params": name.split()[0], "hf": hf,
            "vram_tier": vram, "formats": [{"name": "GGUF", "hf": hf}],
            "engines": [{"engine": e, "tps": str(tps), "hardware": "RTX 4090"} for e in engine_names],
            "supported_engines": engine_names,
            "last_seen": "2026-10-14", "engagement": {"trend_score": 1.0, "posts_7d": 1}}


def _write(path: Path, data) -> Path:
    path.write_text(json.dumps(data, indent=2) + "\n")
    return path


# ---------------------------------------------------------------------------
# the real files: every registry engine has a status, and the gap is committed
# ---------------------------------------------------------------------------
def test_every_registry_engine_has_a_status_and_the_rendered_gap_is_current():
    """The real registry, skills and dated decisions account for every engine, and the
    committed data/engine-skill-gap.json is exactly what the generator produces."""

    # Given the vendored registry, the skills llgenie ships and the dated decisions
    registry, skills, unsupported = gap_mod.inventories()

    # When the gap is computed
    g = gap_mod.gap(registry, skills, unsupported)

    # Then every registry engine has a status, and the shipped set is the skills' engines
    assert set(g["engines"]) == set(registry["engines"])
    assert g["shipped"] == sorted({s.get("engine") for s in skills.values()})
    assert {e["engine"] for e in g["known_unsupported"]} | set(g["unresolved"]) == \
        set(registry["engines"]) - set(g["shipped"])
    for name, entry in g["engines"].items():
        assert entry["status"] in ("shipped", "known-unsupported", "unresolved"), name
        assert set(entry["top_engine"]) == set(gap_mod.ARCHS), name
        assert isinstance(entry["models"], list), name
        assert isinstance(entry["variants"], list), name
        assert entry["image"] == bool(entry["variants"]), name
        if entry["status"] != "shipped":
            assert entry["variants"] == [], name
    # And a skill that ships no image (a drafter, a browser library) is named as such,
    # because rank_engines drops it exactly like an engine with no skill
    assert set(g["imageless_skills"]) <= set(g["shipped"])
    assert all(not g["engines"][n]["image"] for n in g["imageless_skills"])

    # And every known-unsupported engine carries a dated, reasoned decision
    for e in g["known_unsupported"]:
        assert e["decision"] in ("not-shipped", "deferred"), e
        assert e["decided"], e
        assert len(e["reason"]) > 20, e

    # And the committed file is not stale — a sync that forgets the rewrite fails CI
    assert json.loads(RENDERED.read_text()) == g


def test_the_real_files_are_current_and_the_gate_agrees_with_the_gap():
    """`make check-engine-skill-gap` is this command. It must express the real state:
    exit 0 when every unshipped engine is a dated decision, exit 1 naming the engine
    when one is new and unresolved — never the opposite. That agreement is what lets
    the weekly sync keep carrying the data (#219) while the PR's ci-unit goes red."""

    # Given the vendored registry, its skills and the dated decisions
    registry, skills, unsupported = gap_mod.inventories()
    g = gap_mod.gap(registry, skills, unsupported)

    # When the gate runs on exactly those files
    r = _run("check")

    # Then its exit code is exactly "are there unresolved engines", and it names them
    assert r.returncode == (1 if g["unresolved"] else 0), (r.returncode, r.stdout, r.stderr)
    for name in g["unresolved"]:
        assert name in r.stderr and "new and unresolved" in r.stderr
    if not g["unresolved"]:
        assert "unresolved 0" in r.stdout


def test_report_names_the_models_that_can_never_be_offered_and_the_per_engine_list():
    """The report enumerates the models only unsupported engines serve, so no model
    vanishes silently, and the per-engine (inference server) view is in the artifact."""

    # Given the real gap
    registry, skills, unsupported = gap_mod.inventories()
    g = gap_mod.gap(registry, skills, unsupported)

    # When the report is rendered as markdown (what the sync PR body carries)
    md = gap_mod.markdown(g)

    # Then it states the shipped/known/unresolved counts and the per-engine file
    assert f"**{len(g['shipped'])}** of **{g['registry_engines']}**" in md
    assert "data/engine-skill-gap.json" in md
    assert "new and unresolved" in md

    # And a model whose only engine is unskilled is named, not dropped
    only = _registry({"llama.cpp": {"backend": "CUDA", "url": "https://example.invalid"},
                      "MegaCapybara": {"backend": "CUDA", "url": "https://example.invalid"}},
                     [_model("ok-8b", "Ok 8B", "8GB", "Org/Ok-8B-GGUF", ["llama.cpp"]),
                      _model("lost-3b", "Lost 3B", "8GB", "Org/Lost-3B-GGUF", ["MegaCapybara"])])
    g2 = gap_mod.gap(only, skills, {"path": str(MANIFEST), "engines": {}})
    assert [m["id"] for m in g2["models_never_offered"]] == ["lost-3b"]
    assert "`lost-3b`" in gap_mod.markdown(g2)
    assert "UNRESOLVED: MegaCapybara" in gap_mod.text(g2)
    assert "model no engine can offer: Lost 3B (lost-3b)" in gap_mod.text(g2)

    # And a model that merely also lists an unskilled engine is reported as such
    both = _registry({"llama.cpp": {"backend": "CUDA", "url": "https://example.invalid"},
                      "MegaCapybara": {"backend": "CUDA", "url": "https://example.invalid"}},
                     [_model("ok-8b", "Ok 8B", "8GB", "Org/Ok-8B-GGUF", ["llama.cpp", "MegaCapybara"])])
    g3 = gap_mod.gap(both, skills, unsupported)
    assert g3["models_never_offered"] == []
    assert g3["models_touching_unsupported"] == [
        {"id": "ok-8b", "name": "Ok 8B", "engines": ["MegaCapybara", "llama.cpp"],
         "unsupported": ["MegaCapybara"]}]


# ---------------------------------------------------------------------------
# the gate: a new unskilled engine is loud, a dated decision silences it
# ---------------------------------------------------------------------------
def test_a_new_unskilled_engine_fails_the_gate_and_a_dated_decision_silences_it(tmp_path):
    """'no skill and nobody decided' is unresolved; 'no skill but recorded' is deliberate."""

    # Given the real registry with one engine no skill covers and no decision records
    registry, skills, unsupported = gap_mod.inventories()
    new = json.loads(REGISTRY.read_text())
    new["engines"]["BrandNewServer"] = {"backend": "CUDA", "url": "https://example.invalid/new"}
    reg_file = _write(tmp_path / "models.json", new)
    manifest = _write(tmp_path / "unsupported-engines.json", unsupported)
    rendered = tmp_path / "gap.json"

    # When the gate runs before any decision is recorded
    r = _run("check", "--registry", str(reg_file), "--unsupported", str(manifest),
             "--rendered", str(rendered))

    # Then it exits 1 and names the engine
    assert r.returncode == 1, r.stdout
    assert "BrandNewServer" in r.stderr and "new and unresolved" in r.stderr

    # And the report (the sync job's step, which must stay green) calls it unresolved
    rep = _run("report", "--registry", str(reg_file), "--unsupported", str(manifest))
    assert rep.returncode == 0, rep.stderr
    assert "UNRESOLVED: BrandNewServer" in rep.stdout

    # And the validate gate (make skills-validate with the manifest) names it too
    assert any("BrandNewServer" in e and "no dated decision" in e
               for e in es.validate(skills, new["engines"], unsupported))

    # When a dated decision is recorded and the artifact re-rendered
    decisions = dict(unsupported["engines"])
    decisions["BrandNewServer"] = {"decision": "deferred", "decided": "2026-10-14",
                                   "reason": "real OpenAI server, no llgenie skill yet",
                                   "issue": 229}
    _write(manifest, {"note": unsupported.get("note", ""), "engines": decisions})
    assert _run("render", "--registry", str(reg_file), "--unsupported", str(manifest),
                "--rendered", str(rendered)).returncode == 0

    # Then the gate passes, the engine is 'known-unsupported', and validate tolerates it
    ok = _run("check", "--registry", str(reg_file), "--unsupported", str(manifest),
              "--rendered", str(rendered))
    assert ok.returncode == 0, ok.stderr
    g = json.loads(rendered.read_text())
    assert g["unresolved"] == [] and g["engines"]["BrandNewServer"]["status"] == "known-unsupported"
    assert es.validate(skills, new["engines"], {"path": str(manifest), "engines": decisions}) == []


def test_a_decision_for_an_engine_that_ships_a_skill_is_stale(tmp_path):
    """A decision entry outlives its usefulness: it must be deleted, loudly."""

    # Given a decision recorded for an engine that already has a skill
    registry, skills, unsupported = gap_mod.inventories()
    shipped_name = gap_mod.gap(registry, skills, unsupported)["shipped"][0]
    decisions = {shipped_name: {"decision": "not-shipped", "decided": "2026-10-14",
                                "reason": "leftover decision for an engine llgenie ships"}}
    manifest = _write(tmp_path / "unsupported-engines.json", {"engines": decisions})
    rendered = tmp_path / "gap.json"
    _run("render", "--unsupported", str(manifest), "--rendered", str(rendered))

    # When the gate runs
    r = _run("check", "--unsupported", str(manifest), "--rendered", str(rendered))

    # Then it fails, naming the entry as stale
    assert r.returncode == 1
    assert "stale" in r.stderr and shipped_name in r.stderr


def test_a_malformed_decision_is_a_loud_failure_never_a_silent_pass(tmp_path):
    """Every decision needs decision + decided + reason; a gap that is not accounted
    for must never validate silently."""

    # Given a decision entry with no reason and one with an unknown decision
    for bad in ({"decision": "deferred", "decided": "2026-10-14"},
                {"decision": "maybe", "decided": "2026-10-14", "reason": "unclear decision value"}):
        manifest = _write(tmp_path / "unsupported-engines.json", {"engines": {"X": bad}})

        # When the manifest is loaded
        with pytest.raises(SystemExit) as exc:
            es.load_unsupported(manifest)

        # Then it raises naming the entry, rather than tolerating the engine
        assert "X" in str(exc.value)


def test_the_october_fixture_registry_validates_with_the_real_decisions():
    """The pinned fixture (16 engines, all covered by skills) stays 0 errors with the
    manifest, and the strict run (no manifest) is still an error for an engine with no
    skill at all: the manifest tolerates a DECISION, never a missing skill quietly."""

    # Given the pinned October registry and the real dated decisions
    before = REPO / "tests" / "fixtures" / "registry-before" / "models.json"
    skills = es.load_skills()

    # When it is validated with and without the manifest
    # Then the manifest form accepts the covered fixture, and strict still names an
    # engine with no skill at all
    engines = json.loads(before.read_text())["engines"]
    assert es.validate(skills, engines, es.load_unsupported(MANIFEST)) == []
    extra = {**engines, "NothingShipsThis": {"backend": "CUDA", "url": "https://example.invalid"}}
    assert any("has no skill" in e for e in es.validate(skills, extra))


# ---------------------------------------------------------------------------
# the visible artifact: one tracking issue per unresolved engine
# ---------------------------------------------------------------------------
def _fake_gh(tmp_path: Path, open_issues: list | None = None, create_fails: bool = False):
    """`gh` that records every argv as ONE JSON line and answers `issue list` with
    `open_issues` and `issue create` with a URL. It is a real executable the product
    starts as a subprocess — only the GitHub API is a stand-in, never the request the
    product builds (`tests/test_ci_images.py` does the same for `docker`)."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    log = tmp_path / "gh.log"
    listing = tmp_path / "open.json"
    listing.write_text(json.dumps(open_issues or []))
    counter = tmp_path / "n"
    counter.write_text("500")
    gh = tmp_path / "gh"
    gh.write_text(f'''#!{sys.executable}
import json, sys, pathlib
args = sys.argv[1:]
with open({str(log)!r}, "a") as fh:
    fh.write(json.dumps(args) + "\\n")
if args[:2] == ["issue", "list"]:
    sys.stdout.write(pathlib.Path({str(listing)!r}).read_text())
elif args[:2] == ["issue", "create"]:
    if {bool(create_fails)!r}:
        print("boom: 403", file=sys.stderr)
        raise SystemExit(1)
    n = int(pathlib.Path({str(counter)!r}).read_text()) + 1
    pathlib.Path({str(counter)!r}).write_text(str(n))
    print(f"https://github.com/acme/llgenie/issues/{{n}}")
''')
    gh.chmod(0o755)
    return gh, log


def _calls(log: Path) -> list[list[str]]:
    """The argv of every gh invocation the product made."""
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def test_spawn_opens_one_issue_per_unresolved_engine_with_real_evidence(tmp_path):
    """A sync that carries a new engine leaves a visible, linkable work item."""

    # Given a registry with one engine no skill covers and no decision records,
    # and a gh that has no open tracking issue yet
    registry, skills, unsupported = gap_mod.inventories()
    new = json.loads(REGISTRY.read_text())
    new["engines"]["BrandNewServer"] = {"backend": "CUDA", "url": "https://example.invalid/new",
                                        "note": "auto-registered from a thread"}
    new["models"].append(_model("new-7b", "New 7B", "8GB", "Org/New-7B-GGUF", ["BrandNewServer"]))
    reg_file = _write(tmp_path / "models.json", new)
    manifest = _write(tmp_path / "unsupported-engines.json", unsupported)
    gh, log = _fake_gh(tmp_path)

    # When spawn runs
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "engine_skill_gap.py"), "spawn",
                        "--registry", str(reg_file), "--unsupported", str(manifest),
                        "--repo", "acme/llgenie", "--gh", str(gh)],
                       capture_output=True, text=True, timeout=120)

    # Then it creates exactly one issue, for the unresolved engine, and says so
    assert r.returncode == 0, r.stderr
    creates = [c for c in _calls(log) if c[:2] == ["issue", "create"]]
    assert len(creates) == 1, _calls(log)
    args = creates[0]
    assert args[args.index("--repo") + 1] == "acme/llgenie"
    title = args[args.index("--title") + 1]
    body = args[args.index("--body") + 1]
    assert "BrandNewServer" in title and "has no llgenie skill" in title
    # And the body carries the evidence a reviewer needs
    assert "https://example.invalid/new" in body
    assert "CUDA" in body and "auto-registered from a thread" in body
    assert "`new-7b`" in body          # a model that lists it
    assert "new-7b" in body.split("ONLY engines are unskilled")[1]  # and it is the only one
    assert "#229" in body
    # And the body is the repository's issue shape: what/why/how/benefit before the evidence
    assert issue_body.missing(body) == [], issue_body.missing(body)
    assert issue_body.headings(body)[-1] == "Technical"
    assert "created" in r.stdout

    # And the listing call searched for the exact issue title
    lists = [c for c in _calls(log) if c[:2] == ["issue", "list"]]
    assert lists and any(f'in:title "{title}"' in c for c in lists)

    # And no issue is opened for a shipped engine
    assert not any("llama.cpp" in " ".join(c) for c in creates)


def test_spawn_is_idempotent_and_creates_nothing_for_a_decided_engine(tmp_path):
    """Running twice does not open a second issue, and a dated decision creates none."""

    # Given the real registry with a dated decision for its one new engine
    registry, skills, unsupported = gap_mod.inventories()
    new = json.loads(REGISTRY.read_text())
    new["engines"]["BrandNewServer"] = {"backend": "CUDA", "url": "https://example.invalid/new"}
    decisions = dict(unsupported["engines"])
    decisions["BrandNewServer"] = {"decision": "not-shipped", "decided": "2026-10-14",
                                   "reason": "deliberately not shipped: benchmark harness only"}
    reg_file = _write(tmp_path / "models.json", new)
    manifest = _write(tmp_path / "unsupported-engines.json", {"engines": decisions})
    gh, log = _fake_gh(tmp_path)

    # When spawn runs
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "engine_skill_gap.py"), "spawn",
                        "--registry", str(reg_file), "--unsupported", str(manifest),
                        "--repo", "acme/llgenie", "--gh", str(gh)],
                       capture_output=True, text=True, timeout=120)

    # Then nothing is created and nothing is even listed
    assert r.returncode == 0, r.stderr
    assert _calls(log) == []
    assert "no unresolved engine" in r.stdout

    # Given an engine with no decision whose tracking issue is ALREADY open
    gh2, log2 = _fake_gh(tmp_path / "second", open_issues=[
        {"number": 42, "title": gap_mod.issue_title("BrandNewServer")}])
    manifest2 = _write(tmp_path / "unsupported2.json", unsupported)
    r2 = subprocess.run([sys.executable, str(REPO / "scripts" / "engine_skill_gap.py"), "spawn",
                         "--registry", str(reg_file), "--unsupported", str(manifest2),
                         "--repo", "acme/llgenie", "--gh", str(gh2)],
                        capture_output=True, text=True, timeout=120)

    # Then it reports the open issue and creates no duplicate
    assert r2.returncode == 0, r2.stderr
    calls = _calls(log2)
    assert [c[:2] for c in calls] == [["issue", "list"]]
    assert "existing: BrandNewServer" in r2.stdout and "#42" in r2.stdout


def test_spawn_fails_loudly_when_github_refuses(tmp_path):
    """A refused create is a failed step, never a silent no-op."""

    # Given a registry with an unresolved engine and a gh whose create returns 403
    registry, skills, unsupported = gap_mod.inventories()
    new = json.loads(REGISTRY.read_text())
    new["engines"]["BrandNewServer"] = {"backend": "CUDA", "url": "https://example.invalid/new"}
    reg_file = _write(tmp_path / "models.json", new)
    manifest = _write(tmp_path / "unsupported-engines.json", unsupported)
    gh, _log = _fake_gh(tmp_path, create_fails=True)

    # When spawn runs
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "engine_skill_gap.py"), "spawn",
                        "--registry", str(reg_file), "--unsupported", str(manifest),
                        "--repo", "acme/llgenie", "--gh", str(gh)],
                       capture_output=True, text=True, timeout=120)

    # Then the step is red and names the failure
    assert r.returncode == 1
    assert "boom: 403" in r.stderr and "issue create" in r.stderr


def test_spawn_dry_reports_the_issue_it_would_open(tmp_path):
    """--dry is how a reviewer previews the sync's artifacts without opening them."""

    # Given an unresolved engine
    registry, skills, unsupported = gap_mod.inventories()
    new = json.loads(REGISTRY.read_text())
    new["engines"]["BrandNewServer"] = {"backend": "CUDA", "url": "https://example.invalid/new"}
    reg_file = _write(tmp_path / "models.json", new)
    manifest = _write(tmp_path / "unsupported-engines.json", unsupported)
    gh, log = _fake_gh(tmp_path)

    # When spawn runs with --dry
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "engine_skill_gap.py"), "spawn",
                        "--registry", str(reg_file), "--unsupported", str(manifest),
                        "--repo", "acme/llgenie", "--gh", str(gh), "--dry"],
                       capture_output=True, text=True, timeout=120)

    # Then it says what it would open and creates nothing
    assert r.returncode == 0, r.stderr
    assert "would-create: BrandNewServer" in r.stdout
    assert not [c for c in _calls(log) if c[:2] == ["issue", "create"]]


# ---------------------------------------------------------------------------
# the permutation grid: an unskilled engine is never offered, and its model is named
# ---------------------------------------------------------------------------
ENGINE_IDS = {"llama.cpp": {"id": "llama-cpp", "formats": ["gguf"],
                            "variants": ["cuda", "rocm", "vulkan", "cpu"]}}


@pytest.fixture()
def perm_env(monkeypatch):
    """The Hub tree + the engine registry are the stand-ins the grid needs; matrix(),
    rank_engines() and the gap computation are the real code."""
    monkeypatch.setattr(mp, "_tree", lambda repo, revision="main": (
        [{"path": "Ok-8B-Q4_K_M.gguf", "type": "file", "size": 4 * GB},
         {"path": "Lost-3B-Q4_K_M.gguf", "type": "file", "size": 2 * GB}]
        if repo == "Org/Ok-8B-GGUF" or repo == "Org/Lost-3B-GGUF" else []))
    monkeypatch.setattr(mp, "engine_ids", lambda: ENGINE_IDS)


@pytest.mark.parametrize("arch", ["cuda", "rocm", "vulkan", "cpu", "metal"])
@pytest.mark.parametrize("vram", [8, 16, 24, 48])
@pytest.mark.parametrize("ram", [8, 32, 60])
def test_no_permutation_ever_offers_an_engine_with_no_skill_and_the_model_is_named(
        perm_env, arch, vram, ram, tmp_path):
    """The grid drops an unskilled engine's model from the offer; the gap artifact
    names it, so the model is visible work instead of an empty row."""

    # Given a registry whose second model is served ONLY by an engine with no skill,
    # and a manifest that records that engine as a dated decision
    registry = _registry({"llama.cpp": {"backend": "CUDA", "url": "https://example.invalid/llama"},
                          "MegaCapybara": {"backend": "CUDA", "url": "https://example.invalid/mega"}},
                         [_model("ok-8b", "Ok 8B", "8GB", "Org/Ok-8B-GGUF", ["llama.cpp"]),
                          _model("lost-3b", "Lost 3B", "8GB", "Org/Lost-3B-GGUF", ["MegaCapybara"])])
    manifest = {"path": str(MANIFEST),
                "engines": {"MegaCapybara": {"decision": "deferred", "decided": "2026-10-14",
                                             "reason": "no llgenie skill yet", "issue": 229}}}

    # When the (arch, vram, ram) permutation grid is computed
    res = mp.matrix(registry, vram, ram, arch)
    g = gap_mod.gap(registry, es.load_skills(), manifest)

    # Then no offered cell is an engine llgenie has no image for
    offered = {c["engine"]["id"] for row in res["permutations"] for c in row["engines"]}
    assert offered <= {"llama-cpp"}, (arch, vram, ram, offered)
    assert all(row["model"]["id"] == "ok-8b" for row in res["permutations"]), (arch, vram, ram)

    # And the dropped model is skipped for a reason, not silently absent
    reason = next((s["why"] for s in res["skipped"] if s["model"] == "lost-3b"), None)
    assert reason and "MegaCapybara" in reason, (arch, vram, ram, res["skipped"])

    # And the gap artifact names it as a model that can never be offered
    assert [m["id"] for m in g["models_never_offered"]] == ["lost-3b"]
    assert g["engines"]["MegaCapybara"]["status"] == "known-unsupported"
    assert g["engines"]["MegaCapybara"]["models"] == ["lost-3b"]

    # And the per-engine list says who is the top engine where
    assert g["engines"]["llama.cpp"]["top_engine"][arch] == ["ok-8b"] or arch == "metal"
    assert g["engines"]["MegaCapybara"]["top_engine"][arch] == []


# ---------------------------------------------------------------------------
# the wiring: the sync regenerates the gap and spawns the issues; CI gates it
# ---------------------------------------------------------------------------
def _sync_steps() -> list[dict]:
    return yaml.safe_load(WORKFLOW.read_text())["jobs"]["sync"]["steps"]


def test_the_weekly_sync_regenerates_the_gap_and_spawns_a_tracking_issue():
    """The trending-list update also updates the engine view and opens the work item."""

    # Given the registry-sync workflow and the Makefile
    steps = _sync_steps()
    runs = [s.get("run", "") for s in steps]
    mk = (REPO / "Makefile").read_text()
    doc = yaml.safe_load(WORKFLOW.read_text())

    # When its steps are read
    # Then it renders the per-engine gap and commits it with the synced registry
    assert any("make render-engine-skill-gap" in r for r in runs)
    add = next(r for r in runs if "git add" in r)
    assert "data/engine-skill-gap.json" in add
    assert "data/engine-skill-gap.json" in next(r for r in runs if "git diff --quiet" in r)

    # And it reports the gap (a report, so the sync still carries the data, #219)
    assert any("make engine-skill-gap" in r for r in runs)
    checks = next(r for r in runs if "make check-registry" in r)
    # (the step's own comment NAMES the ci-unit gate it relies on; the command must not be it)
    assert "make check-engine-skill-gap" not in checks

    # And it spawns one issue per unresolved engine with the sync token
    spawn = next(s for s in steps if "spawn-engine-skill-issues" in s.get("run", ""))
    assert "secrets.BUMP_TOKEN" in yaml.dump(spawn)
    assert doc["permissions"]["issues"] == "write"

    # And the sync PR body carries the gap, asked of a make target (#296) - not the script directly
    body = next(r for r in runs if "gh pr create" in r)
    assert "make engine-skill-gap-md" in body and "${gap}" in body
    assert "python3 scripts/" not in body

    # And the make targets exist, and the gate is a step of the ci-unit job
    assert "render-engine-skill-gap:" in mk and "check-engine-skill-gap:" in mk
    assert "engine-skill-gap:" in mk and "spawn-engine-skill-issues:" in mk
    assert "$(MAKE) check-engine-skill-gap" in mk.split("\nci-unit:", 1)[1].split("\n\n", 1)[0]


def test_the_spawn_step_runs_even_when_a_gate_above_is_red():
    """A red sync gate is exactly the run whose store names a new unskilled engine, so the
    per-engine spawn must not be suppressed by that failure (issue #758)."""

    # Given the registry-sync workflow's sync job
    steps = _sync_steps()
    spawn = next(s for s in steps if "spawn-engine-skill-issues" in s.get("run", ""))
    pr_step = next(s for s in steps if "gh pr create" in s.get("run", ""))

    # When  the spawn step's condition and its recipe are read
    cond = str(spawn.get("if") or "")
    run = spawn.get("run") or ""

    # Then  it runs whatever a step above did, while still requiring a change
    assert cond == "always() && steps.diff.outputs.changed", cond
    assert "success()" not in cond and "steps.check" not in cond

    # And the guard lives inside the recipe too: no diff, no filing, and `make` is never reached
    assert "git diff --quiet" in run and "exit 0" in run
    assert run.index("git diff --quiet") < run.index("make spawn-engine-skill-issues")

    # And the PR step is NOT unconditional: a file the checks did not pass on is never pushed
    assert str(pr_step.get("if") or "") == "steps.diff.outputs.changed"
    assert "always()" not in str(pr_step.get("if") or "")


def test_the_spawn_recipe_files_nothing_without_a_diff(tmp_path):
    """`always()` must not turn a no-change run into a filing: the step's own recipe re-checks
    the diff and exits before `make` (issue #758)."""

    # Given the workflow's spawn recipe, run in a real git checkout of the watched files
    spawn = next(s for s in _sync_steps() if "spawn-engine-skill-issues" in s.get("run", ""))
    script = tmp_path / "spawn.sh"
    # the runner substitutes `${{ … }}` before bash sees the recipe; do the same here
    script.write_text(spawn["run"].replace("${{ github.repository }}", "acme/llgenie"))
    repo = tmp_path / "repo"
    (repo / "data").mkdir(parents=True)
    (repo / "data" / "models.json").write_text('{"generated_utc": "2026-10-27T18:27:00Z"}\n')
    for cmd in (["git", "init", "-q"],
                ["git", "add", "-A"],
                ["git", "-c", "user.name=T", "-c", "user.email=t@example.invalid",
                 "commit", "-qm", "store"]):
        subprocess.run(cmd, cwd=repo, check=True, capture_output=True, text=True)

    # ...with a `make` that records being called (the external command the recipe drives)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    marker = tmp_path / "make-was-called"
    fake_make = bindir / "make"
    fake_make.write_text(f'#!/bin/sh\necho "$@" >> "{marker}"\n')
    fake_make.chmod(0o755)
    env = {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}", "GH_TOKEN": ""}

    # When  the store is unchanged
    clean = subprocess.run(["bash", str(script)], cwd=repo, env=env,
                           capture_output=True, text=True, timeout=120)

    # Then  it says there is nothing to spawn and never runs the target
    assert clean.returncode == 0, clean.stderr
    assert "nothing to spawn" in clean.stdout
    assert not marker.exists()

    # When  the working tree carries a registry change
    (repo / "data" / "models.json").write_text('{"generated_utc": "2026-11-03T05:19:00Z"}\n')
    changed = subprocess.run(["bash", str(script)], cwd=repo, env=env,
                             capture_output=True, text=True, timeout=120)

    # Then  the target runs, so the guard skipped a no-change run and nothing else
    assert changed.returncode == 0, changed.stderr
    assert marker.exists() and "spawn-engine-skill-issues" in marker.read_text()


def test_the_gap_test_file_runs_in_the_unit_gate():
    """A new tests/test_*.py that no target names runs in NO gate."""

    # Given the unit suite the aggregator computes from the tree (issue #393)
    suite = set(ut.select(REPO))

    # When the selection is read
    # Then this test file is in it, so the gate actually runs it
    assert "tests/test_engine_skill_gap.py" in suite


def test_skills_validate_uses_the_decisions_file_instead_of_a_global_flag():
    """One path: the manifest decides what is tolerable, not a loose global flag."""

    # Given the Makefile and the CI job that validates the vendored registry
    mk = (REPO / "Makefile").read_text()

    # When the skills-validate recipe and its call sites are read
    recipe = mk.split("\nskills-validate:", 1)[1].split("\n\n", 1)[0]

    # Then it passes the decisions file when asked, and the loosened flag is gone
    assert "--unsupported" in recipe and "ALLOW_UNSKILLED" not in mk
    assert "UNSUPPORTED=data/unsupported-engines.json" in mk
