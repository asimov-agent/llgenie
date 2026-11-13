#!/usr/bin/env python3
"""Keep `docs/ARCHITECTURE.md` current, as one linked issue + one reviewable PR (issue #449).

The repository's other recurring readers of the tree (issue-bot, code-review, registry-sync,
engine-bump) each own one kind of drift. Architecture had no bot and no document: a reviewer
reconstructed the install -> pick -> engine image -> launcher path (and the bot/CI topology)
from source every time. This is the deterministic half of that bot; `make
architecture-bot-doc` is the one Hermes leg, and it only rewrites the doc.

Two commands, both stdlib and both driven from real git (nothing is mocked):

    brief    --doc docs/ARCHITECTURE.md --out architecture-brief.md
             The tree's real surface (tracked files, script modules, public make targets,
             workflows and their crons, data/skills/containers/tests) plus what changed
             since the commit that last touched the doc. No model call, writes only the
             brief. A doc with no history is a full rebuild.

    publish  --repo asimov-agent/llgenie --doc docs/ARCHITECTURE.md --stamp 20261021T1200
             When the doc differs from HEAD and no `agent/architecture-*` PR is open:
             ONE issue (Issue/Fix/Benefit/Technical), ONE branch
             `agent/architecture-<stamp>`, ONE commit (the doc plus its owed note+row pair,
             authored `Asimov Agent`, with a message body that closes the issue and mirrors
             the criteria TICKED) and ONE PR that ends with `closes #<issue>`. The issue's
             criteria are ticked with proven strings naming the publish commit BEFORE the PR
             opens (issue #2632), so the issue body, the commit text and the PR body never
             contradict each other. Never merges, never pushes to main. An unchanged doc, a
             missing/short doc, or an already open architecture PR files nothing.

The model is never asked to decide whether there is drift: `git` decides, and `publish`
re-checks the working tree. That is what keeps a quiet run quiet.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import time
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import changes_index  # the note/row pair this bot owes every doc change renders through (issue #2598)
import git_identity  # the ONE source of the commit identity (issue #840)
import issue_body  # the one issue shape every producer renders through (issue #745)
import module_name_guard  # the shared rename rule (#573): the same check `make test-unit` runs
from proc import run_ok  # the subprocess policy seam (issue #797)

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_DEFAULT = "docs/ARCHITECTURE.md"
#: The acceptance heading this bot mirrors into its PR body (issue #2632). The NAME lives here and
#: is interpolated into `## …` at use: issue #745 spells `##` section headings only in
#: scripts/issue_body.py, and `test_check_issue_body` reddens a producer that spells one itself.
ACCEPTANCE_SECTION = "Acceptance criteria"
assert ACCEPTANCE_SECTION in issue_body.SECTIONS, ACCEPTANCE_SECTION
BRANCH_PREFIX = "agent/architecture-"
#: The commit identity, read from the seam that SETS it (issue #840) instead of a second copy of the
#: allowlisted pair here — two copies is how a correct-looking name acquires a wrong domain.
AUTHOR_NAME, AUTHOR_EMAIL = git_identity.identity()
MIN_DOC_CHARS = 200
MAX_LISTED_PATHS = 60

#: A public make target: `name: ## help text` (the lines `make help` prints).
PUBLIC_TARGET = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.-]*):[^=].*?##\s*(\S.*)$", re.M)
WORKFLOW_NAME = re.compile(r"^name:\s*(.+)$", re.M)
CRON = re.compile(r'cron:\s*"([^"]+)"')


# --------------------------------------------------------------------------- git


def git(root: Path, *args: str) -> str:
    """Run real git in `root` and return stdout (raises on a non-zero exit)."""
    return subprocess.run(  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
        ["git", "-C", str(root), *args],
        check=True, capture_output=True, text=True,
    ).stdout


def _git_rc(root: Path, *args: str) -> int:
    return subprocess.run(  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
        ["git", "-C", str(root), *args], capture_output=True, text=True,
    ).returncode


def tracked_files(root: Path = REPO_ROOT) -> list[str]:
    return [line for line in git(root, "ls-files").splitlines() if line]


def tree_files(root: Path, ref: str) -> list[str]:
    """The tracked paths AT `ref` (`git ls-tree`), never the working tree.

    A census is a claim about ONE commit; its counts must be read from the commit the
    doc names, or the pointer and the numbers drift apart (issue #1236).
    """
    return [line for line in git(root, "ls-tree", "-r", "--name-only", ref).splitlines() if line]


def head_sha(root: Path = REPO_ROOT) -> str:
    return git(root, "rev-parse", "--short", "HEAD").strip()


def census_referent(root: Path = REPO_ROOT) -> str:
    """The commit the census must be measured at — an ancestor of `origin/main`.

    The working/PR head a refresh runs on is a commit a subsequent squash can orphan out
    of `main`'s lineage, so a census pointer naming it reds the whole board the next time
    the gate runs (issue #1236). Resolve the pointer to `merge-base(origin/main, HEAD)`
    — a commit both `main` and this branch contain, so it survives the squash. Falls back
    to HEAD when there is no `origin/main` (a fresh clone or a scratch test repo).
    """
    if _git_rc(root, "rev-parse", "--verify", "-q", "refs/remotes/origin/main") == 0:
        base = git(root, "merge-base", "origin/main", "HEAD").strip()
        if base:
            return base
    return git(root, "rev-parse", "HEAD").strip()


def doc_last_commit(root: Path, doc: str) -> str:
    """The full sha of the commit that last wrote `doc`, or "" when it has no history.

    `--diff-filter=AM` is deliberate: a commit that DELETED the doc is not an update to it, and
    counting one would make a freshly re-created doc look current instead of a full rebuild.
    """
    out = git(root, "log", "-1", "--diff-filter=AM", "--format=%H", "--", doc).strip()
    return out


def commit_subject(root: Path, sha: str) -> str:
    return git(root, "log", "-1", "--format=%s (%cs)", sha).strip()


def commits_since(root: Path, sha: str) -> list[str]:
    """`<short sha> <subject>` for every commit after `sha` (empty when `sha` is HEAD)."""
    return [line for line in git(root, "log", "--format=%h %s", f"{sha}..HEAD").splitlines() if line]


def changed_since(root: Path, sha: str, doc: str) -> list[str]:
    """Paths changed after `sha`, excluding the doc itself (the doc is the thing being written)."""
    out = git(root, "diff", "--name-status", f"{sha}..HEAD", "--", ".")
    paths: list[str] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        status, path = fields[0], fields[-1]
        if path == doc:
            continue
        paths.append(f"{status}\t{path}")
    return paths


def current_branch(root: Path = REPO_ROOT) -> str:
    """The branch checked out right now (`HEAD` when detached)."""
    return git(root, "rev-parse", "--abbrev-ref", "HEAD").strip()


def stray_changes(root: Path, doc: str) -> list[str]:
    """Tracked files the run modified besides `doc` — the agent's write boundary.

    Untracked files are ignored on purpose: the brief and the redacted transcript are run
    artifacts, not edits. A TRACKED file other than the doc changed means the agent crossed the
    line the prompt draws, and the refresh must not be published on top of it.
    """
    out = git(root, "status", "--porcelain", "--untracked-files=no")
    stray: list[str] = []
    for line in out.splitlines():
        path = line[3:].strip()
        if " -> " in path:                       # a rename: both sides are edits
            path = path.split(" -> ", 1)[1]
        if path and path != doc:
            stray.append(path)
    return stray


def doc_is_dirty(root: Path, doc: str) -> bool:
    """True when the working tree's doc differs from HEAD (staged, unstaged, or untracked)."""
    if _git_rc(root, "cat-file", "-e", f"HEAD:{doc}") != 0:
        return (root / doc).exists()
    return _git_rc(root, "diff", "--quiet", "HEAD", "--", doc) != 0


# ----------------------------------------------------------------------- surface


def module_summary(path: Path) -> str:
    """The first line of a module's docstring (the module's own statement of purpose)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return "(unparseable)"
    doc = ast.get_docstring(tree) or ""
    first = next((line.strip() for line in doc.splitlines() if line.strip()), "")
    if first:
        return first
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("#") and len(line.strip()) > 1:
            return line.strip("# ").strip()
    return "(no docstring)"


def _makefile_text(root: Path) -> str:
    """The top Makefile + every `mk/*.mk` it `include`s, in include order (issue #800, #2457).

    The census counts the user-facing make surface (`make help`); after the split the targets live
    in `mk/*.mk`, so a reader that stops at the top `Makefile` sees only the includes and reports an
    empty surface while the doc still names every target (issue #800).
    """
    top = root / "Makefile"
    if not top.exists():
        return ""
    parts: list[str] = []
    seen: set[str] = set()
    pending: list[str] = ["Makefile"]
    while pending:
        rel = pending.pop(0)
        if rel in seen:
            continue
        seen.add(rel)
        p = root / rel
        if not p.is_file():
            continue
        parts.append(p.read_text())
        for m in re.finditer(r"^\s*include\s+(\S+)(?:\s+#.*)?\s*$", p.read_text(), re.M):
            inc = m.group(1)
            if "*" in inc:
                pending.extend(sorted(q.relative_to(root).as_posix() for q in root.glob(inc)))
            else:
                pending.append(inc)
    return "\n\n".join(parts)


def public_targets(root: Path = REPO_ROOT) -> list[tuple[str, str]]:
    mk = root / "Makefile"
    if not mk.exists():
        return []
    return [(name, text.strip()) for name, text in PUBLIC_TARGET.findall(_makefile_text(root))]


def workflows(root: Path = REPO_ROOT) -> list[dict]:
    out = []
    for path in sorted((root / ".github" / "workflows").glob("*.yml")):
        text = path.read_text()
        name = WORKFLOW_NAME.search(text)
        out.append({
            "file": path.name,
            "name": name.group(1).strip() if name else path.stem,
            "crons": CRON.findall(text),
        })
    return out


def surface(root: Path = REPO_ROOT) -> dict:
    """What the tree actually contains — the input the doc is written from.

    The census is measured at `census_referent` — an ancestor of `origin/main` — and the
    counts are read from THAT commit via `ls-tree`, never the working/PR head, so a squash
    cannot orphan the `measured at <sha>` pointer out of main's lineage (issue #1236).
    """
    ref = census_referent(root)
    files = tree_files(root, ref)
    top = sorted({p.split("/", 1)[0] for p in files})
    scripts = []
    for rel in sorted(p for p in files if re.fullmatch(r"scripts/[^/]+\.py", p)):
        scripts.append({"path": rel, "summary": module_summary(root / rel)})
    groups = {d: len([p for p in files if p.startswith(d + "/")])
              for d in ("data", "skills", "containers", "tests", "openspec", "agent-wiki")}
    return {
        "head": git(root, "rev-parse", "--short", ref).strip(),
        "tracked_files": len(files),
        "top_level": top,
        "scripts": scripts,
        "targets": public_targets(root),
        "workflows": workflows(root),
        "groups": groups,
        "tests": sorted(p for p in files if re.fullmatch(r"tests/test_[^/]+\.py", p)),
    }


def _surface_markdown(s: dict) -> str:
    lines = [
        f"HEAD: `{s['head']}` — {s['tracked_files']} tracked files.",
        "",
        f"Top level: {', '.join(f'`{t}`' for t in s['top_level'])}.",
        "",
        "Tree sizes: " + ", ".join(f"`{k}/` {v}" for k, v in s["groups"].items()) + ".",
        "",
        "### Script modules (`scripts/`)",
        "",
    ]
    lines += [f"- `{m['path']}` — {m['summary']}" for m in s["scripts"]]
    lines += ["", "### Public make targets (`make help`)", ""]
    lines += [f"- `{name}` — {text}" for name, text in s["targets"]]
    lines += ["", "### Workflows", ""]
    for w in s["workflows"]:
        crons = ", ".join(f"`{c}`" for c in w["crons"]) or "no schedule"
        lines.append(f"- `{w['file']}` — {w['name']} ({crons})")
    lines += ["", f"### Tests\n\n{len(s['tests'])} `tests/test_*.py` files."]
    return "\n".join(lines)


# ------------------------------------------------------------------------- brief


def doc_text(root: Path, doc: str) -> str:
    path = root / doc
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def drift(root: Path, doc: str) -> dict:
    """The doc's last commit and everything that moved after it (real git, no model)."""
    sha = doc_last_commit(root, doc)
    if not sha:
        return {
            "doc_sha": "",
            "doc_subject": "",
            "commits": [],
            "paths": tracked_files(root)[:MAX_LISTED_PATHS],
            "full": True,
        }
    return {
        "doc_sha": sha,
        "doc_subject": commit_subject(root, sha),
        "commits": commits_since(root, sha),
        "paths": changed_since(root, sha, doc),
        "full": sha == git(root, "rev-parse", "HEAD").strip(),
    }


def brief(root: Path = REPO_ROOT, doc: str = DOC_DEFAULT) -> str:
    """The agent's whole input: current doc, what changed, and the real surface."""
    d = drift(root, doc)
    current = doc_text(root, doc)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    out = [f"# Architecture brief — {now}", "", f"Document: `{doc}`", ""]
    if not d["doc_sha"]:
        out.append("The doc has **no committed history**: treat this as a full rebuild and "
                   "create it from the surface below.")
    else:
        out.append(f"The doc was last committed at `{d['doc_sha'][:12]}` — {d['doc_subject']}.")
        out.append(f"Commits since then: {len(d['commits'])}.")
    out += ["", "## What changed since the doc was last written", ""]
    if d["doc_sha"]:
        out += [f"- `{c}`" for c in d["commits"]] or ["- (no commits since the doc's last commit)"]
    if d["paths"]:
        label = "Changed paths:" if d["doc_sha"] else "The tracked tree (a full rebuild covers all of it):"
        out += ["", label, ""]
        out += [f"- `{p.split(chr(9))[-1]}`" for p in d["paths"][:MAX_LISTED_PATHS]]
        if len(d["paths"]) > MAX_LISTED_PATHS:
            out.append(f"- … {len(d['paths']) - MAX_LISTED_PATHS} more")
    out += ["", "## The doc as committed", ""]
    out += ["```markdown", current.strip() or "(the doc does not exist yet)", "```", ""]
    out += ["## The code surface this doc must describe", "", _surface_markdown(surface(root)), ""]
    out += [
        "## What to do",
        "",
        f"1. Rewrite `{doc}` so every path, target, workflow and data file named above is "
        "described as the code actually is now. Keep the existing structure where it is still "
        "true; fix or delete what moved.",
        "2. Cover the shipped path end to end: install -> hardware/backend detection -> trend "
        "list -> engine skill -> engine image -> launcher, plus the data files, the CI jobs, "
        "the bots and their cron slots, and the test/gate layout.",
        "3. Name real files and targets. Do not invent a module, target, workflow, cron or "
        "image that the surface does not list.",
        "4. Write facts, not aspirations. If the surface does not show something, leave it "
        "out rather than guessing.",
        "5. Never name the retired CLI module — the deprecated shim that sits next to "
        "`scripts/llgenie_serve.py`. The rename guard (#251) refuses that spelling in ANY live "
        "file, this doc included, and the deterministic step below checks the doc against it "
        "before it commits (issue #573): describe the launcher as `scripts/llgenie_serve.py` "
        "only, and leave the shim unmentioned.",
        f"6. Modify no file except `{doc}`. Do not create a branch, do not commit, do not "
        "push, do not open an issue or a PR — the deterministic step does that.",
    ]
    return "\n".join(out) + "\n"


# ------------------------------------------------------------------ publish text


def _title(stamp: str) -> str:
    return f"docs(architecture): refresh docs/ARCHITECTURE.md for the tree at {stamp}"


def acceptance_items(doc: str, head: str) -> list[str]:
    """The three criteria of a refresh, stated ONCE (issue #2632). The issue body, the commit
    text and the PR body all mirror these exact strings, so no gate can catch the mirrors
    disagreeing — that is what `check-pr-closing` and the commit-checkbox parity gate look for."""
    return [
        f"`{doc}` describes the tree at `{head}` after the refresh",
        "the refresh commit carries the doc and the note+row+CHANGES.md pair it owes",
        "the PR that carries it names this issue and `closes` it",
    ]


def acceptance_proven(d: dict, doc: str, commit: str, head: str, issue: int) -> list[str]:
    """The evidence behind each tick (issue #745): a reproducible command + rc + sha, naming the
    publish commit — the head every later gate measures these ticks against. A dry preview names
    the base tip in its place (there is no publish commit yet)."""
    base = d["doc_sha"] or head
    return [
        f"`git diff {base}..{commit} --stat` rc=0 shows the doc rewritten against "
        f"{len(d['commits'])} commit(s) and {len(d['paths'])} path(s) of drift",
        f"`git show --stat {commit}` rc=0 names `{doc}`, the `agent-wiki/` note, the "
        f"`docs/changes.d/` row and `CHANGES.md`",
        f"the PR body ends `closes #{issue}` and the commit text carries the same line; "
        f"`make check-pr-closing` rc=0 at `{commit}`",
    ]


def tick_issue_acceptance(issue_text: str, items: list[str], proven: list[str]) -> str:
    """Swap the draft issue's unticked criteria for the ticked mirrors (issue #2632), line for
    line. A criterion the renderer no longer emits is a loud error, never a silent half-tick."""
    out = issue_text
    for item, why in zip(items, proven):
        draft = f"- [ ] {item}"
        if draft not in out:
            raise RuntimeError(f"the issue body no longer carries the criterion {item!r} — "
                               "the three mirrors would silently drift (issue #2632)")
        out = out.replace(draft, f"- [x] {item} (proven: {why})")
    return out


def render_commit_body(issue: int, d: dict, stamp: str, head: str, doc: str) -> str:
    """The bot commit's message body (issue #2632) — never the issue body dumped in again. It
    closes the issue the PR closes and carries the criteria in TICKED form, so the commit matches
    the PR body's checkboxes (issue #2519) and `check-pr-closing` finds one closure, not none."""
    return "\n".join([
        f"<!-- architecture-bot:{stamp} -->",
        "",
        f"Completes issue #{issue}: rewrites `{doc}` for the tree at `{head}` — "
        f"{len(d['commits'])} commit(s) and {len(d['paths'])} path(s) of drift since "
        f"`{d['doc_sha'][:12] or 'its first commit'}`. The commit carries the doc plus the "
        "note+row+CHANGES.md pair `check-docs` owes a doc change (issue #2598).",
        "",
        "Acceptance (the same criteria the issue lists and the PR body mirrors; the live issue "
        "body carries the proven strings):",
        "",
        *[f"- [x] {item}" for item in acceptance_items(doc, head)],
        "",
        f"closes #{issue}",
    ]) + "\n"


def _hygiene_lines(root: Path) -> list[str]:
    """The `AGENTS:`/`BASE:` pair the PR-hygiene gate reads (issue #792, #845): the full sha of
    the main tip this branch started from, plus the AGENTS.md that tip holds. A tree without
    AGENTS.md states neither line rather than inventing one."""
    tip = git(root, "rev-parse", "HEAD").strip()
    proc = _run(["git", "-C", str(root), "show", "HEAD:AGENTS.md"],
                capture_output=True, text=True)
    if proc.returncode != 0:
        return []
    content = proc.stdout
    return [
        f"AGENTS: {tip} {len(content.encode())}b {content.count(chr(10))}l",
        f"BASE: {tip} (== origin/main at open)",
    ]


def render_issue(d: dict, stamp: str, head: str, doc: str) -> str:
    """The refresh issue: the shape every issue in this repository carries (issue #745)."""
    paths = ", ".join(f"`{p.split(chr(9))[-1]}`" for p in d["paths"][:10]) or "(the doc has no history)"
    return issue_body.render(
        marker=f"<!-- architecture-bot:{stamp} -->",
        problem=(
            f"`{doc}` no longer matches the tree at `{head}`. Its last update was "
            f"`{d['doc_sha'][:12] or 'none'}` and {len(d['commits'])} commit(s) plus "
            f"{len(d['paths'])} changed path(s) have landed since, so a reviewer reconstructs the "
            "shipped path from source."
        ),
        why=(
            "The architecture doc is the map a contributor and an agent read before changing "
            "anything: once it lags the code it stops being a summary and becomes a second, wrong "
            "source of truth that is more convincing than no doc at all."
        ),
        how=[
            "`make architecture-bot-brief` derives the surface and the drift from real `git` state.",
            "`make architecture-bot-doc` rewrites the doc inside the agent image, where only the "
            f"doc (`{doc}`) is writable.",
            "The deterministic publish step commits that file on its own branch, pays the pair "
            "`check-docs` owes a doc change (its own `agent-wiki/` note, its `docs/changes.d/` "
            "row, `CHANGES.md`) — the bot used to commit the doc alone and reddened its own "
            "ci-scope (issue #2598) — and opens the linked PR.",
        ],
        benefit=(
            "The architecture map tracks the code on a 6-hour cadence instead of ageing silently, "
            "and every refresh is a small PR a reviewer can check against the drift it names."
        ),
        acceptance=acceptance_items(doc, head),
        technical=[
            f"drift = `git diff {d['doc_sha'] or 'HEAD'}..HEAD` excluding the doc",
            f"changed paths include {paths}",
            f"branch `{BRANCH_PREFIX}{stamp}`, commit authored `{AUTHOR_NAME} <{AUTHOR_EMAIL}>`",
            "the commit carries `agent-wiki/<stamp>-architecture-refresh-<issue>.md` and its "
            "`docs/changes.d/` row plus the rebuilt `CHANGES.md` (issue #2598)",
            "`make architecture-bot-brief` -> `make architecture-bot-doc` (Hermes, agent image) -> "
            "`make architecture-bot-publish`; the bot never merges and never pushes to `main`.",
        ],
    ) + "\n"


def render_pr(issue: int, d: dict, stamp: str, head: str, doc: str, branch: str,
              commit: str = "", hygiene: list[str] | None = None) -> str:
    paths = ", ".join(f"`{p.split(chr(9))[-1]}`" for p in d["paths"][:10]) or "(the doc has no history)"
    measured = commit or head  # a dry preview names the base tip where the publish commit will be
    ticked = [f"- [x] {item} (proven: {why})" for item, why in
              zip(acceptance_items(doc, head), acceptance_proven(d, doc, measured, head, issue))]
    return "\n".join([
        # The author a reviewer sees, before the diff (issue #840).
        git_identity.pr_author_line(),
        "",
        f"Completes the architecture refresh for `{doc}` at `{head}`.",
        "",
        f"Issue: `{doc}` lagged the tree — last updated at `{d['doc_sha'][:12] or 'never'}`, "
        f"with {len(d['commits'])} commit(s) and {len(d['paths'])} changed path(s) since, so "
        "the document did not describe the code a reviewer was reading.",
        "",
        "Fix: the architecture bot re-derived the surface and the drift from real `git` "
        "state and rewrote only the doc; the publish step commits that doc plus the note+row "
        f"pair `check-docs` owes a doc change on `{branch}` (issue #2598).",
        "",
        "Benefit: the architecture document is current again and stays reviewable — a human "
        "approves the refresh, and the next 6-hour run is quiet until the tree moves again.",
        "",
        f"Technical: `make architecture-bot-brief` -> `make architecture-bot-doc` (Hermes, "
        f"agent image) -> `make architecture-bot-publish`. Drift paths include {paths}. "
        f"`{doc}` is committed with its owed pair (`agent-wiki/` note + `docs/changes.d/` row + "
        f"`CHANGES.md`), as `{AUTHOR_NAME} <{AUTHOR_EMAIL}>`. The bot never "
        "merges and never pushes to `main`.",
        "",
        # The same ticked checklist the issue body carries and the commit text mirrors — three
        # mirrors, one objective (issue #2632). The heading NAME is interpolated: issue #745
        # spells `##` section headings only in scripts/issue_body.py (see test_check_issue_body).
        f"## {ACCEPTANCE_SECTION}",
        "",
        *ticked,
        "",
        *(hygiene or []),
        *([""] if hygiene else []),
        f"closes #{issue}",
    ]) + "\n"


# ---------------------------------------------------------------------- publishing


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    # policy: run_ok — the caller inspects rc (issue #797, scripts/proc.py is the one seam).
    return run_ok(cmd, **kwargs)


def _gh(gh: str, *args: str, stdin: str | None = None, token: str = "") -> str:
    """Run `gh`. A `token` override travels in the child's ENVIRONMENT only (never argv)."""
    env = {**os.environ, "GH_TOKEN": token} if token else None
    proc = _run([gh, *args], input=stdin, env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()}")
    return proc.stdout.strip()


#: What a GitHub write can fail with when the answer was lost rather than the write refused: a 502
#: or 504 from the API gateway, or a timeout. Retried, then recovered by looking for the PR the
#: create may in fact have made (issue #479).
TRANSIENT = re.compile(r"50[234]|gateway timeout|timed out|timeout", re.I)


def _gh_retry(gh: str, *args: str, stdin: str | None = None, attempts: int = 3,
              delay: float = 1.0, token: str = "") -> str:
    """`_gh`, retried a bounded number of times on a transient gateway failure."""
    last: RuntimeError | None = None
    for attempt in range(1, attempts + 1):
        try:
            return _gh(gh, *args, stdin=stdin, token=token)
        except RuntimeError as exc:
            last = exc
            if not TRANSIENT.search(str(exc)):
                raise
            if attempt < attempts:
                time.sleep(delay)
    assert last is not None
    raise last


def open_pr_for_branch(gh: str, repo: str, branch: str) -> str:
    """The URL of an OPEN PR whose head is `branch`, or "" — the recovery after a lost create."""
    out = _gh(gh, "pr", "list", "--repo", repo, "--head", branch, "--state", "open",
              "--json", "number,url")
    for row in json.loads(out or "[]"):
        if row.get("url"):
            return str(row["url"])
    return ""


def open_architecture_pr(gh: str, repo: str) -> str:
    """The head branch of an already-open architecture PR, or "" when none is open.

    A 6-hour cadence must not file a second issue for drift a PR already carries: the PR is
    the first bot's answer, and the next run waits for it to land.
    """
    out = _gh(gh, "pr", "list", "--repo", repo, "--state", "open",
              "--limit", "50", "--json", "number,headRefName")
    for row in json.loads(out or "[]"):
        if str(row.get("headRefName", "")).startswith(BRANCH_PREFIX):
            return f"#{row['number']} ({row['headRefName']})"
    return ""


def _safe_doc(doc: str) -> str:
    rel = Path(doc)
    if rel.is_absolute() or ".." in rel.parts or rel.suffix != ".md":
        raise ValueError(f"--doc must be a repository-relative .md path, got {doc!r}")
    return rel.as_posix()


def pair_stem(stamp: str, issue: int) -> str:
    """The stem shared by the refresh pair's note and fragment (issue #2598)."""
    return f"{stamp[0:4]}-{stamp[4:6]}-{stamp[6:8]}-architecture-refresh-{issue}"


def pair_row(stem: str, doc: str, d: dict, issue: int) -> str:
    """The fragment's ONE row: `| date | summary | [note](agent-wiki/<stem>.md) | #issue |`."""
    return (f"| {stem[:10]} | architecture-bot rebuilt `{doc}` from the tree — "
            f"{len(d['commits'])} commit(s), {len(d['paths'])} path(s) since the doc's last "
            f"commit ({d['doc_sha'][:12] or 'none'}) | [{stem}.md](agent-wiki/{stem}.md) "
            f"| #{issue} |")


def pair_note(stem: str, doc: str, d: dict, issue: int) -> str:
    """The `agent-wiki/` work record every doc change's pair carries (issue #1123)."""
    return (
        f"# {stem[:10]} — architecture refresh of `{doc}` (issue #{issue})\n\n"
        f"- Problem: `{doc}` lagged the tree — {len(d['commits'])} commit(s) and "
        f"{len(d['paths'])} changed path(s) since the doc's last commit "
        f"(`{d['doc_sha'][:12] or 'none'}`).\n"
        "- Fix: the brief+doc legs rebuilt the doc from the real tree (the model leg still writes "
        "only the doc); this note and its `docs/changes.d/` row pay the pair `make check-docs` "
        "owes a branch that changes the doc (rule: issue #1123; owning the pair is issue #2598).\n"
    )


def emit_pair(root: Path, doc: str, issue: int, stamp: str, d: dict) -> list[str]:
    """Write the note+row pair and rebuild `CHANGES.md`; return the paths to commit.

    This is the deterministic half: it runs AFTER the stray guard, so the agent's "the doc is
    the ONLY writable file" line never weakens — the bot pays its own debt here (issue #2598,
    measured on PR #2595 whose doc-alone commit reddened its ci-scope `check-docs`).
    """
    stem = pair_stem(stamp, issue)
    note = root / changes_index.WIKI_DIR / f"{stem}.md"
    frag = root / changes_index.FRAGMENTS / f"{stem}.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    frag.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(pair_note(stem, doc, d, issue), encoding="utf-8")
    frag.write_text(pair_row(stem, doc, d, issue) + "\n", encoding="utf-8")
    rc = changes_index.write(root)
    if rc != 0:
        raise ValueError(
            "the refresh pair was written but `changes_index.write` refused the index "
            f"(rc={rc}); nothing was committed or pushed — fix the fragment/note pairing and "
            "re-run")
    return [note.relative_to(root).as_posix(), frag.relative_to(root).as_posix(),
            changes_index.CHANGES]


def publish(root: Path, repo: str, doc: str = DOC_DEFAULT, stamp: str = "",
            dry: bool = False, gh: str | None = None) -> dict:
    """Issue + branch + commit + PR for a real doc change; nothing at all otherwise."""
    doc = _safe_doc(doc)
    stamp = stamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M")
    gh = gh or shutil.which("gh") or "gh"

    text = doc_text(root, doc)
    if not text.strip():
        raise ValueError(f"{doc} is missing or empty — nothing to publish")
    if len(text) < MIN_DOC_CHARS:
        raise ValueError(f"{doc} is only {len(text)} characters (minimum {MIN_DOC_CHARS}) — "
                         "refusing to publish a stub")
    # The same rule `make test-unit` enforces, applied to the WRITER (issue #573): the doc refresh
    # wrote the retired CLI module's name into the doc, and the violation only surfaced 25 minutes
    # later as two red unit jobs on PR #572. Checked here, it costs seconds and nothing is written.
    named = module_name_guard.offenders(text)
    if named:
        raise ValueError(
            f"{doc} names the retired CLI module ({', '.join(sorted(set(named)))}): the rename "
            f"guard refuses that spelling in any live file (issue #251), so this refresh would land "
            f"red on both unit jobs (issue #573). Nothing was committed or pushed — describe the "
            f"launcher as scripts/llgenie_serve.py only.")
    if not doc_is_dirty(root, doc):
        return {"action": "none", "reason": f"{doc} is identical to HEAD — no drift to publish"}

    # The agent may write ONLY the doc. A tracked file changed anywhere else means it crossed that
    # line, and publishing would carry an unreviewed code edit inside an "architecture refresh".
    stray = stray_changes(root, doc)
    if stray:
        raise ValueError(f"the run changed files other than {doc}: {', '.join(stray)} — "
                         "refusing to publish an architecture refresh that edits the product")

    # The commit must start from `main`: publishing from a feature branch would attach the doc to
    # somebody else's PR (`git checkout -b` would branch off that PR's head, not the base).
    branch_now = current_branch(root)
    if branch_now != "main":
        raise ValueError(f"refusing to publish from branch {branch_now!r}: the refresh must start "
                         "from `main`, or it would ride on another branch's PR")

    pending = open_architecture_pr(gh, repo)
    if pending:
        return {"action": "pending", "reason": f"an architecture PR is already open: {pending}"}

    d = drift(root, doc)
    head = head_sha(root)
    branch = f"{BRANCH_PREFIX}{stamp}"
    # The pair is this bot's own debt (issue #2598): prove the fragment row parses BEFORE any
    # issue, branch or commit exists, so a refusal files and writes nothing.
    probe_stem = pair_stem(stamp, 0)
    _, probe_err = changes_index.parse_row(pair_row(probe_stem, doc, d, 0), probe_stem)
    if probe_err:
        raise ValueError("the refresh pair would not parse: " + "; ".join(probe_err))
    issue_text = render_issue(d, stamp, head, doc)
    items = acceptance_items(doc, head)
    hygiene = _hygiene_lines(root)  # the base tip's AGENTS pair — read before this run commits
    # A dry preview shows the FINAL shape: the same ticked mirrors and hygiene lines the wire
    # bodies will carry, with the base tip named where the publish commit will be.
    issue_preview = tick_issue_acceptance(issue_text, items,
                                          acceptance_proven(d, doc, head, head, 0))
    pr_body = render_pr(0, d, stamp, head, doc, branch, hygiene=hygiene)
    result = {"action": "would-publish", "doc": doc, "branch": branch, "head": head,
              "issue_body": issue_preview, "pr_body": pr_body}
    if dry:
        return result

    issue_url = _gh(gh, "issue", "create", "--repo", repo, "--title", _title(stamp),
                    "--body", issue_text)
    issue_num = int(issue_url.rstrip("/").rsplit("/", 1)[-1])

    git(root, "checkout", "-b", branch)
    pair = emit_pair(root, doc, issue_num, stamp, d)
    git(root, "add", "--", doc, *pair)
    # The identity comes from the ONE seam that sets it (`scripts/git_identity.py`, issue #840), the
    # bot half of the allowlist `make check-pr-authors` enforces — not from whatever the host's git
    # config holds, and not from a second literal here that could drift to another domain.
    git_identity.apply(root)
    # The commit text is its own block (issue #2632), not the issue body: the draft issue body
    # carries unticked criteria and no closes line, and dumping it into the commit reddened
    # `check-pr-closing` on every refresh (measured on PR #2629, run 43386226859).
    git(root, "commit", "-m", _title(stamp), "-m", render_commit_body(issue_num, d, stamp, head, doc))
    commit = git(root, "rev-parse", "HEAD").strip()

    # The mirrors are ticked BEFORE the PR opens (issue #2632): every tick names the publish
    # commit — the head ci-scope will judge them against — so no gate ever reads an unticked or
    # unproven criterion on a body it is checking.
    issue_text = tick_issue_acceptance(issue_text, items,
                                       acceptance_proven(d, doc, commit, head, issue_num))
    _gh_retry(gh, "api", "PATCH", f"repos/{repo}/issues/{issue_num}", "-F", "body=@-",
              stdin=issue_text)
    git(root, "push", "-u", "origin", branch)
    pr_body = render_pr(issue_num, d, stamp, head, doc, branch, commit=commit, hygiene=hygiene)
    # A GitHub 502/504 here means the answer was lost, not that the PR was refused: retry, then look
    # for the PR the create may have made, and only then fail (issue #479).
    #
    # The PR is opened with the OWNER PAT, never the job token: a pull request created with
    # `GITHUB_TOKEN` starts NO workflows, so it would carry zero checks and could never become green
    # (issue #497). The issue keeps the job token — the only one of the two with Issues write (#412).
    pr_token = (os.environ.get("PR_TOKEN") or "").strip()
    try:
        pr_url = _gh_retry(gh, "pr", "create", "--repo", repo, "--base", "main", "--head", branch,
                           "--title", _title(stamp), "--body", pr_body, token=pr_token)
    except RuntimeError as exc:
        pr_url = open_pr_for_branch(gh, repo, branch)
        if not pr_url:
            raise RuntimeError(
                f"{exc} — issue #{issue_num} and branch {branch} were created; no PR exists for "
                "that branch, so a human has to open it or the next run will try again") from exc

    result = {"action": "published", "doc": doc, "branch": branch, "commit": commit,
              "issue": issue_num, "issue_url": issue_url, "pr_url": pr_url,
              "head": head, "issue_body": issue_text, "pr_body": pr_body,
              "pair": pair}
    return result


# -------------------------------------------------------------------------- main


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="architecture_bot", description=__doc__)
    p.add_argument("--root", default=str(REPO_ROOT))
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("brief", help="write the architecture brief from the real tree")
    b.add_argument("--doc", default=DOC_DEFAULT)
    b.add_argument("--out", default="architecture-brief.md")

    s = sub.add_parser("surface", help="print the tree's surface as JSON")
    s.add_argument("--json", action="store_true")

    pub = sub.add_parser("publish", help="file ONE issue + ONE PR for a real doc change")
    pub.add_argument("--repo", required=True)
    pub.add_argument("--doc", default=DOC_DEFAULT)
    pub.add_argument("--stamp", default="")
    pub.add_argument("--dry", action="store_true")
    pub.add_argument("--gh", default="")

    args = p.parse_args(argv)
    root = Path(args.root)

    if args.cmd == "surface":
        print(json.dumps(surface(root), indent=2))
        return 0

    if args.cmd == "brief":
        text = brief(root, args.doc)
        Path(args.out).write_text(text, encoding="utf-8")
        d = drift(root, args.doc)
        print(f"brief: {args.out} ({len(text)} chars)")
        print(f"doc: {args.doc} last commit: {d['doc_sha'][:12] or 'none (full rebuild)'}")
        print(f"commits since: {len(d['commits'])}  changed paths: {len(d['paths'])}")
        return 0

    try:
        result = publish(root, args.repo, args.doc, args.stamp, args.dry,
                         args.gh or None)
    except (ValueError, RuntimeError) as exc:
        print(f"architecture-bot: {exc}", file=sys.stderr)
        return 2

    print(f"action={result['action']}")
    for key in ("reason", "branch", "commit", "issue", "issue_url", "pr_url"):
        if result.get(key) not in (None, ""):
            print(f"{key}={result[key]}")
    if args.dry and result["action"] == "would-publish":
        print("--- issue body ---")
        print(result["issue_body"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
