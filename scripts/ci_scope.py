#!/usr/bin/env python3
"""Which CI jobs a diff selects (issue #824).

CI runs one 28-job pipeline for every change: a PR that edits one markdown file pays for the engine
matrix, the scanner images and the published-image tests (measured: PR #767, run 40679882983). This
module is the classifier that answers, from the changed PATHS alone, which change classes a pull request
touches and therefore which jobs it needs.

It is stdlib only and takes the diff as an argument, so it runs in the test image with no network, no
git and no third-party action — the whole point of the design being `git diff` rather than a path-filter
action pinned into the supply chain.

    ci_scope.py classify --paths docs/ARCHITECTURE.md      the classes, one per line
    ci_scope.py jobs --paths … --json                      classes + selected/skipped jobs
    ci_scope.py diff --from origin/main                    read the paths from a real git diff

The tables below ARE the design's table: a job's entry lists the classes that select it. `ALWAYS` is the
set that never depends on the diff, because a skipped one of those would hide a regression in the gate
itself.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys

#: A change class and the path patterns that put a change in it. A pattern with a `/` matches the whole
#: repo-relative path; a bare one matches the file name at any depth (`*.md`, `Makefile`).
CLASSES: dict[str, tuple[str, ...]] = {
    # EXACTLY the trigger's `paths-ignore` list. Markdown is not documentation by extension in this
    # repo: `data/*.md` is read by `sync_registry.py`, `.hermes/skills/**/SKILL.md` and
    # `skills/engines/**/SKILL.md` are contracts, `tests/fixtures/**/*.md` are fixtures. A `*.md`
    # entry here would make the printed selection disagree with the trigger, and the print is the
    # only place a human can see the truth (#824).
    "docs": ("docs/**", "agent-wiki/**", "openspec/**", "README.md", "CHANGES.md"),
    "skills": (".hermes/**", "agents/**"),
    "workflows": (".github/**",),
    "scripts": ("scripts/**", "tools/**"),
    "tests": ("tests/**",),
    "data": ("data/**",),
    "containers": ("containers/**",),
    "engines": ("containers/engines/**", "skills/engines/**"),
    "security": ("renovate.json", "security-reports/**", "tools/security-floors.in"),
}

#: A path that selects EVERY class, deliberately: each one can change what a gate proves or what the
#: pipeline itself does, so a wrong skip here would hide a regression in the gate rather than in the
#: product. Editing the workflows is in this set (`workflows` is also a class) because a change to CI runs
#: everything — that is the repository's own rule for `ci.yml`, applied to itself.
WILDCARDS: tuple[str, ...] = (
    "Makefile", "tools/**", ".github/**", "scripts/ci_*.py", "scripts/engine_*.py",
    "scripts/check_*.py", "scripts/unit_tests.py", "pytest.ini", ".gitleaks.toml", "renovate.json",
    "AGENTS.md",
)

#: The jobs that never depend on the diff. `guard` authorizes publishing; `lint` is the markdown /
#: linefeed gate, so the docs class needs it on both operating systems.
ALWAYS: tuple[str, ...] = ("guard", "linux/lint", "macos/lint")

#: One entry per job of the 28-job matrix (measured 2026-10-28, run 40679882983), listing the classes
#: that select it. `linux-published/*` and the engine rows are one family each, written as families.
JOBS: dict[str, frozenset[str]] = {
    "scanner-images": frozenset({"containers", "security"}),
    "engine-matrix": frozenset({"engines", "containers", "skills"}),
    "engine-base": frozenset({"engines", "containers"}),
    "engine-image": frozenset({"engines", "containers", "skills"}),
    "test-published": frozenset({"engines", "containers", "skills"}),
    "linux-published": frozenset({"engines", "containers"}),
    "linux/unit": frozenset({"scripts", "tests", "data", "skills", "containers", "workflows"}),
    "linux/install": frozenset({"scripts", "containers", "engines", "skills", "data"}),
    "linux/agents-read": frozenset({"skills"}),
    "linux/openspec": frozenset({"docs"}),
    "linux/top-tier": frozenset({"data", "scripts", "containers"}),
    "linux/cpu-health": frozenset({"engines", "containers", "scripts"}),
    "macos/unit": frozenset({"scripts", "tests", "data", "skills", "containers", "workflows"}),
    "macos/install": frozenset({"scripts", "containers", "engines", "skills", "data"}),
    "macos/agents-read": frozenset({"skills"}),
    "macos/openspec": frozenset({"docs"}),
    "macos/top-tier": frozenset({"data", "scripts", "containers"}),
    "macos/cpu-health": frozenset({"engines", "containers", "scripts"}),
}

#: `ci-images` publishes the test image every other job pulls: needed by every class except a docs-only
#: diff, which the docs workflow serves without it.
CI_IMAGES_CLASSES_EXCLUDED: tuple[str, ...] = ("docs",)


def _match(path: str, pattern: str) -> bool:
    """Does ONE repo-relative path match ONE pattern? A `/**` suffix is a directory prefix."""
    if pattern.endswith("/**"):
        base = pattern[:-3]
        return path == base or path.startswith(base + "/")
    if "/" in pattern:
        return fnmatch.fnmatch(path, pattern)
    return fnmatch.fnmatch(path.rsplit("/", 1)[-1], pattern)


def classify(paths: list[str]) -> dict[str, list[str]]:
    """The change classes a diff touches, each with the paths that put it there (empty = no change)."""
    found: dict[str, list[str]] = {name: [] for name in CLASSES}
    wild = [p for p in paths if any(_match(p, w) for w in WILDCARDS)]
    for path in paths:
        for name, patterns in CLASSES.items():
            if any(_match(path, pattern) for pattern in patterns):
                found[name].append(path)
    if wild:
        # A wildcard selects everything: record the wildcard paths under every class so the report says
        # WHY a class is present rather than implying the diff touched that class' own inputs.
        for name in found:
            found[name] = sorted(set(found[name] + wild))
    return {name: hits for name, hits in found.items() if hits}


def jobs_for(classes) -> list[str]:
    """The jobs the detected classes select, sorted; `ALWAYS` first."""
    present = {name for name in classes if name in CLASSES}
    out = list(ALWAYS)
    # every class except a docs-only diff needs the test image
    if present - set(CI_IMAGES_CLASSES_EXCLUDED):
        out.append("ci-images")
    for job, needs in JOBS.items():
        if present & needs:
            out.append(job)
    return sorted(dict.fromkeys(out))


def why(job: str) -> str:
    """What would have selected ONE job family — the reason it is ABSENT, in the same line (#824).

    An AC of this issue is that the log names each skipped stage *with the class that skipped it*: a
    bare list of absent names tells a reader the job did not run, never whether that was right.
    """
    if job in ALWAYS:
        return "always"
    if job == "ci-images":
        return "needs a class other than docs"
    needs = JOBS.get(job)
    if not needs:
        return "no rule names it"
    return "needs one of " + ", ".join(sorted(needs))


def scope(paths: list[str]) -> dict:
    """The whole decision for one diff: classes, the jobs selected, the jobs skipped, and unknown paths."""
    classes = classify(paths)
    known = set(classes)
    selected = jobs_for(known)
    skipped = sorted((set(ALWAYS) | set(JOBS) | {"ci-images"}) - set(selected))
    unknown = sorted({p for p in paths if not any(_match(p, pat) for pats in CLASSES.values() for pat in pats)
                      and not any(_match(p, w) for w in WILDCARDS)})
    return {"classes": sorted(known), "paths": classes, "jobs": selected,
            "skipped": skipped, "skipped_reasons": {job: why(job) for job in skipped},
            "unknown": unknown}


def wide() -> dict:
    """The full-pipeline decision: every class selected, so nothing can be skipped by accident.

    An empty diff and a path no class matches both reach this - a diff the tool cannot read is not
    evidence that a stage is unnecessary (#824: "error or empty diff MUST map to the full pipeline,
    never to an empty selection"). The caller still exits non-zero so the `scope` check is loud; what
    must never happen is a quiet empty set.
    """
    everything = set(CLASSES)
    selected = jobs_for(everything)
    return {"classes": sorted(everything), "paths": {}, "jobs": selected, "skipped": [],
            "skipped_reasons": {}, "unknown": [], "wide": True}


def _paths_from_diff(ref: str) -> list[str]:
    """The changed paths a real CI run would classify (`<ref>...HEAD`, three dots: against the merge base)."""
    proc = subprocess.run(["git", "diff", "--name-only", f"{ref}...HEAD"], capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"[ci-scope] git diff failed for {ref}: {proc.stderr.strip()}")
    return [line for line in proc.stdout.splitlines() if line.strip()]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Which CI jobs a diff selects (issue #824)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("classify", "jobs"):
        p = sub.add_parser(name)
        p.add_argument("--paths", nargs="*", default=None, help="repo-relative paths (default: '--from')")
        p.add_argument("--from", dest="ref", default="", help="a git ref to diff against")
        if name == "jobs":
            p.add_argument("--json", action="store_true")
    d = sub.add_parser("diff", help="print the paths a ref diff touches")
    d.add_argument("--from", dest="ref", default="origin/main")
    a = ap.parse_args(argv)

    if a.cmd == "diff":
        print("\n".join(_paths_from_diff(a.ref)))
        return 0

    paths = a.paths if a.paths is not None else (_paths_from_diff(a.ref) if a.ref else [])
    # A blank entry is a shell artifact, not a changed path: `--paths "$CHANGED"` with an empty variable
    # hands us [""], and treating that as an unclassifiable path turned an empty diff into a RED check -
    # the unfixable red the empty-diff rule exists to prevent. Drop blank entries; what remains decides.
    paths = [path for path in paths if path.strip()]
    if not paths:
        # An empty diff is NOT a defect: there is nothing to fix, so a red check here would be an
        # unfixable red on exactly the refs this check exists for (a merge-queue ref, a dispatch, a
        # force-push that nets to no change). It widens and PASSES. An unclassifiable path still fails,
        # because that one a human must act on (add the glob).
        print("[ci-scope] WIDE: empty diff: no changed paths, so every class is selected; "
              "nothing to fix, so this is not a failure")
        _report(wide(), a.cmd, getattr(a, "json", False))
        return 0

    result = scope(paths)
    if result["unknown"]:
        # fail closed in BOTH directions: the decision is the whole pipeline (never an empty set) and
        # the exit is non-zero (never a quiet green)
        print("[ci-scope] WIDE: path matches no class: every class is selected until one is added")
        for p in result["unknown"]:
            print(f"  {p}")
        _report(wide(), a.cmd, getattr(a, "json", False))
        return 1

    return _report(result, a.cmd, getattr(a, "json", False))


def _report(result: dict, cmd: str, as_json: bool = False) -> int:
    """Print one decision: the classes, the selected jobs, and every skipped job WITH its reason."""
    if cmd == "classify":
        for name in result["classes"]:
            print(name)
        return 0
    if as_json:
        print(json.dumps(result, indent=2))
        return 0
    # One greppable line per class, which is what `scope.yml`'s header promises and what a reader (or
    # a `grep`) can act on without parsing a comma list. The summary line below stays for the log shape.
    for name in result["classes"]:
        print(f"[ci-scope] class={name}")
    print(f"[ci-scope] classes: {', '.join(result['classes']) or 'none'}")
    print(f"[ci-scope] jobs ({len(result['jobs'])} of {len(ALWAYS) + len(JOBS) + 1}): "
          f"{', '.join(result['jobs'])}")
    if result["skipped"]:
        named = ", ".join(f"{job} ({result['skipped_reasons'][job]})" for job in result["skipped"])
        print(f"[ci-scope] skipped: {named}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
