# 2026-11-20 — Code-review bot skips findings an open PR already fixes (issue #293, PR pending)

## What was verified against the spec

- `file_findings` now fetches the open-PR file map ONCE per run (`gh pr list --state open
  --json number,files` via the existing soft-gh helper) and skips filing when a finding's file
  is touched by an open PR, printing `already in flight: PR #N (<path>)`.
- Fixture proof (the measured #270-while-#277-was-open shape): open PR touching the finding's
  file -> zero `issue create` calls + the PR number named in the output; open PR touching only
  another file -> the finding IS filed; bare workflow names match PR path basenames; refused
  `pr list` -> WARNING + degradation NOTE on stderr, filing proceeds on marker dedupe alone.
- Live dry run (`python3 scripts/code_review.py file --repo asimov-agent/llgenie --dry`, rc=0,
  files nothing): the live open-PR fetch exercised; current scan yields one unfound-marker
  finding (`secrets-not-defined/RUN_TOKEN`) reported as `would file` — no open PR touches its
  workflows today, consistent with the in-flight map.
- Targeted battery 34/34 in `tests/test_code_review.py` (5 new pins + the verb-set pin updated:
  `pr list` joins the allowed READ verbs; write verbs stay forbidden).

## Key decisions

- Match accepts exact repo-relative paths AND basenames (the secrets check names files bare).
- Degradation direction: a refused PR listing never silently suppresses filing — it warns loudly
  and falls back to the marker memory (#312 loudness rule).
- The in-flight skip never consumes the per-run cap (it files nothing).

## Current status

OpenSpec change `reviewer-finding-dedupe` validated; unit battery queued; PR to `main` pending push.
