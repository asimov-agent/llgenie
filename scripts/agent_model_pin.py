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

# The Hermes release the image installs (issue #2932). install.sh's `stable` channel floats,
# so the pin names the release AND the commit: the peeled commit of the upstream annotated
# tag v0.23.2 (tag object 28f57ed8e3dba4eceb67dfd3e3abda1a7604452d; a `--commit` checkout of
# the tag OBJECT is a clone failure, only the peeled commit is checkable). PyPI's
# hermes-agent tops out at 0.19.0, so this release line travels only through install.sh.
HERMES_VERSION = "0.23.2"
HERMES_INSTALL_COMMIT = "ae2a81ccc00e9b7c06301523e5bb09608397149c"

DOCKERFILE = "containers/agent/Dockerfile"
INSTALL_SCRIPT = "scripts/install_hermes_ci.sh"

# `ARG HERMES_MODEL_ID="deepseek/deepseek-v4-flash-0731"` (quote style tolerated)
_DOCKERFILE_ARG = re.compile(r'^ARG\s+HERMES_MODEL_ID="?(?P<value>[^"\s]+)"?\s*$', re.MULTILINE)
# `MODEL_ID="${HERMES_MODEL_ID:-deepseek/deepseek-v4-flash-0731}"   # …`
_INSTALL_DEFAULT = re.compile(
    r'^MODEL_ID="\$\{HERMES_MODEL_ID:-(?P<value>[^}]+)\}"', re.MULTILINE
)

# The Hermes version pin (issue #2932): two Dockerfile ARGs, the ARGS list that must pass the
# commit to install.sh, and the install script's own default + read-back assert.
_DOCKERFILE_VERSION_ARG = re.compile(r'^ARG\s+HERMES_VERSION="?(?P<value>[^"\s]+)"?\s*#?.*$', re.MULTILINE)
_DOCKERFILE_COMMIT_ARG = re.compile(r'^ARG\s+HERMES_INSTALL_COMMIT="?(?P<value>[^"\s]+)"?\s*#?.*$', re.MULTILINE)
_DOCKERFILE_INSTALL_ARGS = re.compile(r'^ARG\s+HERMES_INSTALL_ARGS="(?P<value>[^"]*)"', re.MULTILINE)
_INSTALL_VERSION_DEFAULT = re.compile(
    r'^HERMES_VERSION="\$\{HERMES_VERSION:-(?P<value>[^}]+)\}"', re.MULTILINE
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


def version_findings(root: Path = REPO) -> list[str]:
    """The Hermes release the image installs must be named in every home that installs it.

    Four checks (issue #2932): the Dockerfile names the version; the Dockerfile names the
    peeled v0.23.2 commit; the install ARGS actually pass that commit to install.sh via
    --commit; and the install script declares the same version default AND reads the
    installed CLI's version back.
    """
    out: list[str] = []
    dockerfile = _read(root / DOCKERFILE)

    m = _DOCKERFILE_VERSION_ARG.search(dockerfile)
    if not m:
        out.append(f"{DOCKERFILE}: no ARG HERMES_VERSION found (expected {HERMES_VERSION})")
    elif m.group("value") != HERMES_VERSION:
        out.append(f"{DOCKERFILE}: installs Hermes {m.group('value')} (expected {HERMES_VERSION})")

    c = _DOCKERFILE_COMMIT_ARG.search(dockerfile)
    if not c:
        out.append(f"{DOCKERFILE}: no ARG HERMES_INSTALL_COMMIT found (expected {HERMES_INSTALL_COMMIT})")
    elif c.group("value") != HERMES_INSTALL_COMMIT:
        out.append(f"{DOCKERFILE}: pins install commit {c.group('value')} (expected {HERMES_INSTALL_COMMIT})")

    a = _DOCKERFILE_INSTALL_ARGS.search(dockerfile)
    if not a or "--commit ${HERMES_INSTALL_COMMIT}" not in a.group("value"):
        out.append(
            f"{DOCKERFILE}: HERMES_INSTALL_ARGS does not pass ${{HERMES_INSTALL_COMMIT}} "
            "to install.sh via --commit (a floating stable-channel checkout is what this refuses)"
        )

    script = _read(root / INSTALL_SCRIPT)
    v = _INSTALL_VERSION_DEFAULT.search(script)
    if not v:
        out.append(f"{INSTALL_SCRIPT}: no HERMES_VERSION default found (expected {HERMES_VERSION})")
    elif v.group("value") != HERMES_VERSION:
        out.append(f"{INSTALL_SCRIPT}: expects Hermes {v.group('value')} (expected {HERMES_VERSION})")
    if "hermes --version" not in script:
        out.append(f"{INSTALL_SCRIPT}: the installed Hermes version is never read back")
    return out


def report(root: Path = REPO) -> str:
    lines = [
        f"[model-pin] pinned: {MODEL_ID} via alias {ALIAS} "
        f"(max_tokens={MAX_TOKENS}, context_window={CONTEXT_WINDOW})",
        f"[model-pin] {DOCKERFILE}: {pin_in_dockerfile(root) or '(none)'}",
        f"[model-pin] {INSTALL_SCRIPT}: {pin_in_install_script(root) or '(none)'}",
        f"[model-pin] hermes: {HERMES_VERSION} installed at commit {HERMES_INSTALL_COMMIT} (issue #2932)",
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
            "[model-pin] FAIL: the bots would call a different model than the pin "
            "(issue #405); move every value above together",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
