#!/usr/bin/env python3
"""The token every Hugging Face call sends.

`HF_TOKEN` in the environment wins, then `HUGGING_FACE_HUB_TOKEN`, then the
`HF_TOKEN=` line in `~/.zshrc` or `~/.bashrc`. CI sets the environment from
the `HF_TOKEN` Actions secret. The value is never printed and never written
into the repo.
"""
from __future__ import annotations

import os
import re
import urllib.parse
import urllib.request

_LINE = re.compile(
    r"(?m)^[ \t]*(?:export[ \t]+)?HF_TOKEN=[\"']?(hf_[A-Za-z0-9]+)[\"']?[ \t]*$"
)


def hf_token() -> str:
    """The Hub token, or '' when none is configured."""
    for key in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        val = os.environ.get(key, "").strip().strip("\"'")
        if val:
            return val
    for name in (".zshrc", ".bashrc"):
        path = os.path.expanduser(f"~/{name}")
        try:
            text = open(path).read()
        except OSError:
            continue
        match = _LINE.search(text)
        if match:
            return match.group(1)
    return ""


def _hub_host(url: str) -> bool:
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    return host == "huggingface.co" or host.endswith(".huggingface.co")


def authorize(req: urllib.request.Request) -> urllib.request.Request:
    """Attach `Authorization: Bearer` when the URL is the Hub and a token exists."""
    if _hub_host(req.full_url):
        tok = hf_token()
        if tok:
            req.add_header("Authorization", f"Bearer {tok}")
    return req


def apply_env(env: dict) -> dict:
    """Put the token on `env` for the `hf` CLI. Leave an explicit value in place."""
    tok = hf_token()
    if tok:
        env["HF_TOKEN"] = tok
        env.setdefault("HUGGING_FACE_HUB_TOKEN", tok)
    return env
