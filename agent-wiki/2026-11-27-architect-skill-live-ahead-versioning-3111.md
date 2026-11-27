# Architect: version two live-only skill rules into the tree (#3111)

PR on branch `agents/3111-architect-skill-live-ahead`, cut from freshly fetched
`origin/main@4b1fcb2bbee47b57d697b96e8737089a00cde952`.

## What changed

- The architect lane's instruction file was live-ahead of the versioned tree at
  freshly fetched `origin/main@4b1fcb2bbee47b57d697b96e8737089a00cde952`.
- Two live-only paragraphs were versioned into the tree, plus a third rule learned
  while fixing this PR's own CI reds (gates-after-commit, `(#N)` claim rule); the
  tree copy is the canonical 103741 b and the live profile is synced tree→live.
  1. the "An architecture audit asks whether the DOC STATES THE OLD RULE" bullet was
     extended with the superseded-vs-live label check (a labelled historical quote is
     a legitimate change record; the same words unlabelled in a sibling lane's SOUL
     are a live false rule, filed as #3102) and the one-lane-scoped-grep follow-up
     lesson (a one-lane correction does not propagate).
  2. a new "Test a gate's COVERAGE by deleting its evidence in a temp archive, not
     by reading its code" bullet: remove the `## Host lane fleet` table rows in a
     temp archive and re-run `check_fleet_roster.py`, so a prose-masked roster gate
     cannot pass on inspection; plus the exception-predates-window test (the
     planner monitor contract predates the window, so #3110 moved no boundary).
- Nothing else in the file changed: only the three live-only rules were added or
  extended. No `/home/<user>` literal (#2145) — every path uses `$HOME`.

## Why it is versioned

The tree is canonical and `~/.hermes/profiles/<profile>/` is a one-way projection
(`agents/README.md`). The live-ahead paragraphs existed only in the live profile,
unreviewable and erasable by a sync. They now have a versioned home. Tree -> live:
`make sync-agent-profile PROFILE=llgenie-architect` was run after the tree copy was
made byte-identical; `CHECK=1` proved all 12 files match with no shrink (#919/#851).

## Verification

At each PR head (recorded in the #3111 correction comments with the CI run ids):
`HERMES_PROFILES_HOME="$HOME/.hermes/profiles" python3 scripts/check_agent_profiles.py check`
reports 0 findings for this path and 0 `SKIPPED`/`NOT compared` lines;
`make -s skills-validate` rc=0 (18 skills, 18 engines); `make -s check-docs` rc=0;
`cmp` tree-vs-live rc=0. Commit authored `Andy Holst <andy.holst@protonmail.com>`
(check-pr-authors allowlist).

## Not covered

One of three #3111 rows; the product-manager and pr-reviever rows are versioned by
their own lanes' PRs. No gate, workflow, standing-rule or other lane file changed.
This PR does not close #3111 — the three lane PRs must all land first.
