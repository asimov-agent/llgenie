"""Dependencies a new engine pin adds, read from that pin's own files.

`git show <sha>:<path>` supplies requirements files, pyproject.toml, and
Dockerfiles. `dpkg-shlibdeps -O <binary>` names the Debian packages a binary
links. Nothing here guesses a package those commands did not print.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path

_REQ_NAME = re.compile(r"^[A-Za-z0-9_.-]+")
_APT_INSTALL = re.compile(r"apt-get\s+install\s+([^&\n]+)", re.IGNORECASE)
_SHLIB = re.compile(r"shlibs:Depends=(.+)")


def requirement_names(text: str) -> list[str]:
    """Package names in a requirements.txt body. Comments and pip options are ignored."""
    names: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        name = re.split(r"[<>=!~;\[]", line, maxsplit=1)[0].strip()
        if name:
            names.append(name.lower().replace("_", "-"))
    return sorted(set(names))


def pyproject_dependency_names(text: str) -> list[str]:
    """Names in `[project].dependencies`. A file that is not that table is empty."""
    try:
        data = tomllib.loads(text or "")
    except tomllib.TOMLDecodeError:
        return []
    deps = (data.get("project") or {}).get("dependencies") or []
    if not isinstance(deps, list):
        return []
    return requirement_names("\n".join(str(d) for d in deps))


def apt_packages(text: str) -> list[str]:
    """Package names on `apt-get install` lines, flags excluded."""
    names: list[str] = []
    joined = (text or "").replace("\\\n", " ")
    for match in _APT_INSTALL.finditer(joined):
        for tok in match.group(1).split():
            if tok.startswith("-"):
                continue
            if _REQ_NAME.match(tok):
                names.append(tok)
    return sorted(set(names))


def _is_dep_file(path: str) -> bool:
    base = path.rsplit("/", 1)[-1]
    if base == "pyproject.toml" or base == "Dockerfile":
        return True
    if not (base.startswith("requirements") and base.endswith(".txt")):
        return False
    low = base.lower()
    return "dev" not in low and "test" not in low


def _show(repo: Path, sha: str, path: str) -> str | None:
    proc = subprocess.run(
        ["git", "-C", str(repo), "show", f"{sha}:{path}"],
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def _names_at(repo: Path, sha: str, paths: list[str]) -> tuple[list[str], list[str]]:
    python: set[str] = set()
    apt: set[str] = set()
    for path in paths:
        text = _show(repo, sha, path)
        if text is None:
            continue
        base = path.rsplit("/", 1)[-1]
        if base == "Dockerfile":
            apt.update(apt_packages(text))
        elif base == "pyproject.toml":
            python.update(pyproject_dependency_names(text))
        else:
            python.update(requirement_names(text))
    return sorted(python), sorted(apt)


def dependency_paths(skill: dict, present: set[str]) -> list[str]:
    """Watched dependency files that exist at this sha, else the repo-root trio."""
    watched = [p for p in (skill.get("upstream_watch") or []) if _is_dep_file(p) and p in present]
    if watched:
        return watched
    return [p for p in ("requirements.txt", "pyproject.toml", "Dockerfile") if p in present]


def _listing(repo: Path, sha: str) -> set[str]:
    proc = subprocess.run(
        ["git", "-C", str(repo), "ls-tree", "-r", "--name-only", sha],
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        return set()
    return {ln for ln in proc.stdout.splitlines() if ln}


def dependency_delta(repo: Path, old_sha: str, new_sha: str, skill: dict) -> dict:
    """Packages present at `new_sha` and absent at `old_sha`."""
    present = _listing(repo, new_sha) | _listing(repo, old_sha)
    paths = dependency_paths(skill, present)
    old_py, old_apt = _names_at(repo, old_sha, paths)
    new_py, new_apt = _names_at(repo, new_sha, paths)
    return {
        "paths": paths,
        "python_added": [n for n in new_py if n not in old_py],
        "python_removed": [n for n in old_py if n not in new_py],
        "apt_added": [n for n in new_apt if n not in old_apt],
        "apt_removed": [n for n in old_apt if n not in new_apt],
        "python_covered": requirements_covered(skill),
    }


def requirements_covered(skill: dict) -> bool:
    """True when the skill install already pip-installs a requirements file or pyproject."""
    install = skill.get("install") or {}
    steps: list[str] = []
    if isinstance(install, dict):
        for value in install.values():
            steps.extend(value if isinstance(value, list) else [value])
    elif isinstance(install, list):
        steps = list(install)
    blob = "\n".join(str(step) for step in steps)
    if re.search(r"\bpip3?\b[^\n]*-r\s+\S*requirements", blob):
        return True
    if re.search(r"\buv\s+pip\b[^\n]*-r\s+\S*requirements", blob):
        return True
    return "pyproject.toml" in blob and "pip install" in blob


def declared_apt(skill: dict) -> list[str]:
    """Package names already listed on a container `apt:` key."""
    names: list[str] = []
    container = skill.get("container") or {}
    if not isinstance(container, dict):
        return []
    for spec in container.values():
        if isinstance(spec, dict):
            for pkg in spec.get("apt") or []:
                if pkg not in names:
                    names.append(str(pkg))
    return names


def shlib_packages(binary: Path) -> list[str]:
    """Debian packages `dpkg-shlibdeps -O` names for `binary`.

    The tool reads `debian/control` from the working directory before it
    prints `shlibs:Depends=`. A throwaway control file lets it name the
    packages; the names still come only from that Depends line.
    """
    if shutil.which("dpkg-shlibdeps") is None:
        raise RuntimeError("dpkg-shlibdeps is not installed")
    binary = Path(binary).resolve()
    with tempfile.TemporaryDirectory(prefix="llgenie-shlib-") as work:
        control = Path(work) / "debian"
        control.mkdir()
        (control / "control").write_text(
            "Source: llgenie-shlib\n"
            "\n"
            "Package: llgenie-shlib\n"
            "Architecture: any\n"
            "Description: runtime library probe\n"
            " probe\n"
        )
        proc = subprocess.run(
            ["dpkg-shlibdeps", "-O", str(binary)],
            cwd=work, capture_output=True, text=True, timeout=60,
        )
    text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    match = _SHLIB.search(text)
    if not match:
        raise RuntimeError(text.strip() or "dpkg-shlibdeps failed")
    names = []
    for part in match.group(1).split(","):
        name = part.strip().split(" ", 1)[0]
        if name and name not in names:
            names.append(name)
    return names
