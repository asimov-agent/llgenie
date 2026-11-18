"""Ship edge0 as a pack-format engine (issue #2918).

Locks the edge0 engine skill and params against the upstream launch contract v5
(`Edge0-AI/Edge0` `edge0-strata/EDGE0.md`; server-config template
`edge0-strata/edge0/models/edge0-145b.json`): the skill is the source of truth for
`model_contract: "pack"` and the declared parts/config_env. Hermetic — reads the repo's
own skill and params files, never the network.
"""
from __future__ import annotations

from pathlib import Path

import scripts.engine_skills as es

REPO = Path(__file__).resolve().parent.parent
SKILL = es.load_skill(REPO / "skills" / "engines" / "edge0" / "SKILL.md")
PARAMS = __import__("json").loads(
    (REPO / "containers" / "engines" / "params" / "edge0.json").read_text()
)


# The exact EDGE0.md v5 parts the pack-directory launch consumes. Missing parts are a
# launch REFUSAL naming each one (scripts/pack_contract.launch_env), in declared order.
V5_PARTS = ["model-skeleton.gguf", "ple-fp8.gguf", "profile.bin", "experts.bin",
            "labels.bin", "dense.bin", "mtp", "tokenizer"]

# (env var, pack-relative path) — the config_env the pack contract binds as `-e` at run.
V5_CONFIG_ENV = {
    "STRATA_LATENT_A": "experts.bin",
    "STRATA_LATENT_LABELS": "labels.bin",
    "STRATA_LATENT_DENSE": "dense.bin",
}


def test_edge0_skill_declares_the_pack_contract():
    """The skill is forward-declared for the pack launch (issue #2909 carry)."""

    # Given the edge0 skill declares the pack model contract at the top level
    # When  we read model_contract and the pack block
    # Then  it is a pack with exactly the EDGE0.md v5 parts and config_env
    assert SKILL["model_contract"] == "pack"
    assert SKILL["pack"]["parts"] == V5_PARTS
    assert SKILL["pack"]["config_env"] == V5_CONFIG_ENV


def test_edge0_v5_launch_substitutes_the_pack_template():
    """The launch builds its config from the v5 template, placeholders intact."""

    # Given plan renders the skill's pre_launch with the pack contract tokens
    plan = es.plan(SKILL, "cuda", es._fake_hw("cuda"))

    # When  we read the rendered launch pipeline
    rendered = f"{plan['pre_launch']} {plan['launch']}"

    # Then  it consumes the shipped v5 server-config template
    assert "edge0/models/edge0-145b.json" in rendered

    # and every v5 ${PLACEHOLDER} survived the repo renderer as a literal the runtime
    # python substitutes (a brace-collision with _render would red this test)
    for holder in ("${MODEL_DIR}", "${PLE_IO}", "${DU_FILE}", "${LAT_FUSED_Q3K}"):
        assert holder in rendered


def test_edge0_cuda_variant_builds_on_a_cuda13_base():
    """AC2: the Dockerfile lane exists and the CUDA variant sits on a CUDA-13 base."""

    # Given the generated params for edge0's only variant
    variant = PARAMS["variants"]["cuda"]

    # When  we read its base and arch list
    # Then  it is a CUDA-13 devel base with the fat consumer arch list (NVIDIA GPU matrix)
    assert variant["base"].startswith("nvidia/cuda:13")
    assert variant["arch"] == es.FAT_CUDA_ARCHS
    assert variant["detect"].endswith("build/strata --version")


def test_edge0_is_shipped_not_deferred():
    """AC3: the decision record no longer defers edge0; a shipped skill replaces it."""

    # Given the dated decisions file and the shipped skill set
    unsupported = es.load_unsupported()
    shipped = [s.get("engine") for s in es.load_skills().values()]

    # When  edge0 ships a skill
    # Then  it is no longer a dated decision (removing the entry closed the gap)
    assert "edge0" not in (unsupported["engines"] or {})
    assert "edge0" in shipped


def test_edge0_is_in_the_ci_build_matrix():
    """AC2: the engine builds in the engine-build matrix (cuda, version-tested)."""

    # Given the CI matrix built over every committed params file
    import scripts.engine_image as ei

    rows = [r for r in ei.matrix(ci=True) if r["engine"] == "edge0"]

    # When  the edge0 cell is resolved
    # Then  it is the single cuda cell; a pack has no tiny smoke model, so it is detect-
    #       tested (the image's own version), not chat-tested on a GPU-less runner
    assert rows == [{"engine": "edge0", "backend": "cuda", "variant": "cuda",
                     "smoke": False, "test": "detect", "chat": ""}]
