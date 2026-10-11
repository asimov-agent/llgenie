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

    # E5: toolchain — update toolchain.<backend>
    toolchain = auto.get("toolchain") or {}
    if toolchain:
        for backend, ver in toolchain.items():
            pat = re.compile(rf"^  {re.escape(backend)}:.*$", re.MULTILINE)
            if pat.search(text):
                text = pat.sub(f"  {backend}: {ver}", text, count=1)
                changed.append(f"toolchain.{backend}={ver}")

    # E6: gpu targets var — rename AMDGPU_TARGETS -> GPU_TARGETS in hw_flags
    gtv = auto.get("gpu_targets_var")
    if gtv:
        text = text.replace("AMDGPU_TARGETS", gtv)
        changed.append(f"gpu_targets_var={gtv}")

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
        if not (c.startswith("containers/engines/params/") or
                c.startswith("containers/engines/dockerfiles/")):
            raise SystemExit(f"[engine-bump] regen changed a non-engine file: {c}")
        if not (c == f"containers/engines/params/{skill_id}.json" or
                c.startswith(f"containers/engines/dockerfiles/{skill_id}/")):
            raise SystemExit(f"[engine-bump] regen changed another engine's file: {c}")
    return changed


def derive(skill_id: str, sha: str = "", old_sha: str = "") -> dict:
    """Run the skill's extractors against the upstream tree at `sha`."""
    skill = es.get_skill(skill_id)
    sha = sha or skill["pinned"]
    try:
        return epd.derive(skill, sha, old_sha=old_sha or None)
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
    # derive first; a hard fail is recorded, not fatal — the PR still opens
    try:
        findings = derive(skill_id, row["new_sha"], row["old_sha"])
        row["hard_fail"] = None
    except SystemExit as e:
        findings = {"hard_fail": str(e)}
        row["hard_fail"] = str(e)
    pin(skill_id, row["new_ref"], row["new_sha"])
    applied = _apply_findings(skill_id, findings)
    changed = _regen_guard(skill_id)
    print(f"[engine-bump] {skill_id}: {row['old_sha'][:8]} -> {row['new_sha'][:8]} "
          f"({row['new_ref']}); applied: {', '.join(applied) or 'none'}; "
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
