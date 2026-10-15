#!/usr/bin/env python3
"""The code-review bot: read the tree and the pipelines, and file what is actually wrong.

Analysis produces ISSUES, never implementation (AGENTS.md, #231) — this bot's entire output is one
issue per finding, and every issue carries the evidence it was derived from so a reviewer can check
it without re-deriving anything. It never edits a file, never opens a PR, never merges, and never
comments on a PR.

Two halves, deliberately split:

* **the checks** (here, deterministic, no LLM): they read the real tree and the real pipelines and
  emit findings with a stable `key`, a title, the evidence, and where it came from. A check that
  finds nothing files nothing — silence is the success case.
* **the judgement** is the reviewer's: an issue is a claim to verify, so the body says exactly which
  file/line/workflow and which measured number supports it.

Commands (stdlib only; the GitHub API only through a `gh` on PATH, or --gh):

  scan [--json]        every finding, as markdown (the default) or JSON
  file [--dry]         create ONE issue per NEW finding (dedup by the marker in the body),
                       capped per run. Never touches code, never merges.

Checks:

  workflow-inline-scripts  a workflow `run:` invokes a repo script directly instead of a make target
  secrets-not-defined      a workflow reads `secrets.X` and X is not one of the repo's secrets
  workflow-never-ran       a workflow that has never run at all (a pipeline nobody exercises)
  cron-collisions          two workflows scheduled at the same minute+hour on overlapping days

Usage:
    python3 scripts/code_review.py scan --repo asimov-agent/llgenie
    python3 scripts/code_review.py file --repo asimov-agent/llgenie --dry
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ".github/workflows"
#: The marker a filed issue carries, so a later run recognises its own work and stays quiet.
MARKER = "<!-- code-review:{key} -->"

SECRET_REF = re.compile(r"secrets\.([A-Za-z0-9_]+)")
# A `run:` block that reaches into the repo directly: the standing rule is one make target per step.
INLINE_SCRIPT = re.compile(r"(?:^|[^\w./-])((?:python3?\s+)?(?:\./)?(?:scripts/[\w./-]+|tools/[\w./-]+\.sh))\b")
MAKE_CALL = re.compile(r"\bmake\s+[\w-]+")
#: `run:` blocks that are allowed to be shell: the guard/orchestration steps the rule exempts.


def _read(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def _workflow_files(root: Path) -> list[Path]:
    return sorted((root / WORKFLOWS).glob("*.yml"))


def _steps(text: str) -> list[tuple[str, str]]:
    """(step name, its run block) for every step of a workflow file, comments stripped."""
    out: list[tuple[str, str]] = []
    name = ""
    block: list[str] | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if re.match(r"^-\s+name:", stripped):
            name = stripped.split(":", 1)[1].strip().strip("'\"")
        if re.match(r"^-\s+run:", stripped) or re.match(r"^run:", stripped):
            block = []
            tail = stripped.split("run:", 1)[1].strip()
            if tail and tail not in ("|", ">"):
                block.append(tail)
            continue
        if block is not None:
            if line and not line.startswith((" ", "\t")):
                out.append((name, "\n".join(block)))
                block = None
            elif stripped:
                block.append(stripped)
    if block is not None:
        out.append((name, "\n".join(block)))
    return out


def _cron_slots(text: str) -> list[str]:
    return re.findall(r'cron:\s*"([^"]+)"', text)


def _triggers(text: str) -> set[str]:
    """The top-level keys under `on:` — the events that can start this workflow on its own."""
    lines = text.splitlines()
    start = next((n for n, l in enumerate(lines) if l.startswith("on:")), None)
    if start is None:
        return set()
    tail = lines[start].split("on:", 1)[1].strip()
    if tail:
        return {t.strip() for t in tail.strip("[]").split(",") if t.strip()}
    out: set[str] = set()
    for line in lines[start + 1:]:
        if not line.strip() or line.strip().startswith("#"):
            continue
        if not line.startswith(" "):
            break
        if len(line) - len(line.lstrip()) == 2 and ":" in line:
            out.add(line.strip().split(":", 1)[0].strip())
    return out


def _reusable_only(text: str) -> bool:
    """A `workflow_call`-only file is a reusable pipeline: a CALLER starts it, not an event."""
    tr = _triggers(text)
    return tr == {"workflow_call"}


def _days_overlap(a: str, b: str) -> bool:
    """Do two crontab day-of-week fields (5th field) overlap? `*` overlaps everything."""
    a, b = (a or "*"), (b or "*")
    if a == "*" or b == "*":
        return True
    seta = {d.strip() for d in a.split(",") if d.strip()}
    setb = {d.strip() for d in b.split(",") if d.strip()}
    return bool(seta & setb)


# ---------------------------------------------------------------------------
# the checks
# ---------------------------------------------------------------------------
def check_workflow_inline_scripts(root: Path) -> list[dict]:
    """A workflow runs a repo script directly instead of a make target - checked PER COMMAND.

    The rule is one `make <target>` per command (AGENTS.md, "Every command a CI workflow runs must
    be a make target"); only gh/git orchestration that carries no repo logic may stay inline.

    The scan is per LINE, not per step block (issue #296). A block-level exemption (skip the block as
    soon as it contains a make call, or any `gh api`/`gh pr`/...) is exactly how a violation hides: a
    step that legitimately orchestrates with `gh` may still call a repo script on another line, and
    that is what `registry-sync.yml` did with `scripts/engine_skill_gap.py` for as long as the
    exemption existed. A `make` on the SAME line as the script call is the one thing that clears it.
    """
    out = []
    for wf in _workflow_files(root):
        for name, block in _steps(_read(wf)):
            for line in block.splitlines():
                hit = INLINE_SCRIPT.search(line)
                if not hit or MAKE_CALL.search(line):
                    continue
                finding = {
                    "key": f"workflow-inline-scripts/{wf.name}",
                    "title": f"ci: {wf.name} runs a repo script directly instead of a make target",
                    "evidence": (
                        f"`{wf.name}` step \"{name or '(unnamed)'}\" invokes `{hit.group(1)}` on a "
                        f"line of its `run:` block, while the standing rule is that a workflow's "
                        f"`run:` calls a `make` target and nothing else (AGENTS.md, \"Every command "
                        f"a CI workflow runs must be a make target\"). Only gh/git orchestration that "
                        f"carries no repo logic may stay inline."
                    ),
                    "where": f"{WORKFLOWS}/{wf.name}",
                }
                if finding not in out:
                    out.append(finding)
    return out


def check_secrets_not_defined(root: Path, defined: set[str]) -> list[dict]:
    """A workflow reads `secrets.X` and X is not one of the repo's secrets: the job env is empty."""
    used: dict[str, set[str]] = {}
    for wf in _workflow_files(root):
        for name in SECRET_REF.findall(_read(wf)):
            used.setdefault(name, set()).add(wf.name)
    out = []
    for name in sorted(used):
        if name in defined or name in ("GITHUB_TOKEN",):
            continue
        files = ", ".join(sorted(used[name]))
        out.append({
            "key": f"secrets-not-defined/{name}",
            "title": f"ci: the workflows read secrets.{name}, which the repo does not define",
            "evidence": (
                f"{files} reference `secrets.{name}`, and `gh secret list` for the repo does not "
                f"define it. GitHub substitutes an EMPTY string for a secret that does not exist, so "
                f"the job does not fail at startup — it fails later, wherever that value is used "
                f"(measured: a bot step stopped at `NOUS_API_KEY unset - refusing to spend time on a "
                f"dead key` with `NOUS_API_KEY:` blank in its env block). Either the secret is "
                f"missing, or the workflow names the wrong one."
            ),
            "where": files,
        })
    return out


def check_workflow_never_ran(root: Path, runs: dict[str, int]) -> list[dict]:
    """A workflow that runs on its own events and has never run: pipeline code nobody exercises.

    A `workflow_call`-only file is deliberately NOT judged here: GitHub starts it inside a caller
    and its runs are not counted under its own workflow (measured: `ci.yml` invokes `pipeline.yml`
    three times and `ci.yml` reports 892 runs while `pipeline.yml` reports 0), so "0 runs" there is
    an artefact of how the API counts, not evidence of neglect. `reusable-orphan` is the check for
    those.
    """
    out = []
    for wf in _workflow_files(root):
        text = _read(wf)
        if _reusable_only(text):
            continue
        if runs.get(wf.name, -1) != 0:
            continue
        events = ", ".join(sorted(_triggers(text))) or "none"
        out.append({
            "key": f"workflow-never-ran/{wf.name}",
            "title": f"ci: {wf.name} has never run — no run has ever exercised it",
            "evidence": (
                f"The Actions API reports **0 runs** for `{wf.name}` (it can be started by: "
                f"{events}) since it was added. A workflow that has never executed is unverified: "
                f"its guard, its permissions, its image tags and its make targets have only ever "
                f"been reviewed, never run (measured: `publish-agent-image.yml` reported 0 runs, "
                f"and its first dispatch failed on a GHCR scope the file explicitly claimed to "
                f"handle). Run it once deliberately, or delete it."
            ),
            "where": f"{WORKFLOWS}/{wf.name}",
        })
    return out


def check_reusable_orphan(root: Path) -> list[dict]:
    """A `workflow_call` pipeline that no other workflow calls: a pipeline that cannot run."""
    files = _workflow_files(root)
    corpus = {wf.name: _read(wf) for wf in files}
    out = []
    for wf in files:
        text = corpus[wf.name]
        if not _reusable_only(text):
            continue
        callers = [n for n, body in corpus.items()
                   if n != wf.name and f"workflows/{wf.name}" in body]
        if callers:
            continue
        out.append({
            "key": f"reusable-orphan/{wf.name}",
            "title": f"ci: {wf.name} is a reusable pipeline that nothing calls",
            "evidence": (
                f"`{wf.name}` declares `workflow_call` as its only trigger, so only another workflow "
                f"can start it — and no workflow in `{WORKFLOWS}/` references "
                f"`workflows/{wf.name}`. Nothing runs it."
            ),
            "where": f"{WORKFLOWS}/{wf.name}",
        })
    return out


def check_cron_collisions(root: Path) -> list[dict]:
    """Two workflows scheduled at the same minute+hour on overlapping days."""
    slots: list[tuple[str, str, str]] = []       # (workflow, "minute hour", day-of-week)
    for wf in _workflow_files(root):
        for cron in _cron_slots(_read(wf)):
            parts = cron.split()
            if len(parts) < 5 or not parts[0].isdigit() or not parts[1].isdigit():
                continue  # `*`/step crons fire repeatedly; the collision check is for fixed slots
            slots.append((wf.name, f"{parts[1]}:{parts[0].zfill(2)}", parts[4]))
    out = []
    for i, (a, slot_a, days_a) in enumerate(slots):
        for b, slot_b, days_b in slots[i + 1:]:
            if slot_a != slot_b or not _days_overlap(days_a, days_b):
                continue
            out.append({
                "key": f"cron-collisions/{slot_a}-{a}-{b}",
                "title": f"ci: {a} and {b} are both scheduled at {slot_a} UTC",
                "evidence": (
                    f"`{a}` ({days_a}) and `{b}` ({days_b}) share the same minute+hour slot "
                    f"({slot_a} UTC) on overlapping days, so on those days both start together — "
                    f"they contend for the same runner minutes, and for any shared resource "
                    f"(registry, secret, upstream API quota) they race. Stagger one of them."
                ),
                "where": f"{WORKFLOWS}/{a}, {WORKFLOWS}/{b}",
            })
    return out


# ---------------------------------------------------------------------------
# gh (read-only here: scan and dedup)
# ---------------------------------------------------------------------------
def _gh(gh: str, args: list[str]) -> str:
    r = subprocess.run([gh, *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"[code-review] {gh} {' '.join(args)} failed ({r.returncode}): {r.stderr.strip()}")
    return r.stdout


def _gh_soft(gh: str, args: list[str]) -> str | None:
    """`gh` output, or None when the call is refused — a check that needs admin degrades loudly."""
    r = subprocess.run([gh, *args], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"[code-review] WARNING: 'gh {' '.join(args)}' was refused ({r.returncode}): "
              f"{r.stderr.strip().splitlines()[:1]} — that check is SKIPPED this run",
              file=sys.stderr)
        return None
    return r.stdout


def defined_secrets(gh: str, repo: str) -> set[str] | None:
    """The repo's secret names, or None when the token cannot read them (needs admin)."""
    out = _gh_soft(gh, ["secret", "list", "--repo", repo, "--json", "name"])
    if out is None:
        return None
    return {s.get("name") for s in (json.loads(out or "[]") or []) if s.get("name")}


def workflow_run_counts(gh: str, repo: str) -> dict[str, int] | None:
    """{workflow FILE name: total runs ever}, or None when the token cannot read the runs.

    The runs endpoint addresses a workflow by its FILE name (or numeric id), not by its display
    name — querying by `name` 404s for any workflow whose name differs from its file
    (`bench-disk` vs `bench-disk.yml`), which is why the path is what is used here.
    """
    out = _gh_soft(gh, ["workflow", "list", "--repo", repo, "--json", "name,path"])
    if out is None:
        return None
    counts: dict[str, int] = {}
    for row in json.loads(out or "[]") or []:
        name = row.get("name") or ""
        path = (row.get("path") or "").split("/")[-1]
        if not name or not path:
            continue
        got = _gh_soft(gh, ["api", f"repos/{repo}/actions/workflows/{path}/runs?per_page=1",
                            "--jq", ".total_count"])
        if got is None:
            continue
        try:
            counts[path] = int((got or "0").strip() or 0)
        except ValueError:
            counts[path] = 0
    return counts


def findings(root: Path = REPO_ROOT, gh: str | None = None, repo: str = "",
             secrets: set[str] | None = None, runs: dict[str, int] | None = None) -> list[dict]:
    """Every finding, deterministic: the static checks always run, the live ones when data is given."""
    out = (check_workflow_inline_scripts(root) + check_cron_collisions(root)
           + check_reusable_orphan(root))
    if secrets is not None:
        out += check_secrets_not_defined(root, secrets)
    if runs is not None:
        out += check_workflow_never_ran(root, runs)
    return out


# ---------------------------------------------------------------------------
# filing: ONE issue per NEW finding, never code
# ---------------------------------------------------------------------------
def issue_body(f: dict) -> str:
    return "\n".join([
        f.get("evidence", "").strip(),
        "",
        f"- found by: the code-review bot (`scripts/code_review.py`, check `{f['key'].split('/')[0]}`)",
        f"- where: `{f.get('where', '')}`",
        "",
        "This is an analysis finding, not a fix: it is filed for a human to accept, refine or "
        "decline. Nothing was changed by the run that filed it.",
        "",
        MARKER.format(key=f["key"]),
    ])


def filed(gh: str, repo: str, key: str) -> bool:
    """Has this finding been filed already? The marker is the memory, so runs stay idempotent."""
    out = _gh(gh, ["issue", "list", "--repo", repo, "--state", "all", "--search",
                   f"\"{MARKER.format(key=key)}\"", "--limit", "5", "--json", "number"])
    return bool(json.loads(out or "[]") or [])


def file_findings(gh: str, repo: str, items: list[dict], cap: int = 3, dry: bool = False) -> list[dict]:
    """Create one issue per NEW finding, up to `cap` per run. Never edits a file, never merges."""
    created = []
    for f in items:
        if len(created) >= cap:
            print(f"[code-review] cap reached: {len(created)}/{cap} issues filed this run")
            break
        if filed(gh, repo, f["key"]):
            print(f"[code-review] already filed: {f['key']}")
            continue
        if dry:
            print(f"[code-review] would file: {f['title']} (key {f['key']})")
            created.append({**f, "dry": True})
            continue
        out = _gh(gh, ["issue", "create", "--repo", repo, "--title", f["title"],
                       "--body", issue_body(f)])
        print(f"[code-review] filed: {out.strip()}")
        created.append({**f, "url": out.strip()})
    return created


def render(items: list[dict]) -> str:
    if not items:
        return "[code-review] no findings: the checks found nothing to file"
    lines = [f"[code-review] {len(items)} finding(s)"]
    for f in items:
        lines += ["", f"- {f['title']}", f"  key: {f['key']}", f"  where: {f.get('where', '')}"]
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="code_review", description=__doc__)
    sub = p.add_subparsers(dest="cmd")
    for name in ("scan", "file"):
        c = sub.add_parser(name)
        c.add_argument("--repo", required=True, help="owner/repo the pipelines belong to")
        c.add_argument("--gh", default="gh")
        c.add_argument("--root", default=str(REPO_ROOT))
        c.add_argument("--json", action="store_true")
        c.add_argument("--static-only", action="store_true",
                       help="skip the checks that read the GitHub API (secrets, run counts)")
        if name == "file":
            c.add_argument("--cap", type=int, default=3)
            c.add_argument("--dry", action="store_true")

    args = p.parse_args(argv)
    if not args.cmd:
        p.error("need a command: scan | file")
    root = Path(args.root)
    secrets = runs = None
    if not args.static_only:
        secrets = defined_secrets(args.gh, args.repo)
        runs = workflow_run_counts(args.gh, args.repo)
        if secrets is None:
            print("[code-review] NOTE: the secrets check is unavailable here (it needs a token with "
                  "admin on the repo); run the bot with one, or the check reports nothing.",
                  file=sys.stderr)
        if runs is None:
            print("[code-review] NOTE: the run-count check is unavailable here (the Actions API "
                  "refused the read); run the bot with a token that can read them.", file=sys.stderr)
    items = findings(root, args.gh, args.repo, secrets, runs)

    if args.cmd == "scan":
        print(json.dumps(items, indent=2) if args.json else render(items))
        return 0
    created = file_findings(args.gh, args.repo, items, args.cap, args.dry)
    print(f"[code-review] {len(created)} issue(s) {'would be ' if args.dry else ''}filed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
