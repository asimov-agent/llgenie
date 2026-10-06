"""Post-build engine endpoint test (runs inside llgenie/test:latest, which bundles
python + openai + pytest; reached over --network host).

The engine image is already serving on the OpenAI endpoint; this asserts the
contract exactly as an AI harness/agent tool would against the published port:

    OPENAI_BASE_URL=http://127.0.0.1:<port>/v1 \\
        python3 -m pytest test_engine_runs.py -q

  - GET  /v1/models        lists `llm-local`
  - POST /v1/chat/completions model=llm-local "hi" answers non-empty

No image handle is needed here: the server is already running and the OpenAI SDK
is the only client. (The `--version` check on every built image lives in
tests/test_engine_version.py, run in llgenie/test with the host docker socket.)
"""
from __future__ import annotations

import os

import pytest


def _base_url() -> str:
    url = os.environ.get("OPENAI_BASE_URL", "")
    if not url:
        pytest.fail("OPENAI_BASE_URL is not set: run this through `make test-engine ENGINE=<id> ARCH=cpu`, "
                    "which serves the image and points the test at its published port")
    return url


def test_engine_cpu_image_answers_hi():
    """GET /v1/models lists llm-local and a chat completion ('hi') answers."""
    from openai import OpenAI
    client = OpenAI(api_key="llgenie-test", base_url=_base_url(),
                    max_retries=0, timeout=300.0)
    ids = [m.id for m in client.models.list()]
    if os.environ.get("LLGENIE_TEST_ALIAS_MODE") == "any-name":
        # no alias flag (e.g. mlx_lm.server lists the real model path) but it
        # answers any model name: the chat below still sends model=llm-local
        assert ids, "GET /v1/models listed no model"
    else:
        assert any(i.split(":")[0] == "llm-local" for i in ids), f"llm-local not served: {ids}"
    reply = client.chat.completions.create(
        model="llm-local", messages=[{"role": "user", "content": "hi"}], max_tokens=16)
    text = (getattr(reply.choices[0].message, "content", "") or "").strip()
    assert text, "empty chat-completion reply"
    print(f"[endpoint] {_base_url()} answered: {text!r}")
