"""A stand-in for `hermes_nerve.profiles` from keeltrace/hermes-nerve (issue #238).

WHY A STAND-IN: the plugin is a third-party package that is installed FROM ITS PINNED COMMIT at
image build time, so it cannot be vendored into this repo, and the unit job has no plugin. What
the tests need to prove is OUR wiring: that `scripts/install_nerve_ci.sh` selects a profile,
writes it where the plugin reads it, and refuses a profile the plugin does not know.

So this file reproduces the REAL module's contract, taken from the v0.3.1 source
(`hermes_nerve/profiles.py`): the five profile names, the sidecar path
`$HERMES_HOME/nerve/profile.json`, strict validation (version must be the int 1; the profile name
is normalised to lower_snake and must be known; module ids must be known and boolean; advanced
keys must be strings and must not start with `nerve_`), and an atomic replace. The real module is
what runs inside the image, and the image build verifies it with the real loader — which is why
this file is a stand-in for a DEPENDENCY, not a mock of the product under test.

NOT a copy of the real implementation: no module registry, no backup recovery, no file locking.
Only the contract the install script and the preflight depend on.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

PROFILE_NAMES = ("fat_cat", "operator", "lean", "marie_kondo", "custom", "legacy")
#: The subset of module ids the real bundle defines; enough to reject an unknown override.
MODULES = ("reflex", "nervous", "work_submission", "work_supervision", "token_trajectory",
           "receipts", "action_gate", "context_governor", "local_learning", "shadow_testing",
           "shared_context")


def hermes_home() -> Path:
    """The active Hermes home, resolved the way the real plugin resolves it."""
    for var in ("HERMES_HOME", "HERMES_CI_HOME"):
        value = os.environ.get(var)
        if value:
            return Path(value).expanduser()
    return Path.home() / ".hermes"


def normalize_profile_name(value: object) -> str:
    raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    while "__" in raw:
        raw = raw.replace("__", "_")
    return raw


def profile_path(home: str | Path | None = None) -> Path:
    base = Path(home).expanduser() if home is not None else hermes_home()
    return base / "nerve" / "profile.json"


def validate_profile(data: dict) -> dict:
    if not isinstance(data, dict) or set(data) - {"version", "nerve_profile", "nerve_modules", "advanced"}:
        raise ValueError("Invalid profile document")
    if type(data.get("version")) is not int or data["version"] != 1:
        raise ValueError("Unsupported profile version")
    name = normalize_profile_name(data.get("nerve_profile"))
    if name not in PROFILE_NAMES:
        raise ValueError("Unknown Nerve profile")
    modules = data.get("nerve_modules", {})
    advanced = data.get("advanced", {})
    if not isinstance(modules, dict) or any(k not in MODULES or type(v) is not bool
                                            for k, v in modules.items()):
        raise ValueError("Module overrides must contain known module IDs and booleans")
    if not isinstance(advanced, dict) or any(not isinstance(k, str) or k.startswith("nerve_")
                                             for k in advanced):
        raise ValueError("Invalid advanced settings")
    return json.loads(json.dumps(dict(data, nerve_profile=name, nerve_modules=modules,
                                      advanced=advanced), allow_nan=False))


def save_profile(data: dict, home: str | Path | None = None) -> Path:
    """Validate, then write atomically — the real module writes through a locked, atomic replace."""
    payload = (json.dumps(validate_profile(data), indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    path = profile_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return path


def load_profile(home: str | Path | None = None) -> dict | None:
    """The profile as the plugin would load it (None when there is no sidecar)."""
    path = profile_path(home)
    try:
        return validate_profile(json.loads(path.read_text(encoding="utf-8")))
    except FileNotFoundError:
        return None
