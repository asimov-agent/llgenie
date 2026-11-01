#!/usr/bin/env python3
"""The unskilled-engine gap: which registry engines llgenie cannot serve, why, and
which models that hides (issue #229).

  engine_skill_gap.py report [--registry F|URL] [--unsupported F] [--json|--md]
  engine_skill_gap.py render [--registry F|URL] [--unsupported F]      write data/engine-skill-gap.json
  engine_skill_gap.py check  [--registry F|URL] [--unsupported F]      the CI gate (exit 1)
  engine_skill_gap.py spawn  [--registry F|URL] [--repo O/R] [--gh CMD] [--dry]

`registry-sync` copies **every** engine upstream lists. An engine with no
`skills/engines/<id>/SKILL.md` has no `containers/engines/params/<id>.json` and no
image, so `rank_engines` drops it and every model served only by it disappears from
the trend offer — silently. This script makes that gap explicit:

- **a dated decision** in `data/unsupported-engines.json` is what makes an omission
  *deliberate* (`not-shipped`: llgenie will not ship it; `deferred`: accepted work);
- anything else is a **new, unresolved** engine: `check` fails and names it, and
  `spawn` opens ONE tracking issue per unresolved engine so the sync leaves a
  visible, linkable work item instead of a log line;
- the **models whose only engines are unskilled** are enumerated — they can never be
  offered, so no model vanishes without being named;
- the per-engine list (`engines{}` in the rendered file) is the inverse view: each
  engine's image variants, the models that list it, and the models it is the
  top-ranked engine for, per architecture.

`render` writes the committed `data/engine-skill-gap.json`; `make
check-engine-skill-gap` fails when it is stale (a sync that forgot the rewrite) or
when an engine is unresolved. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import engine_skills as es  # noqa: E402
from issue_body import render as render_body  # noqa: E402  (the one issue shape, #745; the
#   local ``issue_body()`` keeps its published name, so the renderer is imported under another one)
import model_engine_pick as mp  # noqa: E402

GAP_FILE = REPO / "data" / "engine-skill-gap.json"
UNSUPPORTED_FILE = REPO / "data" / "unsupported-engines.json"
ARCHS = ("cuda", "rocm", "vulkan", "metal", "cpu")
ISSUE_LABEL = "bug"
# The label that puts the issue in the queue `scripts/issue_implementer.py` reads
# (`agent:implement` first, then `agent:ready`). Without it a spawned tracking issue is
# a dead end: the sync's only automation would be "file work" and the skill would still
# wait for a human to notice (#757). It is set EXPLICITLY after the create and read back,
# because `gh issue create --label` has been measured to be dropped on the CI token path
# (#724) — the issue existing and the issue being labelled are two different facts.
QUEUE_LABEL = "agent:implement"


def _model_engines(model: dict) -> list[str]:
    """Every engine name the registry lists for a model: measurements + supported."""
    return sorted({e["engine"] for e in model.get("engines") or []}
                  | set(model.get("supported_engines") or []))


def _variants_by_name(ids: dict) -> dict:
    """Registry engine name -> the image variants llgenie ships for it."""
    return {name: list(info.get("variants") or []) for name, info in ids.items()}


def inventories(registry_src: str | None = None,
                unsupported_src: str | None = None) -> tuple[dict, dict, dict]:
    """(registry, skills, unsupported decisions) — the real files, no stand-ins."""
    return (mp.load_registry(registry_src), es.load_skills(),
            es.load_unsupported(unsupported_src or UNSUPPORTED_FILE))


def gap(registry: dict, skills: dict, unsupported: dict, archs=ARCHS) -> dict:
    """The whole gap, computed from the real registry + skills + dated decisions.

    The product's offer rule is `engine_ids()`: an engine with no image variant is
    dropped by `rank_engines`, whether llgenie has no skill for it or the skill
    ships no image at all (`servable: false` / `via`, a drafter or a browser
    library). ``models_never_offered`` is exactly the set of models no cell can
    ever be produced for, so none of them can vanish unnoticed.

    ``engines`` is the per-engine (inference server) list: status, image variants,
    whether it is served through other engines, the models that list it, and the
    models it is the top-ranked engine for on each architecture (``rank_engines``,
    the product's own ranking — no Hub call).
    """
    reg_engines = registry.get("engines") or {}
    by_engine = {s.get("engine"): s for s in skills.values()}
    shipped_names = set(by_engine)
    decisions = unsupported.get("engines") or {}
    ids = mp.engine_ids()
    variants = _variants_by_name(ids)

    shipped = sorted(n for n in reg_engines if n in shipped_names)
    # A skill with no image is deliberate (a drafter, a benchmark harness, a browser
    # library) but it is still not servable by rank_engines. So is an engine whose only
    # image variants are disabled (#103): engine_ids() keeps the name with no variant,
    # and rank_engines drops it. "Has an image" is therefore the variants being non-empty.
    imageless = sorted(n for n in shipped if not variants.get(n))
    known = [{"engine": n, "decision": decisions[n]["decision"], "decided": decisions[n]["decided"],
              "reason": decisions[n]["reason"], "issue": decisions[n].get("issue")}
             for n in sorted(reg_engines) if n not in shipped_names and n in decisions]
    unresolved = sorted(n for n in reg_engines if n not in shipped_names and n not in decisions)
    unskilled = {e["engine"] for e in known} | set(unresolved)
    stale = [{"engine": n, "why": ("it ships a skill now" if n in shipped_names
                                   else "the registry no longer names it")}
             for n in sorted(decisions) if n in shipped_names or n not in reg_engines]

    models = list(registry.get("models") or [])
    listing = {n: [m["id"] for m in models if n in _model_engines(m)] for n in reg_engines}
    never_offered, touching = [], []
    for m in models:
        names = _model_engines(m)
        if not names:
            continue
        if not any(variants.get(n) for n in names):
            never_offered.append({"id": m["id"], "name": m["name"], "engines": names})
        elif set(names) & unskilled:
            touching.append({"id": m["id"], "name": m["name"], "engines": names,
                             "unsupported": sorted(set(names) & unskilled)})

    engines = {}
    for name in sorted(reg_engines):
        spec = reg_engines[name] if isinstance(reg_engines[name], dict) else {}
        entry = {"status": ("shipped" if name in shipped_names
                            else ("known-unsupported" if name in decisions else "unresolved")),
                 "backends": sorted({str(spec.get(key)).upper() for key in ("backend",)
                                     if spec.get(key)}),
                 "url": spec.get("url") or "",
                 "image": bool(variants.get(name)),
                 "variants": variants.get(name, []),
                 "models": listing[name],
                 "top_engine": {a: [m["id"] for m in models
                                    if (rows := mp.rank_engines(m, a, ids)) and rows[0]["engine"] == name]
                                for a in archs}}
        if name in ids:
            entry["id"] = (ids.get(name) or {}).get("id", "")
        skill = by_engine.get(name) or {}
        if skill.get("servable") == "via":
            entry["served_via"] = list(skill.get("via") or [])
        if name in decisions:
            entry.update({"decision": decisions[name]["decision"], "decided": decisions[name]["decided"],
                          "reason": decisions[name]["reason"], "issue": decisions[name].get("issue")})
        engines[name] = entry

    return {
        "generated_utc": registry.get("generated_utc", ""),
        "registry_engines": len(reg_engines),
        "skills": len({s.get("id") for s in skills.values()}),
        "shipped": shipped,
        "imageless_skills": imageless,
        "known_unsupported": known,
        "unresolved": unresolved,
        "stale_decisions": stale,
        "models_never_offered": never_offered,
        "models_touching_unsupported": touching,
        "engines": engines,
    }


def _summary(g: dict) -> str:
    return (f"registry {g['registry_engines']} engines, {g['skills']} skills; shipped {len(g['shipped'])} "
            f"({len(g['imageless_skills'])} with no image), known-unsupported {len(g['known_unsupported'])}, "
            f"unresolved {len(g['unresolved'])}; models never offered {len(g['models_never_offered'])}")


def text(g: dict) -> str:
    out = [f"[engine-skill-gap] {_summary(g)}"]
    for e in g["known_unsupported"]:
        tracked = f"#{e['issue']}" if e.get("issue") else "no issue yet"
        out.append(f"  known-unsupported: {e['engine']} ({e['decision']} {e['decided']}, {tracked}) — {e['reason']}")
    for name in g["unresolved"]:
        out.append(f"  UNRESOLVED: {name} has no skill and no dated decision in "
                   f"data/unsupported-engines.json — add the skill or record the decision (#229)")
    for e in g["stale_decisions"]:
        out.append(f"  stale decision: {e['engine']} — delete the entry ({e['why']})")
    for m in g["models_never_offered"]:
        out.append(f"  model no engine can offer: {m['name']} ({m['id']}) — engines {', '.join(m['engines'])}")
    out.append(f"  models that also list an unskilled engine: {len(g['models_touching_unsupported'])}")
    for m in g["models_touching_unsupported"]:
        out.append(f"    - {m['name']} ({m['id']}): {', '.join(m['unsupported'])}")
    return "\n".join(out)


def markdown(g: dict) -> str:
    known = ", ".join(f"`{e['engine']}` ({e['decision']} {e['decided']})" for e in g["known_unsupported"]) or "none"
    unresolved = ", ".join(f"`{n}`" for n in g["unresolved"]) or "none"
    only = ", ".join(f"`{m['id']}`" for m in g["models_never_offered"]) or "none"
    lines = [
        "### Unskilled registry engines (issue #229)",
        "",
        f"- shipped skills: **{len(g['shipped'])}** of **{g['registry_engines']}** registry engines "
        f"({len(g['imageless_skills'])} ship no image: {', '.join(f'`{n}`' for n in g['imageless_skills']) or 'none'})",
        f"- known-unsupported (dated in `data/unsupported-engines.json`): {known}",
        f"- **new and unresolved** (a tracking issue is opened per engine): {unresolved}",
        f"- models no engine can offer: {only}",
        "",
        "The per-engine list is `data/engine-skill-gap.json` (status, image variants, the models "
        "each engine is the top-ranked engine for, per arch); it is regenerated by "
        "`make render-engine-skill-gap` in this same sync.",
    ]
    return "\n".join(lines)


def _rel(path: Path) -> str:
    """A path as a reviewer sees it in the repo, or the absolute path when it is
    outside the checkout (a test's tmp dir)."""
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


# -- the CI gate ------------------------------------------------------------
def check(registry: dict, skills: dict, unsupported: dict, rendered: Path = GAP_FILE) -> list[str]:
    """Errors that make the gap unaccounted for: an unresolved engine, a stale
    decision entry, or a rendered file that no longer matches the real gap."""
    g = gap(registry, skills, unsupported)
    errors = []
    for name in g["unresolved"]:
        errors.append(f"registry engine {name!r} has no skill and no dated decision in "
                      f"{_rel(UNSUPPORTED_FILE)} (new and unresolved, issue #229): add "
                      f"skills/engines/<id>/SKILL.md, or record the decision (decision/decided/reason)")
    for e in g["stale_decisions"]:
        errors.append(f"{_rel(UNSUPPORTED_FILE)}: decision for {e['engine']!r} is stale — "
                      f"{e['why']}; delete the entry")
    if rendered.exists():
        have = json.loads(rendered.read_text())
        if have != g:
            errors.append(f"{_rel(rendered)} is stale: run make render-engine-skill-gap")
    else:
        errors.append(f"missing {_rel(rendered)}: run make render-engine-skill-gap")
    return errors


# -- the visible artifact: one issue per unresolved engine ------------------
def issue_title(name: str) -> str:
    return f"engine: {name} has no llgenie skill (unskilled registry engine from the weekly sync)"


def issue_body(name: str, registry: dict, g: dict) -> str:
    """The tracking issue: the shape every issue in this repository carries (issue #745)."""
    spec = (registry.get("engines") or {}).get(name) or {}
    models = g["engines"].get(name, {}).get("models") or []
    only = [m["id"] for m in g["models_never_offered"] if name in m["engines"]]
    return render_body(
        problem=(
            f"`registry-sync` (#179) carries the engine `{name}` in `data/models.json`, but llgenie "
            f"ships no `skills/engines/<id>/SKILL.md`, no `containers/engines/params/<id>.json` and "
            f"no image for it, so the engine cannot be offered for any model that lists it."
        ),
        why=(
            "`rank_engines` drops an engine with no image, and a model whose ONLY engines are "
            "unskilled is then silently absent from the trend offer: the model looks unavailable "
            "instead of looking like work. That silence is why the omission has to become a dated "
            "decision or a shipped skill, not a gap nobody sees."
        ),
        how=[
            f"Scaffold the skill file: `make engine-skill-scaffold ENGINE=\"{name}\"` writes "
            "`skills/engines/<kebab>/SKILL.md` from the registry's own entry (engine name, repo, "
            "backend) with every key it cannot prove left EMPTY, so `make skills-validate` names "
            "exactly what is still missing instead of a blank page.",
            f"Fill the upstream facts from the pinned repo (never a guess): `ref`/`ref_kind`/"
            "`pinned`, `license`, `install.<backend>` steps from its Dockerfile/README, and "
            "`binary`/`detect`/`launch`/`health`/`alias_mode` for its OpenAI server. Run "
            "`make generate-engine-params ENGINE=<kebab>` and commit the params + Dockerfiles.",
            "Let CI build it: `engine-image-*` picks the new engine x backend up from "
            "`containers/engines/params/` with no workflow edit.",
            "Or record the deliberate decision in `data/unsupported-engines.json` (`decision`, "
            "`decided`, `reason`) so the omission is a decision with a date and a reason.",
            "Either way the registry stays as upstream published it: llgenie never edits the "
            "vendored store to make a gate pass.",
        ],
        benefit=(
            f"`{name}` stops being an unresolved gap: either it becomes selectable for the models "
            "that list it, or the reason it is not is written down where the next sync reads it."
        ),
        acceptance=[
            f"`make check-engine-skill-gap` passes with `{name}` either shipped as a skill or "
            "recorded in `data/unsupported-engines.json`",
            "`make skills-validate REGISTRY=data/models.json UNSUPPORTED=data/unsupported-engines.json` "
            "is green",
            "the models whose only engines are unskilled are offered (or the decision names why not)",
        ],
        technical=[
            f"registry engine: `{name}` (backend `{spec.get('backend') or '?'}`)",
            f"upstream: {spec.get('url') or 'unknown'}",
            f"registry note: {spec.get('note') or 'none'}",
            "models that list this engine: "
            + (", ".join(f"`{m}`" for m in models) or "none"),
            "models whose ONLY engines are unskilled (they can never be offered): "
            + (", ".join(f"`{m}`" for m in only) or "none"),
            "opened automatically by the weekly registry sync for #229; closed when the skill ships "
            "or the decision is recorded.",
        ],
    )


def _gh(gh: str, args: list[str]) -> str:
    r = subprocess.run([gh, *args], capture_output=True, text=True)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
    if r.returncode != 0:
        raise SystemExit(f"[engine-skill-gap] {gh} {' '.join(args)} failed ({r.returncode}): {r.stderr.strip()}")
    return r.stdout


def _gh_api(gh: str, args: list[str]) -> str:
    """`gh api` takes no `--repo` — the full path carries the repository, so this runs bare."""
    return _gh(gh, ["api", *args])


def _issue_labels(gh: str, repo: str, number: int) -> list[str]:
    """The labels the issue ACTUALLY carries, read back from the tracker.

    Read through the REST endpoint the write uses (`repos/<repo>/issues/<n>/labels`), not
    `gh issue view --json labels`: the write this module makes is REST, and a read over the
    other transport can agree with a write that never happened (#724).
    """
    out = _gh_api(gh, [f"repos/{repo}/issues/{number}/labels", "--jq", ".[].name"])
    return [line.strip() for line in (out or "").splitlines() if line.strip()]


def set_labels(gh: str, repo: str, number: int, labels: list[str], dry: bool = False) -> None:
    """Label the issue through the REST API, then PROVE it stuck — or fail the step.

    Neither GitHub write this module used to make can be trusted on the runner's PAT:
    `--label` on `gh issue create` is silently dropped after the issue exists, and
    `gh issue edit --add-label` (GraphQL `addLabelsToLabelable`) is refused outright —
    measured on registry-sync run 40682255828:

        failed to update .../issues/774: GraphQL: Resource not accessible by personal
        access token (addLabelsToLabelable)

    So the POST to `repos/<repo>/issues/<n>/labels` IS the write (#786 does the same for the
    security filer) and the read-back decides. An issue that exists but carries no queue
    label routes the work to nobody — indistinguishable from a green run — hence SystemExit,
    naming the issue and the missing label, instead of a warning.
    """
    if dry:
        print(f"[engine-skill-gap] would label #{number}: {', '.join(labels)}")
        return
    args = ["-X", "POST", f"repos/{repo}/issues/{number}/labels"]
    for label in labels:
        args += ["-f", f"labels[]={label}"]
    _gh_api(gh, args)
    have = _issue_labels(gh, repo, number)
    missing = [label for label in labels if label not in have]
    if missing:
        raise SystemExit(
            f"[engine-skill-gap] #{number} is missing {', '.join(missing)} after the label "
            f"write — an unlabelled tracking issue routes the work to nobody ({QUEUE_LABEL} is "
            "what the implementer bot selects on), so the step fails")
    print(f"[engine-skill-gap] labelled #{number}: {', '.join(labels)}")


def ensure_queue_label(gh: str, repo: str, number: int, dry: bool = False) -> bool:
    """Put the issue in the bots' queue, then PROVE it: returns True when labelled.

    The label is applied through the API (never `--add-label`, #724) and read back, so an
    issue that already exists and lost its queue label is repaired on the next sync instead
    of staying invisible to the bot.
    """
    if QUEUE_LABEL in _issue_labels(gh, repo, number):
        return True
    set_labels(gh, repo, number, [QUEUE_LABEL], dry)
    return True if dry else QUEUE_LABEL in _issue_labels(gh, repo, number)


def open_issue(gh: str, repo: str, name: str, body: str, dry: bool = False) -> dict:
    """Open the tracking issue for one unresolved engine, or report the open one."""
    title = issue_title(name)
    have = json.loads(_gh(gh, ["issue", "list", "--repo", repo, "--state", "open", "--limit", "100",
                               "--json", "number,title", "--search", f'in:title "{title}"']) or "[]")
    hit = next((i for i in have if i["title"] == title), None)
    if hit:
        if not ensure_queue_label(gh, repo, hit["number"], dry):
            raise SystemExit(f"[engine-skill-gap] #{hit['number']} ({name}) exists but does not carry "
                             f"{QUEUE_LABEL}: no bot will pick it up. Add the label and re-run.")
        return {"engine": name, "action": "existing", "number": hit["number"], "url": ""}
    if dry:
        return {"engine": name, "action": "would-create", "number": None, "url": ""}
    # `--label` is NOT passed: on the runner path it is silently dropped, so the issue would
    # exist unlabelled and be invisible to the implementer bot. The labels are applied by
    # `set_labels` (one REST POST + a read-back) the moment the create returns a number (#724).
    out = _gh(gh, ["issue", "create", "--repo", repo, "--title", title, "--body", body])
    url = out.strip().splitlines()[-1] if out.strip() else ""
    number = int(url.rstrip("/").rsplit("/", 1)[-1]) if url.rstrip("/").rsplit("/", 1)[-1].isdigit() else None
    if number is None:
        raise SystemExit(f"[engine-skill-gap] the created issue for {name} returned no number "
                         f"(gh said {url!r}); cannot label or link it")
    set_labels(gh, repo, number, [ISSUE_LABEL, QUEUE_LABEL], dry)
    return {"engine": name, "action": "created", "number": number, "url": url}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="The unskilled-engine gap (issue #229)")
    ap.add_argument("cmd", choices=("report", "render", "check", "spawn"))
    ap.add_argument("--registry", default=None,
                    help="models.json path or URL (default: the vendored data/models.json, "
                         "or LLGENIE_REGISTRY_SRC)")
    ap.add_argument("--unsupported", default=str(UNSUPPORTED_FILE))
    ap.add_argument("--rendered", default=str(GAP_FILE))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--md", action="store_true")
    ap.add_argument("--repo", default="asimov-agent/llgenie")
    ap.add_argument("--gh", default="gh")
    ap.add_argument("--dry", action="store_true", help="spawn: report, do not open")
    a = ap.parse_args(argv)

    registry, skills, unsupported = inventories(a.registry, a.unsupported)

    if a.cmd == "check":
        errors = check(registry, skills, unsupported, Path(a.rendered))
        for e in errors:
            print(f"[engine-skill-gap] {e}", file=sys.stderr)
        if errors:
            return 1
        print(f"[engine-skill-gap] OK {_summary(gap(registry, skills, unsupported))}")
        return 0

    if a.cmd == "render":
        fresh = json.dumps(gap(registry, skills, unsupported), indent=2) + "\n"
        Path(a.rendered).write_text(fresh)
        print(f"[engine-skill-gap] wrote {_rel(Path(a.rendered))}")
        return 0

    if a.cmd == "spawn":
        g = gap(registry, skills, unsupported)
        for e in g["stale_decisions"]:
            print(f"[engine-skill-gap] stale decision: {e['engine']} — {e['why']}", file=sys.stderr)
        if not g["unresolved"]:
            print(f"[engine-skill-gap] no unresolved engine ({_summary(g)})")
            return 0
        for name in g["unresolved"]:
            res = open_issue(a.gh, a.repo, name, issue_body(name, registry, g), a.dry)
            where = res.get("url") or (f"#{res['number']}" if res.get("number") else "")
            print(f"[engine-skill-gap] {res['action']}: {name} -> {where}")
        return 0

    # `report` is a report: it NAMES the unresolved engines and exits 0, so the weekly
    # sync (which must still carry the data, #219) can print it. `check` is the gate.
    g = gap(registry, skills, unsupported)
    if a.json:
        print(json.dumps(g, indent=2))
    elif a.md:
        print(markdown(g))
    else:
        print(text(g))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
