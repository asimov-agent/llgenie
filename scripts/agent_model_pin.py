#!/usr/bin/env python3
"""The bots' model CHAIN, declared ONCE, and a gate that refuses drift (issue #405 → #2929).

The chain has ONE home in this repo: `agents/hermes-base-config.yaml`. Nous FREE models run
first (`nous-longcat` primary), the other free models are the ordered fallbacks, and the paid
`deepseek/deepseek-v4-flash-0731` sits LAST. The install step lands it into the agent image's
global Hermes home and `scripts/provision_agent_profiles.py` lands the identical chain into
every lane profile's config.yaml — bots run as their lane profile (`hermes -p llgenie-<lane>`)
and load the chain from that config. No bot call carries a `-m <model>` flag any more.

Every chain entry is a CUSTOM provider alias: Hermes's bundled `nous` provider is OAuth-only,
so a secret-supplied NOUS_API_KEY only works through an alias pointed at the Nous inference
endpoint (history: see scripts/install_hermes_ci.sh).

This module is the referee:

    python3 scripts/agent_model_pin.py check     # non-zero on drift, naming file + value
    python3 scripts/agent_model_pin.py report    # what each place says

It checks (issue #2929): the base config's structure and ORDER (free first, deepseek-0731
LAST), every alias's wiring (custom provider, the endpoint, NOUS_API_KEY, a written budget),
that the install/provision seams are the writers, that the single-pin build ARGs stayed dead,
that no `-m` bot call survived, and — unchanged from issue #405/#2932 — the Hermes release pin.
Stdlib + PyYAML only, no network, no key. A different snapshot or a re-ordered chain is drift,
never "close enough".
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from apply_hermes_base_config import BASE_CONFIG, load_base  # noqa: E402

REPO = Path(__file__).resolve().parent.parent

# ---- the chain policy (the referee's expectation, issue #2929) ---------------------------
PRIMARY_ALIAS = "nous-longcat"                    # the first alias in the map
PRIMARY_MODEL = "meituan/longcat-2.5:free"        # model.default carries the REAL id:
#   Hermes profile routing sends model.default straight to the endpoint; a bare alias there
#   404s (measured against Hermes 0.23.2). Aliases resolve only for an explicit -m switch.
LAST_MODEL = "deepseek/deepseek-v4-flash-0731"  # the ONLY paid model, and it is LAST
FREE_SUFFIX = ":free"
NOUS_ENDPOINT = "https://inference-api.nousresearch.com/v1"
MAX_TOKENS = 16000                            # every alias carries a written budget
KEY_ENV = "NOUS_API_KEY"
MODEL_ROUTE = {"provider": "custom", "base_url": NOUS_ENDPOINT, "key_env": KEY_ENV,
               "max_tokens": MAX_TOKENS}          # the route a profile run must carry

HERMES_VERSION = "0.23.2"
HERMES_INSTALL_COMMIT = "ae2a81ccc00e9b7c06301523e5bb09608397149c"

DOCKERFILE = "containers/agent/Dockerfile"
INSTALL_SCRIPT = "scripts/install_hermes_ci.sh"

# The Hermes version pin (issue #2932), unchanged.
_DOCKERFILE_VERSION_ARG = re.compile(r'^ARG\s+HERMES_VERSION="?(?P<value>[^"\s]+)"?\s*#?.*$', re.MULTILINE)
_DOCKERFILE_COMMIT_ARG = re.compile(r'^ARG\s+HERMES_INSTALL_COMMIT="?(?P<value>[^"\s]+)"?\s*#?.*$', re.MULTILINE)
_DOCKERFILE_INSTALL_ARGS = re.compile(r'^ARG\s+HERMES_INSTALL_ARGS="(?P<value>[^"]*)"', re.MULTILINE)
_INSTALL_VERSION_DEFAULT = re.compile(
    r'^HERMES_VERSION="\$\{HERMES_VERSION:-(?P<value>[^}]+)\}"', re.MULTILINE
)

# Where a model flag must NOT appear any more: the bot call sites (issue #2929).
BOT_CALL_FILES = ("Makefile", "mk/bots.mk", "mk/agents.mk", "mk/engines.mk", "scripts/fix_loop.sh")
_MODEL_FLAG = re.compile(r'(?:-m|--model)\s+[\w"$.{}-]*(?:nous|deepseek|longcat)[\w$.{}:-]*')
_ALIAS_RE = re.compile(r'nous-alias|nous-model')
_PROFILE_FLAG = re.compile(r'-p\s+(llgenie-[\w-]+)')


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:  # a missing input is a finding, never a skip
        raise SystemExit(f"[model-pin] cannot read {path}: {exc}")


def chain_findings(root: Path = REPO) -> list[str]:
    """Every way the ONE home of the chain fails the policy, as one line each."""
    out: list[str] = []
    try:
        base = load_base(root)
    except SystemExit as exc:  # the seam's own unreadable/missing-base failure, phrased as a finding
        return [str(exc)]

    model = base["model"]
    aliases = model["aliases"]
    default = model.get("default")
    if default != PRIMARY_MODEL:
        hint = " (an ALIAS at model.default 404s: profile routing sends it to the endpoint unresolved)" \
            if default == PRIMARY_ALIAS else ""
        out.append(f"{BASE_CONFIG}: model.default is {default!r} (expected the real primary id "
                   f"{PRIMARY_MODEL!r}{hint})")
    for key, want in MODEL_ROUTE.items():
        if model.get(key) != want:
            out.append(f"{BASE_CONFIG}: model.{key} is {model.get(key)!r} (expected {want!r}: "
                       "a profile run resolves the profile config as its whole route)")
    if not isinstance(model.get("context_window"), int) or model.get("context_window") <= 0:
        out.append(f"{BASE_CONFIG}: model.context_window is not a positive int")
    if aliases.get(PRIMARY_ALIAS, {}).get("model") != PRIMARY_MODEL:
        out.append(f"{BASE_CONFIG}: alias {PRIMARY_ALIAS} must map to {PRIMARY_MODEL!r}")

    # every alias: custom provider, the endpoint, the secret's env name, a written budget
    for name, entry in aliases.items():
        if not isinstance(entry, dict):
            out.append(f"{BASE_CONFIG}: alias {name} is not a mapping")
            continue
        for key, want in (("provider", "custom"), ("base_url", NOUS_ENDPOINT),
                          ("key_env", KEY_ENV), ("max_tokens", MAX_TOKENS)):
            if entry.get(key) != want:
                out.append(f"{BASE_CONFIG}: alias {name}.{key} is {entry.get(key)!r} (expected {want!r})")
        if not isinstance(entry.get("context_window"), int) or entry["context_window"] <= 0:
            out.append(f"{BASE_CONFIG}: alias {name} has no positive context_window")
        mid = entry.get("model")
        if not isinstance(mid, str) or not mid:
            out.append(f"{BASE_CONFIG}: alias {name} declares no model id")

    # the fallback list IS the rest of the chain: every non-primary alias model, in the order
    # the aliases declare them, the paid model LAST. The primary is not its own fallback —
    # Hermes hops only after the primary fails, and hopping back to it is a silent retry.
    fallback = base["fallback_providers"]
    order = [e.get("model") if isinstance(e, dict) else e for e in fallback]
    alias_models = [e.get("model") for e in aliases.values() if isinstance(e, dict)]
    want_order = [m for m in alias_models if m != aliases.get(PRIMARY_ALIAS, {}).get("model")]
    if order != want_order:
        out.append(f"{BASE_CONFIG}: fallback_providers is {order} (expected the non-primary "
                   f"chain in declared order: {want_order})")
    if order and order[-1] != LAST_MODEL:
        out.append(f"{BASE_CONFIG}: fallback_providers ends with {order[-1]!r} "
                   f"(expected {LAST_MODEL!r} LAST)")
    for entry in order[:-1]:
        if not str(entry).endswith(FREE_SUFFIX):
            out.append(f"{BASE_CONFIG}: fallback {entry!r} is not a FREE model — only the LAST "
                       f"entry of the chain may be paid")
    if LAST_MODEL in [str(m) for m in order[:-1]]:
        out.append(f"{BASE_CONFIG}: {LAST_MODEL} appears before the last position — the paid "
                   "fallback is LAST or nowhere")
    if len(set(order)) != len(order):
        out.append(f"{BASE_CONFIG}: fallback_providers repeats a model (order: {order})")
    chain_models = {str(m) for m in order}
    declared = {m for m in alias_models if m}
    if chain_models - declared:
        out.append(f"{BASE_CONFIG}: fallback names models no alias declares: "
                   f"{sorted(chain_models - declared)}")
    # each fallback entry is a full custom route: a hop resolves the ENTRY (its provider +
    # base_url + key_env), not the profile — Hermes's bundled `nous` provider is OAuth-only
    # and a hop aimed at it is silently skipped (fallback_config.py, measured 2026-11-19)
    for pos, entry in enumerate(fallback):
        if not isinstance(entry, dict):
            out.append(f"{BASE_CONFIG}: fallback_providers[{pos}] is not a mapping")
            continue
        if entry.get("provider") != "custom":
            out.append(f"{BASE_CONFIG}: fallback_providers[{pos}] names provider "
                       f"{entry.get('provider')!r} — hops need a full custom route")
        for key, want in (("base_url", NOUS_ENDPOINT), ("key_env", KEY_ENV)):
            if entry.get(key) != want:
                out.append(f"{BASE_CONFIG}: fallback_providers[{pos}].{key} is "
                           f"{entry.get(key)!r} (expected {want!r})")

    # the seams are the only writers, and they must be wired (issue #2929)
    script = _read(root / INSTALL_SCRIPT)
    if "apply_hermes_base_config.py" not in script:
        out.append(f"{INSTALL_SCRIPT}: does not apply the base config — the chain has no installer")
    dockerfile = _read(root / DOCKERFILE)
    if "apply_hermes_base_config.py --check" not in dockerfile:
        out.append(f"{DOCKERFILE}: the build does not re-check the chain against {BASE_CONFIG}")
    if "apply_hermes_base_config.py" not in _read(root / "scripts/provision_agent_profiles.py"):
        out.append("scripts/provision_agent_profiles.py: does not land the chain into lane profiles")
    # profile mode resolves key_env from the PROFILE's OWN .env (measured against Hermes 0.23.2):
    # a key only in the leg's exported environment authenticates nothing, so the image must seed
    # it at leg start (issue #2929)
    if "seed_profile_hermes_env.py" not in dockerfile:
        out.append(f"{DOCKERFILE}: no seed_profile_hermes_env.py hook — a profile run cannot read "
                   "its key_env from the profile .env the image never seeds")

    # the single-pin build ARGs are dead (issue #2929): an ARG naming a model is drift
    for arg in ("HERMES_MODEL_ID", "HERMES_ALIAS", "HERMES_MAX_TOKENS", "HERMES_CONTEXT_WINDOW"):
        if re.search(rf'^ARG\s+{arg}\b', dockerfile, re.MULTILINE):
            out.append(f"{DOCKERFILE}: ARG {arg} is back — the chain has ONE home, not build args")

    # no bot call names a model (issue #2929): profiles load the chain — and every profile a
    # bot call names must be a lane the image installs (issue #2181: a `-p` lane absent from
    # agents/manifest.json resolves against an empty profile home at run time)
    try:
        declared_lanes = {p["name"] for p in json.loads(_read(root / "agents" / "manifest.json"))["profiles"]}
    except (SystemExit, json.JSONDecodeError, KeyError) as exc:
        out.append(f"agents/manifest.json: unreadable lane roster ({exc}) — no `-p` call can be checked")
        declared_lanes = set()
    for rel in BOT_CALL_FILES:
        text = _read(root / rel)
        for m in _MODEL_FLAG.finditer(text):
            out.append(f"{rel}: a bot call names a model ({m.group(0)!r}) — bots run as lane "
                       f"profiles and load the chain (issue #2929)")
        if _ALIAS_RE.search(text):
            out.append(f"{rel}: references the retired nous-alias/nous-model variables")
        for lane in sorted(set(_PROFILE_FLAG.findall(text)) - declared_lanes):
            out.append(f"{rel}: bot call names -p {lane}, which agents/manifest.json does not "
                       f"declare — the image would not install it (issue #2181)")
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
        f"[model-pin] chain home: {BASE_CONFIG} (primary {PRIMARY_ALIAS} = {PRIMARY_MODEL}, "
        f"paid LAST {LAST_MODEL})",
        f"[model-pin] hermes: {HERMES_VERSION} installed at commit {HERMES_INSTALL_COMMIT} (issue #2932)",
    ]
    bad = chain_findings(root) + version_findings(root)
    lines.extend(f"[model-pin] FINDING {f}" for f in bad)
    lines.append(f"[model-pin] {'OK' if not bad else f'{len(bad)} finding(s)'}")
    return "\n".join(lines)


def findings(root: Path = REPO) -> list[str]:
    """The gate's aggregate: chain drift + Hermes version drift (issue #2929 + #2932)."""
    return chain_findings(root) + version_findings(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check the bots' model chain against its ONE home and the seams that install it"
    )
    parser.add_argument("command", choices=("check", "report"))
    parser.add_argument("--root", default=str(REPO), help="repository root (default: this checkout)")
    args = parser.parse_args(argv)
    root = Path(args.root)
    if args.command == "report":
        print(report(root))
        return 0

    bad = findings(root)
    print(report(root))
    if bad:
        print(
            "[model-pin] FAIL: a bot would run a model the chain does not declare "
            "(issue #2929); fix the ONE home or the seam, never a call site",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
