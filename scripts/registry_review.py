#!/usr/bin/env python3
"""Review a GREEN registry-sync PR: is the VRAM trend list listed, and is each row's
server the highest t/s that fits that card? Then open ONE issue about it (issue #709).

  registry_review.py brief   [--repo OWNER/REPO] [--branch BR] [--store FILE] [--out FILE]
  registry_review.py publish [--repo OWNER/REPO] [--in FILE] [--utc STORE_UTC] [--dry]

`brief` has two halves, both deterministic and offline:

* **the precondition** — an OPEN `chore/registry-sync` pull request whose checks are all
  green. No such PR, a red check, or a pending check is `action=skip`: the review exists
  for the store that can land, and nothing is spent on the one that cannot.
* **the selection check** — for every `(arch, vram, ram)` case the trend list is built
  from (`scripts/trend_list_matrix.py`), the models `trend_list()` lists for that card,
  and for each of them the server `rank_engines()` puts first with its t/s. A row whose
  named server is not the fastest of its own rank class, a listed model with no server
  at all, and a tier that lists nothing are findings — the reported classes (#669, #225).

The judgement — which finding matters, what llgenie must change, which engine to ship —
is the agent leg's, under `.hermes/skills/registry-sync-review/SKILL.md`. `publish` reads
that leg's verdict and files ONE issue labelled `agent:implement`, keyed by the store's
`generated_utc`, so a re-run updates the issue instead of filing a second one.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import model_engine_pick as mp  # noqa: E402

STORE = REPO / "data" / "models.json"
MATRIX = REPO / "tests" / "fixtures" / "trend-list-matrix.json"
BRANCH = "chore/registry-sync"
MARKER = "<!-- registry-sync-review: {utc} -->"
CHANGE_MARKER = "<!-- registry-sync-changes: {utc} -->"
LABEL = "agent:implement"
TITLE_PREFIX = "sync review:"
#: The grid the committed trend-list matrix is built from (scripts/trend_list_matrix.py).
ARCHS = ("cuda", "rocm", "vulkan", "metal", "cpu")
VRAMS = (8, 16, 24, 48)
RAMS = (8, 32, 60, 64)
#: The RAM a rendered per-arch table uses; findings are collected over every RAM.
TABLE_RAM = 32


# --------------------------------------------------------------------------- gh
def run_gh(args: list[str], ok_codes: tuple[int, ...] = (0,)) -> str:
    """`gh` is the external system; tests replace this function."""
    out = subprocess.run(["gh", *args], capture_output=True, text=True)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
    if out.returncode not in ok_codes:
        raise RuntimeError(f"gh {' '.join(args)} failed ({out.returncode}): {out.stderr.strip()}")
    return out.stdout


def sync_pr(repo: str | None, branch: str = BRANCH) -> dict:
    """The OPEN registry-sync PR and whether every one of its checks is green."""
    base = ["--repo", repo] if repo else []
    listing = json.loads(run_gh(["pr", "list", *base, "--head", branch, "--state", "open",
                                 "--json", "number,url,title,headRefOid,mergeStateStatus"]))
    if not listing:
        return {"found": False, "green": False,
                "why": f"no open `{branch}` PR (the sync opens one only when its gates pass)"}
    pr = listing[0]
    try:
        # `gh pr checks` exits 8 while a check is pending and 1 when there are none: both
        # are a real answer ("not green yet"), not a broken command.
        raw = run_gh(["pr", "checks", str(pr["number"]), *base,
                      "--json", "bucket,name,state,link"], ok_codes=(0, 1, 8))
    except RuntimeError as exc:  # noqa: BLE001  (gh itself failing is reported, not raised)
        return {"found": True, "green": False, "pr": pr, "checks": [], "why": str(exc)}
    try:
        checks = json.loads(raw) if raw.strip() else []
    except json.JSONDecodeError:
        checks = []
    bad = [c for c in checks if (c.get("bucket") or "").lower() in ("fail", "pending", "cancel")]
    green = bool(checks) and not bad
    why = ""
    if not checks:
        why = "the PR carries no checks (a PR opened with the job token starts none)"
    elif bad:
        why = "; ".join(f"{c.get('name')}={c.get('bucket')}" for c in bad)
    return {"found": True, "green": green, "pr": pr, "checks": checks, "why": why}


# ---------------------------------------------------------------------- selection
def selection(registry: dict, archs=ARCHS, vrams=VRAMS, rams=RAMS,
              ids: dict | None = None, ranker=None, trend=None) -> dict:
    """The trending list per card, and whether each row names the fastest fitting server.

    Pure: `trend_list()` and `rank_engines()` are the product's own rules, read from the
    vendored store and the committed engine params. No Hub, no model, no network.

    `ranker` / `trend` default to `model_engine_pick`'s own functions. They are parameters so a
    test can hand this checker an ORDER THAT IS WRONG (the one thing this check exists to catch)
    without touching the ranking rule it is checking.
    """
    ids = mp.engine_ids() if ids is None else ids
    rank_engines = ranker or mp.rank_engines
    trend_list = trend or mp.trend_list
    cases: list[dict] = []
    for arch in archs:
        for vram in vrams:
            for ram in rams:
                models = trend_list(registry, vram, ram)
                rows, findings = [], []
                for model in models:
                    ranked = rank_engines(model, arch, ids, vram)
                    if not ranked:
                        findings.append({"kind": "no-engine", "model": model.get("id"),
                                         "detail": f"no {arch} engine image can run it"})
                        rows.append({"model": model.get("name"), "server": "", "tps": 0.0,
                                     "rank": None, "measured_on": ""})
                        continue
                    top = ranked[0]
                    same = [e for e in ranked if e["rank"] == top["rank"]]
                    best = max(same, key=lambda e: (e["tps"], e["engagement"]))
                    if best["tps"] > top["tps"]:
                        findings.append({
                            "kind": "slower-than-class", "model": model.get("id"),
                            "detail": f"{top['engine']} ({top['tps']} t/s) is named but "
                                      f"{best['engine']} measured {best['tps']} t/s on the "
                                      f"same class of hardware"})
                    elif top["tps"] <= 0:
                        findings.append({
                            "kind": "unmeasured", "model": model.get("id"),
                            "detail": f"the list names {top['engine']} with no measured t/s"})
                    rows.append({"model": model.get("name"), "server": top["engine"],
                                 "tps": top["tps"], "rank": top["rank"],
                                 "measured_on": top["measured_on"] or ""})
                if not models:
                    findings.append({"kind": "empty-tier", "model": "",
                                     "detail": "no model in the store fits this card"})
                cases.append({"arch": arch, "vram": vram, "ram": ram,
                              "rows": rows, "findings": findings})
    return {"cases": cases, "findings": [dict(case={k: c[k] for k in ("arch", "vram", "ram")},
                                              **f)
                                         for c in cases for f in c["findings"]]}


def _rev() -> str:
    """The commit the brief is reading — the sync PR's head when the job checked it out."""
    out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
    return out.stdout.strip() if out.returncode == 0 else "(unknown)"


def _store_headline(store: Path) -> dict:
    data = json.loads(store.read_text())
    matrix: dict = {}
    try:
        matrix = json.loads(MATRIX.read_text())
    except (OSError, json.JSONDecodeError):
        matrix = {}
    matrix_utc = matrix.get("generated_utc") or "(none)"
    utc = data.get("generated_utc") or "(none)"
    return {"utc": utc,
            "models": len(data.get("models") or []),
            "engines": len(data.get("engines") or {}),
            "matrix_utc": matrix_utc,
            "matrix_cases": len(matrix.get("cases") or []),
            "matrix_stale": bool(matrix) and (matrix.get("generated_utc") or None) != (utc or None)}


# ------------------------------------------------------------------------- render
def _top(rows: list[dict], n: int = 3) -> str:
    shown = [r for r in rows if r.get("server")][:n]
    if not shown:
        return "— nothing listed"
    return ", ".join(f"{r['model']} → {r['server']} ({r['tps']} t/s)" for r in shown)


def render_brief(headline: dict, pr: dict, sel: dict) -> str:
    """What the agent leg reads: the precondition, the numbers, and the table."""
    found = sel["findings"]
    kinds: dict[str, int] = {}
    for f in found:
        kinds[f["kind"]] = kinds.get(f["kind"], 0) + 1

    lines = [
        "# registry-sync review — the green store's trend list and its best server",
        "",
        "## Precondition (the sync PR)",
        "",
        f"- open `{BRANCH}` PR: {'yes — ' + pr['pr']['url'] if pr.get('pr') else 'no'}",
        f"- every check green: {'yes' if pr['green'] else 'no'}"
        + (f" ({pr['why']})" if pr["why"] else ""),
        f"- checks read: {len(pr.get('checks') or [])}",
        "",
        "## The store",
        "",
        f"- read at `{_rev()}` (the sync PR's head when the job checked it out)",
        f"- `generated_utc`: `{headline['utc']}`",
        f"- models: {headline['models']}, engines: {headline['engines']}",
        f"- trend-list matrix: `{headline['matrix_utc']}`, {headline['matrix_cases']} cases"
        + (" — **STALE vs the store** (the fixture describes an older store)"
           if headline["matrix_stale"] else ""),
        "",
        "## The VRAM selection check",
        "",
        "Per architecture and card size (RAM "
        f"{TABLE_RAM} GB; findings are collected over RAM {', '.join(str(r) for r in RAMS)}):",
        "",
    ]
    table_ram = TABLE_RAM if TABLE_RAM in RAMS else RAMS[0]
    for arch in sorted({c["arch"] for c in sel["cases"]}):
        lines.append(f"### {arch}")
        lines.append("")
        lines.append("| VRAM | listed | first rows (model → server (t/s)) |")
        lines.append("|---|---|---|")
        for case in [c for c in sel["cases"] if c["arch"] == arch and c["ram"] == table_ram]:
            n_find = len(case["findings"])
            flag = f" — {n_find} finding(s)" if n_find else ""
            lines.append(f"| {case['vram']} GB | {len(case['rows'])}{flag} | {_top(case['rows'])} |")
        lines.append("")

    lines.append("## Findings")
    lines.append("")
    if not found:
        lines.append("- none: every listed model names the fastest fitting server, "
                     "every tier lists something, and every named server has a measured t/s")
    else:
        lines.append("Counts: " + ", ".join(f"`{k}` {v}" for k, v in sorted(kinds.items())))
        lines.append("")
        # One line per (kind, model, detail): the same fact repeated over 16 cases is one defect,
        # not sixteen. The cases are counted, with one named so it can be reproduced.
        grouped: dict[tuple[str, str, str], list[str]] = {}
        for f in found:
            case = f["case"]
            key = (f["kind"], str(f["model"]), f["detail"])
            grouped.setdefault(key, []).append(f"{case['arch']}/{case['vram']}/{case['ram']}")
        for (kind, model, detail), cases in list(grouped.items())[:40]:
            lines.append(f"- `{kind}` `{model}`: {detail} "
                         f"({len(cases)} case(s), e.g. {cases[0]})")
        if len(grouped) > 40:
            lines.append(f"- … and {len(grouped) - 40} more (the full set is "
                         f"`make registry-review-brief` output over the store)")
    lines.append("")
    lines.append("## What the issue must answer")
    lines.append("")
    lines.append("- does the trend list for the cards llgenie targets actually list models at "
                 "each VRAM tier the store is sold on?")
    lines.append("- is the server named on each row the highest-t/s engine that fits that card "
                 "and that backend (the proven-class rule, #225)?")
    lines.append("- what must change in llgenie — the pick, the goldens, an engine decision — "
                 "for this store (#669, #677, #693, #687)")
    lines.append("")
    return "\n".join(lines)


def brief(store: Path, repo: str | None, branch: str, out: str | None) -> int:
    head = _store_headline(store)
    pr = sync_pr(repo, branch)
    registry = json.loads(store.read_text())
    sel = selection(registry)
    body = render_brief(head, pr, sel)
    if pr["green"]:
        # The selection table is only meaningful for a store that can land, but rendering it
        # either way costs nothing and makes a skipped run diagnosable from its log.
        text = "action=review\n" + body
    else:
        text = f"action=skip\nreason={pr['why']}\n\n" + body
    if out:
        Path(out).write_text(text + "\n")
        print(f"[registry-review] wrote {out}")
    print("action=review" if pr["green"] else "action=skip")
    print(f"reason={pr['why'] or 'the sync PR is green'}")
    print(f"findings={len(sel['findings'])}")
    print(f"utc={head['utc']}")
    return 0


# ------------------------------------------------------------------------- publish
def parse_verdict(text: str) -> tuple[str, str, str]:
    """(verdict, title-or-reason, body) from the leg's `registry-review.md`."""
    verdict, title, rest = "", "", text
    lines = text.splitlines()
    body_at = 0
    for i, line in enumerate(lines):
        if line.startswith("VERDICT:"):
            verdict = line.split(":", 1)[1].strip().lower()
        elif line.startswith("TITLE:"):
            title = line.split(":", 1)[1].strip()
        elif line.startswith("REASON:"):
            title = line.split(":", 1)[1].strip()
        elif line.startswith("#"):
            body_at = i
            break
        else:
            continue
        body_at = i + 1
    rest = "\n".join(lines[body_at:]).strip()
    return verdict, title, rest


def publish(body: str, title: str, utc: str, repo: str | None, dry: bool = False) -> str:
    """ONE issue for this store: create it, or update the one already carrying its marker."""
    marker = MARKER.format(utc=utc)
    body = f"{body}\n\n{marker}\n"
    base = ["--repo", repo] if repo else []
    listing = json.loads(run_gh(["issue", "list", *base, "--state", "open", "--limit", "100",
                                 "--json", "number,body,title"]))
    for issue in listing:
        if marker in (issue.get("body") or ""):
            if dry:
                return f"would update #{issue['number']}"
            run_gh(["issue", "edit", str(issue["number"]), *base, "--body", body])
            return f"updated #{issue['number']}"
    change = CHANGE_MARKER.format(utc=utc)
    linked = next((i["number"] for i in listing if change in (i.get("body") or "")), None)
    if dry:
        return "would create one issue" + (f" (linked to #{linked})" if linked else "")
    full = (body + f"\nThe store's change report is #{linked}.\n") if linked else body
    url = run_gh(["issue", "create", *base, "--title", title, "--label", LABEL,
                  "--body", full]).strip()
    return url


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=("" if __doc__ is None else __doc__).split("\n")[0])
    ap.add_argument("cmd", choices=("brief", "publish"))
    ap.add_argument("--repo")
    ap.add_argument("--branch", default=BRANCH)
    ap.add_argument("--store", default=str(STORE))
    ap.add_argument("--out")
    ap.add_argument("--in", dest="infile", default="registry-review.md")
    ap.add_argument("--utc")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args(argv)

    if a.cmd == "brief":
        return brief(Path(a.store), a.repo, a.branch, a.out)

    path = Path(a.infile)
    if not path.exists():
        print(f"[registry-review] {path} is missing — the agent leg wrote nothing", file=sys.stderr)
        return 2
    verdict, title, body = parse_verdict(path.read_text())
    if verdict != "review":
        print(f"[registry-review] verdict={verdict or '(none)'} — nothing to file "
              f"({title or 'no reason given'})")
        return 0
    if not body:
        print(f"[registry-review] verdict=review with no body in {path}", file=sys.stderr)
        return 2
    utc = a.utc or _store_headline(Path(a.store))["utc"]
    title = title or f"{TITLE_PREFIX} the {utc} store's trend list"
    print(f"[registry-review] {publish(body, title, utc, a.repo, a.dry)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
