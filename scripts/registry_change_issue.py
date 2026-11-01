#!/usr/bin/env python3
"""State what changed in the vendored registry, and open ONE issue about it (issue #704).

  registry_change_issue.py report [--prev-rev REV] [--out FILE]
  registry_change_issue.py open   [--prev-rev REV] [--repo OWNER/REPO] [--dry]

`report` compares the PREVIOUS store — `git show <rev>:data/…`, which is the registry the
repository currently carries — with the working tree's, and renders a markdown body in the
shape this repository's issues use. `open` files one issue labelled `agent:implement` that
carries a marker for the store's `generated_utc`; a later run for the same store UPDATES
that issue instead of opening a second one.

No model is in this path: the diff is the artefact, and this is its index. The judgement —
which contract key to read, which golden to re-derive, which new engine to ship or defer —
belongs to the agent that picks the issue up (#677/#693/#673).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import issue_body  # noqa: E402  (the one issue shape, #745)

REPO = Path(__file__).resolve().parent.parent
STORE = "data/models.json"
CONTRACT = "data/model_contract.json"
README = "data/trending-README.md"
CATALOG = "data/trending-quant-catalog.json"
MATRIX = "tests/fixtures/trend-list-matrix.json"
GAP = "data/engine-skill-gap.json"
FILES = (STORE, CONTRACT, README, CATALOG, MATRIX, GAP)
MARKER = "<!-- registry-sync-changes: {utc} -->"
LABEL = "agent:implement"


def _git_show(rev: str, path: str) -> bytes | None:
    """The file at `rev`, or None when it does not exist there."""
    out = subprocess.run(["git", "show", f"{rev}:{path}"], capture_output=True)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
    return out.stdout if out.returncode == 0 else None


def _read(path: str, rev: str | None) -> bytes | None:
    """The working tree's file when `rev` is None, else the file at that revision."""
    if rev is None:
        p = REPO / path
        return p.read_bytes() if p.exists() else None
    return _git_show(rev, path)


def _json(raw: bytes | None) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _readme_rows(raw: bytes | None) -> list[str]:
    """The model names of the README "Most loved" table, in order."""
    import re
    if not raw:
        return []
    text = raw.decode("utf-8", "replace")
    if "## ❤️ Most loved" not in text:
        return []
    section = text.split("## ❤️ Most loved", 1)[1].split("\n## ", 1)[0]
    return re.findall(r"^\| \[\*\*(.+?)\*\*\]", section, re.M)


def _formats(store: dict) -> set[str]:
    return {str(f.get("name")) for m in store.get("models") or []
            for f in m.get("formats") or []}


def _required(schema: dict, *path: str) -> list[str]:
    node = schema
    for key in path:
        node = (node or {}).get(key) or {}
    return list(node.get("required") or [])


def _enum(schema: dict, *path: str) -> list[str]:
    node = schema
    for key in path:
        node = (node or {}).get(key) or {}
    return list(node.get("enum") or [])


def compare(prev: dict[str, bytes | None], cur: dict[str, bytes | None]) -> dict:
    """The facts that changed between two snapshots of the six files."""
    ps, cs = _json(prev.get(STORE)), _json(cur.get(STORE))
    pc, cc = _json(prev.get(CONTRACT)), _json(cur.get(CONTRACT))
    pm = {m.get("id"): m for m in ps.get("models") or []}
    cm = {m.get("id"): m for m in cs.get("models") or []}
    pe, ce = set(ps.get("engines") or {}), set(cs.get("engines") or {})
    prow, crow = _readme_rows(prev.get(README)), _readme_rows(cur.get(README))
    row_req = ("properties", "models", "items")
    facts = {
        "utc_before": ps.get("generated_utc", "(none)"),
        "utc_after": cs.get("generated_utc", "(none)"),
        "models_before": len(pm), "models_after": len(cm),
        "engines_before": len(pe), "engines_after": len(ce),
        "added_models": [{"id": i, "name": cm[i].get("name"), "vram_tier": cm[i].get("vram_tier")}
                         for i in sorted(set(cm) - set(pm))],
        "removed_models": sorted(set(pm) - set(cm)),
        "renamed_models": [{"id": i, "was": pm[i].get("name"), "now": cm[i].get("name")}
                           for i in sorted(set(pm) & set(cm))
                           if pm[i].get("name") != cm[i].get("name")],
        "new_engines": sorted(ce - pe),
        "gone_engines": sorted(pe - ce),
        "formats_before": sorted(_formats(ps)), "formats_after": sorted(_formats(cs)),
        "contract_changed": prev.get(CONTRACT) != cur.get(CONTRACT),
        "row_required_added": sorted(set(_required(cc, *row_req)) - set(_required(pc, *row_req))),
        "row_required_removed": sorted(set(_required(pc, *row_req)) - set(_required(cc, *row_req))),
        "backend_enum_added": sorted(set(_enum(cc, "properties", "engines", "additionalProperties",
                                               "properties", "backend"))
                                     - set(_enum(pc, "properties", "engines", "additionalProperties",
                                                 "properties", "backend"))),
        "readme_rows_before": len(prow), "readme_rows_after": len(crow),
        "readme_added": [n for n in crow if n not in prow][:20],
        "readme_removed": [n for n in prow if n not in crow][:20],
        "catalog": _catalog_counts(cur.get(CATALOG)),
        "catalog_before": _catalog_counts(prev.get(CATALOG)),
        "matrix_cases": len(_json(cur.get(MATRIX)).get("cases") or _json(cur.get(MATRIX)) or []),
        "unresolved_engines": len(_json(cur.get(GAP)).get("unresolved") or []),
        "changed": {p for p in FILES if prev.get(p) != cur.get(p)},
    }
    return facts


def _catalog_counts(raw: bytes | None) -> dict:
    data = _json(raw)
    models = data.get("files") or {}
    links = sum(len(cell.get("quants") or []) for engs in models.values() if isinstance(engs, dict)
                for cell in engs.values() if isinstance(cell, dict))
    return {"models": len(models), "links": links}


#: How many rows of one kind the issue body lists before it stops and points at the diff.
LIST_CAP = 40


def _bullet(items, empty="none", cap: int = LIST_CAP) -> str:
    if not items:
        return f"- {empty}"
    shown = list(items)[:cap]
    out = "\n".join(f"- {i}" for i in shown)
    if len(items) > cap:
        out += f"\n- … and {len(items) - cap} more (the full set is the `{STORE}` diff)"
    return out


def render(f: dict) -> str:
    """The issue body: the shape every issue in this repository carries (issue #745).

    The measured detail ("what changed") is `## Technical`, where a reviewer verifies it; the four
    readable sections say what happened, why llgenie has to follow it, what the steps are and what
    landing it buys.
    """
    added = [f"`{m['id']}` — {m['name']} (VRAM {m['vram_tier']})" for m in f["added_models"]]
    renamed = [f"`{m['id']}`: {m['was']!r} -> {m['now']!r}" for m in f["renamed_models"]]
    work = []
    if f["added_models"] or f["removed_models"]:
        work.append("**Re-derive the trend/pick goldens** for the new row set (#693, #677) — they "
                    "read the store's rows, so an added or removed model reds them.")
    if f["new_engines"]:
        work.append("**Decide each new engine**: ship a skill, or record a dated decision in "
                    "`data/unsupported-engines.json` (#673/#686). `make check-engine-skill-gap` "
                    "refuses the store until then.")
    if f["row_required_added"] or f["backend_enum_added"]:
        work.append("**Teach llgenie's contract reader** the new field/enum value, then let "
                    "`make check-registry` validate it (#694 vendored the contract).")
    if f["formats_after"] != f["formats_before"]:
        work.append("**Check the formats vocabulary** the pick resolves downloads from "
                    "(#687/#692) — the normaliser narrows it on the way in.")
    work.append("**Run the job's gates on the synced files**: `make check-registry`, "
                "`check-registry-keys`, `check-quant-catalog`, `check-trend-list-matrix`, "
                "`skills-validate REGISTRY=data/models.json UNSUPPORTED=data/unsupported-engines.json`, "
                "`check-engine-skill-gap`, then `make test-unit`.")

    technical = [
        f"models: **{f['models_before']} -> {f['models_after']}**, engines: "
        f"**{f['engines_before']} -> {f['engines_after']}**",
        f"quant catalog: {f['catalog_before']['models']} models / {f['catalog_before']['links']} "
        f"links -> **{f['catalog']['models']} / {f['catalog']['links']}**",
        f"trend-list matrix cases: {f['matrix_cases']}; unresolved engines in the skill gap: "
        f"{f['unresolved_engines']}",
        "files changed: " + (", ".join('`' + p + '`' for p in sorted(f['changed'])) or "none"),
        f"### Models added ({len(f['added_models'])})",
        _bullet(added),
        f"### Models removed ({len(f['removed_models'])})",
        _bullet(['`' + i + '`' for i in f['removed_models']]),
        f"### Renamed ({len(f['renamed_models'])})",
        _bullet(renamed),
        f"### Engines new to the registry ({len(f['new_engines'])})",
        _bullet(['`' + e + '`' for e in f['new_engines']]),
        f"### Contract ({'changed' if f['contract_changed'] else 'unchanged'})",
        f"required keys added per model row: {f['row_required_added'] or 'none'}",
        f"required keys removed per model row: {f['row_required_removed'] or 'none'}",
        f"engine `backend` values added: {f['backend_enum_added'] or 'none'}",
        f"### README \"Most loved\" ({f['readme_rows_before']} -> {f['readme_rows_after']} rows)",
        _bullet(['added: ' + n for n in f['readme_added']] + ['removed: ' + n for n in f['readme_removed']]),
        f"measured against `{f.get('prev_rev', 'HEAD')}`",
    ]

    return issue_body.render(
        problem=(
            f"The weekly `registry-sync` produced a new vendored registry — `generated_utc` "
            f"`{f['utc_before']}` -> `{f['utc_after']}` — and llgenie is still built to the old one: "
            f"the trend list, the pick, the contract it validates against and the tests that pin the "
            f"old rows were all derived from the previous store."
        ),
        why=(
            "`data/models.json` is the data every offer reads, so a store that has moved and a "
            "llgenie that has not is a product quietly answering from yesterday's catalogue: new "
            "models are never offered, an engine nobody taught it about stays unranked, and the "
            "golden tests keep passing against rows upstream has already replaced. Nothing fails "
            "until someone notices a model missing."
        ),
        how=work,
        benefit=(
            "llgenie follows the store upstream actually published: the new models are offered, "
            "every new engine is either shipped or refused with a dated reason, and the tests pin "
            "the current row set instead of the one from last week."
        ),
        acceptance=[
            "`make check-registry check-registry-keys check-quant-catalog check-trend-list-matrix` "
            "are green on the synced files",
            "`make skills-validate REGISTRY=data/models.json "
            "UNSUPPORTED=data/unsupported-engines.json` and `make check-engine-skill-gap` are green "
            "(each new engine shipped or decided)",
            "`make test-unit` is green with the goldens re-derived for the new row set",
            "the sync PR that carries this store merges, so the next weekly run starts from it",
        ],
        technical=technical,
        not_covered=[
            "the ranking rule the trend list is built on is its own decision (#669): this issue "
            "reports the data, it does not choose the gate.",
            "the sync PR itself: it opens when the job's own gates pass; this issue exists whether "
            "it does or not, and it is what the landing change is written from.",
        ],
    )


def _title(utc: str) -> str:
    return f"sync: review the {utc} trending registry (llgenie must follow the new store)"


def run_gh(args: list[str]) -> str:
    """`gh` is the external system; tests replace this function."""
    out = subprocess.run(["gh", *args], capture_output=True, text=True)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
    if out.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {out.stderr.strip()}")
    return out.stdout


def repo_slug(repo: str | None) -> str:
    """`owner/name` — `gh api` paths carry the repository, so it must be spelled out."""
    if repo:
        return repo
    return run_gh(["repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"]).strip()


def _gh_api(args: list[str]) -> str:
    """`gh api` takes no `--repo`; the path carries the repository."""
    return run_gh(["api", *args])


def labels_of(repo: str, number: int) -> list[str]:
    """The labels the issue ACTUALLY carries, read back from the tracker.

    Read over the same REST endpoint the write uses. `gh issue view --json labels` goes the
    GraphQL way, and a read on the other transport can agree with a write that never happened.
    """
    out = _gh_api([f"repos/{repo}/issues/{number}/labels", "--jq", ".[].name"])
    return [line.strip() for line in (out or "").splitlines() if line.strip()]


def set_labels(repo: str, number: int, labels: list[str]) -> None:
    """Label the issue through the REST API and PROVE it stuck, or fail the step.

    `--label` on `gh issue create` is silently dropped on the runner's PAT (#724: issues #710
    and #749 were filed with zero labels, and no `labeled` event exists in their timelines), so
    the create flag is not a write. The POST is the write; the read-back decides. An unlabelled
    change issue is invisible to every bot that selects on `agent:implement`, which looks exactly
    like a green step — hence SystemExit, naming the issue and the missing label.
    """
    args = ["-X", "POST", f"repos/{repo}/issues/{number}/labels"]
    for label in labels:
        args += ["-f", f"labels[]={label}"]
    _gh_api(args)
    have = labels_of(repo, number)
    missing = [label for label in labels if label not in have]
    if missing:
        raise SystemExit(
            f"[registry-change] #{number} is missing {', '.join(missing)} after the label write — "
            "an unlabelled change issue routes the store review to nobody, so the step fails")


def open_issue(body: str, utc: str, repo: str | None, dry: bool = False) -> str:
    """Create ONE issue for this store, or update the open one carrying its marker."""
    marker = MARKER.format(utc=utc)
    body = f"{body}\n\n{marker}\n"
    title = _title(utc)
    base = ["--repo", repo] if repo else []
    listing = json.loads(run_gh(["issue", "list", *base, "--state", "open", "--limit", "100",
                                 "--json", "number,body"]))
    for issue in listing:
        if marker in (issue.get("body") or ""):
            if dry:
                return f"would update #{issue['number']}"
            run_gh(["issue", "edit", str(issue["number"]), *base, "--body", body])
            # An issue that carries the marker but lost its label is re-queued, not skipped: a
            # re-run after a dropped write is how the store review gets back to the bots (#724).
            if LABEL not in labels_of(repo_slug(repo), issue["number"]):
                set_labels(repo_slug(repo), issue["number"], [LABEL])
            return f"updated #{issue['number']}"
    if dry:
        return "would create one issue"
    # No `--label`: it is dropped on the runner path, so the issue would be filed invisible.
    url = run_gh(["issue", "create", *base, "--title", title, "--body", body]).strip()
    number = url.rstrip("/").rsplit("/", 1)[-1]
    if not number.isdigit():
        raise SystemExit(f"[registry-change] the created issue returned no number ({url!r}); "
                         "it cannot be labelled or linked")
    set_labels(repo_slug(repo), int(number), [LABEL])
    return url


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=("report", "open"))
    ap.add_argument("--prev-rev", default="HEAD")
    ap.add_argument("--out")
    ap.add_argument("--repo")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args(argv)

    prev = {p: _read(p, a.prev_rev) for p in FILES}
    cur = {p: _read(p, None) for p in FILES}
    if prev[STORE] is None:
        print(f"[registry-change] {a.prev_rev}:{STORE} does not exist — nothing to compare "
              f"(a first import is not a change)", file=sys.stderr)
        return 0
    if prev[STORE] == cur[STORE] and prev[CONTRACT] == cur[CONTRACT] \
            and prev[README] == cur[README]:
        print("[registry-change] the store, contract and README are unchanged — no issue")
        return 0

    facts = compare(prev, cur)
    facts["prev_rev"] = a.prev_rev
    body = render(facts)
    if a.out:
        Path(a.out).write_text(body)
        print(f"[registry-change] wrote {a.out}")
    if a.cmd == "report":
        if not a.out:
            print(body)
        return 0
    utc = facts["utc_after"]
    print(f"[registry-change] {open_issue(body, utc, a.repo, a.dry)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
