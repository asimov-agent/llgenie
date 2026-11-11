#!/usr/bin/env python3
"""Point every live Hermes config's MAIN model at one cloud model id.

Rewrites only the leading top-level `model:` block of ~/.hermes/config.yaml and
every ~/.hermes/profiles/*/config.yaml, leaving the rest of each file untouched.
The local server stays reachable through a `local-llm` alias.

Usage:
    python3 set_default_model.py <model-id> [provider] [base_url]

Defaults: provider=nous, base_url=https://inference-api.nousresearch.com/v1.
Back up first (see SKILL.md: per-file dirname loop) — this overwrites the block.
Idempotent: re-running writes the same block again.
"""
import glob
import os
import sys

LOCAL_ALIAS = """    local-llm:
      model: local-llm
      provider: custom
      base_url: http://127.0.0.1:11434/v1
"""

BLOCK = """model:
  base_url: {base_url}
  default: {model}
  provider: {provider}
  aliases:
    nous-deepseek:
      model: {model}
      provider: custom
      base_url: {base_url}
      key_env: NOUS_API_KEY
      max_tokens: 16000
      context_window: 1048576
"""


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    model = sys.argv[1]
    provider = sys.argv[2] if len(sys.argv) > 2 else "nous"
    base_url = sys.argv[3] if len(sys.argv) > 3 else "https://inference-api.nousresearch.com/v1"
    block = BLOCK.format(model=model, provider=provider, base_url=base_url) + LOCAL_ALIAS

    home = os.path.expanduser("~/.hermes")
    files = [os.path.join(home, "config.yaml")] + sorted(
        glob.glob(os.path.join(home, "profiles", "*", "config.yaml"))
    )

    for path in files:
        with open(path) as fh:
            lines = fh.readlines()
        if not lines or lines[0].strip() != "model:":
            sys.exit(f"ABORT {path}: does not start with a top-level 'model:' block")
        end = 1
        while end < len(lines) and (lines[end].startswith("  ") or lines[end].strip() == ""):
            end += 1
        while end > 1 and lines[end - 1].strip() == "":
            end -= 1
        rest = lines[end:]
        with open(path, "w") as fh:
            fh.write(block + ("\n" if rest and rest[0].strip() else "") + "".join(rest))
        print(f"rewrote {path}")

    print(f"{len(files)} configs -> {model} ({provider}, {base_url})")


if __name__ == "__main__":
    main()
