"""The KV cache type table, the 8-bit sizing, and the launch/helper agreement (issue #247).

Reported symptom this pins down: `kv_bytes_per_token` had exactly two outcomes —
fp16 or q4_0/q5_* (÷4) — so an 8-bit cache (q8_0, Strata's `int8`, `k8v4`) was
billed at the fp16 size, a 2x overestimate. On the reporting host that is the
difference between "262,144 tokens does not fit" (6.00 GiB computed) and
"262,144 fits" (3.00 GiB real, and 3.6 GB as the engine reports it).

These tests are hermetic: they exercise the pure functions of
`scripts/llama_serve.py` and read the engine skills as data (no server, no
container, no Hub).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import scripts.llama_serve as llama_ai

REPO = Path(__file__).resolve().parents[1]
SKILLS = sorted((REPO / "skills" / "engines").glob("*/SKILL.md"))
FP16 = 2.0  # bytes per element: the baseline every ratio below is expressed in


# --------------------------------------------------------------------------
# the table must cover every type the skills document (the issue's first ask)
# --------------------------------------------------------------------------

def documented_kv_types() -> dict[str, set[str]]:
    """{skill name: {kv types it names}} — parsed from the skills, never hardcoded."""
    out: dict[str, set[str]] = {}
    for path in SKILLS:
        found: set[str] = set()
        for line in path.read_text().splitlines():
            # `--kv q4_0|int8|k8v4`, `--kv q4_0`, `kv q4_0|int8` all count.
            for m in re.finditer(r"--kv[ =]+([A-Za-z0-9_|]+)", line):
                for tok in m.group(1).split("|"):
                    tok = tok.strip().rstrip(",.;")
                    if tok and not tok.isdigit():
                        found.add(tok)
        if found:
            out[path.parent.name] = found
    return out


def test_the_skills_name_kv_types_at_all():
    """Guards the parser: an empty result would make the coverage test vacuous."""
    doc = documented_kv_types()
    assert doc, "no --kv types found in skills/engines/*/SKILL.md — parser or layout changed"
    assert "strata" in doc, f"strata documents the KV types; parsed: {sorted(doc)}"


@pytest.mark.parametrize("skill,types", sorted(documented_kv_types().items()))
def test_every_documented_kv_type_is_sized(skill, types):
    """Every type a skill documents must have an explicit size — none may fall through."""
    unknown = sorted(t for t in types if t not in llama_ai.KV_BYTES_PER_ELEMENT)
    assert not unknown, (
        f"skills/engines/{skill}/SKILL.md documents KV type(s) {unknown} that "
        f"kv_bytes_per_element cannot size (known: {sorted(llama_ai.KV_BYTES_PER_ELEMENT)})"
    )


def test_the_table_covers_the_types_the_issue_names():
    """The issue's list, plus the fp16 baseline the ratios are expressed in."""
    for t in ("q4_0", "q5_0", "q5_1", "q8_0", "int8", "k8v4", "f16", "bf16"):
        assert t in llama_ai.KV_BYTES_PER_ELEMENT, t


def test_eight_bit_types_are_one_byte_per_element():
    """q8_0 and Strata's int8 are 8-bit: 1 byte/element, i.e. exactly fp16 / 2."""
    for t in ("q8_0", "int8"):
        assert llama_ai.KV_BYTES_PER_ELEMENT[t] == FP16 / 2
        assert llama_ai.kv_bytes_per_element(t) == 1.0


def test_k8v4_is_an_eight_bit_k_four_bit_v_split():
    """k8v4 = K 8-bit + V 4-bit: (1 + 0.5) / 2 element-bytes vs fp16's 2."""
    assert llama_ai.KV_BYTES_PER_ELEMENT["k8v4"] == pytest.approx(0.75)
    assert llama_ai.KV_BYTES_PER_ELEMENT["k8v4"] == pytest.approx(FP16 * 0.375)


def test_four_and_five_bit_types_stay_where_they_were():
    """The old ÷4 branch keeps its meaning for q4_0/q4_1; q5_* is 5.5 bits, not 4."""
    for t in ("q4_0", "q4_1", "iq4_nl"):
        assert llama_ai.KV_BYTES_PER_ELEMENT[t] == FP16 / 4
    for t in ("q5_0", "q5_1"):
        assert llama_ai.KV_BYTES_PER_ELEMENT[t] == pytest.approx(5.5 / 8)


# --------------------------------------------------------------------------
# an unknown type is loud, never silently fp16 (the issue's second ask)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("bad", ["q3_0", "Q4_0", "int4", "", None, "f16 ", "fp32"])
def test_an_unknown_kv_type_raises_and_says_what_is_known(bad):
    with pytest.raises(ValueError) as err:
        llama_ai.kv_bytes_per_element(bad)
    msg = str(err.value)
    assert "unknown KV cache type" in msg
    assert "q8_0" in msg and "k8v4" in msg, "the error must name the known types"


def test_an_unknown_type_does_not_quietly_become_fp16():
    """The old code returned `f16_bytes` for anything unrecognised — the bug."""
    meta = _qwen_exp_meta()
    with pytest.raises(ValueError):
        llama_ai.kv_bytes_per_token(meta, "q3_0")
    with pytest.raises(ValueError):
        llama_ai.tuned_context(meta, 1 << 40, quant="q3_0")


# --------------------------------------------------------------------------
# the sizing itself
# --------------------------------------------------------------------------

def _qwen_exp_meta(**over) -> dict:
    """The reported model's shape: Qwen3.8-Flash-Next 125B (qwen4exp), 70.6 GiB."""
    meta = {"file": "/models/qwen3.8-flash-next.gguf", "name": "Qwen3.8-Flash-Next GSQ-RCO",
            "arch": "qwen4exp", "n_layer": 48, "n_embd": 2560, "n_head": 24, "n_head_kv": 2,
            "key_length": 256, "value_length": 256, "full_attention_interval": 4,
            "nextn_layers": 0, "ctx_train": 262144, "size_gb": 70.63}
    meta.update(over)
    return meta


def test_eight_bit_costs_half_of_fp16_and_a_quarter_of_nothing():
    """The reported 2x overestimate: int8 must be f16/2, k8v4 0.375*f16, q4_0 f16/4."""
    meta = _qwen_exp_meta()
    f16 = llama_ai.kv_bytes_per_token(meta, "f16")
    assert llama_ai.kv_bytes_per_token(meta, "int8") == pytest.approx(f16 / 2)
    assert llama_ai.kv_bytes_per_token(meta, "q8_0") == pytest.approx(f16 / 2)
    assert llama_ai.kv_bytes_per_token(meta, "k8v4") == pytest.approx(f16 * 0.375)
    assert llama_ai.kv_bytes_per_token(meta, "q4_0") == pytest.approx(f16 / 4)


def test_the_reported_model_at_262144_int8_is_about_three_gib():
    """The user-visible number: ~3 GiB at 262,144 (measured 3.6 GB by the engine)."""
    meta = _qwen_exp_meta()
    gib = llama_ai.kv_bytes_per_token(meta, "int8") * 262144 / (1024 ** 3)
    assert 2.5 < gib < 4.0, f"int8 KV at 262,144 = {gib:.2f} GiB, expected ~3 (was 6.00 billed as fp16)"
    f16_gib = llama_ai.kv_bytes_per_token(meta, "f16") * 262144 / (1024 ** 3)
    assert f16_gib == pytest.approx(2 * gib), "fp16 must still be exactly twice the 8-bit bill"


def test_the_default_quant_is_the_floor_not_an_unexplained_constant():
    meta = _qwen_exp_meta()
    assert llama_ai.KV_QUANT == "q4_0"
    assert llama_ai.kv_bytes_per_token(meta) == llama_ai.kv_bytes_per_token(meta, llama_ai.KV_QUANT)


# --------------------------------------------------------------------------
# derivation: the type comes from the card (the issue's third ask)
# --------------------------------------------------------------------------

def _card_that_fits(meta, ctx, quant) -> int:
    """The smallest card that holds these weights + that KV cache + the reserve."""
    weights = int(meta["size_gb"] * (1024 ** 3))
    kv = int(llama_ai.kv_bytes_per_token(meta, quant) * ctx)
    return weights + kv + llama_ai.OS_OVERHEAD + (1024 ** 2)


def test_the_card_derives_the_type_fp16_when_it_fits():
    meta = _qwen_exp_meta(size_gb=8.0, n_layer=12)  # a small model that leaves room
    ctx = meta["ctx_train"]
    card = _card_that_fits(meta, ctx, "f16")
    assert llama_ai.kv_quant_for(meta, ctx, card, prefer_larger=True) == "f16"


def test_the_card_derives_eight_bit_when_fp16_does_not_fit():
    meta = _qwen_exp_meta(size_gb=8.0, n_layer=12)
    ctx = meta["ctx_train"]
    card = _card_that_fits(meta, ctx, "q8_0")
    assert llama_ai.kv_quant_for(meta, ctx, card, prefer_larger=True) == "q8_0"


def test_the_card_falls_back_to_the_floor_when_nothing_larger_fits():
    meta = _qwen_exp_meta()  # 70.6 GiB of weights on a 16 GB card: nothing fits
    card = 16 * 1024 ** 3
    assert llama_ai.kv_quant_for(meta, meta["ctx_train"], card, prefer_larger=True) == llama_ai.KV_QUANT


def test_an_unknown_card_leaves_the_floor_alone():
    meta = _qwen_exp_meta()
    assert llama_ai.kv_quant_for(meta, 4096, None) == llama_ai.KV_QUANT


def test_the_default_policy_is_the_floor_no_behaviour_change():
    """#247 fixes the sizing and the coherence; it does NOT change what is served.

    Every host keeps the q4_0 cache it served before (42 launch cases pin it).
    Upgrading capable cards to fp16/q8_0 is the *policy* decision tracked by
    #245; it is reachable here only through the explicit prefer_larger hook.
    """
    meta = _qwen_exp_meta(size_gb=8.0, n_layer=12)
    huge = 1024 * 1024 ** 3
    assert llama_ai.kv_quant_for(meta, meta["ctx_train"], huge) == llama_ai.KV_QUANT
    assert llama_ai.kv_quant_for(meta, meta["ctx_train"], huge, prefer_larger=True) == "f16"


def test_the_derived_type_never_needs_more_room_than_the_budget_gave_it():
    """The invariant that keeps the helper and the launch honest.

    The context is budgeted at the floor type; whatever type is then derived for
    that context must still fit the same card, so switching cannot over-run what
    the context was sized for.
    """
    for size_gb in (4.0, 8.0, 30.0, 70.63):
        for card_gb in (8, 16, 24, 48, 96):
            meta = _qwen_exp_meta(size_gb=size_gb, n_layer=12)
            card = card_gb * 1024 ** 3
            ctx, quant = llama_ai.serve_plan(meta, card)
            weights = int(meta["size_gb"] * (1024 ** 3))
            kv = int(llama_ai.kv_bytes_per_token(meta, quant) * ctx)
            if weights + kv + llama_ai.OS_OVERHEAD <= card or quant == llama_ai.KV_QUANT:
                continue
            pytest.fail(f"size={size_gb} GiB card={card_gb} GiB: chose {quant} which does not fit")


# --------------------------------------------------------------------------
# launch and helper cannot disagree
# --------------------------------------------------------------------------

def test_the_launch_emits_the_derived_type_and_the_helpers_context(monkeypatch):
    monkeypatch.setattr(llama_ai, "LLAMA_SERVER", "llama-server", raising=False)
    meta = _qwen_exp_meta(size_gb=8.0, n_layer=12)
    card = _card_that_fits(meta, meta["ctx_train"], "q8_0")
    ctx, quant = llama_ai.serve_plan(meta, card)
    cmd = llama_ai.build_command(meta, ctx, 11434, card_bytes=card, backend="cuda")
    assert cmd[cmd.index("-ctk") + 1] == quant == llama_ai.kv_quant_for(meta, ctx, card)
    assert cmd[cmd.index("-ctv") + 1] == quant
    assert cmd[cmd.index("-c") + 1] == str(ctx)


def test_the_offload_decision_uses_the_emitted_cache_size():
    """A bigger cache must be able to lower the layer count — same type, one answer."""
    meta = _qwen_exp_meta(size_gb=8.0, n_layer=12)
    ctx = meta["ctx_train"]
    big = _card_that_fits(meta, ctx, "f16")
    small = _card_that_fits(meta, ctx, "q4_0")
    assert llama_ai.gpu_offload_layers(meta, ctx, big, "cuda", "f16") == 99
    # the same card, told the cache is fp16, cannot hold every layer
    ngl = llama_ai.gpu_offload_layers(meta, ctx, small, "cuda", "f16")
    assert isinstance(ngl, int) and ngl < 99
    assert llama_ai.gpu_offload_layers(meta, ctx, small, "cuda", "q4_0") == 99


def test_a_cpu_launch_still_omits_the_gpu_layer_flag(monkeypatch):
    monkeypatch.setattr(llama_ai, "LLAMA_SERVER", "llama-server", raising=False)
    meta = _qwen_exp_meta(size_gb=8.0, n_layer=12)
    ctx, quant = llama_ai.serve_plan(meta, 16 * 1024 ** 3)
    cmd = llama_ai.build_command(meta, ctx, 11434, card_bytes=16 * 1024 ** 3, backend="cpu")
    assert "-ngl" not in cmd
    assert cmd[cmd.index("-ctk") + 1] == quant


# --------------------------------------------------------------------------
# the opt-in knob: the served type is resolved, and one value drives everything
# --------------------------------------------------------------------------

def test_the_knob_is_off_by_default_and_keeps_the_floor(monkeypatch):
    monkeypatch.delenv(llama_ai.KV_QUANT_ENV, raising=False)
    meta = _qwen_exp_meta(size_gb=8.0, n_layer=12)
    assert llama_ai.resolve_kv_quant(meta, meta["ctx_train"], 1024 ** 4) == llama_ai.KV_QUANT


def test_a_named_type_is_validated_and_served(monkeypatch):
    monkeypatch.setenv(llama_ai.KV_QUANT_ENV, "int8")
    monkeypatch.setattr(llama_ai, "LLAMA_SERVER", "llama-server", raising=False)
    meta = _qwen_exp_meta(size_gb=8.0, n_layer=12)
    card = 16 * 1024 ** 3
    ctx, quant = llama_ai.serve_plan(meta, card)
    cmd = llama_ai.build_command(meta, ctx, 11434, card_bytes=card, backend="cuda")
    assert quant == "int8"
    assert cmd[cmd.index("-ctk") + 1] == "int8" and cmd[cmd.index("-ctv") + 1] == "int8"


def test_auto_derives_the_largest_type_that_still_fits(monkeypatch):
    monkeypatch.setenv(llama_ai.KV_QUANT_ENV, "auto")
    meta = _qwen_exp_meta(size_gb=8.0, n_layer=12)
    ctx = meta["ctx_train"]
    card = _card_that_fits(meta, ctx, "q8_0")           # holds 8-bit, not fp16
    assert llama_ai.resolve_kv_quant(meta, ctx, card) == "q8_0"
    assert llama_ai.resolve_kv_quant(meta, ctx, _card_that_fits(meta, ctx, "f16")) == "f16"


def test_the_knob_refuses_a_type_the_table_cannot_size(monkeypatch):
    monkeypatch.setenv(llama_ai.KV_QUANT_ENV, "q3_0")
    meta = _qwen_exp_meta(size_gb=8.0, n_layer=12)
    with pytest.raises(ValueError) as err:
        llama_ai.resolve_kv_quant(meta, meta["ctx_train"], 16 * 1024 ** 3)
    assert "q8_0" in str(err.value) and "k8v4" in str(err.value)


def test_the_knob_type_reaches_the_offload_decision_too(monkeypatch):
    """One value: asking for fp16 must make -ngl account for the fp16 cache."""
    monkeypatch.setenv(llama_ai.KV_QUANT_ENV, "f16")
    monkeypatch.setattr(llama_ai, "LLAMA_SERVER", "llama-server", raising=False)
    meta = _qwen_exp_meta(size_gb=8.0, n_layer=12)
    ctx = meta["ctx_train"]
    card = _card_that_fits(meta, ctx, "q4_0")           # room for the floor only
    cmd = llama_ai.build_command(meta, ctx, 11434, card_bytes=card, backend="cuda")
    assert cmd[cmd.index("-ctk") + 1] == "f16"
    expected = llama_ai.gpu_offload_layers(meta, ctx, card, "cuda", "f16")
    assert cmd[cmd.index("-ngl") + 1] == str(expected)
    assert isinstance(expected, int) and expected < 99, \
        "the fp16 cache cannot fit every layer on this card"
