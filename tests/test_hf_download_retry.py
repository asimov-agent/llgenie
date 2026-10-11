"""Hub downloads wait out a 429 through scripts/hf_auth.hub_open (issue #163).

The size lookup, the ranged chunk download and the preflight probe do not open
a Hub URL themselves. Each test drives the real function and asserts the sleep
against rate_limit_wait, the same function the caller uses.
"""
from __future__ import annotations

import io
import json
import sys
import urllib.error
from email.message import Message
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import hf_auth  # noqa: E402
import hf_download  # noqa: E402
import llama_serve  # noqa: E402
import model_engine_pick as mp  # noqa: E402


def _too_many(seconds):
    hdrs = Message()
    hdrs["RateLimit"] = f'"api";r=0;t={seconds}'
    return urllib.error.HTTPError(
        "https://huggingface.co/api/models", 429, "err", hdrs, io.BytesIO(b""))


class _Body:
    def __init__(self, body):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, n=-1):
        data, self._body = self._body, b""
        return data if n < 0 else data[:n]


def test_size_lookup_waits_out_a_429(monkeypatch):
    """The downloader's size lookup sleeps the shared wait, then reads the tree."""

    # Given a tree listing that is rate-limited once, then names the file
    err = _too_many(12)
    calls = {"n": 0}
    slept = []

    def flaky(req, timeout=30):
        calls["n"] += 1
        if calls["n"] == 1:
            raise err
        body = json.dumps([{"path": "model.gguf", "size": 4096}]).encode()
        return _Body(body)

    monkeypatch.setattr(hf_auth.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(hf_auth.time, "sleep", lambda s: slept.append(s))

    # When the downloader resolves the file size with no size given
    size = hf_download._resolve_expected_bytes("org/repo", "model.gguf", "t", None)

    # Then the sleep is the shared wait and the size is the one in the tree
    assert size == 4096
    assert slept == [hf_auth.rate_limit_wait(err)]


def test_chunk_download_waits_out_a_429(monkeypatch, tmp_path):
    """A ranged chunk download sleeps the shared wait, then writes the bytes."""

    # Given a ranged GET that is rate-limited once, then returns the file bytes
    err = _too_many(12)
    calls = {"n": 0}
    slept = []

    def flaky(req, timeout=30):
        calls["n"] += 1
        if calls["n"] == 1:
            raise err
        return _Body(b"GGUFchunk")

    monkeypatch.setattr(hf_auth.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(hf_auth.time, "sleep", lambda s: slept.append(s))

    # When the chunk download runs
    out = mp.download_chunk("org/repo", "model.gguf", tmp_path, 64)

    # Then the sleep is the shared wait and the file is those bytes
    assert out.read_bytes() == b"GGUFchunk"
    assert slept == [mp.rate_limit_wait(err)]


def test_preflight_probe_waits_out_a_429(monkeypatch):
    """The preflight probe sleeps the shared wait, then accepts a GGUF body."""

    # Given a ranged resolve that is rate-limited once, then returns GGUF bytes
    err = _too_many(12)
    calls = {"n": 0}
    slept = []

    def flaky(req, timeout=30):
        calls["n"] += 1
        if calls["n"] == 1:
            raise err
        return _Body(b"GGUF" + b"\x00" * 252)

    monkeypatch.setattr(hf_auth.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(hf_auth.time, "sleep", lambda s: slept.append(s))

    # When the preflight probe runs
    result = llama_serve._probe_file_downloadable("org/repo", "model.gguf")

    # Then the sleep is the shared wait and the file is downloadable
    assert result == "ok"
    assert slept == [llama_serve.rate_limit_wait(err)]


def test_hub_open_fails_on_the_third_429(monkeypatch):
    """Three consecutive 429s fail the download GET. A fourth attempt is not made."""

    # Given a Hub GET that is rate-limited every time
    calls = {"n": 0}

    def always(req, timeout=30):
        calls["n"] += 1
        raise _too_many(1)

    monkeypatch.setattr(hf_auth, "_rate_limited", 0)
    monkeypatch.setattr(hf_auth.urllib.request, "urlopen", always)
    monkeypatch.setattr(hf_auth.time, "sleep", lambda _s: None)

    # When the shared opener is called
    with pytest.raises(urllib.error.HTTPError) as raised:
        hf_auth.hub_open(urllib.request.Request("https://huggingface.co/org/repo/resolve/main/model.gguf"))

    # Then the third 429 failed the call and no fourth attempt was made
    assert raised.value.code == 429
    assert calls["n"] == 3
