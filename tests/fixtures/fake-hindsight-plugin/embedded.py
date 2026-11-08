"""A stand-in for `plugins/hindsight/embedded.py` from the Hindsight Hermes plugin (issue #2068).

WHY A STAND-IN: the Hindsight plugin is a third-party package installed from its pinned
commit at image-build time (`hermes plugins install`), so it cannot be vendored into this
repo and the unit job has no plugin. What the tests need to prove is OUR wiring: that
`scripts/memory_bootstrap.py` reuses the plugin's env builder so the bootstrap and the
runtime agree by construction, without ever printing a credential value.

So this file reproduces the REAL module's documented contract — the entrypoints the issue
names (`_build_embedded_profile_env`, `_materialize_embedded_profile_env`,
`_embedded_profile_env_path`, `_profile_env_drifted`) and the env key set docs/BOTS.md
measures on the orchestrator host. The real module is what runs on the host through
`load_builder`; this file is a stand-in for a DEPENDENCY, not a mock of the product under
test — the same role `tests/fixtures/fake-nerve-plugin/hermes_nerve/profiles.py` plays.

NOT a copy of the real implementation: no daemon, no network, no file locking. Only the
contract the bootstrap and the verify depend on.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

#: The daemon env key set the running daemon reads from its shared env file (docs/BOTS.md).
ENV_KEYS = (
    "HINDSIGHT_API_LLM_API_KEY",
    "HINDSIGHT_API_LLM_BASE_URL",
    "HINDSIGHT_API_LLM_MODEL",
    "HINDSIGHT_API_LLM_PROVIDER",
    "HINDSIGHT_API_PORT",
    "HINDSIGHT_API_LOG_LEVEL",
    "HINDSIGHT_EMBED_DAEMON_IDLE_TIMEOUT",
)

#: The env names that carry the model/base-url/provider (verify reads /proc/<pid>/environ
#: for these when the daemon is real).
DAEMON_ENV_MODEL = "HINDSIGHT_API_LLM_MODEL"
DAEMON_ENV_BASE_URL = "HINDSIGHT_API_LLM_BASE_URL"
DAEMON_ENV_PROVIDER = "HINDSIGHT_API_LLM_PROVIDER"

_DEFAULTS = {
    "llm_provider": "openai_compatible",
    "llm_model": "deepseek/deepseek-v4-flash-0731",
    "llm_base_url": "https://inference-api.nousresearch.com/v1",
    "port": 9177,
    "idle_timeout": 0,
    "log_level": "info",
}


def _embedded_profile_env_path():
    """The shared per-profile env file the daemon reads (one per host, keyed by profile)."""
    home = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes").expanduser()
    profile = os.environ.get("HINDSIGHT_PROFILE") or "hermes"
    return home / ".hindsight" / "profiles" / f"{profile}.env"


def _build_embedded_profile_env(config: dict, profile: str | None = None,
                                api_key: str | None = None) -> dict:
    """Build the daemon env for *config* + *api_key*, using the runtime defaults.

    This mirrors the real module's key order named in the issue: config.llm_api_key ->
    the caller-supplied secret -> the on-disk profile env (with a placeholder for
    openai_compatible when no key is present at the point of resolution).
    """
    merged = dict(_DEFAULTS)
    merged.update({k: v for k, v in (config or {}).items()
                   if v is not None and k in _DEFAULTS})
    key = api_key
    if not key:
        key = (config or {}).get("llm_api_key")
    env = {
        DAEMON_ENV_MODEL: merged["llm_model"],
        DAEMON_ENV_BASE_URL: merged["llm_base_url"],
        DAEMON_ENV_PROVIDER: str(merged["llm_provider"]).lower(),
        "HINDSIGHT_API_LLM_API_KEY": key or "",
        "HINDSIGHT_API_PORT": str(merged["port"]),
        "HINDSIGHT_API_LOG_LEVEL": merged["log_level"],
        "HINDSIGHT_EMBED_DAEMON_IDLE_TIMEOUT": str(merged["idle_timeout"]),
    }
    return env


def _profile_env_drifted(expected: dict, on_disk: dict) -> bool:
    """True when the on-disk shared env differs from the expected one (the drift gate)."""
    return {k: expected.get(k, "") for k in ENV_KEYS} != {k: on_disk.get(k, "") for k in ENV_KEYS}


def _materialize_embedded_profile_env(expected: dict) -> Path:
    """Write the expected daemon env to the shared per-profile file (mode 0600)."""
    path = _embedded_profile_env_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{key}={expected.get(key, '')}" for key in ENV_KEYS]
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")
        stream.flush()
    os.chmod(path, 0o600)
    return path


def _profile_env_from_config(config: dict | None, profile: str | None = None,
                             api_key: str | None = None) -> dict:
    """Convenience: env straight from a config dict (the runtime builder's entry)."""
    return _build_embedded_profile_env(config or {}, profile=profile, api_key=api_key)


def _config_json_path():
    """The shared per-profile config.json path the plugin reads."""
    home = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes").expanduser()
    profile = os.environ.get("HINDSIGHT_PROFILE") or "hermes"
    return home / ".hindsight" / "profiles" / f"{profile}.json"
