#!/usr/bin/env python3
"""Make a JEV preflight failure readable, and file ONE tracker per failure class (issue #802).

`make agent-jev-preflight NERVE_REQUIRE=1` is a bot job's first step, and when it fails the run's step
list shows a step name and nothing else: an operator reading the Actions page cannot tell whether the
JEV engine is off (fix the secret/plugin), whether the job simply never passes the provider key, or
whether the provider is down. Measured on `asimov-agent/llgenie` (2026-10-28): `issue-dedupe` runs
40697636784 and 40702295009 both died at that step with `TYPESAFE_API_KEY is missing or empty` in the
log, the duplicate sweep decided nothing, and no issue tracked it.

So a failure of the preflight is reported by THIS module, called by `make jev-preflight-required`:

  * it CLASSIFIES the preflight's own output into one failure class (key missing, plugin missing,
    plugin disabled, no hermes, provider unreachable, ...), prints the class, the measured line and
    the fix for that class in words an operator can act on, and
  * it files ONE issue per class, deduped by a body marker — `<!-- jev-preflight: <class> -->` — so a
    second run of the same class prints the existing issue instead of filing a second one. "Once per
    class, not once per run" is the issue's requirement, so a repeat run deliberately files nothing
    and comments nothing: the tracker is the class's memory, not a run log.

The exit status of the preflight is NOT softened: the caller keeps the step red. What changes is that
the failure now names itself and has one open work item.

Stdlib only, and `gh` is the executor (the external system the real run talks to; tests point it at a
stand-in on PATH, the production call runs unchanged).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from issue_body import render as render_body  # the one issue shape (issue #745)

#: The dedupe marker prefix. The full marker is `<!-- jev-preflight: <class> -->`.
MARKER_PREFIX = "jev-preflight:"

#: The label a tracker carries: the issue-bot owns the fix, exactly like a reactor issue.
IMPLEMENT_LABEL = "agent:implement"

#: Every failure class the preflight can report, its matched signatures (checked in order — the
#: first class whose needle appears in the output wins) and the fix an operator can act on.
#: The needles are the preflight's OWN words (`scripts/agent_jev_preflight.sh` and the
#: `require_env.py` guard in front of it), so a class is read from the run, never guessed.
CLASSES: tuple[tuple[str, tuple[str, ...], str], ...] = (
    (
        "key-missing",
        ("is missing or empty", "is not set, so the JEV decision layer"),
        "the provider key never reached the step: set the repository secret TYPESAFE_API_KEY and pass "
        "it as `TYPESAFE_API_KEY: ${{ secrets.TYPESAFE_API_KEY }}` in the job's env (the leg forwards "
        "it to the agent image; the value is never printed)",
    ),
    (
        "plugin-missing",
        ("nerve plugin is not installed",),
        "the agent image was built without the plugin: rebuild it from containers/agent/Dockerfile "
        "and check the build log for the nerve install step (scripts/install_nerve_ci.sh)",
    ),
    (
        "plugin-disabled",
        ("installed-but-disabled", "does nothing for the run"),
        "the plugin is installed but not enabled in the image's HERMES_HOME: enable it in the image "
        "build (scripts/install_nerve_ci.sh) instead of at run time",
    ),
    (
        "hermes-missing",
        ("no hermes on PATH",),
        "the image does not carry the Hermes CLI: rebuild the agent image and check that hermes is on "
        "PATH inside it",
    ),
    (
        "smoke-missing",
        ("live smoke is missing",),
        "the plugin landed without its smoke script: reinstall the plugin at the pinned commit in the "
        "agent image (scripts/install_nerve_ci.sh)",
    ),
    (
        "provider-unsupported",
        ("unsupported HERMES_NERVE_PROVIDER",),
        "the job sets a provider the Nerve plugin cannot use: keep jev_provider at typesafe (the "
        "repository's only provider) or add the provider to the plugin's wiring first",
    ),
    (
        "provider-no-payload",
        ("returned no decision payload",),
        "the provider answered without a decision payload: re-run the smoke "
        "(`make agent-jev-preflight`) and, when it repeats, check the plugin's typesafe_model setting",
    ),
    (
        "provider-unreachable",
        ("did not answer a live decision call",),
        "the provider did not answer: check the TYPESAFE_API_KEY value and the provider's status, then "
        "re-run the smoke (`make agent-jev-preflight`)",
    ),
    (
        "unknown",
        (),
        "read the preflight's output above and run `make agent-jev-preflight` on the host with the same "
        "environment to reproduce it",
    ),
)

#: The ANSI colour an Actions log carries; the tracker reads the text, not the escapes.
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

#: `gh run view --log-failed` prefixes every line with `job<TAB>step<TAB>2026-10-28T14:10:43.7085994Z `.
#: The tracker quotes the line, never the transport: the prefix (and the BOM a step name can start with)
#: is noise in an issue body.
GH_LOG_PREFIX = re.compile(r"^\ufeff?(?:[^\t]*\t){1,2}\ufeff?\d{4}-\d{2}-\d{2}T[\d:.]+Z ")

#: How many trailing log lines the issue body carries.
LOG_TAIL_LINES = 25


def _lines(text: str) -> list[str]:
    return [GH_LOG_PREFIX.sub("", ANSI.sub("", line)).strip("\ufeff").rstrip()
            for line in (text or "").splitlines()]


def classify(text: str) -> tuple[str, str]:
    """The failure class and the measured line that names it. Never guesses past `unknown`."""
    lines = _lines(text)
    for name, needles, _fix in CLASSES:
        for line in lines:
            if any(needle in line for needle in needles):
                return name, line.strip()
    # No signature matched: the first loud line is the best evidence available, and `unknown`
    # says so instead of inventing a class.
    for line in lines:
        if "ERROR:" in line or "FATAL:" in line:
            return "unknown", line.strip()
    tail = [line for line in lines if line.strip()]
    return "unknown", (tail[-1].strip() if tail else "the preflight printed nothing")


def fix_for(name: str) -> str:
    """The operator-facing fix for a class."""
    for cls, _needles, fix in CLASSES:
        if cls == name:
            return fix
    return CLASSES[-1][2]


def marker(name: str) -> str:
    """The dedupe marker: one per class, and the body's first line."""
    return f"<!-- {MARKER_PREFIX} {name} -->"


def issue_title(name: str) -> str:
    return f"ci(jev-preflight): the JEV decision layer is inactive ({name}) — the dependent bot run stopped at its preflight"


def issue_body(name: str, reason: str, run_url: str, log_tail: str) -> str:
    """The tracker body, in the repository's one issue shape (issue #745)."""
    where = f" in `{run_url}`" if run_url else ""
    return render_body(
        marker=marker(name),
        problem=(
            f"The JEV decision layer's preflight failed{where} with class `{name}`: {reason}. "
            "`make agent-jev-preflight NERVE_REQUIRE=1` is a bot job's first step, so the job stopped "
            "there and did none of its work."
        ),
        why=(
            "A bot whose first step refuses to start produces no artifact and no comment, which reads "
            "exactly like \"nothing to do\" on the issue list — the duplicate sweep stopped retiring "
            "duplicates while nothing said so (issue #802). Leaving it unfixed costs a scheduled run "
            "every six hours."
        ),
        how=[
            f"Reproduce the class on the host with the step's own target: `make agent-jev-preflight "
            f"NERVE_REQUIRE=1` (its output is the same one this tracker read).",
            f"Apply the fix for `{name}`: {fix_for(name)}.",
            "Re-run the step until it reports `JEV ready`, then let the bot's next scheduled run prove "
            "it — the duplicate sweep decides again.",
            "This issue is filed ONCE per class: a later run of the same class reports this number "
            "instead of filing a second tracker.",
        ],
        benefit=(
            "A preflight failure names its own class and its fix in the run's output, and the class "
            "has exactly one open work item — so the sweep either runs or says why not in one readable "
            "place, instead of a step name being the only diagnostic."
        ),
        acceptance=[
            "`make agent-jev-preflight NERVE_REQUIRE=1` reports `JEV ready` on the host with the "
            "engine active, and its real output is in the fixing PR",
            "the class above no longer appears in a bot run's preflight step",
            "the bot's next scheduled run completes its decision (a run id is cited in the fixing PR)",
            "a second failure of the SAME class files no second issue",
        ],
        technical=[
            f"**failure class:** `{name}`",
            f"**measured line:** `{reason}`",
            f"**run:** `{run_url}`" if run_url else "**run:** not supplied",
            "**step:** `Prove the JEV engine is active` -> `make agent-jev-preflight NERVE_REQUIRE=1`",
            "**reporter:** `make jev-preflight-required` -> `scripts/jev_preflight_tracker.py`",
            f"**dedupe marker (body line 1):** `{marker(name)}`",
            "",
            "Failing output tail:",
            "",
            "```",
            log_tail,
            "```",
        ],
    )


def _gh(args: list[str]) -> str:
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout


def tracked(repo: str, name: str) -> int | None:
    """The open issue already carrying this class's marker, or None. The marker is the memory.

    The search is the full marker, quoted, exactly as `scripts/run_failure_reactor.py` searches its
    own (`f'"{marker}" in:body'`) — the proven dedupe read in this repository, not a second dialect.
    """
    out = _gh(["issue", "list", "--repo", repo, "--state", "open", "--search",
               f'"{marker(name)}" in:body', "--limit", "5", "--json", "number"])
    rows = json.loads(out or "[]")
    return int(rows[0]["number"]) if rows else None


def report(repo: str, text: str, run_url: str = "", dry: bool = False, local: bool = False) -> int:
    """Print the class + fix, then file ONE tracker per class. Returns 0, or 1 when filing failed.

    `local=True` is a person running the target on their own host: it prints the class and the fix and
    writes NOTHING to the repository. Only a CI run files — measured 2026-10-28, a local run on a host
    with no Docker daemon filed a real `unknown` tracker (#809) for a failure that was the host's, not
    the repository's. The Makefile passes `--local` whenever `GITHUB_ACTIONS` is not `true`.
    """
    name, reason = classify(text)
    print(f"[jev-preflight] the JEV decision layer is INACTIVE (class: {name})", flush=True)
    print(f"[jev-preflight] measured: {reason}", flush=True)
    print(f"[jev-preflight] fix: {fix_for(name)}", flush=True)
    if local:
        print("[jev-preflight] local run: no tracker is filed (only the CI step files one); re-run "
              "with --repo/--run-url to file it by hand", flush=True)
        return 0
    if not repo:
        print("[jev-preflight] REPO is unset, so no tracker was filed — set REPO=<owner/repo> in the "
              "step that runs this target", flush=True)
        return 1
    try:
        existing = tracked(repo, name)
        if existing:
            print(f"[jev-preflight] already tracked: {repo}#{existing} (class {name}) — filed once per "
                  "class, so nothing new is created here", flush=True)
            return 0
        tail = "\n".join(_lines(text)[-LOG_TAIL_LINES:])
        title = issue_title(name)
        if dry:
            print(f"[jev-preflight] DRY: would file {title!r} with marker {marker(name)}", flush=True)
            return 0
        out = _gh(["issue", "create", "--repo", repo, "--title", title,
                   "--body", issue_body(name, reason, run_url, tail),
                   "--label", IMPLEMENT_LABEL])
        print(f"[jev-preflight] filed tracker: {out.strip()}", flush=True)
        return 0
    except Exception as exc:  # noqa: BLE001 - a tracker that cannot file is LOUD, never silent
        print(f"[jev-preflight] WARNING: could not file the tracker: {exc}", file=sys.stderr, flush=True)
        return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Report a JEV preflight failure and file ONE tracker per class.")
    ap.add_argument("command", choices=("report", "classify"))
    ap.add_argument("--repo", default="", help="owner/repo to file the tracker in")
    ap.add_argument("--log", default="", help="the preflight's captured output (default: stdin)")
    ap.add_argument("--run-url", default="", help="the Actions run URL, for the issue body")
    ap.add_argument("--dry", action="store_true", help="print the class and the issue, file nothing")
    ap.add_argument("--local", action="store_true",
                    help="a local run: print the class and the fix, write nothing to the repository")
    args = ap.parse_args(argv)

    if args.log:
        text = Path(args.log).read_text(errors="replace")
    else:
        text = sys.stdin.read()

    if args.command == "classify":
        name, reason = classify(text)
        print(f"class={name}")
        print(f"reason={reason}")
        print(f"fix={fix_for(name)}")
        return 0
    return report(args.repo, text, run_url=args.run_url, dry=args.dry, local=args.local)


if __name__ == "__main__":
    raise SystemExit(main())
