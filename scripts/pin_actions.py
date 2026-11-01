#!/usr/bin/env python3
"""Every GitHub Action is pinned to a full commit SHA (issue #719).

A tag is a moving pointer inside someone else's repository: `actions/checkout@v4` runs whatever
`v4` points at when the job starts, so a force-pushed or compromised release changes what this
repository executes without a commit here. Measured on `main` at `2cbfb11`, 13 distinct refs
across 19 workflows floated on a tag:

    33 uses: actions/checkout@v4
     6 uses: docker/setup-buildx-action@v3
     5 uses: actions/upload-artifact@v4
     5 uses: actions/setup-python@v5
     3 uses: astral-sh/setup-uv@v6
     2 uses: docker/setup-qemu-action@v3
     1 uses: actions/setup-node@v4

A local reference (`./.github/actions/docker`, `./.github/workflows/pipeline.yml`) is this
repository's own content at the commit being run: it cannot move independently, so it is exempt.

The pin keeps the tag as a trailing comment — `uses: actions/checkout@<sha> # v4` — because a
40-hex line is unreadable in review and `update` needs to know which tag to re-resolve.

Commands:
    pin_actions.py check     exit non-zero on any non-local ref that is not a 40-hex SHA
    pin_actions.py report    print every ref, its pin state and its tag
    pin_actions.py update    re-resolve every pinned ref's tag to its current commit and rewrite

`update` needs the network and `gh` (or GITHUB_TOKEN); `check` and `report` are stdlib only, so the
gate runs on the host exactly as `make ci-unit` runs it, on Linux and macOS alike.

Usage:
    python3 scripts/pin_actions.py check
    python3 scripts/pin_actions.py report
    python3 scripts/pin_actions.py update
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SEARCH_DIRS = (".github/workflows", ".github/actions")
#: `uses: [quoted] <ref> [whitespace, then a # tag comment]`
USES_RE = re.compile(
    r"^(?P<indent>\s*(?:-\s+)?uses:\s*)(?P<quote>[\"']?)"
    r"(?P<ref>[^\"'\s#]+)(?P=quote)(?P<tail>[^\n#]*)(?P<comment>#\s*(?P<tag>\S+))?\s*$",
    re.M,
)
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def yaml_files() -> list[Path]:
    """Every workflow and composite action file in the repository."""
    out: list[Path] = []
    for rel in SEARCH_DIRS:
        base = REPO / rel
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix in (".yml", ".yaml") and path.is_file():
                out.append(path)
    return out


def is_local(ref: str) -> bool:
    return ref.startswith("./") or ref.startswith("docker://")


def split_ref(ref: str) -> tuple[str, str]:
    """`owner/repo[/path]@tag` -> (`owner/repo[/path]`, `tag`); a bare ref -> (ref, "")."""
    if "@" not in ref:
        return ref, ""
    head, _, tag = ref.rpartition("@")
    return head, tag


def findings() -> list[dict]:
    """Every `uses:` in the tree with its pin state."""
    out: list[dict] = []
    for path in yaml_files():
        text = path.read_text(encoding="utf-8")
        for m in USES_RE.finditer(text):
            ref = m.group("ref")
            if is_local(ref):
                continue
            head, tag = split_ref(ref)
            # `uses: job` and other non-`owner/repo` strings are not actions; an action ref always
            # carries a `/`. Reporting them would make the gate refuse text it cannot judge.
            action = "/" in head
            out.append({
                "file": str(path.relative_to(REPO)),
                "line": text[: m.start()].count("\n") + 1,
                "ref": ref,
                "action": head,
                "tag": tag,
                "pinned": bool(SHA_RE.match(tag)),
                "comment_tag": m.group("tag") or "",
                "span": (m.start("ref"), m.end("ref")),
                "action_like": action,
            })
    return out


def check() -> int:
    bad = [f for f in findings() if f["action_like"] and not f["pinned"]]
    total = len([f for f in findings() if f["action_like"]])
    if bad:
        print(f"[pin-actions] {len(bad)} of {total} action refs are not pinned to a full commit SHA:")
        for f in bad:
            print(f"  {f['file']}:{f['line']}  {f['ref']}")
        print("[pin-actions] run `make update-actions` and commit the result (docs/SECURITY.md)")
        return 1
    print(f"[pin-actions] OK: {total} third-party action refs, all pinned to a full commit SHA")
    return 0


def report() -> int:
    for f in findings():
        state = "pinned" if f["pinned"] else "FLOATING"
        tag = f["tag"] or f["comment_tag"] or "-"
        print(f"{state:8} {f['file']}:{f['line']:<5} {f['action']} @ {tag}")
    return 0


def _gh_api(path: str) -> dict:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    gh = shutil.which("gh")
    if gh and not token:
        cmd = [gh, "api", path]
    else:
        req = urllib.request.Request(
            "https://api.github.com" + path,
            headers={"Accept": "application/vnd.github+json", **({"Authorization": f"Bearer {token}"} if token else {})},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 — fixed host
                return json.load(resp)
        except urllib.error.HTTPError as exc:  # loud, naming the ref
            raise SystemExit(f"[pin-actions] cannot resolve {path}: HTTP {exc.code}") from exc
    res = subprocess.run(cmd, capture_output=True, text=True)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
    if res.returncode != 0:
        raise SystemExit(f"[pin-actions] cannot resolve {path}: {res.stderr.strip()}")
    return json.loads(res.stdout)


_RESOLVED: dict[tuple[str, str], str] = {}


def resolve(action: str, tag: str) -> str:
    """The commit SHA a tag points at (following an annotated tag object to its commit)."""
    parts = action.split("/")
    if len(parts) < 2:
        raise SystemExit(f"[pin-actions] not an action ref: {action}")
    lookup = "/".join(parts[:2])
    if (lookup, tag) in _RESOLVED:  # one API read per (repo, tag), not per occurrence
        return _RESOLVED[(lookup, tag)]
    obj = _gh_api(f"/repos/{lookup}/git/ref/tags/{tag}")
    sha, kind = obj["object"]["sha"], obj["object"]["type"]
    depth = 0
    while kind == "tag" and depth < 5:
        obj = _gh_api(f"/repos/{lookup}/git/tags/{sha}")
        sha, kind = obj["object"]["sha"], obj["object"]["type"]
        depth += 1
    if kind != "commit":
        raise SystemExit(f"[pin-actions] {action}@{tag} does not resolve to a commit ({kind})")
    _RESOLVED[(lookup, tag)] = sha
    return sha


def update() -> int:
    changed = 0
    for path in yaml_files():
        text = path.read_text(encoding="utf-8")
        pieces: list[str] = []
        last = 0
        mutated = False
        for m in USES_RE.finditer(text):
            ref = m.group("ref")
            if is_local(ref):
                continue
            head, tag = split_ref(ref)
            if "/" not in head:
                continue
            if SHA_RE.match(tag):
                continue  # already pinned; the comment tag is what `update` acts on below
            sha = resolve(head, tag)
            pieces.append(text[last:m.start("ref")])
            pieces.append(f"{head}@{sha}")
            tail = m.group("tail").rstrip()
            pieces.append(f"{tail} # {tag}")
            last = m.end("comment") if m.group("comment") else m.end("tail")
            mutated = True
            changed += 1
            print(f"[pin-actions] {path.relative_to(REPO)}: {ref} -> {head}@{sha} # {tag}")
        if mutated:
            pieces.append(text[last:])
            path.write_text("".join(pieces), encoding="utf-8")
    # A re-run over an already pinned tree must be a no-op.
    if not changed:
        print("[pin-actions] nothing to do: every action ref is pinned")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=("check", "report", "update"))
    args = ap.parse_args(argv)
    return {"check": check, "report": report, "update": update}[args.command]()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
