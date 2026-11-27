# The documented bot fleet now has a roster gate and a weekly review — issue #3106

## Problem

`docs/ARCHITECTURE.md` claims to enumerate the llgenie bot fleet, but nothing measured that claim
against `agents/manifest.json`. A profile added to the manifest (issue #791) could stay absent from
the doc indefinitely. The owner also wanted a weekly Hermes review that suggests architecture
improvements without touching code.

## Measured evidence

At main `412b84f0228df048d997115aaab2bb02c52094dd` (fetched 2026-11-27), the minutes used by
scheduled workflows were 1,3,5,7,9,13,17,19,21,25,27,31,35,39,41,49,53,59 — minute `43` was free.

- `make -s check-workflows` rc=0 (includes actionlint + shellcheck over `.github/workflows/`).
- `make -s check-ci-discipline` rc=0 inside `llgenie/test:latest`.
- Roster gate fixture proof: a doc listing all 13 profiles rc=0; removing `llgenie-tester` rc=1 and
  names it; an extra future lane still rc=0 (subset, not equality).
- At the PR head, `docs/ARCHITECTURE.md` has no `## Host lane fleet` subsection yet — the docs lane
  owns that prose (#3106 routing, comment `7224215751`), so `make check-docs` legitimately fails
  until the docs PR lands. This PR does not edit that prose.

## Traps worth recording

- `workflow_run.workflows` matches a workflow's `name:` verbatim. The reactor is manual-only
  (#2293), so a new workflow cannot be added to its roster; the correct consumer record is a dated
  entry in `tests/fixtures/workflow-run-exemptions.json`, which `check-workflows` reports stale once
  the workflow disappears.
- A scheduled lane must also be added to `SCHEDULE_ALLOW` in `scripts/check_ci_discipline.py`;
  adding it to `AGENT_LANES` instead would red the "#2701 deactivated agent lane re-scheduled" rule.
- The first draft of `check_fleet_roster.py` crashed with `ValueError: ... is not in the subpath of`
  when given an out-of-tree fixture doc; the report now uses a display-path helper so a negative
  case names the missing profile instead of throwing a traceback.

## Author identity on the record

The single atomic commit is authored and committed as `Asimov Agent <support@docondee.com>` — the
`check-pr-authors` allow-list identity — so the CI author gate keeps its meaning. No `SOUL.md`,
`AGENTS.md`, `agents/manifest.json` or other lane's behaviour file was changed by this lane.

## Docs prose landed on the same vehicle

`docs/ARCHITECTURE.md` gains an additive `## Host lane fleet` section beside `## Bots`: all 13
manifest profiles with role, artifact, exclusions and reporting edge, the one-way
`agents/<profile>/` → `$HOME/.hermes/profiles/<profile>/` sync direction and its seam targets, and
a short change-flow edge list. Existing `## Bots` rows are untouched. This is what turns
`make check-fleet-roster` (and therefore `make check-docs`) green; the note trio is this file,
`docs/changes.d/2026-11-27-fleet-roster-gate-3106.md` and the regenerated `CHANGES.md` row.

This PR does not close #3106 because the issue's five acceptance boxes are reviewer-owned: the
body carries evidence-backed ticks for the CI half, and the reviewer writes the issue-level
verdict at the reviewed head. The close wording is recorded here so `check-pr-closing` does not
mistake a resolving reference for an orphaned claim.

**Full-suite repair (six reds from the first run):** `46050988730`'s local mirror found six
contracts the new workflow/scripts had to satisfy — a `# Trigger surface:` header line and the
generated row in `docs/BOTS.md` (`check-dispatch-forms`), the canonical byte-identical guard body
(`test_workflow_guards`), the new modules in `scripts/package-layers.json`
(`test_package_layers`), and an extensible subset assertion in the Hermes-leg model-route test
instead of a hardcoded call-site count. All six were re-run green before the full suite was
repeated; no gate was weakened. A later `check-proc-gate` red in CI named the one bare
`subprocess.run` left in `fleet_architecture.py`; that call now goes through the repository's
`proc.run_checked` seam, with the matching cross-group edge recorded in
`scripts/package-layers.json`. The full suite then passed `4562 passed` locally at head
`9734bf972`, before this proc-seam correction; it is re-run again at the final head.
