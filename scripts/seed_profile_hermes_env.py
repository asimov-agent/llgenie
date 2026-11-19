#!/usr/bin/env python3
"""Land the NAME-addressed secret into the homes Hermes actually reads (issue #2929).

Hermes resolves a profile's `model.key_env` from the PROFILE's own `.env` file —
measured against Hermes 0.23.2: a `hermes -p llgenie-<lane>` run whose key sits only
in the leg's exported environment authenticates nothing ("No inference API key found
… set NOUS_API_KEY … or set model.key_env in config.yaml"); writing the key into
`$HERMES_HOME/profiles/<lane>/.env` makes the same run answer. So this script copies
each key FROM THE CALLER'S ENVIRONMENT into every target home's `.env`, touching
only the named keys and leaving every other line of the file alone.

It never invents a secret and never prints one: a key name whose value is absent
from the environment is not seeded (and with no key present at all the run is a
loud no-op, exit 0 — a keyless leg stays a keyless leg). The agent image runs this
at LEG START through an /etc/profile.d hook (every Makefile agent leg boots the
image with `bash -lc`, which sources it), so each profile home is hot by the time
a bot invokes hermes. The secret itself is never baked into the image — only its
env-var NAME is, which is what the chain's `key_env` references (AGENTS.md: no
secrets baked; the leg supplies the value at run time).

Usage:
  seed_profile_hermes_env.py --all                       # global home + llgenie-* profiles
  seed_profile_hermes_env.py --home <hermes-home>        # one home
  seed_profile_hermes_env.py --lanes [--profiles-parent P]  # profiles only
Exit codes: 0 seeded (or nothing to seed), 1 read-back verification failed, 2 no target home.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from apply_hermes_base_config import profile_homes  # noqa: E402  (the same profile roster rule)

KEYS = ("NOUS_API_KEY",)  # the names the chain's key_env fields reference; values come from HERE


def _default_home() -> Path:
    """The Hermes home the CLI itself would use: $HERMES_HOME or ~/.hermes."""
    return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")


def _env_path(home: Path) -> Path:
    return home / ".env"


def seed_home(home: Path, keys: list[str]) -> list[str]:
    """Merge KEY=value lines into *home*/.env for every name in *keys* whose value
    the caller's environment carries. Other lines survive; mode is 0600."""
    values = {name: os.environ[name] for name in keys if os.environ.get(name)}
    if not values:
        return []
    path = _env_path(home)
    existing: list[str] = []
    if path.is_file():
        existing = path.read_text(encoding="utf-8").splitlines()
    for name, value in values.items():
        pattern = re.compile(rf"^{re.escape(name)}=")
        for i, line in enumerate(existing):
            if pattern.match(line):
                existing[i] = f"{name}={value}"
                break
        else:
            existing.append(f"{name}={value}")
    home.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(existing) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)
    # read-back: the file must actually carry every seeded name (a silent failure
    # here is a leg that fails later at authentication, which is worse than now)
    written = path.read_text(encoding="utf-8")
    missing = [name for name in values if not re.search(rf"^{re.escape(name)}=", written, re.MULTILINE)]
    if missing:
        print(f"[profile-env] {path}: read-back missing {missing}", file=sys.stderr)
        raise SystemExit(1)
    return sorted(values)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--home", help="one Hermes home holding .env")
    parser.add_argument("--profiles-parent", default=None,
                        help="seed every matching profile home below this directory")
    parser.add_argument("--all", action="store_true",
                        help="the global home (--home or $HERMES_HOME or ~/.hermes) AND every "
                             "matching home below --profiles-parent (default: <home>/profiles)")
    parser.add_argument("--lanes", action="store_true",
                        help="profiles only — the interactive default home is not touched")
    parser.add_argument("--match", default="llgenie-*",
                        help="profile directory glob (default: llgenie-*; foreign profiles "
                             "under the same parent are never touched)")
    parser.add_argument("--check", action="store_true",
                        help="verify each target .env already carries every key the caller "
                             "has; exit 1 naming what is missing, write nothing")
    args = parser.parse_args(argv)

    explicit_home = Path(args.home) if args.home else None
    targets: list[Path] = []
    if args.all or args.lanes or explicit_home is None:
        home = explicit_home or _default_home()
        if not args.lanes:
            targets.append(home)
        parent = Path(args.profiles_parent) if args.profiles_parent else home / "profiles"
        try:
            targets.extend(profile_homes(parent, args.match))
        except SystemExit:
            pass  # profiles parent not created yet — the global home is still a valid target
    else:
        targets.append(explicit_home)
    if not targets:
        print("[profile-env] no target home (a profiles parent with no llgenie-* profiles "
              "is exit-2, not a vacuous pass)", file=sys.stderr)
        return 2

    present = [name for name in KEYS if os.environ.get(name)]
    if not present:
        print(f"[profile-env] nothing to seed: the caller carries none of {list(KEYS)} "
              f"(the leg exports the value; this script only moves it into the homes)",
              file=sys.stderr)
        return 0

    if args.check:
        bad = []
        for home in targets:
            path = _env_path(home)
            text = path.read_text(encoding="utf-8") if path.is_file() else ""
            for name in present:
                if not re.search(rf"^{re.escape(name)}=", text, re.MULTILINE):
                    bad.append(f"{path}: {name}")
        if bad:
            print("[profile-env] CHECK FAILED:\n  " + "\n  ".join(bad), file=sys.stderr)
            return 1
        print(f"[profile-env] check OK: {len(targets)} home(s) carry {present} (values never printed)")
        return 0

    touched = 0
    for home in targets:
        if seed_home(home, present):
            touched += 1
    print(f"[profile-env] seeded {touched}/{len(targets)} home(s); keys: {present} "
          "(values never printed; source is this leg's environment)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
