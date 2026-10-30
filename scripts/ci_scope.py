#!/usr/bin/env python3
"""Which stages a pull request's diff selects (issue #824, part a).

CI ran one pipeline for every change: a seven-file markdown PR queued the same 28 jobs as a change to
`containers/engines/`, so a runner minute spent building an engine image for a markdown edit was a minute
not spent giving a real engine change its verdict. This is the classifier that reads the diff ONCE and
says, out loud, which classes it found and which jobs they select.

    python3 scripts/ci_scope.py --base origin/main      # a pull_request run (the PR's base ref)
    python3 scripts/ci_scope.py --before <sha>          # a push run (the commit before the push)
    python3 scripts/ci_scope.py --paths a.md tests/x.py # an explicit list, no git
    python3 scripts/ci_scope.py --all                   # every class, for a push to main

WHAT IT IS NOT: it does not skip a job. A job-level `if:` that skips a stage is invisible in the job
list (`tests/test_ci_images.py::test_no_ci_step_or_job_is_skipped` permits exactly five such shapes and
none of them is a path selection), so part (a) selects the docs class at the TRIGGER
(`pull_request.paths-ignore` in `ci.yml`) and prints the full decision here; per-stage selection inside
`ci.yml` for the code classes is part (b), #824.

THE CONTRACT:

- **one class per rule**, matched by glob where `*` stops at `/` and `**` crosses it;
- **a wildcard path selects every class**: `Makefile`, `tools/**`, `.github/**`, `scripts/ci_*.py`,
  `scripts/engine_*.py`, `scripts/check_*.py`, `pytest.ini`, `.gitleaks.toml`, `renovate.json`,
  `AGENTS.md` can change what ANY gate proves, so a quiet skip there would hide a regression in the
  gate itself;
- **an unmatched path is a LOUD failure** (exit 1 naming the path), never a silent pass: a path nobody
  classified is a stage nobody decided about;
- `guard` and `lint` always run (they authorize publishing and hold the markdown gate), and `push` runs
  to `main` keep the whole matrix — absence is safe for merging but dangerous for reading (#801, #817).

Stdlib only: it runs in the runner with no dependency, and in `ci-unit` on the host.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

TAG = "[ci-scope]"

#: Exit code for a path no class claims, or a diff we could not read.
EXIT_UNCLASSIFIED = 1

#: Exit code for a run that has NO scope decision at all (issue #1111): a different answer from a
#: red verdict, and the one a cancelled fan-out must produce — "nobody decided" is not "all clear".
EXIT_NO_VERDICT = 2

#: The shape `decision()` writes and `verify()` refuses to guess at. Bump it when the JSON moves.
DECISION_SCHEMA = 1

#: class -> the globs it owns. Order is the order the report prints them in.
CLASSES: dict[str, tuple[str, ...]] = {
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

#: A path matching one of these selects EVERY class: it can change what any gate proves.
WILDCARDS: tuple[str, ...] = (
    "Makefile",
    "tools/**",
    ".github/**",
    "scripts/ci_*.py",
    "scripts/engine_*.py",
    "scripts/check_*.py",
    "pytest.ini",
    ".gitleaks.toml",
    "renovate.json",
    "AGENTS.md",
)

#: The classes that select `ci-images`: everything but `docs`, because a docs-only diff needs no image.
_NON_DOCS = tuple(name for name in CLASSES if name != "docs")

#: The `docs` class as a GitHub `paths-ignore` list — the globs a docs-only diff must match, MINUS the
#: wildcards (`AGENTS.md` is a `*.md`, and editing it must re-include the full matrix). `ci.yml` and this
#: constant are compared by `tests/test_ci_scope.py`, so the YAML cannot drift from the classifier.
DOCS_TRIGGER_IGNORE: tuple[str, ...] = CLASSES["docs"]

#: job -> the classes that select it (`None` = always runs). The 28 jobs of `ci.yml`, in file order
#: (issue #824's table). Two rows are families: `engine-image` / `test-published` are matrix rows and
#: `install-published-*` is one job per backend.
_STAGES = {
    "lint": None,
    "unit": ("scripts", "tests", "data", "skills", "containers", "workflows"),
    "install": ("scripts", "containers", "engines", "skills", "data"),
    "agents-read": ("skills",),
    "openspec": ("docs",),
    "top-tier": ("data", "scripts", "containers"),
    "cpu-health": ("engines", "containers", "scripts"),
}

JOBS: tuple[tuple[str, tuple[str, ...] | None], ...] = (
    ("guard", None),
    ("ci-images", _NON_DOCS),
    ("scanner-images", ("containers", "security")),
    ("linux/lint", None),
    ("linux/unit", _STAGES["unit"]),
    ("linux/install", _STAGES["install"]),
    ("linux/agents-read", _STAGES["agents-read"]),
    ("linux/openspec", _STAGES["openspec"]),
    ("linux/top-tier", _STAGES["top-tier"]),
    ("linux/cpu-health", _STAGES["cpu-health"]),
)


def glob_to_regex(pattern: str) -> str:
    """Translate one path glob to a regex: `*` stops at `/`, `**` crosses it, everything else literal."""
    out: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?" )  # zero or more directories
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return "".join(out)


def matches(pattern: str, path: str) -> bool:
    """Does `path` match `pattern` under the classifier's glob rules?"""
    return re.fullmatch(glob_to_regex(pattern), path) is not None


def matched_wildcards(paths: list[str]) -> list[str]:
    """The wildcard globs the diff matched — the reason every class is selected."""
    return [pattern for pattern in WILDCARDS if any(matches(pattern, p) for p in paths)]


def classify(paths: list[str]) -> tuple[list[str], list[str], str | None]:
    """The classes the diff selects, the paths no class claims, and WHY it was widened (issue #860).

    **An unreadable diff fails OPEN, and that decision lives HERE — not in `main()`.** The invariant
    that makes a path-selected pipeline safe is "if the diff cannot be read, select every family": a
    quiet empty set is the failure #824 exists to forbid. `main()` used to own that substitution, so
    every other caller — a test, a script, a future workflow importing this module — reached the
    narrow answer for an empty or unmatched diff while the CLI looked correct. The widening is now the
    library's own behaviour and `main()` only renders it (issue #860).

    Widened for: a wildcard path (it can change what any gate proves), an EMPTY path list (nothing to
    read), and a diff where no path matches a class (the classifier is owed a glob). The third case
    still reports the unmatched paths, because the CLI exits non-zero for it — the widening is about
    what gets selected, never about hiding a defect.
    """
    paths = [p for p in paths if p.strip()]        # `--paths ''` is an empty diff, not a bad path
    wildcards = matched_wildcards(paths)
    if wildcards:
        return list(CLASSES), [], f"wildcard path {', '.join(wildcards)} — every class is selected"
    if not paths:
        return list(CLASSES), [], "empty diff — nothing to read, every class is selected"
    selected: list[str] = []
    unmatched: list[str] = []
    for path in paths:
        hit = [name for name, globs in CLASSES.items() if any(matches(g, path) for g in globs)]
        if not hit:
            unmatched.append(path)
            continue
        for name in hit:
            if name not in selected:
                selected.append(name)
    if unmatched:
        return list(CLASSES), unmatched, f"path matches no class ({unmatched[0]}) — every class is selected until one is added"
    return [name for name in CLASSES if name in selected], [], None


def select(classes: list[str]) -> list[tuple[str, bool, str]]:
    """One `(job, runs, why)` row per job of `ci.yml`, decided by the classes the diff selected.

    An unknown class name is a caller bug, not a narrowing (issue #1061): `wanted` is intersected
    with each job's `needs`, so a name that is not a key of `CLASSES` matches nothing and every job
    needing it used to be dropped in silence — the quiet empty set `classify()` already refuses to
    hide (#860), one layer down. Refuse it here, where every caller sees it, rather than trusting
    each to have validated its own list. An EMPTY list stays legal: it is the documented
    `--paths ''` case, meaning the always-on jobs only.
    """
    unknown = sorted(set(classes) - set(CLASSES))
    if unknown:
        raise ValueError(
            f"unknown class {', '.join(unknown)} — valid classes are {', '.join(CLASSES)}"
        )
    wanted = set(classes)
    rows: list[tuple[str, bool, str]] = []
    for job, needs in JOBS:
        if needs is None:
            rows.append((job, True, "always"))
            continue
        hit = [name for name in needs if name in wanted]
        if hit:
            rows.append((job, True, f"class {'+'.join(hit)}"))
        else:
            rows.append((job, False, f"no class from [{','.join(classes) or '-'}]; needs one of {','.join(needs)}"))
    return rows


def changed_paths(*, base: str | None, before: str | None, cwd: str | None = None) -> list[str]:
    """The diff's paths, read from git — the same `before`/base-ref logic `ci.yml`'s engine-matrix uses."""
    if base and before:
        raise ValueError("give --base (a pull request) or --before (a push), not both")
    if not base and not before:
        raise ValueError("one of --base / --before / --paths is required")
    revision = before or f"{base}...HEAD"
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", revision],
        cwd=cwd, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git diff {revision} failed: {(result.stderr or result.stdout).strip()}")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def report(classes: list[str], rows: list[tuple[str, bool, str]], paths: list[str], wide: str | None) -> list[str]:
    """The lines a run prints: what was read, the class per rule, then every job with its verdict."""
    lines = [f"{TAG} {len(paths)} file(s) changed"]
    if wide:
        lines.append(f"{TAG} WIDE: {wide}")
    for name in classes:
        lines.append(f"{TAG} class={name}")
    for job, runs, why in rows:
        lines.append(f"{TAG} job={job} {'run' if runs else 'skip'} — {why}")
    selected = [job for job, runs, _ in rows if runs]
    lines.append(
        f"{TAG} scope: class(es) {','.join(classes) or '-'} -> {len(selected)} of {len(rows)} job(s): "
        f"{','.join(selected)}"
    )
    if "docs" in classes and set(classes) == {"docs"}:
        lines.append(
            f"{TAG} trigger: a docs-only diff does not start ci.yml at all (`pull_request.paths-ignore`); "
            f"the docs gates run in scope.yml, and the `scope` check states this decision (#824)"
        )
    return lines


def github_output(rows: list[tuple[str, bool, str]], classes: list[str], path: Path | None) -> None:
    """Write the machine-readable answer GitHub needs a step to export."""
    if path is None:
        return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"classes={','.join(classes)}\n")
        handle.write(f"jobs={' '.join(job for job, runs, _ in rows if runs)}\n")
        handle.write("docs_only=%d\n" % int(set(classes) == {"docs"}))


# ---- the DECISION a finished run is held to (issue #1111) --------------------------------
#
# A run's check-runs answer "which jobs reported, and with what conclusion". They do NOT answer
# "was a job ALLOWED to be missing", because a check-run row and the decision that produced it live
# in different places: `linux / unit` never reported on run 41134761297 (its parent `linux` was
# `skipped` because `ci-images` had been cancelled), and every reader counting conclusions saw
# `success=3, failed=0` for a head whose unit gate never ran.
#
# So the decision is DATA: the scope job publishes it (`decision()` below, written by
# `--decision-out`), and a verdict compares a finished run against it (`verify()`), where "skipped"
# is legitimate only when the decision says that job was not needed. No decision is a verdict of its
# own: `none`, never "0 failures" — the failure mode this module exists to end.

#: The verdict words. `none` is not a softer `red`: it means nothing decided, which is exactly what a
#: cancelled fan-out leaves behind and what a summary must never print as a pass.
GREEN = "green"
RED = "red"
NONE = "none"

#: Conclusions that mean "this job did not produce a verdict" rather than "this job passed/failed".
_NOT_A_VERDICT = ("skipped", "cancelled")


def decision(classes: list[str], rows: list[tuple[str, bool, str]], paths: list[str],
             wide: str | None) -> dict:
    """The scope decision as data — the artifact a verdict reads back (issue #1111).

    Deliberately small and dependency-free: it is written by `ci.yml`'s `guard` job, uploaded as the
    `ci-scope-decision` artifact, and read by `scripts/ci_verdict.py` on the finished run. `paths` is
    carried for a reader, never re-classified: the decision is the answer the run was held to, not a
    second opinion about the same diff.
    """
    return {
        "schema": DECISION_SCHEMA,
        "classes": list(classes),
        "paths": list(paths),
        "wide": wide,
        "jobs": {job: {"run": bool(runs), "why": why} for job, runs, why in rows},
    }


def normalise_job_name(name: str) -> str:
    """A check-run/job name as the classifier spells it: `linux / unit` -> `linux/unit`.

    GitHub prints a called workflow's jobs as `<caller> / <callee>` and a matrix row with its value in
    parentheses (`linux / top-tier (none)`). The table in `JOBS` spells the first without spaces and
    the row's value is not part of its identity, so both are folded here — one place, so the report
    and the verdict cannot drift.
    """
    stripped = re.sub(r"\s*\([^()]*\)\s*$", "", str(name).strip())
    return re.sub(r"\s*/\s*", "/", stripped)


def verify(decision_obj: dict | None, jobs: list[dict]) -> dict:
    """Hold a finished run to its decision: one finding per job, a verdict, and a summary line.

    `jobs` is the payload of `GET /repos/{owner}/{repo}/actions/runs/<id>/jobs`. The answer is a dict
    with `verdict` (green | red | none), per-finding `lines`, and `counts` — because the reader this
    exists for quotes a SUMMARY, and `success=6, failed=0` must never be printed for a run in which a
    selected job was `skipped` or never reported (issue #1111).

    The four answers, and no fifth:
      * a decision selected a job and it reported `success` -> counted as success;
      * a decision selected a job and it is skipped/cancelled/absent -> `no_verdict` (red);
      * a decision did NOT select a job and it is skipped/absent -> `skipped_by_decision` (green);
      * there is no decision at all -> every non-success row is `no_verdict`, and `verdict=none`.
    """
    lines: list[str] = []
    counts = {"success": 0, "failure": 0, "skipped_by_decision": 0, "no_verdict": 0, "pending": 0}
    observed: dict[str, list[dict]] = {}
    for job in jobs:
        observed.setdefault(normalise_job_name(job.get("name") or ""), []).append(job)

    def conclusion_of(job: dict) -> str:
        conclusion = (job.get("conclusion") or "").strip().lower()
        if conclusion:
            return conclusion
        # A row that is not completed has no conclusion yet: on a completed run that is a job that
        # never started, which is a non-verdict and never a pass (issue #1111).
        return "pending"

    table = (decision_obj or {}).get("jobs") or {}
    #: The CALLERS whose children `JOBS` names (`linux` -> `linux/unit`, ...): the children are the
    #: accounting unit, so the caller's own row is reported and never counted twice.
    container_names = {job.split("/", 1)[0] for job in table if "/" in job}

    def no_answer(conclusion: str) -> None:
        """Count a row that is not a verdict: `pending` is its own bucket, every other its own."""
        counts["pending" if conclusion == "pending" else "no_verdict"] += 1

    if not decision_obj:
        # No decision exists: nothing can make a missing or skipped gate legitimate.
        lines.append(f"{TAG} NO DECISION: this run published no scope decision — no skip is legitimate")
        for name, rows in sorted(observed.items()):
            for job in rows:
                conclusion = conclusion_of(job)
                if conclusion == "success":
                    counts["success"] += 1
                    lines.append(f"{TAG} {name} success")
                elif conclusion == "failure":
                    counts["failure"] += 1
                    lines.append(f"{TAG} {name} FAILED")
                else:
                    no_answer(conclusion)
                    lines.append(f"{TAG} {name} {conclusion} — no decision says it may be {conclusion}")
        verdict = RED if counts["failure"] else (
            NONE if (counts["no_verdict"] or counts["pending"]) else GREEN)
    else:
        for job, spec in table.items():
            requires = bool(spec.get("run"))
            why = str(spec.get("why") or "")
            rows = observed.get(job)
            if not rows:
                if requires:
                    counts["no_verdict"] += 1
                    lines.append(f"{TAG} {job} ABSENT — the decision selected it ({why}) and no row reported")
                else:
                    counts["skipped_by_decision"] += 1
                    lines.append(f"{TAG} {job} absent — not selected by the decision ({why})")
                continue
            for observed_job in rows:
                conclusion = conclusion_of(observed_job)
                if conclusion == "success":
                    counts["success"] += 1
                    lines.append(f"{TAG} {job} success")
                elif conclusion == "failure":
                    counts["failure"] += 1
                    lines.append(f"{TAG} {job} FAILED")
                elif not requires:
                    counts["skipped_by_decision"] += 1
                    lines.append(f"{TAG} {job} {conclusion} — the decision did not select it ({why})")
                else:
                    no_answer(conclusion)
                    lines.append(f"{TAG} {job} {conclusion} — the decision selected it ({why})")
        for name in sorted(set(observed) - set(table)):
            # A row the table does not name (a new job nobody classified, or another workflow's job):
            # reported, never silently counted as covered.
            for job in observed[name]:
                conclusion = conclusion_of(job)
                if name in container_names:
                    # `linux` is the CALLER of the `linux / *` rows, not one of them: its children
                    # are the accounting unit (they are what `JOBS` names), so the container row is
                    # printed for the reader and never counted — counting it would double-count a
                    # matrix, and counting it as "unaccounted" would red every legitimate skip.
                    lines.append(f"{TAG} {name} {conclusion} — caller of the {name}/* rows, accounted per row")
                elif conclusion in _NOT_A_VERDICT or conclusion == "pending":
                    no_answer(conclusion)
                    lines.append(f"{TAG} {name} {conclusion} — no job in the scope table owns this name")
                elif conclusion == "failure":
                    counts["failure"] += 1
                    lines.append(f"{TAG} {name} FAILED")
                else:
                    counts["success"] += 1
                    lines.append(f"{TAG} {name} success — not in the scope table")
        verdict = RED if counts["failure"] else (
            NONE if (counts["no_verdict"] or counts["pending"]) else GREEN)

    unaccounted = counts["failure"] + counts["no_verdict"] + counts["pending"]
    lines.append(
        f"{TAG} summary: verdict={verdict} success={counts['success']} failure={counts['failure']} "
        f"skipped-by-decision={counts['skipped_by_decision']} no-verdict={counts['no_verdict']} "
        f"pending={counts['pending']}"
    )
    if verdict != GREEN:
        # The sentence a summary must print instead of "0 failures": the number is what made this
        # defect invisible, so the summary names it rather than repeating it (issue #1111).
        lines.append(
            f"{TAG} NO VERDICT: {unaccounted} job(s) unaccounted for — 0 failures is not a verdict"
        )
    return {"verdict": verdict, "lines": lines, "counts": counts, "has_decision": bool(decision_obj)}


def check_run_payload(verdict: str, head_sha: str, lines: list[str],
                      conclusion: str | None = None, run_label: str = "") -> dict:
    """The `POST /repos/{owner}/{repo}/check-runs` body the verdict posts on the run's head.

    A `workflow_run` run creates NO check-run of its own on the commit (measured on 0bd5ac6e: the
    cancelled CI run's rows are the only ones, `auto-merge`'s own run is absent), so a verdict that is
    only a red workflow would still read clean to every check-run reader. Posting it is what puts the
    answer where the question is asked. `conclusion` overrides the verdict's mapping for the
    SUPERSEDED case, where the head is owed nothing because a later run owns it.
    """
    mapped = {"green": "success", "red": "failure", "none": "failure"}
    summary = "\n".join(lines)
    return {
        "name": "ci-verdict",
        "head_sha": head_sha,
        "status": "completed",
        "conclusion": conclusion or mapped[verdict],
        "output": {
            "title": (f"ci-verdict: {verdict}" + (f" ({run_label})" if run_label else ""))[:255],
            "summary": summary[:65000],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Select CI stages from a pull request's changed paths (#824).")
    parser.add_argument("--base", default=None, help="the PR base ref, e.g. origin/main (diffs <base>...HEAD)")
    parser.add_argument("--before", default=None, help="the commit before a push (github.event.before)")
    parser.add_argument("--paths", nargs="*", default=None, help="an explicit path list instead of a git diff")
    parser.add_argument("--paths-from", default=None, help="read the path list from a file ('-' for stdin)")
    parser.add_argument("--all", action="store_true", help="select every class (a push to main keeps the full matrix)")
    parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"),
                        help="append classes=/jobs=/docs_only= to this file (default: $GITHUB_OUTPUT)")
    parser.add_argument("--decision-out", default=os.environ.get("SCOPE_DECISION") or None,
                        help="write the DECISION this run will be held to as JSON (issue #1111); "
                             "default: $SCOPE_DECISION, unset = do not write one")
    parser.add_argument("--cwd", default=None, help="the repository to diff (default: the current directory)")
    args = parser.parse_args(argv)

    try:
        if args.paths is not None:
            paths = list(args.paths)
        elif args.paths_from:
            text = sys.stdin.read() if args.paths_from == "-" else Path(args.paths_from).read_text()
            paths = [line.strip() for line in text.splitlines() if line.strip()]
        elif args.all:
            paths = []
        else:
            paths = changed_paths(base=args.base, before=args.before, cwd=args.cwd)
    except (ValueError, RuntimeError) as exc:
        print(f"{TAG} FAILED: {exc}", file=sys.stderr)
        return EXIT_UNCLASSIFIED

    if args.all:
        classes, unmatched, wide = list(CLASSES), [], "--all: a push keeps the full matrix"
    else:
        classes, unmatched, wide = classify(paths)
    rows = select(classes)
    for line in report(classes, rows, paths, wide):
        print(line)

    if unmatched:
        for path in unmatched:
            print(f"{TAG} FAILED: {path} matches no class — add it to CLASSES in scripts/ci_scope.py "
                  f"(or to WILDCARDS when it can change what any gate proves)", file=sys.stderr)
        return EXIT_UNCLASSIFIED

    github_output(rows, classes, Path(args.github_output) if args.github_output else None)
    if args.decision_out:
        # The artifact a finished run is held to (issue #1111). Written even when the diff is wide:
        # the decision says which jobs MUST report, so "everything runs" is a decision too.
        Path(args.decision_out).write_text(
            json.dumps(decision(classes, rows, paths, wide), indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        print(f"{TAG} decision written to {args.decision_out} (issue #1111)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
