"""Daily engine pin bump (issue #107, feat-engine-bump-daily).

Scope: update each engine skill's upstream pin to the latest commit for its
`ref`, derive the build parameters from the upstream tree (no LLM), apply the
derived params into the skill, and regenerate the params/Dockerfiles.

Commands (stdlib only):
  plan [--engine ID]        git ls-remote -> which engines moved (JSON list)
  pin  ENGINE NEW_REF NEW_SHA   targeted frontmatter edit (pinned/ref/version/verified)
  derive ENGINE [--sha] [--old-sha]   findings JSON for that sha, no writes
  bump ENGINE              pin + derive + apply + make generate-engine-params
  bump-daily [--dry]       plan -> bump each moved engine; --dry prints only

The plan list is the matrix for the engine-bump workflow's bump job. A PR exists
iff the plan found >=1 new hash. A derive hard-fail is recorded, not fatal: the
pin still moves and the PR still opens, with the hard-fail flagged in the body.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from . import engine_skills as es
    from . import engine_params_derive as epd
except ImportError:  # pragma: no cover - script mode
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import engine_skills as es
    import engine_params_derive as epd

REPO_ROOT = es.REPO_ROOT
SKILLS_DIR = es.SKILLS_DIR

# Keys the pin editor may change. Everything else in SKILL.md must stay identical.
PIN_KEYS = ("pinned", "ref", "version", "verified")
_PRE_RELEASE = re.compile(r"(rc|alpha|beta|dev|pre|post)", re.IGNORECASE)


def _run(cmd: list[str], timeout: int = 60, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)


def _ls_remote(repo: str, refspec: str, tries: int = 3) -> str:
    """Return the sha for `refspec` (e.g. 'refs/heads/master' or 'refs/tags/v1.0^{}').
    Empty string on failure after `tries` attempts with backoff."""
    for i in range(tries):
        p = _run(["git", "ls-remote", repo, refspec])
        if p.returncode == 0 and p.stdout.strip():
            return p.stdout.split()[0]
        if i < tries - 1:
            time.sleep(2 ** i)
    return ""


def _tag_shape(current_tag: str) -> re.Pattern:
    r"""Derive a regex matching tags of the same shape as the current tag.
    'v0.35.1' -> ^v\d+\.\d+\.\d+$ ; 'b6500' -> ^b\d+$ ; '1.2.3' -> ^\d+\.\d+\.\d+$."""
    s = current_tag.lstrip("v")
    if re.fullmatch(r"\d+\.\d+\.\d+", s):
        return re.compile(rf"^v?\d+\.\d+\.\d+$")
    if re.fullmatch(r"\d+\.\d+", s):
        return re.compile(rf"^v?\d+\.\d+$")
    if re.fullmatch(r"\d+", s):
        return re.compile(rf"^v?\d+$")
    if re.fullmatch(r"b\d+", current_tag):
        return re.compile(r"^b\d+$")
    return re.compile(re.escape(current_tag) + r"$")


def _version_key(tag: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", tag))


def _resolve_tag(repo: str, current_tag: str) -> tuple[str, str]:
    """Highest stable tag of the same shape as current_tag, and its peeled sha.
    Returns ('', '') when none is newer."""
    p = _run(["git", "ls-remote", "--tags", "--refs", repo])
    if p.returncode != 0:
        return "", ""
    shape = _tag_shape(current_tag)
    candidates = []
    for line in p.stdout.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        sha, ref = parts
        tag = ref.rsplit("/", 1)[-1]
        if not shape.match(tag) or _PRE_RELEASE.search(tag):
            continue
        candidates.append((_version_key(tag), tag, sha))
    if not candidates:
        return "", ""
    _, tag, sha = max(candidates, key=lambda c: c[0])
    return tag, sha


def plan(engine: str | None = None) -> list[dict]:
    """Which engines moved upstream. Sorted by id. Never moves backwards."""
    skills = es.load_skills()
    out = []
    for sid in sorted(skills):
        if engine and sid != engine:
            continue
        s = skills[sid]
        if s.get("servable") is False:
            continue
        repo = s["repo"].rstrip("/")
        if "://" in repo or repo.startswith("git@"):
            repo += ".git"
        old_sha, old_ref = s["pinned"], s["ref"]
        if s.get("ref_kind") == "tag":
            new_ref, new_sha = _resolve_tag(repo, old_ref)
            if not new_ref:
                out.append({"id": sid, "repo": repo, "ref_kind": "tag",
                            "old_ref": old_ref, "old_sha": old_sha,
                            "new_ref": "", "new_sha": "", "status": "lookup failed"})
                continue
        else:  # branch
            new_sha = _ls_remote(repo, f"refs/heads/{old_ref}")
            new_ref = old_ref
            if not new_sha:
                out.append({"id": sid, "repo": repo, "ref_kind": "branch",
                            "old_ref": old_ref, "old_sha": old_sha,
                            "new_ref": new_ref, "new_sha": "", "status": "lookup failed"})
                continue
        if new_sha == old_sha:
            continue  # already at latest
        if s.get("ref_kind") == "tag" and _version_key(new_ref) <= _version_key(old_ref):
            continue  # never backwards
        out.append({"id": sid, "repo": repo, "ref_kind": s.get("ref_kind"),
                    "old_ref": old_ref, "old_sha": old_sha,
                    "new_ref": new_ref, "new_sha": new_sha, "status": "bump"})
    return out


def _edit_frontmatter(path: Path, changes: dict) -> str:
    """Replace the given frontmatter keys in place. Returns the new file text.
    Only the named keys change; every other byte is preserved."""
    text = path.read_text()
    for key, value in changes.items():
        if value is None:
            continue
        pat = re.compile(rf"^{re.escape(key)}:.*$", re.MULTILINE)
        if not pat.search(text):
            raise SystemExit(f"[engine-bump] {path.name}: no frontmatter key {key!r}")
        text = pat.sub(f"{key}: {value}", text, count=1)
    return text


def pin(skill_id: str, new_ref: str, new_sha: str, dry: bool = False) -> str:
    """Surgical frontmatter edit of pinned/ref/version/verified. Returns the new text."""
    path = es.SKILLS_DIR / skill_id / "SKILL.md"
    s = es.load_skill(path)
    changes = {"pinned": new_sha, "verified": f'"{datetime.now(timezone.utc).date().isoformat()}"'}
    if s.get("ref_kind") == "tag":
        changes["ref"] = new_ref
        changes["version"] = new_ref
    new_text = _edit_frontmatter(path, changes)
    if not dry:
        path.write_text(new_text)
    return new_text


def _frontmatter_span(text: str) -> tuple[int, int]:
    """Byte span of the front matter body (between the two `---` lines)."""
    if not text.startswith("---\n"):
        raise SystemExit("[engine-bump] SKILL.md has no front matter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise SystemExit("[engine-bump] unterminated front matter")
    return 4, end


def _block_span(text: str, key: str) -> tuple[int, int] | None:
    """Span of a top-level front-matter block, from its key line through the
    last indented line that belongs to it. None when the key is absent."""
    start, end = _frontmatter_span(text)
    fm = text[start:end]
    m = re.search(rf"^{re.escape(key)}:.*$", fm, re.MULTILINE)
    if not m:
        return None
    abs_start = start + m.start()
    rest = fm[m.end():]
    nxt = re.search(r"\n(?![ \n])", rest)
    abs_end = start + m.end() + (nxt.start() if nxt else len(rest))
    return abs_start, abs_end


def _replace_in_block(text: str, key: str, pat: re.Pattern, repl: str, count: int = 0) -> tuple[str, int]:
    """Substitute `pat` only inside the named front-matter block."""
    span = _block_span(text, key)
    if span is None:
        return text, 0
    a, b = span
    new, n = pat.subn(repl, text[a:b], count=count)
    return text[:a] + new + text[b:], n


def _download(url: str, dest: Path) -> None:
    """Stream `url` to `dest`. stdlib, so it runs in the test image (no curl)."""
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "llgenie-engine-bump"})
    with urllib.request.urlopen(req, timeout=180) as r, dest.open("wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)


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


# (backend) -> (os token, arch token) in `<name>-<version>-<os>-<arch>.tar.gz`.
_ARCHIVE_TARGET = {"cuda": ("linux", "x86_64"), "rocm": ("linux", "x86_64"),
                   "vulkan": ("linux", "x86_64"), "cpu": ("linux", "x86_64"),
                   "metal": ("macos", "arm64")}
_ARCHIVE = re.compile(r"^(?P<name>.+)-(?P<ver>[0-9][0-9.]*)-(?P<os>linux|macos)-(?P<arch>[A-Za-z0-9_]+)\.tar\.gz$")


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
        steps_for[backend] = [
            "mkdir -p {prefix}/{version}",
            "curl -fsSL -o {prefix}/" + asset_tmpl + " {repo}/releases/download/v{version}/" + asset_tmpl,
            "curl -fsSL -o {prefix}/" + asset_tmpl + ".sha256 {repo}/releases/download/v{version}/" + asset_tmpl + ".sha256",
            "cd {prefix} && " + check + " " + asset_tmpl + ".sha256",
            "tar -xzf {prefix}/" + asset_tmpl + " -C {prefix}/{version} --strip-components=1",
            link,
        ]
    return steps_for


def _dump_install(steps_for: dict) -> str:
    lines = ["install:"]
    for backend, steps in steps_for.items():
        lines.append(f"  {backend}:")
        for step in steps:
            lines.append('    - "' + step.replace('"', '\\"') + '"')
    return "\n".join(lines)


def _set_scalar(text: str, key: str, value: str) -> str:
    """Replace a top-level front-matter key (a scalar or a whole block) with one line."""
    line = f"{key}: {value}"
    span = _block_span(text, key)
    if span is not None:
        a, b = span
        return text[:a] + line + text[b:]
    fm_end = text.find("\n---\n")
    if fm_end < 0:
        return text
    return text[:fm_end] + "\n" + line + text[fm_end:]


def _apply_release_archive(text: str, steps_for: dict) -> str:
    span = _block_span(text, "install")
    if span is None:
        return text
    a, b = span
    block = _dump_install(steps_for)
    # keep the newline that separated install from the next key
    text = text[:a] + block + text[b:]
    # The unpacked executable is linked to {id}. detect used to ask pip or
    # `uv tool` for a package the archive does not install.
    text = _set_scalar(text, "binary", '"{prefix}/{version}/bin/{id}"')
    text = _set_scalar(text, "detect", '"{binary} --version"')
    return text


def _apply_findings(skill_id: str, findings: dict) -> list[str]:
    """Write the derived `auto` findings into the skill's frontmatter.

    Returns the list of frontmatter keys changed. Only the derived keys change;
    every other byte is preserved. A hard-fail finding is not applied (nothing is
    guessed) — it is left for a human via the PR body.
    """
    auto = findings.get("auto") or {}
    if not auto:
        return []
    path = es.SKILLS_DIR / skill_id / "SKILL.md"
    text = path.read_text()
    changed: list[str] = []

    # E2: renamed flags — replace -DOLD with -DNEW (keep the value) in cmake_flags/hw_flags
    renames = auto.get("renamed_flags") or {}
    if renames:
        for old, new in renames.items():
            pat = re.compile(rf"-D{re.escape(old)}(?==|\s|$)")
            if pat.search(text):
                text = pat.sub(f"-D{new}", text)
                changed.append(f"rename {old}->{new}")

    # E4: mirrored recipe flags — add -DFLAG=VALUE to cmake_flags.<backend> (or common)
    mirrored = auto.get("mirrored_flags") or {}
    if mirrored:
        for flag, val in mirrored.items():
            if f"-D{flag}=" in text:
                continue  # already present
            # add to the first cmake_flags backend line (common if present, else cuda)
            m = re.search(r"^cmake_flags:\s*$", text, re.MULTILINE)
            if m:
                # find the first indented backend line under cmake_flags
                bm = re.search(r"^  (\w+): \"([^\"]*)\"$", text[m.end():], re.MULTILINE)
                if bm:
                    start = m.end() + bm.start()
                    line = text[start:start + len(bm.group(0))]
                    newline = line[:-1] + f" -D{flag}={val}\""
                    text = text[:start] + newline + text[start + len(line):]
                    changed.append(f"mirror {flag}={val}")
            else:
                # no cmake_flags block yet (empty arg list): create one before the
                # closing `---` of the front matter, with a `common` line
                fm_end = text.find("\n---\n")
                if fm_end > 0:
                    block = f"cmake_flags:\n  common: \"-D{flag}={val}\"\n"
                    text = text[:fm_end + 1] + block + text[fm_end + 1:]
                    changed.append(f"mirror {flag}={val}")

    # E5: toolchain — update toolchain.<backend>, and only that block. A skill
    # with no toolchain: key (llama.cpp keeps its toolchain under prereqs:) is
    # left alone: writing the version onto prereqs.cuda turned `[nvcc]` into
    # `12.8.1` (PR #149).
    toolchain = auto.get("toolchain") or {}
    if toolchain and _block_span(text, "toolchain"):
        for backend, ver in toolchain.items():
            pat = re.compile(rf"^  {re.escape(backend)}:.*$", re.MULTILINE)
            text, n = _replace_in_block(text, "toolchain", pat, f"  {backend}: {ver}", count=1)
            if n:
                changed.append(f"toolchain.{backend}={ver}")

    # E6: gpu targets var — rename AMDGPU_TARGETS inside hw_flags only. A whole
    # file replace also rewrote derive.gpu_targets_var.candidates (PR #149).
    gtv = auto.get("gpu_targets_var")
    if gtv and "AMDGPU_TARGETS" in text:
        text, n = _replace_in_block(text, "hw_flags", re.compile("AMDGPU_TARGETS"), gtv)
        # the prose that names the old variable ("AMDGPU_TARGETS is a legacy alias")
        body_at = text.find("\n---\n", 4)
        if body_at > 0:
            head, body = text[:body_at], text[body_at:]
            body2 = body.replace("AMDGPU_TARGETS", gtv)
            n += body2 != body
            text = head + body2
        if n:
            changed.append(f"gpu_targets_var={gtv}")

    # E10: a tag whose release ships native archives is no longer a pip install
    assets = auto.get("release_assets")
    if assets:
        steps_for = release_archive_install(es.load_skill(path), assets)
        if steps_for:
            text = _apply_release_archive(text, steps_for)
            changed.append("install=release-archive")

    # E11: apt packages the new pin's Dockerfile added
    apt_add = auto.get("apt_add") or []
    if apt_add:
        text, added = _append_apt(text, apt_add)
        if added:
            changed.append("apt=" + ",".join(added))

    # E7: torch backend
    tb = auto.get("torch_backend")
    if tb:
        pat = re.compile(r"^torch_backend:.*$", re.MULTILINE)
        if pat.search(text):
            text = pat.sub(f"torch_backend: {tb}", text, count=1)
            changed.append(f"torch_backend={tb}")

    if changed:
        path.write_text(text)
    return changed


def _append_apt(text: str, packages: list[str]) -> tuple[str, list[str]]:
    """Append packages to every front-matter `apt: [...]` line. The body is unchanged."""
    fm_end = text.find("\n---\n", 4)
    if fm_end < 0:
        return text, []
    head, body = text[:fm_end], text[fm_end:]
    added: list[str] = []

    def repl(match: re.Match) -> str:
        indent, inner = match.group(1), match.group(2)
        current = [part.strip() for part in inner.split(",") if part.strip()]
        for pkg in packages:
            if pkg not in current:
                current.append(pkg)
                if pkg not in added:
                    added.append(pkg)
        return f"{indent}apt: [{', '.join(current)}]"

    head = re.sub(r"^(\s*)apt:\s*\[([^\]]*)\]\s*$", repl, head, flags=re.MULTILINE)
    return head + body, added


def _rewrite_pin_asserts(skill_id: str, old_sha: str, new_sha: str,
                         old_ref: str, new_ref: str) -> list[str]:
    """Rewrite hardcoded pin/version/image-tag asserts that name this engine's old pin.

    The unit suite asserts the skill's current pin in three shapes (issue #144):
    the full sha, its 8-char prefix (image tags), and the tag/version string
    (`v0.35.1`, `0.35.1-rocm`). A bump that moves the pin without moving those
    asserts makes `make test-unit` red on the bump PR. Only `tests/` and
    `README.md` are rewritten; historical OpenSpec/agent-wiki records are not.
    A ref that did not move (branch skills, old_ref == new_ref) is still
    substituted: the unit suite hardcodes the tag string next to the sha, and a
    sha-only move must rewrite both. The substitution is a no-op when the two
    sides are equal.
    """
    pairs = [(old_sha, new_sha), (old_sha[:8], new_sha[:8])]
    # A tag pin's version literal is hardcoded as `v0.40.3` and `0.40.3-rocm`
    # even when only the sha moved (the tag string is the same before and after).
    # Substituting it only when old_ref != new_ref left those asserts red.
    if old_ref and new_ref:
        pairs.append((old_ref, new_ref))
        if old_ref.startswith("v") and new_ref.startswith("v"):
            pairs.append((old_ref[1:], new_ref[1:]))
    changed: list[str] = []
    roots = [REPO_ROOT / "tests", REPO_ROOT / "README.md"]
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(p for p in root.rglob("*") if p.is_file() and p.suffix in {".py", ".md"})
    for path in files:
        text = path.read_text()
        new = text
        for old, repl in pairs:
            if old and old in new:
                new = new.replace(old, repl)
        if new != text:
            path.write_text(new)
            changed.append(str(path.relative_to(REPO_ROOT)))
    return changed


def _sync_generated(skill_id: str) -> list[str]:
    """Re-run the generators whose output embeds this engine's pin.

    `make check-strata-models` (part of `make ci-unit`) fails when
    `data/strata_models.json` was built from a pin other than the skill's, so a
    Strata bump must regenerate it. Other engines have no such artifact.
    """
    generators = {
        "strata": ["make", "sync-strata-models"],
    }
    cmd = generators.get(skill_id)
    if not cmd:
        return []
    p = _run(cmd, cwd=REPO_ROOT, timeout=300)
    if p.returncode != 0:
        raise SystemExit(f"[engine-bump] {' '.join(cmd)} failed:\n{p.stdout}\n{p.stderr}")
    return [cmd[-1]]


def _regen_guard(skill_id: str) -> list[str]:
    """Run make generate-engine-params and fail if the working tree changed
    outside the bumped engine's params/dockerfiles. Reads git status, not make's
    stdout: GNU make prints `make[1]: Entering directory ...` there (run
    38109392303), which is not a changed path."""
    p = _run(["make", "generate-engine-params", f"ENGINE={skill_id}"], cwd=REPO_ROOT, timeout=300)
    if p.returncode != 0:
        raise SystemExit(f"[engine-bump] generate-engine-params failed:\n{p.stdout}\n{p.stderr}")
    status = _run(["git", "status", "--porcelain"], cwd=REPO_ROOT, timeout=60)
    if status.returncode != 0:
        raise SystemExit(f"[engine-bump] git status failed:\n{status.stderr}")
    changed = []
    for ln in status.stdout.splitlines():
        path = ln[3:].strip()
        if " -> " in path:  # rename
            path = path.split(" -> ", 1)[1].strip()
        if path:
            changed.append(path)
    for c in changed:
        skill = f"skills/engines/{skill_id}/SKILL.md"
        own = (c == skill
               or c == f"containers/engines/params/{skill_id}.json"
               or c.startswith(f"containers/engines/dockerfiles/{skill_id}/")
               or c == "containers/engines/binaries.json"  # regenerate-engine-params writes this aggregate manifest even for --only
               or c.startswith("tests/")
               or c == "README.md"
               or c == "data/strata_models.json")
        if not own:
            raise SystemExit(f"[engine-bump] regen changed a file outside {skill_id}: {c}")
    return changed


def derive(skill_id: str, sha: str = "", old_sha: str = "", ref: str = "") -> dict:
    """Run the skill's extractors against the upstream tree at `sha`.

    `ref` is the destination tag. E10 reads that release, not the tag the skill
    file still names (derive runs before pin writes it).
    """
    skill = es.get_skill(skill_id)
    sha = sha or skill["pinned"]
    try:
        return epd.derive(skill, sha, old_sha=old_sha or None, ref=ref or None)
    except epd.HardFail as e:
        raise SystemExit(f"[engine-bump] {skill_id}: {e}")


def bump(skill_id: str, dry: bool = False) -> list[dict]:
    """Pin the engine to its latest upstream commit, derive + apply params, regen.

    A derive hard-fail (removed option/flag we cannot safely rewrite) does NOT
    abort the bump: the pin still moves and a PR is still created, with the
    hard-fail recorded in the row so the PR body flags it and CI goes red on the
    build. Nothing is silently guessed.
    """
    row = next((r for r in plan(skill_id) if r["id"] == skill_id), None)
    if row is None:
        print(f"[engine-bump] {skill_id}: already at latest, nothing to do")
        return []
    if row.get("status") == "lookup failed":
        raise SystemExit(f"[engine-bump] {skill_id}: upstream lookup failed")
    if dry:
        print(json.dumps(row, indent=2))
        return [row]
    # derive first; a hard fail is recorded, not fatal — the PR still opens.
    # The skill file still names the old tag here. E10 must read the destination tag.
    ref = row["new_ref"] if row.get("ref_kind") == "tag" else ""
    try:
        findings = derive(skill_id, row["new_sha"], row["old_sha"], ref=ref)
        row["hard_fail"] = findings.get("hard_fail")
    except SystemExit as e:
        findings = {"hard_fail": str(e)}
        row["hard_fail"] = str(e)
    deps = (findings.get("report") or {}).get("dependencies") or {}
    py_added = ",".join(deps.get("python_added") or [])
    apt_added = ",".join(deps.get("apt_added") or [])
    py_removed = ",".join(deps.get("python_removed") or [])
    apt_removed = ",".join(deps.get("apt_removed") or [])
    if py_added or apt_added or py_removed or apt_removed:
        print(
            "[engine-bump] DEPS "
            f"python_added={py_added} apt_added={apt_added} "
            f"python_removed={py_removed} apt_removed={apt_removed}"
        )
    pin(skill_id, row["new_ref"], row["new_sha"])
    applied = _apply_findings(skill_id, findings)
    rewritten = _rewrite_pin_asserts(skill_id, row["old_sha"], row["new_sha"],
                                     row["old_ref"], row["new_ref"])
    synced = _sync_generated(skill_id)
    changed = _regen_guard(skill_id)
    print(f"[engine-bump] {skill_id}: {row['old_sha'][:8]} -> {row['new_sha'][:8]} "
          f"({row['new_ref']}); applied: {', '.join(applied) or 'none'}; "
          f"asserts: {', '.join(rewritten) or 'none'}; "
          f"synced: {', '.join(synced) or 'none'}; "
          f"regen: {', '.join(changed)}")
    print(f"[engine-bump] {skill_id}: findings {json.dumps(findings, sort_keys=True)}")
    return [row]


def bump_daily(dry: bool = False) -> int:
    """Plan -> bump each moved engine. --dry prints the plan only, no writes."""
    rows = plan()
    if not rows:
        print("[engine-bump] no engines moved upstream")
        return 0
    print(f"[engine-bump] plan: {len(rows)} engine(s) moved")
    for r in rows:
        print(f"  {r['id']:24} {r['old_sha'][:8]} -> {r['new_sha'][:8]} ({r['new_ref']}) "
              f"[{r.get('status')}]")
    if dry:
        return 0
    failed = 0
    for r in rows:
        if r.get("status") == "lookup failed":
            print(f"[engine-bump] {r['id']}: lookup failed, skipped")
            failed += 1
            continue
        try:
            bump(r["id"])
        except SystemExit as e:
            print(f"[engine-bump] {r['id']}: {e}")
            failed += 1
    return 1 if failed else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="llgenie daily engine pin bump")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--engine", default=None)
    d = sub.add_parser("derive")
    d.add_argument("engine")
    d.add_argument("--sha", default="")
    d.add_argument("--old-sha", default="")
    b = sub.add_parser("bump")
    b.add_argument("engine")
    b.add_argument("--dry", action="store_true")
    pn = sub.add_parser("pin")
    pn.add_argument("engine")
    pn.add_argument("new_ref")
    pn.add_argument("new_sha")
    pn.add_argument("--dry", action="store_true")
    d = sub.add_parser("bump-daily")
    d.add_argument("--dry", action="store_true")
    a = ap.parse_args(argv)

    if a.cmd == "plan":
        print(json.dumps(plan(a.engine), indent=2))
        return 0
    if a.cmd == "derive":
        print(json.dumps(derive(a.engine, a.sha, a.old_sha), indent=2, sort_keys=True))
        return 0
    if a.cmd == "pin":
        print(pin(a.engine, a.new_ref, a.new_sha, a.dry))
        return 0
    if a.cmd == "bump":
        bump(a.engine, a.dry)
        return 0
    if a.cmd == "bump-daily":
        return bump_daily(a.dry)
    return 1


if __name__ == "__main__":
    sys.exit(main())
