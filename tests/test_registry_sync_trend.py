"""Weekly trending-registry sync (issue #179).

The October 5 vendored snapshot is tests/fixtures/registry-before/. The live
case downloads andyholst/trending-local-llms with sync_registry.sync and ranks
both files with rank_models / rank_engines. No stand-in for that download.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import engine_skills as es  # noqa: E402
import model_engine_pick as mp  # noqa: E402
import sync_registry as sr  # noqa: E402

BEFORE = REPO / "tests" / "fixtures" / "registry-before"
BEFORE_MODELS = BEFORE / "models.json"
BEFORE_README = BEFORE / "README.md"
OCTOBER_5 = "2026-10-05T23:49:35Z"
WORKFLOW = REPO / ".github" / "workflows" / "registry-sync.yml"


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _same_hw(model: dict, arch: str = "cuda") -> dict | None:
    rows = [r for r in mp.rank_engines(model, arch) if r["same_hw"]]
    return rows[0] if rows else None


def _listing(reg: dict, gb: float, arch: str = "cuda") -> list[tuple]:
    """What startup can pick: README order, card fit, highest t/s server first."""
    out = []
    for row in mp.rank_models(reg, arch, gb):
        engine = row["engines"][0]
        out.append((row["model"]["id"], row["model"]["name"], engine["engine"],
                    engine["id"], engine["tps"], engine["measured_on"], engine["variant"]))
    return out


# Card size and architecture are arguments. System RAM is an argument to the
# download budget and to Strata's quant. None of these replace rank_engines.
HARDWARE = (
    ("cuda", 16, 64),
    ("cuda", 48, 64),
    ("cuda", 8, 16),
    ("cuda", 15.9921875, 62),
    ("rocm", 48, 32),
    ("vulkan", 24, 32),
    ("metal", 48, 48),
    ("cpu", 16, 32),
    ("cpu", 2, 8),
)


def _fits_card(model: dict, gb: float) -> bool:
    return mp._num(model.get("vram_tier")) <= mp.card_class_gb(gb)


@pytest.fixture(scope="module")
def live_sync(tmp_path_factory):
    """One real upstream download for every test that ranks the new registry."""

    dest = tmp_path_factory.mktemp("registry") / "models.json"
    assert sr.sync(sr.UPSTREAM, dest, sr.UPSTREAM_README) == 0
    reg = _load(dest)
    readme = (dest.parent / "trending-README.md").read_text()
    sr.check_readme_matches(reg, readme)
    return {"reg": reg, "readme": readme, "dest": dest}


def test_october_5_fixture_ranks_qwen38_27b_on_sglang():
    """The frozen list, before the sync: 16 GB CUDA still shows the old servers."""

    # Given the 2026-10-05 models and the README they were copied with
    reg = _load(BEFORE_MODELS)
    readme = BEFORE_README.read_text()

    # When that snapshot is ranked for a 16 GB CUDA card
    rows = _listing(reg, 16)
    by_id = {row[0]: row for row in rows}
    best = sr.readme_best(readme, "CUDA t/s (best)")

    # Then the servable names are the README rows at or under 16 GB
    assert reg["generated_utc"] == OCTOBER_5
    assert [row[1] for row in rows] == [
        "Qwen3.8-Flash-Next 125B", "Qwen3.8-27B", "Bonsai 2 27B",
        "RavenX-Conjecture-Qwen3-8B-MLX", "Qwen3.6-35B-A3B", "Qwen3 8B",
        "Gemma 4 12B", "Qwen3 14B", "Gemma 4 E2B", "Llama 3.1 8B",
        "DeepSeek R1 1.5B"]
    assert by_id["qwen3.8-27b"][2:6] == ("SGLang", "sglang", 44.0, "CUDA")
    assert by_id["qwen3.8-flash-next-125b"][2] == "Strata"
    assert best["Qwen3.8-27B"] == "DFlash2"
    assert best["Qwen3.8-Flash-Next 125B"] == "Strata"


def test_a_dated_decision_omits_an_unknown_engine_and_dropping_ours_is_still_an_error():
    """A registry engine with no skill fails the strict check; with a dated decision in
    data/unsupported-engines.json (issue #229) it is tolerated, and an engine llgenie
    DOES ship can never be dropped."""

    # Given the October 5 engines plus one name no skill covers, and a copy that drops vLLM
    base = es.load_registry(str(BEFORE_MODELS))
    skills = es.load_skills()
    unsupported = es.load_unsupported(REPO / "data" / "unsupported-engines.json")
    extra = {**base, "MegaCapybara": {"backend": "CUDA", "url": "https://example.invalid"}}
    dropped = {name: spec for name, spec in base.items() if name != "vLLM"}

    # When both registries are validated
    strict = es.validate(skills, extra)
    decided = es.validate(skills, extra, unsupported)
    missing_ours = es.validate(skills, dropped, unsupported)

    # Then only the strict run names MegaCapybara, and dropping our engine is still an error
    assert any("MegaCapybara" in err and "has no skill" in err for err in strict)
    assert not any("has no skill" in err for err in decided)
    assert decided == []
    assert any("vLLM" in err and "not a key" in err for err in missing_ours)

    # And an engine with no skill AND no decision is named as new and unresolved
    unresolved = es.validate(skills, {**base, "NobodyDecidedThis": {"backend": "CUDA"}}, unsupported)
    assert any("NobodyDecidedThis" in err and "no dated decision" in err for err in unresolved)


def test_registry_sync_workflow_is_weekly_and_accounts_for_unskilled_engines():
    """The sync job is weekly, uses the owner token, and never touches skills/*. It
    reports the unskilled-engine gap instead of loosening validation (#229)."""

    # Given the registry-sync workflow
    text = WORKFLOW.read_text()
    doc = yaml.safe_load(text)
    steps = doc["jobs"]["sync"]["steps"]
    opening = next(step for step in steps if "pr create" in step.get("run", ""))

    # When its schedule and its pull-request step are read
    # PyYAML parses the bare workflow key `on` as boolean true.
    cron = re.search(r'cron:\s*"([^"]+)"', text).group(1)

    # Then it is Monday 05:17 UTC, accounts for the unshipped engines (a report + one
    # tracking issue per new one), and commits the registry files
    assert cron == "19 5 * * 1", "its own Monday slot (issue #275)"
    assert "ALLOW_UNSKILLED" not in text
    assert "make engine-skill-gap" in text and "spawn-engine-skill-issues" in text
    assert "secrets.BUMP_TOKEN" in yaml.dump(opening)
    for path in ("data/models.json", "data/trending-README.md",
                 "data/trending-quant-catalog.json", "tests/fixtures/trending-quant-catalog.json",
                 "tests/fixtures/trend-list-matrix.json"):
        assert path in opening["run"]
    assert "render-trend-list-matrix" in text
    assert "skills/" not in opening["run"]
    assert "gh pr merge" not in text
    assert "workflow_dispatch" in text


def test_live_sync_adopts_a_higher_skilled_tps_for_models_that_fit_48gb(live_sync):
    """Download the live registry and rank it against the October 5 snapshot.

    The download is sync_registry.sync. The lists are rank_models for a 48 GB
    CUDA card. A higher same-hardware t/s on an engine we ship replaces the
    old recommendation. An engine with no skill stays out of the list.
    """

    # Given the frozen October 5 registry and the file sync wrote
    old = _load(BEFORE_MODELS)
    assert old["generated_utc"] == OCTOBER_5
    before = _listing(old, 48)
    before_ids = {row[0] for row in before}

    # When that live download is ranked for a 48 GB CUDA card
    new = live_sync["reg"]
    readme = live_sync["readme"]
    dest = live_sync["dest"]
    after = _listing(new, 48)
    after_by = {row[0]: row for row in after}

    # Then the download is newer and the 48 GB list is the README order that fits
    assert new["generated_utc"] > old["generated_utc"]
    fitting = mp.trend_list(new, 48)
    assert [m["name"] for m in fitting] == [
        name for name in sr.readme_order(readme) if mp._num(next(
            m["vram_tier"] for m in new["models"] if m["name"] == name)) <= 48]
    assert any(mp._num(m["vram_tier"]) > 48 for m in new["models"])
    assert all(mp._num(m["vram_tier"]) <= 48 for m in fitting)
    added = [m["id"] for m in fitting if m["id"] not in {row["id"] for row in old["models"]}]
    assert added, "the live list must add models that fit a 48 GB card"

    # And at least one shipped engine got a higher same-hardware t/s, Qwen3.8-27B included
    old_by_id = {m["id"]: m for m in old["models"]}
    increases = []
    for model in new["models"]:
        if model["id"] not in old_by_id:
            continue
        previous = _same_hw(old_by_id[model["id"]])
        current = _same_hw(model)
        if previous and current and current["tps"] > previous["tps"]:
            increases.append((model["id"], previous, current))
    assert increases, f"before {before}\nafter {after}"
    assert any(mid == "qwen3.8-27b" for mid, _prev, _cur in increases)
    for mid, previous, current in increases:
        if mid not in after_by:
            continue
        shown = after_by[mid]
        assert shown[2] == current["engine"], (mid, shown, current)
        assert shown[4] == current["tps"] > previous["tps"]
        assert shown[5] == "CUDA"
    assert "qwen3.8-27b" in before_ids and "qwen3.8-27b" in after_by

    # And an engine with no skill is not the recommendation, even with a higher raw t/s
    skills = es.load_skills()
    no_skill = set(new["engines"]) - {s.get("engine") for s in skills.values()}
    no_image = set(new["engines"]) - set(mp.engine_ids())
    assert no_skill <= no_image
    ranked_names = {row[2] for row in after}
    assert not ranked_names & no_image
    qwen = next(m for m in new["models"] if m["id"] == "qwen3.8-27b")
    raw = max(mp._num(e.get("tps")) for e in qwen["engines"])
    assert raw > after_by["qwen3.8-27b"][4]
    assert any(e["engine"] in no_skill and mp._num(e.get("tps")) == raw for e in qwen["engines"])

    # And the dated decisions accept that registry while the strict validate names the gap.
    # A LIVE registry may carry an engine upstream added after the decisions were dated:
    # that must be reported as undecided (new and unresolved, #229) and must be the ONLY
    # kind of error — never a loosened pass, never an unrelated failure.
    registry = es.load_registry(str(dest))
    decisions = es.load_unsupported(REPO / "data" / "unsupported-engines.json")
    undecided = sorted(set(registry) - set(decisions["engines"])
                       - {s.get("engine") for s in skills.values()})
    decided = es.validate(skills, registry, decisions)
    assert [e for e in decided if "no dated decision" not in e] == [], decided
    assert {n for n in undecided if any(n in e for e in decided)} == set(undecided), decided
    strict = es.validate(skills, registry)
    assert strict and all("has no skill" in err for err in strict)
    for name in no_skill:
        assert any(name in err for err in strict)


def test_rank_follows_the_given_vram_ram_and_arch(live_sync):
    """Card size, system RAM, and architecture are arguments to the real functions.

    rank_models / rank_engines decide the list and the server. weight_budget_gb
    and strata_choice decide how much weight fits and which Strata quant is
    installed. The host's detected GPU is not consulted.
    """

    # Given the October 5 snapshot and the live download
    old = _load(BEFORE_MODELS)
    new = live_sync["reg"]
    qwen_old = next(m for m in old["models"] if m["id"] == "qwen3.8-27b")
    qwen_new = next(m for m in new["models"] if m["id"] == "qwen3.8-27b")
    pinned = {}

    # When each card size and architecture is ranked, and each RAM size is budgeted
    for arch, vram, ram in HARDWARE:
        for reg in (old, new):
            rows = mp.rank_models(reg, arch, vram)
            recommended = [r for r in mp.recommend(reg, arch, vram) if r["engines"]]

            # Then the list is the README rows that fit this card and have an image here
            assert [r["model"]["id"] for r in recommended] == [r["model"]["id"] for r in rows]
            for model in reg["models"]:
                engines = mp.rank_engines(model, arch)
                listed = next((r for r in rows if r["model"]["id"] == model["id"]), None)
                if not _fits_card(model, vram) or not engines:
                    assert listed is None
                    continue
                assert listed is not None
                assert listed["engines"][0]["id"] == engines[0]["id"]
                assert listed["engines"][0]["tps"] == engines[0]["tps"]
                assert listed["engines"][0]["variant"] == engines[0]["variant"]
                assert listed["engines"][0]["measured_on"] == engines[0]["measured_on"]
                keys = [(e["rank"], -e["tps"]) for e in listed["engines"]]
                assert keys == sorted(keys)
        pinned[(arch, vram)] = next(
            (r["engines"][0] for r in mp.rank_models(old, arch, vram)
             if r["model"]["id"] == "qwen3.8-27b"), None)
        # RAM is the MoE spill on CUDA. Metal and CPU keep one memory pool.
        budget_card = vram if vram >= 8 else 16
        moe = mp.weight_budget_gb(budget_card, True, ram, arch)
        dense = mp.weight_budget_gb(budget_card, False, ram, arch)
        if arch in ("metal", "cpu"):
            assert moe == dense
        else:
            assert moe == dense + max(0.0, ram - 4)

    # And the October 5 server follows the architecture, not one global pick
    assert (pinned[("cuda", 16)]["id"], pinned[("cuda", 16)]["tps"],
            pinned[("cuda", 16)]["variant"]) == ("sglang", 44.0, "cuda")
    assert pinned[("cuda", 15.9921875)]["id"] == "sglang"
    assert pinned[("cuda", 8)] is None
    assert (pinned[("metal", 48)]["id"], pinned[("metal", 48)]["tps"],
            pinned[("metal", 48)]["variant"]) == ("tensorfold", 189.0, "metal")
    assert (pinned[("rocm", 48)]["id"], pinned[("rocm", 48)]["variant"],
            pinned[("rocm", 48)]["measured_on"]) == (
                "llama.cpp-laurentzuijdwijk", "rocm", "ROCm")
    assert (pinned[("vulkan", 24)]["id"], pinned[("vulkan", 24)]["variant"]) == (
        "llama.cpp-laurentzuijdwijk", "vulkan")
    assert pinned[("cpu", 16)]["id"] == "mlx"
    assert all(e["id"] != "tensorfold" for e in mp.rank_engines(qwen_old, "cpu"))
    assert {pinned[("cuda", 16)]["id"], pinned[("metal", 48)]["id"],
            pinned[("rocm", 48)]["id"], pinned[("cpu", 16)]["id"]} == {
                "sglang", "tensorfold", "llama.cpp-laurentzuijdwijk", "mlx"}

    # And RAM changes the CUDA MoE budget and the Strata quant, not the Metal or CPU budget
    assert mp.weight_budget_gb(16, True, 8, "cuda") < mp.weight_budget_gb(16, True, 64, "cuda")
    assert mp.weight_budget_gb(16, False, 8, "cuda") == mp.weight_budget_gb(16, False, 64, "cuda")
    assert mp.weight_budget_gb(48, True, 16, "metal") == mp.weight_budget_gb(48, True, 128, "metal")
    assert mp.weight_budget_gb(16, True, 8, "cpu") == mp.weight_budget_gb(16, True, 64, "cpu")
    assert mp.strata_choice(8)[1] == mp.strata_choice(59)[1] == "Q2_0"
    assert mp.strata_choice(60)[1] == mp.strata_choice(64)[1] == "IQ3_XXS"

    # And the live CUDA figure for Qwen3.8-27B is the higher one at 16 GB and at 48 GB
    previous = _same_hw(qwen_old, "cuda")
    for vram in (16, 48):
        shown = next(r for r in mp.rank_models(new, "cuda", vram)
                     if r["model"]["id"] == "qwen3.8-27b")
        current = _same_hw(qwen_new, "cuda")
        assert shown["engines"][0]["engine"] == current["engine"]
        assert shown["engines"][0]["tps"] == current["tps"] > previous["tps"]
        assert shown["engines"][0]["measured_on"] == "CUDA"
    assert next((r for r in mp.rank_models(new, "cuda", 8)
                 if r["model"]["id"] == "qwen3.8-27b"), None) is None
    metal = mp.rank_engines(qwen_new, "metal")[0]
    assert metal["measured_on"] == "Metal" and metal["variant"] == "metal"
    assert all(e["variant"] != "metal" for e in mp.rank_engines(qwen_new, "cpu"))
    big = [m for m in new["models"] if mp._num(m["vram_tier"]) > 48]
    assert big
    at_48 = {r["model"]["id"] for r in mp.rank_models(new, "cuda", 48)}
    assert all(m["id"] not in at_48 for m in big)


def test_skills_validate_cli_with_the_decisions_exits_zero_on_the_october_5_fixture():
    """`make skills-validate REGISTRY=<file> UNSUPPORTED=data/unsupported-engines.json` is
    this command (issue #229: one path — the decisions file, not a loose global flag)."""

    # Given the October 5 registry, which our skills already cover
    cmd = [sys.executable, str(REPO / "scripts" / "engine_skills.py"), "validate",
           "--registry", str(BEFORE_MODELS),
           "--unsupported", str(REPO / "data" / "unsupported-engines.json")]

    # When the validator CLI runs
    result = subprocess.run(cmd, capture_output=True, text=True)

    # Then it reports 0 errors
    assert result.returncode == 0, result.stderr
    assert "0 error(s)" in result.stdout


def test_the_sync_job_validates_the_registry_it_just_synced():
    """Issue #319: the sync job's post-sync gate must validate the SAME data ci-unit does.

    Without the overrides `make skills-validate` falls back to the Makefile's small fixture, and the
    earlier form passed REGISTRY without UNSUPPORTED — so the job's own gate could pass (or error on
    recorded-unsupported engines) while the registry it was about to push was never really checked.
    """

    # Given the sync workflow's validation step and ci-unit's own skills-validate line
    wf = yaml.safe_load(WORKFLOW.read_text())
    step = next(s for s in wf["jobs"]["sync"]["steps"]
                if "skills-validate" in (s.get("run") or ""))
    ci_lines = [l.strip() for l in (REPO / "Makefile").read_text().splitlines()
                if "skills-validate" in l and "REGISTRY=data/models.json" in l]

    # When the sync job's invocation is read
    run = step["run"]

    # Then it pins the same registry AND the same unsupported-decisions list ci-unit uses
    assert ("make skills-validate REGISTRY=data/models.json "
            "UNSUPPORTED=data/unsupported-engines.json") in run, run
    assert ci_lines, "ci-unit must keep validating the real registry"
    assert "UNSUPPORTED=data/unsupported-engines.json" in ci_lines[0], ci_lines
