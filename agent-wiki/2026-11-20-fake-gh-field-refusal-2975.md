# 2026-11-20 — fake-gh field refusal: every bot fake answers --json like real gh (issue #2975)

Issue: #2975 (deferred end-to-end half of #515). Branch: `feat/fake-gh-field-refusal-2975`.

## What was verified against the spec

- **Shared seam** `tests/gh_fake.py`: `enforce(argv)` gates one fake-gh invocation against
  `tests/fixtures/gh-json-fields.json` (the roster the merged #515 guard landed); attribution mirrors
  `scripts/check_gh_json_fields.py`'s pr|issue|run roster, so `gh search`/`gh api` pass through.
  Refusal prints gh's own `Unknown JSON field: "<name>"` and exits 1. `preamble(tests_dir)` is the
  one install line for heredoc'd fakes; `python3 gh_fake.py "$@" || exit 1` is the bash-fake form.
- **Migration**: all 15 responder files (measured 2026-11-20; three files that only grep `--json`
  text out of scripts are not responders) carry the guard line — test_code_review,
  test_issue_refiner, test_rebase_bot_sweep, test_arms, test_holds, test_pr_reconcile_guard,
  test_arm_pr (bash), test_issue_implementer, test_auto_merge, test_check_pr_acceptance,
  test_pr_hygiene_commit_checkboxes, test_issue_cleaner, test_pr_body_write, test_queued_run_alarm,
  test_run_failure_reactor — each with one red pin asking the #513 `authorAssociation` shape and
  asserting its own fake refuses.
- **Re-home**: `tests/test_auto_merge.py`'s inline allowlist validation now reads the shared fixture
  through `gh_fake.load_allowlists()`; the pinned behaviour (subset assertion, `authorAssociation`
  absence, real-gh provenance) is unchanged. `scripts/auto_merge.py`'s constant comment and
  `docs/BOTS.md` carry the re-home note.
- Proofs measured this lane: `pytest tests/test_gh_fake.py` rc=0; per-family `pytest` rc=0
  (33+ passed code_review; 139 combined quartet; 36 trio; 270 remaining-quintet run; 93 quartet run);
  `make check-import-roots` rc=0 (bare `import gh_fake` stays inside the pytest rootdir).

## Key decisions

- Guard roster = pr|issue|run only (mirrors the #515 scanner); unguarded commands and fixture-absent
  pairs fail closed only inside the guarded roster.
- `tests/` is a pytest rootdir (prepend mode), so a bare `import gh_fake` needs no `sys.path.insert`
  and adds no new import root to the #1101 ratchet.
- The older `tests/fixtures/gh-pr-view-fields.json` stays on disk as history; the shared fixture is
  the forward roster for both the scan-time guard and the fakes.

## Current status

OpenSpec change `fake-gh-field-refusal` validated; full `make test-unit` proof runs at the
committed head before the PR closing #2975 is opened.
