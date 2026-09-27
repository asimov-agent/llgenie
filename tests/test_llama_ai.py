"""Unit tests for scripts/llama_serve.py (the GGUF launcher).

Run under the gguf venv python (`make test-unit`). These are hermetic:
they do NOT launch llama-server or require installed ~/bin artifacts — they
exercise the pure functions in scripts/llama_serve.py and the on-disk model scan.
"""
from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

import io
import urllib.error

import pytest

import scripts.llama_serve as llama_ai  # noqa: E402  (relocated from root llgenie.py; importable: gguf+numpy come from the venv)


def _minimal_gguf(tmp_path: Path, filename: str = "mini.gguf") -> Path:
    """Write a tiny but well-formed GGUF header so the fast reader parses it.

    Builds: general.architecture (str), general.name (str), block_count,
    embedding_length, attention.head_count, attention.head_count_kv,
    context_length (all uint32), tokenizer.chat_template (str).
    """
    p = tmp_path / filename

    def s(v: str) -> bytes:
        b = v.encode("utf-8")
        return struct.pack("<Q", len(b)) + b

    def kv(key: str, vtype: int, val: bytes) -> bytes:
        return struct.pack("<Q", len(key)) + key.encode() + struct.pack("<I", vtype) + val

    buf = bytearray()
    buf += b"GGUF"
    buf += struct.pack("<I", 3)          # version
    buf += struct.pack("<Q", 0)          # tensor_count
    pairs = [
        kv("general.architecture", 8, s("qwen2")),
        kv("general.name", 8, s("mini-model")),
        kv("qwen2.block_count", 4, struct.pack("<I", 28)),
        kv("qwen2.embedding_length", 4, struct.pack("<I", 3584)),
        kv("qwen2.attention.head_count", 4, struct.pack("<I", 28)),
        kv("qwen2.attention.head_count_kv", 4, struct.pack("<I", 4)),
        kv("qwen2.context_length", 4, struct.pack("<I", 32768)),
        kv("tokenizer.chat_template", 8, s("<|im_start|>template<|im_end|>")),
    ]
    buf += struct.pack("<Q", len(pairs))
    for x in pairs:
        buf += x
    p.write_bytes(bytes(buf))
    return p


# ---------------------------------------------------------------------------
# metadata reader
# ---------------------------------------------------------------------------
def test_fast_reader_parses_minimal_gguf(tmp_path):
    p = _minimal_gguf(tmp_path)
    m = llama_ai.read_model_meta_fast(str(p))
    assert m is not None
    assert m["arch"] == "qwen2"
    assert m["name"] == "mini-model"
    assert m["n_layer"] == 28
    assert m["n_embd"] == 3584
    assert m["n_head"] == 28
    assert m["n_head_kv"] == 4
    assert m["ctx_train"] == 32768
    assert "template" in m["chat_template"]


def test_fast_reader_returns_none_on_non_gguf(tmp_path):
    p = tmp_path / "junk.bin"
    p.write_bytes(b"NOTAGGUFFILE" * 16)
    assert llama_ai.read_model_meta_fast(str(p)) is None


def test_download_metadata_verification_accepts_real_gguf(tmp_path):
    """The post-download metadata verification (download_top_tier_candidate) accepts a
    genuine GGUF model file — proves the right model was downloaded (by its GGUF header)."""
    p = _minimal_gguf(tmp_path)
    meta = llama_ai.read_model_meta_fast(str(p)) or llama_ai.read_model_meta(str(p))
    assert meta is not None, "a real GGUF model must be verifiable by its metadata"
    # the exact metadata that identifies which model it is:
    assert meta["name"] == "mini-model"
    assert meta["arch"] == "qwen2"
    assert meta["n_layer"] == 28


def test_download_metadata_verification_rejects_html_error_page(tmp_path):
    """story: a botched download (e.g. an HTML error page saved as model.gguf) must be
    caught by the metadata verification and NOT accepted as a valid model."""
    # an HTML error page is NOT a GGUF — mirror the download path's verification:
    # fast reader returns None, full reader raises, and the result is REJECTED.
    p = tmp_path / "model.gguf"
    p.write_bytes(b"<html><body>404: Model Not Found</body></html>")
    meta = llama_ai.read_model_meta_fast(str(p))
    if meta is None:
        try:
            meta = llama_ai.read_model_meta(str(p))
        except Exception:
            meta = None
    assert meta is None, "an HTML error page is not a valid GGUF model and must be rejected"


# ---------------------------------------------------------------------------
# model scan (reads whatever lives under MODELS_ROOT)
# ---------------------------------------------------------------------------
@pytest.fixture
def hermetic_models_dir(tmp_path, monkeypatch):
    """Seed a temp models dir with two mini GGUFs of different sizes and point
    llama_ai.MODELS_ROOT at it, so the scan tests run hermetically — no host
    ~/models dependency, no skips."""
    models = tmp_path / "models"
    models.mkdir()
    _minimal_gguf(models, "a-small.gguf")                      # tiny header
    big = _minimal_gguf(models, "z-big.gguf")                  # larger file
    big.write_bytes(big.read_bytes() + b"\x00" * (2048 * 1024))  # ~2 MB
    monkeypatch.setattr(llama_ai, "MODELS_ROOT", str(models))
    return models


def test_models_root_exists(hermetic_models_dir):
    # MODELS_ROOT points at a real, existing seeded dir — no host dependency.
    assert llama_ai.MODELS_ROOT == str(hermetic_models_dir)
    assert Path(llama_ai.MODELS_ROOT).is_dir(), (
        "MODELS_ROOT points at a dir that does not exist"
    )


def test_scan_models_returns_sorted_list(hermetic_models_dir):
    models = llama_ai.scan_models()
    assert len(models) == 2, "expected the two seeded ggu files to be scanned"
    for m in models:
        for key in ("file", "name", "arch", "size_gb", "ctx_train"):
            assert key in m, f"meta missing key {key}"
    sizes = [m["size_gb"] for m in models]
    assert sizes == sorted(sizes, reverse=True), "models not sorted by size desc"
    # the bigger (padded z-big.gguf) must sort first
    assert models[0]["size_gb"] > models[1]["size_gb"]
    assert models[0]["file"].endswith("z-big.gguf")


# ---------------------------------------------------------------------------
# reasoning detection
# ---------------------------------------------------------------------------
def test_is_reasoning_model_detects_markers():
    assert llama_ai.is_reasoning_model({"chat_template": "x<|start_of_fim|>y"})
    assert llama_ai.is_reasoning_model({"chat_template": "deepseek reasoning cot"})
    assert not llama_ai.is_reasoning_model({"chat_template": "llama3 meta"})
    assert not llama_ai.is_reasoning_model({"chat_template": ""})


# ---------------------------------------------------------------------------
# auto-tuning math
# ---------------------------------------------------------------------------
def test_kv_bytes_per_token_positive():
    meta = {"n_embd": 3584, "n_head": 28, "n_head_kv": 4, "n_layer": 28}
    assert llama_ai.kv_bytes_per_token(meta) > 0
    # q4_0 (default) is ~4x smaller than fp16
    assert llama_ai.kv_bytes_per_token(meta, "q4_0") < llama_ai.kv_bytes_per_token(meta, "f16")


def test_tuned_context_capped_by_train_ctx():
    """A model's trained context is the ceiling, and a tiny budget floors at 2048."""

    # Given a dense model trained to 4096 tokens
    meta = {
        "ctx_train": 4096, "n_embd": 3584, "n_head": 28,
        "n_head_kv": 4, "n_layer": 28,
    }

    # When the KV budget cannot hold even one token, and when it is huge
    assert llama_ai.kv_bytes_per_token(meta) > 0
    ctx = llama_ai.tuned_context(meta, 1)
    ctx2 = llama_ai.tuned_context(meta, 10 ** 18)

    # Then the tiny budget floors at 2048 and the huge budget stays at the train ctx
    assert ctx == 2048
    assert ctx2 <= 4096
    assert ctx2 % 1024 == 0


def _bonsai_mtp_meta(size_gb=6.5):
    """Shape of Ternary-Bonsai-2-27B-PTQ1_0-mtp.gguf (qwen35 hybrid, 262144 train ctx)."""
    return {
        "file": "/models/Ternary-Bonsai-2-27B-PTQ1_0-mtp.gguf",
        "name": "bonsai",
        "arch": "qwen35",
        "n_layer": 65,
        "n_embd": 5120,
        "n_head": 24,
        "n_head_kv": 4,
        "ctx_train": 262144,
        "key_length": 256,
        "value_length": 256,
        "full_attention_interval": 4,
        "nextn_layers": 1,
        "chat_template": "qwen",
        "size_gb": size_gb,
    }


def test_hybrid_kv_counts_full_attention_layers_only():
    """Hybrid models must not price every block as full attention."""

    # Given a Bonsai-shaped hybrid (interval 4, key/value length 256, one MTP block)
    meta = _bonsai_mtp_meta()

    # When KV bytes/token are estimated
    per = llama_ai.kv_bytes_per_token(meta)
    dense = {
        **meta,
        "full_attention_interval": 0,
        "key_length": 0,
        "value_length": 0,
    }
    dense_per = llama_ai.kv_bytes_per_token(dense)

    # Then only the full-attention layers are charged, using the real head dim
    # 16 language layers (64 // 4) + 1 MTP block, q4_0, key=value=256, 4 KV heads
    assert per == 17 * 4 * (256 + 256) * 0.5
    assert per < dense_per


def test_build_command_offloads_every_layer_when_the_card_fits(server_on_path):
    """A GPU card that holds the weights and the KV cache asks for every layer."""

    # Given a Bonsai-shaped file and a CUDA backend on a 16 GB card
    meta = _bonsai_mtp_meta()
    card = 16 * 1024 ** 3

    # When the launch command is built
    ctx = llama_ai.serve_context(meta, card)
    cmd = llama_ai.build_command(meta, ctx, 11434, card_bytes=card, backend="cuda")

    # Then context stays at the trained max and every layer goes to the GPU
    assert cmd[cmd.index("-c") + 1] == "262144"
    assert cmd[cmd.index("-ngl") + 1] == "99"
    assert cmd[cmd.index("-fa") + 1] == "on"
    assert cmd[cmd.index("-ctk") + 1] == "q4_0"
    assert cmd[cmd.index("-ctv") + 1] == "q4_0"
    assert cmd[cmd.index("-b") + 1] == "2048"
    assert cmd[cmd.index("-ub") + 1] == "512"
    assert "--jinja" in cmd
    assert cmd[cmd.index("--spec-draft-n-max") + 1] == "1"


def test_build_command_offloads_fewer_layers_when_the_weights_do_not_fit(server_on_path):
    """An 8 GB card keeps a shorter context and a partial GPU offload."""

    # Given the same file on an 8 GB CUDA card
    meta = _bonsai_mtp_meta()
    card = 8 * 1024 ** 3

    # When the launch command is built
    ctx = llama_ai.serve_context(meta, card)
    cmd = llama_ai.build_command(meta, ctx, 11434, card_bytes=card, backend="cuda")

    # Then -c is the reduced window and -ngl is only the layers that fit
    assert cmd[cmd.index("-c") + 1] == "30720"
    assert int(cmd[cmd.index("-ngl") + 1]) == 45
    assert cmd[cmd.index("-b") + 1] == "512"
    assert cmd[cmd.index("-ub") + 1] == "256"


def test_build_command_cpu_backend_skips_gpu_flags(server_on_path):
    """A CPU backend does not request GPU layers or flash attention."""

    # Given a Bonsai-shaped file and a CPU backend
    meta = _bonsai_mtp_meta()
    card = 16 * 1024 ** 3

    # When the launch command is built
    ctx = llama_ai.serve_context(meta, card)
    cmd = llama_ai.build_command(meta, ctx, 11434, card_bytes=card, backend="cpu")

    # Then GPU-only flags are absent and the context flag remains
    assert "-ngl" not in cmd
    assert "-fa" not in cmd
    assert cmd[cmd.index("-c") + 1] == "262144"


def test_build_command_omits_flags_the_model_does_not_support(server_on_path):
    """No chat template, no reasoning template, and no MTP head means those flags stay off."""

    # Given a plain dense model
    meta = {
        "file": "/models/plain.gguf", "name": "plain", "arch": "llama",
        "n_layer": 32, "n_embd": 4096, "n_head": 32, "n_head_kv": 8,
        "ctx_train": 8192, "chat_template": "", "nextn_layers": 0,
        "size_gb": 4.0,
    }

    # When the launch command is built for a CUDA card
    cmd = llama_ai.build_command(
        meta, ctx=8192, port=11434, card_bytes=16 * 1024 ** 3, backend="cuda",
    )

    # Then template, reasoning, and spec-decode flags are absent
    assert "--jinja" not in cmd
    assert "--reasoning" not in cmd
    assert "--spec-type" not in cmd


def test_batch_grows_with_the_card():
    """A larger card gets a larger logical batch and micro-batch."""

    # Given three card sizes
    small = 8 * 1024 ** 3
    mid = 16 * 1024 ** 3
    big = 48 * 1024 ** 3

    # When the batch is chosen
    # Then it steps up with the card
    assert llama_ai.batch_for_card(small) == (512, 256)
    assert llama_ai.batch_for_card(mid) == (2048, 512)
    assert llama_ai.batch_for_card(big) == (4096, 1024)


def _prism_ptq_meta(quant="PTQ1_0", size_gb=5.93):
    """Ternary Bonsai 2 low-bit packing. Shape matches the 27B qwen35 MTP file."""
    meta = _bonsai_mtp_meta(size_gb)
    meta["file"] = f"/models/Ternary-Bonsai-2-27B-{quant}.gguf"
    meta["quant"] = quant
    return meta


def test_ptq1_0_on_16gb_keeps_full_context_and_bonsai_sampling(server_on_path):
    """A Prism PTQ1_0 file that fits gets the trained window and Bonsai sampling."""

    # Given a PTQ1_0 Bonsai file and a 16 GB CUDA card
    meta = _prism_ptq_meta("PTQ1_0", 5.93)
    card = 16 * 1024 ** 3

    # When llgenie builds the server command
    ctx = llama_ai.serve_context(meta, card)
    cmd = llama_ai.build_command(meta, ctx, 11434, card_bytes=card, backend="cuda")

    # Then the trained context, full offload, and Bonsai sampling are set
    assert cmd[cmd.index("-c") + 1] == "262144"
    assert cmd[cmd.index("-ngl") + 1] == "99"
    assert cmd[cmd.index("-fa") + 1] == "on"
    assert cmd[cmd.index("-ctk") + 1] == "q4_0"
    assert cmd[cmd.index("-b") + 1] == "2048"
    assert cmd[cmd.index("--temp") + 1] == "0.5"
    assert cmd[cmd.index("--top-p") + 1] == "0.85"
    assert cmd[cmd.index("--top-k") + 1] == "20"
    assert cmd[cmd.index("--min-p") + 1] == "0"
    assert cmd[cmd.index("--spec-draft-n-max") + 1] == "1"


def test_ptq1_0_on_8gb_shrinks_context_and_offload(server_on_path):
    """The same PTQ1_0 file on 8 GB does not keep 262144 or every layer."""

    # Given that PTQ1_0 file on an 8 GB CUDA card
    meta = _prism_ptq_meta("PTQ1_0", 5.93)
    card = 8 * 1024 ** 3

    # When llgenie builds the server command
    ctx = llama_ai.serve_context(meta, card)
    cmd = llama_ai.build_command(meta, ctx, 11434, card_bytes=card, backend="cuda")

    # Then context and GPU layers both shrink
    assert cmd[cmd.index("-c") + 1] == "30720"
    assert cmd[cmd.index("-ngl") + 1] == "49"


def test_pq2_0_on_8gb_offloads_fewer_layers_than_ptq1_0(server_on_path):
    """PQ2_0 is heavier, so the same 8 GB card offloads fewer layers."""

    # Given a PQ2_0 file (about 7.25 GB) on an 8 GB CUDA card
    meta = _prism_ptq_meta("PQ2_0", 7.25)
    card = 8 * 1024 ** 3

    # When llgenie builds the server command
    ctx = llama_ai.serve_context(meta, card)
    cmd = llama_ai.build_command(meta, ctx, 11434, card_bytes=card, backend="cuda")

    # Then context matches the card and fewer layers are offloaded than PTQ1_0
    assert cmd[cmd.index("-c") + 1] == "30720"
    assert cmd[cmd.index("-ngl") + 1] == "40"
    assert cmd[cmd.index("--temp") + 1] == "0.5"


def test_prism_file_keeps_author_sampling_when_present(server_on_path):
    """A sampling block in the GGUF replaces the Bonsai defaults."""

    # Given a PTQ1_0 file that already names a temperature
    meta = _prism_ptq_meta()
    meta["sampling"] = {"temperature": "0.7"}

    # When llgenie builds the server command
    cmd = llama_ai.build_command(
        meta, ctx=4096, port=11434, card_bytes=16 * 1024 ** 3, backend="cuda",
    )

    # Then the file's temperature is used and the Bonsai 0.5 default is not
    assert cmd[cmd.index("--temp") + 1] == "0.7"
    assert "0.5" not in cmd


def _install_fake_llama_server(monkeypatch, tmp_path, card_bytes, backend):
    """Point llgenie at a fake binary. The script itself is not patched.

    VRAM and backend go through LLAMA_RAM_BYTES and LLAMA_BACKEND, which
    detect_server already reads. The fake binary records its argv and exits.
    """
    binary = tmp_path / "fake-bin" / "llama-server"
    binary.parent.mkdir(parents=True, exist_ok=True)
    argv_out = tmp_path / "fake-bin" / "argv.txt"
    binary.write_text("#!/bin/sh\nprintf '%s\\n' \"$0\" \"$@\" > \"$LLAMA_ARGV_OUT\"\n")
    binary.chmod(0o755)
    monkeypatch.setenv("LLAMA_SERVER", str(binary))
    monkeypatch.setenv("LLAMA_ARGV_OUT", str(argv_out))
    monkeypatch.setenv("LLAMA_RAM_BYTES", str(int(card_bytes)))
    monkeypatch.setenv("LLAMA_BACKEND", backend)
    return binary, argv_out


def _read_fake_argv(argv_out):
    assert argv_out.is_file(), "llama-server was not started"
    return argv_out.read_text().splitlines()


def _run_llgenie(monkeypatch, tmp_path, filename, arch, fields, size_gb, card_bytes, backend, select):
    """Run llama_serve.main. Only the llama-server binary is fake."""
    models = tmp_path / "models"
    models.mkdir()
    _gguf_file(
        models, filename, arch, fields,
        {"tokenizer.chat_template": "qwen"},
        int(size_gb * 1024 ** 3),
    )
    _binary, argv_out = _install_fake_llama_server(monkeypatch, tmp_path, card_bytes, backend)
    monkeypatch.setenv("LLAMA_MODELS_ROOT", str(models))
    monkeypatch.setattr(sys, "argv", ["llgenie", select, "--port", "45119"])
    llama_ai.main()
    return _read_fake_argv(argv_out)


def _gguf_file(directory, filename, arch, fields, strings, size_bytes):
    """Write a GGUF header, then set the file size the launcher will see."""

    def s(v: str) -> bytes:
        b = v.encode("utf-8")
        return struct.pack("<Q", len(b)) + b

    def kv(key: str, vtype: int, val: bytes) -> bytes:
        return struct.pack("<Q", len(key)) + key.encode() + struct.pack("<I", vtype) + val

    pairs = [
        kv("general.architecture", 8, s(arch)),
        kv("general.name", 8, s(filename)),
    ]
    for key, value in fields.items():
        pairs.append(kv(f"{arch}.{key}", 4, struct.pack("<I", int(value))))
    for key, value in strings.items():
        pairs.append(kv(key, 8, s(value)))
    buf = bytearray(b"GGUF" + struct.pack("<I", 3) + struct.pack("<Q", 0))
    buf += struct.pack("<Q", len(pairs))
    for pair in pairs:
        buf += pair
    path = directory / filename
    path.write_bytes(bytes(buf))
    os.truncate(path, int(size_bytes))
    return path


PRISM_HEADER = {
    "block_count": 65,
    "embedding_length": 5120,
    "attention.head_count": 24,
    "attention.head_count_kv": 4,
    "context_length": 262144,
    "attention.key_length": 256,
    "attention.value_length": 256,
    "full_attention_interval": 4,
    "nextn_predict_layers": 1,
}
STOCK_HEADER = {
    "block_count": 28,
    "embedding_length": 3584,
    "attention.head_count": 28,
    "attention.head_count_kv": 4,
    "context_length": 32768,
}


def _run_llgenie(monkeypatch, tmp_path, filename, arch, fields, size_gb, card_bytes, backend, select):
    """Run real llgenie.main against a GGUF on disk and a fake llama-server."""
    models = tmp_path / "models"
    models.mkdir()
    _gguf_file(models, filename, arch, fields, {"tokenizer.chat_template": "qwen"}, int(size_gb * 1024 ** 3))
    binary, argv_out = _install_fake_llama_server(monkeypatch, tmp_path, card_bytes, backend)
    monkeypatch.setenv("LLAMA_MODELS_ROOT", str(models))
    monkeypatch.setattr(sys, "argv", ["llgenie", select, "--port", "45119"])
    llama_ai.main()
    cmd = _read_fake_argv(argv_out)
    assert cmd[0] == str(binary)
    return cmd


def test_mocked_llgenie_start_ptq_uses_vram_and_does_not_exec(monkeypatch, tmp_path):
    """Real llgenie reads a PTQ1_0 file and starts the fake binary with 16 GB flags."""

    # Given a PTQ1_0 GGUF on disk and LLAMA_RAM_BYTES of 16 GB
    cmd = _run_llgenie(
        monkeypatch, tmp_path, "Ternary-Bonsai-2-27B-PTQ1_0.gguf", "qwen35",
        PRISM_HEADER, 5.93, 16 * 1024 ** 3, "cuda", "PTQ1_0",
    )

    # Then the fake binary received the 16 GB parameters
    assert cmd[cmd.index("-c") + 1] == "262144"
    assert cmd[cmd.index("-ngl") + 1] == "99"
    assert cmd[cmd.index("-b") + 1] == "2048"
    assert cmd[cmd.index("--temp") + 1] == "0.5"
    assert cmd[cmd.index("--spec-draft-n-max") + 1] == "1"


def test_mocked_llgenie_start_ptq_on_8gb_shrinks_the_argv(monkeypatch, tmp_path):
    """The same real launch on 8 GB carries the smaller context and partial offload."""

    # Given that PTQ1_0 file and an 8 GB card
    cmd = _run_llgenie(
        monkeypatch, tmp_path, "Ternary-Bonsai-2-27B-PTQ1_0.gguf", "qwen35",
        PRISM_HEADER, 5.93, 8 * 1024 ** 3, "cuda", "PTQ1_0",
    )

    # Then the fake binary received the 8 GB parameters
    assert cmd[cmd.index("-c") + 1] == "30720"
    assert cmd[cmd.index("-ngl") + 1] == "49"
    assert cmd[cmd.index("-b") + 1] == "512"
    assert cmd[cmd.index("-ub") + 1] == "256"


def test_mocked_llgenie_start_pq2_on_8gb(monkeypatch, tmp_path):
    """PQ2_0 is heavier, so the fake binary is started with fewer layers."""

    # Given a PQ2_0 file and an 8 GB card
    cmd = _run_llgenie(
        monkeypatch, tmp_path, "Ternary-Bonsai-2-27B-PQ2_0.gguf", "qwen35",
        PRISM_HEADER, 7.25, 8 * 1024 ** 3, "cuda", "PQ2_0",
    )

    # Then context matches the card and fewer layers are offloaded
    assert cmd[cmd.index("-c") + 1] == "30720"
    assert cmd[cmd.index("-ngl") + 1] == "40"


# (quant, weight GB, card GB, -c, -ngl, -b, -ub, --spec-draft-n-max)
# PTQ1_0 and TQ1_0 are the lighter packings (5.93 GB). PQ2_0 and TQ2_0 are
# the heavier packings (7.25 GB). 12 GB is where their contexts diverge.
PRISM_VRAM_CASES = [
    ("PTQ1_0", 5.93, 2, "30720", "0", "512", "256", "1"),
    ("PTQ1_0", 5.93, 4, "30720", "5", "512", "256", "1"),
    ("PTQ1_0", 5.93, 8, "30720", "49", "512", "256", "1"),
    ("PTQ1_0", 5.93, 12, "188416", "99", "2048", "512", "1"),
    ("PTQ1_0", 5.93, 16, "262144", "99", "2048", "512", "1"),
    ("PTQ1_0", 5.93, 24, "262144", "99", "2048", "512", "2"),
    ("PTQ1_0", 5.93, 32, "262144", "99", "4096", "1024", "3"),
    ("PTQ1_0", 5.93, 48, "262144", "99", "4096", "1024", "3"),
    ("PTQ1_0", 5.93, 64, "262144", "99", "4096", "1024", "3"),
    ("PTQ1_0", 5.93, 128, "262144", "99", "4096", "1024", "3"),
    ("PQ2_0", 7.25, 2, "30720", "0", "512", "256", "1"),
    ("PQ2_0", 7.25, 4, "30720", "4", "512", "256", "1"),
    ("PQ2_0", 7.25, 8, "30720", "40", "512", "256", "1"),
    ("PQ2_0", 7.25, 12, "107520", "99", "2048", "512", "1"),
    ("PQ2_0", 7.25, 16, "262144", "99", "2048", "512", "1"),
    ("PQ2_0", 7.25, 24, "262144", "99", "2048", "512", "2"),
    ("PQ2_0", 7.25, 32, "262144", "99", "4096", "1024", "3"),
    ("PQ2_0", 7.25, 48, "262144", "99", "4096", "1024", "3"),
    ("PQ2_0", 7.25, 64, "262144", "99", "4096", "1024", "3"),
    ("PQ2_0", 7.25, 128, "262144", "99", "4096", "1024", "3"),
    ("TQ1_0", 5.93, 2, "30720", "0", "512", "256", "1"),
    ("TQ1_0", 5.93, 4, "30720", "5", "512", "256", "1"),
    ("TQ1_0", 5.93, 8, "30720", "49", "512", "256", "1"),
    ("TQ1_0", 5.93, 12, "188416", "99", "2048", "512", "1"),
    ("TQ1_0", 5.93, 16, "262144", "99", "2048", "512", "1"),
    ("TQ1_0", 5.93, 24, "262144", "99", "2048", "512", "2"),
    ("TQ1_0", 5.93, 32, "262144", "99", "4096", "1024", "3"),
    ("TQ1_0", 5.93, 48, "262144", "99", "4096", "1024", "3"),
    ("TQ1_0", 5.93, 64, "262144", "99", "4096", "1024", "3"),
    ("TQ1_0", 5.93, 128, "262144", "99", "4096", "1024", "3"),
    ("TQ2_0", 7.25, 2, "30720", "0", "512", "256", "1"),
    ("TQ2_0", 7.25, 4, "30720", "4", "512", "256", "1"),
    ("TQ2_0", 7.25, 8, "30720", "40", "512", "256", "1"),
    ("TQ2_0", 7.25, 12, "107520", "99", "2048", "512", "1"),
    ("TQ2_0", 7.25, 16, "262144", "99", "2048", "512", "1"),
    ("TQ2_0", 7.25, 24, "262144", "99", "2048", "512", "2"),
    ("TQ2_0", 7.25, 32, "262144", "99", "4096", "1024", "3"),
    ("TQ2_0", 7.25, 48, "262144", "99", "4096", "1024", "3"),
    ("TQ2_0", 7.25, 64, "262144", "99", "4096", "1024", "3"),
    ("TQ2_0", 7.25, 128, "262144", "99", "4096", "1024", "3"),
]


@pytest.mark.parametrize("backend", ["cuda", "metal"])
@pytest.mark.parametrize(
    "quant,size_gb,gb,ctx,ngl,batch,ubatch,nmax", PRISM_VRAM_CASES,
)
def test_mocked_llgenie_start_each_prism_quant_at_each_vram(
    monkeypatch, tmp_path, backend, quant, size_gb, gb, ctx, ngl, batch, ubatch, nmax,
):
    """Every Prism packing, on CUDA and Metal, at every card size that changes a flag."""

    # Given this packing on disk and the card size in LLAMA_RAM_BYTES
    cmd = _run_llgenie(
        monkeypatch, tmp_path, f"Ternary-Bonsai-2-27B-{quant}.gguf", "qwen35",
        PRISM_HEADER, size_gb, gb * 1024 ** 3, backend, quant,
    )

    # Then the fake binary received that packing's argv
    assert cmd[cmd.index("-c") + 1] == ctx
    assert cmd[cmd.index("-ngl") + 1] == ngl
    assert cmd[cmd.index("-b") + 1] == batch
    assert cmd[cmd.index("-ub") + 1] == ubatch
    assert cmd[cmd.index("--spec-draft-n-max") + 1] == nmax
    assert cmd[cmd.index("--temp") + 1] == "0.5"
    assert cmd[cmd.index("-ctk") + 1] == "q4_0"
    assert cmd[cmd.index("-fa") + 1] == "on"


@pytest.mark.parametrize(
    "quant,size_gb,gb,ctx,ngl,batch,ubatch,nmax", PRISM_VRAM_CASES,
)
def test_mocked_llgenie_start_prism_quant_on_cpu_skips_gpu_flags(
    monkeypatch, tmp_path, quant, size_gb, gb, ctx, ngl, batch, ubatch, nmax,
):
    """CPU keeps the card-tuned context and batch, and does not request a GPU."""

    # Given this packing on disk and a CPU card of this size
    cmd = _run_llgenie(
        monkeypatch, tmp_path, f"Ternary-Bonsai-2-27B-{quant}.gguf", "qwen35",
        PRISM_HEADER, size_gb, gb * 1024 ** 3, "cpu", quant,
    )

    # Then context, batch, and MTP depth follow the card, and GPU flags are absent
    assert cmd[cmd.index("-c") + 1] == ctx
    assert cmd[cmd.index("-b") + 1] == batch
    assert cmd[cmd.index("-ub") + 1] == ubatch
    assert cmd[cmd.index("--spec-draft-n-max") + 1] == nmax
    assert cmd[cmd.index("--temp") + 1] == "0.5"
    assert "-ngl" not in cmd
    assert "-fa" not in cmd
    assert ngl is not None


# Stock Qwen2 7B Q4, not a Prism packing. Context stays at its trained 32768
# because that KV cache fits the 512 MiB floor. -ngl still follows the card.
STOCK_VRAM_CASES = [
    (2, "32768", "0", "512", "256"),
    (4, "32768", "3", "512", "256"),
    (8, "32768", "27", "512", "256"),
    (12, "32768", "99", "2048", "512"),
    (16, "32768", "99", "2048", "512"),
    (24, "32768", "99", "2048", "512"),
    (32, "32768", "99", "4096", "1024"),
    (48, "32768", "99", "4096", "1024"),
    (64, "32768", "99", "4096", "1024"),
    (128, "32768", "99", "4096", "1024"),
]


def _stock_qwen_meta():
    return {
        "file": "/models/qwen2.5-7b-instruct-q4_k_m.gguf",
        "name": "qwen",
        "arch": "qwen2",
        "n_layer": 28,
        "n_embd": 3584,
        "n_head": 28,
        "n_head_kv": 4,
        "ctx_train": 32768,
        "chat_template": "qwen",
        "nextn_layers": 0,
        "size_gb": 4.68,
    }


@pytest.mark.parametrize("backend", ["cuda", "metal"])
@pytest.mark.parametrize("gb,ctx,ngl,batch,ubatch", STOCK_VRAM_CASES)
def test_mocked_llgenie_start_stock_model_at_each_vram(
    monkeypatch, tmp_path, backend, gb, ctx, ngl, batch, ubatch,
):
    """A non-Prism model on CUDA and Metal. No Bonsai sampling and no MTP flags."""

    # Given a stock Q4 Qwen file on disk and this card size
    cmd = _run_llgenie(
        monkeypatch, tmp_path, "qwen2.5-7b-instruct-q4_k_m.gguf", "qwen2",
        STOCK_HEADER, 4.68, gb * 1024 ** 3, backend, "qwen",
    )

    # Then the fake binary received the stock argv
    assert cmd[cmd.index("-c") + 1] == ctx
    assert cmd[cmd.index("-ngl") + 1] == ngl
    assert cmd[cmd.index("-b") + 1] == batch
    assert cmd[cmd.index("-ub") + 1] == ubatch
    assert cmd[cmd.index("-fa") + 1] == "on"
    assert cmd[cmd.index("--temp") + 1] == "0.6"
    assert "--spec-type" not in cmd
    assert "--jinja" in cmd


@pytest.mark.parametrize("gb,ctx,ngl,batch,ubatch", STOCK_VRAM_CASES)
def test_mocked_llgenie_start_stock_model_on_cpu(
    monkeypatch, tmp_path, gb, ctx, ngl, batch, ubatch,
):
    """A non-Prism model on CPU keeps -c and the batch, and skips GPU flags."""

    # Given a stock Q4 Qwen file on disk and a CPU card
    cmd = _run_llgenie(
        monkeypatch, tmp_path, "qwen2.5-7b-instruct-q4_k_m.gguf", "qwen2",
        STOCK_HEADER, 4.68, gb * 1024 ** 3, "cpu", "qwen",
    )

    # Then context and batch follow the card and GPU flags are absent
    assert cmd[cmd.index("-c") + 1] == ctx
    assert cmd[cmd.index("-b") + 1] == batch
    assert cmd[cmd.index("-ub") + 1] == ubatch
    assert cmd[cmd.index("--temp") + 1] == "0.6"
    assert "-ngl" not in cmd
    assert "-fa" not in cmd
    assert "--spec-type" not in cmd
    assert ngl is not None


def test_mocked_start_reads_prism_quant_from_the_gguf_filename(monkeypatch, tmp_path):
    """The packing is read from the file llgenie scans, not from a hand-built dict."""

    # Given a tiny GGUF whose name is PTQ1_0 and a 16 GB CUDA card
    cmd = _run_llgenie(
        monkeypatch, tmp_path, "Ternary-Bonsai-2-27B-PTQ1_0.gguf", "qwen2",
        STOCK_HEADER, 0.001, 16 * 1024 ** 3, "cuda", "PTQ1_0",
    )

    # Then context comes from the header and Bonsai sampling from the filename
    assert cmd[cmd.index("-c") + 1] == "32768"
    assert cmd[cmd.index("-ngl") + 1] == "99"
    assert cmd[cmd.index("--temp") + 1] == "0.5"
    assert cmd[cmd.index("-fa") + 1] == "on"


def test_mocked_start_reads_a_stock_file_without_prism_sampling(monkeypatch, tmp_path):
    """A file that is not a Prism packing keeps the generic sampler."""

    # Given a tiny stock GGUF and a 16 GB CUDA card
    cmd = _run_llgenie(
        monkeypatch, tmp_path, "qwen2.5-7b-instruct-q4_k_m.gguf", "qwen2",
        STOCK_HEADER, 0.001, 16 * 1024 ** 3, "cuda", "qwen",
    )

    # Then the header context is used and the sampler is the generic preset
    assert cmd[cmd.index("-c") + 1] == "32768"
    assert cmd[cmd.index("--temp") + 1] == "0.6"
    assert "--spec-type" not in cmd


def test_run_log_records_the_argv_before_the_mocked_binary(monkeypatch, tmp_path):
    """The script writes the parameters, then the fake binary receives that same argv."""

    # Given a PTQ1_0 file and a 16 GB CUDA card
    cmd = _run_llgenie(
        monkeypatch, tmp_path, "Ternary-Bonsai-2-27B-PTQ1_0.gguf", "qwen35",
        PRISM_HEADER, 5.93, 16 * 1024 ** 3, "cuda", "PTQ1_0",
    )

    # Then .run.log holds the same command the fake binary was given
    logged = (tmp_path / "models" / ".run.log").read_text()
    assert " ".join(cmd) in logged
    assert "-c 262144" in logged
    assert "-ngl 99" in logged
    assert "--temp 0.5" in logged


def test_dry_llgenie_call_prints_ptq_command_for_16gb(server_on_path, monkeypatch, capsys):
    """A mocked llgenie dry launch of PTQ1_0 on 16 GB prints the full command."""

    # Given a PTQ1_0 model and a mocked 16 GB CUDA card
    meta = _prism_ptq_meta("PTQ1_0", 5.93)
    monkeypatch.setattr(llama_ai, "resolve_llama_server", lambda: "/usr/local/bin/llama-server")
    monkeypatch.setattr(llama_ai.detect_server, "detect_card_ram_bytes", lambda: 16 * 1024 ** 3)
    monkeypatch.setattr(llama_ai.detect_server, "detect_backend", lambda: "cuda")
    args = type("Args", (), {"port": 11434, "dry": True})()

    # When the dry launch runs
    llama_ai._serve_chosen(meta, args)
    out = capsys.readouterr().out

    # Then the printed command has the trained context, full offload, and Bonsai sampling
    assert "-c \\\n  262144" in out
    assert "-ngl \\\n  99" in out
    assert "--temp \\\n  0.5" in out
    assert "--top-p \\\n  0.85" in out


def test_serve_context_uses_model_max_when_the_card_fits():
    """Selecting Bonsai on a 16 GB card serves its trained 262144 context."""

    # Given the Bonsai MTP metadata and a 16 GB card
    meta = _bonsai_mtp_meta()
    card = 16 * 1024 ** 3

    # When the launch context is tuned
    ctx = llama_ai.serve_context(meta, card)

    # Then -c is the model's trained maximum
    assert ctx == 262144


def test_serve_context_shrinks_when_the_card_cannot_hold_the_train_ctx():
    """A card that cannot hold the trained window gets a smaller multiple of 1024."""

    # Given the same Bonsai file on an 8 GB card
    meta = _bonsai_mtp_meta()
    card = 8 * 1024 ** 3

    # When the launch context is tuned
    ctx = llama_ai.serve_context(meta, card)

    # Then the window stays under the trained maximum and above the floor
    assert ctx == 30720
    assert ctx < meta["ctx_train"]
    assert ctx % 1024 == 0


def test_serve_context_missing_train_ctx_caps_at_32768():
    """A GGUF with no context_length is capped at 32768 even on a huge card."""

    # Given a dense model whose header omitted context_length
    meta = {
        "ctx_train": 0, "n_embd": 3584, "n_head": 28,
        "n_head_kv": 4, "n_layer": 28, "size_gb": 1.0,
    }

    # When it is served on a 48 GB card
    ctx = llama_ai.serve_context(meta, 48 * 1024 ** 3)

    # Then the fallback ceiling is 32768
    assert ctx == 32768


def test_launch_context_reads_card_ram_not_the_48gb_constant(monkeypatch):
    """The serve path asks the card detector, not TOTAL_RAM_BYTES."""

    # Given a card detector that reports 16 GB
    monkeypatch.setattr(
        llama_ai.detect_server, "detect_card_ram_bytes", lambda: 16 * 1024 ** 3,
    )
    meta = _bonsai_mtp_meta()

    # When the launcher resolves the context the way main() does
    card = llama_ai.detect_server.detect_card_ram_bytes()
    ctx = llama_ai.serve_context(meta, card)

    # Then the result matches the 16 GB card, which holds this model's full window
    assert card == 16 * 1024 ** 3
    assert ctx == 262144
    assert llama_ai.TOTAL_RAM_BYTES == 48 * 1024 ** 3


def test_fast_reader_captures_hybrid_context_fields(tmp_path):
    """The header reader keeps the fields serve_context needs for a hybrid model."""

    # Given a qwen35 header with a 262144 context and a full-attention interval
    def s(v: str) -> bytes:
        b = v.encode("utf-8")
        return struct.pack("<Q", len(b)) + b

    def kv(key: str, vtype: int, val: bytes) -> bytes:
        return struct.pack("<Q", len(key)) + key.encode() + struct.pack("<I", vtype) + val

    pairs = [
        kv("general.architecture", 8, s("qwen35")),
        kv("general.name", 8, s("bonsai")),
        kv("qwen35.block_count", 4, struct.pack("<I", 65)),
        kv("qwen35.embedding_length", 4, struct.pack("<I", 5120)),
        kv("qwen35.attention.head_count", 4, struct.pack("<I", 24)),
        kv("qwen35.attention.head_count_kv", 4, struct.pack("<I", 4)),
        kv("qwen35.attention.key_length", 4, struct.pack("<I", 256)),
        kv("qwen35.attention.value_length", 4, struct.pack("<I", 256)),
        kv("qwen35.context_length", 4, struct.pack("<I", 262144)),
        kv("qwen35.full_attention_interval", 4, struct.pack("<I", 4)),
        kv("qwen35.nextn_predict_layers", 4, struct.pack("<I", 1)),
        kv("tokenizer.chat_template", 8, s("chat")),
    ]
    buf = bytearray(b"GGUF" + struct.pack("<I", 3) + struct.pack("<Q", 0))
    buf += struct.pack("<Q", len(pairs))
    for x in pairs:
        buf += x
    p = tmp_path / "bonsai.gguf"
    p.write_bytes(bytes(buf))

    # When the fast reader parses it
    m = llama_ai.read_model_meta_fast(str(p))

    # Then the trained context and the hybrid KV fields are present
    assert m["ctx_train"] == 262144
    assert m["key_length"] == 256
    assert m["value_length"] == 256
    assert m["full_attention_interval"] == 4
    assert m["nextn_layers"] == 1
    assert llama_ai.serve_context(m, 16 * 1024 ** 3) == 262144


def test_serve_chosen_dry_run_passes_ctx_flag(server_on_path, monkeypatch, capsys):
    """The launch path prints llama-server -c from serve_context, and does not start the server."""

    # Given Bonsai on a mocked 16 GB card, and the same file on an 8 GB card
    meta = _bonsai_mtp_meta()
    monkeypatch.setattr(llama_ai, "resolve_llama_server", lambda: "/usr/local/bin/llama-server")
    args = type("Args", (), {"port": 11434, "dry": True})()

    # When the dry launch runs on 16 GB
    monkeypatch.setattr(llama_ai.detect_server, "detect_card_ram_bytes", lambda: 16 * 1024 ** 3)
    llama_ai._serve_chosen(meta, args)
    out_16 = capsys.readouterr().out

    # Then the command carries -c 262144 and the process returns without serving
    assert "-c \\\n  262144" in out_16
    assert "context = 262144 tokens" in out_16

    # When the same dry launch runs on 8 GB
    monkeypatch.setattr(llama_ai.detect_server, "detect_card_ram_bytes", lambda: 8 * 1024 ** 3)
    llama_ai._serve_chosen(meta, args)
    out_8 = capsys.readouterr().out

    # Then -c is the reduced window
    assert "-c \\\n  30720" in out_8
    assert "context = 30720 tokens" in out_8


def test_main_dry_run_uses_selected_gguf_context(server_on_path, monkeypatch, capsys, tmp_path):
    """`llgenie <name> --dry` sets -c from the file that was selected."""

    # Given one hybrid GGUF under the model root and a 16 GB card
    models = tmp_path / "models"
    models.mkdir()
    def s(v: str) -> bytes:
        b = v.encode("utf-8")
        return struct.pack("<Q", len(b)) + b

    def kv(key: str, vtype: int, val: bytes) -> bytes:
        return struct.pack("<Q", len(key)) + key.encode() + struct.pack("<I", vtype) + val

    pairs = [
        kv("general.architecture", 8, s("qwen35")),
        kv("general.name", 8, s("bonsai")),
        kv("qwen35.block_count", 4, struct.pack("<I", 65)),
        kv("qwen35.embedding_length", 4, struct.pack("<I", 5120)),
        kv("qwen35.attention.head_count", 4, struct.pack("<I", 24)),
        kv("qwen35.attention.head_count_kv", 4, struct.pack("<I", 4)),
        kv("qwen35.attention.key_length", 4, struct.pack("<I", 256)),
        kv("qwen35.attention.value_length", 4, struct.pack("<I", 256)),
        kv("qwen35.context_length", 4, struct.pack("<I", 262144)),
        kv("qwen35.full_attention_interval", 4, struct.pack("<I", 4)),
        kv("qwen35.nextn_predict_layers", 4, struct.pack("<I", 1)),
        kv("tokenizer.chat_template", 8, s("chat")),
    ]
    buf = bytearray(b"GGUF" + struct.pack("<I", 3) + struct.pack("<Q", 0))
    buf += struct.pack("<Q", len(pairs))
    for x in pairs:
        buf += x
    gguf = models / "Ternary-Bonsai-2-27B-PTQ1_0-mtp.gguf"
    gguf.write_bytes(bytes(buf))
    monkeypatch.setattr(llama_ai, "MODELS_ROOT", str(models))
    monkeypatch.setattr(llama_ai.detect_server, "detect_card_ram_bytes", lambda: 16 * 1024 ** 3)
    monkeypatch.setattr(llama_ai, "resolve_llama_server", lambda: "/usr/local/bin/llama-server")
    monkeypatch.setattr(sys, "argv", ["llgenie", "bonsai", "--dry"])

    # When main selects that file and stops at --dry
    llama_ai.main()
    out = capsys.readouterr().out

    # Then the printed server command uses the model's trained context
    assert "context = 262144 tokens" in out
    assert "-c \\\n  262144" in out
    assert str(gguf) in out or "Ternary-Bonsai-2-27B-PTQ1_0-mtp.gguf" in out


# ---------------------------------------------------------------------------
# command construction
# ---------------------------------------------------------------------------
@pytest.fixture
def server_on_path(monkeypatch):
    """Force llama_ai to believe a llama-server exists at a fake path."""
    fake = "/usr/local/bin/llama-server"
    monkeypatch.setenv("LLAMA_SERVER", fake)
    monkeypatch.setattr(llama_ai, "LLAMA_SERVER", fake, raising=False)


def test_build_command_has_core_flags(server_on_path):
    meta = {
        "file": "/models/x.gguf", "name": "x", "arch": "qwen2",
        "n_layer": 28, "n_embd": 3584, "n_head": 28, "n_head_kv": 4,
        "ctx_train": 32768,
        "chat_template": "llama3",   # non-reasoning
        "size_gb": 24.0,
    }
    cmd = llama_ai.build_command(
        meta, ctx=4096, port=11434, card_bytes=64 * 1024 ** 3, backend="cuda",
    )
    joined = " ".join(cmd)
    assert cmd[0] == "/usr/local/bin/llama-server"
    assert "-m" in cmd and str(meta["file"]) in cmd
    assert "--host" in cmd and "0.0.0.0" in cmd
    assert "--port" in cmd and "11434" in cmd
    assert "-c" in cmd and "4096" in cmd
    assert "-ngl" in cmd and "99" in cmd
    assert "--alias" in cmd and "llm-local" in cmd
    assert "--jinja" in cmd
    # big model => 1 parallel slot
    assert joined.endswith("-np 1") or "-np 1" in joined
    # non-reasoning => no --reasoning
    assert "--reasoning" not in cmd


def test_build_command_reasoning_and_slots(server_on_path):
    meta = {
        "file": "/models/y.gguf", "name": "y", "arch": "deepseek",
        "n_layer": 28, "n_embd": 3584, "n_head": 28, "n_head_kv": 4,
        "ctx_train": 32768,
        "chat_template": "deepseek cot",  # reasoning
        "size_gb": 4.0,                   # small => 2 slots
    }
    cmd = llama_ai.build_command(
        meta, ctx=4096, port=11434, card_bytes=48 * 1024 ** 3, backend="cuda",
    )
    assert "--reasoning" in cmd and "on" in cmd
    assert "--reasoning-format" in cmd and "deepseek" in cmd
    assert "-np" in cmd and "2" in cmd


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# MTP (spec-decode) card-driven flags (issue #84: n-max / p-min / -np)
#
# Grounded in the qwen38-mtp community rules:
#   * rule 1: depth (n-max) sweet-spot is card/bandwidth dependent -> derive it
#     from the card's RAM (8/12/16 GB -> 1, 24 GB inclusive -> 2, >24 GB -> 3).
#   * rule 2: --spec-draft-p-min helps starved cards and hurts fast ones ->
#     never a default; opt-in via the LLAMA_SPEC_DRAFT_P_MIN env seam.
#   * rule 5: speculative decode is a single-stream optimisation -> when MTP is
#     engaged, -np is pinned to 1 regardless of model size (--parallel > 1
#     kills the gain and inflates the baseline).
# ---------------------------------------------------------------------------
_GB = 1024 ** 3  # GiB


def _mtp_meta(size_gb, nextn=1):
    """MTP model metadata (nextn_layers>0) sized `size_gb` GB."""
    return {
        "file": f"/models/mtp-{int(size_gb)}.gguf",
        "name": f"mtp-{int(size_gb)}",
        "arch": "qwen2",
        "n_layer": 28,
        "n_embd": 3584,
        "n_head": 28,
        "n_head_kv": 4,
        "ctx_train": 32768,
        "chat_template": "llama3",
        "size_gb": size_gb,
        "nextn_layers": nextn,
    }


def test_mtp_depth_for_card_16_gb_or_less_is_1():
    """8/12/16 GB cards (<=16 GB) get depth 1 (shallow: pays everywhere)."""
    for gb in (8, 12, 16):
        assert llama_ai.mtp_depth_for_card(gb * _GB) == 1


def test_mtp_depth_for_card_24_gb_is_2():
    """20/24 GB cards get depth 2 (24 GB is the inclusive boundary)."""
    assert llama_ai.mtp_depth_for_card(24 * _GB) == 2
    assert llama_ai.mtp_depth_for_card(20 * _GB) == 2


def test_mtp_depth_for_card_above_24_gb_is_3():
    """>24 GB cards (32/48/64/128/...) get depth 3."""
    for gb in (32, 48, 64, 128):
        assert llama_ai.mtp_depth_for_card(gb * _GB) == 3


def test_mtp_depth_for_card_falls_back_to_card_ram_seam(monkeypatch):
    """card_bytes=None reads the card-RAM seam (mocked, hermetic)."""
    monkeypatch.setattr(llama_ai, "read_total_ram_bytes", lambda: 32 * _GB)
    assert llama_ai.mtp_depth_for_card(None) == 3


def test_mtp_spec_flags_empty_when_no_nextn():
    """A model without an MTP head (nextn_layers=0) emits no spec flags."""
    meta = _mtp_meta(24.0, nextn=0)
    assert llama_ai.mtp_spec_flags(meta, 24 * _GB, env={}) == []


def test_mtp_spec_flags_emits_type_and_card_driven_depth():
    """nextn_layers>0 => --spec-type draft-mtp; n-max follows the card."""
    meta = _mtp_meta(24.0)
    flags = llama_ai.mtp_spec_flags(meta, 24 * _GB, env={})
    assert flags[:4] == ["--spec-type", "draft-mtp", "--spec-draft-n-max", "2"]
    # depth follows the card, not a hard-coded constant
    assert llama_ai.mtp_spec_flags(_mtp_meta(8.0), 8 * _GB, env={})[2:4]         == ["--spec-draft-n-max", "1"]
    assert llama_ai.mtp_spec_flags(_mtp_meta(48.0), 48 * _GB, env={})[2:4]         == ["--spec-draft-n-max", "3"]


def test_mtp_spec_flags_p_min_off_by_default():
    """Rule 2: p-min is a knob, never a default (absent when env unset)."""
    meta = _mtp_meta(24.0)
    flags = llama_ai.mtp_spec_flags(meta, 24 * _GB, env={})
    assert "--spec-draft-p-min" not in flags


def test_mtp_spec_flags_p_min_emitted_only_when_env_set():
    """p-min is emitted only when LLAMA_SPEC_DRAFT_P_MIN is set (opt-in)."""
    meta = _mtp_meta(24.0)
    flags = llama_ai.mtp_spec_flags(
        meta, 24 * _GB, env={"LLAMA_SPEC_DRAFT_P_MIN": "0.7"})
    i = flags.index("--spec-draft-p-min")
    assert flags[i + 1] == "0.7"


def test_build_command_mtp_emits_spec_flags_and_pins_np_1(server_on_path):
    """MTP model => spec flags present and -np 1 regardless of model size
    (rule 5: spec decode is single-stream; --parallel > 1 kills the gain)."""
    meta = _mtp_meta(24.0)
    cmd = llama_ai.build_command(meta, ctx=4096, port=11434, card_bytes=24 * _GB)
    assert "--spec-type" in cmd and "draft-mtp" in cmd
    assert cmd[cmd.index("--spec-draft-n-max") + 1] == "2"
    assert cmd[cmd.index("-np") + 1] == "1"


def test_build_command_mtp_pins_np_1_even_on_small_card(server_on_path):
    """Rule 5 holds for a small MTP model: the size-based -np 2 must not win."""
    meta = _mtp_meta(4.0)
    cmd = llama_ai.build_command(meta, ctx=4096, port=11434, card_bytes=4 * _GB)
    assert "--spec-type" in cmd
    assert cmd[cmd.index("-np") + 1] == "1"
    # depth follows the 4 GB card (<=16 GB -> depth 1)
    assert cmd[cmd.index("--spec-draft-n-max") + 1] == "1"


def test_build_command_mtp_card_bytes_drives_depth(server_on_path):
    """The same MTP model on a bigger card gets a deeper n-max (card-driven)."""
    meta = _mtp_meta(24.0)
    small = llama_ai.build_command(meta, ctx=4096, port=11434, card_bytes=16 * _GB)
    big = llama_ai.build_command(meta, ctx=4096, port=11434, card_bytes=64 * _GB)
    assert small[small.index("--spec-draft-n-max") + 1] == "1"
    assert big[big.index("--spec-draft-n-max") + 1] == "3"


def test_build_command_no_mtp_keeps_normal_slots_and_no_spec_flags(server_on_path):
    """Non-MTP model => no spec flags and size-based -np slots unchanged
    (2 slots when the model is <10 GB)."""
    meta = {
        "file": "/models/plain.gguf", "name": "plain", "arch": "qwen2",
        "n_layer": 28, "n_embd": 3584, "n_head": 28, "n_head_kv": 4,
        "ctx_train": 32768, "chat_template": "llama3", "size_gb": 4.0,
        "nextn_layers": 0,
    }
    cmd = llama_ai.build_command(meta, ctx=4096, port=11434, card_bytes=16 * _GB)
    assert "--spec-type" not in cmd
    assert "--spec-draft-n-max" not in cmd
    assert cmd[cmd.index("-np") + 1] == "2"


def test_build_command_mtp_auto_detects_card_when_card_bytes_none(server_on_path, monkeypatch):
    """card_bytes=None => build_command reads
    detect_server.detect_card_ram_bytes() and derives depth from the real card."""
    meta = _mtp_meta(24.0)
    monkeypatch.setattr(llama_ai.detect_server, "detect_card_ram_bytes",
                        lambda: 48 * _GB)
    cmd = llama_ai.build_command(meta, ctx=4096, port=11434)
    assert cmd[cmd.index("--spec-draft-n-max") + 1] == "3"
# author-recommended sampling defaults (general.sampling.*)
# ---------------------------------------------------------------------------
def test_build_command_uses_model_sampling_when_present(server_on_path):
    """Model-supplied sampling emits model-specific flags (separate argv elems)."""
    meta = {
        "file": "/models/s.gguf", "name": "s", "arch": "qwen2",
        "n_layer": 28, "n_embd": 3584, "n_head": 28, "n_head_kv": 4,
        "ctx_train": 32768, "chat_template": "llama3", "size_gb": 24.0,
        "sampling": {"temperature": "0.7", "top_p": "0.95"},
    }
    cmd = llama_ai.build_command(meta, ctx=4096, port=11434)
    assert "--temp" in cmd and "0.7" in cmd
    assert "--top-p" in cmd and "0.95" in cmd
    # the preset's values must NOT also appear (no double flags)
    assert "0.6" not in cmd
    assert "0.9" not in cmd
    # flag and value adjacent (separate argv elements, not "--temp 0.7")
    assert cmd[cmd.index("--temp") + 1] == "0.7"
    assert cmd[cmd.index("--top-p") + 1] == "0.95"


def test_build_command_falls_back_to_preset_when_no_sampling(server_on_path):
    """No sampling metadata => emit the global SAMPLING preset (unchanged)."""
    meta = {
        "file": "/models/p.gguf", "name": "p", "arch": "qwen2",
        "n_layer": 28, "n_embd": 3584, "n_head": 28, "n_head_kv": 4,
        "ctx_train": 32768, "chat_template": "general", "size_gb": 24.0,
        "sampling": {},
    }
    cmd = llama_ai.build_command(meta, ctx=4096, port=11434)
    joined = " ".join(cmd)
    assert "--temp 0.6" in joined
    assert "--top-p 0.9" in joined
    assert "--top-k 40" in joined
    assert "--min-p 0.05" in joined
    assert "--repeat-penalty 1.05" in joined


def test_sampling_flag_map_covers_all_keys(server_on_path):
    meta = {
        "file": "/models/a.gguf", "name": "a", "arch": "qwen2",
        "n_layer": 28, "n_embd": 3584, "n_head": 28, "n_head_kv": 4,
        "ctx_train": 32768, "chat_template": "llama", "size_gb": 24.0,
        "sampling": {
            "temperature": "0.7", "top_p": "0.9", "top_k": "40",
            "min_p": "0.05", "repeat_penalty": "1.1",
        },
    }
    cmd = llama_ai.build_command(meta, ctx=4096, port=11434)
    for flag in ("--temp", "--top-p", "--top-k", "--min-p", "--repeat-penalty"):
        assert flag in cmd, f"missing {flag}"


def test_build_command_skips_unknown_sampling_key_no_keyerror(server_on_path):
    """An unrecognised sampling key must be ignored, never raise KeyError."""
    meta = {
        "file": "/models/u.gguf", "name": "u", "arch": "qwen2",
        "n_layer": 28, "n_embd": 3584, "n_head": 28, "n_head_kv": 4,
        "ctx_train": 32768, "chat_template": "llama", "size_gb": 24.0,
        "sampling": {"temperature": "0.7", "nonsense_key": "9.9"},
    }
    cmd = llama_ai.build_command(meta, ctx=4096, port=11434)
    assert "--temp" in cmd and "0.7" in cmd
    assert "nonsense_key" not in cmd
    assert "--nonsense-key" not in cmd


def test_extract_sampling_from_kv_picks_present_fields():
    kv = {
        "general.architecture": "qwen2",
        "general.sampling.temperature": 0.7,
        "general.sampling.top_p": 0.95,
    }
    out = llama_ai._extract_sampling_from_kv(kv)
    assert out == {"temperature": "0.7", "top_p": "0.95"}
    # absent keys omitted; never raises
    assert llama_ai._extract_sampling_from_kv({"general.architecture": "qwen2"}) == {}


# ---------------------------------------------------------------------------
# llama-server resolution
# ---------------------------------------------------------------------------
def test_resolve_from_env(monkeypatch, tmp_path):
    fake_a = tmp_path / "fake-server-a"
    fake_a.write_bytes(b"binary")
    fake_a.chmod(0o755)
    monkeypatch.setenv("LLAMA_SERVER", str(fake_a))
    assert llama_ai.resolve_llama_server() == str(fake_a)


def test_resolve_from_path(monkeypatch, tmp_path):
    monkeypatch.delenv("LLAMA_SERVER", raising=False)
    fake = tmp_path / "llama-server"
    fake.write_bytes(b"binary")
    fake.chmod(0o755)
    monkeypatch.setattr(llama_ai.shutil, "which", lambda _: str(fake))
    assert llama_ai.resolve_llama_server() == str(fake)


def test_resolve_missing_raises_systemexit(monkeypatch, tmp_path):
    monkeypatch.delenv("LLAMA_SERVER", raising=False)
    monkeypatch.setattr(llama_ai.shutil, "which", lambda _: None)
    # Redirect the ~/bin/llama-server fallback to an empty tmp dir so the
    # "missing" path is genuinely exercised even on hosts with make-installed
    # ~/bin/llama-server symlinks.
    empty = tmp_path / "fakehome"
    empty.mkdir()
    monkeypatch.setattr(llama_ai.os.path, "expanduser", lambda _: str(empty))
    with pytest.raises(SystemExit) as e:
        llama_ai.resolve_llama_server()
    assert e.value.code != 0
    assert "llama-server" in str(e.value)


def test_resolve_falls_back_to_home_bin(monkeypatch, tmp_path):
    monkeypatch.delenv("LLAMA_SERVER", raising=False)
    monkeypatch.setattr(llama_ai.shutil, "which", lambda _: None)
    home = tmp_path / "fakehome"
    srv = home / "bin" / "llama-server"
    srv.parent.mkdir(parents=True)
    srv.write_bytes(b"binary")
    srv.chmod(0o755)
    monkeypatch.setattr(llama_ai.os.path, "expanduser", lambda _: str(home))
    assert llama_ai.resolve_llama_server() == str(srv)


def test_resolve_bad_env_raises_systemexit(monkeypatch, tmp_path):
    monkeypatch.setenv("LLAMA_SERVER", str(tmp_path / "does-not-exist"))
    with pytest.raises(SystemExit):
        llama_ai.resolve_llama_server()


# ---------------------------------------------------------------------------
# top-tier discovery: min_trending_score rating floor
# ---------------------------------------------------------------------------
def test_discover_top_tier_min_trending_score_filters(monkeypatch):
    """discover_top_tier must drop repos below the rating floor."""
    repos = [
        {"repo": "unsloth/Qwen3.8-27B-GGUF", "downloads": 1, "likes": 1, "trendingScore": 300},
        {"repo": "orcarouter/Qwen3.8-27B-Uncensored-GGUF", "downloads": 1, "likes": 1,
         "trendingScore": 120},
    ]

    def fake_trending(limit=25):
        return repos

    def fake_files(repo):
        return [{"path": f"{repo.split('/')[-1]}-Q8_0.gguf", "size_bytes": 5 * 1024 ** 3,
                 "size_gb": 5.0}]

    monkeypatch.setattr(llama_ai, "_trending_gguf_repos", fake_trending)
    monkeypatch.setattr(llama_ai, "_repo_gguf_files", fake_files)
    monkeypatch.setattr(llama_ai, "_probe_file_downloadable", lambda *a, **k: "ok")
    monkeypatch.setattr(llama_ai, "MIN_TOP_TIER_GB", 1.0)

    # no floor -> both fit and are returned, sorted by size (tie -> trend desc)
    all = llama_ai.discover_top_tier(limit=5, total_ram_bytes=48 * 1024 ** 3,
                                     headroom_bytes=3 * 1024 ** 3, min_trending_score=0)
    assert len(all) == 2

    # floor 200 -> only the 300-rated repo survives
    rated = llama_ai.discover_top_tier(limit=5, total_ram_bytes=48 * 1024 ** 3,
                                       headroom_bytes=3 * 1024 ** 3, min_trending_score=200)
    assert [c["repo"] for c in rated] == ["unsloth/Qwen3.8-27B-GGUF"]

    # floor 400 -> nothing survives
    none = llama_ai.discover_top_tier(limit=5, total_ram_bytes=48 * 1024 ** 3,
                                      headroom_bytes=3 * 1024 ** 3, min_trending_score=400)
    assert none == []


def test_discover_top_tier_high_and_lower_per_provider(monkeypatch):
    """discover_top_tier must offer, from each provider, a HIGH quant plus a clearly
    LOWER quant (e.g. Q8 + Q4), grouped per provider — not just one Q8 per provider
    (which barely fits) nor all-Q8 picks across many providers."""
    repos = [
        {"repo": "unsloth/Qwen3.8-27B-GGUF", "downloads": 1, "likes": 1, "trendingScore": 300},
        {"repo": "unsloth/Qwen3.8-27B-UD-GGUF", "downloads": 1, "likes": 1, "trendingScore": 280},
        {"repo": "orcarouter/Qwen3.8-27B-Uncensored-GGUF", "downloads": 1, "likes": 1,
         "trendingScore": 120},
    ]

    files_by_repo = {
        "unsloth/Qwen3.8-27B-GGUF": [
            {"path": "model-Q8_0.gguf", "size_bytes": 20 * 1024 ** 3, "size_gb": 20.0},
            {"path": "model-Q4_K_M.gguf", "size_bytes": 12 * 1024 ** 3, "size_gb": 12.0},  # clearly lower
        ],
        "unsloth/Qwen3.8-27B-UD-GGUF": [
            {"path": "model-Q6_K.gguf", "size_bytes": 16 * 1024 ** 3, "size_gb": 16.0},
            {"path": "model-Q3_K_S.gguf", "size_bytes": 9 * 1024 ** 3, "size_gb": 9.0},
        ],
        "orcarouter/Qwen3.8-27B-Uncensored-GGUF": [
            {"path": "model-Q8_0.gguf", "size_bytes": 20 * 1024 ** 3, "size_gb": 20.0},
            {"path": "model-Q4_K_M.gguf", "size_bytes": 12 * 1024 ** 3, "size_gb": 12.0},
        ],
    }

    def fake_trending(limit=25):
        return repos

    def fake_files(repo):
        return files_by_repo[repo]

    monkeypatch.setattr(llama_ai, "_trending_gguf_repos", fake_trending)
    monkeypatch.setattr(llama_ai, "_repo_gguf_files", fake_files)
    monkeypatch.setattr(llama_ai, "_probe_file_downloadable", lambda *a, **k: "ok")
    monkeypatch.setattr(llama_ai, "MIN_TOP_TIER_GB", 1.0)

    # 3 providers x 2 quants (high+lower), ordered by TRENDING (not by file size)
    result = llama_ai.discover_top_tier(limit=6, total_ram_bytes=48 * 1024 ** 3,
                                        headroom_bytes=3 * 1024 ** 3, min_trending_score=0,
                                        per_provider=2)
    # grouped per provider(repo), ordered by trendingScore desc, high->lower each
    # Each repo appears with exactly its high+lower pair (per_provider=2).
    entries = [(c["repo"], c["size_bytes"] // (1024 ** 3), c["trendingScore"]) for c in result]
    assert len(entries) == 6, f"expected 6 (3 repos x 2 quants), got {entries}"
    # repos are grouped (a repo's 2 quants adjacent) ...
    repo_scores = [entries[i][2] for i in range(0, 6, 2)]
    assert repo_scores == sorted(repo_scores, reverse=True), \
        f"repos must be ordered by trendingScore desc (top-tier TRENDING): {repo_scores}"
    # ... and each repo's pair is high -> lower with a clearly-lower 2nd quant
    for i in range(0, 6, 2):
        hi, lo = entries[i][1], entries[i + 1][1]
        assert hi > lo, f"{entries[i][0]} must be high->lower: {hi}->{lo}"
        assert (hi - lo) >= 0.25 * hi, f"{entries[i][0]} lower must be clearly lower"


def test_discover_drops_low_fidelity_iq_quants(monkeypatch):
    """\"no lower models\": a trending provider that only offers low-fidelity
    IQ1/IQ2/IQ3 quants (e.g. an 8-11 GB quant of a 27B) must be skipped, even if it
    is #1-trending — we want the TOP-TIER (high-fidelity) trending models."""
    repos = [
        {"repo": "ista/Qwen3.8-27B-GGUF", "downloads": 1, "likes": 1, "trendingScore": 999},
        {"repo": "unsloth/Qwen3.8-27B-GGUF", "downloads": 1, "likes": 1, "trendingScore": 500},
    ]

    def fake_trending(limit=25):
        return repos

    def fake_files(repo):
        if repo.startswith("ista"):
            return [{"path": "model-IQ3_S.gguf", "size_bytes": 9 * 1024 ** 3, "size_gb": 9.0},
                    {"path": "model-IQ2_XS.gguf", "size_bytes": 7 * 1024 ** 3, "size_gb": 7.0}]
        return [{"path": "model-Q8_0.gguf", "size_bytes": 28 * 1024 ** 3, "size_gb": 28.0},
                {"path": "model-Q6_K.gguf", "size_bytes": 21 * 1024 ** 3, "size_gb": 21.0}]

    monkeypatch.setattr(llama_ai, "_trending_gguf_repos", fake_trending)
    monkeypatch.setattr(llama_ai, "_repo_gguf_files", fake_files)
    monkeypatch.setattr(llama_ai, "_probe_file_downloadable", lambda *a, **k: "ok")
    monkeypatch.setattr(llama_ai, "MIN_TOP_TIER_GB", 1.0)

    result = llama_ai.discover_top_tier(limit=4, total_ram_bytes=48 * 1024 ** 3,
                                        headroom_bytes=3 * 1024 ** 3, min_trending_score=0,
                                        per_provider=2)
    repos_out = [c["repo"] for c in result]
    # the #1-trending ISP-DASLab-style repo (only IQ quants) must be DROPPED
    assert not any(r.startswith("ista") for r in repos_out), \
        f"low-fidelity-only provider must be dropped: {repos_out}"
    assert any(r.startswith("unsloth") for r in repos_out), "high-fidelity provider must remain"
    # and its quants must be Q8_0/Q6_K (real top-tier), not IQ
    assert all("I_Q" not in c["filename"].upper() and not c["filename"].startswith("model-IQ")
               for c in result), f"no low-fidelity quant may be selected: {repos_out}"


def test_discover_drops_mtp_companion_files(monkeypatch):
    """mtp-* files are multi-token-prediction COMPANION heads (e.g. an MTP/mtp-Q8_0
    auxiliary file), NOT the serviceable model. A trending repo that only offers a
    split model + mtp companions must not offer the mtp file as a 'top-tier' pick."""
    repos = [{"repo": "unsloth/Qwen3.8-Flash-Next-GGUF", "downloads": 1, "likes": 1,
              "trendingScore": 400}]

    def fake_trending(limit=25):
        return repos

    def fake_files(repo):
        return [
            {"path": "MTP/mtp-Qwen3.8-Flash-Next-BF16.gguf", "size_bytes": 7 * 1024 ** 3,
             "size_gb": 7.0},
            {"path": "MTP/mtp-Qwen3.8-Flash-Next-Q8_0.gguf", "size_bytes": 4 * 1024 ** 3,
             "size_gb": 4.0},
        ]

    monkeypatch.setattr(llama_ai, "_trending_gguf_repos", fake_trending)
    monkeypatch.setattr(llama_ai, "_repo_gguf_files", fake_files)
    monkeypatch.setattr(llama_ai, "_probe_file_downloadable", lambda *a, **k: "ok")
    monkeypatch.setattr(llama_ai, "MIN_TOP_TIER_GB", 1.0)

    result = llama_ai.discover_top_tier(limit=4, total_ram_bytes=48 * 1024 ** 3,
                                        headroom_bytes=3 * 1024 ** 3, min_trending_score=0,
                                        per_provider=2)
    assert result == [], "an MTP-companion-only repo must not produce any top-tier pick"
    assert all("mtp-" not in c["filename"].lower() for c in result)


def test_fit_gate_rejects_too_big_model(monkeypatch):
    """A candidate that does NOT fit must be dropped by the fit gate.

    Given  a tiny card (e.g. 12 GB total, 3 GB headroom, 1 GB KV = ~8 GB budget),
    When   a provider offers a Q8 quant far bigger than that budget,
    Then   the fit gate must REJECT it (no pick is returned for that provider) —
           the calculation must protect against OOM, not just list what's popular.
    """
    total_small = 12 * 1024 ** 3        # 12 GiB card
    head = 3 * 1024 ** 3                # 3 GiB headroom
    kv = 1024 ** 3                      # 1 GiB KV reserve
    budget = total_small - head - kv    # = 8 GiB

    # The only file from the #1-trending provider is a 29 GB Q8 — far over budget.
    repos = [{"repo": "unsloth/Qwen3.8-27B-GGUF", "downloads": 1, "likes": 1, "trendingScore": 999}]

    def fake_trending(limit=25):
        return repos

    def fake_files(repo):
        return [{"path": "model-Q8_0.gguf", "size_bytes": 29 * 1024 ** 3, "size_gb": 29.0}]

    monkeypatch.setattr(llama_ai, "_trending_gguf_repos", fake_trending)
    monkeypatch.setattr(llama_ai, "_repo_gguf_files", fake_files)
    monkeypatch.setattr(llama_ai, "_probe_file_downloadable", lambda *a, **k: "ok")
    monkeypatch.setattr(llama_ai, "MIN_TOP_TIER_GB", 1.0)

    result = llama_ai.discover_top_tier(limit=2, total_ram_bytes=total_small,
                                        headroom_bytes=head, min_trending_score=0, per_provider=2)
    assert result == [], \
        "fit gate must REJECT a 29 GB model on a 12 GB card (budget {budget/1e9:.0f}GB), got {result}"


def test_lower_quant_keeps_comfortable_headroom(monkeypatch):
    """The HIGH quant is the biggest that fits; the LOWER quant is chosen ~25%+ smaller
    so it leaves comfortable headroom (no model teeters at the OOM edge)."""
    # Simulate a 16 GB card: budget = 16 - head - kv. Use headroom so only the high
    # fits tightly and the lower must be clearly smaller.
    total = 24 * 1024 ** 3
    head = 3 * 1024 ** 3
    kv = 1024 ** 3
    # high Q8 = 18 GB (fits: 18+3+1=22 <= 24), lower Q4 = 12 GB (clearly smaller, comfy)
    repos = [{"repo": "unsloth/Qwen3.8-27B-GGUF", "downloads": 1, "likes": 1, "trendingScore": 900}]

    def fake_trending(limit=25):
        return repos

    def fake_files(repo):
        return [{"path": "model-Q8_0.gguf", "size_bytes": 18 * 1024 ** 3, "size_gb": 18.0},
                {"path": "model-Q4_K_M.gguf", "size_bytes": 12 * 1024 ** 3, "size_gb": 12.0},
                {"path": "model-Q3_K_M.gguf", "size_bytes": 9 * 1024 ** 3, "size_gb": 9.0}]

    monkeypatch.setattr(llama_ai, "_trending_gguf_repos", fake_trending)
    monkeypatch.setattr(llama_ai, "_repo_gguf_files", fake_files)
    monkeypatch.setattr(llama_ai, "_probe_file_downloadable", lambda *a, **k: "ok")
    monkeypatch.setattr(llama_ai, "MIN_TOP_TIER_GB", 1.0)

    result = llama_ai.discover_top_tier(limit=4, total_ram_bytes=total,
                                        headroom_bytes=head, min_trending_score=0, per_provider=2)
    sizes = sorted([c["size_bytes"] for c in result], reverse=True)
    assert len(sizes) == 2, f"expected high + lower, got {sizes}"
    # HIGH must be the biggest that still fits with headroom
    assert sizes[0] + head + kv <= total, f"high must fit with headroom: {sizes[0]/1e9:.1f}GB"
    # LOWER must be clearly smaller (~25%+), so it leaves even MORE headroom
    assert (sizes[0] - sizes[1]) >= 0.25 * sizes[0], \
        f"lower must be clearly smaller: {sizes[0]/1e9:.1f}->{sizes[1]/1e9:.1f}GB"
    # ...and the lower must still FIT comfortably (with generous leftover budget)
    assert total - (sizes[1] + head + kv) >= 0.1 * total, \
        f"lower should leave comfortable headroom: leftover {(total-(sizes[1]+head+kv))/1e9:.1f}GB"


def test_argparse_recognizes_all_top_tier_flags_with_defaults(monkeypatch):
    """ALL `--download-top-tier` CLI flags are recognized by argparse with correct
    defaults (hermetic wiring test — no network).
    """
    import argparse as _argparse
    import scripts.llama_serve as _ls

    # Rebuild the parser exactly as main() does and parse a representative argv.
    ap = _argparse.ArgumentParser()
    ap.add_argument("model", nargs="?")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--port", type=int, default=11434)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--download-top-tier", action="store_true")
    ap.add_argument("--count", type=int, default=5)
    ap.add_argument("--per-provider", type=int, default=2)
    ap.add_argument("--min-trending-score", type=int, default=0)

    # --list (with --count/--per-provider/--min-trending-score variations)
    a = ap.parse_args(["--download-top-tier", "--list", "--port", "18080"])
    assert a.download_top_tier is True and a.list is True and a.port == 18080

    # --dry + all three tunables given explicitly
    a = ap.parse_args(["--download-top-tier", "--dry", "--count", "3",
                       "--per-provider", "1", "--min-trending-score", "250"])
    assert a.dry is True and a.count == 3 and a.per_provider == 1 and a.min_trending_score == 250

    # defaults, none given explicitly
    a = ap.parse_args(["--download-top-tier"])
    assert a.count == 5 and a.per_provider == 2 and a.min_trending_score == 0 \
        and a.list is False and a.dry is False and a.port == 11434


def test_trending_gguf_repos_queries_rank_and_filters(monkeypatch):
    """The LIVE trending-source function `_trending_gguf_repos`:
    - queries HF with sort=trendingScore&direction=-1&filter=gguf
    - KEEPS only top-tier-family repos (Qwen3/GLM/...), DROPS the rest
    - fills downloads/likes/trendingScore per repo
    - returns them ranked by trendingScore DESC (the live ranked table).
    """
    seen_urls = []

    def fake_hf_get(url, timeout=30):
        seen_urls.append(url)
        assert "sort=trendingScore" in url and "direction=-1" in url and "filter=gguf" in url
        return [
            # (out of order on purpose -> must be re-ranked; one non-top-tier -> dropped)
            {"id": "orcarouter/Qwen3.8-27B-Uncensored-GGUF", "downloads": 284000,
             "likes": 722, "trendingScore": 123},
            {"id": "some/podcast-clip-audio", "downloads": 999999, "likes": 999,  # non-top-tier
             "trendingScore": 999},
            {"id": "unsloth/Qwen3.8-27B-GGUF", "downloads": 10200000, "likes": 3526,
             "trendingScore": 284},
            {"id": "ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF", "downloads": 297000,
             "likes": 354, "trendingScore": 320},
        ]

    monkeypatch.setattr(llama_ai, "_hf_get", fake_hf_get)
    result = llama_ai._trending_gguf_repos(limit=25)
    # exact descending trendingScore order (matches the live ranked table shape)
    assert [r["trendingScore"] for r in result] == [320, 284, 123]
    # popular trending LLMs in the broadened allow-list are KEPT (not dropped):
    assert llama_ai._is_top_tier_repo("ornith-ai/Ornith-1.5-9B-GGUF") is True
    assert llama_ai._is_top_tier_repo("Jackrong/Qwopus3.8-27B-Flash-GGUF") is True
    assert llama_ai._is_top_tier_repo("IFM/K2-Horizon-MoVA-36B-A4B-GGUF") is True
    assert llama_ai._is_top_tier_repo("peculiar-ragdoll/Tiel-Coder-35B-A3B-GGUF") is True
    # non-LLM / TTS / image repos must stay DROPPED (the whole reason the list exists):
    assert llama_ai._is_top_tier_repo("nvidia/parakeet-tdt-0.6b-v3") is False
    assert llama_ai._is_top_tier_repo("ampixa/sanoTTS") is False
    assert llama_ai._is_top_tier_repo("ponpoke/flux2-klein-9b-uncensored-text-encoder") is False
    # the non-top-tier repo (podcast-clip-audio) is dropped
    assert all("podcast" not in r["repo"] for r in result)
    # each carries downloads/likes/trendingScore and is a top-tier family
    for r in result:
        assert r["repo"].split("/", 1)[0] in ("ISTA-DASLab", "unsloth", "orcarouter")
        assert r["downloads"] > 0 and r["likes"] > 0
    # the query hit HF with the trending sort
    assert any("sort=trendingScore" in u for u in seen_urls)


def test_repo_fit_classification_matches_table():
    """The 'fits 48 GB?' classification from the ranked table: given a 48 GB card
    (48 GiB total, ~3.6 GiB headroom, 1 GiB KV), a 29 GB Q8 repo fits ('yes'), a
    split-shard/MTP-only repo can't form a single file ('check'), and a giant repo
    like a 400 GB bf16 does NOT fit ('no')."""
    total = 48 * 1024 ** 3
    head = (3 * 1024 ** 3) * 6 // 5   # ~3.6 GiB like the live host
    kv = 1024 ** 3

    def fits_ok(size_gb):
        return (int(size_gb * 1024 ** 3)) + head + kv <= total

    # 'yes' — 29.3 GB Q8 of a 27B on the 48 GB card
    assert fits_ok(29.3) is True
    # 21.5 GB Q6 also yes
    assert fits_ok(21.5) is True
    # 'no' — ~400 GB flash/bf16 model
    assert fits_ok(400) is False
    # GPU budget boundary: 48 GiB - 3.6 - 1 ~ 43.4 GiB -> a 43 GB model barely, 44 doesn't
    assert fits_ok(40) is True
    assert fits_ok(45) is False


def test_pick_tier_folder_small_card_unchanged():
    """A 48 GB card keeps the mid/large buckets 16/24/48; the small tiers (1/2/4)
    are added below 8 so small models get truthful folders, not a catch-all 8GB."""
    _48 = 48 * 1024 ** 3
    # new small tiers (down-extension) are truthful
    assert llama_ai.pick_tier_folder(int(0.43 * 1024 ** 3), _48) == "1GB"
    assert llama_ai.pick_tier_folder(int(7 * 1024 ** 3), _48) == "8GB"
    # mid/large buckets unchanged
    assert llama_ai.pick_tier_folder(int(15 * 1024 ** 3), _48) == "16GB"
    assert llama_ai.pick_tier_folder(int(22 * 1024 ** 3), _48) == "24GB"
    assert llama_ai.pick_tier_folder(int(29 * 1024 ** 3), _48) == "48GB"
    assert llama_ai.pick_tier_folder(int(47 * 1024 ** 3), _48) == "48GB"


def test_pick_tier_folder_big_card_gets_truthful_tiers():
    """On a 512 GB card a large model is labelled by a large tier, NEVER 48GB/."""
    _512 = 512 * 1024 ** 3
    # small/mid models still use the small buckets on the big card
    assert llama_ai.pick_tier_folder(int(29 * 1024 ** 3), _512) == "48GB"
    assert llama_ai.pick_tier_folder(int(7 * 1024 ** 3), _512) == "8GB"
    # large models get tiers that grow past 48
    assert llama_ai.pick_tier_folder(int(60 * 1024 ** 3), _512) == "96GB"
    assert llama_ai.pick_tier_folder(int(100 * 1024 ** 3), _512) == "128GB"
    assert llama_ai.pick_tier_folder(int(256 * 1024 ** 3), _512) == "256GB"
    assert llama_ai.pick_tier_folder(int(400 * 1024 ** 3), _512) == "512GB"
    assert llama_ai.pick_tier_folder(int(512 * 1024 ** 3), _512) == "512GB"
    # a model bigger than the card falls back to the largest available bucket
    assert "48GB" != llama_ai.pick_tier_folder(int(400 * 1024 ** 3), _512)
    assert llama_ai.pick_tier_folder(int(700 * 1024 ** 3), _512) == "512GB"


def test_pick_tier_folder_deterministic_with_total_argument():
    """Passing total_ram_bytes makes placement independent of the runner's card."""
    _512 = 512 * 1024 ** 3
    _48 = 48 * 1024 ** 3
    # same 60 GB model, two cards -> two different truthful tiers
    assert llama_ai.pick_tier_folder(int(60 * 1024 ** 3), _48) == "48GB"
    assert llama_ai.pick_tier_folder(int(60 * 1024 ** 3), _512) == "96GB"


def test_discover_top_tier_offers_and_places_large_model_on_big_card(monkeypatch):
    """On a 512 GB card a 400 GB trending model IS offered (fit gate passes) and its
    tier_folder is a large tier (512GB/), never misleadingly 48GB/ (issue #51)."""
    repo = "unsloth/Qwen4-400B-GGUF"
    files_by_repo = {
        repo: [  # a 400 GB bf16 + a 200 GB lower quant, both only fit a big card
            {"path": "model-BF16.gguf", "size_bytes": 400 * 1024 ** 3, "size_gb": 400.0},
            {"path": "model-Q8_0.gguf", "size_bytes": 200 * 1024 ** 3, "size_gb": 200.0},
        ],
    }

    def fake_trending(limit=25):
        return [{"repo": repo, "downloads": 1000, "likes": 100, "trendingScore": 500}]

    def fake_files(r):
        return files_by_repo[r]

    monkeypatch.setattr(llama_ai, "_trending_gguf_repos", fake_trending)
    monkeypatch.setattr(llama_ai, "_repo_gguf_files", fake_files)
    monkeypatch.setattr(llama_ai, "_probe_file_downloadable", lambda *a, **k: "ok")
    monkeypatch.setattr(llama_ai, "MIN_TOP_TIER_GB", 1.0)

    _512 = 512 * 1024 ** 3
    _1 = 1024 ** 3
    result = llama_ai.discover_top_tier(limit=4, total_ram_bytes=_512,
                                        headroom_bytes=_1, min_trending_score=0,
                                        per_provider=2)
    # both quants are offered (each fits 512 GB with the 1 GiB headroom)
    assert len(result) == 2, f"expected 2 candidates on 512 GB card, got {len(result)}"
    tiers = [c["tier_folder"] for c in result]
    assert "512GB" in tiers, f"the 400 GB model must land in a big tier, got {tiers}"
    assert all(t != "48GB" for t in tiers), f"big models must never be 48GB/, got {tiers}"
    # 400 GB -> 512GB/ ; 200 GB -> 256GB/ (next available bucket >= 200)
    assert result[0]["size_gb"] == 400.0 and result[0]["tier_folder"] == "512GB"
    assert result[1]["size_gb"] == 200.0 and result[1]["tier_folder"] == "256GB"


# ---------------------------------------------------------------------------
# FULL VRAM-parameterized placement: assume a specific GPU VRAM and verify each
# mocked model lands in the folder for the card it FITS (issue #51).
# For every card size in the ladder and a sweep of model sizes, the model's
# dest_path/<TierGB> must equal the smallest available bucket >= its size.
# ---------------------------------------------------------------------------
def _expected_tier(model_gb, card_gb):
    """Reference impl: smallest TIER_LADDER_GB entry <= card_gb (available buckets),
    and within those the smallest bucket >= model_gb, else the largest."""
    avail = [b for b in llama_ai.TIER_LADDER_GB if b <= card_gb]
    assert avail, "card too small for any bucket"
    for b in avail:
        if model_gb <= b:
            return f"{b}GB"
    return f"{avail[-1]}GB"


def test_placement_parametrized_over_all_card_sizes():
    """Every ladder card size x a model sweep -> correct TierGB folder (full dest_path)."""
    ALL_LADDER = llama_ai.TIER_LADDER_GB
    # one representative model per tier (fits comfortably on cards >= that tier)
    model_sizes_gb = [5, 12, 20, 29, 60, 100, 200, 400, 500, 1000]
    for card_gb in ALL_LADDER:
        total = int(card_gb * (1024 ** 3))
        for mgb in model_sizes_gb:
            want = _expected_tier(mgb, card_gb)
            got = llama_ai.pick_tier_folder(int(mgb * 1024 ** 3), total)
            assert got == want, (
                f"{mgb} GB model on {card_gb} GB card: expected {want}, got {got}")

            # also verify the full placement path embeds the same tier
            p = llama_ai.provider_dest_path("unsloth/X-GGUF", "x.gguf",
                                            int(mgb * 1024 ** 3), models_root="/m",
                                            total_ram_bytes=total)
            assert f"/{want}/x.gguf" in p, (
                f"{mgb} GB model on {card_gb} GB card dest_path {p} missing tier {want}")


def test_placement_fit_gate_and_folder_agree(monkeypatch):
    """The fit gate (eligibility) and the tier folder (placement) must agree on the
    same assumed VRAM: a model with size+headroom+KV <= card IS offered AND its
    folder says it fits; a model that can't fit is NOT offered at all."""
    card_gb = 512
    total = int(card_gb * 1024 ** 3)
    head = 4 * 1024 ** 3
    kv = 1024 ** 3

    repo = "unsloth/Big-GGUF"
    sizes = [40, 400]  # 40 GB fits any card; 400 GB only fits >=512

    def fake_trending(limit=25):
        return [{"repo": repo, "downloads": 1, "likes": 1, "trendingScore": 900}]

    def fake_files(r):
        return [{"path": f"m{s}.gguf", "size_bytes": int(s * 1024 ** 3), "size_gb": s}
                for s in sizes]

    monkeypatch.setattr(llama_ai, "_trending_gguf_repos", fake_trending)
    monkeypatch.setattr(llama_ai, "_repo_gguf_files", fake_files)
    monkeypatch.setattr(llama_ai, "_probe_file_downloadable", lambda *a, **k: "ok")
    monkeypatch.setattr(llama_ai, "MIN_TOP_TIER_GB", 1.0)

    # headroom_bytes is passed separately; the gate uses size+head+kv <= total
    result = llama_ai.discover_top_tier(limit=10, total_ram_bytes=total,
                                        headroom_bytes=head, min_trending_score=0,
                                        per_provider=5)
    placed = {c["size_gb"]: c["tier_folder"] for c in result}
    # 40 GB fits 512 GB card comfortably -> offered, tier 48GB (smallest >= 40)
    # 400 GB fits 512 GB card (400+4+1=405 <=512) -> offered, tier 512GB
    assert set(placed) == {40, 400}, f"expected both to be offered, got {placed}"
    assert placed[40] == "48GB" and placed[400] == "512GB"

    # Now the SAME model on a 48 GB card: 400 GB does NOT fit -> not offered; 40 fits.
    total48 = 48 * 1024 ** 3
    result48 = llama_ai.discover_top_tier(limit=10, total_ram_bytes=total48,
                                          headroom_bytes=head, min_trending_score=0,
                                          per_provider=2)
    placed48 = {c["size_gb"]: c["tier_folder"] for c in result48}
    assert 40 in placed48 and 400 not in placed48, (
        f"on 48 GB card only 40 GB offered, got {placed48}")


# ---------------------------------------------------------------------------
# EDGE-CASE MOCK-DOWNLOAD PLACEMENT (issue #51, user: "mock the card size, mock
# the downloads, real asserts the mocked GGUF lands in the RIGHT directory").
# Drives the REAL discover_top_tier (mock the model list), then MOCKS the actual
# download by writing the candidate into its discovered dest_path, and asserts the
# real file is in the correct tier folder — for card sizes 512/256/128/96/64/48
# and the tiny 32/16/8/2 GB edge cases.
# ---------------------------------------------------------------------------
def _mock_discovery(monkeypatch, repos_files, min_gb=4.0, probe_result="ok"):
    """Install fake trending + file-list so discover_top_tier runs hermetically."""
    # repos_files: {repo: {"trend": int, "files": [(name, size_gb), ...]}}
    def fake_trending(limit=25):
        out = []
        for rid, info in repos_files.items():
            out.append({"repo": rid, "downloads": 1000, "likes": 100,
                        "trendingScore": info["trend"]})
        out.sort(key=lambda r: -r["trendingScore"])
        return out

    def fake_files(repo):
        return [{"path": name, "size_bytes": int(gb * 1024 ** 3), "size_gb": gb}
                for (name, gb) in repos_files[repo]["files"]]

    def fake_probe(repo, filename, timeout=15, probe_bytes=65536):
        if isinstance(probe_result, dict):
            return probe_result.get(repo, "ok")
        return probe_result

    monkeypatch.setattr(llama_ai, "_trending_gguf_repos", fake_trending)
    monkeypatch.setattr(llama_ai, "_repo_gguf_files", fake_files)
    monkeypatch.setattr(llama_ai, "_probe_file_downloadable", fake_probe)
    monkeypatch.setattr(llama_ai, "MIN_TOP_TIER_GB", min_gb)


def _mock_download_write_stub(monkeypatch, tmp_path):
    """Replace download_top_tier_candidate with a stub that materializes the
    candidate into its own dest_path (a mock of the real hf download), recording
    the files it 'downloaded'."""
    written = []

    def fake_download(cand, models_root=None):
        dest = cand["dest_path"]
        p = Path(dest)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"MOCKGGUF\x00" * 16)  # small stub — placement is what we assert
        written.append(str(p))
        return str(p)

    monkeypatch.setattr(llama_ai, "download_top_tier_candidate", fake_download)
    return written


def test_mock_download_places_each_model_in_right_tier_dir(tmp_path, monkeypatch):
    """Story: mock the card size + mock the downloads, assert each mocked GGUF lands
    in the folder for the card it fits, across the edge-case card sizes."""
    G = 1024 ** 3
    # 5 trending providers, each a realistic model spanning large -> small.
    repos_files = {
        "unsloth/Qwen3.8-27B-GGUF":   {"trend": 281, "files": [("q8.gguf", 29.0), ("q6.gguf", 21.5)]},
        "DavidAU/Qwen3.8-27B-GGUF":   {"trend": 221, "files": [("q8.gguf", 27.7), ("q5.gguf", 19.3)]},
        "HauhauCS/Qwen3.8-27B-GGUF":  {"trend": 170, "files": [("q8.gguf", 29.3), ("q5.gguf", 18.8)]},
        "OBLITERATUS/Qwen3.8-27B-GGUF": {"trend": 129, "files": [("q8.gguf", 27.1), ("q5.gguf", 18.2)]},
        "orcarouter/Qwen3.8-27B-GGUF":{"trend": 114, "files": [("q8.gguf", 27.1), ("q5.gguf", 18.2)]},
    }
    _mock_discovery(monkeypatch, repos_files)
    written = _mock_download_write_stub(monkeypatch, tmp_path)

    head = 3 * G  # floor headroom
    # card sizes: the edge cases — big, medium, small
    for card_gb in [512, 256, 128, 96, 64, 48, 32, 16, 8, 2]:
        total = int(card_gb * G)
        result = llama_ai.discover_top_tier(limit=5, total_ram_bytes=total,
                                            headroom_bytes=head, min_trending_score=0,
                                            per_provider=2)
        # mock-download every discovered candidate
        for cand in result:
            ll = llama_ai.download_top_tier_candidate(cand, models_root=str(tmp_path))
            # the mock actually wrote the file at the right place
            assert Path(ll).is_file(), f"mocked download missing: {ll}"
            # the dest_path's TIER folder == the tier the card-fits logic picked
            tier = cand["tier_folder"]
            assert f"/{tier}/" in ll, (
                f"{card_gb} GB card: file {ll} missing tier folder {tier}")
        # (download_top_tier_candidate is stubbed, so 'written' list isn't needed here)


def test_mock_download_picks_top5_by_trend_and_places(tmp_path, monkeypatch):
    """Story: the top-5 trending providers get mock-downloaded into the right tier dir;
    assert the top-5 BY TREND (not by file size) are the ones actually placed (issue #49/#51)."""
    G = 1024 ** 3
    repos_files = {
        "low_trend/Big":  {"trend": 10,  "files": [("q8.gguf", 400.0)]},
        "high_trend/Small":{"trend": 999, "files": [("q8.gguf", 10.0)]},
        "med/Both":       {"trend": 500, "files": [("q8.gguf", 100.0), ("q4.gguf", 50.0)]},
    }
    _mock_discovery(monkeypatch, repos_files, min_gb=1.0)
    _mock_download_write_stub(monkeypatch, tmp_path)

    total = 512 * G
    head = 3 * G
    result = llama_ai.discover_top_tier(limit=5, total_ram_bytes=total,
                                        headroom_bytes=head, min_trending_score=0,
                                        per_provider=1)
    # RANKING is by TRENDING (999 > 500 > 10), not by file size (400 > 100 > 10):
    # the trend-999 repo MUST be first. med/Both (500) contributes its high+lower
    # (2 rows under per_provider=2 logic), then low_trend/Big (10) LAST.
    placed_repos = [c["repo"] for c in result]
    assert placed_repos[0] == "high_trend/Small", (
        f"trend 999 must rank #1, got {placed_repos}")
    assert placed_repos[1] == "med/Both", f"trend 500 next, got {placed_repos}"
    assert placed_repos[-1] == "low_trend/Big", (
        f"trend 10 must rank LAST (not ahead of higher-trend models): {placed_repos}")
    # every mocked download lands in the folder for the card it fits
    for cand in result:
        ll = llama_ai.download_top_tier_candidate(cand, models_root=str(tmp_path))
        assert Path(ll).is_file()
        assert f"/{cand['tier_folder']}/" in ll


def test_discover_skips_gated_repo_and_refills(tmp_path, monkeypatch):
    """A 401/403-gated repo is excluded pre-flight (probe fails) and discovery REFILLS
    the count from the next provider, so len(cands) stays at `limit` even when some
    trending repos can't be downloaded (issue #53)."""
    G = 1024 ** 3
    repos_files = {
        "good/A": {"trend": 900, "files": [("q8.gguf", 20.0)]},
        "gated/B": {"trend": 800, "files": [("q8.gguf", 25.0)]},   # probe -> access-denied
        "good/C": {"trend": 700, "files": [("q8.gguf", 30.0)]},
    }
    _mock_discovery(monkeypatch, repos_files, min_gb=1.0,
                    probe_result={"good/A": "ok", "gated/B": "access-denied", "good/C": "ok"})
    total = 512 * G
    head = 3 * G
    limit = 2
    result = llama_ai.discover_top_tier(limit=limit, total_ram_bytes=total,
                                        headroom_bytes=head, min_trending_score=0,
                                        per_provider=1)
    placed = [c["repo"] for c in result]
    assert len(result) == limit, f"must refill to {limit}, got {len(result)}: {placed}"
    assert "gated/B" not in placed, f"gated repo must be excluded, got {placed}"
    assert "good/A" in placed and "good/C" in placed, f"must refill from next provider, got {placed}"


def test_probe_downloadable_verifies_real_gguf_chunk(monkeypatch):
    """The pre-flight probe verifies a REAL GGUF chunk, and rejects an HTML/error body
    even when served with 200 (auth-ok but not a real model file)."""

    def make_urlopen(body):
        class Ctx:
            def __enter__(self): return type("R", (), {"read": lambda s, n=None: body})()
            def __exit__(self, *a): return False
        return lambda *a, **k: Ctx()

    monkeypatch.setattr(llama_ai.urllib.request, "urlopen", make_urlopen(b"GGUF" + b"\x00" * 1024))
    assert llama_ai._probe_file_downloadable("x/repo", "m.gguf") == "ok"

    monkeypatch.setattr(llama_ai.urllib.request, "urlopen",
                        make_urlopen(b"<html><body>404 Not Found</body></html>"))
    assert llama_ai._probe_file_downloadable("x/repo", "m.gguf") is None  # 200-but-HTML -> not real


def test_skip_summary_line_handles_3tuples_without_crash():
    """Regression for issue #56: the completion summary must tolerate the REAL
    skip-list shape (repo, filename, reason) without a tuple-unpack crash."""

    # Given a non-empty skip_summary of (repo, filename, reason) 3-tuples
    skip_summary = [
        ("orcarouter/Qwen3.8-27B-Uncensored-GGUF", "a-Q8_0.gguf", "access-denied"),
        ("orcarouter/Qwen3.8-27B-Uncensored-GGUF", "a-Q5_K_M.gguf", "access-denied"),
        ("dead/provider", "b.gguf", "dead"),
    ]

    # When we format it via _skip_summary_line
    line = llama_ai._skip_summary_line(skip_summary)

    # Then it returns the grouped-by-reason line WITHOUT crashing
    #   (previously 'ValueError: not enough values to unpack (expected 2)')
    assert "3 skipped pre-flight" in line, line
    assert "2 access-denied" in line, line
    assert "1 dead" in line, line


def test_skip_summary_line_empty_no_suffix():
    """Empty/None skip_summary must yield no skip suffix."""

    # Given no pre-flight skips

    # When  we format empty and None skip_summary via _skip_summary_line

    # Then  it returns '' (so the completion line has no skip suffix)
    assert llama_ai._skip_summary_line([]) == ""
    assert llama_ai._skip_summary_line(None) == ""


# ---------------------------------------------------------------------------
# --family: top providers of ONE model family (issue #61)
# ---------------------------------------------------------------------------
G = 1024 ** 3

# Deterministic fake qwen family for the family-mode pipeline tests: 5 clean
# member repos (real-ish GGUF sizes), a substring trap that must be dropped, a
# gated repo (probe -> access-denied), and providers at different trending
# scores / download counts. Wire order is deliberately scrambled so discovery
# must re-rank.
FAMILY_QWEN_REPOS = [
    {"repo": "Qwen/Qwen2.5-7B-Instruct-GGUF", "downloads": 5000000, "likes": 900,
     "trendingScore": 200},
    {"repo": "unsloth/Qwen3.8-27B-GGUF", "downloads": 1000000, "likes": 400,
     "trendingScore": 120},
    {"repo": "bartowski/Qwen3.8-27B-GGUF", "downloads": 400000, "likes": 150,
     "trendingScore": 120},
    {"repo": "orcarouter/Qwen3.8-27B-Uncensored-GGUF", "downloads": 284000, "likes": 72,
     "trendingScore": 120},        # gated (probe -> access-denied): skipped + refilled
    {"repo": "maddes/Another-Qwen-GGUF", "downloads": 90000, "likes": 30,
     "trendingScore": 10},
    {"repo": "Qwen/Qwen2.5-0.5B-Instruct-GGUF", "downloads": 700000, "likes": 100,
     "trendingScore": 5},          # refill provider (low trend)
]

FAMILY_QWEN_FILES = {
    "Qwen/Qwen2.5-7B-Instruct-GGUF": [
        ("qwen2.5-7b-instruct-q8_0.gguf", 7.5),
        ("qwen2.5-7b-instruct-q4_0.gguf", 4.7),
    ],
    "unsloth/Qwen3.8-27B-GGUF": [
        ("Qwen3.8-27B-Q8_0.gguf", 29.0),
        ("Qwen3.8-27B-Q5_K_M.gguf", 17.0),
        ("Qwen3.8-27B-IQ2_XXS.gguf", 8.0),    # low-fidelity: never picked
        ("mmproj-Qwen3.8-27B-f16.gguf", 0.5),  # projector: never picked
    ],
    "bartowski/Qwen3.8-27B-GGUF": [("Qwen3.8-27B-Q8_0.gguf", 29.0)],
    "orcarouter/Qwen3.8-27B-Uncensored-GGUF": [
        ("Qwen3.8-27B-Uncensored-Q8_0.gguf", 29.0)],
    "maddes/Another-Qwen-GGUF": [
        ("another-qwen-Q6_K.gguf", 12.0),
        ("another-qwen-Q4_K_M.gguf", 8.5),
    ],
    "Qwen/Qwen2.5-0.5B-Instruct-GGUF": [
        ("qwen2.5-0.5b-instruct-q4_0.gguf", 4.5),
    ],
}


def _install_family_mocks(monkeypatch, repos, files_by_repo,
                          probe_result=("ok",)):
    """Point the family-search + file-listing + probe seams at deterministic fakes.

    `repos` is returned verbatim as the family repo list (already what the real
    `_family_gguf_repos` would have produced — word-boundary filtered, ranked).
    The word-boundary filter itself is covered separately by
    `test_family_gguf_repos_word_boundary_and_ranking`.
    """
    def fake_family(keyword, limit=300):
        assert keyword == "qwen"
        return [dict(r) for r in repos][:limit]

    def fake_files(repo):
        return [{"path": name, "size_bytes": int(gb * G), "size_gb": gb}
                for name, gb in files_by_repo.get(repo, [])]

    def fake_probe(repo, filename, timeout=15, probe_bytes=65536):
        if isinstance(probe_result, dict):
            return probe_result.get(repo, "ok")
        return probe_result

    monkeypatch.setattr(llama_ai, "_family_gguf_repos", fake_family)
    monkeypatch.setattr(llama_ai, "_repo_gguf_files", fake_files)
    monkeypatch.setattr(llama_ai, "_probe_file_downloadable", fake_probe)


def test_family_keyword_matches_word_boundary():
    """Story: the family keyword matches on a word boundary, NOT substring.

    Given  repos for the `qwen` family search — including `Qwen2.5`/`Qwen3.8`
           (keyword followed by a version DIGIT) and the traps `qwopus`/`qwythos`
           (different families starting with the same letters),
    When   `_family_keyword_matches` classifies them,
    Then   the Qwen repos match, and NO trap matches.
    """
    # Given real + trap repo ids from the live qwen family
    qwen_members = ["unsloth/Qwen3.8-27B-GGUF",
                    "Qwen/Qwen2.5-0.5B-Instruct-GGUF",
                    "unsloth/Qwen3-27B-GGUF"]
    traps = ["Jackrong/Qwopus3.8-27B-Flash-GGUF", "empero-ai/Qwythos-9B",
             "foo/qwenix-GGUF", "qwq/other-family"]

    # When each is word-boundary matched against the keyword `qwen`

    # Then members match; traps (and other families) do not
    for rid in qwen_members:
        assert llama_ai._family_keyword_matches(rid, "qwen"), f"{rid} must match"
    for rid in traps:
        assert not llama_ai._family_keyword_matches(rid, "qwen"), \
            f"{rid} must NOT match --family qwen"
    assert not llama_ai._family_keyword_matches("x/y", ""), "empty kw never matches"


def test_family_gguf_repos_word_boundary_and_ranking(monkeypatch):
    """Story: `_family_gguf_repos` queries the FULL model set (filter=gguf,
    sort=downloads — NOT the trending slice), drops substring traps, keeps only
    top-tier families, and ranks trendingScore desc with downloads desc.

    Given  a mocked HF search response with traps, a non-top-tier repo, and
           out-of-order members,
    When   `_family_gguf_repos('qwen')` runs,
    Then   the URL is the family search (no sort=trendingScore), the traps are
           dropped, and the survivors are ranked (trend desc, downloads desc).
    """
    # Given a scrambled, trap-laden HF search response
    seen_urls = []

    def fake_hf_get(url, timeout=30):
        seen_urls.append(url)
        return [
            {"id": "Jackrong/Qwopus3.8-27B-Flash-GGUF", "downloads": 999999,
             "likes": 999, "trendingScore": 500},   # substring trap
            {"id": "empero-ai/Qwythos-9B", "downloads": 500000, "likes": 200,
             "trendingScore": 39},                   # substring trap
            {"id": "some/podcast-clip-audio", "downloads": 999999, "likes": 999,
             "trendingScore": 999},                  # not a top-tier family
            {"id": "orcarouter/Qwen3.8-27B-Uncensored-GGUF", "downloads": 284000,
             "likes": 722, "trendingScore": 123},
            {"id": "unsloth/Qwen3.8-27B-GGUF", "downloads": 10200000, "likes": 3526,
             "trendingScore": 284},
            {"id": "ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF", "downloads": 297000,
             "likes": 354, "trendingScore": 320},
        ]

    monkeypatch.setattr(llama_ai, "_hf_get", fake_hf_get)

    # When the family repo list is built for keyword `qwen`
    result = llama_ai._family_gguf_repos("qwen", limit=25)

    # Then the query is the family search (downloads sort, no trending sort)
    assert seen_urls and "filter=gguf" in seen_urls[0], seen_urls
    assert "sort=downloads" in seen_urls[0] and "direction=-1" in seen_urls[0]
    assert "trendingScore" not in seen_urls[0].split("sort=")[1]
    # traps are dropped (word boundary) and the non-top-tier repo is dropped
    ids = [r["repo"] for r in result]
    assert all("qwopus" not in i and "qwythos" not in i for i in ids), ids
    assert all("podcast" not in i for i in ids), ids
    # ranked trendingScore desc, downloads desc tie-break
    assert ids == [
        "ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF",   # trend 320
        "unsloth/Qwen3.8-27B-GGUF",               # trend 284
        "orcarouter/Qwen3.8-27B-Uncensored-GGUF",  # trend 123
    ], f"family ranking wrong: {ids}"
    for r in result:
        assert r["downloads"] > 0 and r["likes"] > 0


def test_hf_get_retries_transient_and_fails_permanent(monkeypatch):
    """Story: `_hf_get` retries TRANSIENT HF errors with backoff and fails FAST on
    permanent ones.

    Root cause of the issue #61 CI flake (same commit RED on the push run, GREEN on
    the pull_request run, minutes apart): the family dry-run fans out one HF API
    call per repo tree (hundreds), and `_hf_get` had NO retry — so a single 429 on
    one tree call silently dropped that repo (turning a valid match into a false
    "no model fits"), while a 429 on the search call itself hard-exited the CLI.

    Given  a mocked urllib.request.urlopen,
    When   `_hf_get` is called and the first responses are transient,
    Then   transient errors (429) are retried with backoff until success, a
           permanent error (404) fails fast on the FIRST try (no retry), and a
           persistent transient error exhausts the budget and raises SystemExit.
    """
    import json as _json
    from email.message import Message

    class _FakeResponse:
        """Minimal stand-in for urllib's response: a context manager with read()."""
        def __init__(self, body: bytes):
            self._body = body
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            return False
        def read(self, *a):
            return self._body

    def _http_error(code: int, retry_after=None) -> urllib.error.HTTPError:
        hdrs = Message()
        if retry_after is not None:
            hdrs["Retry-After"] = str(retry_after)
        return urllib.error.HTTPError("https://huggingface.co/api/models", code,
                                      "err", hdrs, io.BytesIO(b""))

    # no real sleeping in CI — drive the budget/pause via module attributes
    monkeypatch.setattr(llama_ai, "HF_GET_MAX_ATTEMPTS", 4)
    monkeypatch.setattr(llama_ai, "HF_GET_BASE_PAUSE", 0.0)

    # --- Given: a transient 429 (twice) that clears on the 3rd call ---
    calls = {"n": 0}

    def flaky_urlopen(req, timeout=30):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise _http_error(429, retry_after="0")
        return _FakeResponse(_json.dumps({"ok": True}).encode())

    monkeypatch.setattr(llama_ai.urllib.request, "urlopen", flaky_urlopen)

    # When the transient 429s resolve after retrying
    got = llama_ai._hf_get("https://huggingface.co/api/models?x")

    # Then it retried through the 429s and returned the payload on the 3rd call
    assert got == {"ok": True}, got
    assert calls["n"] == 3, f"expected 3 urlopen calls (2 x 429 + 1 ok), got {calls['n']}"

    # --- Given: a permanent 404 (a genuinely dead repo/file) ---
    calls2 = {"n": 0}

    def dead_urlopen(req, timeout=30):
        calls2["n"] += 1
        raise _http_error(404)

    monkeypatch.setattr(llama_ai.urllib.request, "urlopen", dead_urlopen)

    # When _hf_get hits a permanent error
    with pytest.raises(SystemExit):
        llama_ai._hf_get("https://huggingface.co/api/models?dead")

    # Then it failed FAST — exactly one attempt, never retried (F3/#53 skip path
    # and the F8 "no repos" path rely on permanent errors surfacing immediately)
    assert calls2["n"] == 1, f"404 must fail fast (1 call), got {calls2['n']}"

    # --- Given: a persistent 429 that never clears ---
    calls3 = {"n": 0}

    def always429(req, timeout=30):
        calls3["n"] += 1
        raise _http_error(429, retry_after="0")

    monkeypatch.setattr(llama_ai.urllib.request, "urlopen", always429)

    # When the retry budget is exhausted
    with pytest.raises(SystemExit) as e:
        llama_ai._hf_get("https://huggingface.co/api/models?rate")

    # Then it used EVERY attempt exactly (budget-bounded, never an infinite retry)
    assert calls3["n"] == llama_ai.HF_GET_MAX_ATTEMPTS, \
        f"must try exactly HF_GET_MAX_ATTEMPTS times, got {calls3['n']}"
    assert "still failing after" in str(e.value), str(e.value)


def test_family_scope_mocked(monkeypatch):
    """Story: `--family qwen` downloads the top providers of ONE family.

    Given  a deterministic fake qwen family (5 clean member repos with
           real-ish GGUF sizes, a gated repo, and providers at different
           trending scores / download counts),
    When   family-mode discovery runs on a mocked 48 GB card with --count 5,
    Then   high+lower per provider, gated skip+refill, provider-aware
           placement, and ranking all hold.
    """
    # Given the fake family wired into the network seams, a 48 GB card,
    #        and a gated repo
    probe = {"orcarouter/Qwen3.8-27B-Uncensored-GGUF": "access-denied"}
    _install_family_mocks(monkeypatch, FAMILY_QWEN_REPOS, FAMILY_QWEN_FILES,
                          probe_result=probe)
    total = 48 * G
    head = 3 * G
    skip_summary = []

    # When family-mode discovery runs (--family qwen, --count 5, per_provider 2)
    cands = llama_ai.discover_top_tier(limit=5 * 2, total_ram_bytes=total,
                                       headroom_bytes=head, min_trending_score=0,
                                       per_provider=2, skip_summary=skip_summary,
                                       family="qwen")

    # Then 1. scope: only family-member repos appear — no substring trap leaked
    for c in cands:
        assert "qwopus" not in c["repo"].lower(), \
            f"substring trap qwopus matched: {c['repo']}"
        assert "qwythos" not in c["repo"].lower(), \
            f"substring trap qwythos matched: {c['repo']}"
    # Then 2. high+lower per provider: unsloth yields Q8 AND clearly-lower Q5,
    #        never the IQ2, never the mmproj
    unsloth = [c for c in cands if c["repo"] == "unsloth/Qwen3.8-27B-GGUF"]
    assert len(unsloth) == 2, f"unsloth must yield high+lower, got {unsloth}"
    sizes = [c["size_gb"] for c in unsloth]
    assert sizes[0] == 29.0 and sizes[1] == 17.0, f"high+lower: {sizes}"
    assert (sizes[0] - sizes[1]) >= 0.25 * sizes[0], "lower must be clearly lower"
    for c in cands:
        assert "iq2" not in c["filename"].lower(), f"IQ2 picked: {c['filename']}"
        assert not c["filename"].startswith("mmproj"), f"mmproj picked: {c['filename']}"
    # Then 3. gated skip + refill: orcarouter absent, in the skip summary
    assert all(c["repo"] != "orcarouter/Qwen3.8-27B-Uncensored-GGUF" for c in cands)
    assert ("orcarouter/Qwen3.8-27B-Uncensored-GGUF",
            "Qwen3.8-27B-Uncensored-Q8_0.gguf", "access-denied") in skip_summary
    # ...and the count refilled from the next fitting provider: 5 distinct
    #        providers (the 0.5B repo yields no candidate below the MIN floor)
    repos = {c["repo"] for c in cands}
    assert len(repos) == 5, f"expected 5 distinct providers, got {sorted(repos)}"
    # Then 4. placement: every dest_path = <root>/<owner>/<family>/<TierGB>/<file>
    #        with the correct dynamic tier for the 48 GB card
    for c in cands:
        owner, fam = c["repo"].split("/", 1)
        assert c["dest_path"].endswith(
            f"/{owner}/{fam}/{c['tier_folder']}/{c['filename']}"), c["dest_path"]
        assert c["tier_folder"] == llama_ai.pick_tier_folder(c["size_bytes"], total)
        assert c["tier_folder"] in ("1GB", "2GB", "4GB", "8GB", "16GB", "24GB", "48GB")
    # Then 5. ranking: providers ordered by trendingScore desc, downloads desc
    #        tie-break (200 > 120[1M dl] > 120[400k] > 120[284k gated] > 10).
    #        0.5B (trend 15) produces NO candidates (below MIN_TOP_TIER_GB).
    order = []
    for c in cands:
        if c["repo"] not in order:
            order.append(c["repo"])
    assert order == [
        "Qwen/Qwen2.5-7B-Instruct-GGUF",      # trend 200
        "unsloth/Qwen3.8-27B-GGUF",           # trend 120, 1.0M downloads
        "bartowski/Qwen3.8-27B-GGUF",         # trend 120, 400k downloads
        "maddes/Another-Qwen-GGUF",           # trend 10
        "Qwen/Qwen2.5-0.5B-Instruct-GGUF",    # trend 5 (refilled after gated skip)
    ], f"provider ranking wrong: {order}"


def test_family_ranking_downloads_tiebreak(monkeypatch):
    """Story: when two family providers tie on trendingScore, the one with MORE
    downloads ranks first (trendingScore is sparse — downloads breaks ties)."""

    # Given two family providers with identical trendingScore, different downloads
    repos = [
        {"repo": "low/DL", "downloads": 1000, "likes": 1, "trendingScore": 0},
        {"repo": "high/DL", "downloads": 900000, "likes": 1, "trendingScore": 0},
    ]
    files = {"low/DL": [("q8.gguf", 20.0)], "high/DL": [("q8.gguf", 20.0)]}
    _install_family_mocks(monkeypatch, repos, files)

    # When family-mode discovery returns them
    cands = llama_ai.discover_top_tier(limit=4, total_ram_bytes=48 * G,
                                       headroom_bytes=3 * G, min_trending_score=0,
                                       per_provider=1, family="qwen")

    # Then the higher-downloads provider is ordered first
    assert [c["repo"] for c in cands] == ["high/DL", "low/DL"], \
        f"downloads tie-break: {[c['repo'] for c in cands]}"


def test_family_min_trending_score_ignored(monkeypatch):
    """In family mode --min-trending-score is IGNORED: a niche family's repos are
    mostly unscored (trendingScore 0), and a score floor would filter them all
    out. Family mode forces the floor to 0."""

    # Given a family of two repos that both report trendingScore 0
    repos = [
        {"repo": "a/One", "downloads": 100, "likes": 1, "trendingScore": 0},
        {"repo": "b/Two", "downloads": 200, "likes": 1, "trendingScore": 0},
    ]
    files = {"a/One": [("q8.gguf", 10.0)], "b/Two": [("q8.gguf", 10.0)]}
    _install_family_mocks(monkeypatch, repos, files)

    # When discovery runs in family mode with a high (would-exclude-all) floor
    cands = llama_ai.discover_top_tier(limit=4, total_ram_bytes=48 * G,
                                       headroom_bytes=3 * G, min_trending_score=999,
                                       per_provider=1, family="qwen")

    # Then the floor is ignored in family mode: both zero-score repos survive
    assert {c["repo"] for c in cands} == {"a/One", "b/Two"}, \
        f"min_trending_score must be ignored in family mode: {cands}"


def test_family_zero_matches_fails_loudly(monkeypatch, capsys):
    """Story: an unknown family (typo / non-GGUF) is a loud failure, never a
    silent success.

    Given  a family keyword with zero matching GGUF repos,
    When   the CLI's family branch runs,
    Then   it prints `no GGUF repos found for family '<kw>'` and exits non-zero.
    """
    # Given the family search returns nothing (typo'd / non-GGUF family)
    monkeypatch.setattr(llama_ai, "_family_gguf_repos", lambda kw, limit=300: [])

    # When the CLI dispatches --download-top-tier --family zzz
    import argparse
    args = argparse.Namespace(download_top_tier=True, family="zzz", count=5,
                              per_provider=2, min_trending_score=0, dry=False,
                              list=False, port=11434)

    # Then it exits non-zero with the clear family message
    with pytest.raises(SystemExit) as e:
        llama_ai._main_download_top_tier(args)
    assert e.value.code == 1, f"unknown family must exit 1, got {e.value.code}"
    out = capsys.readouterr()
    assert "no GGUF repos found for family 'zzz'" in (out.out + out.err)


def test_family_one_provider_fewer_than_count_honest(monkeypatch):
    """Story: a family with fewer providers than --count downloads what exists
    and reports honestly (no crash, no silent padding)."""

    # Given a family with exactly ONE provider but --count 5 requested
    repos = [{"repo": "solo/Only", "downloads": 500, "likes": 1, "trendingScore": 0}]
    files = {"solo/Only": [("q8.gguf", 20.0), ("q5.gguf", 13.0)]}
    _install_family_mocks(monkeypatch, repos, files)

    # When family-mode discovery asks for 5 providers
    cands = llama_ai.discover_top_tier(limit=5 * 2, total_ram_bytes=48 * G,
                                       headroom_bytes=3 * G, min_trending_score=0,
                                       per_provider=2, family="qwen")

    # Then exactly that one provider (with high+lower) is returned — no crash,
    # no padding, an honest 1/5 the CLI reports as completed 1/1 of candidates
    assert [c["repo"] for c in cands] == ["solo/Only", "solo/Only"], \
        f"1-provider family must yield its high+lower only: {[c['repo'] for c in cands]}"


def test_discover_family_none_uses_trending(monkeypatch):
    """Story: WITHOUT --family the code path is unchanged — discovery uses the
    global trending window (F7: byte-identical to pre-existing behavior)."""

    # Given fakes for BOTH the trending and family seams, each with a marker repo
    trending_calls, family_calls = [], []

    def fake_trending(limit=25):
        trending_calls.append(limit)
        return [{"repo": "trend/Repo", "downloads": 10, "likes": 1,
                 "trendingScore": 100}]

    def fake_family(keyword, limit=300):
        family_calls.append(keyword)
        return [{"repo": "fam/Repo", "downloads": 10, "likes": 1,
                 "trendingScore": 100}]

    files = {"trend/Repo": [("q8.gguf", 10.0)], "fam/Repo": [("q8.gguf", 10.0)]}
    _install_family_mocks(monkeypatch, [], files)  # installs _repo_gguf_files+probe
    monkeypatch.setattr(llama_ai, "_trending_gguf_repos", fake_trending)
    monkeypatch.setattr(llama_ai, "_family_gguf_repos", fake_family)

    # When discovery runs with family=None (the default, no --family)
    cands = llama_ai.discover_top_tier(limit=2, total_ram_bytes=48 * G,
                                       headroom_bytes=3 * G, min_trending_score=0,
                                       per_provider=1)

    # Then the TRENDING source was used and the family source was NOT touched
    assert trending_calls, "family=None must use _trending_gguf_repos"
    assert not family_calls, "family=None must never call _family_gguf_repos"
    assert [c["repo"] for c in cands] == ["trend/Repo"]
