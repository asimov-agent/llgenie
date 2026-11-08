"""A pinned engine release's native archives: list, classify and unpack (issue #830, #795).

This module is the ONE owner of the "does this tag ship a native archive, and how
is it installed" question. It sits BELOW both directions of the bump pipeline:

    engine_bump  ->  derive  ->  engine_release_archive

`engine_bump` imports it to turn a derived `release_assets` finding into install
steps, and `engine_params_derive` imports it to read the release while deriving.
Before issue #795 that reverse edge ran `engine_params_derive -> engine_bump`, a
function-local import that made the two modules a cycle: `import
scripts.engine_bump` dragged in the whole derive pipeline and was invisible to
any static analysis. The shared step lives here so the graph is one-directional.

`engine_bump` re-exports these names (`_release_assets`, `_native_archives`,
`_pip_install`, `release_archive_install`), so the bump pipeline's public surface
is unchanged for callers and tests.

Stdlib only: it runs in the test image.
"""
from __future__ import annotations

import os
import re

# (backend) -> (os token, arch token) in `<name>-<version>-<os>-<arch>.tar.gz`.
_ARCHIVE_TARGET = {"cuda": ("linux", "x86_64"), "rocm": ("linux", "x86_64"),
                   "vulkan": ("linux", "x86_64"), "cpu": ("linux", "x86_64"),
                   "metal": ("macos", "arm64")}
_ARCHIVE = re.compile(r"^(?P<name>.+)-(?P<ver>[0-9][0-9.]*)-(?P<os>linux|macos)-(?P<arch>[A-Za-z0-9_]+)\.tar\.gz$")


def _github_token() -> str:
    """The forwarded GitHub token. `GITHUB_TOKEN`, else `GH_TOKEN`. Never logged."""
    for key in ("GITHUB_TOKEN", "GH_TOKEN"):
        token = os.environ.get(key, "").strip()
        if token:
            return token
    return ""


def _release_json(url: str, headers: dict) -> dict:
    import json as _json
    import urllib.request
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = _json.load(r)
    return data if isinstance(data, dict) else {}


def _release_assets(repo: str, tag: str) -> list[dict]:
    """The published GitHub release's assets for `tag`. Empty on any failure
    (a missing release is "no archive", not a hard fail — other engines continue).

    Sends the token the test container forwarded (`GITHUB_TOKEN`, else
    `GH_TOKEN`). An installation token is scoped to this repository and GitHub
    answers 401 or 403 for another public repo; that one denial is retried
    with no Authorization header.
    """
    m = re.match(r"https?://github\.com/([^/]+/[^/]+?)(?:\.git)?/?$", repo.strip())
    if not m:
        return []
    url = f"https://api.github.com/repos/{m.group(1)}/releases/tags/{tag}"
    base = {"Accept": "application/vnd.github+json", "User-Agent": "llgenie-engine-bump"}
    token = _github_token()
    headers = dict(base)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        data = _release_json(url, headers)
    except Exception as exc:
        if not (token and getattr(exc, "code", None) in (401, 403)):
            return []
        try:
            data = _release_json(url, base)
        except Exception:
            return []
    return [{"name": a.get("name", "")} for a in data.get("assets") or []]


def _native_archives(assets: list[dict]) -> dict[tuple[str, str], str]:
    """`(os, arch) -> asset name` for archives that ship a sibling `.sha256`."""
    names = {a["name"] for a in assets}
    out = {}
    for name in sorted(names):
        m = _ARCHIVE.match(name)
        if m and f"{name}.sha256" in names:
            out[(m.group("os"), m.group("arch"))] = name
    return out


def _pip_install(steps) -> bool:
    return any(re.search(r"\b(uv|pip3?)\b", str(s)) and "git+" in str(s) for s in (steps or []))


def release_archive_install(skill: dict, assets: list[dict]) -> dict | None:
    """Install steps that unpack the release archive, or None when the release
    is not a native-archive release (or the skill does not pip-install from git)."""
    found = _native_archives(assets)
    if not found:
        return None
    install = skill.get("install") or {}
    if not isinstance(install, dict) or not any(_pip_install(v if isinstance(v, list) else [v])
                                                for v in install.values()):
        return None
    steps_for = {}
    for backend in skill.get("backends") or []:
        target = _ARCHIVE_TARGET.get(backend)
        if target is None or target not in found:
            return None  # a backend we cannot place an archive for: do not guess
        asset = found[target]
        # `{version}` is the skill version with no leading v, which is how the
        # archive is named (tensorfold-1.0.5-linux-x86_64.tar.gz)
        ver = re.search(r"-([0-9][0-9.]*)-", asset)
        if ver is None:
            return None
        asset_tmpl = asset.replace(f"-{ver.group(1)}-", "-{version}-", 1)
        check = "sha256sum -c" if target[0] == "linux" else "shasum -a 256 -c"
        # The archive's bin/ name is upstream's (tensorfold-native), not the
        # skill id. Link the one executable to {id} so binary/detect/launch
        # share one path. No pipe: the runner uses bash -o pipefail.
        link = ("exe=$(find {prefix}/{version}/bin -maxdepth 1 -type f -perm -111); "
                "set -- $exe; ln -sfn \"$1\" {prefix}/{version}/bin/{id}")
        # A pinned version in the binary path would bake {version} into detect,
        # so native_status could only ever say missing/current (issue #386).
        # Point {prefix}/current at the release and detect the INSTALLED binary
        # through it, so `binary --version` can report an older/newer release.
        steps_for[backend] = [
            "mkdir -p {prefix}/{version}",
            "curl -fsSL -o {prefix}/" + asset_tmpl + " {repo}/releases/download/v{version}/" + asset_tmpl,
            "curl -fsSL -o {prefix}/" + asset_tmpl + ".sha256 {repo}/releases/download/v{version}/" + asset_tmpl + ".sha256",
            "cd {prefix} && " + check + " " + asset_tmpl + ".sha256",
            "tar -xzf {prefix}/" + asset_tmpl + " -C {prefix}/{version} --strip-components=1",
            link,
            "ln -sfn {prefix}/{version} {prefix}/current",
        ]
    return steps_for
