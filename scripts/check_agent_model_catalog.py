#!/usr/bin/env python3
"""check_agent_model_catalog — the weekly catalog check for the Hermes model chain (issue #2930).

Why: `agents/hermes-base-config.yaml` pins the five `:free` members of the Hermes model
chain (issue #2929) by catalog id, with `context_window` budgets copied from the catalog's
published `context_length`. A synthesized free variant can leave the catalog, or its
published length can change, and then every bot leg whose primary or fallback hops to that
alias fails at 404 with no alarm. This check reads the chain from the config, GETs the
catalog, and says so.

Measured 2026-11-19 (issue #2930): `GET https://inference-api.nousresearch.com/v1/models`
answers HTTP 200 WITHOUT any auth header (413 model objects; each carries `id` and
`context_length`). The check therefore reads no credential and sends no Authorization
header — no secret can leak from a lane step that never touches one.

Exit codes:
  0  every declared member is listed AND its budget matches the published context_length
  1  findings: the ONE deduped issue was updated or filed (or would have been, --dry-run)
  3  the catalog could not be read: nothing is filed on a transport failure

Filing follows the repository producer idioms: the marker is the body's first line
(issue_body.render), dedupe searches OPEN issue bodies rather than a page scan (#2848),
the body write is REST PATCH with a read-back (#2673), and the label write is proven by a
read-back (#724). `gh` is the external system; tests replace `run_gh`.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import issue_body  # noqa: E402  (the ONE issue shape, #745)
import proc  # noqa: E402  (the ONE subprocess policy seam, issue #797)

REPO_ROOT = HERE.parent
CONFIG_PATH = REPO_ROOT / "agents" / "hermes-base-config.yaml"
CATALOG_URL = "https://inference-api.nousresearch.com/v1/models"
MARKER = "<!-- agent-model-catalog-check: chain-membership -->"
LABEL = "agent:implement"
USER_AGENT = "llgenie-agent-model-catalog-check/1.0 (issue #2930)"

TITLE = ("chore(agent-model): a Hermes model chain member left the Nous catalog "
         "or its budget drifted")


def run_gh(args: list[str]) -> str:
    """`gh` is the external system; tests replace this function."""
    return proc.run_text(["gh", *args], timeout=60)


def repo_slug(repo: str | None) -> str:
    if repo:
        return repo
    return run_gh(["repo", "view", "--json", "nameWithOwner",
                   "--jq", ".nameWithOwner"]).strip()


def chain_members(config_path: Path = CONFIG_PATH) -> dict[str, dict]:
    """Every model id the base config declares, with its committed budget(s).

    The chain is read from the config itself (the referee, issue #2929): the `model:`
    block's `default`, every `model.aliases.*` entry, and every `fallback_providers`
    entry. Ids are deduped; a budget disagreement INSIDE the config is a finding too —
    two budgets for one id mean the chain no longer states one intent.
    """
    import yaml  # noqa: PLC0415  (lazy per apply_hermes_base_config.py)
    doc = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise SystemExit(f"[agent-model-catalog] {config_path} does not parse to a mapping")
    members: dict[str, dict] = {}

    def add(entry: dict, source: str) -> None:
        mid = entry.get("model") or entry.get("default")
        if not mid:
            return
        slot = members.setdefault(str(mid), {"sources": [], "budgets": []})
        slot["sources"].append(source)
        budget = entry.get("context_window")
        if budget is not None:
            slot["budgets"].append((source, int(budget)))

    model = doc.get("model") or {}
    add(model, "model:")
    for name, alias in (model.get("aliases") or {}).items():
        add(alias, f"alias {name}")
    for entry in (doc.get("fallback_providers") or []):
        add(entry, "fallback_providers")
    if not members:
        raise SystemExit(f"[agent-model-catalog] {config_path} declares no model ids — "
                         "the check would pass vacuously, so it refuses to")
    return members


def fetch_catalog(url: str) -> list[dict]:
    """The public catalog list. No auth header is sent (measured 2026-11-19: 200 without one)."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise SystemExit(f"[agent-model-catalog] the catalog at {url} could not be read "
                         f"({exc}); a transport failure files nothing — nothing here is stale news")
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        raise SystemExit(f"[agent-model-catalog] the catalog payload carries no `data` list; "
                         "the check refuses to declare an unreadable catalog clean")
    return data


def compare(members: dict[str, dict], catalog_models: list[dict]) -> list[str]:
    """Return finding lines (empty == green), printing one line per member."""
    catalog = {str(m["id"]): m for m in catalog_models
               if isinstance(m, dict) and m.get("id")}
    free_candidates = sorted(mid for mid in catalog if mid.endswith(":free"))
    findings: list[str] = []
    for mid, info in sorted(members.items()):
        budgets = sorted({b for _, b in info["budgets"]})
        if len(budgets) > 1:
            findings.append(f"FINDING: {mid} carries conflicting context_window budgets "
                            f"in the config: {budgets} ({', '.join(info['sources'])})")
        budget = budgets[0] if budgets else None
        entry = catalog.get(mid)
        if entry is None:
            findings.append(f"FINDING: {mid} ({', '.join(info['sources'])}) is not in the "
                            f"catalog; current :free candidates: {', '.join(free_candidates)}")
            continue
        published = entry.get("context_length")
        if budget is not None and published is not None and int(published) != budget:
            findings.append(f"FINDING: {mid} budget {budget} != published context_length "
                            f"{published}")
            continue
        print(f"member {mid}: listed; budget {budget} matches published "
              f"context_length {published}")
    for line in findings:
        print(line)
    return findings


def issue_text(findings: list[str], members: dict[str, dict],
               catalog_models: list[dict], utc: str) -> str:
    catalog = [str(m["id"]) for m in catalog_models if isinstance(m, dict) and m.get("id")]
    free_candidates = sorted(mid for mid in catalog if mid.endswith(":free"))
    names = [line.removeprefix("FINDING: ").split(" (")[0] for line in findings]
    return issue_body.render(
        problem=("The Hermes model chain installed in every agent image "
                 "(`agents/hermes-base-config.yaml`, issue #2929) pins catalog ids whose "
                 "live catalog membership is not checked anywhere. This run found "
                 f"{len(findings)} drift(s): " + "; ".join(findings)),
        why=("A chain member that left the catalog makes every bot leg that hops to its "
             "alias fail at 404. Today that is discovered by watching a bot fail, not by "
             "the weekly lane that already reads this catalog family. A budget drift "
             "(committed context_window != published context_length) mis-sizes sessions "
             "the same way a removed member mis-routes them."),
        how=["Re-pin the affected member(s) in agents/hermes-base-config.yaml to a live "
             "catalog model (the current :free ids are listed below as candidates),",
             "run make apply-hermes-base-config --all so every profile home AND the agent "
             "image build re-read the chain,",
             "confirm make check-agent-model-catalog exits 0 against the live catalog."],
        benefit=("Chain membership stops rotting silently: the weekly registry-sync lane "
                 "files this issue the moment a member or budget drifts, and the agent "
                 "re-pins before a bot leg pays the 404."),
        acceptance=["Re-pin or restore every named member and prove "
                    "`make check-agent-model-catalog` exits 0 (proven: the command's rc "
                    "on the fixed tree, or the next weekly registry-sync run carrying it "
                    "green)",
                    "the agent image rebuilds with the re-pinned chain (proven: "
                    "`make agent-image-profiles-check` rc=0 on the fixed tree)"],
        technical=[f"Producer: scripts/check_agent_model_catalog.py (make check-agent-model-catalog).",
                   f"Measured {utc}: {len(catalog)} models in {CATALOG_URL}; the :free "
                   f"catalog ids: {', '.join(free_candidates)}",
                   f"Named by this run: {', '.join(names)}",
                   f"Declared chain ids ({len(members)}): {', '.join(sorted(members))}"],
        marker=MARKER,
    )


def marker_issue(marker: str, slug: str) -> int | None:
    """The OPEN issue carrying this marker, by body SEARCH — never a page scan (#2848)."""
    needle = marker.removeprefix("<!-- ").removesuffix(" -->")
    try:
        hits = json.loads(run_gh(["api", "-X", "GET", "search/issues",
                                  "-f", f'q=repo:{slug} "{needle}" in:body state:open']))
    except (RuntimeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"[agent-model-catalog] the dedupe search for {needle!r} failed "
                         f"({exc}); the filer cannot read its own filing memory, so it "
                         "files nothing blind (#2848)")
    for number in sorted(int(h["number"]) for h in (hits.get("items") or [])
                         if "pull_request" not in h):
        body = run_gh(["api", f"repos/{slug}/issues/{number}", "--jq", ".body"])
        if marker in (body or ""):
            return number
    return None


def edit_body(slug: str, number: int, body: str) -> bool:
    """REST PATCH + exact read-back (#2673/#819 idiom); False only on a refused write."""
    path = f"repos/{slug}/issues/{number}"
    try:
        run_gh(["api", "-X", "PATCH", path, "-f", f"body={body}"])
    except RuntimeError as exc:
        if "not accessible" in str(exc) or "HTTP 403" in str(exc):
            print(f"[agent-model-catalog] #{number} body write REFUSED by the credential "
                  f"over {path} ({exc}); the issue keeps its previous body.", file=sys.stderr)
            return False
        raise
    after = run_gh(["api", path, "--jq", ".body"])
    if (after or "").strip() != body.strip():
        raise SystemExit(f"[agent-model-catalog] #{number} body read-back is not the body "
                         "this write sent — a body write that claims success but never "
                         "stuck leaves the finding invisible, so the step fails")
    return True


def set_label(slug: str, number: int, label: str) -> None:
    """POST the label and PROVE it stuck by reading it back (#724 idiom)."""
    try:
        run_gh(["api", "-X", "POST", f"repos/{slug}/issues/{number}/labels",
                "-f", f"labels[]={label}"])
    except RuntimeError as exc:
        if "not accessible" in str(exc) or "HTTP 403" in str(exc):
            print(f"[agent-model-catalog] #{number} label write refused ({exc}) — the "
                  f"issue is filed but carries no {label}; a token that can write labels "
                  "must queue it.", file=sys.stderr)
            return
        raise
    have = run_gh(["api", f"repos/{slug}/issues/{number}/labels", "--jq", ".[].name"])
    if label not in [line.strip() for line in (have or "").splitlines()]:
        raise SystemExit(f"[agent-model-catalog] #{number} is missing {label} after the "
                         "label write — an unlabelled finding routes the fix to nobody")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="check the Hermes model chain against the Nous model catalog (issue #2930)")
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--catalog", type=Path, default=None,
                        help="read the catalog payload from this JSON file instead of the network")
    parser.add_argument("--url", default=CATALOG_URL)
    parser.add_argument("--repo", default=None, help="owner/name (default: the tracked repo)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the would-be issue body; file nothing")
    args = parser.parse_args(argv)

    members = chain_members(args.config)
    print(f"[agent-model-catalog] {args.config.name} declares {len(members)} chain model ids")
    if args.catalog:
        models = fetch_catalog_from_file(args.catalog)
    else:
        models = fetch_catalog(args.url)
    findings = compare(members, models)
    if not findings:
        print("[agent-model-catalog] catalog check: OK — every chain member is listed "
              "with a matching budget")
        return 0

    utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    body = issue_text(findings, members, models, utc)
    if args.dry_run:
        print("[agent-model-catalog] findings; --dry-run prints the body and files nothing:")
        print(body)
        return 1

    slug = repo_slug(args.repo)
    found = marker_issue(MARKER, slug)
    if found is not None:
        outcome = f"updated #{found}" if edit_body(slug, found, body) else f"update refused for #{found}"
    else:
        url = run_gh(["issue", "create", "--repo", slug, "--title", TITLE,
                      "--body", body]).strip()
        number = url.rstrip("/").rsplit("/", 1)[-1]
        if not number.isdigit():
            raise SystemExit(f"[agent-model-catalog] the created issue returned no number "
                             f"({url!r}); the filing is unverifiable")
        set_label(slug, int(number), LABEL)
        outcome = f"filed #{number}"
    print(f"[agent-model-catalog] {len(findings)} finding(s) -> {outcome}")
    return 1


def fetch_catalog_from_file(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        raise SystemExit(f"[agent-model-catalog] {path} carries no `data` list")
    return data


if __name__ == "__main__":
    sys.exit(main())
