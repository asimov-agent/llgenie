#!/usr/bin/env python3
"""Register the checkout's `.hermes/skills` with Hermes, so `hermes -s <name>` resolves (issue #577).

Every bot leg preloads its contract with `hermes -s <name>`. Hermes looks for skills in its own
home and in `skills.external_dirs`, so the repository's skill directory has to be registered in the
agent image's `$HERMES_HOME/config.yaml` — once, at build time. The leg runs with `/repo` mounted,
which is why `--dir` defaults to that path.

Why this script instead of `hermes config set skills.external_dirs …`: the CLI's value parsing
differs across versions. A newer Hermes refuses a bare string ("it must be a list"), an older one
(the pinned `hermes-agent==0.19.0`) stores a JSON literal as an opaque STRING, which
`get_external_skills_dirs()` then treats as one non-existent path — both forms fail on one side. A
real YAML list is read correctly by every version, so this writes the list itself and reads it back.

`--check` verifies a home without writing (the build's read-back). Exit codes: 0 ok, 1 not
registered (`--check`), 2 unreadable/unwritable config or missing PyYAML — never a silent pass.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

KEY = "external_dirs"


def _yaml():
    try:
        import yaml  # noqa: PLC0415  (a hard dependency of Hermes; absent is a loud failure)
    except ModuleNotFoundError:
        print("[hermes-skills] PyYAML is not installed, so config.yaml cannot be edited safely "
              "(it ships with Hermes; run this inside the agent image)", file=sys.stderr)
        raise SystemExit(2) from None
    return yaml


def config_path(home: Path) -> Path:
    return home / "config.yaml"


def read_dirs(path: Path) -> list[str]:
    """`skills.external_dirs` as a plain list of strings, from any of the shapes a Hermes writes."""
    if not path.is_file():
        return []
    data = _yaml().safe_load(path.read_text(encoding="utf-8") or "") or {}
    if not isinstance(data, dict):
        print(f"[hermes-skills] {path} is not a YAML mapping", file=sys.stderr)
        raise SystemExit(2)
    skills = data.get("skills") or {}
    if not isinstance(skills, dict):
        print(f"[hermes-skills] {path}: `skills` is not a mapping", file=sys.stderr)
        raise SystemExit(2)
    raw = skills.get(KEY)
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(entry) for entry in raw if isinstance(entry, (str, os.PathLike))]
    print(f"[hermes-skills] {path}: `skills.{KEY}` is a {type(raw).__name__}, expected a list",
          file=sys.stderr)
    raise SystemExit(2)


def registered(home: Path, directory: Path) -> bool:
    want = str(directory)
    return any(os.path.abspath(entry) == os.path.abspath(want) for entry in read_dirs(config_path(home)))


def register(home: Path, directory: Path) -> list[str]:
    """Add *directory* to `skills.external_dirs`, keeping everything else, and return the result."""
    yaml = _yaml()
    path = config_path(home)
    data = {}
    if path.is_file():
        data = yaml.safe_load(path.read_text(encoding="utf-8") or "") or {}
        if not isinstance(data, dict):
            print(f"[hermes-skills] {path} is not a YAML mapping", file=sys.stderr)
            raise SystemExit(2)
    skills = data.get("skills")
    if skills is None:
        skills = data["skills"] = {}
    if not isinstance(skills, dict):
        print(f"[hermes-skills] {path}: `skills` is not a mapping", file=sys.stderr)
        raise SystemExit(2)
    dirs = read_dirs(path)
    if not registered(home, directory):
        dirs.append(str(directory))
    skills[KEY] = dirs
    home.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, default_flow_style=False),
                    encoding="utf-8")
    return read_dirs(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--home", default=os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes"),
                        help="Hermes home holding config.yaml (default: $HERMES_HOME or ~/.hermes)")
    parser.add_argument("--dir", default=str(Path("/repo/.hermes/skills")),
                        help="the skill directory to register (default: /repo/.hermes/skills)")
    parser.add_argument("--check", action="store_true",
                        help="verify the registration without writing; exit 1 when it is missing")
    args = parser.parse_args(argv)
    home = Path(args.home).expanduser()
    directory = Path(args.dir).expanduser()

    if args.check:
        if registered(home, directory):
            print(f"[hermes-skills] {directory} is registered in {config_path(home)}")
            return 0
        print(f"[hermes-skills] {directory} is NOT in skills.{KEY} of {config_path(home)}: every "
              "bot leg would preload no skill at all", file=sys.stderr)
        return 1

    dirs = register(home, directory)
    print(f"[hermes-skills] skills.{KEY} = {dirs} ({config_path(home)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
