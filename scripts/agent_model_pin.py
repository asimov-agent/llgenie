#!/usr/bin/env python3
"""The bots' model pin, declared ONCE, and a gate that refuses drift (issue #405).

The agent image runs the Hermes CLI against the Nous OpenAI-compatible endpoint through a
CUSTOM provider alias (`nous-deepseek`; Hermes's bundled `nous` provider is OAuth-only, so a
secret-supplied NOUS_API_KEY only works through an alias — see scripts/install_hermes_ci.sh).

Two files carry that pin, because each is an independent build input:

    containers/agent/Dockerfile       ARG HERMES_MODEL_ID="…"
    scripts/install_hermes_ci.sh      MODEL_ID="${HERMES_MODEL_ID:-…}"

Nothing used to compare them, and the only test on the id was a SUBSTRING assert
(``"deepseek/deepseek-v4.1-flash" in script``) that any newer snapshot satisfies — so the bots
quietly ran the previous snapshot (``…-20260910``, served by Impala) while the owner's host ran
``…-1017`` (``…-20261017``). Both answer 200 from inside a bot job, which is why nothing went red.

This module is the referee:

    python3 scripts/agent_model_pin.py check     # non-zero on drift, naming file + value
    python3 scripts/agent_model_pin.py report    # what each place says

Stdlib only, no network, no key: it reads the two files and compares them with the values below.
A DIFFERENT snapshot (older or newer) is drift, never "close enough".

The values are the pinned snapshot's own: the catalogue at
https://inference-api.nousresearch.com/v1/models publishes
``context_length: 1048576`` and ``max_completion_tokens: 943718`` for this id, so a 16000-token
reply budget with the full 1M window is a deliberate, sub-limit choice (the host's alias uses the
same pair). Leaving them unset makes Hermes budget the run from models.dev, which does not carry
this snapshot id at all.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# ---- the pin (the ONE declaration) ------------------------------------------------------
# Provider-prefixed: the endpoint 404s a bare id. The `-1017` suffix is the SNAPSHOT
# (2026-10-17) — dropping it silently selects the previous release.
MODEL_ID = "deepseek/deepseek-v4.1-flash-1017"
ALIAS = "nous-deepseek"
MAX_TOKENS = 16000
CONTEXT_WINDOW = 1048576

DOCKERFILE = "containers/agent/Dockerfile"
INSTALL_SCRIPT = "scripts/install_hermes_ci.sh"

# `ARG HERMES_MODEL_ID="deepseek/deepseek-v4.1-flash-1017"` (quote style tolerated)
_DOCKERFILE_ARG = re.compile(r'^ARG\s+HERMES_MODEL_ID="?(?P<value>[^"\s]+)"?\s*$', re.MULTILINE)
# `MODEL_ID="${HERMES_MODEL_ID:-deepseek/deepseek-v4.1-flash-1017}"   # …`
_INSTALL_DEFAULT = re.compile(
    r'^MODEL_ID="\$\{HERMES_MODEL_ID:-(?P<value>[^}]+)\}"', re.MULTILINE
)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:  # a missing input is a finding, never a skip
        raise SystemExit(f"[model-pin] cannot read {path}: {exc}")


def pin_in_dockerfile(root: Path = REPO) -> str | None:
    """The value of the Dockerfile's `ARG HERMES_MODEL_ID` default, or None when absent."""
    match = _DOCKERFILE_ARG.search(_read(root / DOCKERFILE))
    return match.group("value") if match else None


def pin_in_install_script(root: Path = REPO) -> str | None:
    """The install script's `MODEL_ID` default, or None when absent."""
    match = _INSTALL_DEFAULT.search(_read(root / INSTALL_SCRIPT))
    return match.group("value") if match else None


def findings(root: Path = REPO) -> list[str]:
    """Every place that does not carry the pinned snapshot, as one line each."""
    out: list[str] = []
    for path, reader in ((DOCKERFILE, pin_in_dockerfile), (INSTALL_SCRIPT, pin_in_install_script)):
        value = reader(root)
        if value is None:
            out.append(f"{path}: no model pin found (expected {MODEL_ID})")
        elif value != MODEL_ID:
            out.append(f"{path}: pins {value} (expected {MODEL_ID})")
    return out


def budget_findings(root: Path = REPO) -> list[str]:
    """The alias must carry the model's real budget, in the script AND in the build assert."""
    out: list[str] = []
    script = _read(root / INSTALL_SCRIPT)
    for key, value in (("max_tokens", MAX_TOKENS), ("context_window", CONTEXT_WINDOW)):
        line = re.search(
            rf'hermes config set "model\.aliases\.\$\{{ALIAS}}\.{key}"\s+"?(?P<value>[^"\s]+)"?',
            script,
        )
        if not line:
            out.append(f"{INSTALL_SCRIPT}: the alias never sets {key} (expected {value})")
        elif line.group("value") != str(value):
            out.append(f"{INSTALL_SCRIPT}: alias {key} is {line.group('value')} (expected {value})")

    dockerfile = _read(root / DOCKERFILE)
    for key in ("model", "max_tokens", "context_window"):
        if f'model.aliases.${{HERMES_ALIAS}}.{key}' not in dockerfile:
            out.append(f"{DOCKERFILE}: the build does not assert the alias's {key}")
    return out


def report(root: Path = REPO) -> str:
    lines = [
        f"[model-pin] pinned: {MODEL_ID} via alias {ALIAS} "
        f"(max_tokens={MAX_TOKENS}, context_window={CONTEXT_WINDOW})",
        f"[model-pin] {DOCKERFILE}: {pin_in_dockerfile(root) or '(none)'}",
        f"[model-pin] {INSTALL_SCRIPT}: {pin_in_install_script(root) or '(none)'}",
    ]
    bad = findings(root) + budget_findings(root)
    lines.extend(f"[model-pin] FINDING {f}" for f in bad)
    lines.append(f"[model-pin] {'OK' if not bad else f'{len(bad)} finding(s)'}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check the bots' pinned model snapshot against the files that carry it"
    )
    parser.add_argument("command", choices=("check", "report"))
    parser.add_argument("--root", default=str(REPO), help="repository root (default: this checkout)")
    args = parser.parse_args(argv)
    root = Path(args.root)
    if args.command == "report":
        print(report(root))
        return 0

    bad = findings(root) + budget_findings(root)
    print(report(root))
    if bad:
        print(
            "[model-pin] FAIL: the bots would call a different model than the pin "
            "(issue #405); move every value above together",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
