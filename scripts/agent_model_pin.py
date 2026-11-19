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
``context_length: 1048576`` and ``max_completion_tokens: 65536`` for this id, so a 16000-token
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
# Provider-prefixed: the endpoint 404s a bare id. The `-0731` suffix is the SNAPSHOT
# (2026-07-31) of DeepSeek V4 Flash. There is no `deepseek-v4.1-flash-0731`. Dropping
# the suffix selects `deepseek/deepseek-v4-flash`, the April 23 release, not this pin.
MODEL_ID = "deepseek/deepseek-v4-flash-0731"
ALIAS = "nous-deepseek"
MAX_TOKENS = 16000
CONTEXT_WINDOW = 1048576

# The Hermes CLI version the agent image is built against: install.sh's default `stable`
# channel floats (it takes "the latest published release" as of the build moment), so the
# image pins it through the Dockerfile's `--commit` flag. HERMES_VERSION and
# HERMES_INSTALL_COMMIT are the ONE declaration, mirrored in the Dockerfile ARG defaults and
# the install script's VERSION default; drift reddens this gate like a model drift does.
HERMES_VERSION = "0.23.2"
HERMES_INSTALL_COMMIT = "ae2a81ccc00e9b7c06301523e5bb09608397149c"  # peeled v0.23.2 tag commit

DOCKERFILE = "containers/agent/Dockerfile"
INSTALL_SCRIPT = "scripts/install_hermes_ci.sh"

# `ARG HERMES_MODEL_ID="deepseek/deepseek-v4-flash-0731"` (quote style tolerated)
_DOCKERFILE_ARG = re.compile(r'^ARG\s+HERMES_MODEL_ID="?(?P<value>[^"\s]+)"?\s*$', re.MULTILINE)
_DOCKERFILE_VERSION_ARG = re.compile(r'^ARG\s+HERMES_VERSION="?(?P<value>[^"\s]+)"?\s*$', re.MULTILINE)
# trailing `# …` comment tolerated (the ARG carries a "peeled v0.23.2" inline note)
_DOCKERFILE_COMMIT_ARG = re.compile(r'^ARG\s+HERMES_INSTALL_COMMIT="?(?P<value>[^"\s]+)"?.*$', re.MULTILINE)
# `MODEL_ID="${HERMES_MODEL_ID:-deepseek/deepseek-v4-flash-0731}"   # …`
_INSTALL_DEFAULT = re.compile(
    r'^MODEL_ID="\$\{HERMES_MODEL_ID:-(?P<value>[^}]+)\}"', re.MULTILINE
)
# `VERSION="${HERMES_VERSION:-0.23.2}"`
_INSTALL_VERSION_DEFAULT = re.compile(
    r'^VERSION="\$\{HERMES_VERSION:-(?P<value>[^}]+)\}"', re.MULTILINE
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


def version_in_dockerfile(root: Path = REPO) -> str | None:
    """The Dockerfile's `ARG HERMES_VERSION` default, or None when absent."""
    match = _DOCKERFILE_VERSION_ARG.search(_read(root / DOCKERFILE))
    return match.group("value") if match else None


def commit_in_dockerfile(root: Path = REPO) -> str | None:
    """The Dockerfile's `ARG HERMES_INSTALL_COMMIT` default, or None when absent."""
    match = _DOCKERFILE_COMMIT_ARG.search(_read(root / DOCKERFILE))
    return match.group("value") if match else None


def pin_in_install_script(root: Path = REPO) -> str | None:
    """The install script's `MODEL_ID` default, or None when absent."""
    match = _INSTALL_DEFAULT.search(_read(root / INSTALL_SCRIPT))
    return match.group("value") if match else None


def version_in_install_script(root: Path = REPO) -> str | None:
    """The install script's `VERSION` default, or None when absent."""
    match = _INSTALL_VERSION_DEFAULT.search(_read(root / INSTALL_SCRIPT))
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


def version_findings(root: Path = REPO) -> list[str]:
    """Every place that does not carry the pinned Hermes version/commit, as one line each."""
    out: list[str] = []
    dv = version_in_dockerfile(root)
    if dv is None:
        out.append(f"{DOCKERFILE}: no HERMES_VERSION ARG found (expected {HERMES_VERSION})")
    elif dv != HERMES_VERSION:
        out.append(f"{DOCKERFILE}: ARG HERMES_VERSION is {dv} (expected {HERMES_VERSION})")
    sv = version_in_install_script(root)
    if sv is None:
        out.append(f"{INSTALL_SCRIPT}: no VERSION default found (expected {HERMES_VERSION})")
    elif sv != HERMES_VERSION:
        out.append(f"{INSTALL_SCRIPT}: VERSION default is {sv} (expected {HERMES_VERSION})")
    commit = commit_in_dockerfile(root)
    if commit is None:
        out.append(f"{DOCKERFILE}: no HERMES_INSTALL_COMMIT ARG found (expected {HERMES_INSTALL_COMMIT})")
    elif commit != HERMES_INSTALL_COMMIT:
        out.append(
            f"{DOCKERFILE}: ARG HERMES_INSTALL_COMMIT is {commit} (expected {HERMES_INSTALL_COMMIT})"
        )
    # The install script receives the pin only through HERMES_INSTALL_ARGS's `--commit` flag;
    # if that flag is dropped, the checkout floats. The Dockerfile may forward it either as the
    # literal pinned sha or as the `${HERMES_INSTALL_COMMIT}` variable reference (docker resolves
    # the latter to the pinned ARG default at build time); both are the same pin, and anything
    # else — a different literal, or none — is drift.
    dockerfile = _read(root / DOCKERFILE)
    args_line = re.search(r'^ARG\s+HERMES_INSTALL_ARGS=\"[^\"]*--commit\s+(\S+)', dockerfile,
                          re.MULTILINE)
    forwarded = args_line.group(1).strip('"') if args_line else None
    if forwarded != HERMES_INSTALL_COMMIT and forwarded != "${HERMES_INSTALL_COMMIT}":
        out.append(
            f"{DOCKERFILE}: HERMES_INSTALL_ARGS must forward --commit {HERMES_INSTALL_COMMIT} "
            "to install.sh (install.sh's `stable` channel floats otherwise)"
        )
    return out


def report(root: Path = REPO) -> str:
    lines = [
        f"[model-pin] pinned: {MODEL_ID} via alias {ALIAS} "
        f"(max_tokens={MAX_TOKENS}, context_window={CONTEXT_WINDOW})",
        f"[model-pin] hermes {HERMES_VERSION} @ {HERMES_INSTALL_COMMIT}",
        f"[model-pin] {DOCKERFILE}: {pin_in_dockerfile(root) or '(none)'}",
        f"[model-pin] {INSTALL_SCRIPT}: {pin_in_install_script(root) or '(none)'}",
        f"[model-pin] {DOCKERFILE} HERMES_VERSION: {version_in_dockerfile(root) or '(none)'}",
        f"[model-pin] {DOCKERFILE} HERMES_INSTALL_COMMIT: {commit_in_dockerfile(root) or '(none)'}",
        f"[model-pin] {INSTALL_SCRIPT} VERSION default: {version_in_install_script(root) or '(none)'}",
    ]
    bad = findings(root) + budget_findings(root) + version_findings(root)
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

    bad = findings(root) + budget_findings(root) + version_findings(root)
    print(report(root))
    if bad:
        print(
            "[model-pin] FAIL: the bots would call a different model than the pin, or the image "
            "would install a different Hermes than the pin (issue #405): move every value above together",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
