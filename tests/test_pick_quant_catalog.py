"""The whole-repo pick answers through the committed HF class table (issue #2719).

`matrix()` gates each cell through `pick_quant`, which reads `data/trending-quant-catalog.json`;
`plan_download()` — the seam `offer()` and `llgenie --pick` use — used to resolve MLX/safetensors
plans against the LIVE Hub, so an upstream quant re-push made the matrix propose a cell the CLI
refused (ci-hf-live red on `lfm2.5-24b-a2b::MLX::metal`). These tests pin the seam hermetically:
a diverged live recording must not outrank the table, an uncatalogued pair still resolves live,
and a covered model whose table plans all exceed the budget gets NO invented plan.
"""

import json
import urllib.parse

from scripts import model_engine_pick as mp

GIB = 2**30
CAT_ENV = "LLGENIE_QUANT_CATALOG"
HUB_ENV = mp.HUB_SNAPSHOT_ENV

MODEL_ID = "test-mlx-model"
MLX_REPO = "org/test-m-MLX-3bit"
GB, RAM, ARCH = 24.0, 64.0, "cuda"
BUDGET_GB = mp.weight_budget_gb(GB, False, RAM, ARCH)


def _model(mid=MODEL_ID):
    return {"id": mid, "name": "Test M", "hf": "org/test-m", "vram_min": "8GB",
            "formats": [{"name": "MLX", "hf": MLX_REPO}],
            "engines": [{"engine": "MLX", "tps": "90", "hardware": "M5 Max"}],
            "supported_engines": []}


def _tree_url(repo=MLX_REPO):
    return f"https://huggingface.co/api/models/{repo}/tree/main?recursive=true"


def _search_url(model=None):
    name = mp._base_name(model or _model())
    return (f"https://huggingface.co/api/models?search={urllib.parse.quote(name)}"
            "&filter=mlx&sort=downloads&direction=-1&limit=50")


def _use_catalog(tmp_path, monkeypatch, cells):
    f = tmp_path / "catalog.json"
    f.write_text(json.dumps({"meta": {"generated_utc": "2026-01-01T00:00:00Z"}, "files": cells}))
    monkeypatch.setenv(CAT_ENV, str(f))
    monkeypatch.setattr(mp, "_QUANT_CATALOG_CACHE", None, raising=False)
    mp._reset_tree_memo()
    return f


def _use_recording(tmp_path, monkeypatch, trees=None, searches=None):
    """Install the hub-snapshot replay substitute: the scope text must name
    HUB_SNAPSHOT_ENV itself so the #1000 purity scan sees it through the helper."""
    f = tmp_path / "hub.json"
    f.write_text(json.dumps({"note": "test recording for the catalog seam",
                             "trees": trees or {}, "searches": searches or {}}))
    monkeypatch.setenv(mp.HUB_SNAPSHOT_ENV, str(f))
    mp._reset_tree_memo()
    return f


def _dir_quant(repo=MLX_REPO, size_gb=BUDGET_GB - 0.5):
    return {"repo": repo, "revision": "main", "path": "", "dir": True,
            "files": ["config.json", "model-00001-of-00002.safetensors",
                      "model-00002-of-00002.safetensors"],
            "size_gb": size_gb}


def test_the_table_wins_over_a_diverged_live_recording(tmp_path, monkeypatch):
    """A re-pushed Hub repo no longer fits; the committed table still names the plan."""

    # Given  the table lists a fitting whole-repo MLX quant AND the recording reports the
    #        same repo larger than the weight budget
    _use_catalog(tmp_path, monkeypatch,
                 {MODEL_ID: {"MLX": {"arch": ["cuda"], "quants": [_dir_quant()]}}})
    over_budget = int((BUDGET_GB + 5.0) * GIB)
    _use_recording(tmp_path, monkeypatch, trees={
        _tree_url(): [("config.json", 2048),
                      ("model-00001-of-00002.safetensors", over_budget // 2),
                      ("model-00002-of-00002.safetensors", over_budget // 2)],
    })

    # When   the whole-repo plan is asked for
    plan = mp.plan_download(_model(), GB, RAM, "mlx-safetensors", ARCH)

    # Then   the table's plan is the answer, not the diverged live size
    assert plan is not None
    assert plan["repo"] == MLX_REPO and plan["dir"] is True
    assert abs(plan["size"] - (BUDGET_GB - 0.5) * GIB) < 1
    urls = mp.plan_url(plan)
    assert urls and all(u.startswith(f"https://huggingface.co/{MLX_REPO}/resolve/main/")
                        for u in urls)


def test_a_covered_model_whose_table_exceeds_the_budget_gets_no_invented_plan(tmp_path, monkeypatch):
    """The table decides BOTH ways: nothing fits means no plan — never a live re-query."""

    # Given  the table's only whole-repo quant exceeds the budget AND the recording has NO
    #        answer for that repo's tree: a live query would raise HubSnapshotMissing
    _use_catalog(tmp_path, monkeypatch,
                 {MODEL_ID: {"MLX": {"arch": ["cuda"],
                                     "quants": [_dir_quant(size_gb=BUDGET_GB + 3.0)]}}})
    _use_recording(tmp_path, monkeypatch)  # deliberately empty

    # When   the whole-repo plan is asked for
    plan = mp.plan_download(_model(), GB, RAM, "mlx-safetensors", ARCH)

    # Then   no plan is invented from anywhere else
    assert plan is None


def test_an_uncatalogued_pair_still_resolves_against_the_live_recording(tmp_path, monkeypatch):
    """The documented fallback: a model the table has not been rendered for still resolves live."""

    # Given  a table rendered for OTHER models, and a recording where a fitting MLX repo exists
    _use_catalog(tmp_path, monkeypatch,
                 {"some-other-model": {"llama.cpp": {"arch": ["cuda"], "quants": []}}})
    fit = int((BUDGET_GB - 1.0) * GIB)
    _use_recording(tmp_path, monkeypatch, trees={
        _tree_url(): [("config.json", 2048), ("model-00001-of-00001.safetensors", fit)],
    }, searches={_search_url(): [MLX_REPO]})
    # When   the whole-repo plan is asked for
    plan = mp.plan_download(_model(), GB, RAM, "mlx-safetensors", ARCH)

    # Then   live resolution answers exactly as before the seam
    assert plan is not None and plan["repo"] == MLX_REPO
    assert plan["size"] <= BUDGET_GB * GIB


def test_offer_and_matrix_agree_through_the_table(tmp_path, monkeypatch):
    """One decider, both directions: a fitting table cell offers the engine; an oversized one
    refuses it in BOTH the CLI seam (offer) and the matrix seam (pick_quant)."""

    # Given  a fitting table plan for the pair
    cells = {MODEL_ID: {"MLX": {"arch": ["cuda"], "quants": [_dir_quant()]}}}
    _use_catalog(tmp_path, monkeypatch, cells)
    _use_recording(tmp_path, monkeypatch)  # empty: the table answers, no live query may happen

    row = _model()

    # When   the CLI seam and the matrix seam pick the same pair
    offered = mp.offer({"models": [row]}, root=tmp_path, gb=GB, ram_gb=RAM, arch=ARCH)
    cell = mp.pick_quant(_model(), {"engine": "MLX"}, GB, RAM, ARCH)

    # Then   both propose the same repo, and the CLI's plan matches the cell's
    assert cell is not None and cell["repo"] == MLX_REPO
    assert offered and MLX_REPO in json.dumps(offered[0].get("plans") or {})

    # Given  the table re-rendered so the quant exceeds the budget
    _use_catalog(tmp_path, monkeypatch,
                 {MODEL_ID: {"MLX": {"arch": ["cuda"],
                                     "quants": [_dir_quant(size_gb=BUDGET_GB + 3.0)]}}})

    # When   both seams pick the same pair again
    refused = mp.offer({"models": [row]}, root=tmp_path, gb=GB, ram_gb=RAM, arch=ARCH)
    cell = mp.pick_quant(_model(), {"engine": "MLX"}, GB, RAM, ARCH)

    # Then   both refuse: no matrix cell, and no engine kept for the CLI
    assert cell is None
    assert refused and refused[0].get("engines") == [] and refused[0].get("why")
