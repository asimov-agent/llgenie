#!/usr/bin/env python3
"""Apply `agents/hermes-base-config.yaml` to a Hermes home (issue #2929).

The model chain gets ONE home in this repo — `agents/hermes-base-config.yaml` —
and this script is the only writer of its keys into any Hermes config. It merges
the OWNED keys — the `model:` route (`default`, `provider`, `base_url`,
`key_env`, `max_tokens`, `context_window`), `model.aliases`, and
`fallback_providers` — into the target `config.yaml`, keeping every other key
the home already has (a profile may add its own tool settings; only the keys
below are owned).

OWNED-key semantics (issue #2929, shape measured against Hermes 0.23.2):
  * `model.default` / `provider` / `base_url` / `key_env` / `max_tokens` /
    `context_window` are replaced with the base values — a profile run
    (`hermes -p <lane>`, no `-m`) resolves the PROFILE config as its whole
    route, so the route travels with the chain or the profile wizard-steps.
  * every alias the base declares is written with the base's exact mapping;
    an alias the base does NOT declare is left in place (a profile's own
    addition), but an alias the base declares with a DIFFERENT value is drift.
  * `fallback_providers` is replaced with the base's ordered list — the order
    IS the chain (Nous free first, deepseek-v4-flash-0731 LAST), and each
    entry carries its own custom route (a `nous`-provider entry is skipped by
    the hop: the bundled provider is OAuth-only).

Usage:
  apply_hermes_base_config.py --home <hermes-home>            # write one home
  apply_hermes_base_config.py --profiles-parent <dir>          # write every profile home below it
  apply_hermes_base_config.py ... --check                      # compare only; exit 1 on drift
  apply_hermes_base_config.py --all                            # global home ($HERMES_HOME or ~/.hermes) AND profiles

Exit codes: 0 ok, 1 drift/unapplied (`--check`), 2 unreadable/unwritable config
or missing PyYAML — never a silent pass (mirrors scripts/hermes_skills_register.py).
"""
from __future__ import annotations

import argparse
import copy
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BASE_CONFIG = "agents/hermes-base-config.yaml"
ROUTE_KEYS = ("default", "provider", "base_url", "key_env", "max_tokens",
              "context_window")  # inside `model:` (issue #2929: the route travels)
OWNED_KEYS = ROUTE_KEYS + ("aliases",)  # inside `model:`
FALLBACK_KEY = "fallback_providers"  # top level


def _yaml():
    try:
        import yaml  # noqa: PLC0415  (a hard dependency of Hermes; absent is a loud failure)
    except ModuleNotFoundError:
        print("[base-config] PyYAML is not installed, so config.yaml cannot be edited safely "
              "(it ships with Hermes; run this inside the agent image)", file=sys.stderr)
        raise SystemExit(2) from None
    return yaml


def load_base(root: Path = REPO) -> dict:
    """The base config as a plain dict — the ONE source of truth for the chain."""
    path = root / BASE_CONFIG
    if not path.is_file():
        raise SystemExit(f"[base-config] {path} is missing: the chain has no home")
    data = _yaml().safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"[base-config] {path} is not a YAML mapping")
    for key in ("model", FALLBACK_KEY):
        if key not in data:
            raise SystemExit(f"[base-config] {path}: no `{key}` section")
    model = data["model"]
    if not isinstance(model, dict) or not isinstance(model.get("aliases"), dict):
        raise SystemExit(f"[base-config] {path}: `model.aliases` must be a mapping")
    for key in ROUTE_KEYS:
        if key not in model:
            raise SystemExit(f"[base-config] {path}: `model.{key}` is missing — the chain "
                             "declares its own route (a profile run has no other)")
    if not isinstance(data[FALLBACK_KEY], list) or not data[FALLBACK_KEY]:
        raise SystemExit(f"[base-config] {path}: `{FALLBACK_KEY}` must be a non-empty list")
    return data


def config_path(home: Path) -> Path:
    return home / "config.yaml"


def _read_target(path: Path) -> dict:
    if not path.is_file():
        return {}
    data = _yaml().safe_load(path.read_text(encoding="utf-8") or "") or {}
    if not isinstance(data, dict):
        raise SystemExit(f"[base-config] {path} is not a YAML mapping")
    return data


def _owned_view(data: dict) -> dict:
    """The owned subtree of a config, for exact comparison."""
    model = data.get("model") or {}
    if not isinstance(model, dict):
        model = {}
    view = {key: model.get(key) for key in ROUTE_KEYS}
    view["aliases"] = model.get("aliases") or {}
    view[FALLBACK_KEY] = data.get(FALLBACK_KEY)
    return view


def drift(home: Path, base: dict) -> list[str]:
    """Every owned key that does not match the base, as one line each."""
    out: list[str] = []
    data = _read_target(config_path(home))
    view = _owned_view(data)
    for key in ROUTE_KEYS:
        want = base["model"].get(key)
        if view[key] != want:
            out.append(f"{config_path(home)}: model.{key} is {view[key]!r} (expected {want!r})")
    aliases = view["aliases"]
    if not isinstance(aliases, dict):
        out.append(f"{config_path(home)}: model.aliases is not a mapping")
        aliases = {}
    for name, want in base["model"]["aliases"].items():
        got = aliases.get(name)
        if got is None:
            out.append(f"{config_path(home)}: alias {name} is missing")
        elif got != want:
            out.append(f"{config_path(home)}: alias {name} differs from the base config")
    fallback = view[FALLBACK_KEY]
    want_fallback = base[FALLBACK_KEY]
    if fallback != want_fallback:
        out.append(f"{config_path(home)}: {FALLBACK_KEY} is {fallback!r} "
                   f"(expected the base order ending {want_fallback[-1].get('model')!r})")
    return out


def apply(home: Path, base: dict) -> None:
    """Write the owned keys into *home*'s config.yaml, keeping everything else."""
    yaml = _yaml()
    path = config_path(home)
    data = _read_target(path)
    model = data.get("model")
    if model is None:
        model = data["model"] = {}
    if not isinstance(model, dict):
        raise SystemExit(f"[base-config] {path}: `model` is not a mapping")
    for key in ROUTE_KEYS:
        model[key] = copy.deepcopy(base["model"][key])  # load_base validated every one
    aliases = model.get("aliases")
    if aliases is None:
        aliases = model["aliases"] = {}
    if not isinstance(aliases, dict):
        raise SystemExit(f"[base-config] {path}: `model.aliases` is not a mapping")
    for name, value in base["model"]["aliases"].items():
        aliases[name] = copy.deepcopy(value)
    data[FALLBACK_KEY] = copy.deepcopy(base[FALLBACK_KEY])
    home.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, default_flow_style=False),
                    encoding="utf-8")


def profile_homes(parent: Path, match: str = "llgenie-*") -> list[Path]:
    """Every profile home below *parent* that this repo's chain owns — the llgenie lane
    profiles. Foreign profiles under the same parent (tll-*, personal homes) are NOT
    touched: the base config is llgenie's, not the whole Hermes fleet's."""
    import fnmatch  # noqa: PLC0415
    homes: list[Path] = []
    if not parent.is_dir():
        raise SystemExit(f"[base-config] profiles parent {parent} does not exist")
    for child in sorted(parent.iterdir()):
        if child.is_dir() and fnmatch.fnmatch(child.name, match):
            homes.append(child)
    return homes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    # Non-exclusive on purpose: --all may NAME its home and profiles parent (--all --home H
    # --profiles-parent P), which is exactly how the host target and the tests drive it.
    parser.add_argument("--home", help="one Hermes home holding config.yaml")
    parser.add_argument("--profiles-parent", default=None,
                        help="apply to every matching profile home below this directory")
    parser.add_argument("--all", action="store_true",
                        help="the global home (--home or $HERMES_HOME or ~/.hermes) AND every matching "
                             "home below --profiles-parent (default: <home>/profiles)")
    parser.add_argument("--lanes", action="store_true",
                        help="every matching profile home below --profiles-parent WITHOUT the global "
                             "home — the host target's scope: the interactive default home's own "
                             "model config is not the bots' chain's owner (issue #2929)")
    parser.add_argument("--match", default="llgenie-*",
                        help="profile directory glob the chain owns (default: llgenie-*)")
    parser.add_argument("--base", default=str(REPO / BASE_CONFIG),
                        help=argparse.SUPPRESS)
    parser.add_argument("--root", default=str(REPO), help=argparse.SUPPRESS)
    parser.add_argument("--check", action="store_true",
                        help="compare the owned keys without writing; exit 1 on drift")
    args = parser.parse_args(argv)

    if not (args.home or args.profiles_parent or args.all or args.lanes):
        parser.error("one of --home / --profiles-parent / --all / --lanes is required")

    base = load_base(Path(args.root))
    global_home = Path(args.home or os.environ.get("HERMES_HOME") or
                       Path.home() / ".hermes").expanduser()
    parent = Path(args.profiles_parent or os.environ.get("HERMES_PROFILES_DIR") or
                  global_home / "profiles")
    if args.all:
        homes = [global_home] + profile_homes(parent, args.match)
    elif args.home and not (args.lanes or args.profiles_parent):
        homes = [global_home]
    else:
        homes = profile_homes(parent, args.match)

    if not homes:
        print("[base-config] no Hermes homes found under the given parent — refusing to pass vacuously",
              file=sys.stderr)
        return 1

    if args.check:
        bad = [line for home in homes for line in drift(home, base)]
        for line in bad:
            print(f"[base-config] FINDING {line}", file=sys.stderr)
        if bad:
            print(f"[base-config] FAIL: {len(bad)} drift(s) across {len(homes)} home(s) "
                  "(issue #2929: the chain must be identical in every lane)", file=sys.stderr)
            return 1
        print(f"[base-config] OK: {len(homes)} home(s) carry the base chain "
              f"({base['model']['default']} primary, "
              f"{base['fallback_providers'][-1]['model']} last)")
        return 0

    for home in homes:
        apply(home, base)
    # read-back: the write is only real if the owned keys come back identical
    bad = [line for home in homes for line in drift(home, base)]
    for line in bad:
        print(f"[base-config] FINDING {line}", file=sys.stderr)
    if bad:
        print("[base-config] FAIL: the config was written but the read-back drifts", file=sys.stderr)
        return 1
    print(f"[base-config] applied to {len(homes)} home(s); chain "
          f"{base['model']['default']} → ... → {base['fallback_providers'][-1]['model']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
