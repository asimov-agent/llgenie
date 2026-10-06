"""OpenAI-SDK conformance client for llgenie engines.

A harness/AI-agent tool talks to llgenie through the *OpenAI* wire contract
over OpenAI HTTP (127.0.0.1) or OpenAI-compatible ports. This client exercises
that same surface with the pinned `openai` package (tools/requirements-dev.txt;
the version here comes from the same lockfile) so CI proves the engine speaks
the API an agent actually uses — not just a raw HTTP body we hand-roll.

Drive it through the engine smoke test (`utils/engine_smoke.py`) so it does not
need openai preinstalled anywhere:

    OPENAI_BASE_URL=http://127.0.0.1:<port>/v1 \
    UV_SYSTEM_PYTHON=1 \
      uv run --quiet --with openai==P.Q.R \
        scripts/tools/llgenie_harness.py

Exit 0 means the served model:
  - GET  /v1/models                  -> lists a model whose id ends in `llm-local`
  - POST /v1/chat/completions        -> returns text for model=llm-local (Bearer auth)
  - POST /v1/chat/completions stream -> yields a chunk delta
"""
from __future__ import annotations

import os
import sys
import json

from openai import OpenAI


def red(text: str) -> str:
    return f"\033[91m{text}\033[0m"


def main() -> int:
    base = os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENAI_API_BASE")
    if not base:
        print(red("[harness] OPENAI_BASE_URL is required"), file=sys.stderr)
        return 1
    client = OpenAI(api_key=os.environ.get("LLGENIE_SMOKE_KEY", "test"), base_url=base,
                    max_retries=0, timeout=300.0)

    # 1. models listing contains llm-local
    try:
        models = client.models.list()
    except Exception as e:  # noqa: BLE001
        print(red(f"[harness] GET /v1/models failed: {e}"), file=sys.stderr)
        return 2
    ids = [m.id for m in models.data]
    if not any(i.split(":")[0] == "llm-local" for i in ids):
        print(red(f"[harness] llm-local missing from /v1/models ({ids})"), file=sys.stderr)
        return 3
    print(f"[harness] /v1/models: {ids}")

    # 2. sync chat completion via the SDK
    try:
        reply = client.chat.completions.create(
            model="llm-local",
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=16,
        )
        text = (getattr(reply.choices[0].message, "content", "") or "").strip()
    except Exception as e:  # noqa: BLE001
        print(red(f"[harness] POST /v1/chat/completions failed: {e}"), file=sys.stderr)
        return 4
    if not text:
        print(red("[harness] empty completion text"), file=sys.stderr)
        return 5
    print(f"[harness] [hi] {text}")

    # 3. stream
    try:
        chunks = [c for c in client.chat.completions.create(
            model="llm-local",
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=8, stream=True,
        )]
        deltas = []
        for c in chunks:
            try:
                deltas += [d.content for d in c.choices if getattr(d, "delta", None)]
            except TypeError:
                continue
        if not any(deltas):
            raise RuntimeError("no streaming delta content")
    except Exception as e:  # noqa: BLE001
        print(red(f"[harness] streaming failed: {e}"), file=sys.stderr)
        return 6
    print(f"[harness] OK {base} -> model=llm-local, sync + stream answered via the OpenAI SDK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
